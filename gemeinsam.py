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
import random
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
    "stilprofil":    "stilprofil.json",
    "kapitel":       "kapitel.json",
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
# 'annotation' war bis August 2026 EINE Rolle fuer zwei sehr verschiedene
# Arbeiten: eine Begruendungszeile je Aenderung (Massenware, zwanzig Stueck
# je Aufruf) und das Screening des ganzen Buches gegen das Original (die
# eigentliche Qualitaetspruefung). Ein Modell fuer beides heisst: entweder
# zahlt man den Preis der Pruefung fuer die Massenware, oder man prueft mit
# dem Modell der Massenware.
ROLLEN = ("uebersetzung", "revision", "stil", "korrektorat", "zitat",
          "vorbereitung", "judge", "begruendung", "screening", "vergleich")


STANDARD = {
    "sprachpaar":                "nl-de",
    "varietaet":                 "bundesdeutsch",
    "quotes":                    "guillemets",
    "dash":                      "halbgeviert",
    "eszett":                    True,

    # Die Modellbelegung je Rolle steht in projekt.json. Es gibt keinen
    # Rueckfall mehr: Eine Rolle ohne Modell ist ein Konfigurationsfehler
    # und wird gemeldet, nicht stillschweigend ersetzt.
    "backend_standard":          "anthropic",
    "modell_uebersetzung":       "",
    "modell_revision":           "",
    "modell_stil":               "",
    "modell_korrektorat":        "",
    "modell_vorbereitung":       "",
    "modell_zitat":              "",
    "modell_judge":              "",
    "modell_begruendung":        "",
    "modell_screening":          "",
    "modell_vergleich":          "",
    "effort_uebersetzung":       "hoch",
    "effort_revision":           "hoch",
    "effort_stil":               "hoch",
    "effort_korrektorat":        "hoch",
    "effort_vorbereitung":       "hoch",
    "effort_zitat":              "hoch",
    "effort_judge":              "hoch",
    "effort_begruendung":        "niedrig",
    "effort_screening":          "hoch",
    "effort_vergleich":          "hoch",
    "max_tokens_api":            32000,
    "timeout_read_api":          600,       # Auftrag Paket 1: hoechstens 10 min
    # Lebensdauer des Prompt-Caches. '1h' ist eine Versicherung, kein
    # Sparposten: Das Praefix ueberlebt eine Pause zwischen zwei Chunks.
    # Leer laesst die Voreinstellung des Anbieters (fuenf Minuten).
    "cache_ttl":                 "1h",
    # Anbieter-SDK benutzen, wenn sie installiert ist. 'false' erzwingt den
    # requests-Pfad — der bleibt der Rueckfall und muss lauffaehig bleiben.
    "sdk_nutzen":                True,

    "chunk_words":               800,
    "chunk_words_variante":      1200,      # Rueckfall, wenn 'varianten' leer ist

    # Vergleichsvarianten des Testlaufs. Je Eintrag ein Name und, was
    # abweicht: chunk_words und/oder modell_uebersetzung (Paket 5).
    "varianten": [
        {"name": "B", "chunk_words": 1600},
        {"name": "C", "chunk_words": 800,
         "modell_uebersetzung": "claude-fable-5"},
    ],
    "context_words":             250,
    "revision_pass":             True,

    "lektorat_passes":           ["det", "stil", "korrektorat", "det"],

    # Leer = altes Verhalten: die Referenz-JSONs werden direkt gelesen.
    # Gesetzt = das Spreadsheet ist die Quelle, referenz_sync erzeugt die
    # JSONs daraus. Kein Bestandteil des Konfigurationsfingerabdrucks —
    # der Ablageort der Referenzdaten aendert den Text nicht.
    "sheets_id":                 "",

    # Zeile, an der eine Erzaehlebene wechselt. Harte Chunkgrenze plus
    # Rueckschau-Reset (Paket 5). Leer = keine Rahmenwechsel im Text.
    "rahmen_marker":             "#",

    # Technische Schluessel, die dieses Buch fuer sich beansprucht. Der
    # Abgleich 'pipeline.py technik' laesst sie in Ruhe — sonst setzt er
    # eine bewusste Modellwahl je Projekt still zurueck.
    "technik_ausnahmen":         [],

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
    "max_retries":               3,
}

# Diese Schluessel werden von der Pipeline selbst gesetzt und duerfen von
# einer eingespielten projekt.json NICHT ueberschrieben werden (V4).
GESCHUETZT = {"ratio_min", "ratio_max", "ratio_kalibriert", "sprachpaar"}

# Nur diese Schluessel darf ein externes Rueckspiel aendern (V4).
AENDERBAR = {
    "chunk_words", "chunk_words_variante", "context_words",
    "revision_pass", "lektorat_passes",
    "diminutive", "tempus", "anrede_vorgabe",
    "quotes", "eszett", "varietaet", "dash",
    "test_words_erzaehlung", "test_words_dialog",
    "lektorat_ratio_min", "lektorat_ratio_max",
    "export_glossar", "export_bewertung", "glossar_quelle", "sheets_id",
    "rahmen_marker", "varianten", "technik_ausnahmen",
    "timeout_connect", "max_retries",
    "backend_standard", "max_tokens_api", "timeout_read_api", "cache_ttl",
    "sdk_nutzen",
} | {f"modell_{r}" for r in ROLLEN} | {f"effort_{r}" for r in ROLLEN}


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
        if k.startswith("_"):
            continue                    # Hinweiszeilen, keine Einstellung
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
# Laufumgebung und Schluessel
# ==================================================================
def ist_colab():
    """Einzige Colab-Erkennung des Projekts. Bitte nirgendwo sonst."""
    try:
        import google.colab            # noqa: F401
        return True
    except Exception:
        return False


# Anzeigename -> (Umgebungsvariable, Colab-Secret)
SCHLUESSEL = {
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    "google":    ("GEMINI_API_KEY",    "GoogleKI"),
}


def api_schluessel(anbieter, still=True):
    """Liest den Schluessel aus der Umgebung, in Colab aus userdata.

    Gibt None zurueck, wenn keiner da ist. Der Wert wird nirgends geloggt
    oder in eine Datei geschrieben."""
    var, secret = SCHLUESSEL.get(anbieter, (None, None))
    if not var:
        return None
    wert = os.environ.get(var)
    if wert:
        return wert.strip()
    if ist_colab():
        try:
            from google.colab import userdata
            wert = userdata.get(secret)
            if wert:
                os.environ[var] = wert.strip()      # fuer Unterprozesse
                return wert.strip()
        except Exception as e:
            if not still:
                print(f"  Colab-Secret '{secret}' nicht lesbar: {e}")
    return None


