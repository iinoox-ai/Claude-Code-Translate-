#!/usr/bin/env python3
"""
Gemeinsames Modul — Pipeline NIEDERLAENDISCH -> DEUTSCH.

Wird von allen anderen Skripten importiert. Nichts hier wird direkt
aufgerufen; Einstieg ist pipeline.py.

ACHTUNG: Dieser Skriptsatz ist fuer NL -> DE. Jedes Skript gibt die
Sprachrichtung beim Start aus, und projekt.json traegt "sprachpaar": "nl-de".
"""

import hashlib
import json
import os
import re
import sys
import time

import requests

RICHTUNG = "NL \u2192 DE"

CONFIG      = "projekt.json"
ANWEISUNGEN = "anweisungen.md"
MANIFEST    = "manifest.json"

F = {
    "quelle":        "input.txt",
    "glossar":       "glossar.json",
    "personen":      "personen.json",
    "figuren":       "figurenblatt.json",
    "anrede":        "anrede.json",
    "leitmotive":    "leitmotive.json",
    "zitate":        "zitate.json",
    "entwurf":       "uebersetzung_entwurf.txt",
    "uebersetzung":  "uebersetzung_deutsch.txt",
    "normalisiert":  "normalisiert.txt",
    "lektoriert":    "manuskript_lektoriert.txt",
}

# Verzeichnisse fuer Einzel-Chunks (macht Resume und Retranslate robust)
TEILE = {
    "uebersetzung": "teile/uebersetzung",
    "entwurf":      "teile/entwurf",
    "lektorat":     "teile/lektorat",
}


# ==================================================================
# Konfiguration
# ==================================================================
STANDARD = {
    "sprachpaar":                "nl-de",
    "varietaet":                 "bundesdeutsch",
    "quotes":                    "guillemets",
    "dash":                      "halbgeviert",
    "eszett":                    True,

    "backend":                   "ollama",
    "modell":                    "mistral-medium-3.5:128b-q8_0",
    "ollama_host":               "http://localhost:21434",
    "num_ctx":                   16384,

    "chunk_words":               800,
    "chunk_words_variante":      1200,      # fuer den Chunkgroessen-Vergleich
    "context_words":             250,
    "temperature_uebersetzung":  0.35,
    "temperature_revision":      0.25,
    "temperature_stil":          0.25,
    "temperature_korrektorat":   0.10,
    "revision_pass":             True,

    "lektorat_passes":           ["det", "stil", "korrektorat", "det"],

    "glossar_quelle":            "extern",
    "export_glossar":            True,
    "export_bewertung":          True,

    "test_words_erzaehlung":     1500,
    "test_words_dialog":         1500,

    "ratio_min":                 0.90,
    "ratio_max":                 1.20,
    "ratio_kalibriert":          False,
    "lektorat_ratio_min":        0.92,
    "lektorat_ratio_max":        1.10,

    "diminutive":                "aufloesen",
    "tempus":                    "quellnah",
    "anrede_vorgabe":            "u=Sie, jij/je=du",

    "timeout_connect":           10,
    "timeout_read":              900,       # 15 min statt 90 — Retry greift schneller
    "max_retries":               3,
}

# Diese Schluessel werden von der Pipeline selbst gesetzt und duerfen von
# einer eingespielten projekt.json NICHT ueberschrieben werden (V4).
GESCHUETZT = {"ratio_min", "ratio_max", "ratio_kalibriert", "sprachpaar"}

# Nur diese Schluessel darf ein externes Rueckspiel aendern (V4).
AENDERBAR = {
    "chunk_words", "chunk_words_variante", "context_words",
    "temperature_uebersetzung", "temperature_revision",
    "temperature_stil", "temperature_korrektorat",
    "revision_pass", "lektorat_passes",
    "diminutive", "tempus", "anrede_vorgabe",
    "quotes", "eszett", "varietaet", "dash",
    "num_ctx", "modell", "backend", "ollama_host",
    "test_words_erzaehlung", "test_words_dialog",
    "lektorat_ratio_min", "lektorat_ratio_max",
    "export_glossar", "export_bewertung", "glossar_quelle",
    "timeout_connect", "timeout_read", "max_retries",
}


