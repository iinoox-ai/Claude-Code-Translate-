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
    python3 referenz_sync.py --erstbefuellung   JSONs ins Sheet uebertragen
    python3 referenz_sync.py --modelle  Modellbelegung ins Sheet spiegeln

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
import re
import sys

import gemeinsam as G


class SyncFehler(Exception):
    """Zeilengenaue Sammelmeldung. Bricht den Schritt ab."""


def _liste(wert):
    return [t.strip() for t in str(wert).split(",") if t.strip()]


def _zahl(wert):
    s = str(wert).strip()
    return int(s) if s.isdigit() else None


# (Tab, Spalten, Zielschluessel in G.F, Zeilenbauer, Pflichtspalten,
#  Zerleger fuer die Gegenrichtung)
#
# Tabs in OPTIONAL duerfen in einem aelteren Spreadsheet fehlen: Dann
# bleibt die JSON-Datei die Quelle, statt dass jeder Schritt abbricht.
# Ohne das haette ein nachtraeglich ergaenzter Tab jede vorhandene
# Einrichtung lahmgelegt.
#
# Die Spaltennamen sind die des Auftrags und nicht ueberall gleich den
# JSON-Feldern: 'deutsch_ziel' im Sheet wird zu 'deutsch' im JSON, weil
# uebersetzung.block_anrede genau diesen Namen liest. Der Selbsttest
# haelt beide Seiten aneinander.
TABS = [
    ("Glossar", ["nl", "de", "hinweis"], "glossar",
     lambda z: (z["nl"], z["de"]), ["nl", "de"],
     lambda k, v: [k, str(v), ""]),

    ("Personen", ["name", "pronomen"], "personen",
     lambda z: (z["name"], z["pronomen"]), ["name", "pronomen"],
     lambda k, v: [k, str(v)]),

    ("Figurenblatt", ["name", "pronomen", "rolle", "sprache"], "figuren",
     lambda z: (z["name"], {"pronomen": z["pronomen"],
                            "rolle": z["rolle"],
                            "sprache": z["sprache"]}),
     ["name", "pronomen"],
     lambda k, v: [k, v.get("pronomen", ""), v.get("rolle", ""),
                   v.get("sprache", "")]),

    ("Anrede", ["beziehung", "figuren", "niederlaendisch", "deutsch_ziel",
                "hinweis"], "anrede",
     lambda z: (z["beziehung"], {"figuren": _liste(z["figuren"]),
                                 "niederlaendisch": z["niederlaendisch"],
                                 "deutsch": z["deutsch_ziel"],
                                 "hinweis": z["hinweis"]}),
     ["beziehung", "figuren", "deutsch_ziel"],
     lambda k, v: [k, ", ".join(v.get("figuren", [])),
                   v.get("niederlaendisch", ""), v.get("deutsch", ""),
                   v.get("hinweis", "")]),

    ("Kapitel", ["ueberschrift", "zeile"], "kapitel",
     lambda z: (z["ueberschrift"], z["zeile"]), ["ueberschrift", "zeile"],
     lambda k, v: [k, str(v)]),

    ("Leitmotive", ["wendung", "vorschlag", "haeufigkeit", "absicht"],
     "leitmotive",
     lambda z: (z["wendung"], {"vorschlag": z["vorschlag"],
                               "haeufigkeit": _zahl(z["haeufigkeit"]),
                               "absicht": z["absicht"]}),
     ["wendung", "vorschlag"],
     lambda k, v: [k, v.get("vorschlag", ""),
                   str(v.get("haeufigkeit") or ""), v.get("absicht", "")]),
]

# Kapitel kam mit Paket 4 dazu und fehlt in Spreadsheets, die vorher
# eingerichtet wurden. --vorlage legt ihn nach.
OPTIONAL = {"Kapitel"}

# Paket 6 pflegt diesen Tab; hier steht er nur, damit --vorlage ihn
# gleich mit anlegt und niemand ihn spaeter von Hand nachtraegt.
#
# Die Spalten kommen aus gemeinsam, nicht von hier: Bis August 2026 legte
# die Vorlage den Tab mit fuenf ausgedachten Ueberschriften an, die
# Zitatrecherche schrieb danach ihre eigenen acht hinein. Aufgefallen ist
# das nie — sie loescht den Tab vor dem Schreiben. Wer die Vorlage las,
# hatte trotzdem ein falsches Bild vom Tab.
TAB_ZITATE = ("ZitateReview", G.ZITAT_SPALTEN)