# ==================================================================
# Rollen, Modelle, Backends
# ==================================================================
# Das Backend ergibt sich aus dem Modellnamen, nicht aus der Konfiguration.
# 'backend_standard' ist nur der Default fuer Rollen ohne eigenes Modell.
PRAEFIXE = (("claude-", "anthropic"), ("gemini-", "google"))

# projekt.json haelt die Stufen deutsch, die APIs erwarten englisch.
EFFORT = {"niedrig": "low", "mittel": "medium", "hoch": "high",
          "sehr_hoch": "xhigh", "maximal": "max"}

# Nur Anthropic-Modelle kennen 'effort'. Gemini bekommt den Schluessel gar
# nicht erst geschickt — 'effort_screening' zu aendern hat dort keine
# Wirkung, und das gehoert dazugesagt, statt dass jemand daran dreht.
EFFORT_WIRKT = ("anthropic",)


# ==================================================================
# Empfehlung je Rolle — die eine Stelle, an der Modell und Tiefe
# begruendet stehen. Geaendert wird in projekt.json; 'pipeline.py modelle'
# stellt Ist und Empfehlung nebeneinander.
#
# Die Begruendung steht bewusst hier und nicht in einer Doku: Wer die
# Belegung aendert, liest sie genau in dem Moment, in dem es darauf
# ankommt. Empfehlung heisst Empfehlung — abweichen ist vorgesehen,
# 'technik_ausnahmen' haelt die Abweichung fest.
# ==================================================================
EMPFEHLUNG = {
    "uebersetzung": (
        "claude-opus-5", "hoch",
        "Der Text selbst. Hier wird nicht gespart — jeder Fehler dieses "
        "Passes wandert durch alle folgenden."),
    "revision": (
        "claude-opus-5", "hoch",
        "Sieht Quelle und Entwurf nebeneinander und aendert in 99 % der "
        "Chunks substanziell. Ein schwaecheres Modell hier hiesse: mit "
        "dem schwaecheren Urteil ueber das staerkere entscheiden."),
    "stil": (
        "claude-opus-5", "hoch",
        "Wort und Wendung, 86 % der Lektoratsaenderungen. Das ist "
        "Sprachgefuehl, nicht Regelanwendung."),
    "korrektorat": (
        "claude-sonnet-5", "mittel",
        "Regelanwendung: Rechtschreibung, Zeichensetzung, Kongruenz. "
        "Dafuer braucht es kein Spitzenmodell, und der Pass laeuft ueber "
        "das ganze Buch. Wird der Diff duenn oder greift er daneben, "
        "zurueck auf claude-opus-5 — die Messung steht aus."),
    "vorbereitung": (
        "claude-fable-5", "sehr_hoch",
        "Einmalig, wenige Aufrufe, und alles Spaetere haengt daran: "
        "Glossar, Figurenblatt, Anrede, Leitmotive, Stilprofil. Ein "
        "Fehler hier steht in jedem Chunk des Buches. Der Aufpreis faellt "
        "bei neun Aufrufen nicht ins Gewicht."),
    "zitat": (
        "claude-opus-5", "hoch",
        "Recherche mit Websuche. Ein erfundener Wortlaut waere schlimmer "
        "als eine markierte Luecke — das Modell muss wissen, wann es "
        "nichts weiss."),
    "judge": (
        "gemini-3.1-pro-preview", "hoch",
        "Fremdurteil. Bewusst nicht von Anthropic: Ein Modell, das seine "
        "eigene Ausgabe bewertet, bevorzugt sie."),
    "begruendung": (
        "gemini-3.6-flash", "niedrig",
        "Massenware: eine Zeile je Aenderung, zwanzig Stueck je Aufruf, "
        "rein berichtend. Der Leser ueberfliegt sie."),
    "screening": (
        "gemini-3.1-pro-preview", "hoch",
        "Liest das ganze Buch gegen das Original und sucht, was vier "
        "Anthropic-Durchgaenge uebersehen haben. Als Fremdurteil nur "
        "brauchbar, wenn es von einem anderen Anbieter kommt — und nur "
        "mit einem Modell, das genau hinsieht."),
    "vergleich": (
        "claude-fable-5", "hoch",
        "Einmaliger Vergleichslauf. Wird von keinem Schritt gerufen; der "
        "Ping vor dem Lauf prueft den Namen trotzdem mit."),
}


def empfehlung(rolle):
    """(Modell, Effort, Begruendung) — oder Leeres fuer unbekannte Rollen."""
    return EMPFEHLUNG.get(rolle, ("", "", ""))


# Schluessel, die technische Entscheidungen tragen und deshalb mit dem
# Code wandern muessen, nicht mit dem Projekt. Modellnamen aendern sich,
# wenn ein Anbieter umbenennt — die kalibrierten Pruefgrenzen eines
# laufenden Buchs duerfen davon nicht beruehrt werden.
#
# Der Ueberschreibschutz der projekt.json bleibt: erkannt wird die
# Abweichung, uebernommen wird sie nur auf ausdrueckliche Ansage.
TECHNIK = ({"backend_standard", "max_tokens_api", "timeout_read_api",
            "cache_ttl", "sdk_nutzen"}
           | {f"modell_{r}" for r in ROLLEN}
           | {f"effort_{r}" for r in ROLLEN})


def technik_abweichung(projekt_cfg, repo_cfg):
    """(Schluessel, Projektwert, Repowert) fuer jede technische Abweichung.

    Schluessel in 'technik_ausnahmen' bleiben aussen vor: Sie gehoeren
    diesem Buch, nicht dem Code. Ohne diese Liste haette der Abgleich
    eine bewusste Modellwahl je Projekt stillschweigend zurueckgesetzt —
    und das faellt erst am Kostenbericht auf."""
    ausnahmen = set(projekt_cfg.get("technik_ausnahmen") or [])
    raus = []
    for k in sorted(TECHNIK):
        if k not in repo_cfg or k in ausnahmen:
            continue
        alt, neu = projekt_cfg.get(k), repo_cfg[k]
        if alt != neu:
            raus.append((k, alt, neu))
    return raus


def technik_beansprucht(projekt_cfg, repo_cfg):
    """Was das Projekt fuer sich beansprucht und was im Repo stuende."""
    ausnahmen = set(projekt_cfg.get("technik_ausnahmen") or [])
    return [(k, projekt_cfg.get(k), repo_cfg.get(k))
            for k in sorted(ausnahmen & TECHNIK)
            if projekt_cfg.get(k) != repo_cfg.get(k)]


def _json_lesen(pfad):
    try:
        return json.load(open(pfad, encoding="utf-8"))
    except Exception:
        return {}


def technik_vergleich(projekt_pfad, repo_pfad):
    return technik_abweichung(_json_lesen(projekt_pfad),
                              _json_lesen(repo_pfad))


