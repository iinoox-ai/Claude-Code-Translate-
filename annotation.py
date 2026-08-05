#!/usr/bin/env python3
"""
Annotation und Volltext-Screening (Paket 7).

Zwei nachgelagerte Berichte, die den Text NICHT anfassen. Sie laufen unter
ZWEI Rollen, weil es zwei verschiedene Arbeiten sind — die Belegung steht
in projekt.json, die Begruendung in gemeinsam.EMPFEHLUNG:

  1. Begruendungen (Rolle 'begruendung'): je substanzieller
     Lektoratsaenderung eine Zeile,
     warum sie sinnvoll ist. Landet in begruendungen.json und von dort
     als Spalte in bericht.html.
  2. Screening (Rolle 'screening'): ein Durchgang ueber das ganze Buch,
     Quell- gegen
     Zielchunk, der Verdachtsstellen meldet — uebersehene falsche
     Freunde, Auslassungen, Registerbrueche. Landet in
     screening_review.md.

    python3 annotation.py
    python3 annotation.py --nur-anzeigen
    python3 annotation.py --nur begruendungen
    python3 annotation.py --nur screening

Der Schritt ist rein berichtend. Das ist keine Zurueckhaltung, sondern
der Grund, warum es ihn gibt: Ein weiterer Editierpass waere ein
weiterer Pass, der glaettet. Ein Bericht kann nur uebersehen werden, er
kann nichts kaputt machen.

Damit das nicht bloss eine Absichtserklaerung bleibt, geht jeder
Schreibzugriff durch schreiben() — und die Funktion kennt genau zwei
erlaubte Ziele. Der Selbsttest prueft, dass keine Textdatei darunter
ist.

Typografie und reine Interpunktion werden nicht annotiert: Sie stammen
aus dem deterministischen Durchgang und haben keine Begruendung ausser
'so ist die Regel'.
"""

import argparse
import hashlib
import json
import os
import re
import sys

import gemeinsam as G

BEGRUENDUNGEN = "begruendungen.json"
SCREENING     = "screening_review.md"

# Die EINZIGEN Dateien, die dieser Schritt schreiben darf.
SCHREIBBAR = {BEGRUENDUNGEN, SCREENING}

# Nur substanzielle Kategorien. Typografie und Interpunktion nicht.
SUBSTANZIELL = ("Wort", "Wendung", "Teilsatz", "Umbau", "Absatz")

BUENDEL = 20          # Aenderungen je Aufruf
CHUNKS_JE_AUFRUF = 4  # Chunkpaare je Screening-Aufruf

SYSTEM_BEGRUENDUNG = (
    "Du erklaerst Lektoratsentscheidungen an einer literarischen "
    "Uebersetzung Niederlaendisch nach Deutsch.\n\n"
    "Zu jeder Aenderung eine einzige knappe Zeile: Warum ist die neue "
    "Fassung besser — oder warum ist sie es nicht? Sag es klar, wenn eine "
    "Aenderung ueberfluessig oder schaedlich aussieht; das ist der "
    "eigentliche Nutzen dieser Liste.\n\n"
    "Keine Wiederholung des Diffs, keine Floskeln. Antworte als "
    "JSON-Objekt: Schluessel ist die 'id' der Aenderung, Wert die Zeile.\n"
    '{ "a1b2c3d4": "»laufen« war hier gehen — falscher Freund behoben" }')

SYSTEM_SCREENING = (
    "Du liest Abschnitte eines niederlaendischen Originals neben der "
    "deutschen Fassung und meldest Verdachtsstellen.\n\n"
    "Worauf es ankommt: uebersehene falsche Freunde, ausgelassene oder "
    "hinzugefuegte Inhalte, Registerbrueche (die Erzaehlstimme wird "
    "gehoben), mechanisch uebertragene Konstruktionen.\n\n"
    "Melde nur, was du wirklich siehst. Eine leere Liste ist ein gutes "
    "Ergebnis; erfundene Befunde machen die Liste wertlos, weil dann "
    "niemand mehr hineinsieht.\n\n"
    "Antworte als JSON: eine Liste von Objekten mit 'chunk' (Zahl), "
    "'art' und 'befund' (eine Zeile).\n"
    '[ { "chunk": 12, "art": "falscher Freund", '
    '"befund": "»lopen« als »laufen« statt »gehen«" } ]')


class SchreibSperre(Exception):
    """Der Schritt hat versucht, eine Datei anzufassen, die ihm nicht
    gehoert."""


def schreiben(pfad, inhalt):
    """Der einzige Schreibweg dieses Moduls.

    Die Sperre ist kein Misstrauen gegen den Code von heute, sondern
    gegen den von uebermorgen: Wer hier eine Zeile ergaenzt, die eine
    Textdatei anfasst, bekommt eine Ausnahme statt eines stillen
    Ueberschreibens."""
    if os.path.basename(pfad) not in SCHREIBBAR:
        raise SchreibSperre(
            f"annotation.py darf {pfad} nicht schreiben. Erlaubt sind nur "
            f"{', '.join(sorted(SCHREIBBAR))} — der Schritt ist berichtend.")
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(inhalt)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, pfad)


