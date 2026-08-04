#!/usr/bin/env python3
"""
Einmalige Verifikation vor dem ersten Volllauf.

Holt nach, was sich ohne API-Schluessel und ohne offenes Netz nicht
pruefen liess (Auftrag Paket 1, verschoben nach Paket 2):

  1. Schreibsemantik des Drive-Mounts   — ohne Modellaufruf
  2. Ein-Token-Ping je Anbieter
  3. Mini-Echtlauf: ein Kurz-Chunk je Anbieter, mit Token-Usage
  4. Sampling-Doktrin am lebenden Objekt: dasselbe Payload mit
     'temperature' — belegt das dokumentierte HTTP 400, statt es zu glauben
  5. Google-Tarife gegen die Preisseite

Aufruf im Projektordner (Arbeitsverzeichnis), nicht im Code-Verzeichnis:

    python3 verifikation.py
    python3 verifikation.py --ohne-netz     nur Schreibtest

Die Modellaufrufe kosten wenige Cent. Sie werden unter der Rolle
'verifikation' gebucht und verfaelschen die Rollenstatistik des Buchs
damit nicht.
"""

import argparse
import json
import os
import re
import sys
import time

import requests

import gemeinsam as G

# Selbst geschriebener Probetext — bewusst KEIN Buchtext, damit nichts
# Urheberrechtlich geschuetztes im Repo landet.
PROBE_NL = ("De oude man zette zijn kopje neer en keek naar buiten. "
            "Het regende al de hele ochtend, en de straat lag er verlaten "
            "bij. Hij zou nog even wachten, dacht hij, voordat hij zijn "
            "jas zou pakken.")
PROBE_SYSTEM = ("Du uebersetzt einen niederlaendischen Satz ins Deutsche. "
                "Gib ausschliesslich die Uebersetzung aus, ohne Vorrede.")

PREISSEITE = "https://ai.google.dev/gemini-api/docs/pricing"


class Ergebnis:
    def __init__(self):
        self.zeilen, self.fehler, self.warnungen = [], 0, 0

    def ok(self, thema, text=""):
        self._add("[ok]  ", thema, text)

    def warn(self, thema, text=""):
        self.warnungen += 1
        self._add("[warn]", thema, text)

    def fehl(self, thema, text=""):
        self.fehler += 1
        self._add("[FEHL]", thema, text)

    def info(self, thema, text=""):
        self._add("[info]", thema, text)

    def _add(self, sym, thema, text):
        zeile = f"{sym} {thema}"
        if text:
            zeile += "\n         " + str(text).replace("\n", "\n         ")
        print(zeile, flush=True)
        self.zeilen.append(zeile)


# ==================================================================
def pruefe_schreiben(e):
    """Genau die Sequenz, die G.teil_schreiben fuer jeden Chunk benutzt.

    Auf einem FUSE-Mount ist os.replace nicht selbstverstaendlich. Wenn
    das hier bricht, bricht es sonst drei Stunden in den Lauf hinein."""
    print("\n--- 1 · Schreibsemantik des Arbeitsverzeichnisses " + "-" * 12)
    probe = "0000.txt"
    ordner = os.path.join("teile", "_verifikation")
    try:
        os.makedirs(ordner, exist_ok=True)
        pfad = os.path.join(ordner, probe)
        tmp = pfad + ".tmp"
        inhalt = f"Probe {time.time()}\nUmlaute: ä ö ü ß — »Guillemets«\n"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(inhalt)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, pfad)
        zurueck = open(pfad, encoding="utf-8").read()
        if zurueck != inhalt:
            e.fehl("Zurueckgelesener Inhalt weicht ab",
                   "Der Mount liefert nicht, was geschrieben wurde.")
        else:
            e.ok(f"Schreiben, fsync, os.replace, Zuruecklesen in "
                 f"{os.getcwd()}")
        os.remove(pfad)
        os.rmdir(ordner)
    except Exception as ex:
        e.fehl("Schreibtest fehlgeschlagen", f"{type(ex).__name__}: {ex}\n"
               "Der Lauf koennte Chunks verlieren. Vor dem Volllauf klaeren.")


