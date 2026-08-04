#!/usr/bin/env python3
"""
Modellpreise gegen die Preisseiten der Anbieter halten.

    python3 tarife.py              pruefen und, wo eindeutig, uebernehmen
    python3 tarife.py --nur-pruefen        nichts schreiben
    python3 tarife.py --erzwingen          auch bei altem Stand neu holen

Warum das kein einfacher Abruf ist: **Keiner der beiden Anbieter
veroeffentlicht eine Preis-API.** Es gibt HTML-Seiten fuer Menschen, und
die aendern jederzeit ihr Layout. Ein Auslesen daraus ist eine Schaetzung
ueber eine Textstelle, keine Auskunft.

Deshalb gilt hier derselbe Grundsatz wie bei den Zitaten: **Uebernommen
wird nur, was eindeutig ist.** Findet die Seite genau zwei Preise im
Umfeld des Modellnamens und liegt der Eingabepreis unter dem
Ausgabepreis, wird der Wert mit Quelle und Datum in tarife.json
geschrieben. Alles andere wird gemeldet und der hinterlegte Wert bleibt
stehen — ein falscher Preis verzerrt sonst jeden Kostenbericht, ohne
dass es auffaellt.

tarife.json liegt im Projektordner und hat Vorrang vor gemeinsam.TARIFE.
Die Konstanten dort bleiben die dokumentierte Grundlage.
"""

import argparse
import json
import os
import re
import sys
import time

import requests

import gemeinsam as G

DATEI = "tarife.json"

PREISSEITEN = {
    "anthropic": "https://docs.claude.com/en/docs/about-claude/pricing",
    "google":    "https://ai.google.dev/gemini-api/docs/pricing",
}

# Aelter als das? Dann neu holen. Preise aendern sich nicht taeglich, und
# jeder Lauf soll nicht an zwei fremden Servern haengen.
MAX_ALTER_TAGE = 7


def seite_text(url, timeout=(10, 60)):
    r = requests.get(url, timeout=timeout,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    text = re.sub(r"<[^>]+>", " ", r.text)
    return re.sub(r"\s+", " ", text)


def preise_finden(text, modell, fenster=(300, 600)):
    """Alle Dollarbetraege im Umfeld des Modellnamens, ohne Deutung."""
    stellen = [m.start() for m in re.finditer(re.escape(modell), text)]
    if not stellen:
        return None
    vor, nach = fenster
    umfeld = " ".join(text[max(0, s - vor):s + nach] for s in stellen[:3])
    roh = re.findall(r"\$\s?(\d+(?:[.,]\d{1,2})?)", umfeld)
    return sorted({float(x.replace(",", ".")) for x in roh})


def urteil(gefunden, hinterlegt):
    """('bestaetigt'|'abweichend'|'unklar'|'fehlt', ein, aus).

    Eindeutig heisst: genau zwei Betraege, und der kleinere ist die
    Eingabe. Drei oder mehr bedeutet fast immer, dass die Seite Stufen
    oder Cache-Preise mitfuehrt — da wird nicht geraten."""
    if gefunden is None:
        return "fehlt", None, None
    if len(gefunden) != 2:
        return "unklar", None, None
    ein, aus = gefunden[0], gefunden[1]
    if ein >= aus:
        return "unklar", None, None
    if hinterlegt and abs(hinterlegt["ein"] - ein) < 0.005 \
       and abs(hinterlegt["aus"] - aus) < 0.005:
        return "bestaetigt", ein, aus
    return "abweichend", ein, aus


def lokal_lesen():
    if not os.path.exists(DATEI):
        return {}
    try:
        return json.load(open(DATEI, encoding="utf-8"))
    except Exception:
        return {}


def lokal_schreiben(d):
    tmp = DATEI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, DATEI)


def frisch_genug(d, tage=MAX_ALTER_TAGE):
    """True, wenn alle Eintraege juenger als 'tage' sind."""
    if not d:
        return False
    grenze = time.time() - tage * 86400
    return all(e.get("geholt_am", 0) >= grenze for e in d.values()
               if isinstance(e, dict))


