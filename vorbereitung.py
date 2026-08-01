#!/usr/bin/env python3
"""
Vorbereitung: aus den Befunden einen Vorschlag fuer anweisungen.md machen.

Sammelt, was Konkordanzanalyse und Testlauf gefunden haben, laesst das
Vorbereitungsmodell daraus die drei Anweisungsabschnitte schreiben und
legt das Ergebnis als VORSCHLAG ab. Eingespielt wird nur vom Menschen.

    python3 vorbereitung.py
    python3 vorbereitung.py --nur-anzeigen    was ginge raus, was kostet es
    python3 vorbereitung.py --ausgabe datei.md

Zwei Entscheidungen, die nicht aussehen wie Zufall:

  - Der Volltext am Ende des Analysepakets bleibt draussen. 'Konkordanzen
    statt Volltext' ist in ENTSCHEIDUNGEN.md begruendet: 100.000 Woerter
    liegen im Bereich, in dem Modelle in der Mitte langer Kontexte
    nachweislich Information verlieren.
  - Die Briefings kommen aus dem CODE-Verzeichnis, nicht aus dem
    Projektordner. Die Kopie im Projekt stammt vom letzten Testlauf und
    veraltet, sobald die Vorlage sich aendert — das ist genau einmal
    passiert und hat eine Auswertung mit falschen Vorgaben gekostet.

anweisungen.md wird nie ueberschrieben (Auftrag Paket 4).
"""

import argparse
import os
import re
import sys

import gemeinsam as G

CODE     = os.path.dirname(os.path.abspath(__file__))
AUSGABE  = "anweisungen_vorschlag.md"
VOLLTEXT = "\n---\n## Volltext"

SYSTEM = (
    "Du bist Lektor und Uebersetzungsberater fuer literarische Prosa "
    "Niederlaendisch nach Deutsch. Antworte auf Deutsch, knapp und konkret.\n\n"
    "Liefere die verlangte anweisungen.md vollstaendig als Codeblock, mit "
    "den Abschnitten '## Übersetzung', '## Stillektorat' und "
    "'## Korrektorat'. Sie wird woertlich an die System-Prompts angehaengt: "
    "nur Anweisungen, keine Erlaeuterungen, keine HTML-Kommentare.\n\n"
    "Nutze die Konkordanzbefunde fuer Figurensprache, zu schuetzende "
    "Wiederholungen und falsche Freunde.\n\n"
    "Schlage ausserdem anrede.json und leitmotive.json vor, jeweils als "
    "eigenen Codeblock. Halte dich genau an diese Formen — die Pipeline "
    "liest sie so und ueberspringt stillschweigend alles, was anders "
    "aufgebaut ist:\n\n"
    "anrede.json — flache Abbildung Beziehungsname -> Objekt. 'figuren' "
    "nennt die Namen so, wie sie im Text und in personen.json stehen; nur "
    "wenn eine davon im Chunk vorkommt, wird der Eintrag eingeblendet:\n"
    '{\n'
    '  "Scott zu Vorgesetzten": {\n'
    '    "figuren": ["Scott", "Dunn"],\n'
    '    "niederlaendisch": "u",\n'
    '    "deutsch": "Sie",\n'
    '    "hinweis": "bleibt auch nach Jahren beim Sie"\n'
    '  }\n'
    '}\n\n'
    "leitmotive.json — flache Abbildung NIEDERLAENDISCHE Wendung -> "
    "Objekt. Der Schluessel wird woertlich im Quellchunk gesucht, muss "
    "also genau so im Original stehen:\n"
    '{\n'
    '  "deze hele rotzooi": {\n'
    '    "vorschlag": "dieser ganze Schlamassel",\n'
    '    "haeufigkeit": 7,\n'
    '    "absicht": "wiederkehrende Formel des Erzaehlers"\n'
    '  }\n'
    '}\n\n'
    "Keine Listen auf oberster Ebene, keine Sammelschluessel wie "
    "'paare' oder 'leitmotive'.")

# (Datei, Verzeichnis, Ueberschrift im Prompt, Pflicht)
QUELLEN = [
    ("analysepaket.md",               None, "Konkordanzbefunde",      True),
    ("briefing_bewertung_vorlage.md", CODE, "Briefing Uebersetzung",  True),
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
    """Warnt, wenn das Analysepaket aus einem alten Lauf stammt.

    Ein leerer Anredeabschnitt war ein echter Fehler und ist behoben —
    eine Datei von davor traegt ihn aber weiter, und der Auswertungslauf
    kostet Geld. Lieber vorher fragen."""
    hinweise = []
    for ueberschrift, was in (("Anredebelege", "Siez-Belege"),
                              ("Wiederkehrende Wendungen", "Wendungen")):
        m = re.search(rf"(?m)^## {re.escape(ueberschrift)}.*$", inhalt)
        if not m:
            hinweise.append(f"Abschnitt '{ueberschrift}' fehlt ganz")
            continue
        rest = inhalt[m.end():]
        block = rest.split("\n## ")[0]
        n = len([z for z in block.splitlines() if z.startswith("- ")])
        if n == 0:
            hinweise.append(f"'{ueberschrift}' ist leer — keine {was}")
    return hinweise


def zusammenstellen():
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-anzeigen", action="store_true",
                    help="zeigt Umfang und Kostenschaetzung, ruft kein Modell")
    ap.add_argument("--ausgabe", default=AUSGABE)
    args = ap.parse_args()

    G.kopf("VORBEREITUNG")
    cfg = G.lade_config()
    print(f"Arbeitsverzeichnis: {os.getcwd()}")
    print(f"Code:               {CODE}\n")
    print("Quellen:")
    user = zusammenstellen()

    modell = G.modell_fuer(cfg, "vorbereitung")
    woerter = len(user.split())
    faktor = G.token_faktor()
    t = G.tarif(modell)
    print(f"\nZusammen: {woerter} Woerter, geschaetzt "
          f"{woerter*faktor:,.0f} Token")
    if t:
        print(f"Kosten:   rund {woerter*faktor*t['ein']/1e6:.2f} $ Eingabe "
              f"({modell})")
    if args.nur_anzeigen:
        print("\nNur Anzeige — kein Modellaufruf.")
        return

    if os.path.exists(G.ANWEISUNGEN):
        gefuellt = [n for n in ("Übersetzung", "Stillektorat", "Korrektorat")
                    if G.lade_anweisungen(n)]
        if gefuellt:
            print(f"\nHinweis: {G.ANWEISUNGEN} hat bereits Inhalt in "
                  f"{', '.join(gefuellt)}.\n         Sie wird nicht "
                  f"angetastet — der Vorschlag geht nach {args.ausgabe}.")

    print(f"\n{modell} arbeitet ...", flush=True)
    antwort = G.chat(cfg, SYSTEM, user, 0.0, rolle="vorbereitung", roh=True)
    if not antwort.strip():
        sys.exit("FEHLER: leere Antwort.")

    tmp = args.ausgabe + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(antwort + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, args.ausgabe)

    bloecke = len(re.findall(r"(?m)^```", antwort)) // 2
    print(f"\nFertig: {args.ausgabe} ({len(antwort)} Zeichen, "
          f"{bloecke} Codebloecke)")
    print(f"\nJetzt lesen und uebernehmen, was stimmt:")
    print(f"  - die drei Abschnitte nach {G.ANWEISUNGEN}")
    print(f"  - Vorschlaege fuer {G.F['anrede']} und {G.F['leitmotive']}")
    print(f"\nEingespielt wird nur von Hand. Das Skript schreibt "
          f"{G.ANWEISUNGEN} nie.")


if __name__ == "__main__":
    main()
