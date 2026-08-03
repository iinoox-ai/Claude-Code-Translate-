#!/usr/bin/env python3
"""
Referenzdaten aus dem Google-Spreadsheet holen und als JSON ablegen.

Bei gesetzter 'sheets_id' ist das Spreadsheet die Quelle; die JSONs sind
erzeugte Artefakte und werden ueberschrieben. Ohne 'sheets_id' passiert
gar nichts — dann gilt das alte Verhalten, die JSONs werden direkt
gelesen. Dieser Rueckfallpfad bleibt, damit die Pipeline auf einem
nackten Server ohne Google-Zugang lauffaehig ist.

    python3 referenz_sync.py            holen und schreiben
    python3 referenz_sync.py --pruefen  nur pruefen, nichts schreiben
    python3 referenz_sync.py --vorlage  leere Tabs mit Kopfzeilen anlegen

Die Validierung laeuft VOR dem Schreiben und meldet zeilengenau. Grund:
Ein Schritt, der Referenzdaten braucht, ruft gleich darauf ein Modell —
ein Tippfehler in Zeile 14 soll nicht erst nach dreissig Dollar
auffallen.

Die Zeilennummern sind die des Spreadsheets: Kopfzeile ist Zeile 1, der
erste Datensatz steht in Zeile 2.
"""

import argparse
import json
import os
import sys

import gemeinsam as G


class SyncFehler(Exception):
    """Zeilengenaue Sammelmeldung. Bricht den Schritt ab."""


def _liste(wert):
    return [t.strip() for t in str(wert).split(",") if t.strip()]


def _zahl(wert):
    s = str(wert).strip()
    return int(s) if s.isdigit() else None


# (Tab, Spalten, Zielschluessel in G.F, Zeilenbauer, Pflichtspalten)
#
# Die Spaltennamen sind die des Auftrags und nicht ueberall gleich den
# JSON-Feldern: 'deutsch_ziel' im Sheet wird zu 'deutsch' im JSON, weil
# uebersetzung.block_anrede genau diesen Namen liest. Der Selbsttest
# haelt beide Seiten aneinander.
TABS = [
    ("Glossar", ["nl", "de", "hinweis"], "glossar",
     lambda z: (z["nl"], z["de"]), ["nl", "de"]),

    ("Personen", ["name", "pronomen"], "personen",
     lambda z: (z["name"], z["pronomen"]), ["name", "pronomen"]),

    ("Figurenblatt", ["name", "pronomen", "rolle", "sprache"], "figuren",
     lambda z: (z["name"], {"pronomen": z["pronomen"],
                            "rolle": z["rolle"],
                            "sprache": z["sprache"]}),
     ["name", "pronomen"]),

    ("Anrede", ["beziehung", "figuren", "niederlaendisch", "deutsch_ziel",
                "hinweis"], "anrede",
     lambda z: (z["beziehung"], {"figuren": _liste(z["figuren"]),
                                 "niederlaendisch": z["niederlaendisch"],
                                 "deutsch": z["deutsch_ziel"],
                                 "hinweis": z["hinweis"]}),
     ["beziehung", "figuren", "deutsch_ziel"]),

    ("Leitmotive", ["wendung", "vorschlag", "haeufigkeit", "absicht"],
     "leitmotive",
     lambda z: (z["wendung"], {"vorschlag": z["vorschlag"],
                               "haeufigkeit": _zahl(z["haeufigkeit"]),
                               "absicht": z["absicht"]}),
     ["wendung", "vorschlag"]),
]

# Paket 6 pflegt diesen Tab; hier steht er nur, damit --vorlage ihn
# gleich mit anlegt und niemand ihn spaeter von Hand nachtraegt.
TAB_ZITATE = ("ZitateReview",
              ["marke", "quelle", "wortlaut", "uebersetzer", "freigegeben"])


def aktiv(cfg):
    """Sheets-Betrieb oder Rueckfallpfad? Eine Stelle, nicht sieben."""
    return bool(str(cfg.get("sheets_id", "")).strip())


def _client(cfg):
    """gspread nur hinter Laufzeit-Erkennung. Fehlt es, ist das kein
    Fehler des Aufrufers, sondern ein Grund fuer den Rueckfallpfad."""
    try:
        import gspread
    except ImportError:
        raise SyncFehler(
            "sheets_id ist gesetzt, aber gspread ist nicht verfuegbar.\n"
            "  In Colab ist es vorinstalliert. Sonst: sheets_id leeren, "
            "dann werden die JSONs direkt gelesen.")
    if G.ist_colab():
        from google.colab import auth
        import google.auth
        auth.authenticate_user()
        creds, _ = google.auth.default()
        return gspread.authorize(creds)
    pfad = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not pfad:
        raise SyncFehler(
            "Ausserhalb von Colab braucht der Sheets-Zugriff ein "
            "Dienstkonto in GOOGLE_APPLICATION_CREDENTIALS.\n"
            "  Ohne das: sheets_id leeren und die JSONs direkt pflegen.")
    return gspread.service_account(filename=pfad)