# ==================================================================
def _anbieter_rollen(cfg):
    """Je Anbieter eine aktive Rolle und ihr Modell."""
    treffer = {}
    for rolle in G.aktive_rollen(cfg):
        modell = G.modell_fuer(cfg, rolle)
        anbieter = G.backend_name(modell)
        if anbieter in ("anthropic", "google"):
            treffer.setdefault(anbieter, (rolle, modell))
    return treffer


def _alle_modelle(cfg):
    """Jedes konfigurierte API-Modell einmal, mit den Rollen die es nutzen.

    Bewusst ueber ALLE Rollen, nicht nur die aktiven: 'annotation' und
    'vergleich' rufen erst in spaeteren Paketen ein Modell. Ein falscher
    Name dort faellt sonst erst auf, wenn der Schritt gebaut wird — und
    genau so ist der Judge-Name durchgerutscht."""
    treffer = {}
    for rolle in G.ROLLEN:
        modell = G.modell_fuer(cfg, rolle)
        if G.backend_name(modell) in ("anthropic", "google"):
            treffer.setdefault(modell, []).append(rolle)
    return treffer


def kandidaten(anbieter, modell):
    """Bei 404: was der Anbieter wirklich anbietet.

    Der Preisname und der API-Name eines Modells sind nicht dasselbe.
    Statt zu raten wird die Modellliste geholt und gefiltert."""
    try:
        alle = G.BACKENDS[anbieter].verfuegbare_modelle({})
    except Exception as ex:
        return f"Modellliste nicht abrufbar: {type(ex).__name__}: {ex}"
    if not alle:
        return "Modellliste leer oder nicht unterstuetzt."
    stamm = re.split(r"[-.]", modell)[0]
    nah = [m for m in alle if m.startswith(stamm)]
    return ("Verfuegbar (Auswahl):\n  " + "\n  ".join(nah or alle[:25])
            + f"\n\nPassenden Namen in projekt.json als modell_<rolle> "
              f"eintragen.")


def pruefe_ping(e, cfg):
    """Pingt JEDES konfigurierte Modell, auch das spaeterer Pakete.

    Gibt die Anbieter zurueck, deren Modell der aktiven Rollen traegt."""
    print("\n--- 2 · Ein-Token-Ping " + "-" * 38)
    aktiv = {m for r, m in ((r, G.modell_fuer(cfg, r))
                            for r in G.aktive_rollen(cfg))}
    tragen = set()
    for modell, rollen in sorted(_alle_modelle(cfg).items()):
        anbieter = G.backend_name(modell)
        wann = "" if modell in aktiv else "  (erst in spaeteren Paketen)"
        probe = dict(cfg)
        probe["max_tokens_api"] = 1
        t0 = time.time()
        try:
            G.BACKENDS[anbieter].chat(probe, "Antworte mit OK.", "OK",
                                      rolle="verifikation", modell=modell)
            e.ok(f"{modell} antwortet ({time.time()-t0:.1f}s)",
                 f"Rollen: {', '.join(rollen)}{wann}")
            if modell in aktiv:
                tragen.add(anbieter)
        except SystemExit as ex:
            e.fehl(f"{anbieter}: {ex}")
        except Exception as ex:
            # Ein nicht existierendes Modell ist kein Ping-Problem, das man
            # spaeter nochmal versuchen koennte — es scheitert jedes Mal.
            if "HTTP 404" in str(ex):
                e.fehl(f"{modell} existiert unter diesem Namen nicht",
                       f"Rollen: {', '.join(rollen)}{wann}\n"
                       + kandidaten(anbieter, modell))
            else:
                e.warn(f"{modell}: keine verwertbare Antwort auf den Ping",
                       f"{type(ex).__name__}: {ex}")
                if modell in aktiv:
                    tragen.add(anbieter)   # koennte voruebergehend sein
    return tragen