def lade_config(pfad=CONFIG, pflicht=True):
    if not os.path.exists(pfad):
        if pflicht:
            sys.exit(f"FEHLER: {pfad} fehlt. Erst 'python3 pipeline.py init'.")
        return dict(STANDARD)
    cfg = dict(STANDARD)
    try:
        cfg.update(json.load(open(pfad, encoding="utf-8")))
    except Exception as e:
        sys.exit(f"FEHLER: {pfad} nicht lesbar — {e}")
    if cfg.get("sprachpaar") != "nl-de":
        sys.exit(f"FEHLER: projekt.json ist fuer '{cfg.get('sprachpaar')}', "
                 f"dieser Skriptsatz ist fuer 'nl-de'.")
    return cfg


def speichere_config(cfg, pfad=CONFIG):
    json.dump(cfg, open(pfad, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, sort_keys=True)


def merge_config(alt, neu):
    """Spielt eine extern angepasste Konfiguration ein und schuetzt die
    Schluessel, die die Pipeline selbst gesetzt hat (V4).

    Gibt (config, uebernommen, abgelehnt) zurueck."""
    cfg = dict(alt)
    uebernommen, abgelehnt = {}, {}
    for k, v in neu.items():
        if k in GESCHUETZT:
            if alt.get(k) != v:
                abgelehnt[k] = (v, "geschuetzt: von der Pipeline gesetzt")
            continue
        if k not in AENDERBAR:
            abgelehnt[k] = (v, "nicht in der Liste aenderbarer Schluessel")
            continue
        if alt.get(k) != v:
            uebernommen[k] = (alt.get(k), v)
            cfg[k] = v
    return cfg, uebernommen, abgelehnt


def config_hash(cfg):
    """Fingerabdruck aller Schluessel, die das Ergebnis beeinflussen (F7)."""
    relevant = {k: cfg[k] for k in sorted(cfg) if k in AENDERBAR
                or k in ("quotes", "eszett", "diminutive", "tempus")}
    roh = json.dumps(relevant, sort_keys=True, ensure_ascii=False)
    for name in (ANWEISUNGEN,):
        if os.path.exists(name):
            roh += open(name, encoding="utf-8").read()
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


def lade_json(pfad, still=False):
    if not os.path.exists(pfad):
        return {}
    try:
        d = json.load(open(pfad, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        if not still:
            print(f"  WARNUNG: {pfad} nicht lesbar, wird ignoriert.")
        return {}


KOMMENTAR = re.compile(r"<!--.*?-->", re.DOTALL)


def lade_anweisungen(abschnitt, pfad=ANWEISUNGEN):
    """Liest einen Abschnitt aus anweisungen.md.

    WICHTIG (F2): HTML-Kommentare werden entfernt. Ohne das landeten die
    Platzhalter-Beispiele der Vorlage woertlich in den System-Prompts."""
    if not os.path.exists(pfad):
        return ""

    def norm(s):
        s = s.lower().strip()
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            s = s.replace(a, b)
        return s

    ziel = norm(abschnitt)
    teile = re.split(r"(?m)^##\s+(.+?)\s*$",
                     open(pfad, encoding="utf-8").read())
    for i in range(1, len(teile) - 1, 2):
        if norm(teile[i]) == ziel:
            inhalt = KOMMENTAR.sub("", teile[i + 1])
            inhalt = re.sub(r"(?m)^\s*<!--.*$", "", inhalt)   # unvollstaendige
            return inhalt.strip()
    return ""


def kopf(skript):
    print("=" * 62)
    print(f"  {skript}   [{RICHTUNG}]")
    print("=" * 62)


# ==================================================================
# Zielsprachliche Vorgaben
# ==================================================================
def zielbaustein(cfg):
    if cfg["quotes"] == "guillemets":
        anf = ("deutsche Guillemets nach innen: »Rede«, verschachtelt ›so‹. "
               "Keine englischen oder niederlaendischen Anfuehrungszeichen")
    else:
        anf = "deutsche Anfuehrungszeichen: „Rede“, verschachtelt ‚so‘"
    strich = ("Halbgeviertstrich mit Spatien ( – ) als Gedankenstrich, niemals "
              "Geviertstrich oder doppelter Bindestrich")
    sz = ("ß nach langem Vokal und Diphthong (Straße, groß, heiß, außen), ss "
          "nach kurzem Vokal (Fluss, muss, dass)"
          if cfg["eszett"] else
          "durchgehend ss statt ß (schweizerische Schreibung)")
    return ("- Zielsprache: deutsches Standarddeutsch (bundesdeutsche "
            "Varietät). Keine österreichischen oder schweizerischen "
            f"Varianten.\n- Verwende {anf}.\n- Verwende {strich}.\n"
            f"- Schreibung: {sz}.\n- Geltende amtliche Rechtschreibung.")


DIMINUTIV_ANW = {
    "aufloesen": (
        "Niederländische Diminutive auf -je/-tje/-pje/-kje sind meist nicht "
        "verkleinernd, sondern affektiv oder lexikalisiert (een biertje, een "
        "uurtje, een kopje koffie). Löse sie im Deutschen auf: Grundwort, "
        "Mengenangabe oder Umschreibung. Setze -chen oder -lein NUR, wo aus "
        "dem Kontext echte Verkleinerung, Zärtlichkeit oder Herablassung "
        "hervorgeht. Mechanisch übertragene Diminutive machen deutschen Text "
        "unerträglich verniedlicht."),
    "erhalten": (
        "Übertrage niederländische Diminutive, wo das Deutsche eine "
        "natürliche Entsprechung hat."),
}

TEMPUS_ANW = {
    "quellnah": (
        "Das Niederländische wechselt in der Erzählung freier zwischen "
        "Präteritum und Perfekt als das Deutsche. Folge diesem Wechsel, wo er "
        "im Deutschen grammatisch einwandfrei ist und die Erzählstimme trägt. "
        "Glätte ihn NICHT zu durchgehendem Präteritum. Achte aber darauf, "
        "dass jede Form für sich korrekt ist: richtiges Hilfsverb "
        "(haben/sein), richtige Zeitenfolge im Nebensatz, kein Perfekt dort, "
        "wo das Deutsche zwingend Präteritum verlangt."),
    "praeteritum": (
        "Erzähle durchgehend im Präteritum, wie in deutscher literarischer "
        "Prosa üblich. Perfekt nur, wo es semantisch nötig ist."),
}


def projektbausteine(cfg):
    return (DIMINUTIV_ANW.get(cfg["diminutive"], DIMINUTIV_ANW["aufloesen"]),
            TEMPUS_ANW.get(cfg["tempus"], TEMPUS_ANW["quellnah"]))


# ==================================================================
# Backend-Adapter (V11a) — schlank, ohne Fremdabhaengigkeit
# ==================================================================
class Backend:
    """Basisklasse. Ein weiterer Anbieter heisst: eine Unterklasse."""

    def chat(self, cfg, system, user, temperature, num_ctx=None):
        raise NotImplementedError

    def verfuegbare_modelle(self, cfg):
        return []


class OllamaBackend(Backend):
    _think = True

    def chat(self, cfg, system, user, temperature, num_ctx=None):
        host = cfg["ollama_host"]
        timeout = (cfg["timeout_connect"], cfg["timeout_read"])

        def post(mit_think):
            p = {
                "model": cfg["modell"],
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                "stream": False, "keep_alive": "60m",
                "options": {"num_ctx": num_ctx or cfg["num_ctx"],
                            "num_predict": -1, "temperature": temperature,
                            "top_p": 1.0, "repeat_penalty": 1.0,
                            "presence_penalty": 0.0},
            }
            if mit_think:
                p["think"] = False
            return requests.post(f"{host}/api/chat", json=p, timeout=timeout)

        r = post(self._think)
        if r.status_code == 400 and self._think:
            OllamaBackend._think = False
            r = post(False)
        r.raise_for_status()
        d = r.json()
        if d.get("done_reason") == "length":
            print("    WARNUNG: Ausgabe am Limit abgeschnitten.")
        return saeubern(d.get("message", {}).get("content", ""))

    def verfuegbare_modelle(self, cfg):
        r = requests.get(f"{cfg['ollama_host']}/api/tags", timeout=10)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]


BACKENDS = {"ollama": OllamaBackend()}


def backend(cfg):
    b = BACKENDS.get(cfg.get("backend", "ollama"))
    if b is None:
        sys.exit(f"FEHLER: unbekanntes Backend '{cfg.get('backend')}'. "
                 f"Verfuegbar: {', '.join(BACKENDS)}")
    return b


def chat(cfg, system, user, temperature, num_ctx=None):
    return backend(cfg).chat(cfg, system, user, temperature, num_ctx)


def modelle_vorhanden(cfg):
    return backend(cfg).verfuegbare_modelle(cfg)


PREAMBEL = re.compile(
    r"^\s*(hier (ist|folgt|die|der)[^\n:]{0,70}:|"
    r"(die )?(deutsche )?(übersetzung|fassung|version)[^\n:]{0,40}:|"
    r"(der )?(korrigierte|lektorierte|überarbeitete) text[^\n:]{0,40}:|"
    r"here (is|'s)[^\n:]{0,70}:)\s*", re.IGNORECASE)


def saeubern(text):
    t = (text or "").strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"^```[a-z]*\s*", "", t.strip())
    t = re.sub(r"\s*```$", "", t)
    return PREAMBEL.sub("", t.strip()).strip()


def json_aus_antwort(raw):
    raw = re.sub(r"^```[a-z]*\s*|\s*```$", "", (raw or "").strip())
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"[\{\[].*[\}\]]", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


# ==================================================================
# Niederlaendische Satz- und Absatztrennung
# ==================================================================
ABK_NL = [
    "afb", "bijv", "blz", "bv", "ca", "cf", "dhr", "d.w.z", "e.a", "e.d",
    "enz", "etc", "evt", "excl", "fa", "ir", "incl", "jl", "kg", "km",
    "m.a.w", "m.b.t", "mevr", "mej", "mr", "mw", "n.a.v", "nl", "nr",
    "o.a", "o.m", "pag", "resp", "St", "t.a.v", "t.b.v", "t.o.v",
    "tel", "v.Chr", "n.Chr", "vgl", "zgn", "ds", "drs", "prof", "dr",
    "jan", "feb", "mrt", "apr", "jun", "jul", "aug", "sep", "okt", "nov", "dec",
]

SCHLIESSER = r'["\u201c\u201d\u2018\u2019\u00ab\u00bb\')\]]*'
GRENZE_NL = (r'(?<=[.!?])' + SCHLIESSER + r'\s+'
             r'(?=[\u201c\u201e\u00ab"\u2018\'(\[\u2014\u2013]?'
             r'[A-Z\u00c4\u00d6\u00dc\u00c9\u00c8])')
GRENZE_DE = (r'(?<=[.!?\u2026])' + SCHLIESSER + r'\s+'
             r'(?=[\u00bb\u201e"\u203a\'(\[\u2013]?[A-Z\u00c4\u00d6\u00dc])')


def saetze_nl(text):
    p = text
    for a in ABK_NL:
        p = re.sub(rf"\b{re.escape(a)}\.",
                   a.replace(".", "<PD>") + "<PD>", p)
    p = re.sub(r"\b([A-Z])\.", r"\1<PD>", p)
    p = re.sub(r"(\d)\.", r"\1<PD>", p)
    p = p.replace("...", "<EL>").replace("\u2026", "<EL>")
    out = []
    for s in re.split(GRENZE_NL, p):
        s = s.replace("<PD>", ".").replace("<EL>", "...").strip()
        if s:
            out.append(s)
    return out


def saetze_de(text):
    return [s.strip() for s in re.split(GRENZE_DE, text) if s.strip()]


def absaetze(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def chunks_bauen(paras, ziel, ausnahmen=None):
    """Absatzgrenzen haben Vorrang. Absaetze in 'ausnahmen' (etwa Zitate)
    bilden jeweils einen eigenen Chunk und bleiben unangetastet.

    Gibt eine Liste von (text, geschuetzt) zurueck."""
    ausnahmen = ausnahmen or set()
    einheiten = []
    for p in paras:
        if p in ausnahmen:
            einheiten.append((p, True, True))
            continue
        if len(p.split()) <= ziel * 1.8:
            einheiten.append((p, True, False))
            continue
        buf, n, erster = [], 0, True
        for s in saetze_nl(p):
            buf.append(s)
            n += len(s.split())
            if n >= ziel:
                einheiten.append((" ".join(buf), erster, False))
                buf, n, erster = [], 0, False
        if buf:
            einheiten.append((" ".join(buf), erster, False))

    chunks, buf, n = [], [], 0
    for txt, start, geschuetzt in einheiten:
        if geschuetzt:
            if buf:
                chunks.append(("\n\n".join(buf), False))
                buf, n = [], 0
            chunks.append((txt, True))
            continue
        w = len(txt.split())
        if buf and n + w > ziel:
            chunks.append(("\n\n".join(buf), False))
            buf, n = [], 0
        if buf and not start:
            buf[-1] += " " + txt
        else:
            buf.append(txt)
        n += w
    if buf:
        chunks.append(("\n\n".join(buf), False))
    return chunks


def schlusswoerter(text, n):
    w = text.split()
    if len(w) <= n:
        return text.strip()
    s = " ".join(w[-n:])
    m = re.search(r'(?<=[.!?\u2026])' + SCHLIESSER + r'\s+', s)
    return (s[m.end():] if m else s).strip()


def verhaeltnis(a, b):
    wa = len(a.split())
    return (len(b.split()) / wa) if wa else 0.0


# ==================================================================
# Metriken (F1, V16, V15)
# ==================================================================
# Grossgeschriebene Woerter auf -chen/-lein, die KEINE Diminutive sind.
NICHT_DIMINUTIV = {
    "Zeichen", "Küchen", "Kirchen", "Flächen", "Sachen", "Sprachen", "Wochen",
    "Knochen", "Drachen", "Rachen", "Kuchen", "Buchen", "Suchen", "Brachen",
    "Lachen", "Machen", "Rechen", "Blechen", "Brechen", "Zechen", "Seuchen",
    "Bauchen", "Sträuchen", "Tuchen", "Bräuchen", "Gerüchen", "Geräuchen",
    "Versprechen", "Verbrechen", "Gespräche", "Wachen", "Sichen", "Riechen",
    "Kriechen", "Streichen", "Gleichen", "Reichen", "Weichen", "Speichen",
    "Leichen", "Deichen", "Teichen", "Eichen", "Bächen", "Dächern",
    "Allein", "Verzeichnen",
}
# Diminutive sind Substantive, also gross. Kleingeschriebene Treffer
# (sprechen, zwischen, riechen) fallen damit von selbst heraus.
DIMINUTIV_MUSTER = re.compile(
    r"\b([A-ZÄÖÜ][a-zäöüß]{2,}(?:chen|lein))\b")

PARTIZIP = re.compile(
    r"\b(?:ge[a-zäöüß]{2,}(?:t|en)|"
    r"(?:be|ent|er|ver|zer|miss|über|unter|um|wider)[a-zäöüß]{3,}(?:t|en))\b")
AUXILIAR = re.compile(
    r"\b(hat|hatte|hatten|habe|haben|hast|habt|"
    r"ist|war|waren|bin|bist|sind|seid|wart)\b")


def diminutive_zaehlen(text):
    """F1: korrigierte Zaehlung. Gibt (anzahl, treffer) zurueck."""
    treffer = [w for w in DIMINUTIV_MUSTER.findall(text)
               if w not in NICHT_DIMINUTIV]
    return len(treffer), treffer


def perfekt_quote(text):
    """V16: Anteil der Saetze mit Perfektkonstruktion.

    Satzweise Ko-Okkurrenz von finitem Hilfsverb und Partizip — damit wird
    auch die deutsche Verbklammer erfasst ('dass er es gesagt hat')."""
    saetze = saetze_de(text)
    if not saetze:
        return 0.0, 0, 0
    mit = sum(1 for s in saetze if AUXILIAR.search(s) and PARTIZIP.search(s))
    return mit / len(saetze), mit, len(saetze)


def leitmotiv_varianten(text, wortlaut, min_wortlaenge=4):
    """V15: findet Saetze, die alle Inhaltswoerter der Wendung enthalten,
    aber nicht den vorgeschriebenen Wortlaut."""
    inhalt = [w.lower() for w in re.findall(r"\w{%d,}" % min_wortlaenge, wortlaut)]
    if not inhalt:
        return []
    raus = []
    for s in saetze_de(text):
        low = s.lower()
        if wortlaut.lower() in low:
            continue
        if all(w in low for w in inhalt):
            raus.append(s.strip()[:200])
    return raus


# ==================================================================
class Bericht:
    def __init__(self, titel):
        self.titel = f"{titel}   [{RICHTUNG}]"
        self.zeilen, self.fehler, self.warnungen = [], 0, 0

    def add(self, status, thema, text=""):
        sym = {"OK": "[ok]   ", "WARN": "[warn] ",
               "FEHLER": "[FEHL] ", "INFO": "[info] "}.get(status, "       ")
        self.zeilen.append(f"{sym}{thema}"
                           + (f"\n           {text}" if text else ""))
        if status == "FEHLER":
            self.fehler += 1
        elif status == "WARN":
            self.warnungen += 1

    def abschnitt(self, name):
        self.zeilen.append(f"\n--- {name} " + "-" * max(4, 58 - len(name)))

    def text(self):
        k = [self.titel, "=" * len(self.titel), time.strftime("%Y-%m-%d %H:%M"), ""]
        f = ["", "=" * 60,
             f"Ergebnis: {self.fehler} Fehler, {self.warnungen} Warnungen",
             "BESTANDEN" if self.fehler == 0 else "NICHT BESTANDEN"]
        return "\n".join(k + self.zeilen + f)

    def schreiben(self, pfad):
        open(pfad, "w", encoding="utf-8").write(self.text() + "\n")
        print(self.text())
        print(f"\nBericht: {pfad}")
        return self.fehler == 0


def fortschritt(i, n, start, extra=""):
    pro = (time.time() - start) / max(1, i)
    return f"[{i}/{n}] {extra}  (Rest ca. {(n-i)*pro/60:.0f} min)"


# ==================================================================
# Chunk-Dateien
# ==================================================================
def teil_pfad(art, i, praefix=""):
    d = os.path.join(praefix, TEILE[art]) if praefix else TEILE[art]
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{i:04d}.txt")


def teil_schreiben(art, i, text, praefix=""):
    p = teil_pfad(art, i, praefix)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def teil_lesen(art, i, praefix=""):
    p = teil_pfad(art, i, praefix)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


def teile_vorhanden(art, n, praefix=""):
    """Index des ersten fehlenden Teils — das ist der Resume-Punkt."""
    for i in range(n):
        if teil_lesen(art, i, praefix) is None:
            return i
    return n


def teile_zusammensetzen(art, n, praefix=""):
    stuecke = []
    for i in range(n):
        t = teil_lesen(art, i, praefix)
        if t is None:
            return None
        stuecke.append(t.strip())
    return "\n\n".join(stuecke)