def technik_schreiben(projekt_pfad, repo_pfad):
    """Uebertraegt NUR die technischen Schluessel. Gibt die Aenderungen zurueck.

    Kalibrierte Pruefgrenzen, Chunkgroesse und alles andere Projekteigene
    bleiben unberuehrt — deshalb wird hier gezielt gesetzt statt kopiert."""
    cfg = _json_lesen(projekt_pfad)
    ab = technik_abweichung(cfg, _json_lesen(repo_pfad))
    if not ab:
        return []
    for k, _alt, neu in ab:
        cfg[k] = neu
    tmp = projekt_pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, projekt_pfad)
    return ab


def modell_fuer(cfg, rolle):
    """Modellname der Rolle.

    Ohne Eintrag ist Schluss: Seit dem Wegfall des Ollama-Pfads gibt es
    kein Modell mehr, auf das sich zurueckfallen liesse. Ein stiller
    Ersatz waere die teuerste Art, das zu bemerken — naemlich am
    Kostenbericht."""
    modell = (cfg.get(f"modell_{rolle}") or "").strip()
    if not modell:
        sys.exit(f"FEHLER: 'modell_{rolle}' ist nicht gesetzt.\n"
                 f"  Belegung ansehen und ergaenzen: "
                 f"python3 pipeline.py modelle")
    return modell


def backend_name(modell):
    for praefix, name in PRAEFIXE:
        if modell.startswith(praefix):
            return name
    sys.exit(f"FEHLER: zu '{modell}' gehoert kein bekannter Anbieter.\n"
             f"  Erkannt werden Praefixe: "
             f"{', '.join(p for p, _ in PRAEFIXE)}")


def effort_fuer(cfg, rolle):
    stufe = (cfg.get(f"effort_{rolle}") or "hoch").strip().lower()
    if stufe not in EFFORT:
        sys.exit(f"FEHLER: effort_{rolle} ist '{stufe}'. Erlaubt: "
                 f"{', '.join(EFFORT)}.")
    return EFFORT[stufe]


# ==================================================================
# Tarife und Kosten
# ==================================================================
# Dollar je 1 Mio Token, Stand 31.07.2026.
#
# Alle vier Werte sind gegen die Anbieterdokumentation geprueft: die
# Anthropic-Tarife beim Bau des Adapters, die Google-Tarife am 31.07.2026
# im Colab-Lauf von 'verifikation.py' gegen die Preisseite (aus der
# Entwicklungsumgebung ist ai.google.dev durch die Netzwerkpolicy
# gesperrt). Beim Wechsel auf ein Modell ohne Tarif wird geschaetzt, nicht
# geraten — die Kostenuebersicht weist das aus.
#
# Achtung Namen: die Preisseite fuehrt das Judge-Modell als
# 'gemini-3.1-pro', die API kennt es nur als 'gemini-3.1-pro-preview'
# (v1beta). Beide Schluessel stehen deshalb hier — der erste, weil die
# Preisseite ihn nennt, der zweite, weil die Rolle ihn benutzt.
TARIFE = {
    "claude-opus-5":            {"ein":  5.00, "aus": 25.00,
                                 "geprueft": True},
    "claude-fable-5":           {"ein": 10.00, "aus": 50.00,
                                 "geprueft": True},
    "gemini-3.1-pro":           {"ein":  2.00, "aus": 12.00,
                                 "geprueft": True,
                                 "hinweis": "Tarif bis 200k-Prompt"},
    "gemini-3.1-pro-preview":   {"ein":  2.00, "aus": 12.00,
                                 "geprueft": True,
                                 "hinweis": "Preisseite nennt das Modell "
                                            "ohne '-preview'"},
    "gemini-3.6-flash":         {"ein":  1.50, "aus":  7.50,
                                 "geprueft": True},
}

# Wortzahl -> Token. Bewusst konservativ (hoch) angesetzt: der Tokenizer der
# Opus-5-Aera zaehlt gegenueber aelteren bis etwa das 1,35-fache, und eine zu
# niedrige Schaetzung vor einem fuenfstuendigen Lauf ist der teurere Fehler.
# Nach dem ersten Echtlauf kalibriert 'token_faktor' gegen die gemessene
# Usage in manifest.json.
TOKEN_JE_WORT = 2.4


def tarif(modell, datei="tarife.json"):
    """Preis je Mio Token. tarife.json hat Vorrang vor der Konstante.

    Die Konstante bleibt die dokumentierte Grundlage; die Datei traegt,
    was tarife.py an den Preisseiten geholt und als eindeutig befunden
    hat — mit Quelle und Datum."""
    if os.path.exists(datei):
        try:
            e = json.load(open(datei, encoding="utf-8")).get(modell)
            if isinstance(e, dict) and "ein" in e and "aus" in e:
                return {"ein": float(e["ein"]), "aus": float(e["aus"]),
                        "geprueft": True, "hinweis": e.get("quelle", "")}
        except Exception:
            pass
    return TARIFE.get(modell)


def token_faktor(manifest=None):
    """Konservativer Schaetzwert, sofern keine Messung vorliegt.

    Sobald 'kosten' in manifest.json echte Token neben echten Woertern
    stehen hat, gilt das gemessene Verhaeltnis."""
    try:
        woerter = (manifest or {}).get("kosten", {}).get("_woerter_quelle", 0)
        # Nur die Buchproduktion: Testlaeufe rechnen auf einem Auszug und
        # wuerden das Verhaeltnis Token je Quellwort verzerren.
        ein = sum(e.get("ein", 0) for lauf, _, _, e in kosten_posten(manifest)
                  if lauf in ("voll", ""))
        if woerter > 500 and ein > 0:
            return round(ein / woerter, 2)
    except Exception:
        pass
    return TOKEN_JE_WORT


# Alle gebuchten Tokenarten an einer Stelle. Wer eine ergaenzt, ergaenzt sie
# damit zugleich in Buchung, Differenz und Rollenstand.
USAGE_FELDER = ("ein", "aus", "cache_lesen", "cache_schreiben",
                "cache_schreiben_1h")


# Laufkontext der Buchung. Ein Testlauf mit einem anderen Modell darf die
# Buchung der Buchproduktion nicht ueberschreiben — genau das ist beim Lauf
# 1919 passiert und hat die Kosten um 57 % zu hoch ausgewiesen.
_LAUF = "voll"


def lauf_setzen(praefix):
    """Bucht folgende Aufrufe unter diesem Lauf.

    Aufrufer geben den Ausgabepraefix weiter ('test/', 'testB/', ''), so
    steht die Zuordnung an derselben Stelle wie die Dateiablage."""
    global _LAUF
    _LAUF = (praefix or "").strip("/") or "voll"


def lauf_name():
    return _LAUF


def kosten_schluessel(lauf, rolle, modell):
    """Buchungsschluessel. Drei Teile, damit der Leser sie ohne Doku trennt."""
    return f"{lauf}/{rolle}/{modell}"


