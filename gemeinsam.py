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
# Die Vorlage im Repo. Sie heisst absichtlich anders als die Arbeitsdatei:
# Gearbeitet wird IMMER mit der projekt.json im Projektordner, die Vorlage
# wird beim Erstlauf einmal dorthin kopiert und danach nie wieder angefasst.
# Solange beide gleich hiessen, sah die Vorlage aus wie "die" Konfiguration
# — und wer eine Einstellung suchte, aenderte die falsche Datei.
VORLAGE     = "projekt_vorlage.json"
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
    "ebenen":        "ebenen.json",
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
    # Zwischenstand des Screenings. Kein Text des Buches, sondern die
    # Befunde je Aufrufbuendel — abgelegt aus demselben Grund wie die
    # Chunks: Ein Absturz bei Aufruf 30 von 37 soll nicht 30 Aufrufe
    # kosten. Annotation darf nur hierher schreiben, sonst nirgends.
    "screening":    "teile/screening",
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
          "vorbereitung", "ebenen", "judge", "begruendung", "screening",
          "vergleich")


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
    "modell_ebenen":             "",
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
    "effort_ebenen":             "hoch",
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
    # Antwort im Stream abholen statt in einem Stueck. Wirkt nur auf dem
    # SDK-Pfad: Der requests-Pfad braeuchte einen handgeschriebenen
    # SSE-Parser, und ein Rueckfallpfad mit eigener Fehlerklasse ist keiner.
    "streaming":                 True,
    # Rueckfall bei einer Ablehnung durch den Sicherheitsklassifikator.
    # 'default' laesst den Anbieter das Ersatzmodell nach Kategorie waehlen,
    # eine Liste von bis zu drei Modellnamen bestimmt es selbst, '' schaltet
    # den Rueckfall ab. Das antwortende Modell steht in der Kostenuebersicht.
    "fallback_modelle":          "default",
    # Serverseitige Websuche der Zitatrecherche. Die Fassung ab Februar 2026
    # filtert Treffer vor dem Kontextfenster; 'websuche_filtern: false'
    # erzwingt den direkten Aufruf ohne diesen Zwischenschritt.
    "websuche_werkzeug":         "web_search_20260209",
    "websuche_filtern":          True,
    "websuche_max":              6,
    # Stapelbetrieb ('uebersetzung.py --stapel'). Laengste Kette, die
    # seriell bleibt. 0 heisst: nur an den Ebenenfugen trennen — dort
    # setzt die Rueckschau ohnehin zurueck, diese Schnitte kosten nichts.
    # Jeder weitere Schnitt ist eine Naht ohne deutsche Rueckschau; was
    # sie wert ist, misst 'bewertung.py --fugen'. Die Vorgabe ist
    # bewusst der Wert ohne Qualitaetskosten: Wer schneller fertig sein
    # will, entscheidet das mit 'pipeline.py wellen' vor Augen.
    "kette_max":                 0,
    "stapel_takt":               20,      # Sekunden zwischen zwei Blicken

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
    # Vorwegschau: die ersten Woerter des NAECHSTEN Chunks als Kontext.
    # Die Rueckschau allein laesst den Uebersetzer am Chunkende blind
    # werden — ein angefangener Satzbogen, eine Anrede, die erst danach
    # aufgeloest wird. 0 schaltet sie ab.
    "context_words_voraus":      150,
    # Woraus die Rueckschau gebildet wird: 'revision' (die Endfassung des
    # vorigen Chunks) oder 'entwurf' (Pass 1). Siehe ENTSCHEIDUNGEN.md.
    "rueckschau_quelle":         "revision",
    # Wie viele Chunks eine einmal genannte Figur im Personenblock
    # nachhallt. 0 = nur wer im Chunk vorkommt. Zurueckgesetzt wird der
    # Nachhall NUR an Ebenenfugen — innerhalb einer Erzaehlebene bleibt
    # die Figur dieselbe.
    "figuren_nachhall":          3,
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

    # Drei Testauszuege. Erzaehlung und Dialog messen, ob der Text als
    # deutsche Prosa besteht; die Fallenpassage misst, ob die Warnungen
    # aus dem Fallenblock ankommen — die Schwaeche dieser Sprachrichtung
    # faellt in einem ruhigen Erzaehlabschnitt gar nicht auf.
    # 0 fuer 'test_words_fallen' laesst den dritten Auszug weg.
    "test_words_erzaehlung":     2500,
    "test_words_dialog":         2500,
    "test_words_fallen":         2000,

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

# Spalten der Zitat-Freigabeliste. Sie stehen hier, weil zwei Module sie
# brauchen und keines das andere importieren kann: 'zitatrecherche' schreibt
# und liest die Liste, 'referenz_sync' legt den Tab an — und importiert
# umgekehrt. Zwei Listen waren zwei Wahrheiten: Die Vorlage legte den Tab
# mit anderen Ueberschriften an, als der Schritt danach hineinschrieb.
#
# 'belege' vor 'freigegeben': Der Mensch liest von links nach rechts, und die
# Freigabe ist die letzte Entscheidung. Gelesen wird ueber den Spaltennamen,
# nie ueber die Position.
ZITAT_SPALTEN = ["index", "sprache", "original", "vorschlag_de",
                 "uebersetzer", "quelle", "konfidenz", "belege",
                 "freigegeben"]

# Diese Schluessel werden von der Pipeline selbst gesetzt und duerfen von
# einer eingespielten projekt.json NICHT ueberschrieben werden (V4).
GESCHUETZT = {"ratio_min", "ratio_max", "ratio_kalibriert", "sprachpaar"}

# Nur diese Schluessel darf ein externes Rueckspiel aendern (V4).
AENDERBAR = {
    "chunk_words", "chunk_words_variante", "context_words",
    "context_words_voraus", "rueckschau_quelle", "figuren_nachhall",
    "revision_pass", "lektorat_passes",
    "diminutive", "tempus", "anrede_vorgabe",
    "quotes", "eszett", "varietaet", "dash",
    "test_words_erzaehlung", "test_words_dialog", "test_words_fallen",
    "lektorat_ratio_min", "lektorat_ratio_max",
    "export_glossar", "export_bewertung", "glossar_quelle", "sheets_id",
    "rahmen_marker", "varianten", "technik_ausnahmen",
    "timeout_connect", "max_retries",
    "backend_standard", "max_tokens_api", "timeout_read_api", "cache_ttl",
    "sdk_nutzen", "streaming", "fallback_modelle",
    "websuche_werkzeug", "websuche_filtern", "websuche_max",
    "kette_max", "stapel_takt",
} | {f"modell_{r}" for r in ROLLEN} | {f"effort_{r}" for r in ROLLEN}


def vorlage_pfad():
    """Die Vorlage neben dem Code, oder ''.

    Sie liegt im Code-Verzeichnis, nicht im Arbeitsverzeichnis: Sie
    gehoert dem Repo, die Arbeitsdatei dem Buch."""
    hier = os.path.dirname(os.path.abspath(__file__))
    for name in (VORLAGE, CONFIG):        # CONFIG: aelterer Auscheck
        p = os.path.join(hier, name)
        if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(CONFIG):
            return p
    return ""


