#!/usr/bin/env python3
"""
Vorbereitung: aus den Befunden die Referenzdateien machen (Paket 4).

Ersetzt den externen Handschritt. Das Vorbereitungsmodell bekommt das
Analysepaket und liefert Glossar, Personen, Figurenblatt, Anrede,
Leitmotive, Stilprofil, Kapitelzeilen und einen Entwurf der drei
Anweisungsabschnitte.

    python3 vorbereitung.py
    python3 vorbereitung.py --nur-anzeigen      was ginge raus, was kostet es
    python3 vorbereitung.py --nur stilprofil    eine Lieferung nachziehen

Drei Entscheidungen, die nicht aussehen wie Zufall:

  - Der Volltext am Ende des Analysepakets bleibt draussen. 'Konkordanzen
    statt Volltext' ist in ENTSCHEIDUNGEN.md begruendet: 100.000 Woerter
    liegen im Bereich, in dem Modelle in der Mitte langer Kontexte
    nachweislich Information verlieren.
  - Je Lieferung ein eigener Aufruf, nicht eine grosse Antwort. Die
    Befunde stehen dabei im System-Prompt und sind damit ab dem zweiten
    Aufruf zwischengespeichert — acht kleine Aufrufe kosten weniger als
    einer, der acht Dateien auf einmal ausgibt, und jede Lieferung
    laesst sich einzeln pruefen und einzeln nachziehen.
  - Die Briefings kommen aus dem CODE-Verzeichnis, nicht aus dem
    Projektordner. Die Kopie im Projekt stammt vom letzten Testlauf und
    veraltet, sobald die Vorlage sich aendert.

Vorhandene Dateien werden nie ueberschrieben: Hat die Zieldatei Inhalt,
geht die Lieferung nach '<datei>.neu' — wie in konkordanz.py.
"""

import argparse
import json
import os
import re
import sys

import gemeinsam as G
import referenz_sync as R

CODE      = os.path.dirname(os.path.abspath(__file__))
VORSCHLAG = "anweisungen_vorschlag.md"
VOLLTEXT  = "\n---\n## Volltext"

ROLLE = (
    "Du bist Lektor und Uebersetzungsberater fuer literarische Prosa "
    "Niederlaendisch nach Deutsch. Du bekommst die Konkordanzbefunde zu "
    "einem Buch und lieferst daraus einzelne Vorbereitungsdateien.\n\n"
    "Antworte auf Deutsch. Gib AUSSCHLIESSLICH das Verlangte aus — bei "
    "JSON nur das JSON, ohne Codezaun, ohne Vorrede, ohne Kommentar. "
    "Erfinde nichts: Was die Befunde nicht hergeben, bleibt weg.")


