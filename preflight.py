#!/usr/bin/env python3
"""
Preflight NL -> DE.

Nicht interaktiv (V3). Die Konfigurationsfragen stellt 'pipeline.py init'.

Neu gegenueber der ersten Fassung:
  - Selbsttest aller Normalisierer und Prompt-Bauer vor allem anderen
  - Begleitdateien werden AUCH im Schnellmodus geprueft (F4), mit
    Schemapruefung; leeres Glossar bei glossar_quelle=extern ist ein Fehler
  - Epigraph und Attributionszeile werden gemeinsam ausgeklammert (F3)

Aufrufe:
    python3 preflight.py
    python3 preflight.py --quick
    python3 preflight.py --selbsttest
"""

import argparse
import json
import os
import re
import subprocess
import sys

import requests

import gemeinsam as G

REPORT = "preflight_report.txt"

NL_MARKER = [r"\bhet\b", r"\bde\b", r"\been\b", r"\bik\b", r"\bhij\b",
             r"\bzij\b", r"\bniet\b", r"\bmaar\b", r"\bdat\b", r"\bmet\b",
             r"\bvoor\b", r"\bzijn\b", r"\bheeft\b", r"\bwerd\b", r"\bnaar\b"]
DE_MARKER = [r"\bder\b", r"\bdie\b", r"\bdas\b", r"\bund\b", r"\bnicht\b",
             r"\bich\b", r"\bwar\b", r"\bmit\b", r"\bauf\b", r"\bhatte\b"]


# ==================================================================
# Selbsttest — haette den \u-Fehler und die ss/ß-Kollision gefunden
# ==================================================================
def selbsttest(cfg, b):
    b.abschnitt("Selbsttest")
    import lektorat as L
    import uebersetzung as U
    import qa as Q

    probe = ('Hij zei -- eigenlijk fluisterde hij -- dat het "goed" was... '
             'Die Masse der Menschen. Die Busse fuhren nicht. Ein Ass im '
             'Ärmel. Strasse, gross, draussen. Ein Test\u2014mit Strich.')
    try:
        neu, zaehler = L.normalisieren(probe, cfg)
        for falsch, soll in (("Maße der Menschen", "Masse der Menschen"),
                             ("Buße fuhren", "Busse fuhren"),
                             ("Aß im", "Ass im")):
            if falsch in neu:
                b.add("FEHLER", f"Normalisierer verfaelscht: '{soll}' -> "
                                f"'{falsch}'")
        for soll in ("Straße", "groß", "draußen", " – ", "»goed«", "…"):
            if soll not in neu:
                b.add("FEHLER", f"Normalisierer setzt '{soll}' nicht")
        b.add("OK", f"Normalisierer laeuft ({sum(zaehler.values())} "
                    f"Aenderungen auf der Probe)")
    except Exception as e:
        b.add("FEHLER", "Normalisierer wirft Ausnahme", repr(e))

    try:
        n, treffer = G.diminutive_zaehlen(
            "Sie wollte sprechen, aber zwischen ihnen lag ein Zeichen. "
            "Ein Häuschen, ein Mädchen, ein Fräulein.")
        if n != 3:
            b.add("FEHLER", f"Diminutivzaehler liefert {n} statt 3",
                  f"Treffer: {treffer}")
        else:
            b.add("OK", "Diminutivzaehler korrekt (3 von 3)")
    except Exception as e:
        b.add("FEHLER", "Diminutivzaehler wirft Ausnahme", repr(e))

    try:
        q, mit, ges = G.perfekt_quote(
            "Er ging nach Hause. Sie sagte, dass er es gesagt hat. "
            "Ich habe es gesehen.")
        if mit != 2:
            b.add("WARN", f"Perfektmetrik findet {mit} von 2 erwarteten")
        else:
            b.add("OK", f"Perfektmetrik korrekt ({mit}/{ges} Saetze)")
    except Exception as e:
        b.add("FEHLER", "Perfektmetrik wirft Ausnahme", repr(e))

    try:
        p_ueb, p_rev = U.prompts(cfg)
        p_stil, p_korr = L.prompts(cfg)
        for name, p in (("Übersetzung", p_ueb), ("Revision", p_rev),
                        ("Stil", p_stil), ("Korrektorat", p_korr)):
            if "<!--" in p:
                b.add("FEHLER", f"Prompt '{name}' enthaelt HTML-Kommentare",
                      "anweisungen.md wird nicht gefiltert (F2).")
            if len(p) < 400:
                b.add("WARN", f"Prompt '{name}' auffaellig kurz ({len(p)})")
        b.add("OK", "Alle vier Prompts baubar, keine Kommentarreste")
    except Exception as e:
        b.add("FEHLER", "Prompt-Bau wirft Ausnahme", repr(e))

    try:
        block = U.block_fallen("Hij zou ziek zijn en liep naar de winkel met "
                              "een biertje. Er waren veel mensen.", cfg)
        if "zou" not in block or "winkel" not in block:
            b.add("WARN", "Fallenblock findet die Testfaelle nicht",
                  block[:200])
        else:
            b.add("OK", "Fallenblock erkennt zou, winkel, Diminutiv")
    except Exception as e:
        b.add("FEHLER", "Fallenblock wirft Ausnahme", repr(e))