def usage_buchen(rolle, modell, usage):
    """Summiert Token je (Lauf, Rolle, Modell) in manifest.json.

    Nicht je Rolle allein: Wer eine Rolle einmal mit einem anderen Modell
    probiert, haette sonst die gesamte Rolle auf dieses Modell umetikettiert
    — Token und Preis waeren danach unvereinbar.

    Schlaegt das Buchen fehl, kostet das nur die Statistik — nie den Lauf."""
    try:
        m = {}
        if os.path.exists(MANIFEST):
            m = json.load(open(MANIFEST, encoding="utf-8"))
        k = m.setdefault("kosten", {})
        e = k.setdefault(kosten_schluessel(_LAUF, rolle, modell),
                         dict({"lauf": _LAUF, "rolle": rolle,
                               "modell": modell, "aufrufe": 0},
                              **dict.fromkeys(USAGE_FELDER, 0)))
        e["aufrufe"] += 1
        for feld in USAGE_FELDER:
            e[feld] = int(e.get(feld, 0)) + int(usage.get(feld, 0) or 0)
        tmp = MANIFEST + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        os.replace(tmp, MANIFEST)
    except Exception:
        pass


def kosten_schnappschuss():
    """Stand der Token-Buchung, fuer Differenzen je Variante."""
    if not os.path.exists(MANIFEST):
        return {}
    try:
        return json.load(open(MANIFEST, encoding="utf-8")).get("kosten", {})
    except Exception:
        return {}