# (Name, Zieldatei, Auftrag an das Modell, Formpruefung)
#
# Die Formpruefung ist dieselbe Frage, die der Leser im Prompt stellt.
# Ein Vorschlag in falscher Form wird nicht geschrieben, statt spaeter
# stillschweigend uebersprungen zu werden.
LIEFERUNGEN = [
    ("glossar", G.F["glossar"],
     "Liefere glossar.json: eine flache Abbildung NIEDERLAENDISCHES Wort "
     "-> deutsche Entsprechung, beide als Zeichenkette. Nur Eigennamen, "
     "Orts- und Sachbegriffe, die durchgehend gleich uebersetzt werden "
     "muessen. Kein Allgemeinwortschatz.\n"
     '{ "moestuin": "Gemüsegarten", "Ieper": "Ypern" }',
     lambda d: all(isinstance(k, str) and isinstance(v, str)
                   for k, v in d.items())),

    ("personen", G.F["personen"],
     "Liefere personen.json: flache Abbildung Figurenname -> Pronomen in "
     "der Form 'er/ihn' oder 'sie/sie'. Nur Figuren, die im Text handeln "
     "oder sprechen.\n"
     '{ "Bennett": "er/ihn", "Babette": "sie/sie" }',
     lambda d: bool(d) and all(isinstance(v, str) and v.strip()
                               for v in d.values())),

    ("figuren", G.F["figuren"],
     "Liefere figurenblatt.json: Abbildung Name -> Objekt mit 'pronomen', "
     "'rolle' (ein Halbsatz) und 'sprache' (wie die Figur spricht; leer "
     "lassen, wenn die Befunde nichts hergeben).\n"
     '{ "Bennett": { "pronomen": "er/ihn", "rolle": "Ich-Erzähler, '
     'Steinmetz", "sprache": "lakonisch, parataktisch" } }',
     lambda d: all(isinstance(v, dict) for v in d.values())),

    ("anrede", G.F["anrede"],
     "Liefere anrede.json: flache Abbildung Beziehungsname -> Objekt mit "
     "'figuren' (Liste), 'niederlaendisch', 'deutsch', 'hinweis'. Die "
     "Namen in 'figuren' so schreiben wie in personen.json; nur wenn eine "
     "davon im Abschnitt vorkommt, wird der Eintrag eingeblendet. Stuetze "
     "dich auf die Anredebelege.\n"
     '{ "Bennett zu Vorgesetzten": { "figuren": ["Bennett", "Dunn"], '
     '"niederlaendisch": "u", "deutsch": "Sie", "hinweis": "bleibt auch '
     'nach Jahren beim Sie" } }',
     lambda d: all(isinstance(v, dict) and "deutsch" in v
                   for v in d.values())),

    ("leitmotive", G.F["leitmotive"],
     "Liefere leitmotive.json: flache Abbildung NIEDERLAENDISCHE Wendung "
     "-> Objekt mit 'vorschlag', 'haeufigkeit', 'absicht'. Der Schluessel "
     "wird woertlich im Quelltext gesucht, muss also genau so im Original "
     "stehen. Nur Wendungen, deren Wiederholung Absicht ist.\n"
     '{ "geen flauw idee": { "vorschlag": "keine blasse Ahnung", '
     '"haeufigkeit": 12, "absicht": "Erzählerformel" } }',
     lambda d: all(isinstance(v, dict) and str(v.get("vorschlag", "")).strip()
                   for v in d.values())),

    ("stilprofil", G.F["stilprofil"],
     "Liefere stilprofil.json mit genau diesen Schluesseln: 'ton', "
     "'register', 'satzlaenge', 'tempus' (je eine Zeichenkette) und "
     "'perspektive' (Abbildung Erzaehlebene -> Person und Tempus). Das "
     "geht woertlich in den System-Prompt der Uebersetzung — knapp und "
     "anweisend, keine Literaturkritik.\n"
     '{ "ton": "lakonisch, parataktisch", "register": "…", '
     '"satzlaenge": "kurz, selten Hypotaxe", "tempus": "…", '
     '"perspektive": { "Rahmen 1919": "erste Person Präsens", '
     '"Kriegsrückblende": "erste Person Präteritum" } }',
     lambda d: bool(str(d.get("ton", "")).strip())),

    ("kapitel", G.F["kapitel"],
     "Liefere kapitel.json: flache Abbildung KAPITELUEBERSCHRIFT -> eine "
     "Zeile Zusammenfassung. Der Schluessel muss die Ueberschrift im "
     "WORTLAUT DER QUELLE sein, sonst findet die Pipeline sie nicht. Hat "
     "das Buch Datumszeilen statt Kapitelnamen, nimm die Datumszeilen.\n"
     '{ "23 augustus 1919": "Ankunft in Ypern, erste Nacht im Hotel" }',
     lambda d: all(isinstance(k, str) and isinstance(v, str)
                   for k, v in d.items())),
]

ANWEISUNGS_AUFTRAG = (
    "Liefere die Datei anweisungen.md mit genau den Abschnitten "
    "'## Übersetzung', '## Stillektorat' und '## Korrektorat'. Sie wird "
    "woertlich an die System-Prompts angehaengt: nur Anweisungen, keine "
    "Erlaeuterungen, keine HTML-Kommentare, kein Codezaun. Nutze die "
    "Befunde zu Figurensprache, geschuetzten Wiederholungen und falschen "
    "Freunden.")