def pruefe_echtlauf(e, cfg, anbieter_rollen, tragen):
    """Mini-Echtlauf: ein Kurz-Chunk je Anbieter, mit Usage-Ausweis."""
    print("\n--- 3 · Mini-Echtlauf " + "-" * 39)
    e.info("Probetext (selbst geschrieben, kein Buchtext)",
           PROBE_NL[:80] + " …")
    for anbieter, (rolle, modell) in sorted(anbieter_rollen.items()):
        if anbieter not in tragen:
            e.info(f"{modell}: uebersprungen",
                   "Der Ping ist bereits gescheitert — siehe oben.")
            continue
        vorher = _usage_stand()
        t0 = time.time()
        try:
            text = G.BACKENDS[anbieter].chat(
                cfg, PROBE_SYSTEM, PROBE_NL,
                rolle="verifikation", modell=modell)
        except Exception as ex:
            e.fehl(f"{modell}: Echtlauf fehlgeschlagen",
                   f"{type(ex).__name__}: {ex}")
            continue
        nachher = _usage_stand()
        d = {k: nachher.get(k, 0) - vorher.get(k, 0)
             for k in ("ein", "aus", "cache_lesen", "cache_schreiben")}
        if not text.strip():
            e.fehl(f"{modell}: leere Antwort")
            continue
        if not d["ein"] and not d["aus"]:
            e.warn(f"{modell}: keine Token-Usage erfasst",
                   "Ein modellrufender Schritt ohne Usage gilt als unfertig.")
        e.ok(f"{modell} ({time.time()-t0:.1f}s)",
             f"Antwort: {text.strip()[:160]}\n"
             f"Usage:   {d['ein']} ein / {d['aus']} aus"
             + (f", Cache {d['cache_lesen']} gelesen / "
                f"{d['cache_schreiben']} geschrieben"
                if d["cache_lesen"] or d["cache_schreiben"] else ""))


def _usage_stand():
    try:
        m = json.load(open(G.MANIFEST, encoding="utf-8"))
        e = m.get("kosten", {}).get("verifikation", {})
        return {k: e.get(k, 0) for k in
                ("ein", "aus", "cache_lesen", "cache_schreiben")}
    except Exception:
        return {}


# ==================================================================
def pruefe_sampling(e, cfg, anbieter_rollen, tragen):
    """Schickt das echte Payload plus 'temperature' und meldet, was kommt.

    Das ist der Beleg fuer die Entscheidung aus ENTSCHEIDUNGEN.md — und
    zugleich der Hinweis, falls ein Anbieter seine Haltung aendert."""
    print("\n--- 4 · Sampling-Doktrin am lebenden Objekt " + "-" * 17)
    for anbieter, (rolle, modell) in sorted(anbieter_rollen.items()):
        if anbieter not in tragen:
            continue
        b = G.BACKENDS[anbieter]
        p = b.payload(cfg, PROBE_SYSTEM, PROBE_NL, "verifikation", modell)
        p = dict(p)
        if anbieter == "anthropic":
            p["temperature"] = 0.35
            url = b.URL
            kopf = {"x-api-key": G.api_schluessel("anthropic"),
                    "anthropic-version": b.VERSION,
                    "content-type": "application/json"}
        else:
            p["generationConfig"] = {"temperature": 0.35}
            url = f"{b.BASIS}/{modell}:generateContent"
            kopf = {"x-goog-api-key": G.api_schluessel("google"),
                    "content-type": "application/json"}
        try:
            r = requests.post(url, json=p, headers=kopf, timeout=(10, 120))
        except Exception as ex:
            e.warn(f"{modell}: Sampling-Probe nicht durchfuehrbar", str(ex))
            continue
        if r.status_code == 400:
            e.ok(f"{modell} lehnt 'temperature' mit HTTP 400 ab",
                 "Bestaetigt: keine Sampling-Parameter senden.")
        elif r.status_code == 200:
            e.warn(f"{modell} akzeptiert 'temperature' (HTTP 200)",
                   "Die Doktrin bleibt richtig — der Parameter wirkt laut "
                   "Anbieter nicht und faellt kuenftig weg. Aber die "
                   "Begruendung in ENTSCHEIDUNGEN.md sollte das "
                   "widerspiegeln.")
        else:
            e.info(f"{modell}: HTTP {r.status_code} auf die Sampling-Probe",
                   (r.text or "")[:200])