def _tab_lesen(buch, name, spalten):
    """Liefert Zeilen als Abbildung Spaltenname -> Wert, plus Zeilennummer.

    Fehlende Spalten sind ein Fehler, zusaetzliche werden ignoriert —
    sonst bricht das Sheet, sobald jemand eine Notizspalte anhaengt."""
    try:
        blatt = buch.worksheet(name)
    except Exception:
        raise SyncFehler(f"Tab '{name}' fehlt im Spreadsheet.")
    werte = blatt.get_all_values()
    if not werte:
        return []
    kopf = [z.strip().lower() for z in werte[0]]
    fehlend = [s for s in spalten if s not in kopf]
    if fehlend:
        raise SyncFehler(
            f"{name}, Zeile 1: Spalte(n) {', '.join(fehlend)} fehlen. "
            f"Gefunden: {', '.join(kopf) or '(leer)'}")
    idx = {s: kopf.index(s) for s in spalten}
    zeilen = []
    for nr, roh in enumerate(werte[1:], start=2):
        z = {s: (roh[i].strip() if i < len(roh) else "")
             for s, i in idx.items()}
        if any(z.values()):                      # ganz leere Zeilen weg
            zeilen.append((nr, z))
    return zeilen


def _pruefen_und_bauen(tabname, zeilen, bauer, pflicht):
    """Sammelt ALLE Fehler, statt beim ersten abzubrechen — wer ein Sheet
    korrigiert, will die Liste, nicht einen Fehler pro Durchlauf."""
    fehler, daten, gesehen = [], {}, {}
    for nr, z in zeilen:
        leer = [s for s in pflicht if not z[s]]
        if leer:
            fehler.append(f"{tabname}, Zeile {nr}: "
                          f"{', '.join(leer)} fehlt")
            continue
        schluessel, wert = bauer(z)
        if schluessel in gesehen:
            fehler.append(f"{tabname}, Zeile {nr}: '{schluessel}' steht "
                          f"schon in Zeile {gesehen[schluessel]}")
            continue
        gesehen[schluessel] = nr
        daten[schluessel] = wert
    return daten, fehler


def _schreiben(pfad, daten):
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, pfad)


def sync(cfg, schreiben=True, still=False):
    """Holt alle Tabs, validiert, schreibt die JSONs. Gibt einen Bericht
    je Tab zurueck. Bei Fehlern: SyncFehler mit allen Meldungen."""
    buch = _client(cfg).open_by_key(str(cfg["sheets_id"]).strip())
    fehler, bericht = [], []
    fertig = {}
    for tabname, spalten, ziel, bauer, pflicht in TABS:
        zeilen = _tab_lesen(buch, tabname, spalten)
        daten, f = _pruefen_und_bauen(tabname, zeilen, bauer, pflicht)
        fehler += f
        fertig[ziel] = daten
        bericht.append(f"{tabname}: {len(daten)} Zeilen")
    if fehler:
        raise SyncFehler("\n  ".join(["Referenzdaten fehlerhaft:"] + fehler))
    if schreiben:
        for ziel, daten in fertig.items():
            _schreiben(G.F[ziel], daten)
    if not still:
        print("Referenzdaten aus Sheets: " + ", ".join(bericht))
    return bericht


def sicherstellen(cfg, still=False):
    """Von jedem Schritt aufzurufen, der Referenzdaten braucht.

    Ohne sheets_id ein No-op — der Rueckfallpfad muss unveraendert
    bleiben, sonst ist die Pipeline an Google gebunden."""
    if not aktiv(cfg):
        return False
    try:
        sync(cfg, still=still)
    except SyncFehler as e:
        sys.exit(f"\nFEHLER: {e}\n\n"
                 f"  Im Spreadsheet korrigieren, dann denselben Schritt "
                 f"erneut starten.\n"
                 f"  Es wurde nichts geschrieben und kein Modell gerufen.")
    return True


def vorlage(cfg):
    """Legt fehlende Tabs mit Kopfzeile an. Vorhandene bleiben unberuehrt."""
    buch = _client(cfg).open_by_key(str(cfg["sheets_id"]).strip())
    da = {b.title for b in buch.worksheets()}
    alle = [(t, s) for t, s, _, _, _ in TABS] + [TAB_ZITATE]
    for name, spalten in alle:
        if name in da:
            print(f"  {name}: vorhanden, unveraendert")
            continue
        blatt = buch.add_worksheet(title=name, rows=200,
                                   cols=max(4, len(spalten)))
        blatt.update([spalten], "A1")
        print(f"  {name}: angelegt ({', '.join(spalten)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pruefen", action="store_true",
                    help="validieren, aber keine JSONs schreiben")
    ap.add_argument("--vorlage", action="store_true",
                    help="fehlende Tabs mit Kopfzeile anlegen")
    args = ap.parse_args()

    G.kopf("REFERENZ-SYNC")
    cfg = G.lade_config()
    if not aktiv(cfg):
        print("sheets_id ist leer — Rueckfallpfad aktiv.")
        print("Die Referenz-JSONs werden direkt gelesen, nichts zu tun.")
        return

    print(f"Spreadsheet: {str(cfg['sheets_id']).strip()[:12]}…\n")
    try:
        if args.vorlage:
            vorlage(cfg)
            return
        sync(cfg, schreiben=not args.pruefen)
        if args.pruefen:
            print("Nur geprueft — keine Datei geschrieben.")
    except SyncFehler as e:
        sys.exit(f"\nFEHLER: {e}")


if __name__ == "__main__":
    main()