# Die Bewertungen fehlen beim regulaeren Lauf, weil der Schritt vor dem
# Testlauf kommt — sie sind deshalb freiwillig. Laeuft die Vorbereitung
# spaeter noch einmal (nachgeschaerft, neues Sprachpaar), sind sie da und
# das beste Material im Paket: Befunde an echtem uebersetztem Text.
QUELLEN = [
    ("analysepaket.md",               None, "Konkordanzbefunde",      True),
    ("briefing_glossar_vorlage.md",   CODE, "Briefing Glossar",       False),
    ("briefing_bewertung_vorlage.md", CODE, "Briefing Uebersetzung",  False),
    ("bewertung_uebersetzung.md",     None, "Bewertung Uebersetzung", False),
    ("briefing_lektorat_vorlage.md",  CODE, "Briefing Lektorat",      False),
    ("bewertung_lektorat.md",         None, "Bewertung Lektorat",     False),
]


def lies(name, ordner=None):
    pfad = os.path.join(ordner, name) if ordner else name
    if not os.path.exists(pfad):
        return None
    return open(pfad, encoding="utf-8").read()


def paket_pruefen(inhalt):
    """Warnt, wenn das Analysepaket aus einem alten Lauf stammt."""
    hinweise = []
    for ueberschrift, was in (("Anredebelege", "Siez-Belege"),
                              ("Wiederkehrende Wendungen", "Wendungen")):
        m = re.search(rf"(?m)^## {re.escape(ueberschrift)}.*$", inhalt)
        if not m:
            hinweise.append(f"Abschnitt '{ueberschrift}' fehlt ganz")
            continue
        block = inhalt[m.end():].split("\n## ")[0]
        if not [z for z in block.splitlines() if z.startswith("- ")]:
            hinweise.append(f"'{ueberschrift}' ist leer — keine {was}")
    return hinweise


def befunde():
    teile, fehlend = [], []
    for name, ordner, titel, pflicht in QUELLEN:
        inhalt = lies(name, ordner)
        if inhalt is None:
            (fehlend.append(name) if pflicht else
             print(f"  {name}: fehlt, wird uebersprungen"))
            continue
        if name == "analysepaket.md":
            ganz = len(inhalt.split())
            inhalt = inhalt.split(VOLLTEXT)[0]
            weg = ganz - len(inhalt.split())
            print(f"  {name}: {len(inhalt.split())} Woerter"
                  + (f" (Volltext mit {weg} Woertern abgeschnitten)"
                     if weg else " (kein Volltext angehaengt)"))
            for h in paket_pruefen(inhalt):
                print(f"    WARNUNG: {h}")
        else:
            print(f"  {name}: {len(inhalt.split())} Woerter"
                  + (" [aus dem Code-Verzeichnis]" if ordner else ""))
        teile.append(f"# {titel}\n\n{inhalt}")
    if fehlend:
        sys.exit(f"\nFEHLER: {', '.join(fehlend)} fehlt.\n"
                 f"  Analysepaket erzeugen:  python3 konkordanz.py --extern")
    return "\n\n---\n\n".join(teile)


def json_lesen(antwort):
    """Nimmt auch eine Antwort mit Codezaun entgegen — das Modell haelt
    sich meistens daran, aber nicht immer."""
    text = antwort.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text)
    anfang, ende = text.find("{"), text.rfind("}")
    if anfang < 0 or ende < anfang:
        raise ValueError("keine JSON-Struktur in der Antwort")
    return json.loads(text[anfang:ende + 1])


def schreiben(pfad, inhalt):
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(inhalt)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, pfad)


def zieldatei(pfad):
    """Vorhandene Daten werden nicht ueberschrieben (Auftrag Paket 4)."""
    if os.path.exists(pfad) and G.lade_json(pfad, still=True):
        return pfad + ".neu", True
    return pfad, False