def aktiv(cfg):
    """Sheets-Betrieb oder Rueckfallpfad? Eine Stelle, nicht sieben."""
    return bool(str(cfg.get("sheets_id", "")).strip())


ID_ZEICHEN = re.compile(r"^[A-Za-z0-9_-]{20,}$")


def sheet_id(roh):
    """Nimmt die ID oder die ganze Bearbeitungs-URL, liefert die ID.

    Der Dateiname ist keine ID. Das sieht man ihm nicht an, und die
    Fehlermeldung von Google dazu ist unbrauchbar — also hier abfangen,
    bevor eine Anmeldung ueberhaupt versucht wird."""
    s = str(roh).strip()
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    if ID_ZEICHEN.match(s):
        return s
    raise SyncFehler(
        f"'{s}' sieht nicht nach einer Spreadsheet-ID aus.\n"
        f"  Gemeint ist der markierte Teil der Adresse, nicht der "
        f"Dateiname:\n"
        f"  https://docs.google.com/spreadsheets/d/1a2B3c…XyZ/edit\n"
        f"                                        ^^^^^^^^^^^\n"
        f"  Die ganze Adresse einzutragen geht auch.")


def _im_kernel():
    """Laeuft dieser Prozess IM Notebook-Kernel — oder als Unterprozess?

    Colabs authenticate_user() spricht ueber den Kernel-Kanal mit der
    Oberflaeche. In einem Unterprozess gibt es den nicht, und der Aufruf
    stirbt mit AttributeError statt mit einer Aussage. Die Pipeline
    startet ihre Schritte grundsaetzlich als Unterprozess."""
    try:
        from IPython import get_ipython
        return getattr(get_ipython(), "kernel", None) is not None
    except Exception:
        return False


def anmeldung_taugt(creds):
    """Ist das eine echte Anmeldung — oder nur der Rueckfall der VM?

    'google.auth.default()' findet in Colab IMMER etwas: Die Laufzeit ist
    eine Google-VM mit Metadatendienst, und der liefert eine
    Compute-Engine-Anmeldung. Nur haengt an ihr kein Dienstkonto. Das
    Objekt laesst sich bauen, der Aufruf gibt es zurueck, und erst beim
    ersten Zugriff kommt

        Failed to retrieve http://metadata.google.internal/…/service-
        accounts/default/ from the Google Compute Engine metadata
        service. Status: 404

    — eine Meldung, die nach einem Problem des Spreadsheets aussieht und
    keines ist. Ohne diese Pruefung nahm '_credentials' den Rueckfall fuer
    eine Anmeldung, kam nie beim Colab-Zweig an und meldete am Ende
    'Stimmt die ID, und ist das Dokument freigegeben?', obwohl beides
    stimmte.

    Ausserhalb von Colab ist dieselbe Anmeldung voellig in Ordnung: Auf
    einer echten GCE-Maschine mit Dienstkonto ist sie der normale Weg.
    Verworfen wird sie deshalb nur dort, wo sie nichts bedeutet."""
    if not G.ist_colab():
        return True
    try:
        import google.auth.compute_engine as ce
        return not isinstance(creds, ce.Credentials)
    except Exception:
        return True


def _credentials():
    """Drei Wege, in dieser Reihenfolge: Dienstkonto, bereits vorhandene
    Anmeldung, interaktive Anmeldung. Der mittlere ist der wichtige —
    ueber ihn sehen die Unterprozesse, was in der Zelle angemeldet
    wurde."""
    pfad = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if pfad:
        import google.oauth2.service_account as sa
        return sa.Credentials.from_service_account_file(
            pfad, scopes=["https://www.googleapis.com/auth/spreadsheets",
                          "https://www.googleapis.com/auth/drive"])
    try:
        import google.auth
        creds, _ = google.auth.default()
        if anmeldung_taugt(creds):
            return creds
    except Exception:
        pass
    if G.ist_colab() and _im_kernel():
        from google.colab import auth
        import google.auth
        auth.authenticate_user()
        creds, _ = google.auth.default()
        return creds
    if G.ist_colab():
        raise SyncFehler(
            "Keine Google-Anmeldung vorhanden, und dieser Schritt laeuft "
            "als Unterprozess —\n"
            "  dort kann Colab das Anmeldefenster nicht oeffnen.\n\n"
            "  Einmal je Sitzung in einer Zelle ausfuehren:\n"
            "      colab_start.sheets_anmelden()\n\n"
            "  Danach diesen Schritt erneut starten.")
    raise SyncFehler(
        "Ausserhalb von Colab braucht der Sheets-Zugriff ein Dienstkonto "
        "in GOOGLE_APPLICATION_CREDENTIALS.\n"
        "  Ohne das: sheets_id leeren und die JSONs direkt pflegen.")


