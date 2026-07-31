#!/usr/bin/env python3
"""
pipeline.py — Steuerung der gesamten Uebersetzung NL -> DE.

Ein Einstieg statt acht Handaufrufen. Kennt den Ablauf, weiss wo er steht,
setzt an der richtigen Stelle fort und loescht nur auf ausdruecklichen Befehl.

    python3 pipeline.py init            Konfiguration anlegen (interaktiv)
    python3 pipeline.py run             weiter am naechsten offenen Schritt
    python3 pipeline.py run --hg        dasselbe, abgekoppelt im Hintergrund
    python3 pipeline.py status          Stand, Chunkzaehler, Restzeit
    python3 pipeline.py log             Log ansehen  (-f = mitlaufen)
    python3 pipeline.py stop            laufenden Hintergrundlauf beenden
    python3 pipeline.py config          projekt.json einspielen und mergen
    python3 pipeline.py reset --ab NAME einen Schritt und alles danach oeffnen
    python3 pipeline.py neu             ALLES verwerfen (mit Rueckfrage)
    python3 pipeline.py schritte        Liste der Schritte

Das einzige Kommando, das Ergebnisse loescht, ist 'neu'. 'reset' oeffnet nur
Schritte wieder; die Dateien bleiben, bis der Schritt sie neu schreibt.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time

import gemeinsam as G

LOG  = "pipeline.log"
PID  = "pipeline.pid"

# Code und Daten liegen im Colab-Betrieb getrennt: der Code kommt per
# git in die VM, gearbeitet wird im Drive-Projektordner. Schrittskripte
# muessen deshalb ueber ihr Verzeichnis aufgerufen werden, Datenpfade
# bleiben relativ zum Arbeitsverzeichnis.
CODE = os.path.dirname(os.path.abspath(__file__))

# name, Beschreibung, Kommando (None = Pause), Dauerschaetzung in Minuten
SCHRITTE = [
    ("selbsttest",   "Selbsttest der Normalisierer und Prompts",
     ["preflight.py", "--selbsttest"], 1),
    ("preflight",    "Systempruefung, Textpruefung, Zitaterkennung",
     ["preflight.py"], 5),
    ("konkordanz",   "Kandidatenanalyse, Analysepaket oder lokales Glossar",
     ["konkordanz.py"], 15),
    ("PAUSE_glossar", "Glossardateien extern erstellen und hochladen",
     None, 0),
    ("test",         "Testuebersetzung, zwei Auszuege",
     ["uebersetzung.py", "--test"], 35),
    ("testB",        "Testuebersetzung mit alternativer Chunkgroesse",
     ["uebersetzung.py", "--test", "--variante", "B"], 30),
    ("bewertung",    "Testuebersetzung bewerten",
     ["bewertung.py"], 8),
    ("chunkvergleich", "Chunkgroessen A gegen B vergleichen",
     ["bewertung.py", "--chunkvergleich"], 1),
    ("test_lektorat", "Testlektorat",
     ["lektorat.py", "--test"], 30),
    ("qa_test_lekt", "Qualitaetspruefung des Testlektorats",
     ["qa.py", "--lektorat", "--test"], 1),
    ("bew_lektorat", "Testlektorat bewerten",
     ["bewertung.py", "--lektorat"], 2),
    ("PAUSE_pruefung", "Berichte pruefen, entscheiden, Dateien einspielen",
     None, 0),
    ("voll",         "Vollstaendige Uebersetzung",
     ["uebersetzung.py"], 190),
    ("qa_uebersetzung", "Qualitaetspruefung der Uebersetzung",
     ["qa.py", "--uebersetzung"], 2),
    ("lektorat",     "Vollstaendiges Lektorat",
     ["lektorat.py"], 100),
    ("qa_lektorat",  "Qualitaetspruefung des Lektorats",
     ["qa.py", "--lektorat"], 2),
    ("konsistenz",   "Globale Konsistenzpruefung ueber das ganze Buch",
     ["qa.py", "--konsistenz"], 2),
    ("paket",        "Ergebnis paketieren",
     ["paket.py"], 2),
]
NAMEN = [s[0] for s in SCHRITTE]


# ==================================================================
def manifest_lesen():
    if not os.path.exists(G.MANIFEST):
        return {"schritte": {}, "angelegt": time.strftime("%Y-%m-%d %H:%M")}
    try:
        return json.load(open(G.MANIFEST, encoding="utf-8"))
    except Exception:
        return {"schritte": {}}


def manifest_schreiben(m):
    tmp = G.MANIFEST + ".tmp"
    json.dump(m, open(tmp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    os.replace(tmp, G.MANIFEST)


def status_von(m, name):
    return m["schritte"].get(name, {}).get("status", "offen")


def setze(m, name, status, **extra):
    e = m["schritte"].setdefault(name, {})
    e["status"] = status
    e["zeit"] = time.strftime("%Y-%m-%d %H:%M")
    e.update(extra)
    manifest_schreiben(m)


def kostenuebersicht(m):
    """Was der Lauf an Token und Geld gekostet hat, je Rolle.

    Ein Schritt, der Modelle ruft und hier nicht auftaucht, erfasst seine
    Usage nicht — das gilt als unfertig, nicht als kostenlos."""
    zeilen, summe, unsicher = G.kosten_je_rolle(m)
    if not zeilen:
        return
    print("\nKosten je Rolle")
    print("-" * 62)
    for rolle, e, dollar, t in zeilen:
        token = f"{e['ein']:>9,} ein / {e['aus']:>8,} aus"
        cache = (f", Cache {e['cache_lesen']:,} gelesen"
                 if e["cache_lesen"] else "")
        preis = f"{dollar:6.2f} $" if dollar is not None else "  kein Tarif"
        print(f"  {rolle:<14} {e['modell']:<18} {token}{cache}")
        print(f"  {'':<14} {e['aufrufe']:>4} Aufrufe {'':<12} {preis}")
    print("-" * 62)
    print(f"  Summe: rund {summe:.2f} $")
    if unsicher:
        print("  Hinweis: nicht alle Tarife sind gegen die Anbieterdoku "
              "verifiziert\n           (Google-Tarife: Stand 31.07.2026, "
              "Verifikation in Paket 2).")


def uebersprungen(cfg, name):
    """Schritte, die die Konfiguration nicht braucht."""
    if name == "PAUSE_glossar" and cfg["glossar_quelle"] == "lokal":
        return True
    if name in ("testB", "chunkvergleich") and \
       cfg["chunk_words_variante"] == cfg["chunk_words"]:
        return True
    return False


# ==================================================================
def laeuft():
    # In Colab gibt es keinen Hintergrundlauf und damit auch keine
    # PID-Datei; eine liegengebliebene aus dem VPS-Betrieb wuerde hier
    # nur einen Lauf blockieren, den es nicht gibt.
    if G.ist_colab() or not os.path.exists(PID):
        return None
    try:
        pid = int(open(PID).read().strip())
        os.kill(pid, 0)
        return pid
    except Exception:
        return None


def cmd_status(cfg):
    m = manifest_lesen()
    G.kopf("STATUS")
    pid = laeuft()
    print(f"Hintergrundlauf: {'ja, PID ' + str(pid) if pid else 'nein'}")
    print(f"Fingerabdruck:   {G.config_hash(cfg)}\n")

    rest = 0
    for name, beschreibung, cmd, dauer in SCHRITTE:
        s = status_von(m, name)
        if uebersprungen(cfg, name):
            s = "uebersprungen"
        sym = {"fertig": "[x]", "laufend": "[>]", "fehler": "[!]",
               "uebersprungen": "[-]"}.get(s, "[ ]")
        pause = "  ⏸" if cmd is None else ""
        zusatz = ""
        if s == "laufend" or (s == "offen" and cmd):
            rest += dauer
        if name in ("voll", "test", "testB", "lektorat", "test_lektorat"):
            zusatz = chunkstand(name)
        print(f" {sym} {name:16s} {beschreibung[:44]:46s}{pause}{zusatz}")
    print(f"\nGeschaetzte Restzeit der GPU-Schritte: ca. {rest} min")

    naechster = naechster_schritt(cfg, m)
    if naechster is None:
        print("\nAlle Schritte erledigt.")
    else:
        name, _, cmd, _ = naechster
        if cmd is None:
            print(f"\nNaechster Schritt: PAUSE '{name}'")
            print("Nach dem Einspielen der Dateien:")
            print(f"  python3 pipeline.py reset --ab {name} --fertig")
            print("  python3 pipeline.py run")
        else:
            print(f"\nNaechster Schritt: {name}")
            print("  python3 pipeline.py run")


def chunkstand(name):
    praefix = {"test": "test/", "testB": "testB/",
               "test_lektorat": "test/"}.get(name, "")
    art = "lektorat" if "lektorat" in name else "uebersetzung"
    st = G.lade_json(praefix + f"{'lektorat' if art=='lektorat' else 'uebersetzung'}_state.json",
                     still=True)
    if not st.get("total"):
        return ""
    n = int(st["total"])
    da = G.teile_vorhanden(art, n, praefix)
    return f"   {da}/{n}"


def naechster_schritt(cfg, m):
    for eintrag in SCHRITTE:
        name = eintrag[0]
        if uebersprungen(cfg, name):
            continue
        if status_von(m, name) != "fertig":
            return eintrag
    return None


# ==================================================================
def cmd_run(cfg, args):
    if laeuft():
        sys.exit(f"Es laeuft bereits ein Lauf (PID {laeuft()}). "
                 f"'pipeline.py status' oder 'pipeline.py stop'.")

    if args.hg and G.ist_colab():
        sys.exit(
            "FEHLER: '--hg' ist in Colab gesperrt.\n\n"
            "Ein abgekoppelter Prozess ueberlebt die Laufzeit nicht und\n"
            "haelt die Sitzung auch nicht wach. In Colab gehoert der Lauf\n"
            "in den Vordergrund der Zelle: die Chunk-Fortschrittsausgabe\n"
            "verhindert nebenbei die Idle-Einstufung.\n\n"
            "  python3 pipeline.py run\n\n"
            "Ein Abbruch kostet nichts — jeder fertige Chunk liegt in\n"
            "teile/ auf Drive, der Resume zaehlt Dateien.")

    if args.hg:
        # V2: sich selbst abkoppeln
        if os.path.exists(LOG) and os.path.getsize(LOG) > 5_000_000:
            shutil.move(LOG, LOG + "." + time.strftime("%Y%m%d-%H%M"))
        with open(LOG, "a") as log:
            p = subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "run"],
                stdout=log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True,
                cwd=os.getcwd())
        open(PID, "w").write(str(p.pid))
        print(f"Im Hintergrund gestartet, PID {p.pid}.")
        print("  python3 pipeline.py status")
        print("  python3 pipeline.py log -f")
        return

    if not G.ist_colab():
        open(PID, "w").write(str(os.getpid()))
    m = manifest_lesen()
    fingerprint = G.config_hash(cfg)
    try:
        while True:
            eintrag = naechster_schritt(cfg, m)
            if eintrag is None:
                print("\n" + "=" * 62)
                print("Alle Schritte erledigt.")
                print("=" * 62)
                kostenuebersicht(manifest_lesen())
                break
            name, beschreibung, cmd, _ = eintrag

            if cmd is None:
                print("\n" + "=" * 62)
                print(f"PAUSE — {beschreibung}")
                print("=" * 62)
                # In Colab gibt es keine Instanz zum Stoppen und kein
                # /workspace: der Projektordner liegt in Drive und ist
                # waehrend der Pause direkt bearbeitbar.
                ordner = os.getcwd()
                if G.ist_colab():
                    if name == "PAUSE_glossar":
                        print(f"1. Im Drive-Ordner {ordner}:")
                        print("   analysepaket.md und briefing_glossar.md "
                              "herunterladen")
                        print("2. Die sechs Rueckgabedateien in denselben "
                              "Ordner legen")
                        print("3. Dann in einer Zelle:")
                    else:
                        print(f"1. Im Drive-Ordner {ordner}:")
                        print("   Berichte pruefen")
                        print("2. projekt.json und anweisungen.md dort "
                              "anpassen (die Dateien liegen in Drive,")
                        print("   ein Download ist nicht noetig)")
                        print("3. Dann in einer Zelle:")
                    print(f"     !python3 $CODE/pipeline.py reset "
                          f"--ab {name} --fertig")
                    print("   und Zelle 1 erneut ausfuehren.")
                else:
                    if name == "PAUSE_glossar":
                        print("1. Instanz STOPPEN (nicht zerstoeren)")
                        print("2. analysepaket.md und briefing_glossar.md "
                              "herunterladen")
                        print("3. Die sechs Rueckgabedateien nach "
                              "/workspace legen")
                        print("4. Instanz starten, dann:")
                    else:
                        print("1. Instanz STOPPEN")
                        print("2. Berichte herunterladen und pruefen")
                        print("3. Angepasste projekt.json und anweisungen.md "
                              "hochladen, dann:")
                        print("     python3 pipeline.py config "
                              "projekt_neu.json")
                        print("4. Danach:")
                    print(f"     python3 pipeline.py reset --ab {name} "
                          f"--fertig")
                    print("     python3 pipeline.py run")
                setze(m, name, "wartet")
                break

            print("\n" + "=" * 62)
            print(f"SCHRITT {name}  —  {beschreibung}")
            print("=" * 62, flush=True)
            setze(m, name, "laufend", fingerprint=fingerprint)
            t0 = time.time()
            # cmd[0] ist ein Skriptname im Code-Verzeichnis, nicht im
            # Arbeitsverzeichnis. Das Kindprozess-sys.path[0] wird damit
            # automatisch das Code-Verzeichnis — 'import gemeinsam' traegt.
            # '-u' haelt die Fortschrittsausgabe der Kindprozesse
            # ungepuffert — in Colab haengt daran die Idle-Erkennung.
            rc = subprocess.call(
                [sys.executable, "-u", os.path.join(CODE, cmd[0])] + cmd[1:],
                cwd=os.getcwd())
            dauer = (time.time() - t0) / 60

            if rc == 0:
                setze(m, name, "fertig", dauer_min=round(dauer, 1),
                      fingerprint=fingerprint)
                print(f"\n-> {name} fertig ({dauer:.0f} min)")
            else:
                setze(m, name, "fehler", rc=rc, dauer_min=round(dauer, 1))
                print("\n" + "!" * 62)
                print(f"SCHRITT '{name}' FEHLGESCHLAGEN (Rueckgabewert {rc})")
                print("Ursache im Bericht oder im Log nachsehen.")
                print("Nach der Behebung:  python3 pipeline.py run")
                print("!" * 62)
                break
    finally:
        if not G.ist_colab() and os.path.exists(PID):
            os.remove(PID)


def cmd_stop():
    pid = laeuft()
    if not pid:
        print("Kein Lauf aktiv.")
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        os.kill(pid, signal.SIGTERM)
    print(f"SIGTERM an PID {pid} gesendet.")
    print("Die Chunk-Dateien bleiben erhalten; 'run' setzt fort.")


def cmd_log(args):
    if not os.path.exists(LOG):
        print(f"{LOG} existiert noch nicht.")
        return
    if args.f:
        subprocess.call(["tail", "-f", LOG])
    else:
        subprocess.call(["tail", "-n", str(args.n), LOG])


def cmd_config(args):
    """V4: Konfiguration einspielen, geschuetzte Schluessel bewahren."""
    if not os.path.exists(args.datei):
        sys.exit(f"FEHLER: {args.datei} nicht gefunden.")
    try:
        neu = json.load(open(args.datei, encoding="utf-8"))
    except Exception as e:
        sys.exit(f"FEHLER: {args.datei} ist kein gueltiges JSON — {e}")

    alt = G.lade_config(pflicht=False)
    cfg, uebernommen, abgelehnt = G.merge_config(alt, neu)

    G.kopf("KONFIGURATION EINSPIELEN")
    if uebernommen:
        print("Uebernommen:")
        for k, (a, b) in sorted(uebernommen.items()):
            print(f"  {k}: {a!r} -> {b!r}")
    else:
        print("Keine Aenderungen uebernommen.")
    if abgelehnt:
        print("\nAbgelehnt:")
        for k, (v, grund) in sorted(abgelehnt.items()):
            print(f"  {k} = {v!r}   ({grund})")

    if uebernommen:
        G.speichere_config(cfg)
        print(f"\n{G.CONFIG} aktualisiert.")
        print(f"Neuer Fingerabdruck: {G.config_hash(cfg)}")
        print("\nHinweis: Schritte, die mit dem alten Fingerabdruck gelaufen "
              "sind, bleiben\nals 'fertig' markiert. Sollen sie neu laufen:")
        print("  python3 pipeline.py reset --ab SCHRITT")


def cmd_reset(cfg, args):
    m = manifest_lesen()
    if args.ab not in NAMEN:
        sys.exit(f"FEHLER: '{args.ab}' ist kein Schritt. "
                 f"'pipeline.py schritte' zeigt die Liste.")
    i = NAMEN.index(args.ab)
    if args.fertig:
        setze(m, args.ab, "fertig", hinweis="von Hand als erledigt markiert")
        print(f"'{args.ab}' als fertig markiert.")
        betroffen = NAMEN[i + 1:]
    else:
        betroffen = NAMEN[i:]
    geaendert = []
    for name in betroffen:
        if status_von(m, name) != "offen":
            m["schritte"].pop(name, None)
            geaendert.append(name)
    manifest_schreiben(m)
    if geaendert:
        print("Wieder geoeffnet: " + ", ".join(geaendert))
    print("\nDie Ergebnisdateien bleiben erhalten. Ein Schritt, der neu "
          "laeuft,\nsetzt an seinen vorhandenen Chunk-Dateien fort. Sollen "
          "diese weg:")
    print("  python3 pipeline.py neu --nur-teile")


WEG_TEILE = ["teile", "test/teile", "testB/teile",
             "uebersetzung_state.json", "test/uebersetzung_state.json",
             "testB/uebersetzung_state.json",
             "lektorat_state.json", "test/lektorat_state.json"]

WEG_ALLES = WEG_TEILE + [
    G.MANIFEST, LOG, PID, "test", "testB",
    G.F["entwurf"], G.F["uebersetzung"], G.F["normalisiert"], G.F["lektoriert"],
    "lektorat_diff.txt", "normalisierung_report.txt",
    "uebersetzung_warnungen.log", "lektorat_warnungen.log",
    "qa_uebersetzung.txt", "qa_lektorat.txt", "qa_konsistenz.txt",
    "preflight_report.txt", "leitmotiv_varianten.txt",
    "analysepaket.md", "bewertung_uebersetzung.md", "bewertung_lektorat.md",
    "bewertung_chunkgroesse.md", "bericht.html",
]


def cmd_neu(args):
    weg = WEG_TEILE if args.nur_teile else WEG_ALLES
    vorhanden = [p for p in weg if os.path.exists(p)]
    if not vorhanden:
        print("Nichts zu loeschen.")
        return
    G.kopf("VERWERFEN")
    print("Diese Dateien und Ordner werden geloescht:\n")
    for p in vorhanden:
        art = "Ordner" if os.path.isdir(p) else "Datei "
        print(f"  {art}  {p}")
    print("\nNICHT betroffen: input.txt, projekt.json, anweisungen.md, "
          "glossar.json,\n  personen.json, figurenblatt.json, anrede.json, "
          "leitmotive.json, zitate.json,\n  alle *.py")
    if input("\nWirklich loeschen? Tippe 'ja': ").strip().lower() != "ja":
        print("Abgebrochen.")
        return
    for p in vorhanden:
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    print(f"\n{len(vorhanden)} Eintraege entfernt.")


def cmd_schritte(cfg):
    G.kopf("SCHRITTE")
    m = manifest_lesen()
    for name, beschreibung, cmd, dauer in SCHRITTE:
        s = ("uebersprungen" if uebersprungen(cfg, name)
             else status_von(m, name))
        art = "Pause" if cmd is None else f"{dauer} min"
        print(f"  {name:16s} {art:>8s}  {s:14s} {beschreibung}")


def cmd_init():
    cfg = frage_alles(G.lade_config(pflicht=False))
    G.speichere_config(cfg)
    print(f"\n{G.CONFIG} geschrieben. Weiter mit:")
    print("  python3 pipeline.py run --hg")


def frage(text, optionen, standard):
    print(f"\n{text}")
    for k, (label, _) in optionen.items():
        print(f"  {k}) {label}" + (" (Vorgabe)" if k == standard else ""))
    while True:
        a = input(f"Auswahl [{standard}]: ").strip() or standard
        if a in optionen:
            return optionen[a][1]
        print("  Ungueltig.")


def frage_alles(cfg):
    G.kopf("KONFIGURATION")
    cfg = dict(cfg)
    cfg["sprachpaar"] = "nl-de"
    cfg["quotes"] = frage(
        "Wörtliche Rede im deutschen Zieltext?",
        {"1": ("»Rede«  — Guillemets nach innen, innen ›so‹", "guillemets"),
         "2": ("„Rede“  — Anführungszeichen unten/oben", "anfuehrung")}, "1")
    cfg["eszett"] = frage(
        "ß verwenden?",
        {"1": ("ja — bundesdeutsche Schreibung", True),
         "2": ("nein — schweizerisch, durchgehend ss", False)}, "1")
    cfg["diminutive"] = frage(
        "Niederländische Diminutive (-je/-tje)?",
        {"1": ("auflösen, -chen nur bei echter Verkleinerung", "aufloesen"),
         "2": ("übertragen, wo es natürlich klingt", "erhalten")}, "1")
    cfg["tempus"] = frage(
        "Erzähltempus?",
        {"1": ("quellnah — Wechsel Präteritum/Perfekt folgen", "quellnah"),
         "2": ("durchgehend Präteritum", "praeteritum")}, "1")
    cfg["glossar_quelle"] = frage(
        "Wie soll das Glossar entstehen?",
        {"1": ("Extern — deutlich bessere Qualität", "extern"),
         "2": ("Lokal über das Modell — nichts verlässt die Instanz",
               "lokal")}, "1")
    if cfg["glossar_quelle"] == "extern":
        cfg["export_glossar"] = frage(
            "Darf der Volltext ins Analysepaket?",
            {"1": ("Ja — beste Qualität", True),
             "2": ("Nein, nur Konkordanzen", False)}, "1")
    else:
        cfg["export_glossar"] = False
    cfg["export_bewertung"] = frage(
        "Dürfen Testauszüge für die externe Bewertung exportiert werden?",
        {"1": ("Ja", True), "2": ("Nein", False)}, "1")
    cfg["chunk_words_variante"] = frage(
        f"Chunkgrößen-Vergleich? Basis ist {cfg['chunk_words']} Wörter.",
        {"1": (f"ja, gegen 1200 Wörter testen", 1200),
         "2": ("nein, nur die Basisgröße", cfg["chunk_words"])}, "1")
    return cfg


# ==================================================================
def main():
    ap = argparse.ArgumentParser(add_help=True)
    sub = ap.add_subparsers(dest="kommando")

    sub.add_parser("init")
    p = sub.add_parser("run")
    p.add_argument("--hg", action="store_true", help="im Hintergrund")
    sub.add_parser("status")
    p = sub.add_parser("log")
    p.add_argument("-f", action="store_true")
    p.add_argument("-n", type=int, default=40)
    sub.add_parser("stop")
    p = sub.add_parser("config")
    p.add_argument("datei")
    p = sub.add_parser("reset")
    p.add_argument("--ab", required=True)
    p.add_argument("--fertig", action="store_true",
                   help="diesen Schritt als erledigt markieren")
    p = sub.add_parser("neu")
    p.add_argument("--nur-teile", action="store_true",
                   help="nur Chunk-Dateien und Zustaende")
    sub.add_parser("schritte")

    args = ap.parse_args()
    if not args.kommando:
        ap.print_help()
        return

    if args.kommando == "init":
        cmd_init()
        return
    if args.kommando == "neu":
        cmd_neu(args); return
    if args.kommando == "log":
        cmd_log(args); return
    if args.kommando == "stop":
        cmd_stop(); return
    if args.kommando == "config":
        cmd_config(args); return

    cfg = G.lade_config()
    {"run": lambda: cmd_run(cfg, args),
     "status": lambda: cmd_status(cfg),
     "reset": lambda: cmd_reset(cfg, args),
     "schritte": lambda: cmd_schritte(cfg)}[args.kommando]()


if __name__ == "__main__":
    main()