# ==================================================================
def pruefe_ollama(cfg, b):
    b.abschnitt("Backend und Modell")
    b.add("INFO", "Backend", cfg.get("backend", "ollama"))
    try:
        modelle = G.modelle_vorhanden(cfg)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        if code == 401:
            b.add("FEHLER", f"Port {cfg['ollama_host']} liefert 401",
                  "Davor sitzt der vast.ai-Proxy, nicht Ollama.\n"
                  "           ss -tlnp | grep ollama  — Port in "
                  "projekt.json eintragen.")
        else:
            b.add("FEHLER", f"Backend antwortet mit HTTP {code}")
        return False
    except Exception as e:
        b.add("FEHLER", f"Backend nicht erreichbar ({cfg['ollama_host']})",
              f"{e}\n           ss -tlnp | grep ollama")
        return False

    b.add("OK", f"Backend erreichbar ({cfg['ollama_host']})")
    if cfg["modell"] not in modelle:
        fam = [m for m in modelle
               if m.split(":")[0] == cfg["modell"].split(":")[0]]
        if len(fam) == 1:
            b.add("WARN", f"'{cfg['modell']}' nicht vorhanden",
                  f"Benutze '{fam[0]}'.")
            cfg["modell"] = fam[0]
        else:
            b.add("FEHLER", f"Modell '{cfg['modell']}' fehlt",
                  f"Vorhanden: {', '.join(modelle) or 'keines'}\n"
                  f"           ollama pull {cfg['modell']}")
            return False
    else:
        b.add("OK", f"Modell vorhanden: {cfg['modell']}")
    return True


def pruefe_gpu(cfg, b):
    b.abschnitt("GPU-Belegung")
    print("  Lade Modell zur Pruefung (kann einige Minuten dauern) ...")
    try:
        requests.post(f"{cfg['ollama_host']}/api/chat", timeout=(10, 1200),
                      json={"model": cfg["modell"],
                            "messages": [{"role": "user", "content": "Hallo"}],
                            "stream": False, "keep_alive": "60m",
                            "options": {"num_ctx": cfg["num_ctx"],
                                        "num_predict": 4}}).raise_for_status()
    except Exception as e:
        b.add("FEHLER", "Testanfrage fehlgeschlagen", str(e))
        return
    try:
        ps = subprocess.run(["ollama", "ps"], capture_output=True,
                            text=True, timeout=30).stdout
    except Exception as e:
        b.add("WARN", "'ollama ps' nicht ausfuehrbar", str(e))
        return

    zeile = next((l for l in ps.splitlines()
                  if cfg["modell"].split(":")[0] in l), "")
    if not zeile:
        b.add("WARN", "Modell nach der Testanfrage nicht in 'ollama ps'")
    elif "100% GPU" in zeile:
        b.add("OK", "Modell vollstaendig im VRAM (100% GPU)")
    elif "CPU" in zeile:
        m = re.search(r"(\d+)%/(\d+)%\s*CPU/GPU", zeile)
        b.add("FEHLER", "Modell nicht vollstaendig im VRAM "
                        f"({m.group(1)+'% CPU' if m else 'teilweise CPU'})",
              "Der Lauf waere um Groessenordnungen langsamer.\n"
              "           'num_ctx' senken, kleinere Quantisierung oder "
              "groessere Instanz.")
    else:
        b.add("WARN", "GPU-Anteil unklar", zeile.strip())

    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used",
             "--format=csv,noheader"], capture_output=True, text=True,
            timeout=20).stdout.strip()
        for l in smi.splitlines():
            b.add("INFO", "GPU", l.strip())
    except Exception:
        pass