def _buch(cfg):
    """gspread nur hinter Laufzeit-Erkennung. Fehlt es, ist das kein
    Fehler des Aufrufers, sondern ein Grund fuer den Rueckfallpfad."""
    kennung = sheet_id(cfg["sheets_id"])     # zuerst, kostet keine Anmeldung
    try:
        import gspread
    except ImportError:
        raise SyncFehler(
            "sheets_id ist gesetzt, aber gspread ist nicht verfuegbar.\n"
            "  In Colab ist es vorinstalliert. Sonst: sheets_id leeren, "
            "dann werden die JSONs direkt gelesen.")
    try:
        return gspread.authorize(_credentials()).open_by_key(kennung)
    except SyncFehler:
        raise
    except Exception as e:
        # Scheitert die Anmeldung selbst, hat das mit dem Spreadsheet
        # nichts zu tun — und die Frage nach ID und Freigabe schickt
        # jemanden eine Stunde in die falsche Richtung. Der Metadaten-404
        # ist der haeufigste Fall: keine Anmeldung, nur die VM.
        if "metadata.google.internal" in str(e):
            raise SyncFehler(
                "Keine Google-Anmeldung — die ID und die Freigabe sind "
                "nicht das Problem.\n"
                "  Was hier antwortet, ist der Metadatendienst der VM, "
                "nicht Google Sheets.\n\n"
                "  Einmal je Sitzung in einer Zelle ausfuehren:\n"
                "      colab_start.sheets_anmelden()\n\n"
                "  Danach diesen Schritt erneut starten.")
        raise SyncFehler(
            f"Spreadsheet {kennung[:12]}… nicht erreichbar: {e}\n"
            f"  Stimmt die ID, und ist das Dokument fuer dieses Konto "
            f"freigegeben?")


def _tab_lesen(buch, name, spalten):
    """Liefert Zeilen als Abbildung Spaltenname -> Wert, plus Zeilennummer.

    Fehlende Spalten sind ein Fehler, zusaetzliche werden ignoriert —
    sonst bricht das Sheet, sobald jemand eine Notizspalte anhaengt."""
    try:
        blatt = buch.worksheet(name)
    except Exception:
        if name in OPTIONAL:
            return None                  # Datei bleibt Quelle
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


def leerung_pruefen(fertig, lesen=None):
    """Ein leerer Tab ueber einer gefuellten JSON ist fast immer ein
    Versehen — frisch angelegte Tabs, aber die Daten stehen noch in den
    Dateien. Ohne diese Sperre haette der naechste Schritt das Glossar
    stillschweigend durch {} ersetzt und erst der Volllauf haette es
    gezeigt."""
    lesen = lesen or (lambda p: G.lade_json(p, still=True))
    warnungen = []
    for ziel, daten in fertig.items():
        if daten:
            continue
        alt = lesen(G.F[ziel])
        echte = {k: v for k, v in alt.items() if not k.startswith("_")}
        if echte:
            warnungen.append(
                f"{G.F[ziel]} hat {len(echte)} Eintraege, der zugehoerige "
                f"Tab ist leer")
    return warnungen


