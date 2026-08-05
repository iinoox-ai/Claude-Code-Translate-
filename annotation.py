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


def teil_schreiben(j, befunde):
    """Zwischenstand eines Screening-Buendels.

    Der zweite und letzte Schreibweg dieses Moduls. Er fuehrt
    ausschliesslich nach teile/screening/ und schreibt ausschliesslich
    Befundlisten — kein Text des Buches liegt dort, und die Sperre oben
    bleibt damit das, was sie verspricht. Der Selbsttest prueft beides:
    dass dieser Weg nur dorthin fuehrt, und dass 'schreiben' weiterhin
    keine Textdatei annimmt."""
    G.teil_schreiben("screening", j,
                     json.dumps(befunde, ensure_ascii=False), "")


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
    """Die JSON-Struktur aus einer Antwort, Objekt oder Liste.

    Probiert wird in der Reihenfolge, in der die Klammern im Text
    vorkommen. Das ist kein Schoenheitsdetail: Bei einer Liste mit GENAU
    EINEM Objekt liegt die geschweifte Klammer innerhalb der eckigen, und
    wer zuerst auf '{' probiert, bekommt das Objekt statt der Liste
    zurueck. Der Aufrufer verwirft es dann, weil er eine Liste erwartet.

    Genau so hat das Screening jeden Befund verloren, der allein in
    seinem Buendel stand — bei mehreren Befunden schlug der Versuch fehl
    ('Extra data') und der zweite griff, bei einem einzigen nicht."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", t).strip()
    paare = [("{", "}"), ("[", "]")]
    stellen = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if stellen and t[min(stellen)] == "[":
        paare.reverse()
    for auf, zu in paare:
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


def chunkpaare(cfg):
    """(Nummer, Quelle, Fassung) je Chunk — dieselbe Einteilung wie der Lauf.

    Die Quellchunks kommen aus G.quellchunks_wie_lauf und nicht aus einem
    eigenen Nachbau. Der eigene Nachbau war hier bis August 2026 falsch:
    Er las den Rahmenmarker, waehrend der Lauf laengst ebenen.json las.
    Damit stand niederlaendischer Chunk 40 neben deutschem Chunk 43, und
    das Screening meldete Auslassungen, die keine waren — Befunde, die
    ein Mensch einzeln nachschlagen muss, um sie zu verwerfen."""
    st = G.lade_json("uebersetzung_state.json", still=True)
    n = int(st.get("total") or 0)
    if not n:
        return []
    _, chunks, _, _ = G.quellchunks_wie_lauf(cfg)
    paare = []
    for i in range(n):
        ziel = G.teil_lesen("lektorat", i, "") or G.teil_lesen(
            "uebersetzung", i, "")
        if ziel:
            paare.append((i + 1, chunks[i][0], ziel))
    return paare


def muster(x):
    """Schluessel, unter dem gleichlautende Befunde zusammenfallen.

    Ein wiederkehrender falscher Freund wird in jedem Buendel neu
    gemeldet, in dem er vorkommt. Ueber 37 Aufrufe wird daraus eine Liste,
    in die niemand mehr hineinsieht — und das ist derselbe Schaden, den
    der System-Prompt mit 'erfinde nichts' abwehren soll, nur von der
    anderen Seite.

    Verdichtet wird nur, was WOERTLICH gleich lautet. Aehnliches
    zusammenzuziehen hiesse raten, und ein faelschlich verschmolzener
    Befund verschwindet aus der Liste, ohne dass jemand ihn gesehen hat."""
    art = re.sub(r"\s+", " ", str(x.get("art", "")).strip().lower())
    bef = re.sub(r"\s+", " ", str(x.get("befund", "")).strip().lower())
    return art, bef.rstrip(".;:!? ")


def gedaechtnis(befunde, hoechstens=40):
    """Die bisher gemeldeten Muster als Prompt-Baustein, oder ''.

    Steht im USER-Prompt, nicht im System-Prompt: Der System-Prompt ist
    das zwischengespeicherte Praefix und ueber alle Aufrufe byteweise
    identisch. Ein wachsendes Gedaechtnis darin zerstoert die
    Cache-Trefferquote bei jedem Aufruf.

    Die Verdichtung im Bericht haengt nicht daran — sie laeuft lokal. Das
    hier spart Ausgabe und Aufmerksamkeit, mehr nicht: Ignoriert das
    Modell den Baustein, ist die Liste trotzdem sauber."""
    zaehler = {}
    for x in befunde:
        k = muster(x)
        zaehler[k] = zaehler.get(k, 0) + 1
    if not zaehler:
        return ""
    haeufig = sorted(zaehler.items(), key=lambda kv: -kv[1])[:hoechstens]
    zeilen = "\n".join(f"- [{a}] {b}" for (a, b), _ in haeufig)
    return ("=== BEREITS GEMELDET (nicht wiederholen) ===\n"
            "Diese Verdachtsstellen stehen schon in der Liste. Melde sie "
            "NICHT erneut, auch nicht fuer einen anderen Chunk — sie sind "
            "als wiederkehrend erfasst. Melde nur, was hier fehlt.\n"
            + zeilen + "\n\n")


def screenen(cfg, paare, drucken=print):
    """Befunde ueber alle Chunkpaare. Gibt (Befunde, uebersprungene Nummern).

    Ein gescheiterter Aufruf in der Mitte wurde frueher nur gedruckt und
    dann vergessen: Der Bericht sah vollstaendig aus, obwohl drei Buendel
    fehlten. Uebersprungene Chunks kommen deshalb zurueck und stehen im
    Bericht."""
    befunde, luecken = [], []
    buendel = [paare[i:i + CHUNKS_JE_AUFRUF]
               for i in range(0, len(paare), CHUNKS_JE_AUFRUF)]
    for j, teil in enumerate(buendel):
        # Resume wie beim Chunklauf: gezaehlt werden Dateien, nicht
        # Eintraege in einer Zustandsdatei. Ein abgebrochener Lauf hat
        # seine bisherigen Buendel schon bezahlt.
        alt = G.teil_lesen("screening", j, "")
        if alt is not None:
            try:
                befunde += json.loads(alt)
                continue
            except json.JSONDecodeError:
                pass
        stuecke = [f"### Chunk {nr}\n\nNIEDERLAENDISCH:\n{quelle}"
                   f"\n\nDEUTSCH:\n{ziel}" for nr, quelle, ziel in teil]
        drucken(f"  Chunk {teil[0][0]}–{teil[-1][0]} von {paare[-1][0]} …")
        try:
            antwort = G.chat(cfg, SYSTEM_SCREENING,
                             gedaechtnis(befunde) + "\n\n".join(stuecke),
                             rolle="screening", roh=True)
            d = json_lesen(antwort)
            neu = [x for x in d if isinstance(x, dict)] \
                if isinstance(d, list) else []
            teil_schreiben(j, neu)
            befunde += neu
        except Exception as e:
            drucken(f"    uebersprungen: {e}")
            luecken += [nr for nr, _, _ in teil]
            if j == 0:
                raise AlleFehlgeschlagen(str(e))
    return befunde, luecken


def screening_schreiben(befunde, luecken=()):
    gruppen = {}
    for x in befunde:
        gruppen.setdefault(muster(x), []).append(x)
    # Nach erstem Vorkommen sortiert: Wer die Liste durchgeht, liest sie
    # in der Reihenfolge des Buches.
    def erste(eintraege):
        return min(int(y.get("chunk", 0) or 0) for y in eintraege)

    reihen = sorted(gruppen.values(), key=erste)

    L = ["# Screening — Verdachtsstellen", "",
         "Ein Modell hat Quelle und Zielfassung nebeneinander gelesen. "
         "Die Liste ist **berichtend**:",
         "Sie verändert nichts und enthält Falschmeldungen. Prüfen, "
         "entscheiden, von Hand korrigieren.", "",
         f"{len(befunde)} Meldungen, zu {len(reihen)} Verdachtsstellen "
         f"zusammengefasst.",
         "Gleichlautende Meldungen stehen in einer Zeile; die Spalte "
         "`Chunks` nennt alle Fundstellen.", ""]
    if luecken:
        # Eine Luecke ist kein Nebensatz: Der Bericht sieht vollstaendig
        # aus, und niemand kaeme von selbst darauf, dass 12 Chunks gar
        # nicht geprueft wurden.
        L += [f"> **Nicht geprüft:** {len(luecken)} Chunks "
              f"({kurzliste(luecken)}). Die Aufrufe sind gescheitert.",
              "> `python3 annotation.py --nur screening` holt sie nach — "
              "die fertigen Bündel laufen nicht noch einmal.", ""]
    L += ["| Chunks | Anzahl | Art | Befund |", "|---|---:|---|---|"]
    for eintraege in reihen:
        art = str(eintraege[0].get("art", "")).replace("|", "\\|")
        bef = str(eintraege[0].get("befund", "")).replace(
            "|", "\\|").replace("\n", " ")
        nummern = sorted({int(y.get("chunk", 0) or 0) for y in eintraege})
        L.append(f"| {kurzliste(nummern)} | {len(eintraege)} | {art} "
                 f"| {bef} |")
    schreiben(SCREENING, "\n".join(L) + "\n")


def kurzliste(nummern, hoechstens=8):
    """Chunknummern als Zelle, ohne die Zeile zu sprengen."""
    n = sorted(set(int(x) for x in nummern))
    kopf = ", ".join(str(x) for x in n[:hoechstens])
    return kopf + (f" … (+{len(n) - hoechstens})" if len(n) > hoechstens
                   else "")


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
    paare = []
    if os.path.exists(G.F["quelle"]):
        try:
            paare = chunkpaare(cfg)
        except G.ChunksWeichenAb as e:
            # Kein Warnfall: Das Screening vergliche ab hier fremde
            # Absaetze und meldete Auslassungen, die keine sind. Solche
            # Befunde muss ein Mensch einzeln nachschlagen, um sie zu
            # verwerfen — das ist teurer als kein Bericht.
            sys.exit(f"FEHLER: {e}\n  Screening nicht moeglich. "
                     f"'--nur begruendungen' laeuft weiter.")

    fertig = sum(1 for j in range((len(paare) + CHUNKS_JE_AUFRUF - 1)
                                  // CHUNKS_JE_AUFRUF)
                 if G.teil_lesen("screening", j, "") is not None)
    offen = (len(paare) + CHUNKS_JE_AUFRUF - 1) // CHUNKS_JE_AUFRUF - fertig
    print(f"Substanzielle Aenderungen: {len(aenderungen)} "
          f"({(len(aenderungen) + BUENDEL - 1)//BUENDEL} Aufrufe)")
    print(f"Chunkpaare fuers Screening: {len(paare)} "
          f"({offen} Aufrufe offen"
          + (f", {fertig} liegen vor" if fertig else "") + ")")
    print(f"Modell Begruendungen: {m_beg}")
    print(f"Modell Screening:     {m_scr}")

    # Kostenschaetzung wie in vorbereitung.py — 'Kosten sind Teil des
    # Ergebnisses' gilt auch fuer den Schritt, der nur berichtet. Getrennt
    # je Rolle, weil die beiden Arbeiten verschiedene Modelle haben
    # duerfen und die Summe sonst nichts mehr aussagt.
    faktor = G.token_faktor()
    # Geschaetzt wird, was noch laeuft: Fertige Buendel liegen in teile/
    # und kosten nichts mehr. Die Quellwoerter sind jetzt gezaehlt statt
    # geschaetzt — vorher stand dort die Zielseite mal zwei.
    anteil = offen / max(1, fertig + offen)
    summe, unsicher = 0.0, False
    for label, modell, ein, aus in (
            ("Begruendungen", m_beg,
             sum(len((a["alt"] + a["neu"] + a["kontext"]).split())
                 for a in aenderungen) * faktor,
             len(aenderungen) * 15 * faktor),
            ("Screening", m_scr,
             sum(len(q.split()) + len(z.split()) for _, q, z in paare)
             * faktor * anteil,
             offen * 60 * faktor)):
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
        try:
            befunde, luecken = screenen(cfg, paare)
        except AlleFehlgeschlagen as e:
            sys.exit(f"\nAbbruch: schon der erste Aufruf ist gescheitert "
                     f"— {e}\n  Nichts wurde geschrieben.")
        screening_schreiben(befunde, luecken)
        stellen = len({muster(x) for x in befunde})
        print(f"  {len(befunde)} Meldungen zu {stellen} Verdachtsstellen "
              f"-> {SCREENING}")
        if luecken:
            print(f"  WARNUNG: {len(luecken)} Chunks nicht geprüft "
                  f"({kurzliste(luecken)}).\n"
                  f"           Erneut aufrufen holt sie nach; die fertigen "
                  f"Bündel laufen nicht noch einmal.")

    print(f"\nDer Schritt hat nichts am Text geaendert — er darf es nicht.")


if __name__ == "__main__":
    main()