def pruefe_umgebung(b):
    b.abschnitt("Umgebung")
    try:
        st = os.statvfs(".")
        frei = st.f_bavail * st.f_frsize / 1e9
        (b.add("FEHLER", f"Nur {frei:.0f} GB frei", "Mindestens 20 GB noetig.")
         if frei < 20 else b.add("OK", f"{frei:.0f} GB frei"))
    except Exception as e:
        b.add("WARN", "Plattenplatz nicht ermittelbar", str(e))
    try:
        __import__("requests")
        b.add("OK", "Modul 'requests' vorhanden")
    except ImportError:
        b.add("FEHLER", "Modul 'requests' fehlt",
              "pip install requests --break-system-packages")


# ==================================================================
def pruefe_text(cfg, b):
    b.abschnitt("Manuskript (niederlaendisch)")
    pfad = G.F["quelle"]
    if not os.path.exists(pfad):
        b.add("FEHLER", f"{pfad} nicht gefunden", f"cwd: {os.getcwd()}")
        return None

    try:
        text = open(pfad, "rb").read().decode("utf-8")
        b.add("OK", "Kodierung UTF-8")
    except UnicodeDecodeError:
        b.add("FEHLER", "Datei ist nicht UTF-8",
              "iconv -f ISO-8859-1 -t UTF-8 input.txt > t && mv t input.txt")
        return None

    if "\r\n" in text:
        b.add("WARN", "Windows-Zeilenenden", "sed -i 's/\\r$//' input.txt")
    for z, name in (("\u200b", "Zero-width space"), ("\f", "Form feed"),
                    ("\xa0", "Geschuetztes Leerzeichen")):
        if text.count(z):
            b.add("WARN", f"{text.count(z)}x {name}",
                  "Stammt meist aus PDF- oder Word-Export.")

    low = text.lower()
    nl = sum(len(re.findall(p, low)) for p in NL_MARKER)
    de = sum(len(re.findall(p, low)) for p in DE_MARKER)
    if nl < de:
        b.add("FEHLER", "Der Text sieht nicht niederlaendisch aus",
              f"NL-Marker {nl}, DE-Marker {de}. Falsche Datei?")
        return None
    b.add("OK", f"Quelltext ist niederlaendisch (Marker {nl} zu {de})")

    paras = G.absaetze(text)
    woerter = len(text.split())
    b.add("INFO", "Umfang", f"{woerter} Woerter, {len(paras)} Absaetze")
    if len(paras) < 20:
        b.add("FEHLER", f"Nur {len(paras)} Absaetze erkannt",
              "Absaetze muessen durch Leerzeilen getrennt sein.\n"
              "           head -c 600 input.txt")
        return None

    laengen = sorted(len(p.split()) for p in paras)
    median = laengen[len(laengen) // 2]
    b.add("INFO", "Absatzlaenge",
          f"Median {median}, Mittel {sum(laengen)/len(laengen):.0f}, "
          f"Maximum {laengen[-1]}")
    if median < 25:
        b.add("INFO", "Dialoglastiger Text",
              f"Bei Median {median} lohnt der Chunkgroessen-Vergleich "
              f"({cfg['chunk_words']} gegen {cfg['chunk_words_variante']}).")

    kandidaten = {"„…“": text.count("\u201e"), "“…”": text.count("\u201c"),
                  "«…»": text.count("\u00ab"), "‘…’": text.count("\u2018"),
                  'gerade "': text.count('"'),
                  "Gedankenstrich": len(re.findall(r"(?m)^\s*[\u2014\u2013]\s",
                                                   text))}
    dom = max(kandidaten, key=kandidaten.get)
    if kandidaten[dom] < 10:
        b.add("WARN", "Kaum Dialogmarkierung gefunden")
    else:
        b.add("INFO", "Dialogtypografie der Quelle",
              f"vorwiegend {dom} ({kandidaten[dom]}x) — wird auf "
              f"{'»…«' if cfg['quotes']=='guillemets' else '„…“'} umgestellt")

    dim = len(re.findall(r"\b\w{3,}(?:tje|pje|kje|je)s?\b", low))
    b.add("INFO", "Diminutive in der Quelle",
          f"{dim} ({dim/max(1,woerter/1000):.1f} je 1000 Woerter) — "
          f"Politik: {cfg['diminutive']}")
    u = len(re.findall(r"\bu\b", low))
    jij = len(re.findall(r"\b(jij|je|jou|jouw|jullie)\b", low))
    b.add("INFO", "Anredeformen",
          f"u: {u}, jij/je: {jij} — Vorgabe: {cfg['anrede_vorgabe']}")
    zou = len(re.findall(r"\bzou(den)?\b", low))
    b.add("INFO", "Evidentielles 'zou'",
          f"{zou} Vorkommen — jedes braucht die Entscheidung "
          f"'soll' gegen 'wuerde'")
    return text


ATTRIB = re.compile(r"^[\u2014\u2013-]?\s*[A-ZÄÖÜÉÈ][A-ZÄÖÜÉÈ\s.'’-]{3,60}$")


def finde_zitate(text, b):
    """F3: Epigraph UND Attributionszeile werden gemeinsam ausgeklammert."""
    b.abschnitt("Zitate und Motti")
    paras = G.absaetze(text)
    erstes_kapitel = next(
        (i for i, p in enumerate(paras)
         if re.fullmatch(r"\d{1,3}", p.strip())
         or re.fullmatch(r"(?i)(hoofdstuk|deel)\s+\S+", p.strip())),
        min(12, len(paras)))

    sicher, verdacht = [], []
    for i in range(max(0, erstes_kapitel - 1)):
        if i + 1 < len(paras) and ATTRIB.match(paras[i + 1].strip()) \
           and len(paras[i].split()) >= 4:
            sicher.append({"index": i, "index_attribution": i + 1,
                           "typ": "epigraph", "text": paras[i],
                           "attribution": paras[i + 1].strip(),
                           "original_deutsch": None, "status": "offen"})

    for i in range(erstes_kapitel, len(paras)):
        p = paras[i].strip()
        if re.match(r'^["„“«»\u2018].{20,300}["”«»\u2019]$', p) and \
           re.search(r"\b(zong|zingt|lied|gedicht|schreef|citeer\w*|regel)\b",
                     p, re.I):
            verdacht.append({"index": i, "text": p[:140]})

    if sicher:
        b.add("WARN", f"{len(sicher)} Epigraph(en) erkannt",
              "Zitat und Attributionszeile werden ausgeklammert. Deutschen "
              "Wortlaut in zitate.json eintragen.")
        for z in sicher:
            b.add("INFO", f"  Absatz {z['index']}+{z['index_attribution']}",
                  z["attribution"])
    else:
        b.add("OK", "Kein Epigraph vor Kapitel 1 erkannt")

    if verdacht:
        b.add("INFO", f"{len(verdacht)} moegliche Zitate im Fliesstext",
              "Werden NICHT ausgeklammert. Siehe zitate_verdacht.txt.")
        with open("zitate_verdacht.txt", "w", encoding="utf-8") as f:
            f.write("Moegliche Zitate im Fliesstext — bitte durchsehen.\n"
                    "Zum Ausklammern nach zitate.json uebernehmen.\n"
                    + "=" * 64 + "\n\n")
            for v in verdacht:
                f.write(f"Absatz {v['index']}:\n  {v['text']}\n\n")

    json.dump({"epigraphen": sicher},
              open(G.F["zitate"], "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


# ==================================================================
SCHEMA = {
    "glossar":    ("Abbildung nl -> de", lambda d: all(
        isinstance(k, str) and isinstance(v, str) for k, v in d.items())),
    "personen":   ("Abbildung Name -> Pronomen", lambda d: all(
        isinstance(v, str) and ("/" in v or v.strip()) for v in d.values())),
    "figuren":    ("je Figur ein Objekt", lambda d: all(
        isinstance(v, dict) for k, v in d.items() if not k.startswith("_"))),
    "anrede":     ("je Eintrag ein Objekt", lambda d: all(
        isinstance(v, dict) for k, v in d.items() if not k.startswith("_"))),
    "leitmotive": ("je Eintrag ein Objekt", lambda d: all(
        isinstance(v, dict) for k, v in d.items() if not k.startswith("_"))),
}


def pruefe_begleitdateien(cfg, b, streng):
    """F4: auch im Schnellmodus, mit Schemapruefung. 'streng' verlangt ein
    nichtleeres Glossar."""
    b.abschnitt("Begleitdateien")
    for schluessel, (beschreibung, pruef) in SCHEMA.items():
        pfad = G.F[schluessel]
        if not os.path.exists(pfad):
            if streng and schluessel in ("glossar", "personen"):
                b.add("FEHLER", f"{pfad} fehlt",
                      "Nach der Glossarphase muss die Datei vorliegen.")
            else:
                b.add("INFO", f"{pfad} fehlt noch",
                      "Wird in der Konkordanzphase erzeugt.")
            continue
        try:
            d = json.load(open(pfad, encoding="utf-8"))
        except Exception as e:
            b.add("FEHLER", f"{pfad} ist kein gueltiges JSON", str(e))
            continue
        if not isinstance(d, dict):
            b.add("FEHLER", f"{pfad} ist kein JSON-Objekt")
            continue
        nutz = {k: v for k, v in d.items() if not k.startswith("_")}
        if streng and schluessel == "glossar" and not nutz:
            b.add("FEHLER", "glossar.json ist leer",
                  f"glossar_quelle ist '{cfg['glossar_quelle']}' — ohne "
                  f"Glossar liefe der Lauf ohne Terminologie.")
            continue
        if not pruef(nutz):
            b.add("FEHLER", f"{pfad} entspricht dem Schema nicht",
                  f"Erwartet: {beschreibung}")
            continue
        b.add("OK", f"{pfad}: {len(nutz)} Eintraege, Schema in Ordnung")

    if os.path.exists(G.ANWEISUNGEN):
        gefuellt = [a for a in ("Übersetzung", "Stillektorat", "Korrektorat")
                    if G.lade_anweisungen(a)]
        roh = open(G.ANWEISUNGEN, encoding="utf-8").read()
        if "<!--" in roh:
            b.add("INFO", f"{G.ANWEISUNGEN} enthaelt Kommentare",
                  "Werden herausgefiltert und gelangen nicht in die Prompts.")
        b.add("OK", f"{G.ANWEISUNGEN} vorhanden",
              f"Abschnitte mit echtem Inhalt: {', '.join(gefuellt) or 'keine'}")
    else:
        b.add("INFO", f"{G.ANWEISUNGEN} fehlt",
              "Ohne Sonderanweisungen laufen die Standardvorgaben.")


def pruefe_config(cfg, b):
    b.abschnitt("Konfiguration")
    b.add("INFO", "Zielform",
          f"{cfg['varietaet']}, "
          f"{'»…«' if cfg['quotes']=='guillemets' else '„…“'}, "
          f"{'mit ß' if cfg['eszett'] else 'ohne ß'}")
    b.add("INFO", "Diminutive", cfg["diminutive"])
    b.add("INFO", "Erzähltempus", cfg["tempus"])
    b.add("INFO", "Chunkgroesse",
          f"{cfg['chunk_words']} (Vergleichsvariante "
          f"{cfg['chunk_words_variante']})")
    if cfg["chunk_words"] * 4 > cfg["num_ctx"]:
        b.add("WARN", "num_ctx knapp fuer die Chunkgroesse",
              f"Revisionspass braucht etwa {cfg['chunk_words']*4} Token.")
    unbekannt = [p for p in cfg["lektorat_passes"]
                 if p not in ("det", "stil", "korrektorat")]
    if unbekannt:
        b.add("FEHLER", f"Unbekannte Lektoratsstufe: {', '.join(unbekannt)}")
    else:
        b.add("OK", "Lektoratsfolge: " + " -> ".join(cfg["lektorat_passes"]))
    if cfg["ratio_kalibriert"]:
        b.add("OK", f"Prueffgrenzen kalibriert: "
                    f"{cfg['ratio_min']:.2f}–{cfg['ratio_max']:.2f}")
    else:
        b.add("INFO", "Prueffgrenzen noch nicht kalibriert",
              "Werden nach dem Testlauf aus den Messwerten gesetzt.")
    b.add("INFO", "Konfigurationsfingerabdruck", G.config_hash(cfg))


# ==================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--selbsttest", action="store_true",
                    help="nur den Selbsttest, ohne Modell")
    ap.add_argument("--streng", action="store_true",
                    help="Begleitdateien muessen vollstaendig sein")
    args = ap.parse_args()

    G.kopf("PREFLIGHT" + (" (kurz)" if args.quick else ""))
    cfg = G.lade_config(pflicht=False)
    b = G.Bericht("PREFLIGHT")

    selbsttest(cfg, b)
    if args.selbsttest:
        ok = b.schreiben(REPORT)
        sys.exit(0 if ok else 1)

    if b.fehler:
        b.add("FEHLER", "Selbsttest fehlgeschlagen — kein Modellaufruf")
        b.schreiben(REPORT)
        sys.exit(1)

    if not pruefe_ollama(cfg, b):
        b.schreiben(REPORT)
        sys.exit(1)
    pruefe_gpu(cfg, b)
    pruefe_begleitdateien(cfg, b, args.streng)      # F4: immer

    if not args.quick:
        pruefe_umgebung(b)
        pruefe_config(cfg, b)
        text = pruefe_text(cfg, b)
        if text:
            finde_zitate(text, b)

    G.speichere_config(cfg)
    ok = b.schreiben(REPORT)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