def sync(cfg, schreiben=True, still=False):
    """Holt alle Tabs, validiert, schreibt die JSONs. Gibt einen Bericht
    je Tab zurueck. Bei Fehlern: SyncFehler mit allen Meldungen."""
    buch = _buch(cfg)
    fehler, bericht = [], []
    fertig = {}
    for tabname, spalten, ziel, bauer, pflicht, _ in TABS:
        zeilen = _tab_lesen(buch, tabname, spalten)
        if zeilen is None:
            bericht.append(f"{tabname}: kein Tab, {G.F[ziel]} bleibt Quelle")
            continue
        daten, f = _pruefen_und_bauen(tabname, zeilen, bauer, pflicht)
        fehler += f
        fertig[ziel] = daten
        bericht.append(f"{tabname}: {len(daten)} Zeilen")
    if fehler:
        raise SyncFehler("\n  ".join(["Referenzdaten fehlerhaft:"] + fehler))
    leer = leerung_pruefen(fertig)
    if leer and schreiben:
        raise SyncFehler(
            "\n  ".join(["Das Spreadsheet wuerde vorhandene Daten "
                         "loeschen:"] + leer)
            + "\n\n  Die Dateien zuerst ins Spreadsheet uebertragen:\n"
              "      python3 referenz_sync.py --erstbefuellung\n"
              "  Oder sheets_id leeren, dann bleibt alles wie bisher.")
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


# Der Tab 'Modelle' ist die eine Ausnahme in dieser Datei: Er wird
# GESCHRIEBEN und NIE ZURUECKGELESEN.
#
# Der Grund ist keine Bequemlichkeit. Modellnamen sind Code-Daten — sie
# wandern mit dem Repo, damit eine Umbenennung beim Anbieter alle Buecher
# erreicht (siehe gemeinsam.TECHNIK). Referenzdaten sind Projektdaten und
# wandern mit dem Buch. Ein zurueckgelesener Tab machte die Modellwahl zur
# dritten Quelle neben Repo- und Projekt-projekt.json — und bei drei
# Quellen weiss niemand mehr, welcher Wert gilt.
#
# Sichtbar im Spreadsheet, geaendert in projekt.json.
TAB_MODELLE = ("Modelle", ["rolle", "modell", "tiefe", "empfohlen",
                           "empfohlene_tiefe", "kosten_letzter_lauf",
                           "begruendung"])


def modelle_schreiben(cfg, still=False):
    """Spiegelt die Modellbelegung ins Spreadsheet. Nur diese Richtung.

    Legt den Tab an, wenn er fehlt — anders als bei den Referenztabs ist
    das hier gefahrlos, weil nichts zurueckgelesen wird."""
    if not aktiv(cfg):
        return False
    name, spalten = TAB_MODELLE
    buch = _buch(cfg)
    try:
        blatt = buch.worksheet(name)
    except Exception:
        blatt = buch.add_worksheet(title=name, rows=40, cols=len(spalten))

    kosten = {}
    try:
        m = json.load(open(G.MANIFEST, encoding="utf-8"))
        for lauf, rolle, _, e in G.kosten_posten(m):
            if lauf in ("voll", ""):
                d = G.kosten_dollar(e, G.tarif(e.get("modell", "")))
                if d is not None:
                    kosten[rolle] = kosten.get(rolle, 0.0) + d
    except Exception:
        pass

    aktiv_jetzt = set(G.aktive_rollen(cfg))
    zeilen = [spalten]
    for rolle in G.ROLLEN:
        soll_m, soll_e, warum = G.empfehlung(rolle)
        zeilen.append([
            rolle + ("" if rolle in aktiv_jetzt else "  (ungenutzt)"),
            (cfg.get(f"modell_{rolle}") or "").strip() or "— nicht gesetzt",
            (cfg.get(f"effort_{rolle}") or "").strip(),
            soll_m, soll_e,
            f"{kosten[rolle]:.2f}" if rolle in kosten else "",
            warum,
        ])
    zeilen.append([])
    zeilen.append(["Dieser Tab wird geschrieben, nicht gelesen. "
                   "Aenderungen hier wirken nicht — die Belegung steht in "
                   "projekt.json."])
    _blatt_schreiben(blatt, zeilen)
    if not still:
        print(f"  {name}: {len(G.ROLLEN)} Rollen eingetragen "
              f"(nur lesend — geaendert wird in {G.CONFIG})")
    return True


def _blatt_schreiben(blatt, zeilen):
    """gspread hat die Reihenfolge dieser beiden Argumente zwischen 5 und
    6 vertauscht. Welche Fassung in Colab steckt, entscheidet Google —
    also beide bedienen, statt eine zu raten."""
    try:
        blatt.update(zeilen, "A1")
    except TypeError:
        blatt.update("A1", zeilen)


