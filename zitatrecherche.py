#!/usr/bin/env python3
"""
Zitatrecherche: fuer jedes erkannte Zitat den etablierten deutschen
Wortlaut suchen — und ihn NICHT einsetzen (Paket 6).

    python3 zitatrecherche.py
    python3 zitatrecherche.py --nur-anzeigen   was recherchiert wuerde
    python3 zitatrecherche.py --uebernehmen    Freigaben einlesen

Ablauf je Zitat: Sprache bestimmen. Ist sie nicht Niederlaendisch, bleibt
das Zitat unveraendert stehen (Status 'original_belassen') — ein
englisches Motto in einem niederlaendischen Roman ist auch im Deutschen
englisch. Sonst wird die anerkannte Uebersetzung gesucht, mit
Uebersetzer, Fundstelle und Konfidenz.

Der Vorschlag geht in eine Review-Liste, nicht in den Text. Eingesetzt
wird ausschliesslich, was ein Mensch mit 'freigegeben = ja' versehen hat.
Der Grund steht in ENTSCHEIDUNGEN.md: Abdruckrechte etablierter
Uebersetzungen, und 'lieber markierte Luecke als erfundener Wortlaut'.
Ein rueckuebersetztes Motto erzeugt einen Satz, den der zitierte Autor
nie geschrieben hat.
"""

import argparse
import json
import os
import re
import sys

import gemeinsam as G
import referenz_sync as R

REVIEW = "zitate_review.md"
TAB = "ZitateReview"

# Serverseitige Websuche. Ohne sie raet das Modell einen Wortlaut
# zusammen, und genau das ist der Fehler, den dieser Schritt verhindern
# soll — die Suche ist kein Beiwerk, sie ist der Zweck.
WERKZEUGE = [{"type": "web_search_20250305", "name": "web_search",
              "max_uses": 6}]

SYSTEM = (
    "Du recherchierst Zitatnachweise fuer eine literarische Uebersetzung "
    "Niederlaendisch nach Deutsch.\n\n"
    "Regeln:\n"
    "1. Bestimme zuerst die Sprache des Zitats.\n"
    "2. Ist sie NICHT Niederlaendisch, bleibt das Zitat unveraendert — "
    "ein englisches oder franzoesisches Motto steht auch in der deutschen "
    "Ausgabe im Original. Status 'original_belassen', kein Vorschlag.\n"
    "3. Sonst: Suche die anerkannte deutsche Uebersetzung. Nenne "
    "Uebersetzer, Ausgabe oder Fundstelle und eine Konfidenz von 0 bis 1.\n"
    "4. Findest du keine belegte Fassung, sage das. Erfinde NICHTS und "
    "uebersetze NICHT selbst — ein zurueckuebersetztes Zitat ist ein Satz, "
    "den der Autor nie geschrieben hat, und das faellt im Druck auf.\n\n"
    "Antworte ausschliesslich mit einem JSON-Objekt:\n"
    '{ "sprache": "niederlaendisch", "status": "gefunden", '
    '"vorschlag_de": "…", "uebersetzer": "…", "quelle": "…", '
    '"konfidenz": 0.8, "begruendung": "ein Satz" }\n\n'
    "Erlaubte Werte fuer 'status': 'gefunden', 'original_belassen', "
    "'nicht_gefunden'.")

SPALTEN = ["index", "sprache", "original", "vorschlag_de", "uebersetzer",
           "quelle", "konfidenz", "freigegeben"]

# Unterhalb dieser Konfidenz gilt der Vorschlag als unsicher und wird in
# der Liste als solcher markiert. Er wird trotzdem gezeigt — der Mensch
# entscheidet, nicht die Schwelle.
SCHWELLE = 0.6


def zitate_lesen():
    d = G.lade_json(G.F["zitate"], still=True)
    return d, d.get("epigraphen", [])


def zitate_schreiben(d):
    tmp = G.F["zitate"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, G.F["zitate"])


def antwort_lesen(text):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", t)
    a, e = t.find("{"), t.rfind("}")
    if a < 0 or e < a:
        raise ValueError("keine JSON-Struktur in der Antwort")
    return json.loads(t[a:e + 1])


def recherchieren(cfg, z):
    """Ein Aufruf je Zitat. Gibt den Befund als Abbildung zurueck."""
    frage = (f"Zitat:\n{z['text']}\n\n"
             f"Attributionszeile im Buch: {z.get('attribution', '')}\n\n"
             f"Bestimme die Sprache und liefere den Befund als JSON.")
    antwort = G.chat(cfg, SYSTEM, frage, 0.0, rolle="zitat", roh=True,
                     werkzeuge=WERKZEUGE)
    return antwort_lesen(antwort)