def kosten_differenz_schreiben(vorher, pfad):
    """Was dieser Lauf gekostet hat, als eigene Datei neben dem Ergebnis.

    Das Manifest bucht fortlaufend, nicht je Variante. Die Differenz
    vor/nach dem Lauf ist die einzige ehrliche Zuordnung — ohne sie
    liesse sich 'Kosten je Variante' nur schaetzen."""
    try:
        nachher = kosten_schnappschuss()
        d = {}
        for schluessel, e in nachher.items():
            if not isinstance(e, dict) or schluessel.startswith("_"):
                continue
            alt = vorher.get(schluessel, {})
            diff = {f: int(e.get(f, 0)) - int(alt.get(f, 0))
                    for f in ("aufrufe",) + USAGE_FELDER}
            if diff["aufrufe"] > 0:
                for f in ("lauf", "rolle", "modell"):
                    diff[f] = e.get(f, "")
                d[schluessel] = diff
        with open(pfad, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# Cache-Lesen kostet ein Zehntel des Eingabepreises, Cache-Schreiben mehr als
# das Schreiben ohne Cache. Der Faktor haengt an der Lebensdauer des Eintrags:
# 1,25 bei fuenf Minuten, 2,0 bei einer Stunde.
CACHE_LESE_FAKTOR = 0.1
CACHE_SCHREIB_FAKTOR = 1.25
CACHE_SCHREIB_FAKTOR_1H = 2.0

def kosten_dollar(e, t):
    """Preis einer Buchung. Eine Formel fuer alle Auswertungen.

    Zwei Formeln waren zwei Wahrheiten: die Variantenkosten in
    bewertung.py liessen den Cache weg und lagen dadurch zu niedrig."""
    if not t:
        return None
    # 'cache_schreiben' ist die Gesamtzahl; der Anteil mit einer Stunde
    # Lebensdauer steht daneben und kostet mehr.
    lang = int(e.get("cache_schreiben_1h", 0))
    kurz = max(0, int(e.get("cache_schreiben", 0)) - lang)
    return (int(e.get("ein", 0)) * t["ein"]
            + int(e.get("cache_lesen", 0)) * t["ein"] * CACHE_LESE_FAKTOR
            + kurz * t["ein"] * CACHE_SCHREIB_FAKTOR
            + lang * t["ein"] * CACHE_SCHREIB_FAKTOR_1H
            + int(e.get("aus", 0)) * t["aus"]) / 1e6


def kosten_posten(manifest):
    """Buchungen als (lauf, rolle, modell, werte), Buchproduktion zuerst.

    Liest auch das alte Format, in dem der Schluessel nur die Rolle war —
    dort ist der Lauf unbekannt und bleibt leer, statt 'voll' zu behaupten."""
    raus = []
    for schluessel, e in (manifest or {}).get("kosten", {}).items():
        if not isinstance(e, dict) or schluessel.startswith("_"):
            continue
        teile = schluessel.split("/")
        alt = len(teile) != 3
        raus.append((e.get("lauf", "") if alt else teile[0],
                     e.get("rolle") or (schluessel if alt else teile[1]),
                     e.get("modell", "") if alt else teile[2],
                     e))
    raus.sort(key=lambda x: (x[0] not in ("voll", ""), x[0], x[1], x[2]))
    return raus


def kosten_stand_rolle(rolle):
    """Bisher gebuchte Token einer Rolle, ueber alle Modelle und Laeufe.

    Fuer Aufrufer, die nur die Differenz ihres eigenen Aufrufs brauchen."""
    stand = dict.fromkeys(USAGE_FELDER, 0)
    try:
        m = json.load(open(MANIFEST, encoding="utf-8"))
    except Exception:
        return stand
    for _, r, _, e in kosten_posten(m):
        if r == rolle:
            for f in stand:
                stand[f] += int(e.get(f, 0) or 0)
    return stand


def kosten_je_rolle(manifest):
    """(Zeilen, Summen je Lauf, unsicher) fuer die Kostenuebersicht.

    Zeile: (lauf, rolle, modell, werte, dollar, tarif)."""
    zeilen, summen, unsicher = [], {}, False
    for lauf, rolle, modell, e in kosten_posten(manifest):
        t = tarif(modell)
        d = kosten_dollar(e, t)
        if d is None:
            unsicher = True
        else:
            summen[lauf] = summen.get(lauf, 0.0) + d
            unsicher = unsicher or not t["geprueft"]
        zeilen.append((lauf, rolle, modell, e, d, t))
    return zeilen, summen, unsicher


# ==================================================================
# Backend-Adapter (V11a) — schlank, ohne Fremdabhaengigkeit
# ==================================================================
class Backend:
    """Basisklasse. Ein weiterer Anbieter heisst: eine Unterklasse."""

    def chat(self, cfg, system, user, rolle="uebersetzung", modell="",
             roh=False):
        raise NotImplementedError

    def zaehle_tokens(self, cfg, system, user, modell=""):
        """Exakte Eingabetoken beim Anbieter, oder None.

        Kostenlos bei beiden Anbietern und unabhaengig vom Tokenizer, den
        das Modell gerade benutzt. 'None' heisst: nicht ermittelbar (kein
        Schluessel, kein Netz, Endpunkt geaendert) — dann greift die
        Schaetzung, statt dass ein Bericht ausfaellt."""
        return None

    def verfuegbare_modelle(self, cfg):
        return []


class ApiFehler(RuntimeError):
    """Fehler eines API-Backends, den der Aufrufer als Versuch zaehlen darf."""


def _warte(antwort, versuch):
    """Wartezeit vor dem naechsten Versuch. 'retry-after' hat Vorrang."""
    if antwort is not None:
        kopf = antwort.headers.get("retry-after") if antwort.headers else None
        if kopf:
            try:
                return min(60.0, max(1.0, float(kopf)))
            except ValueError:
                pass
    return min(32.0, 2.0 ** versuch) + random.uniform(0, 0.5)


def sende(post, max_retries, schlafen=time.sleep):
    """Fuehrt 'post' aus und wiederholt bei 429 und 5xx mit Backoff.

    4xx ausser 429 sind Anwendungsfehler und werden sofort gemeldet —
    ein falsches Payload wird durch Wiederholen nicht richtig."""
    letzter = None
    for versuch in range(1, max(1, max_retries) + 1):
        try:
            r = post()
        except requests.RequestException as e:
            letzter = ApiFehler(f"Netzwerkfehler: {e}")
            if versuch >= max_retries:
                break
            schlafen(_warte(None, versuch))
            continue
        if r.status_code == 200:
            return r
        text = (r.text or "")[:300]
        if r.status_code == 429 or r.status_code >= 500:
            letzter = ApiFehler(f"HTTP {r.status_code}: {text}")
            if versuch >= max_retries:
                break
            schlafen(_warte(r, versuch))
            continue
        if r.status_code in (401, 403):
            raise ApiFehler(
                f"HTTP {r.status_code} — Schluessel fehlt, ist abgelaufen "
                f"oder hat keine Berechtigung fuer dieses Modell.\n{text}")
        raise ApiFehler(f"HTTP {r.status_code}: {text}")
    raise letzter or ApiFehler("Anfrage fehlgeschlagen")


# Lebensdauer des Cache-Eintrags. Wird sie vom Anbieter abgelehnt, faellt
# der Lauf hierueber auf die Voreinstellung zurueck, statt abzubrechen.
_TTL_ABGELEHNT = False


def cache_ttl(cfg):
    """Gewuenschte Cache-Lebensdauer, oder '' fuer die Voreinstellung.

    'Versicherung, keine Kostenersparnis': Bei einer Stunde ueberlebt das
    Praefix eine Pause zwischen zwei Chunks — eine getrennte Colab-Sitzung,
    einen Blick in den Bericht, einen langsamen Chunk. Bezahlt wird das mit
    einem hoeheren Schreibpreis; das lohnt erst, wenn ohne TTL geschrieben
    werden muesste."""
    if _TTL_ABGELEHNT:
        return ""
    t = str(cfg.get("cache_ttl", "") or "").strip()
    return t if t in ("5m", "1h") else ""


# Die Anbieter-SDK, wenn sie installiert ist. Sie bringt Streaming ohne
# handgeschriebenen SSE-Parser, exakte Tokenzaehlung und den Stapel-Adapter.
# Fehlt sie, laeuft der requests-Pfad unveraendert weiter — die Pipeline muss
# auf einem nackten VPS mit nur 'requests' lauffaehig bleiben.
_SDK = None          # None: noch nicht versucht. False: nicht vorhanden.
_KLIENTEN = {}


def anthropic_sdk():
    """Das Modul 'anthropic', oder False. Einmal versucht, dann gemerkt."""
    global _SDK
    if _SDK is None:
        try:
            import anthropic
            _SDK = anthropic
        except Exception:
            _SDK = False
    return _SDK


def sdk_antwort(klient, payload):
    """Ein Aufruf ueber die SDK, als dasselbe dict wie der requests-Pfad.

    'model_dump' gibt genau die Struktur zurueck, die auch ueber die Leitung
    kaeme. Damit bleibt 'antwort_lesen' der einzige Ort, der Antworten
    versteht — sonst driften die beiden Wege auseinander und nur einer wird
    getestet."""
    sdk = anthropic_sdk()
    try:
        return klient.messages.create(**payload).model_dump()
    except Exception as e:
        raise sdk_fehler(sdk, e) from e


def sdk_fehler(sdk, e):
    """SDK-Ausnahme -> ApiFehler im Wortlaut des requests-Pfads.

    Der Wortlaut ist nicht Kosmetik: 'ttl_abgelehnt' und die Fehlersuche im
    Log lesen 'HTTP <code>'. Ein SDK-Pfad mit eigenem Wortlaut haette den
    Rueckfall der Cache-Lebensdauer still ausgehebelt."""
    code = getattr(e, "status_code", None)
    if code is None and sdk and isinstance(e, getattr(
            sdk, "APIConnectionError", ())):
        return ApiFehler(f"Netzwerkfehler: {e}")
    if code is None:
        return ApiFehler(str(e))
    koerper = getattr(e, "body", None) or getattr(e, "message", "") or str(e)
    if code in (401, 403):
        return ApiFehler(
            f"HTTP {code} — Schluessel fehlt, ist abgelaufen oder hat keine "
            f"Berechtigung fuer dieses Modell.\n{str(koerper)[:300]}")
    return ApiFehler(f"HTTP {code}: {str(koerper)[:300]}")


def ttl_abgelehnt(fehler):
    """Ist dieser Fehler die Ablehnung der Cache-Lebensdauer?

    Eng gefasst: nur HTTP 400, und nur wenn die Meldung den Marker selbst
    benennt. Ein zu weiter Fang wuerde echte Payloadfehler verschlucken und
    still ein zweites Mal Geld ausgeben."""
    t = str(fehler)
    return t.startswith("HTTP 400") and "ttl" in t.lower()


class AnthropicBackend(Backend):
    """Messages-API. Drei Eigenheiten sind Absicht, nicht Versehen:

    - Der System-Prompt traegt einen Cache-Marker. Er ist ueber alle Chunks
      byteweise identisch; wer Bausteine umsortiert, zerstoert die
      Trefferquote unbemerkt.
    - Es gehen KEINE Sampling-Parameter raus. claude-opus-5 hat
      temperature/top_p/top_k entfernt und antwortet darauf mit HTTP 400.
      Die Tiefe steuert 'effort'. Begruendung in ENTSCHEIDUNGEN.md.
    - Die Cache-Lebensdauer ist eine Versicherung, kein Sparposten. Lehnt
      der Anbieter sie ab, laeuft der Lauf ohne sie weiter.
    """

    URL     = "https://api.anthropic.com/v1/messages"
    VERSION = "2023-06-01"

    def payload(self, cfg, system, user, rolle, modell, werkzeuge=None):
        marker = {"type": "ephemeral"}
        ttl = cache_ttl(cfg)
        if ttl:
            marker["ttl"] = ttl
        p = {
            "model": modell,
            "max_tokens": int(cfg.get("max_tokens_api", 32000)),
            # Liste statt String: nur ein Block kann den Cache-Marker tragen.
            "system": [{"type": "text", "text": system,
                        "cache_control": marker}],
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": effort_fuer(cfg, rolle)},
        }
        if werkzeuge:
            p["tools"] = werkzeuge
        return p

    def antwort_lesen(self, d, roh=False):
        """(Text, Usage). Wirft bei Ablehnung, statt Leeres zurueckzugeben."""
        if d.get("stop_reason") == "refusal":
            grund = (d.get("stop_details") or {}).get("category") or "ohne Angabe"
            raise ApiFehler(
                f"Das Modell hat die Anfrage abgelehnt (Kategorie: {grund}). "
                f"Der Chunk bleibt unuebersetzt.")
        text = "".join(b.get("text", "") for b in d.get("content", [])
                       if b.get("type") == "text")
        u = d.get("usage") or {}
        # Die Aufschluesselung entscheidet ueber den Preis: ein Eintrag mit
        # einer Stunde Lebensdauer kostet beim Schreiben doppelt, einer mit
        # fuenf Minuten das 1,25-fache. Ohne sie waere jede Kostenzeile eine
        # Schaetzung.
        c = u.get("cache_creation") or {}
        usage = {"ein": u.get("input_tokens", 0),
                 "aus": u.get("output_tokens", 0),
                 "cache_lesen": u.get("cache_read_input_tokens", 0),
                 "cache_schreiben": u.get("cache_creation_input_tokens", 0),
                 "cache_schreiben_1h": c.get("ephemeral_1h_input_tokens", 0)}
        if d.get("stop_reason") == "max_tokens":
            print("    WARNUNG: Ausgabe am max_tokens-Limit abgeschnitten.")
        return (text if roh else saeubern(text)), usage

    ZAEHLER = "https://api.anthropic.com/v1/messages/count_tokens"

    def klient(self, cfg):
        """Der SDK-Klient, oder None. Einmal gebaut, dann behalten.

        Je Aufruf einen neuen zu bauen wuerde den Verbindungspool
        wegwerfen — bei 600 Aufrufen je Buch ist das keine Kleinigkeit."""
        sdk = anthropic_sdk()
        if not sdk or not cfg.get("sdk_nutzen", True):
            return None
        schluessel = api_schluessel("anthropic")
        if not schluessel:
            return None
        if schluessel not in _KLIENTEN:
            _KLIENTEN[schluessel] = sdk.Anthropic(
                api_key=schluessel,
                timeout=float(cfg.get("timeout_read_api", 600)),
                max_retries=int(cfg.get("max_retries", 3)))
        return _KLIENTEN[schluessel]

    def zaehle_tokens(self, cfg, system, user, modell=""):
        schluessel = api_schluessel("anthropic")
        if not schluessel:
            return None
        anfrage = {"model": modell,
                   "system": [{"type": "text", "text": system}],
                   "messages": [{"role": "user", "content": user}]}
        k = self.klient(cfg)
        try:
            if k is not None:
                return int(k.messages.count_tokens(**anfrage).input_tokens)
            r = requests.post(
                self.ZAEHLER, json=anfrage,
                headers={"x-api-key": schluessel,
                         "anthropic-version": self.VERSION,
                         "content-type": "application/json"},
                timeout=(cfg.get("timeout_connect", 10), 60))
            return int(r.json()["input_tokens"]) if r.status_code == 200 \
                else None
        except Exception:
            return None

    def chat(self, cfg, system, user, rolle="uebersetzung", modell="",
             roh=False, werkzeuge=None):
        schluessel = api_schluessel("anthropic")
        if not schluessel:
            sys.exit("FEHLER: ANTHROPIC_API_KEY fehlt.\n"
                     "  Colab:  im Secrets-Reiter hinterlegen\n"
                     "  sonst:  export ANTHROPIC_API_KEY=...")
        kopfzeilen = {"x-api-key": schluessel,
                      "anthropic-version": self.VERSION,
                      "content-type": "application/json"}
        timeout = (cfg["timeout_connect"], cfg.get("timeout_read_api", 600))
        k = self.klient(cfg)

        # Ein Payloadbauer, ein Antwortleser, zwei Transportwege. Wer die
        # SDK an 'payload' vorbei aufruft, hat zwei Wahrheiten darueber,
        # was wirklich rausgeht — und der Selbsttest prueft nur eine.
        def einmal():
            p = self.payload(cfg, system, user, rolle, modell, werkzeuge)
            if k is not None:
                return sdk_antwort(k, p)
            return sende(lambda: requests.post(self.URL, json=p,
                                               headers=kopfzeilen,
                                               timeout=timeout),
                         cfg["max_retries"]).json()
        try:
            r = einmal()
        except ApiFehler as e:
            # Die Lebensdauer ist eine Versicherung. Kennt der Anbieter sie
            # nicht, waere ein Abbruch mitten im Buch der teurere Fehler:
            # einmal melden, ohne sie weiterlaufen.
            if not (cache_ttl(cfg) and ttl_abgelehnt(e)):
                raise
            globals()["_TTL_ABGELEHNT"] = True
            print(f"    WARNUNG: Cache-Lebensdauer '{cfg.get('cache_ttl')}' "
                  f"wird abgelehnt — der Lauf geht ohne sie weiter.\n"
                  f"             'cache_ttl' in projekt.json leeren, dann "
                  f"verschwindet diese Meldung.")
            r = einmal()
        text, usage = self.antwort_lesen(r, roh)
        usage_buchen(rolle, modell, usage)
        return text


class GeminiBackend(Backend):
    """generateContent.

    Sendet KEINE Sampling-Parameter: die API ignoriert temperature/top_p/
    top_k bei 3.6 Flash, kuenftige Generationen antworten mit HTTP 400.
    Der Selbsttest prueft, dass das Payload sauber bleibt.
    """

    BASIS = "https://generativelanguage.googleapis.com/v1beta/models"

    def payload(self, cfg, system, user, rolle, modell):
        return {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
        }

    def antwort_lesen(self, d, roh=False):
        kandidaten = d.get("candidates") or []
        if not kandidaten:
            grund = (d.get("promptFeedback") or {}).get("blockReason")
            raise ApiFehler(f"Keine Antwort erhalten (blockReason: "
                            f"{grund or 'ohne Angabe'}).")
        k = kandidaten[0]
        ende = k.get("finishReason")
        if ende in ("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "RECITATION"):
            raise ApiFehler(f"Antwort abgebrochen (finishReason: {ende}).")
        text = "".join(t.get("text", "") for t
                       in (k.get("content") or {}).get("parts", []))
        if ende == "MAX_TOKENS":
            print("    WARNUNG: Ausgabe am Token-Limit abgeschnitten.")
        u = d.get("usageMetadata") or {}
        usage = {"ein": u.get("promptTokenCount", 0),
                 "aus": u.get("candidatesTokenCount", 0),
                 "cache_lesen": u.get("cachedContentTokenCount", 0),
                 "cache_schreiben": 0}
        return (text if roh else saeubern(text)), usage

    def verfuegbare_modelle(self, cfg):
        """Modellnamen, die generateContent unterstuetzen.

        Der Preisname eines Modells und sein API-Name sind nicht dasselbe —
        wer 404 bekommt, sieht hier, was der Anbieter wirklich anbietet."""
        schluessel = api_schluessel("google")
        if not schluessel:
            return []
        namen = []
        seite = f"{self.BASIS}?pageSize=200"
        while seite:
            r = requests.get(seite, headers={"x-goog-api-key": schluessel},
                             timeout=(10, 60))
            r.raise_for_status()
            d = r.json()
            for m in d.get("models", []):
                if "generateContent" in (m.get("supportedGenerationMethods")
                                         or []):
                    namen.append(m.get("name", "").replace("models/", ""))
            weiter = d.get("nextPageToken")
            seite = (f"{self.BASIS}?pageSize=200&pageToken={weiter}"
                     if weiter else None)
        return sorted(namen)

    def zaehle_tokens(self, cfg, system, user, modell=""):
        schluessel = api_schluessel("google")
        if not schluessel:
            return None
        try:
            r = requests.post(
                f"{self.BASIS}/{modell}:countTokens",
                json=self.payload(cfg, system, user, "begruendung", modell),
                headers={"x-goog-api-key": schluessel,
                         "content-type": "application/json"},
                timeout=(cfg.get("timeout_connect", 10), 60))
            return int(r.json()["totalTokens"]) if r.status_code == 200 \
                else None
        except Exception:
            return None

    def chat(self, cfg, system, user, rolle="begruendung", modell="",
             roh=False):
        schluessel = api_schluessel("google")
        if not schluessel:
            sys.exit("FEHLER: GEMINI_API_KEY fehlt.\n"
                     "  Colab:  Secret 'GoogleKI' hinterlegen\n"
                     "  sonst:  export GEMINI_API_KEY=...")
        p = self.payload(cfg, system, user, rolle, modell)
        url = f"{self.BASIS}/{modell}:generateContent"
        kopfzeilen = {"x-goog-api-key": schluessel,
                      "content-type": "application/json"}
        timeout = (cfg["timeout_connect"], cfg.get("timeout_read_api", 600))
        r = sende(lambda: requests.post(url, json=p, headers=kopfzeilen,
                                        timeout=timeout),
                  cfg["max_retries"])
        text, usage = self.antwort_lesen(r.json(), roh)
        usage_buchen(rolle, modell, usage)
        return text


BACKENDS = {"anthropic": AnthropicBackend(), "google": GeminiBackend()}


def backend(modell):
    """Backend zum Modellnamen."""
    b = BACKENDS.get(backend_name(modell))
    if b is None:
        sys.exit(f"FEHLER: kein Backend fuer '{modell}'. "
                 f"Verfuegbar: {', '.join(BACKENDS)}")
    return b


def chat(cfg, system, user, rolle="uebersetzung", roh=False, werkzeuge=None):
    """Der einzige Modellaufruf des Projekts.

    Die Rolle loest Modell, Backend und Effort auf. Es gehen keine
    Sampling-Parameter hinaus: claude-opus-5 hat temperature/top_p/top_k
    entfernt und antwortet darauf mit HTTP 400, Gemini ignoriert sie. Die
    Tiefe steuert 'effort_<rolle>'.

    'roh=True' schaltet saeubern() ab. Noetig, wenn die Antwort selbst
    Codebloecke enthaelt: saeubern schneidet den aeusseren Zaun ab und
    laesst die inneren unpaarig zurueck. Fuer uebersetzten Fliesstext
    bleibt saeubern richtig — es entfernt genau die Vorreden und Zaeune,
    die ein Modell unaufgefordert um Prosa legt."""
    modell = modell_fuer(cfg, rolle)
    b = backend(modell)
    if werkzeuge and not isinstance(b, AnthropicBackend):
        # Serverseitige Werkzeuge gibt es nur auf dem Anthropic-Pfad. Lieber
        # ohne laufen als mit einer Payload, die der Anbieter ablehnt.
        print(f"    HINWEIS: {modell} kennt keine Werkzeuge — "
              f"Aufruf ohne Websuche")
        werkzeuge = None
    zusatz = {"werkzeuge": werkzeuge} if werkzeuge else {}
    return b.chat(cfg, system, user, rolle=rolle, modell=modell, roh=roh,
                  **zusatz)


def tokens_zaehlen(cfg, rolle, system, user):
    """Exakte Eingabetoken fuer diese Rolle, oder None.

    Der Schaetzfaktor TOKEN_JE_WORT war bewusst hoch gesetzt, weil eine zu
    niedrige Schaetzung vor einem fuenfstuendigen Lauf der teurere Fehler
    ist. Wo der Anbieter zaehlt, wird nicht mehr geschaetzt."""
    modell = modell_fuer(cfg, rolle)
    return backend(modell).zaehle_tokens(cfg, system, user, modell)


def aktive_rollen(cfg):
    """Rollen, die dieser Lauf tatsaechlich aufruft.

    Die Liste ist die Grundlage der Kostenschaetzung und des Pings vor dem
    Lauf. Eine fehlende Rolle heisst dort: kostenlos und ungeprueft — und
    genau so sind 'zitat' und 'screening' durchgerutscht, nachdem ihre
    Schritte gebaut waren. Wer einen modellrufenden Schritt ergaenzt,
    ergaenzt ihn hier."""
    rollen = ["uebersetzung"]
    if cfg.get("revision_pass"):
        rollen.append("revision")
    for stufe in cfg.get("lektorat_passes", []):
        if stufe in ("stil", "korrektorat") and stufe not in rollen:
            rollen.append(stufe)
    # vorbereitung.py ist ein fester Pipelineschritt; konkordanz.py ruft
    # dieselbe Rolle zusaetzlich, wenn das Glossar lokal entsteht.
    rollen.append("vorbereitung")
    rollen.append("zitat")            # zitatrecherche.py
    rollen.append("begruendung")      # annotation.py, Teil 1
    rollen.append("screening")        # annotation.py, Teil 2
    if cfg.get("export_bewertung"):
        rollen.append("judge")
    # 'vergleich' bleibt draussen: konfiguriert, aber von keinem Schritt
    # gerufen. Der Ping in verifikation.py prueft es trotzdem mit.
    return rollen


def benutzte_backends(cfg):
    return {backend_name(modell_fuer(cfg, r)) for r in aktive_rollen(cfg)}


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

# Alle Anfuehrungszeichen, die in niederlaendischen Quellen vorkommen.
# Einfache Zeichen \u2018\u2026\u2019 sind dort die Regel, nicht die Ausnahme \u2014 wer sie
# in einer Zeichenklasse vergisst, verliert den halben Dialog.
ANFUEHRUNG = "\"\u201c\u201d\u201e\u2018\u2019\u00ab\u00bb\u2039\u203a"

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


def varianten(cfg):
    """Die Vergleichsvarianten des Testlaufs (Paket 5).

    Eine Variante unterscheidet sich von der Basis in der Chunkgroesse
    ODER im Modell — beides gehoert in dieselbe Mechanik, weil beides
    dieselbe Frage stellt: Wird der Text dadurch besser?

    Ist 'varianten' leer, wird die alte B-Variante aus
    'chunk_words_variante' abgeleitet. Damit laeuft eine projekt.json
    aus der Zeit davor unveraendert weiter."""
    roh = cfg.get("varianten") or []
    if not roh:
        b = cfg.get("chunk_words_variante")
        if b and b != cfg.get("chunk_words"):
            roh = [{"name": "B", "chunk_words": b}]
    sauber = []
    for v in roh:
        name = str(v.get("name", "")).strip()
        if name and name != "A":
            sauber.append(dict(v, name=name))
    return sauber


def variante_anwenden(cfg, v):
    """Uebernimmt die Abweichungen der Variante in eine Kopie der Config.

    Gibt (config, chunk_words, beschreibung) zurueck."""
    cfg = dict(cfg)
    chunk_words = int(v.get("chunk_words", cfg["chunk_words"]))
    teile = [f"{chunk_words} Woerter/Chunk"]
    modell = str(v.get("modell_uebersetzung", "")).strip()
    if modell:
        cfg["modell_uebersetzung"] = modell
        cfg["modell_revision"] = str(
            v.get("modell_revision", modell)).strip()
        teile.append(modell)
    return cfg, chunk_words, ", ".join(teile)


def rahmen_gruppen(paras, marker="#"):
    """Teilt die Absaetze an jeder Marker-Zeile (Paket 5).

    Die Markerzeile beginnt die neue Gruppe und bleibt im Text — sie ist
    die Gliederung des Autors, nicht unsere. Jede Gruppe wird getrennt
    gechunkt; die Fuge dazwischen setzt die Rueckschau zurueck.

    Grund: Tempus und Person der einen Erzaehlebene duerfen nicht in die
    andere bluten. Ohne den Schnitt bekaeme der erste Chunk nach dem
    Wechsel die letzten Saetze der vorigen Ebene als Vorbild."""
    if not marker:
        return [list(paras)]
    gruppen, aktuell = [], []
    for p in paras:
        if p.strip() == marker or p.strip().startswith(marker + " "):
            if aktuell:
                gruppen.append(aktuell)
            aktuell = [p]
        else:
            aktuell.append(p)
    if aktuell:
        gruppen.append(aktuell)
    return gruppen or [[]]


def ebenen_folge(gruppen, marker, perspektive):
    """Je Gruppe der Name der Erzaehlebene aus dem Stilprofil.

    Drei Faelle, in dieser Reihenfolge:
      - Die Markerzeile nennt die Ebene ('# Krieg') und der Name kommt in
        'perspektive' vor: die wird genommen.
      - Nackter Marker und genau zwei Ebenen: die jeweils andere als
        zuletzt. Nicht 'gerade/ungerade' — nach einer benannten Gruppe
        waere das versetzt.
      - Alles andere: keine Benennung. Lieber schweigen als raten — eine
        falsch benannte Ebene ist schaedlicher als gar keine.

    Die Reihenfolge in 'perspektive' ist die des ersten Auftretens im
    Buch, nicht die alphabetische: Der Text beginnt auf der zuerst
    genannten Ebene."""
    namen = list(perspektive) if isinstance(perspektive, dict) else []
    folge, letzte = [], None
    for gruppe in gruppen:
        kopf = gruppe[0].strip() if gruppe else ""
        rest = kopf[len(marker):].strip() if kopf.startswith(marker) else ""
        treffer = [n for n in namen if rest and n.lower() in rest.lower()]
        if treffer:
            name = treffer[0]
        elif len(namen) == 2:
            name = (namen[0] if letzte is None
                    else namen[1] if letzte == namen[0] else namen[0])
        else:
            name = ""
        folge.append(name)
        if name:
            letzte = name
    return folge


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


# Ab wann ein Chunk als uebergross gilt. Nicht 1,0: Die Chunkbildung haelt
# Absatzgrenzen ein, und ein Absatz endet selten genau auf der Zielmarke.
UEBERLAENGE = 1.25


def chunk_ueberlaengen(chunks, ziel, faktor=UEBERLAENGE):
    """(Nummer, Woerter, geschuetzt) je Chunk ueber der Marke.

    Gekappt wird bewusst nicht: Ein Absatz gehoert zusammen, und ein
    geschuetztes Zitat erst recht. Gezaehlt wird trotzdem, denn Ueberlaenge
    ist die Ursache hinter zwei Befunden, die sonst raetselhaft bleiben —
    verworfene Laengenverhaeltnisse und verschobene Absatzzahlen."""
    grenze = ziel * faktor
    raus = []
    for i, (text, geschuetzt) in enumerate(chunks, 1):
        w = len(text.split())
        if w > grenze:
            raus.append((i, w, geschuetzt))
    return raus


def ueberlaengen_melden(chunks, ziel, drucken=print):
    """Eine Zeile, wenn es Ueberlaengen gibt — sonst schweigen."""
    lang = chunk_ueberlaengen(chunks, ziel)
    if not lang:
        return lang
    groesster = max(w for _, w, _ in lang)
    geschuetzt = sum(1 for _, _, g in lang if g)
    drucken(f"Ueberlange Chunks:  {len(lang)} von {len(chunks)} ueber "
            f"{ziel * UEBERLAENGE:.0f} Woertern, groesster {groesster}"
            + (f", davon {geschuetzt} geschuetzt (Zitate)"
               if geschuetzt else ""))
    drucken("                    Nicht gekappt — Absatzgrenzen haben "
            "Vorrang. Erwarte dort eher\n"
            "                    verworfene Laengenverhaeltnisse.")
    return lang


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
    # Am Testauszug 1919 gefunden: vier der neun gemeldeten Treffer waren
    # Falschmeldungen und blaehten die Kennzahl um rund 80 Prozent auf.
    # Erst messen, dann anpassen — die Liste ist die richtige Stelle dafuer.
    "Menschen", "Deutschen", "Rauschen", "Griechen", "Gesprächen",
    "Bereichen", "Vergleichen", "Anzeichen", "Kennzeichen", "Zeichen",
    "Rauchen", "Tauchen", "Fluchen", "Kochen", "Pochen", "Stechen",
    "Sprechen", "Schleichen", "Erreichen", "Wichen", "Krachen",
    "München", "Mönchen",
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