def pruefen(cfg, schreiben=True, holen=seite_text):
    """Gibt (Berichtzeilen, uebernommen) zurueck."""
    modelle = sorted({G.modell_fuer(cfg, r) for r in G.ROLLEN
                      if G.modell_fuer(cfg, r)})
    lokal, zeilen, neu = lokal_lesen(), [], {}
    seiten = {}
    for modell in modelle:
        anbieter = G.backend_name(modell)
        url = PREISSEITEN.get(anbieter)
        if not url:
            zeilen.append(f"  {modell}: kein Preisseite fuer '{anbieter}'")
            continue
        if anbieter not in seiten:
            try:
                seiten[anbieter] = holen(url)
            except Exception as ex:
                seiten[anbieter] = None
                zeilen.append(f"  {anbieter}: Preisseite nicht erreichbar "
                              f"({type(ex).__name__}) — hinterlegte Werte "
                              f"bleiben")
        if seiten[anbieter] is None:
            continue

        hinterlegt = G.tarif(modell)
        stand, ein, aus = urteil(preise_finden(seiten[anbieter], modell),
                                 hinterlegt)
        if stand == "bestaetigt":
            zeilen.append(f"  {modell}: {ein:.2f} / {aus:.2f} $ bestaetigt")
            neu[modell] = {"ein": ein, "aus": aus, "quelle": url,
                           "geholt_am": time.time(), "stand": "bestaetigt"}
        elif stand == "abweichend":
            alt = (f"{hinterlegt['ein']:.2f} / {hinterlegt['aus']:.2f}"
                   if hinterlegt else "bisher unbekannt")
            zeilen.append(f"  {modell}: {alt} -> {ein:.2f} / {aus:.2f} $ "
                          f"— UEBERNOMMEN" if schreiben else
                          f"  {modell}: {alt} -> {ein:.2f} / {aus:.2f} $ "
                          f"— Abweichung, nicht uebernommen")
            if schreiben:
                neu[modell] = {"ein": ein, "aus": aus, "quelle": url,
                               "geholt_am": time.time(),
                               "stand": "uebernommen"}
        elif stand == "unklar":
            zeilen.append(f"  {modell}: Preise auf der Seite nicht eindeutig "
                          f"— hinterlegter Wert bleibt")
        else:
            zeilen.append(f"  {modell}: auf der Preisseite nicht gefunden "
                          f"— Modellname geaendert?")
    if schreiben and neu:
        lokal.update(neu)
        lokal_schreiben(lokal)
    return zeilen, neu


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-pruefen", action="store_true",
                    help="melden, aber nichts schreiben")
    ap.add_argument("--erzwingen", action="store_true",
                    help="auch holen, wenn der Stand noch frisch ist")
    args = ap.parse_args()

    G.kopf("TARIFE")
    cfg = G.lade_config()
    lokal = lokal_lesen()
    if lokal and frisch_genug(lokal) and not args.erzwingen:
        print(f"{DATEI} ist juenger als {MAX_ALTER_TAGE} Tage — nichts zu "
              f"tun.")
        for m, e in sorted(lokal.items()):
            print(f"  {m}: {e['ein']:.2f} / {e['aus']:.2f} $ ({e['stand']})")
        print("\nNeu holen mit --erzwingen.")
        return

    print("Preisseiten:")
    for a, u in PREISSEITEN.items():
        print(f"  {a}: {u}")
    print()
    zeilen, neu = pruefen(cfg, schreiben=not args.nur_pruefen)
    print("\n".join(zeilen) or "  keine Modelle belegt")
    if neu:
        print(f"\n{len(neu)} Eintraege in {DATEI}.")
    print("\nWas nicht eindeutig war, blieb auf dem hinterlegten Wert. "
          "Keiner der\nAnbieter hat eine Preis-API — ausgelesen wird eine "
          "Seite fuer Menschen.")


if __name__ == "__main__":
    main()