def uebernehmen(z, befund):
    """Traegt den Befund in den Zitateintrag — ohne 'original_deutsch'.

    Das Feld, das uebersetzung.py einsetzt, bleibt leer. Es wird
    ausschliesslich von freigabe_einlesen() gefuellt, und nur wenn ein
    Mensch freigegeben hat. Diese Trennung ist der ganze Punkt des
    Schritts."""
    z["sprache"] = str(befund.get("sprache", "")).strip()
    z["status"] = str(befund.get("status", "nicht_gefunden")).strip()
    z["vorschlag_de"] = str(befund.get("vorschlag_de", "") or "").strip()
    z["uebersetzer"] = str(befund.get("uebersetzer", "") or "").strip()
    z["quelle"] = str(befund.get("quelle", "") or "").strip()
    try:
        z["konfidenz"] = round(float(befund.get("konfidenz", 0)), 2)
    except (TypeError, ValueError):
        z["konfidenz"] = 0.0
    z["begruendung"] = str(befund.get("begruendung", "") or "").strip()
    if z["status"] == "original_belassen":
        # Das Original ist der Zieltext. Kein Vorschlag, keine Freigabe
        # noetig — hier gibt es nichts zu entscheiden.
        z["original_deutsch"] = z["text"]
        z["freigegeben"] = "entfaellt"
    else:
        z.setdefault("freigegeben", "nein")
    return z


def zeilen(epigraphen):
    raus = []
    for z in epigraphen:
        raus.append([str(z.get("index", "")), z.get("sprache", ""),
                     z.get("text", "")[:300], z.get("vorschlag_de", ""),
                     z.get("uebersetzer", ""), z.get("quelle", ""),
                     str(z.get("konfidenz", "")),
                     str(z.get("freigegeben", "nein"))])
    return raus


def review_schreiben(epigraphen):
    L = ["# Zitate — Freigabe", "",
         "Eingesetzt wird ausschliesslich, was in der Spalte "
         "`freigegeben` ein `ja` traegt.",
         "Ohne Freigabe bleibt an der Stelle eine markierte Luecke.",
         "Zitate mit Status `original_belassen` brauchen keine Freigabe — "
         "sie stehen im Original.", "",
         "| " + " | ".join(SPALTEN) + " |",
         "|" + "---|" * len(SPALTEN)]
    for z in zeilen(epigraphen):
        L.append("| " + " | ".join(x.replace("|", "\\|").replace("\n", " ")
                                   for x in z) + " |")
    L += ["", "## Befunde im Einzelnen", ""]
    for z in epigraphen:
        L.append(f"### Absatz {z.get('index')} — {z.get('attribution','')}")
        L.append(f"- Original: {z.get('text','')[:400]}")
        L.append(f"- Sprache: {z.get('sprache','?')}, "
                 f"Status: {z.get('status','offen')}, "
                 f"Konfidenz: {z.get('konfidenz','?')}")
        if z.get("vorschlag_de"):
            L.append(f"- Vorschlag: {z['vorschlag_de']}")
            L.append(f"- Uebersetzer: {z.get('uebersetzer','?')}")
            L.append(f"- Quelle: {z.get('quelle','?')}")
        if z.get("begruendung"):
            L.append(f"- Begruendung: {z['begruendung']}")
        L.append("")
    open(REVIEW, "w", encoding="utf-8").write("\n".join(L) + "\n")


def review_in_tab(cfg, epigraphen):
    """Schreibt die Freigabeliste in den Tab ZitateReview.

    Die Zeilen erzeugt die Recherche, die Spalte 'freigegeben' setzt der
    Mensch. Deshalb wird sie hier aus dem aktuellen Stand uebernommen —
    freigabe_einlesen() hat sie kurz zuvor aus Tab bzw. Datei geholt, ein
    'ja' geht also nicht verloren.

    Ohne diese Richtung waere der Tab eine leere Tabelle, die niemand
    fuellt, und die Meldung 'im Spreadsheet zu pflegen' waere unwahr."""
    blatt = R._buch(cfg).worksheet(TAB)
    blatt.clear()
    R._blatt_schreiben(blatt, [SPALTEN] + zeilen(epigraphen))
    return len(epigraphen)


def review_lesen():
    """Freigaben aus der Markdown-Tabelle. Gibt {index: (ja?, wortlaut)}."""
    if not os.path.exists(REVIEW):
        return {}
    raus = {}
    for zeile in open(REVIEW, encoding="utf-8"):
        if not zeile.startswith("|"):
            continue
        felder = [f.strip() for f in zeile.strip().strip("|").split("|")]
        if len(felder) != len(SPALTEN) or felder[0] in ("index", "---"):
            continue
        if not felder[0].lstrip("-").isdigit():
            continue
        raus[int(felder[0])] = (felder[-1].lower() in ("ja", "j", "yes"),
                                felder[3])
    return raus