def kennung(chunk, kat, alt, neu):
    """Stabiler Schluessel je Aenderung — auch nach einem zweiten Lauf."""
    roh = f"{chunk}|{kat}|{alt}|{neu}"
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:8]


def aenderungen_lesen(diffdatei, kontext=7):
    """Substanzielle Aenderungen aus dem Lektoratsdiff."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import diffview as D
    raus = []
    for chunk, name, vorher, nachher in D.read_difffile(diffdatei):
        for a, b in D.align(vorher, nachher):
            for kat, links, alt, neu, rechts in D.changes(a, b, kontext):
                if kat not in SUBSTANZIELL:
                    continue
                raus.append({"id": kennung(chunk, kat, alt, neu),
                             "chunk": chunk, "pass": name, "kat": kat,
                             "alt": alt, "neu": neu,
                             "kontext": f"…{links} ▸◂ {rechts}…"})
    return raus


def json_lesen(text):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", t)
    for auf, zu in (("{", "}"), ("[", "]")):
        a, e = t.find(auf), t.rfind(zu)
        if a >= 0 and e > a:
            try:
                return json.loads(t[a:e + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("keine JSON-Struktur in der Antwort")


class AlleFehlgeschlagen(RuntimeError):
    """Der erste Aufruf ging schief — die anderen gehen genauso schief.

    Ohne diesen Abbruch laeuft der Schritt 61-mal in denselben Fehler,
    schreibt eine leere Datei und meldet 'fertig'."""


def begruenden(cfg, aenderungen):
    fertig = {}
    for i in range(0, len(aenderungen), BUENDEL):
        buendel = aenderungen[i:i + BUENDEL]
        frage = "\n\n".join(
            f"id {a['id']} [{a['kat']}, Chunk {a['chunk']}, {a['pass']}]\n"
            f"  vorher:  {a['alt']}\n  nachher: {a['neu']}\n"
            f"  Umfeld:  {a['kontext']}" for a in buendel)
        print(f"  {i+1}–{i+len(buendel)} von {len(aenderungen)} …",
              flush=True)
        try:
            antwort = G.chat(cfg, SYSTEM_BEGRUENDUNG, frage,
                             rolle="begruendung", roh=True)
            d = json_lesen(antwort)
            if isinstance(d, dict):
                fertig.update({k: str(v) for k, v in d.items()})
        except Exception as e:
            print(f"    uebersprungen: {e}")
            if i == 0:
                raise AlleFehlgeschlagen(str(e))
    return fertig


def chunkpaare():
    """Quell- und Zielchunk nebeneinander, aus den abgelegten Teilen."""
    st = G.lade_json("uebersetzung_state.json", still=True)
    n = int(st.get("total") or 0)
    if not n:
        return []
    paare = []
    for i in range(n):
        ziel = G.teil_lesen("lektorat", i, "") or G.teil_lesen(
            "uebersetzung", i, "")
        if ziel:
            paare.append((i + 1, ziel))
    return paare


def screenen(cfg, quelle_chunks, paare):
    befunde = []
    for i in range(0, len(paare), CHUNKS_JE_AUFRUF):
        teil = paare[i:i + CHUNKS_JE_AUFRUF]
        stuecke = []
        for nr, ziel in teil:
            quelle = quelle_chunks.get(nr, "")
            stuecke.append(f"### Chunk {nr}\n\nNIEDERLAENDISCH:\n{quelle}"
                           f"\n\nDEUTSCH:\n{ziel}")
        print(f"  Chunk {teil[0][0]}–{teil[-1][0]} von {paare[-1][0]} …",
              flush=True)
        try:
            antwort = G.chat(cfg, SYSTEM_SCREENING, "\n\n".join(stuecke),
                             rolle="screening", roh=True)
            d = json_lesen(antwort)
            if isinstance(d, list):
                befunde += [x for x in d if isinstance(x, dict)]
        except Exception as e:
            print(f"    uebersprungen: {e}")
            if i == 0:
                raise AlleFehlgeschlagen(str(e))
    return befunde


def screening_schreiben(befunde):
    L = ["# Screening — Verdachtsstellen", "",
         "Ein Modell hat Quelle und Zielfassung nebeneinander gelesen. "
         "Die Liste ist **berichtend**:",
         "Sie verändert nichts und enthält Falschmeldungen. Prüfen, "
         "entscheiden, von Hand korrigieren.", "",
         f"{len(befunde)} Verdachtsstellen.", "",
         "| Chunk | Art | Befund |", "|---:|---|---|"]
    for x in sorted(befunde, key=lambda y: int(y.get("chunk", 0) or 0)):
        art = str(x.get("art", "")).replace("|", "\\|")
        bef = str(x.get("befund", "")).replace("|", "\\|").replace("\n", " ")
        L.append(f"| {x.get('chunk', '?')} | {art} | {bef} |")
    schreiben(SCREENING, "\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-anzeigen", action="store_true")
    ap.add_argument("--nur", choices=["begruendungen", "screening"],
                    default=None)
    args = ap.parse_args()

    G.kopf("ANNOTATION")
    cfg = G.lade_config()
    print(f"Arbeitsverzeichnis: {os.getcwd()}\n")
    m_beg = G.modell_fuer(cfg, "begruendung")
    m_scr = G.modell_fuer(cfg, "screening")

    diffdatei = "lektorat_diff.txt"
    aenderungen = (aenderungen_lesen(diffdatei)
                   if os.path.exists(diffdatei) else [])
    quelle_chunks, paare = {}, []
    if os.path.exists(G.F["quelle"]):
        paare = chunkpaare()

    print(f"Substanzielle Aenderungen: {len(aenderungen)} "
          f"({(len(aenderungen) + BUENDEL - 1)//BUENDEL} Aufrufe)")
    print(f"Chunkpaare fuers Screening: {len(paare)} "
          f"({(len(paare) + CHUNKS_JE_AUFRUF - 1)//CHUNKS_JE_AUFRUF} "
          f"Aufrufe)")
    print(f"Modell Begruendungen: {m_beg}")
    print(f"Modell Screening:     {m_scr}")

    # Kostenschaetzung wie in vorbereitung.py — 'Kosten sind Teil des
    # Ergebnisses' gilt auch fuer den Schritt, der nur berichtet. Getrennt
    # je Rolle, weil die beiden Arbeiten verschiedene Modelle haben
    # duerfen und die Summe sonst nichts mehr aussagt.
    faktor = G.token_faktor()
    summe, unsicher = 0.0, False
    for label, modell, ein, aus in (
            ("Begruendungen", m_beg,
             sum(len((a["alt"] + a["neu"] + a["kontext"]).split())
                 for a in aenderungen) * faktor,
             len(aenderungen) * 15 * faktor),
            ("Screening", m_scr,
             sum(len(z.split()) for _, z in paare) * 2 * faktor,
             len(paare) // CHUNKS_JE_AUFRUF * 60 * faktor)):
        d = G.kosten_dollar({"ein": ein, "aus": aus}, G.tarif(modell))
        if d is None:
            unsicher = True
            continue
        summe += d
        print(f"Kosten {label}: rund {d:.2f} $ "
              f"({ein:,.0f} Token ein, {aus:,.0f} aus)")
    print(f"Kosten zusammen: rund {summe:.2f} $"
          + ("  (unvollstaendig, Tarif unbekannt)" if unsicher else ""))
    print()
    if args.nur_anzeigen:
        print("Nur Anzeige — kein Modellaufruf.")
        return

    if args.nur in (None, "begruendungen") and aenderungen:
        print("Begruendungen:")
        alt = G.lade_json(BEGRUENDUNGEN, still=True)
        offen = [a for a in aenderungen if a["id"] not in alt]
        print(f"  {len(alt)} liegen vor, {len(offen)} offen")
        try:
            alt.update(begruenden(cfg, offen))
        except AlleFehlgeschlagen as e:
            sys.exit(f"\nAbbruch: schon der erste Aufruf ist gescheitert "
                     f"— {e}\n  Nichts wurde geschrieben.")
        schreiben(BEGRUENDUNGEN, json.dumps(alt, ensure_ascii=False,
                                            indent=2, sort_keys=True) + "\n")
        print(f"  {len(alt)} Begruendungen -> {BEGRUENDUNGEN}")

    if args.nur in (None, "screening") and paare:
        print("\nScreening:")
        text = open(G.F["quelle"], encoding="utf-8").read()
        gruppen = G.rahmen_gruppen(G.absaetze(text), cfg["rahmen_marker"])
        chunks = []
        for gruppe in gruppen:
            chunks += G.chunks_bauen(gruppe, cfg["chunk_words"])
        quelle_chunks = {i + 1: t for i, (t, _) in enumerate(chunks)}
        try:
            befunde = screenen(cfg, quelle_chunks, paare)
        except AlleFehlgeschlagen as e:
            sys.exit(f"\nAbbruch: schon der erste Aufruf ist gescheitert "
                     f"— {e}\n  Nichts wurde geschrieben.")
        screening_schreiben(befunde)
        print(f"  {len(befunde)} Verdachtsstellen -> {SCREENING}")

    print(f"\nDer Schritt hat nichts am Text geaendert — er darf es nicht.")


if __name__ == "__main__":
    main()