def erstbefuellung(cfg):
    """Traegt die vorhandenen JSONs einmalig ins Spreadsheet ein.

    Der Weg von Hand gepflegter Dateien in den Sheets-Betrieb. Tabs, die
    schon Zeilen haben, bleiben unangetastet — diese Richtung ueberschreibt
    nichts, sonst waere sie gefaehrlicher als das Problem, das sie loest."""
    buch = _buch(cfg)
    for tabname, spalten, ziel, _, _, zerleger in TABS:
        daten = {k: v for k, v in G.lade_json(G.F[ziel], still=True).items()
                 if not k.startswith("_")}
        try:
            blatt = buch.worksheet(tabname)
        except Exception:
            if tabname in OPTIONAL:
                print(f"  {tabname}: kein Tab — erst --vorlage, wenn er "
                      f"im Spreadsheet gepflegt werden soll")
                continue
            raise SyncFehler(f"Tab '{tabname}' fehlt — erst --vorlage.")
        vorhanden = [z for z in blatt.get_all_values()[1:] if any(z)]
        if vorhanden:
            print(f"  {tabname}: {len(vorhanden)} Zeilen vorhanden, "
                  f"unveraendert")
            continue
        if not daten:
            # Zwischen 'Datei fehlt' und 'Datei ist leer' unterscheiden.
            # Beides sieht im Sheet gleich aus, hat aber verschiedene
            # Ursachen — falsches Arbeitsverzeichnis gegen nichts zu tun.
            fehlt = not os.path.exists(G.F[ziel])
            print(f"  {tabname}: {G.F[ziel]} "
                  + ("nicht gefunden — falsches Arbeitsverzeichnis?"
                     if fehlt else "ist leer, nichts zu uebertragen"))
            continue
        zeilen = [spalten] + [zerleger(k, daten[k]) for k in sorted(daten)]
        _blatt_schreiben(blatt, zeilen)
        print(f"  {tabname}: {len(daten)} Zeilen aus {G.F[ziel]} uebertragen")


def vorlage(cfg):
    """Legt fehlende Tabs mit Kopfzeile an. Vorhandene bleiben unberuehrt."""
    buch = _buch(cfg)
    da = {b.title for b in buch.worksheets()}
    alle = [(t, s) for t, s, _, _, _, _ in TABS] + [TAB_ZITATE, TAB_MODELLE]
    for name, spalten in alle:
        if name in da:
            print(f"  {name}: vorhanden, unveraendert")
            continue
        blatt = buch.add_worksheet(title=name, rows=200,
                                   cols=max(4, len(spalten)))
        _blatt_schreiben(blatt, [spalten])
        print(f"  {name}: angelegt ({', '.join(spalten)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pruefen", action="store_true",
                    help="validieren, aber keine JSONs schreiben")
    ap.add_argument("--vorlage", action="store_true",
                    help="fehlende Tabs mit Kopfzeile anlegen")
    ap.add_argument("--erstbefuellung", action="store_true",
                    help="vorhandene JSONs einmalig ins Spreadsheet "
                         "uebertragen (ueberschreibt keine Zeilen)")
    ap.add_argument("--modelle", action="store_true",
                    help="Modellbelegung ins Spreadsheet spiegeln "
                         "(nur diese Richtung; geaendert wird in "
                         "projekt.json)")
    args = ap.parse_args()

    G.kopf("REFERENZ-SYNC")
    cfg = G.lade_config()
    if not aktiv(cfg):
        print("sheets_id ist leer — Rueckfallpfad aktiv.")
        print("Die Referenz-JSONs werden direkt gelesen, nichts zu tun.")
        return

    print(f"Spreadsheet:        {sheet_id(cfg['sheets_id'])[:12]}…")
    print(f"Arbeitsverzeichnis: {os.getcwd()}\n")
    try:
        if args.vorlage:
            vorlage(cfg)
            return
        if args.erstbefuellung:
            erstbefuellung(cfg)
            return
        if args.modelle:
            modelle_schreiben(cfg)
            return
        sync(cfg, schreiben=not args.pruefen)
        if args.pruefen:
            print("Nur geprueft — keine Datei geschrieben.")
    except SyncFehler as e:
        sys.exit(f"\nFEHLER: {e}")


if __name__ == "__main__":
    main()