def freigabe_einlesen(cfg, epigraphen):
    """Setzt 'original_deutsch' — die EINZIGE Stelle, die das tut.

    Quelle ist die Review-Liste bzw. der Sheet-Tab, nicht das Modell."""
    freigaben = {}
    if R.aktiv(cfg):
        try:
            blatt = R._buch(cfg).worksheet(TAB)
            werte = blatt.get_all_values()
            kopf = [z.strip().lower() for z in werte[0]] if werte else []
            if "index" in kopf and "freigegeben" in kopf:
                i_idx, i_frei = kopf.index("index"), kopf.index("freigegeben")
                i_vor = kopf.index("vorschlag_de") \
                    if "vorschlag_de" in kopf else None
                for roh in werte[1:]:
                    if len(roh) <= max(i_idx, i_frei) \
                       or not roh[i_idx].strip().isdigit():
                        continue
                    freigaben[int(roh[i_idx])] = (
                        roh[i_frei].strip().lower() in ("ja", "j", "yes"),
                        roh[i_vor].strip() if i_vor is not None
                        and len(roh) > i_vor else "")
            print(f"Freigaben aus dem Tab {TAB}: {len(freigaben)} Zeilen")
        except R.SyncFehler as e:
            print(f"WARNUNG: {TAB} nicht lesbar — {e}")
        except Exception as e:
            print(f"WARNUNG: {TAB} nicht lesbar — {e}")
    if not freigaben:
        freigaben = review_lesen()
        if freigaben:
            print(f"Freigaben aus {REVIEW}: {len(freigaben)} Zeilen")

    gesetzt, offen = 0, 0
    for z in epigraphen:
        if z.get("status") == "original_belassen":
            continue
        ja, wortlaut = freigaben.get(z.get("index"), (False, ""))
        if ja and (wortlaut or z.get("vorschlag_de")):
            z["original_deutsch"] = wortlaut or z["vorschlag_de"]
            z["freigegeben"] = "ja"
            gesetzt += 1
        else:
            z["original_deutsch"] = None
            z["freigegeben"] = "nein"
            offen += 1
    return gesetzt, offen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-anzeigen", action="store_true",
                    help="zeigt, was recherchiert wuerde, ruft kein Modell")
    ap.add_argument("--uebernehmen", action="store_true",
                    help="nur Freigaben einlesen, nicht recherchieren")
    args = ap.parse_args()

    G.kopf("ZITATRECHERCHE")
    cfg = G.lade_config()
    print(f"Arbeitsverzeichnis: {os.getcwd()}\n")

    daten, epigraphen = zitate_lesen()
    if not epigraphen:
        print(f"Keine Zitate in {G.F['zitate']} — nichts zu tun.")
        print("Erkannt werden sie im Preflight.")
        return

    offen = [z for z in epigraphen if not z.get("status")
             or z.get("status") == "offen"]
    print(f"{len(epigraphen)} Zitat(e), davon {len(offen)} unrecherchiert")

    if args.nur_anzeigen:
        for z in offen:
            print(f"  Absatz {z['index']}: {z['text'][:90]}")
        modell = G.modell_fuer(cfg, "zitat")
        print(f"\n{len(offen)} Aufrufe an {modell}, je mit Websuche.")
        print("Nur Anzeige — kein Modellaufruf.")
        return

    if not args.uebernehmen:
        for z in offen:
            print(f"\nAbsatz {z['index']}: {z['text'][:70]} …", flush=True)
            try:
                befund = recherchieren(cfg, z)
            except Exception as e:
                print(f"  FEHLER: {e} — bleibt offen")
                continue
            uebernehmen(z, befund)
            if z["status"] == "original_belassen":
                print(f"  {z['sprache']} — bleibt im Original stehen")
            elif z["status"] == "gefunden":
                warnung = ("  UNSICHER" if z["konfidenz"] < SCHWELLE else "")
                print(f"  Vorschlag von {z['uebersetzer'] or '?'} "
                      f"(Konfidenz {z['konfidenz']}){warnung}")
                print(f"  Quelle: {z['quelle'] or '?'}")
            else:
                print("  nichts Belegtes gefunden — markierte Luecke bleibt")

    gesetzt, ohne = freigabe_einlesen(cfg, epigraphen)
    daten["epigraphen"] = epigraphen
    zitate_schreiben(daten)
    review_schreiben(epigraphen)

    print(f"\nFreigegeben und eingesetzt: {gesetzt}")
    print(f"Ohne Freigabe (markierte Luecke): {ohne}")
    print(f"\nReview-Liste: {REVIEW}")
    if R.aktiv(cfg):
        try:
            n = review_in_tab(cfg, epigraphen)
            print(f"Im Spreadsheet zu pflegen: Tab {TAB} ({n} Zeilen "
                  f"geschrieben)")
        except Exception as e:
            print(f"WARNUNG: Tab {TAB} nicht beschreibbar — {e}")
            print(f"  Die Freigabe geht dann ueber {REVIEW}.")
    print("\nFreigabe erteilen: in der Spalte 'freigegeben' ein 'ja' "
          "eintragen,\ndann diesen Schritt mit --uebernehmen erneut "
          "starten.")


if __name__ == "__main__":
    main()