def anweisungen_gefuellt():
    return [n for n in ("Übersetzung", "Stillektorat", "Korrektorat")
            if G.lade_anweisungen(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-anzeigen", action="store_true",
                    help="zeigt Umfang und Kostenschaetzung, ruft kein Modell")
    ap.add_argument("--nur", default=None,
                    help="nur diese Lieferung (Name oder 'anweisungen')")
    args = ap.parse_args()

    namen = [l[0] for l in LIEFERUNGEN] + ["anweisungen"]
    if args.nur and args.nur not in namen:
        sys.exit(f"FEHLER: '{args.nur}' ist keine Lieferung.\n"
                 f"  Moeglich: {', '.join(namen)}")

    G.kopf("VORBEREITUNG")
    cfg = G.lade_config()
    print(f"Arbeitsverzeichnis: {os.getcwd()}")
    print(f"Code:               {CODE}\n")
    print("Quellen:")
    stoff = befunde()

    system = ROLLE + "\n\n# BEFUNDE ZU DIESEM BUCH\n\n" + stoff
    modell = G.modell_fuer(cfg, "vorbereitung")
    woerter = len(system.split())
    faktor = G.token_faktor()
    t = G.tarif(modell)

    offen = [l for l in LIEFERUNGEN if args.nur in (None, l[0])]
    mit_anweisungen = args.nur in (None, "anweisungen")
    anzahl = len(offen) + (1 if mit_anweisungen else 0)

    print(f"\nBefunde: {woerter} Woerter, geschaetzt "
          f"{woerter*faktor:,.0f} Token je Aufruf")
    print(f"Aufrufe: {anzahl} ({modell})")
    if t:
        # Ab dem zweiten Aufruf greift der Cache auf dem System-Prompt.
        eins = woerter * faktor * t["ein"] / 1e6
        print(f"Kosten:  rund {eins + 0.1 * eins * (anzahl - 1):.2f} $ "
              f"Eingabe — der erste Aufruf zahlt die Befunde, die "
              f"weiteren treffen den Cache")
    if args.nur_anzeigen:
        print("\nNur Anzeige — kein Modellaufruf.")
        return

    gefuellt = anweisungen_gefuellt()
    if gefuellt:
        print(f"\nHinweis: {G.ANWEISUNGEN} hat Inhalt in "
              f"{', '.join(gefuellt)} — die Datei wird nicht angetastet, "
              f"der Entwurf geht nach {VORSCHLAG}.")

    erzeugt, vorschlaege = [], []
    for name, datei, auftrag, pruef in offen:
        print(f"\n{name} …", flush=True)
        antwort = G.chat(cfg, system, auftrag, rolle="vorbereitung",
                         roh=True)
        try:
            daten = json_lesen(antwort)
        except Exception as e:
            print(f"  FEHLER: {e} — {datei} nicht geschrieben")
            continue
        if not isinstance(daten, dict) or not pruef(daten):
            print(f"  FEHLER: Form passt nicht zu dem, was die Pipeline "
                  f"liest — {datei} nicht geschrieben")
            continue
        ziel, ausweich = zieldatei(datei)
        schreiben(ziel, json.dumps(daten, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n")
        print(f"  {len(daten)} Eintraege -> {ziel}"
              + ("   (vorhandene Datei unangetastet)" if ausweich else ""))
        (vorschlaege if ausweich else erzeugt).append(ziel)

    if mit_anweisungen:
        print("\nanweisungen …", flush=True)
        antwort = G.chat(cfg, system, ANWEISUNGS_AUFTRAG,
                         rolle="vorbereitung", roh=True)
        ziel = VORSCHLAG if gefuellt else G.ANWEISUNGEN
        schreiben(ziel, antwort.rstrip() + "\n")
        print(f"  {len(antwort)} Zeichen -> {ziel}")
        (vorschlaege if gefuellt else erzeugt).append(ziel)

    print("\nUebernommen:  " + (", ".join(erzeugt) or "nichts"))
    if vorschlaege:
        print("Als Vorschlag: " + ", ".join(vorschlaege))
        print("  Vorhandene Daten wurden nicht ueberschrieben. Pruefen "
              "und von Hand uebernehmen.")

    if R.aktiv(cfg):
        print("\nsheets_id ist gesetzt — Uebertragung ins Spreadsheet:")
        try:
            R.erstbefuellung(cfg)
        except R.SyncFehler as e:
            print(f"  {e}")


if __name__ == "__main__":
    main()