# ==================================================================
def pruefe_tarife(e):
    """Vergleicht die hinterlegten Google-Tarife mit der Preisseite."""
    print("\n--- 5 · Google-Tarife " + "-" * 39)
    try:
        r = requests.get(PREISSEITE, timeout=(10, 60),
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as ex:
        e.warn("Preisseite nicht erreichbar",
               f"{PREISSEITE}\n{type(ex).__name__}: {ex}\n"
               "Tarife bleiben unverifiziert (geprueft: False).")
        return

    text = re.sub(r"<[^>]+>", " ", r.text)
    text = re.sub(r"\s+", " ", text)
    for modell in ("gemini-3.1-pro", "gemini-3.6-flash"):
        t = G.TARIFE[modell]
        stellen = [m.start() for m in re.finditer(re.escape(modell), text)]
        if not stellen:
            e.warn(f"{modell} auf der Preisseite nicht gefunden",
                   "Modellname geaendert? Manuell nachsehen.")
            continue
        umfeld = " ".join(text[max(0, s - 300):s + 600] for s in stellen[:3])
        erwartet = (f"{t['ein']:.2f}", f"{t['aus']:.2f}")
        gefunden = [w for w in erwartet if w in umfeld]
        if len(gefunden) == 2:
            e.ok(f"{modell}: {erwartet[0]} / {erwartet[1]} $ je Mio Token "
                 f"auf der Seite belegt")
        else:
            zahlen = sorted(set(re.findall(r"\$ ?(\d+\.\d{2})", umfeld)))[:8]
            e.warn(f"{modell}: hinterlegt {erwartet[0]} / {erwartet[1]} $, "
                   f"auf der Seite nicht so belegt",
                   f"Gefundene Betraege im Umfeld: "
                   f"{', '.join(zahlen) or 'keine'}\n"
                   f"Bitte manuell abgleichen: {PREISSEITE}")


# ==================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ohne-netz", action="store_true",
                    help="nur den Schreibtest, keine Modellaufrufe")
    args = ap.parse_args()

    G.kopf("VERIFIKATION")
    print(f"Arbeitsverzeichnis: {os.getcwd()}")
    print(f"Code:               {os.path.dirname(os.path.abspath(__file__))}")

    cfg = G.lade_config(pflicht=False)
    e = Ergebnis()

    pruefe_schreiben(e)

    if not args.ohne_netz:
        anbieter_rollen = _anbieter_rollen(cfg)
        if not anbieter_rollen:
            e.info("Keine API-Rolle aktiv",
                   "Keine Rolle ist einem Modell zugeordnet — "
                   "'pipeline.py modelle' zeigt die Belegung.")
        else:
            tragen = pruefe_ping(e, cfg)
            pruefe_echtlauf(e, cfg, anbieter_rollen, tragen)
            pruefe_sampling(e, cfg, anbieter_rollen, tragen)
        pruefe_tarife(e)

    print("\n" + "=" * 62)
    print(f"Ergebnis: {e.fehler} Fehler, {e.warnungen} Warnungen")
    print("BESTANDEN" if e.fehler == 0 else "NICHT BESTANDEN")
    print("=" * 62)
    print("\nDiese Ausgabe bitte zurueckmelden — daraus wird der "
          "Ergebnisteil\nvon ABBRUCHPROBE.md und der Verifikationsstand "
          "der Tarife gesetzt.")
    sys.exit(0 if e.fehler == 0 else 1)


if __name__ == "__main__":
    main()