def lade_config(pfad=CONFIG, pflicht=True):
    if not os.path.exists(pfad):
        if pflicht:
            sys.exit(f"FEHLER: {pfad} fehlt. Erst 'python3 pipeline.py init'.")
        # Ohne Arbeitsdatei gilt die Vorlage. Das betrifft nur Aufrufer,
        # die ohne Projekt auskommen — den Selbsttest, die Schrittliste.
        # Ein Buchlauf verlangt weiterhin seine eigene Konfiguration:
        # Er soll nicht mit fremden Werten anlaufen.
        v = vorlage_pfad()
        if v:
            cfg = dict(STANDARD)
            try:
                cfg.update(json.load(open(v, encoding="utf-8")))
            except Exception:
                pass
            return cfg
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
    "ebenen": (
        "claude-opus-5", "hoch",
        "Findet die Erzaehlebenen im Quelltext. Ein Aufruf je Buch, und "
        "das Ergebnis bestimmt JEDE Chunkgrenze und jeden Rueckschau-Reset "
        "— eine falsche Fuge laesst Tempus und Person der einen Ebene in "
        "die andere bluten. Der Plan sah hier gemini-3.6-flash vor; bei "
        "unter einem halben Dollar Unterschied fuer ein ganzes Buch ist "
        "das die falsche Stelle zum Sparen. Die Messung steht aus."),
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
# Dasselbe gilt fuer Transport und Anbieterfassungen: Die Fassung der
# Websuche altert beim Anbieter und haengt nicht am Text. Ein Buch, das eine
# andere braucht, nennt sie in 'technik_ausnahmen'.
#
# Der Ueberschreibschutz der projekt.json bleibt: erkannt wird die
# Abweichung, uebernommen wird sie nur auf ausdrueckliche Ansage.
TECHNIK = ({"backend_standard", "max_tokens_api", "timeout_read_api",
            "cache_ttl", "sdk_nutzen", "streaming", "fallback_modelle",
            "websuche_werkzeug", "websuche_filtern", "websuche_max",
            "stapel_takt"}
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
#
# 'suchen' zaehlt keine Token, sondern Aufrufe der serverseitigen Websuche.
# Sie kostet je Suche und unabhaengig vom Modell; ohne eigenes Feld waere die
# Zitatrecherche der einzige Schritt, dessen Rechnung nicht aufgeht.
USAGE_FELDER = ("ein", "aus", "cache_lesen", "cache_schreiben",
                "cache_schreiben_1h", "suchen")


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


def kosten_schluessel(lauf, rolle, modell, stapel=False):
    """Buchungsschluessel. Die Teile sind mit '/' getrennt lesbar.

    Der Stapel bekommt einen eigenen Schluessel, weil er einen eigenen
    Tarif hat — die halben Preise. In derselben Zeile summiert waeren
    Token zweier Preise, und die Zeile liesse sich nicht mehr rechnen.
    Das ist derselbe Grund, aus dem der Schluessel ueberhaupt drei Teile
    hat statt einem."""
    return f"{lauf}/{rolle}/{modell}" + ("/stapel" if stapel else "")


def usage_buchen(rolle, modell, usage, stapel=False):
    """Summiert Token je (Lauf, Rolle, Modell, Weg) in manifest.json.

    Nicht je Rolle allein: Wer eine Rolle einmal mit einem anderen Modell
    probiert, haette sonst die gesamte Rolle auf dieses Modell umetikettiert
    — Token und Preis waeren danach unvereinbar.

    Schlaegt das Buchen fehl, kostet das nur die Statistik — nie den Lauf."""
    try:
        m = {}
        if os.path.exists(MANIFEST):
            m = json.load(open(MANIFEST, encoding="utf-8"))
        k = m.setdefault("kosten", {})
        e = k.setdefault(kosten_schluessel(_LAUF, rolle, modell, stapel),
                         dict({"lauf": _LAUF, "rolle": rolle,
                               "modell": modell, "aufrufe": 0,
                               "stapel": bool(stapel)},
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

# Preis einer serverseitigen Websuche, 10 $ je 1000. Anders als die
# Tokenpreise haengt er nicht am Modell und steht deshalb hier und nicht in
# TARIFE — sonst muesste ihn jeder Modelleintrag wiederholen.
SUCHE_DOLLAR = 0.010

# Die Stapel-API rechnet alles zum halben Preis — Eingabe, Ausgabe und
# Cache. Der Rabatt liegt auf dem Tarif, nicht auf einzelnen Posten;
# deshalb ein Faktor am Ende und keine zweite Preisformel.
STAPEL_FAKTOR = 0.5


def kosten_dollar(e, t):
    """Preis einer Buchung. Eine Formel fuer alle Auswertungen.

    Zwei Formeln waren zwei Wahrheiten: die Variantenkosten in
    bewertung.py liessen den Cache weg und lagen dadurch zu niedrig.

    Ob die Buchung ueber den Stapel lief, steht in ihr selbst ('stapel')
    — nicht im Tarif. Der Tarif gehoert dem Modell, der Rabatt dem Weg."""
    if not t:
        return None
    if e.get("stapel"):
        return kosten_dollar({k: v for k, v in e.items() if k != "stapel"},
                             t) * STAPEL_FAKTOR
    # 'cache_schreiben' ist die Gesamtzahl; der Anteil mit einer Stunde
    # Lebensdauer steht daneben und kostet mehr.
    lang = int(e.get("cache_schreiben_1h", 0))
    kurz = max(0, int(e.get("cache_schreiben", 0)) - lang)
    return ((int(e.get("ein", 0)) * t["ein"]
             + int(e.get("cache_lesen", 0)) * t["ein"] * CACHE_LESE_FAKTOR
             + kurz * t["ein"] * CACHE_SCHREIB_FAKTOR
             + lang * t["ein"] * CACHE_SCHREIB_FAKTOR_1H
             + int(e.get("aus", 0)) * t["aus"]) / 1e6
            + int(e.get("suchen", 0)) * SUCHE_DOLLAR)


def kosten_posten(manifest):
    """Buchungen als (lauf, rolle, modell, werte), Buchproduktion zuerst.

    Liest auch das alte Format, in dem der Schluessel nur die Rolle war —
    dort ist der Lauf unbekannt und bleibt leer, statt 'voll' zu behaupten.
    Der vierte Teil '/stapel' unterscheidet den Weg; der Tarif dahinter
    steht in der Buchung selbst, nicht im Schluessel."""
    raus = []
    for schluessel, e in (manifest or {}).get("kosten", {}).items():
        if not isinstance(e, dict) or schluessel.startswith("_"):
            continue
        teile = schluessel.split("/")
        alt = len(teile) not in (3, 4)
        raus.append((e.get("lauf", "") if alt else teile[0],
                     e.get("rolle") or (schluessel if alt else teile[1]),
                     e.get("modell", "") if alt else teile[2],
                     e))
    raus.sort(key=lambda x: (x[0] not in ("voll", ""), x[0], x[1], x[2],
                             bool(x[3].get("stapel"))))
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

    def chat_meta(self, cfg, system, user, rolle="uebersetzung", modell="",
                  roh=False, werkzeuge=None, schema=None):
        """(Text, Befund). Der Befund traegt, was neben dem Text anfiel:
        das antwortende Modell, die Belege der Websuche, die Zahl der
        Suchen. Wer nur den Text braucht, ruft 'chat'."""
        raise NotImplementedError

    def chat(self, cfg, system, user, **kw):
        return self.chat_meta(cfg, system, user, **kw)[0]

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


# Zwei Zusicherungen, die der Lauf notfalls aufgibt: die Lebensdauer des
# Cache-Eintrags und der serverseitige Rueckfall bei einer Ablehnung. Beide
# sind Versicherungen, keine Voraussetzungen — lehnt der Anbieter eine ab,
# waere ein Abbruch mitten im Buch der teurere Fehler.
#
# Je ein Merker, der nach der ersten Ablehnung stehen bleibt: Ohne ihn liefe
# jeder weitere Chunk erneut in denselben Fehlversuch und zahlte ihn.
_TTL_ABGELEHNT = False
_FALLBACK_ABGELEHNT = False


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


def sdk_antwort(klient, payload, betas=(), streamen=False):
    """Ein Aufruf ueber die SDK, als dasselbe dict wie der requests-Pfad.

    'model_dump' gibt genau die Struktur zurueck, die auch ueber die Leitung
    kaeme. Damit bleibt 'antwort_lesen' der einzige Ort, der Antworten
    versteht — sonst driften die beiden Wege auseinander und nur einer wird
    getestet. Das gilt auch fuer den Stream: 'get_final_message' liefert
    dieselbe Nachricht wie ein Aufruf ohne Stream, nur eingesammelt.

    Streamen ist keine Bequemlichkeit. Ohne Stream haengt eine stockende
    Anfrage bis zum Lesetimeout — zehn Minuten, in denen nichts ankommt und
    niemand weiss, ob noch etwas kommt. Mit Stream haelt die Verbindung sich
    selbst am Leben, und die SDK verlangt ihn ohnehin, sobald 'max_tokens'
    gross genug ist, dass die Antwort das HTTP-Zeitfenster sprengen koennte.

    Betakennwoerter gehen ueber den Namensraum 'beta'; ohne sie bleibt der
    normale Weg, damit ein Lauf ohne Betafunktionen nichts davon mitbekommt.
    """
    sdk = anthropic_sdk()
    ziel = klient.beta.messages if betas else klient.messages
    p = dict(payload, betas=list(betas)) if betas else payload
    try:
        if streamen:
            with ziel.stream(**p) as strom:
                return strom.get_final_message().model_dump()
        return ziel.create(**p).model_dump()
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


# Der Betaname muss genau dieses Datum tragen: Nur '2026-07-01' nimmt
# 'default' an, '2026-06-01' kann ausschliesslich die Modellliste. Jeder
# andere Wert laesst die API das Feld 'fallbacks' mit HTTP 400 ablehnen.
BETA_FALLBACK = "server-side-fallback-2026-07-01"


def fallbacks_wert(cfg):
    """Der Wert des Feldes 'fallbacks', oder None.

    Eine Ablehnung durch den Sicherheitsklassifikator ist keine Ausnahme,
    die man wegkonfiguriert: Ein Roman ueber Krieg, Krankheit oder Gewalt
    trifft sie irgendwann. Ohne Rueckfall kostet sie drei gleich
    aussichtslose Wiederholungen und danach den Abbruch — mitten im Buch,
    bei Chunk 300.

    'default' ueberlaesst dem Anbieter die Wahl des Ersatzmodells nach
    Ablehnungskategorie, eine Liste bestimmt sie selbst. Mehr als drei
    Modelle nimmt die API nicht an; gekappt wird hier, damit der Anbieter
    daraus keinen HTTP 400 machen muss."""
    if _FALLBACK_ABGELEHNT:
        return None
    w = cfg.get("fallback_modelle", "")
    if isinstance(w, str):
        return "default" if w.strip().lower() == "default" else None
    if isinstance(w, (list, tuple)):
        namen = [str(m).strip() for m in w if str(m).strip()][:3]
        return [{"model": m} for m in namen] or None
    return None


def fallback_abgelehnt(fehler):
    """Ist dieser Fehler die Ablehnung des serverseitigen Rueckfalls?

    Faengt beides: das unbekannte Betakennwort im Kopf und das abgelehnte
    Feld im Payload. Beide Meldungen nennen 'fallback' im Wortlaut, und
    beide sind HTTP 400 — enger geht es nicht, ohne die Meldungstexte des
    Anbieters festzuschreiben."""
    t = str(fehler)
    return t.startswith("HTTP 400") and "fallback" in t.lower()


def werkzeug_datum(typ):
    """Die Datumsziffern einer Werkzeugfassung ('20260209'), oder ''.

    Die Fassungen heissen 'web_search_<JJJJMMTT>'; verglichen wird das
    Datum, nicht der ganze Name. Ein Stringvergleich ueber den Namen sieht
    richtig aus und bricht beim ersten Werkzeug mit anderem Praefix."""
    m = re.search(r"_(\d{8})$", str(typ or ""))
    return m.group(1) if m else ""


# Ab dieser Fassung filtert die Websuche ihre Treffer aus der
# Codeausfuehrung heraus, bevor sie ins Kontextfenster wandern.
WEBSUCHE_FILTERND = "20260209"


def websuche_werkzeug(cfg):
    """Werkzeugdefinition der serverseitigen Websuche, oder None.

    Die Fassung steht in projekt.json, nicht im Code: Sie wechselt
    schneller als dieses Projekt, und ein hartkodierter Name laesst den
    Schritt eines Tages mit veralteten Treffern laufen, ohne dass jemand
    es merkt."""
    typ = str(cfg.get("websuche_werkzeug", "") or "").strip()
    if not typ:
        return None
    w = {"type": typ, "name": "web_search",
         "max_uses": int(cfg.get("websuche_max", 6) or 6)}
    # Die filternden Fassungen rufen die Suche standardmaessig aus der
    # Codeausfuehrung heraus. 'websuche_filtern: false' erzwingt den
    # direkten Aufruf — noetig fuer Modelle, die das Programmieren von
    # Werkzeugaufrufen nicht koennen und sonst mit HTTP 400 antworten.
    if werkzeug_datum(typ) >= WEBSUCHE_FILTERND \
            and not cfg.get("websuche_filtern", True):
        w["allowed_callers"] = ["direct"]
    return [w]


def belege(d):
    """Quellenangaben aus den Zitatmarken einer Antwort.

    Die Websuche haengt an jeden Textblock, den ein Treffer gestuetzt hat,
    die Fundstelle mit URL, Titel und belegtem Wortlaut. Das ist etwas
    anderes als die Quellenangabe, die das Modell in seine Antwort
    schreibt: Die eine ist ein abgerufener Treffer, die andere ein Satz,
    den das Modell formuliert hat.

    Genau diesen Unterschied soll die Zitatrecherche sichtbar machen —
    'erfinde nichts' ist eine Anweisung, eine URL ist ein Beleg."""
    raus, gesehen = [], set()
    for b in d.get("content") or []:
        if b.get("type") != "text":
            continue
        for z in b.get("citations") or []:
            url = str(z.get("url") or "").strip()
            if not url or url in gesehen:
                continue
            gesehen.add(url)
            raus.append({"url": url,
                         "titel": str(z.get("title") or "").strip(),
                         "stelle": str(z.get("cited_text") or "").strip()})
    return raus


def rueckfall_gelaufen(d):
    """Hat ein Ersatzmodell diese Antwort erzeugt?

    Der Modellname allein reicht als Beleg nicht: Ein Alias loest auf einen
    datierten Namen auf, und jede Antwort waere ein falscher Alarm. Der
    Beleg ist der Eintrag 'fallback_message' unter den Iterationen. Er
    steht auch dann da, wenn die API die Anfrage wegen einer frueheren
    Ablehnung gleich an das Ersatzmodell geleitet hat — dann entsteht gar
    kein Uebergabeblock, und nur die Iterationen verraten es."""
    return any((it or {}).get("type") == "fallback_message"
               for it in ((d.get("usage") or {}).get("iterations") or []))


def bedient_von(d, angefragt):
    """Das Modell, unter dem diese Antwort gebucht gehoert.

    Nach einem Rueckfall ist das nicht das angefragte. Ohne Rueckfall
    bleibt es beim angefragten Namen, auch wenn die Antwort einen
    aufgeloesten traegt: Ein zweiter Name fuer dasselbe Modell zerlegte die
    Kostenzeile und liesse den Tarif ins Leere greifen."""
    if not rueckfall_gelaufen(d):
        return angefragt
    return str(d.get("model") or "").strip() or angefragt


def ohne_none(x):
    """Kopie ohne Schluessel mit dem Wert None.

    Die SDK fuellt ungesetzte Felder mit None; unveraendert
    zurueckgeschickt lehnt die API sie ab. Betrifft nur den Weg, auf dem
    eine angehaltene Antwort zurueckgeht — gelesen wird weiter das
    vollstaendige dict."""
    if isinstance(x, dict):
        return {k: ohne_none(v) for k, v in x.items() if v is not None}
    if isinstance(x, list):
        return [ohne_none(v) for v in x]
    return x


class AnthropicBackend(Backend):
    """Messages-API. Vier Eigenheiten sind Absicht, nicht Versehen:

    - Der System-Prompt traegt einen Cache-Marker. Er ist ueber alle Chunks
      byteweise identisch; wer Bausteine umsortiert, zerstoert die
      Trefferquote unbemerkt.
    - Es gehen KEINE Sampling-Parameter raus. claude-opus-5 hat
      temperature/top_p/top_k entfernt und antwortet darauf mit HTTP 400.
      Die Tiefe steuert 'effort'. Begruendung in ENTSCHEIDUNGEN.md.
    - Die Cache-Lebensdauer ist eine Versicherung, kein Sparposten. Lehnt
      der Anbieter sie ab, laeuft der Lauf ohne sie weiter.
    - Eine Ablehnung des Sicherheitsklassifikators faellt auf ein
      Ersatzmodell zurueck ('fallbacks'), statt den Lauf abzubrechen.
      Gebucht wird unter dem Modell, das wirklich geantwortet hat.
    """

    URL     = "https://api.anthropic.com/v1/messages"
    VERSION = "2023-06-01"

    def payload(self, cfg, system, user, rolle, modell, werkzeuge=None,
                schema=None):
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
        if schema:
            # Strukturierte Ausgabe: Der Anbieter erzwingt die Form, statt
            # dass ein Parser sie aus Prosa fischt. 'format' steht neben
            # 'effort' im selben Block.
            p["output_config"]["format"] = {"type": "json_schema",
                                            "schema": schema}
        if werkzeuge:
            p["tools"] = werkzeuge
        rueckfall = fallbacks_wert(cfg)
        if rueckfall:
            # Achtung Paket G: Die Stapel-API nimmt 'fallbacks' NICHT an —
            # ein Stapeleintrag damit kommt als Fehler zurueck. Der
            # Stapeladapter muss das Feld also entfernen, nicht erben.
            p["fallbacks"] = rueckfall
        return p

    def betas(self, cfg):
        """Betakennwoerter fuer diesen Aufruf. Leer heisst: normaler Weg."""
        return [BETA_FALLBACK] if fallbacks_wert(cfg) else []

    def antwort_lesen(self, d, roh=False):
        """(Text, Usage). Wirft bei Ablehnung, statt Leeres zurueckzugeben."""
        if d.get("stop_reason") == "refusal":
            s = d.get("stop_details") or {}
            grund = s.get("category") or "ohne Angabe"
            # Der Erklaertext ist nicht stabil formuliert und wird deshalb
            # gezeigt, nicht ausgewertet. Fuer den Menschen vor dem Log ist
            # er das einzige, was die Kategorie greifbar macht.
            erklaerung = str(s.get("explanation") or "").strip()
            raise ApiFehler(
                f"Das Modell hat die Anfrage abgelehnt (Kategorie: {grund})."
                + (f" {erklaerung}" if erklaerung else "")
                + " Der Chunk bleibt unuebersetzt.")
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
                 "cache_schreiben_1h": c.get("ephemeral_1h_input_tokens", 0),
                 "suchen": (u.get("server_tool_use") or {}).get(
                     "web_search_requests", 0)}
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

    # Wie oft eine angehaltene Werkzeugrunde fortgesetzt wird. Die API haelt
    # eine lange Werkzeugschleife an und antwortet mit 'pause_turn'; wer
    # nicht fortsetzt, bekommt eine halbe Antwort und liest sie als
    # Formfehler — bei der Zitatrecherche hiess das: Zitat uebersprungen,
    # Luecke, die spaeter jemand von Hand sucht. Die Grenze verhindert, dass
    # eine Schleife ohne Ende Geld kostet.
    PAUSEN_MAX = 4

    def versicherung_aufgeben(self, cfg, e):
        """Gibt eine Zusicherung auf, wenn dieser Fehler sie ablehnt.

        True heisst: derselbe Aufruf darf noch einmal laufen, jetzt ohne
        sie. False heisst: echter Fehler, weiterreichen.

        Der Aufrufer darf in einer Schleife fragen — jede Zusicherung laesst
        sich nur einmal aufgeben, danach melden 'cache_ttl' und
        'fallbacks_wert' nichts mehr und die Schleife endet."""
        if cache_ttl(cfg) and ttl_abgelehnt(e):
            globals()["_TTL_ABGELEHNT"] = True
            print(f"    WARNUNG: Cache-Lebensdauer '{cfg.get('cache_ttl')}' "
                  f"wird abgelehnt — der Lauf geht ohne sie weiter.\n"
                  f"             'cache_ttl' in projekt.json leeren, dann "
                  f"verschwindet diese Meldung.")
            return True
        if fallbacks_wert(cfg) and fallback_abgelehnt(e):
            globals()["_FALLBACK_ABGELEHNT"] = True
            print(f"    WARNUNG: Serverseitiger Rueckfall wird abgelehnt — "
                  f"der Lauf geht ohne ihn weiter.\n"
                  f"             Eine Ablehnung bricht ab jetzt den Chunk ab. "
                  f"'fallback_modelle' in projekt.json leeren, dann "
                  f"verschwindet diese Meldung.")
            return True
        return False

    def chat_meta(self, cfg, system, user, rolle="uebersetzung", modell="",
                  roh=False, werkzeuge=None, schema=None):
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
        streamen = bool(cfg.get("streaming", True))

        def neues_payload():
            return self.payload(cfg, system, user, rolle, modell, werkzeuge,
                                schema)

        # Ein Payloadbauer, ein Antwortleser, zwei Transportwege. Wer die
        # SDK an 'payload' vorbei aufruft, hat zwei Wahrheiten darueber,
        # was wirklich rausgeht — und der Selbsttest prueft nur eine.
        def einmal(p):
            betas = self.betas(cfg)
            if k is not None:
                return sdk_antwort(k, p, betas, streamen)
            kopf = dict(kopfzeilen)
            if betas:
                kopf["anthropic-beta"] = ",".join(betas)
            return sende(lambda: requests.post(self.URL, json=p,
                                               headers=kopf,
                                               timeout=timeout),
                         cfg["max_retries"]).json()

        def mit_versicherung(p):
            while True:
                try:
                    return einmal(p)
                except ApiFehler as e:
                    if not self.versicherung_aufgeben(cfg, e):
                        raise
                    # Die Zusicherung ist jetzt abgeschaltet; das Payload
                    # muss neu gebaut werden, sonst traegt es sie weiter.
                    # Der Gespraechsverlauf bleibt, er gehoert nicht dazu.
                    p = dict(neues_payload(), messages=p["messages"])

        p = neues_payload()
        text, usage = "", dict.fromkeys(USAGE_FELDER, 0)
        gefunden, bedient = [], modell
        for _ in range(self.PAUSEN_MAX + 1):
            d = mit_versicherung(p)
            # Gesaeubert wird erst am Ende: saeubern() schneidet Vorreden
            # und Codezaeune ab, und ein Zaun, der ueber zwei Runden geht,
            # waere nach zwei Teilreinigungen unpaarig.
            stueck, u = self.antwort_lesen(d, roh=True)
            text += stueck
            for f in USAGE_FELDER:
                usage[f] += int(u.get(f, 0) or 0)
            gefunden += belege(d)
            bedient = bedient_von(d, modell)
            if d.get("stop_reason") != "pause_turn":
                break
            # Die Werkzeugschleife wurde angehalten, nicht beendet. Die
            # angehaltene Antwort geht unveraendert zurueck, dann laeuft
            # sie weiter.
            p = dict(p, messages=list(p["messages"])
                     + [{"role": "assistant",
                         "content": ohne_none(d.get("content") or [])}])
        else:
            print(f"    WARNUNG: Werkzeugschleife nach {self.PAUSEN_MAX} "
                  f"Fortsetzungen abgebrochen — die Antwort kann "
                  f"unvollstaendig sein.")

        if bedient != modell:
            print(f"    HINWEIS: {modell} hat abgelehnt, geantwortet hat "
                  f"{bedient}. Die Stelle steht in der Kostenuebersicht "
                  f"unter diesem Modell.")
        usage_buchen(rolle, bedient, usage)
        return (text if roh else saeubern(text)), \
            {"modell": bedient, "belege": gefunden,
             "suchen": usage.get("suchen", 0)}


# ==================================================================
# Stapelverarbeitung (Paket G)
# ==================================================================
# Die Stapel-API rechnet zum halben Preis und arbeitet asynchron. Der
# Preis dafuer ist nicht das Warten — die meisten Stapel sind in unter
# einer Stunde fertig —, sondern dass ein Chunk die Fassung des
# vorigen NICHT sehen kann, wenn beide im selben Stapel stehen. Deshalb
# laeuft der Buchlauf in Wellen ueber Ketten; siehe 'ketten' weiter unten.
#
# Was die Stapel-API nicht annimmt, steht hier und nicht verstreut:
STAPEL_VERBOTEN = ("stream", "fallbacks", "speed", "store",
                   "previous_thread_event_id", "cache_hint", "context_hint")


class StapelFehler(ApiFehler):
    """Der Stapel selbst ist gescheitert — nicht ein einzelner Eintrag."""


def stapel_payload(p):
    """Ein Messages-Payload, wie die Stapel-API es annimmt.

    Gebaut wird es weiter von 'payload()'. Hier faellt nur weg, was die
    Stapel-API mit einem Validierungsfehler ablehnt — allen voran
    'fallbacks': Der serverseitige Rueckfall ist auf diesem Weg nicht zu
    haben, ein Stapeleintrag damit kommt als Fehler zurueck.

    Zwei Payloadbauer waeren zwei Wahrheiten darueber, was rausgeht. Ein
    Filter ist keiner."""
    raus = {k: v for k, v in p.items() if k not in STAPEL_VERBOTEN}
    # Mindestens ein Token, sonst weist die API den Eintrag ab.
    raus["max_tokens"] = max(1, int(raus.get("max_tokens", 1)))
    return raus


def stapel_id_saeubern(roh):
    """custom_id nach der Regel des Anbieters: ^[a-zA-Z0-9_-]{1,64}$.

    Die Kennungen dieses Projekts sind Rolle und Chunknummer und damit
    ohnehin harmlos — gesaeubert wird trotzdem, weil ein abgelehnter
    Stapel erst nach dem Absenden auffaellt und dann alle Eintraege
    kostet, nicht nur den einen."""
    sauber = re.sub(r"[^A-Za-z0-9_-]", "-", str(roh))[:64]
    return sauber or "x"


class Stapel:
    """Ein Stapel bei der Anthropic-Messages-Batches-API.

    Drei Schritte, wie die API sie kennt: absenden, auf 'ended' warten,
    Ergebnisse zeilenweise lesen. Beide Transportwege wie ueberall — die
    SDK, wenn sie da ist, sonst 'requests'."""

    URL = "https://api.anthropic.com/v1/messages/batches"

    def __init__(self, cfg):
        self.cfg = cfg
        self.b = BACKENDS["anthropic"]
        self.klient = self.b.klient(cfg)

    def _kopf(self):
        return {"x-api-key": api_schluessel("anthropic"),
                "anthropic-version": self.b.VERSION,
                "content-type": "application/json"}

    def senden(self, anfragen):
        """anfragen: [(custom_id, payload)] -> Stapelkennung."""
        koerper = {"requests": [{"custom_id": stapel_id_saeubern(k),
                                "params": stapel_payload(p)}
                               for k, p in anfragen]}
        if self.klient is not None:
            try:
                return self.klient.messages.batches.create(
                    **koerper).model_dump()["id"]
            except Exception as e:
                raise sdk_fehler(anthropic_sdk(), e) from e
        r = sende(lambda: requests.post(self.URL, json=koerper,
                                        headers=self._kopf(),
                                        timeout=(self.cfg["timeout_connect"],
                                                 120)),
                  self.cfg["max_retries"])
        return r.json()["id"]

    def stand(self, kennung):
        """'in_progress' oder 'ended'."""
        if self.klient is not None:
            try:
                d = self.klient.messages.batches.retrieve(
                    kennung).model_dump()
            except Exception as e:
                raise sdk_fehler(anthropic_sdk(), e) from e
        else:
            r = sende(lambda: requests.get(f"{self.URL}/{kennung}",
                                           headers=self._kopf(),
                                           timeout=(
                                               self.cfg["timeout_connect"],
                                               60)),
                      self.cfg["max_retries"])
            d = r.json()
        return d.get("processing_status", ""), d.get("request_counts") or {}

    def ergebnisse(self, kennung):
        """Ergibt (custom_id, art, antwort) je Eintrag.

        'art' ist succeeded, errored, canceled oder expired. Nur bei
        'succeeded' ist 'antwort' eine Nachricht; die anderen drei kosten
        nichts und muessen wiederholt werden."""
        if self.klient is not None:
            try:
                for e in self.klient.messages.batches.results(kennung):
                    d = e.model_dump()
                    yield (d.get("custom_id", ""),
                           (d.get("result") or {}).get("type", ""),
                           (d.get("result") or {}).get("message") or {})
                return
            except Exception as e:
                raise sdk_fehler(anthropic_sdk(), e) from e
        r = sende(lambda: requests.get(f"{self.URL}/{kennung}",
                                       headers=self._kopf(),
                                       timeout=(self.cfg["timeout_connect"],
                                                60)),
                  self.cfg["max_retries"])
        url = r.json().get("results_url")
        if not url:
            raise StapelFehler(f"Stapel {kennung} hat keine Ergebnisdatei.")
        antwort = sende(lambda: requests.get(url, headers=self._kopf(),
                                             timeout=(
                                                 self.cfg["timeout_connect"],
                                                 600)),
                        self.cfg["max_retries"])
        for zeile in antwort.text.splitlines():
            if not zeile.strip():
                continue
            d = json.loads(zeile)
            yield (d.get("custom_id", ""),
                   (d.get("result") or {}).get("type", ""),
                   (d.get("result") or {}).get("message") or {})


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

    def chat_meta(self, cfg, system, user, rolle="begruendung", modell="",
                  roh=False, werkzeuge=None, schema=None):
        # 'schema' wird angenommen und NICHT gesendet: Gemini spricht einen
        # anderen Schema-Dialekt (OpenAPI-Subset, kein JSON Schema). Ein
        # durchgereichtes Schema waere hier ein HTTP 400. Der Parser traegt.
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
        # Kein Rueckfall, keine Belege, keine Suchen: Der Befund ist hier
        # leer, damit Aufrufer ihn nicht je Anbieter unterscheiden muessen.
        return text, {"modell": modell, "belege": [], "suchen": 0}


BACKENDS = {"anthropic": AnthropicBackend(), "google": GeminiBackend()}


def backend(modell):
    """Backend zum Modellnamen."""
    b = BACKENDS.get(backend_name(modell))
    if b is None:
        sys.exit(f"FEHLER: kein Backend fuer '{modell}'. "
                 f"Verfuegbar: {', '.join(BACKENDS)}")
    return b


def chat_voll(cfg, system, user, rolle="uebersetzung", roh=False,
              werkzeuge=None, schema=None):
    """Der einzige Modellaufruf des Projekts. Gibt (Text, Befund).

    Im Befund steht, was neben dem Text anfiel: das Modell, das wirklich
    geantwortet hat, die Belege der Websuche und die Zahl der Suchen. Wer
    davon nichts braucht, ruft 'chat' und bekommt nur den Text.

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
    if schema and not isinstance(b, AnthropicBackend):
        # Dieselbe Haltung wie bei den Werkzeugen: lieber ohne laufen als
        # mit einer Payload, die der Anbieter ablehnt. Gemini kennt einen
        # anderen Schema-Dialekt; dort traegt der Parser weiter.
        print(f"    HINWEIS: {modell} kennt keine strukturierte Ausgabe — "
              f"Antwort wird gelesen statt erzwungen")
        schema = None
    zusatz = {}
    if werkzeuge:
        zusatz["werkzeuge"] = werkzeuge
    if schema:
        zusatz["schema"] = schema
    return b.chat_meta(cfg, system, user, rolle=rolle, modell=modell, roh=roh,
                       **zusatz)


def chat(cfg, system, user, rolle="uebersetzung", roh=False, werkzeuge=None,
         schema=None):
    """Wie chat_voll, aber nur der Text. Der Normalfall."""
    return chat_voll(cfg, system, user, rolle=rolle, roh=roh,
                     werkzeuge=werkzeuge, schema=schema)[0]


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
    rollen.append("ebenen")           # vorbereitung.py, Erzaehlebenen
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


def schema_maengel(schema, pfad="$"):
    """Was der Anbieter an diesem Schema ablehnen wuerde, als Liste.

    Das unterstuetzte Subset ist enger, als es aussieht. Zwei Regeln
    kosten sonst einen ganzen Schritt, und zwar erst im Lauf:

    - Jedes Objekt braucht 'additionalProperties': false und 'required'.
    - Offene Abbildungen (beliebige Schluessel) lassen sich damit nicht
      ausdruecken. Genau daran scheitern die Vorbereitungslieferungen —
      Glossar, Personen, Kapitel sind Wort-zu-Wort-Abbildungen, und die
      haben keine feste Schluesselliste. Sie behalten deshalb den Parser
      und ihre Formpruefung.

    Ebenfalls nicht im Subset: rekursive Schemata sowie Zahl- und
    Laengengrenzen ('minimum', 'maxLength' …). Die werden hier gemeldet,
    nicht stillschweigend entfernt."""
    m = []
    if not isinstance(schema, dict):
        return [f"{pfad}: kein Objekt"]
    typ = schema.get("type")
    if typ == "object":
        if schema.get("additionalProperties") is not False:
            m.append(f"{pfad}: 'additionalProperties': false fehlt "
                     f"(offene Abbildungen sind nicht ausdrueckbar)")
        if "properties" not in schema:
            m.append(f"{pfad}: 'properties' fehlt")
        if "required" not in schema:
            m.append(f"{pfad}: 'required' fehlt")
        for name, teil in (schema.get("properties") or {}).items():
            m += schema_maengel(teil, f"{pfad}.{name}")
    elif typ == "array":
        if "items" not in schema:
            m.append(f"{pfad}: 'items' fehlt")
        else:
            m += schema_maengel(schema["items"], f"{pfad}[]")
    for verboten in ("minimum", "maximum", "multipleOf",
                     "minLength", "maxLength", "pattern"):
        if verboten in schema:
            m.append(f"{pfad}: '{verboten}' gehoert nicht zum Subset")
    if "$ref" in schema and "$defs" not in schema:
        m.append(f"{pfad}: '$ref' ohne '$defs' — rekursiv wird abgelehnt")
    return m


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
    """Absaetze eines Textes, an Leerzeilen getrennt.

    Zeilenenden werden zuerst vereinheitlicht. Das ist kein Luxus: Eine
    Datei aus Word oder von einem Windows-Rechner trennt ihre Absaetze mit
    '\\r\\n\\r\\n'. Ohne Normalisierung greift die Trennung dort nicht, und
    aus einem Buch von 56 000 Woertern werden zehn Absaetze — gemeldet als
    'Absaetze muessen durch Leerzeilen getrennt sein', obwohl genau das
    der Fall ist. Der Fehler traf das Buch Alexander im ersten Anlauf."""
    sauber = text.replace("\r\n", "\n").replace("\r", "\n")
    return [p.strip() for p in re.split(r"\n\s*\n", sauber) if p.strip()]


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


# Was eine Variante ausser 'chunk_words' verstellen darf. Bewusst eine
# Liste und kein "alles ausser 'name'": Ein Tippfehler im Variantennamen
# eines Schluessels wuerde sonst still eine Einstellung erfinden, und der
# Vergleich maesse etwas anderes als er behauptet.
VARIANTENSCHALTER = ({"chunk_words", "context_words", "context_words_voraus",
                      "rueckschau_quelle", "figuren_nachhall",
                      "revision_pass", "lektorat_passes", "tempus",
                      "diminutive",
                      # 'kette_max' gehoert dazu, weil die Frage »was
                      # kostet eine Naht ohne Rueckschau« nur am Text zu
                      # beantworten ist — nicht am Preisschild.
                      "kette_max"}
                     | {f"modell_{r}" for r in ROLLEN}
                     | {f"effort_{r}" for r in ROLLEN})


def variante_maengel(v):
    """Schluessel einer Variante, die nichts bewirken wuerden."""
    return [k for k in v if k != "name" and k not in VARIANTENSCHALTER]


def variante_anwenden(cfg, v):
    """Uebernimmt die Abweichungen der Variante in eine Kopie der Config.

    Bis Paket D trug eine Variante nur 'chunk_words' und Modellnamen.
    Damit liessen sich die Schalter aus Paket C — Vorwegschau,
    Rueckschauquelle, Figurennachhall — gar nicht vergleichen: Ein
    Schalter, den man nicht messen kann, ist eine Meinung.

    Gibt (config, chunk_words, beschreibung) zurueck."""
    cfg = dict(cfg)
    chunk_words = int(v.get("chunk_words", cfg["chunk_words"]))
    teile = [f"{chunk_words} Woerter/Chunk"]

    # 'modell_uebersetzung' zieht 'modell_revision' mit, wenn dieses nicht
    # eigens genannt ist: Ein Vergleich, der Pass 1 umstellt und Pass 2
    # beim alten Modell laesst, misst eine Mischung.
    modell = str(v.get("modell_uebersetzung", "")).strip()
    if modell and "modell_revision" not in v:
        cfg["modell_revision"] = modell

    for k, wert in v.items():
        if k == "name" or k == "chunk_words" or k not in VARIANTENSCHALTER:
            continue
        cfg[k] = wert
        if k != "modell_uebersetzung":
            teile.append(f"{k}={wert}")
    if modell:
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


def ebenen_lesen(pfad=None, still=True):
    """ebenen.json als Liste. Eigene Routine, weil lade_json Objekte liest.

    'lade_json' liefert bei allem, was kein JSON-Objekt ist, ein leeres
    Objekt zurueck — still. Diese Datei ist die einzige Referenzdatei mit
    einer LISTE an der Wurzel (die Reihenfolge ist die Information), und
    ueber lade_json gelesen waere sie immer leer. Kein Fehler, keine
    Meldung, nur keine Fugen. Deshalb hier und nicht dort: Eine Ausnahme
    in lade_json haette dieselbe Falle fuer die naechste Datei gestellt.

    Ein Objekt mit dem Schluessel 'ebenen' wird ebenfalls angenommen —
    so schreibt es niemand von Hand, aber ein Modell schon."""
    pfad = pfad or F["ebenen"]
    if not os.path.exists(pfad):
        return []
    try:
        d = json.load(open(pfad, encoding="utf-8"))
    except Exception:
        if not still:
            print(f"  WARNUNG: {pfad} nicht lesbar, wird ignoriert.")
        return []
    if isinstance(d, dict):
        d = d.get("ebenen", [])
    return d if isinstance(d, list) else []


def ebenen_anfaenge(paras, ebenen):
    """(Absatzindex, Ebenenname) je Eintrag aus ebenen.json.

    Ein Eintrag ist {'beginn': …, 'ebene': …}; 'beginn' sind die ersten
    Woerter des Absatzes IM WORTLAUT DER QUELLE — dieselbe Idee wie bei
    den Ueberschriften in kapitel.json. Absatznummern waeren kuerzer und
    waeren beim ersten korrigierten Absatz alle falsch.

    Ein Eintrag, dessen 'beginn' im Text nicht vorkommt, wird
    uebersprungen und gemeldet. Er still einzusortieren waere schlimmer
    als die Luecke: Die Fuge saesse dann am falschen Absatz."""
    raus, unbekannt, gesehen = [], [], set()
    for e in ebenen or []:
        if not isinstance(e, dict):
            continue
        anfang = str(e.get("beginn", "")).strip()
        name = str(e.get("ebene", "")).strip()
        if not anfang or not name:
            unbekannt.append(str(e)[:60])
            continue
        idx = next((i for i, p in enumerate(paras)
                    if i not in gesehen and p.strip().startswith(anfang)), None)
        if idx is None:
            unbekannt.append(anfang[:60])
            continue
        gesehen.add(idx)
        raus.append((idx, name))
    raus.sort()
    return raus, unbekannt


def ebenen_gruppen(paras, ebenen):
    """(Gruppen, Ebenennamen) aus ebenen.json — die zweite Quelle.

    Der 'rahmen_marker' setzt voraus, dass der Autor die Wechsel markiert
    hat. Beim Buch 1919 tat er das nicht: Das Stilprofil beschreibt fuenf
    Erzaehlebenen mit drei Tempora, der Marker fand ueber 147 Chunks
    genau eine Gruppe — die deutsche Rueckschau lief also ueber jeden
    Ebenenwechsel hinweg. Das ist der Fehler, gegen den diese Datei
    steht: Sie benennt die Wechsel, auch wenn der Text sie nicht
    auszeichnet."""
    anfaenge, _ = ebenen_anfaenge(paras, ebenen)
    if not anfaenge:
        return [list(paras)], [""]
    # Ein Buch beginnt selten bei Absatz 0 mit dem ersten Eintrag; was
    # davor steht, ist eine eigene, unbenannte Gruppe.
    grenzen = [i for i, _ in anfaenge]
    namen = [n for _, n in anfaenge]
    if grenzen[0] > 0:
        grenzen.insert(0, 0)
        namen.insert(0, "")
    gruppen = []
    for k, start in enumerate(grenzen):
        ende = grenzen[k + 1] if k + 1 < len(grenzen) else len(paras)
        gruppen.append(list(paras[start:ende]))
    return gruppen, namen


def ebenen_maengel(ebenen, perspektive):
    """Was an ebenen.json nicht stimmt, als Liste von Zeilen.

    Die Namen muessen die aus stilprofil.json sein. Zwei Schreibweisen
    derselben Ebene sehen im Bericht wie zwei Ebenen aus, und der
    Ebenenblock im User-Prompt findet die Beschreibung dann nicht."""
    m = []
    if not isinstance(ebenen, list):
        return ["ebenen.json ist keine Liste von Eintraegen"]
    bekannt = list(perspektive) if isinstance(perspektive, dict) else []
    for nr, e in enumerate(ebenen, 1):
        if not isinstance(e, dict):
            m.append(f"Eintrag {nr}: kein Objekt")
            continue
        if not str(e.get("beginn", "")).strip():
            m.append(f"Eintrag {nr}: 'beginn' fehlt")
        if not str(e.get("ebene", "")).strip():
            m.append(f"Eintrag {nr}: 'ebene' fehlt")
        elif bekannt and e["ebene"] not in bekannt:
            m.append(f"Eintrag {nr}: Ebene '{e['ebene']}' steht nicht in "
                     f"stilprofil.json ({', '.join(bekannt)})")
    return m


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


def zitat_absaetze(zitate):
    """Die Absaetze, die ausgeklammert werden — Zitat UND Attribution (F3)."""
    raus = {}
    for z in zitate:
        raus[z["index"]] = z
        if "index_attribution" in z:
            raus[z["index_attribution"]] = None      # nur entfernen
    return raus


def ebenengruppen(cfg, paras, drucken=print):
    """(Gruppen, Ebenennamen) — zwei Quellen, ebenen.json hat Vorrang.

    Der 'rahmen_marker' setzt voraus, dass der Autor die Ebenenwechsel
    ausgezeichnet hat. Beim Buch 1919 tat er das nicht: fuenf Ebenen im
    Stilprofil, eine Gruppe ueber 147 Chunks. Die deutsche Rueckschau
    lief damit ueber jeden Wechsel hinweg, und die buchweite Perfektquote
    in qa.py konnte das gar nicht sehen.

    Deshalb liest dieser Schritt zuerst ebenen.json. Ist sie da, benennt
    sie die Gruppen; sonst gilt weiter der Marker. Beides gleichzeitig
    waere eine Quelle zu viel — der Marker bleibt der Rueckfall, nicht
    die zweite Meinung.

    Die Funktion steht in gemeinsam und nicht in uebersetzung, weil drei
    Schritte dieselbe Gruppierung brauchen: der Lauf, die Leseausgabe und
    das Screening. Zwei Wege dorthin heissen fremde Absaetze
    nebeneinander — und das sieht niemand, weil beide Spalten fuer sich
    plausibel aussehen."""
    ebenen = ebenen_lesen()
    if ebenen:
        anfaenge, unbekannt = ebenen_anfaenge(paras, ebenen)
        for a in unbekannt:
            drucken(f"    WARNUNG: ebenen.json — »{a}« kommt so nicht im "
                    f"Text vor, Eintrag übersprungen")
        if anfaenge:
            gruppen, namen = ebenen_gruppen(paras, ebenen)
            benannt = sorted({n for n in namen if n})
            drucken(f"Erzählebenen:       {len(gruppen)} Abschnitte aus "
                    f"{F['ebenen']} ({len(benannt)} Ebenen: "
                    f"{', '.join(benannt)})")
            return gruppen, namen
        drucken(f"    WARNUNG: ebenen.json — kein Eintrag passt auf den "
                f"Text, es gilt der Marker »{cfg['rahmen_marker']}«")

    gruppen = rahmen_gruppen(paras, cfg["rahmen_marker"])
    if len(gruppen) > 1:
        drucken(f"Rahmenwechsel:      {len(gruppen)-1} an Marker "
                f"»{cfg['rahmen_marker']}«")
    else:
        # Eine Gruppe ueber das ganze Buch heisst: Die Rueckschau laeuft
        # ueber jeden Ebenenwechsel. Wenn das Stilprofil mehrere Ebenen
        # kennt, ist das fast sicher falsch — und es faellt sonst
        # nirgends auf.
        p = lade_json(F["stilprofil"], still=True).get("perspektive")
        if isinstance(p, dict) and len(p) > 1:
            drucken(f"\nACHTUNG: {len(p)} Erzählebenen im Stilprofil, aber "
                    f"keine einzige Fuge im Text.")
            drucken(f"         Der Marker »{cfg['rahmen_marker']}« kommt "
                    f"nicht vor, {F['ebenen']} fehlt oder ist leer.")
            drucken(f"         Die deutsche Rückschau läuft damit über jeden "
                    f"Ebenenwechsel hinweg —")
            drucken(f"         Tempus und Person der einen Ebene bluten in "
                    f"die andere.")
            drucken("         Abhilfe: python3 vorbereitung.py "
                    "--nur ebenen\n")
    return gruppen, None


def quellchunks(cfg, paras_alle, zitate, chunk_words, drucken=print):
    """Die Chunkbildung des Laufs, an einer Stelle.

    Gibt (marken, chunks, fugen, ebenen_je_chunk). Wer Quelle und Fassung
    nebeneinanderstellt — Leseausgabe, Screening —, muss dieselben Chunks
    bekommen wie der Lauf. Vorher stand die Bildung dreimal im Code, und
    die drei Fassungen sind auseinandergelaufen: Der Lauf las seit August
    2026 ebenen.json, die beiden Leser weiter nur den Rahmenmarker. Damit
    verglich das Screening niederländischen Chunk 40 gegen deutschen
    Chunk 43 und meldete Auslassungen, die keine waren."""
    marken = zitat_absaetze(zitate)
    rest = [p for i, p in enumerate(paras_alle) if i not in marken]
    gruppen, namen = ebenengruppen(cfg, rest, drucken)
    perspektive = lade_json(F["stilprofil"], still=True).get("perspektive")
    if namen is not None:
        ebenen = namen                       # aus ebenen.json benannt
    else:
        ebenen = ebenen_folge(gruppen, cfg["rahmen_marker"], perspektive)
    chunks, fugen, je_chunk = [], set(), []
    for gruppe, ebene in zip(gruppen, ebenen):
        teil = chunks_bauen(gruppe, chunk_words)
        if chunks:
            fugen.add(len(chunks))
        chunks.extend(teil)
        je_chunk.extend([ebene] * len(teil))
    return marken, chunks, fugen, je_chunk


def ketten(n, fugen, kette_max):
    """Die Chunks in Ketten, die nebeneinander laufen koennen.

    Der Buchlauf ist seriell, und zwar aus einem Grund: Jeder Chunk sieht
    die deutsche Fassung des vorigen. Ein Stapel kann das nicht — die
    Eintraege werden gleichzeitig verarbeitet. Wer den ganzen Text in
    einen Stapel legt, spart die Haelfte und wirft die Rueckschau weg;
    das ist kein Handel, das ist ein anderes Verfahren.

    Deshalb Ketten: Innerhalb einer Kette bleibt es seriell, die Ketten
    laufen nebeneinander. Je Welle geht der naechste Chunk jeder Kette in
    denselben Stapel.

    Geschnitten wird zuerst an den Ebenenfugen. Dort setzt die Rueckschau
    ohnehin zurueck — diese Schnitte kosten nichts. Erst wenn ein
    Abschnitt laenger als 'kette_max' ist, wird zusaetzlich getrennt, und
    jeder dieser Schnitte ist eine Naht ohne Rueckschau. Genau die misst
    'bewertung.py --fugen'.

    kette_max <= 0 heisst: nur an den Ebenenfugen trennen."""
    grenzen = sorted({0, n} | {f for f in fugen if 0 < f < n})
    raus = []
    for a, e in zip(grenzen, grenzen[1:]):
        laenge = e - a
        if kette_max and kette_max > 0 and laenge > kette_max:
            # Gleichmaessig aufteilen statt 'kette_max, kette_max, Rest':
            # Eine Kette mit drei Chunks am Ende bestimmt die Zahl der
            # Wellen genauso wie eine mit dreissig, und die kurze steht
            # die meiste Zeit still.
            teile = -(-laenge // kette_max)
            schritt = -(-laenge // teile)
            for s in range(a, e, schritt):
                raus.append(list(range(s, min(s + schritt, e))))
        else:
            raus.append(list(range(a, e)))
    return raus


def wellen(kettenliste):
    """Je Welle ein Chunk aus jeder Kette, die noch einen hat.

    Die Welle ist der Stapel: Ihre Eintraege haengen nicht voneinander ab,
    weil sie aus verschiedenen Ketten kommen."""
    tiefe = max((len(k) for k in kettenliste), default=0)
    return [[k[i] for k in kettenliste if i < len(k)] for i in range(tiefe)]


def zusatzfugen(kettenliste, fugen):
    """Kettenanfaenge, die keine Ebenenfuge sind — die bezahlten Nähte.

    Der Anfang der ersten Kette zaehlt nicht: Dort faengt das Buch an."""
    return sorted({k[0] for k in kettenliste if k and k[0] > 0}
                  - set(fugen))


class ChunksWeichenAb(Exception):
    """Die nachgebauten Quellchunks passen nicht zum Lauf.

    Kein Warnfall: Ab hier stuende in jedem Vergleich der falsche Absatz
    neben dem falschen, und zwar unauffaellig. Lieber abbrechen."""


def quellchunks_wie_lauf(cfg, praefix="", drucken=print):
    """Die Quellchunks des abgeschlossenen Laufs, nachgebaut und geprueft.

    'chunk_words' kommt aus dem Zustand des Laufs, nicht aus der aktuellen
    Konfiguration: Wer die Chunkgroesse nach dem Lauf verstellt, bekaeme
    sonst eine andere Einteilung als die, die uebersetzt wurde.

    Die Zahl wird gegen 'total' geprueft. Diese Pruefung ist der eigentliche
    Zweck der Funktion — eine abweichende Einteilung faellt sonst nirgends
    auf, weil Quelle und Fassung jede fuer sich plausibel aussehen."""
    st = lade_json(praefix + "uebersetzung_state.json", still=True)
    total = int(st.get("total") or 0)
    chunk_words = int(st.get("chunk_words") or cfg["chunk_words"])
    paras = absaetze(open(F["quelle"], encoding="utf-8").read())
    zitate = lade_json(F["zitate"], still=True).get("epigraphen", [])
    marken, chunks, fugen, ebenen = quellchunks(cfg, paras, zitate,
                                                chunk_words, drucken)
    if total and len(chunks) != total:
        raise ChunksWeichenAb(
            f"{len(chunks)} nachgebaute Quellchunks, aber der Lauf hatte "
            f"{total}.\n  Quelle, ebenen.json oder zitate.json haben sich "
            f"seit dem Lauf geaendert.\n  Ein Vergleich stellte ab hier "
            f"fremde Absaetze nebeneinander.")
    return marken, chunks, fugen, ebenen


def schlusswoerter(text, n):
    w = text.split()
    if len(w) <= n:
        return text.strip()
    s = " ".join(w[-n:])
    m = re.search(r'(?<=[.!?\u2026])' + SCHLIESSER + r'\s+', s)
    return (s[m.end():] if m else s).strip()


def anfangswoerter(text, n):
    """Die ersten n Woerter, an einer Satzgrenze abgeschnitten.

    Gegenstueck zu 'schlusswoerter'. Der Schnitt an der Satzgrenze ist
    hier wichtiger als dort: Ein mitten im Satz endender Ausblick liest
    sich wie ein abgebrochener Auftrag, und das Modell neigt dann dazu,
    ihn zu Ende zu uebersetzen — genau das, was der Ausblick nicht will.

    Bleibt nach dem Schnitt nichts uebrig (ein einziger langer Satz),
    wird der ungeschnittene Anfang genommen: lieber ein Satzfragment als
    gar kein Ausblick."""
    if n <= 0:
        return ""
    w = text.split()
    if len(w) <= n:
        return text.strip()
    s = " ".join(w[:n])
    treffer = list(re.finditer(r'[.!?…]' + SCHLIESSER + r'(?=\s|$)', s))
    return (s[:treffer[-1].end()] if treffer else s).strip()


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
