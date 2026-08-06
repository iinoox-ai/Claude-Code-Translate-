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
# Der Code liegt im Colab-Betrieb NICHT im Arbeitsverzeichnis. Wer hier
# eine Quelldatei relativ oeffnet, bekommt dort einen FileNotFoundError —
# und der Selbsttest meldet 'nicht pruefbar' statt zu pruefen. Genau das
# ist der Judge-Pruefung passiert.
CODE = os.path.dirname(os.path.abspath(__file__))


def _glob_py():
    """Alle Projektskripte im CODE-Verzeichnis."""
    import glob
    return glob.glob(os.path.join(CODE, "*.py"))


def _glob_md():
    """Alle Dokumente im CODE-Verzeichnis, mit Pfad."""
    import glob
    return sorted(glob.glob(os.path.join(CODE, "*.md")))


def quelltext(name):
    """Eine Datei aus dem CODE-Verzeichnis, nie relativ zum Arbeitsordner."""
    return open(os.path.join(CODE, name), encoding="utf-8").read()

def selbsttest(cfg, b):
    import inspect
    b.abschnitt("Selbsttest")
    import lektorat as L
    import uebersetzung as U
    import qa as Q

    probe = ('Hij zei -- eigenlijk fluisterde hij -- dat het "goed" was... '
             'Die Masse der Menschen. Die Busse fuhren nicht. Ein Ass im '
             'Ärmel. Strasse, gross, draussen. Ein Test\u2014mit Strich. '
             'Meine Eltern sind ... nicht die Sorte , sagte er ; leise.')
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
        # Das Spatium vor … traegt Bedeutung (ausgelassenes Wort gegen
        # abgebrochenes) und darf nicht wegnormalisiert werden; vor Komma
        # und Semikolon muss es weiterhin fallen.
        if "sind … nicht" not in neu:
            b.add("FEHLER", "Spatium vor … wird getilgt",
                  "Auslassungspunkte fuer ein ganzes Wort behalten es. "
                  "Diese Regel hat im Testlektorat eine Anweisung "
                  "ueberstimmt.")
        elif "Sorte, sagte er; leise" not in neu:
            b.add("FEHLER", "Spatium vor Komma oder Semikolon bleibt stehen")
        else:
            b.add("OK", "Spatien: vor … erhalten, vor Komma und "
                        "Semikolon getilgt")
        # Absatztrennung unabhaengig vom Zeilenende. Eine Datei aus Word
        # trennt mit '\r\n\r\n'; ohne Normalisierung wurden aus dem Buch
        # Alexander (56 000 Woerter) zehn Absaetze — gemeldet als
        # 'Absaetze muessen durch Leerzeilen getrennt sein', obwohl genau
        # das der Fall war.
        drei = ["Eerste alinea met woorden.", "Tweede alinea, ook met.",
                "Derde alinea tenslotte."]
        for name, ende in (("Unix", "\n\n"), ("Windows", "\r\n\r\n"),
                           ("alter Mac", "\r\r")):
            if G.absaetze(ende.join(drei)) != drei:
                b.add("FEHLER", f"Absatztrennung scheitert an "
                                f"{name}-Zeilenenden",
                      f"{len(G.absaetze(ende.join(drei)))} statt 3 Absaetze")
                break
        else:
            b.add("OK", "Absatztrennung unabhaengig vom Zeilenende "
                        "(Unix, Windows, alter Mac)")

        b.add("OK", f"Normalisierer laeuft ({sum(zaehler.values())} "
                    f"Aenderungen auf der Probe)")
    except Exception as e:
        b.add("FEHLER", "Normalisierer wirft Ausnahme", repr(e))

    try:
        # Die zweite Zeile stammt aus dem Testauszug 1919: dort waren vier
        # der neun gemeldeten Treffer Falschmeldungen auf -chen.
        n, treffer = G.diminutive_zaehlen(
            "Sie wollte sprechen, aber zwischen ihnen lag ein Zeichen. "
            "Ein Häuschen, ein Mädchen, ein Fräulein. "
            "Die Menschen der Deutschen hörten das Rauschen und das "
            "Krachen, drüben bei den Griechen in München.")
        if n != 3:
            b.add("FEHLER", f"Diminutivzaehler liefert {n} statt 3",
                  f"Treffer: {treffer}")
        else:
            b.add("OK", "Diminutivzaehler korrekt (3 von 3, sieben "
                        "Falschmeldungen auf -chen abgewiesen)")
    except Exception as e:
        b.add("FEHLER", "Diminutivzaehler wirft Ausnahme", repr(e))

    # --- Paket 4: Stilprofil im Prompt, Kapitelzeile, Ueberschreibschutz
    # Abnahmekriterien des Auftrags, alle ohne Modell pruefbar.
    try:
        import vorbereitung as V
        fehler = []

        stil = {"ton": "lakonisch, parataktisch",
                "register": "Umgangssprache in der Rede",
                "satzlaenge": "kurz, selten Hypotaxe",
                "tempus": "quellnaher Wechsel",
                "perspektive": {"Rahmen 1919": "erste Person Präsens",
                                "Rückblende": "erste Person Präteritum"}}
        block = U.block_stilprofil(stil)
        for stueck in ("lakonisch", "kurz, selten Hypotaxe",
                       "Rahmen 1919", "erste Person Präteritum"):
            if stueck not in block:
                fehler.append(f"Stilprofil: '{stueck}' fehlt im Baustein")
        if U.block_stilprofil({}) or U.block_stilprofil({"ton": "  "}):
            fehler.append("leeres Stilprofil erzeugt trotzdem einen Baustein")

        # Der Baustein muss im gebauten System-Prompt landen, nicht nur
        # als Funktion existieren.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            alt = os.getcwd()
            try:
                os.chdir(tmp)
                json.dump(stil, open(G.F["stilprofil"], "w"))
                p_ueb, p_rev = U.prompts(cfg)
                if "lakonisch, parataktisch" not in p_ueb:
                    fehler.append("Stilprofil erscheint nicht im "
                                  "System-Prompt der Uebersetzung")
                if "lakonisch, parataktisch" not in p_rev:
                    fehler.append("Stilprofil fehlt im Revisions-Prompt")

                # Ueberschreibschutz: gefuellte Datei bleibt, Vorschlag
                # geht auf .neu.
                json.dump({"a": "b"}, open(G.F["glossar"], "w"))
                ziel, ausweich = V.zieldatei(G.F["glossar"])
                if not ausweich or not ziel.endswith(".neu"):
                    fehler.append("gefuellte Datei wuerde ueberschrieben")
                json.dump({}, open(G.F["kapitel"], "w"))
                ziel, ausweich = V.zieldatei(G.F["kapitel"])
                if ausweich:
                    fehler.append("leere Datei wird unnoetig ausgewichen")
            finally:
                os.chdir(alt)

        # Kapitelzuordnung: das laufende Kapitel wirkt fort.
        kapitel = {"23 augustus 1919": "Ankunft in Ypern",
                   "24 augustus 1919": "Besuch am Grab"}
        chunks = [("Vorspann ohne Datum.", False),
                  ("23 augustus 1919\n\nWir kamen an.", False),
                  ("Der Tag ging weiter.", False),
                  ("24 augustus 1919\n\nAm Grab.", False)]
        zuordnung = U.kapitel_zuordnen(chunks, kapitel)
        if zuordnung != ["", "23 augustus 1919", "23 augustus 1919",
                         "24 augustus 1919"]:
            fehler.append(f"Kapitelzuordnung falsch: {zuordnung}")
        if "Ankunft in Ypern" not in U.block_kapitel(zuordnung[2], kapitel):
            fehler.append("Kapitelzeile erscheint nicht im User-Prompt")
        if U.block_kapitel("", kapitel):
            fehler.append("Kapitelblock ohne Ueberschrift ist nicht leer")

        # Paket 5: Marker-Zeilen erzwingen Chunkgrenzen genau dort.
        paras = ["Vorspann.", "# Krieg", "Im Graben.", "Noch im Graben.",
                 "#", "Wieder 1919."]
        gruppen = G.rahmen_gruppen(paras, "#")
        if [len(g) for g in gruppen] != [1, 3, 2]:
            fehler.append(f"Rahmenmarker teilt falsch: "
                          f"{[len(g) for g in gruppen]}")
        if gruppen[1][0] != "# Krieg":
            fehler.append("Markerzeile beginnt die neue Gruppe nicht")
        if len(G.rahmen_gruppen(paras, "")) != 1:
            fehler.append("leerer Marker teilt trotzdem")

        perspektive = {"Rahmen 1919": "erste Person Präsens",
                       "Krieg": "erste Person Präteritum"}
        folge = G.ebenen_folge(gruppen, "#", perspektive)
        if folge != ["Rahmen 1919", "Krieg", "Rahmen 1919"]:
            fehler.append(f"Ebenenfolge falsch: {folge}")
        nackt = G.ebenen_folge(G.rahmen_gruppen(["a", "#", "b", "#", "c"],
                                                "#"), "#", perspektive)
        if nackt != ["Rahmen 1919", "Krieg", "Rahmen 1919"]:
            fehler.append(f"nackte Marker wechseln nicht: {nackt}")
        if any(G.ebenen_folge(gruppen, "#", dict(perspektive, Dritte="x"))
               [i] for i in (0, 2)):
            fehler.append("bei drei Ebenen wird geraten statt geschwiegen")
        if "erste Person Präteritum" not in U.block_ebene("Krieg",
                                                          perspektive):
            fehler.append("Erzählebene erscheint nicht im User-Prompt")
        if U.block_ebene("", perspektive) or U.block_ebene("Krieg", {}):
            fehler.append("Ebenenblock ohne Angabe ist nicht leer")

        # Paket 5: Varianten aus der Konfiguration, Schritte daraus.
        import pipeline as PL
        probe = dict(cfg, chunk_words=800, varianten=[
            {"name": "B", "chunk_words": 1600},
            {"name": "C", "chunk_words": 800,
             "modell_uebersetzung": "claude-fable-5"}])
        namen = [v["name"] for v in G.varianten(probe)]
        if namen != ["B", "C"]:
            fehler.append(f"Varianten falsch gelesen: {namen}")
        _, cw, besch = G.variante_anwenden(probe, probe["varianten"][0])
        if cw != 1600 or "1600" not in besch:
            fehler.append(f"Chunkgroesse der Variante greift nicht: {besch}")
        c2, cw2, besch2 = G.variante_anwenden(probe, probe["varianten"][1])
        if c2["modell_uebersetzung"] != "claude-fable-5" \
           or c2["modell_revision"] != "claude-fable-5":
            fehler.append("Modellwechsel der Variante greift nicht")
        if "claude-fable-5" not in besch2:
            fehler.append("Modell fehlt in der Variantenbeschreibung")
        # Rueckfall auf die alte B-Variante, wenn 'varianten' leer ist.
        alt = G.varianten(dict(probe, varianten=[], chunk_words_variante=1200))
        if [v["name"] for v in alt] != ["B"] or alt[0]["chunk_words"] != 1200:
            fehler.append(f"Rueckfall auf chunk_words_variante fehlt: {alt}")
        if G.varianten(dict(probe, varianten=[], chunk_words_variante=800)):
            fehler.append("identische Variante wird nicht verworfen")

        # Paket D: Eine Variante darf jeden Schalter tragen, nicht nur
        # Chunkgroesse und Modell. Sonst laesst sich kein Schalter aus
        # Paket C vergleichen — und ein Schalter ohne Messung ist eine
        # Meinung.
        c3, _, besch3 = G.variante_anwenden(
            probe, {"name": "D", "rueckschau_quelle": "entwurf",
                    "context_words_voraus": 0, "figuren_nachhall": 0,
                    "effort_uebersetzung": "maximal", "revision_pass": False})
        for k, soll in (("rueckschau_quelle", "entwurf"),
                        ("context_words_voraus", 0),
                        ("figuren_nachhall", 0),
                        ("effort_uebersetzung", "maximal"),
                        ("revision_pass", False)):
            if c3[k] != soll:
                fehler.append(f"Variante setzt {k} nicht ({c3[k]!r})")
        if "rueckschau_quelle=entwurf" not in besch3:
            fehler.append(f"Schalter fehlt in der Beschreibung: {besch3}")
        # Ein Tippfehler im Schluessel darf NICHT still eine Einstellung
        # erfinden — der Vergleich maesse sonst etwas anderes, als er sagt.
        c4, _, _ = G.variante_anwenden(probe, {"name": "E",
                                               "rueckschau_qelle": "entwurf"})
        if "rueckschau_qelle" in c4:
            fehler.append("unbekannter Variantenschluessel wird uebernommen")
        if G.variante_maengel({"name": "E", "rueckschau_qelle": "x"}) != \
                ["rueckschau_qelle"]:
            fehler.append("Tippfehler im Variantenschluessel wird nicht "
                          "gemeldet")
        if G.variante_maengel({"name": "B", "chunk_words": 1600}):
            fehler.append("gueltige Variante wird beanstandet")

        # Ein Buch darf ein anderes Modell waehlen, ohne dass der
        # Technik-Abgleich es beim naechsten Lauf still zuruecksetzt.
        pj = {"modell_uebersetzung": "claude-sonnet-5",
              "modell_stil": "veraltet",
              "technik_ausnahmen": ["modell_uebersetzung"]}
        rp = {"modell_uebersetzung": "claude-opus-5",
              "modell_stil": "claude-opus-5"}
        ueberschrieben = [k for k, _, _ in G.technik_abweichung(pj, rp)]
        if "modell_uebersetzung" in ueberschrieben:
            fehler.append("technik setzt die Modellwahl des Buchs zurueck")
        if "modell_stil" not in ueberschrieben:
            fehler.append("technik zieht veraltete Schluessel nicht mehr nach")
        if not G.technik_beansprucht(pj, rp):
            fehler.append("beanspruchte Schluessel werden nicht gemeldet")

        # Ohne Terminal darf die Rueckfrage nicht mit einem Traceback
        # enden — und erst recht nicht stillschweigend loeschen.
        class _Args:
            ja = False
            nur_test = True
            nur_teile = False

        def _eof(_):
            raise EOFError

        if PL.bestaetigung(_Args(), _eof) is not None:
            fehler.append("fehlende Eingabe wird nicht als solche erkannt")
        if PL.bestaetigung(_Args(), lambda _: "nein") is not False:
            fehler.append("'nein' loescht trotzdem")
        if PL.bestaetigung(_Args(), lambda _: " JA ") is not True:
            fehler.append("getipptes 'ja' wird nicht angenommen")
        _mit = _Args()
        _mit.ja = True
        if PL.bestaetigung(_mit, _eof) is not True:
            fehler.append("--ja wirkt nicht ohne Terminal")

        # --nur-test darf die Chunks des Volllaufs nicht anfassen: Sonst
        # kann annotation.py hinterher keine Chunkpaare mehr bilden und
        # qa.py meldet den Lauf als unvollstaendig.
        voll = {"teile", "uebersetzung_state.json", "lektorat_state.json"}
        drin = [x for x in PL.WEG_TEST if x in voll]
        if drin:
            fehler.append(f"--nur-test loescht den Volllauf mit: {drin}")
        if not any(x.startswith("testB/") for x in PL.WEG_TEST):
            fehler.append("--nur-test raeumt die Variantenordner nicht")
        if not voll <= set(PL.WEG_TEILE):
            fehler.append("--nur-teile raeumt den Volllauf nicht mehr")

        schritte = [s[0] for s in PL.schritte_mit_varianten(
            PL.SCHRITTE_ROH if hasattr(PL, "SCHRITTE_ROH") else
            [("VARIANTEN", None, None, 0)], probe)]
        if "testB" not in schritte or "testC" not in schritte:
            fehler.append(f"Variantenschritte fehlen: {schritte}")

        # Jede Lieferung muss eine Formpruefung haben, die die Form des
        # Lesers meint — sonst schreibt die Vorbereitung Dateien, die
        # spaeter stillschweigend uebersprungen werden.
        for name, datei, auftrag, pruef in V.LIEFERUNGEN:
            if datei not in G.F.values():
                fehler.append(f"{name}: Zieldatei {datei} unbekannt")
            if pruef({}) and name in ("personen", "stilprofil"):
                fehler.append(f"{name}: leere Lieferung gilt als gueltig")
        if not V.LIEFERUNGEN[0][3]({"a": "b"}):
            fehler.append("Glossarpruefung weist gueltige Form ab")
        if V.LIEFERUNGEN[3][3]({"x": {"figuren": []}}):
            fehler.append("Anredepruefung laesst fehlendes 'deutsch' durch")

        if fehler:
            b.add("FEHLER", "Vorbereitung/Prompt-Einspeisung fehlerhaft",
                  "; ".join(fehler))
        else:
            b.add("OK", "Stilprofil steht im Prompt, Kapitelzeile wirkt "
                        "fort, gefuellte Dateien bleiben unangetastet")
    except Exception as e:
        b.add("FEHLER", "Paket 4 nicht pruefbar", repr(e))

    # --- Alle Backends muessen dieselbe chat()-Signatur haben ----------
    # Gemini fehlte 'roh'. Gemerkt hat es niemand, weil der Selbsttest die
    # Payloads prueft und nicht den Aufruf — und weil die betroffene Rolle
    # (annotation) erst am Ende der Kette ruft. 61 Aufrufe, jeder mit
    # demselben TypeError, eine leere Ergebnisdatei und die Meldung
    # 'fertig'.
    try:
        import inspect
        fehler = []
        # Geprueft wird 'chat_meta': Das ist die Methode, die jedes Backend
        # selbst schreibt. 'chat' erbt jeder von der Basisklasse und ist
        # deshalb trivial gleich — sie zu pruefen hiesse, nichts zu pruefen.
        soll = set(inspect.signature(G.Backend.chat_meta).parameters)
        for name, backend in sorted(G.BACKENDS.items()):
            ist = set(inspect.signature(type(backend).chat_meta).parameters)
            fehlt = soll - ist
            if fehlt:
                fehler.append(f"{name}: {', '.join(sorted(fehlt))} fehlt")
            # Der Befund neben dem Text ist Teil des Vertrags: Wer nur den
            # Text zurueckgibt, laesst 'chat_voll' beim Auspacken auflaufen.
            if not isinstance(type(backend).chat_meta.__doc__ or "", str):
                fehler.append(f"{name}: chat_meta ohne Beschreibung")
        # 'roh' und 'rolle' muessen ueberall ankommen — chat() reicht sie
        # ungeprueft durch.
        for pflicht in ("roh", "rolle", "modell"):
            if pflicht not in soll:
                fehler.append(f"Basisklasse kennt '{pflicht}' nicht")
        if fehler:
            b.add("FEHLER", "Backends haben verschiedene Signaturen",
                  "; ".join(fehler))
        else:
            b.add("OK", f"Alle {len(G.BACKENDS)} Backends nehmen dieselben "
                        f"Argumente entgegen")
    except Exception as e:
        b.add("FEHLER", "Backend-Signaturen nicht pruefbar", repr(e))

    # --- Tarife: nur Eindeutiges wird uebernommen ----------------------
    # Ein falsch ausgelesener Preis verzerrt jeden Kostenbericht, ohne
    # dass es auffaellt. Deshalb wird geraten nur, wo nichts zu raten ist.
    try:
        import tarife as T
        fehler = []
        faelle = [
            ([5.0, 25.0], {"ein": 5.0, "aus": 25.0}, "bestaetigt"),
            ([3.0, 15.0], {"ein": 5.0, "aus": 25.0}, "abweichend"),
            ([1.0, 5.0, 25.0], {"ein": 5.0, "aus": 25.0}, "unklar"),
            ([25.0, 5.0][:1], {"ein": 5.0, "aus": 25.0}, "unklar"),
            ([25.0, 25.0][:1], None, "unklar"),
            (None, {"ein": 5.0, "aus": 25.0}, "fehlt"),
        ]
        for gefunden, hinterlegt, soll in faelle:
            ist = T.urteil(gefunden, hinterlegt)[0]
            if ist != soll:
                fehler.append(f"urteil({gefunden}) -> {ist} statt {soll}")
        # Eingabe teurer als Ausgabe gibt es nicht — das waere ein
        # vertauschtes Paar, und vertauscht ist schlimmer als unbekannt.
        if T.urteil([25.0, 5.0], None)[0] != "unklar":
            fehler.append("vertauschtes Preispaar wird uebernommen")

        text = ("Model claude-opus-5 Input $5.00 per million tokens "
                "Output $25.00 per million tokens")
        if T.preise_finden(text, "claude-opus-5") != [5.0, 25.0]:
            fehler.append(f"Preise nicht gefunden: "
                          f"{T.preise_finden(text, 'claude-opus-5')}")
        if T.preise_finden(text, "claude-sonnet-5") is not None:
            fehler.append("unbekanntes Modell liefert trotzdem Preise")

        if fehler:
            b.add("FEHLER", "Tarifabgleich fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Tarife: nur eindeutige Preispaare werden "
                        "uebernommen, alles andere bleibt hinterlegt")
    except Exception as e:
        b.add("FEHLER", "Tarifabgleich nicht pruefbar", repr(e))

    # --- Kostenbuchung: je Lauf, Rolle UND Modell ---------------------
    # Der teuerste Fehler der Buchhaltung: Ein Testlauf mit einem anderen
    # Modell hat die ganze Rolle auf dieses Modell umetikettiert und die
    # Buchkosten dadurch um 57 % zu hoch ausgewiesen (109,5 statt 69,7 $).
    try:
        import tempfile
        fehler = []
        alt_cwd, alt_lauf = os.getcwd(), G.lauf_name()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                G.lauf_setzen("")
                G.usage_buchen("uebersetzung", "claude-opus-5",
                               {"ein": 100, "aus": 200, "cache_lesen": 300,
                                "cache_schreiben": 40})
                G.lauf_setzen("testB/")
                G.usage_buchen("uebersetzung", "claude-fable-5",
                               {"ein": 10, "aus": 20})
                m = json.load(open(G.MANIFEST, encoding="utf-8"))
            finally:
                os.chdir(alt_cwd)
                G.lauf_setzen(alt_lauf)

        posten = G.kosten_posten(m)
        if len(posten) != 2:
            fehler.append(f"{len(posten)} Buchungen statt 2 — der Testlauf "
                          f"hat die Buchproduktion ueberschrieben")
        else:
            (l1, r1, mo1, e1), (l2, r2, mo2, e2) = posten
            if (l1, mo1) != ("voll", "claude-opus-5"):
                fehler.append(f"Buchproduktion steht nicht zuerst: {l1}/{mo1}")
            if (l2, mo2) != ("testB", "claude-fable-5"):
                fehler.append(f"Testlauf falsch gebucht: {l2}/{mo2}")
            if e1["ein"] != 100 or e1["aus"] != 200:
                fehler.append(f"Token vermischt: {e1['ein']}/{e1['aus']}")
            if r1 != "uebersetzung" or r2 != "uebersetzung":
                fehler.append(f"Rolle verloren: {r1}, {r2}")

        # Die Summe wird je Lauf gebildet, sonst zahlt das Buch den Test mit.
        _, summen, _ = G.kosten_je_rolle(m)
        t = G.tarif("claude-opus-5")
        soll = (100 * t["ein"] + 300 * t["ein"] * G.CACHE_LESE_FAKTOR
                + 40 * t["ein"] * G.CACHE_SCHREIB_FAKTOR
                + 200 * t["aus"]) / 1e6
        if abs(summen.get("voll", 0) - soll) > 1e-9:
            fehler.append(f"Summe voll {summen.get('voll')} statt {soll}")
        if "testB" not in summen:
            fehler.append("Testlauf taucht in den Summen nicht auf")

        # Gegenprobe Altformat: ein Manifest ohne Laufkennung bleibt lesbar
        # und behauptet nicht, es sei die Buchproduktion gewesen.
        a = G.kosten_posten({"kosten": {"revision": {
            "modell": "claude-opus-5", "aufrufe": 1, "ein": 1, "aus": 1,
            "cache_lesen": 0, "cache_schreiben": 0}}})
        if len(a) != 1 or a[0][0] != "" or a[0][1] != "revision":
            fehler.append(f"Altformat falsch gelesen: {a}")

        if fehler:
            b.add("FEHLER", "Kostenbuchung fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Kosten: je Lauf, Rolle und Modell gebucht, "
                        "Testlauf getrennt ausgewiesen")
    except Exception as e:
        b.add("FEHLER", "Kostenbuchung nicht pruefbar", repr(e))

    # --- Fugenurteil: die Zahl hinter 'kette_max' ----------------------
    # Im Stapelbetrieb (Paket G) laeuft die Kette nur so lange, wie ein
    # Chunk auf den vorigen warten kann. Kuerzere Ketten heissen mehr
    # Fugen — und ob das schadet, gehoert gemessen statt geschaetzt.
    try:
        import tempfile
        import bewertung as BW
        fehler = []
        if "bruch" not in BW.FUGE_SYSTEM:
            fehler.append("Fugenprompt verlangt kein Urteil 'bruch'")
        for wort in ("Tempus", "Anrede", "Wiederaufnahme"):
            if wort not in BW.FUGE_SYSTEM:
                fehler.append(f"Fugenprompt nennt '{wort}' nicht")
        # Er darf NICHT nach der Qualitaet im Uebrigen fragen — sonst
        # misst er dasselbe wie das Blindurteil und nichts ueber die Naht.
        if "AUSSCHLIESSLICH den Uebergang" not in BW.FUGE_SYSTEM:
            fehler.append("Fugenprompt grenzt die Frage nicht ein")

        # Ohne Testlauf darf nichts abstuerzen und kein Modell laufen.
        gerufen = []
        echt_chat, alt_cwd = G.chat, os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                G.chat = lambda *a, **k: gerufen.append(1) or "{}"
                os.chdir(tmp)
                if BW.fugenurteil(cfg, praefix="test/") != []:
                    fehler.append("ohne Testlauf wird ein Urteil behauptet")
            finally:
                G.chat = echt_chat
                os.chdir(alt_cwd)
        if gerufen:
            fehler.append("ohne Testlauf wird trotzdem ein Modell gerufen")

        if fehler:
            b.add("FEHLER", "Fugenurteil fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Fugenurteil fragt nur nach der Naht und laeuft "
                        "ohne Testlauf nicht los")
    except Exception as e:
        b.add("FEHLER", "Fugenurteil nicht pruefbar", repr(e))

    # --- Dritter Testauszug: die Fallenpassage (Paket D) ---------------
    # Erzaehlung und Dialog messen, ob der Text als deutsche Prosa
    # besteht. Ob die Warnungen aus dem Fallenblock ankommen, messen sie
    # nicht — in einem ruhigen Erzaehlabschnitt kommen die Fallen gar
    # nicht vor. Der dritte Auszug sucht die dichteste Stelle.
    try:
        import uebersetzung as UE
        import bewertung as BW
        fehler = []

        ruhig = ("De zon ging onder achter de heuvel en het werd stil. "
                 "Wij keken naar de rivier en zeiden niets meer. ")
        fallen = ("Hij zou het meisje bellen maar het was al klaar. "
                  "Zij liep naar de winkel en kocht een tafeltje. ")
        if UE.fallendichte(fallen) <= UE.fallendichte(ruhig):
            fehler.append(f"Fallendichte unterscheidet nicht: "
                          f"{UE.fallendichte(fallen):.0f} gegen "
                          f"{UE.fallendichte(ruhig):.0f}")

        # Absaetze muessen unterscheidbar sein: Der Ueberschneidungstest
        # vergleicht sie als Menge, und identische Zeichenketten waeren
        # immer eine Ueberschneidung.
        # Absaetze muessen unterscheidbar sein: Der Ueberschneidungstest
        # vergleicht sie als Menge. Und die Fallenpassage liegt bewusst
        # NICHT in der Mitte — dort sucht der Erzaehlauszug, und die
        # beiden duerfen sich hier nicht zufaellig treffen.
        paras = ([f"{ruhig * 6} Nummer {k}." for k in range(40)]
                 + [f"{fallen * 6} Nummer {k}." for k in range(40, 52)])
        t1, t2, t3, kz = UE.testauszuege(paras, 300, 300, 300)
        if not t3:
            fehler.append("dritter Auszug bleibt leer")
        elif UE.fallendichte("\n\n".join(t3)) <= UE.fallendichte(
                "\n\n".join(t1)):
            fehler.append("dritter Auszug ist nicht der fallenreichste")
        # Er darf sich mit den anderen beiden nicht ueberschneiden — sonst
        # urteilt der Judge zweimal ueber denselben Text.
        for a, b_ in (("Erzaehlung", t1), ("Dialog", t2)):
            if set(t3) & set(b_):
                fehler.append(f"dritter Auszug ueberschneidet {a}")
        # 0 laesst ihn weg, und die Kennzahlen bleiben lesbar.
        _, _, leer, kz2 = UE.testauszuege(paras, 300, 300, 0)
        if leer:
            fehler.append("test_words_fallen=0 liefert trotzdem einen Auszug")
        if "dialogdichte" not in kz2 or "fallendichte" not in kz:
            fehler.append(f"Kennzahlen unvollstaendig: {kz}")

        # teile.json trennt die Auszuege im Ergebnis. Ohne sie schnitt die
        # alte Fassung bei der Haelfte der Absaetze und verglich damit
        # Erzaehlung gegen Dialog.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "x.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n\n".join(f"Absatz {k}" for k in range(10)))
            a, b_, c = BW.teile_trennen(p, {"erzaehlung": 4, "dialog": 3,
                                            "fallen": 3})
            if (len(G.absaetze(a)), len(G.absaetze(b_)),
                    len(G.absaetze(c))) != (4, 3, 3):
                fehler.append(f"teile_trennen schneidet falsch: "
                              f"{a!r} | {b_!r} | {c!r}")
            if "Absatz 0" not in a or "Absatz 4" not in b_ \
                    or "Absatz 7" not in c:
                fehler.append("teile_trennen ordnet die Absaetze falsch zu")

        if fehler:
            b.add("FEHLER", "Dritter Testauszug fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Fallenpassage wird gefunden, ueberschneidet die "
                        "anderen Auszuege nicht, teile.json trennt exakt")
    except Exception as e:
        b.add("FEHLER", "Dritter Testauszug nicht pruefbar", repr(e))

    # --- Vorwegschau und Figurennachhall (Paket C) ---------------------
    # Beide geben dem Chunk Kontext, den er von sich aus nicht hat. Beide
    # koennen dabei Schaden anrichten: eine Vorwegschau, die mituebersetzt
    # wird, und ein Nachhall, der ueber eine Ebenenfuge laeuft und Figuren
    # der einen Erzaehlebene in die andere traegt.
    try:
        import uebersetzung as UE
        fehler = []

        # Vorwegschau endet an der Satzgrenze — ein Fragment liest sich
        # wie ein abgebrochener Auftrag.
        t = "Erster Satz. Zweiter Satz! Noch einer laeuft weiter und weiter"
        if G.anfangswoerter(t, 4) != "Erster Satz. Zweiter Satz!":
            fehler.append(f"Schnitt nicht an der Satzgrenze: "
                          f"{G.anfangswoerter(t, 4)!r}")
        if G.anfangswoerter(t, 500) != t:
            fehler.append("kurzer Text wird beschnitten")
        if G.anfangswoerter(t, 0) != "":
            fehler.append("0 schaltet die Vorwegschau nicht ab")
        # Ein einziger langer Satz: lieber Fragment als gar nichts.
        if not G.anfangswoerter("Ein Satz ganz ohne jede Grenze hier", 4):
            fehler.append("Satz ohne Grenze liefert keinen Ausblick")
        # Sie darf nicht mit der Rueckschau verwechselt werden.
        if G.anfangswoerter(t, 4) == G.schlusswoerter(t, 4):
            fehler.append("Vorwegschau und Rueckschau liefern dasselbe")

        # Der Personenblock: wer nachhallt, muss als solcher erkennbar
        # sein — sonst sucht das Modell den Namen im Abschnitt.
        personen = {"Bennett": "er/ihn", "Babette": "sie/sie"}
        da = UE.block_personen("Bennett ging fort.", personen, {})
        if "Babette" in da:
            fehler.append("nicht genannte Figur steht ohne Nachhall im Block")
        hall = UE.block_personen("Hij ging fort.", personen, {},
                                 nachhall={"Bennett"})
        if "Bennett" not in hall:
            fehler.append("Nachhall bringt die Figur nicht in den Block")
        if "zuletzt erwähnt" not in hall:
            fehler.append("nachhallende Figur ist nicht als solche markiert")
        if "zuletzt erwähnt" in da:
            fehler.append("anwesende Figur wird als nachhallend markiert")
        if UE.figuren_im_chunk("Bennett und Babette.", personen) != \
                {"Bennett", "Babette"}:
            fehler.append("Figurenerkennung im Chunk falsch")

        # Die Fugenregel ist der Kern: Die Vorwegschau darf die
        # Ebenenfuge NICHT unterlaufen. Sonst sieht der letzte Chunk der
        # einen Ebene den Anfang der naechsten — mit anderem Tempus und
        # anderer Person — und genau davor schuetzt die Fuge.
        ch = [("Eerste stuk. Nog een zin.", False),
              ("Tweede stuk. Nog een zin.", False),
              ("Derde stuk. Nog een zin.", False),
              ("Een citaat blijft staan.", True),
              ("Vijfde stuk. Nog een zin.", False)]
        fugen = {2}                       # vor Chunk 2 liegt eine Fuge
        if not UE.vorwegschau(ch, 0, fugen, 50).startswith("Tweede"):
            fehler.append("Vorwegschau innerhalb der Ebene fehlt")
        if UE.vorwegschau(ch, 1, fugen, 50) != "":
            fehler.append("Vorwegschau laeuft ueber die Ebenenfuge hinweg")
        if UE.vorwegschau(ch, 2, fugen, 50) != "":
            fehler.append("geschuetztes Zitat wird als Ausblick gegeben")
        if UE.vorwegschau(ch, 4, fugen, 50) != "":
            fehler.append("letzter Chunk liefert einen Ausblick")
        if UE.vorwegschau(ch, 0, fugen, 0) != "":
            fehler.append("abgeschaltete Vorwegschau liefert trotzdem Text")

        # Der Prompt muss die Vorwegschau ankuendigen, sonst uebersetzt
        # das Modell sie mit — und die Laengenpruefung verwirft den Chunk.
        p_ueb, _ = UE.prompts(cfg)
        if "SO GEHT ES DANACH WEITER" not in p_ueb:
            fehler.append("System-Prompt kennt den Vorwegschau-Block nicht")
        if "NICHT übersetzen" not in p_ueb and "niemals erneut" not in p_ueb:
            fehler.append("System-Prompt verbietet das Mituebersetzen nicht")

        # Der Revisionsprompt muss die Rueckschau kennen. Ohne den Block
        # glaettet Pass 2 genau die Anschluesse weg, die Pass 1 hergestellt
        # hat — und ohne die Absatzregel bricht er die Absatztreue, an der
        # Leseausgabe, Zitateinsatz und Tempusmessung haengen.
        _, p_rev = UE.prompts(cfg)
        if "ENDE DES VORIGEN ABSCHNITTS" not in p_rev:
            fehler.append("Revisionsprompt kennt die Rueckschau nicht")
        if "Absätze" not in p_rev and "Absätzen" not in p_rev:
            fehler.append("Revisionsprompt nennt die Absatzregel nicht")

        # Die drei neuen Schalter muessen verstellbar sein — sonst haelt
        # eine eingespielte projekt.json sie nicht.
        for k in ("context_words_voraus", "rueckschau_quelle",
                  "figuren_nachhall"):
            if k not in G.AENDERBAR:
                fehler.append(f"{k} ist nicht verstellbar")
            if k not in G.STANDARD:
                fehler.append(f"{k} fehlt in STANDARD")

        if fehler:
            b.add("FEHLER", "Vorwegschau oder Nachhall fehlerhaft",
                  "; ".join(fehler))
        else:
            b.add("OK", "Vorwegschau schneidet an Satzgrenzen, Nachhall "
                        "markiert abwesende Figuren")
    except Exception as e:
        b.add("FEHLER", "Vorwegschau nicht pruefbar", repr(e))

    # --- Erzaehlebenen: die zweite Quelle der Fugen --------------------
    # Der 'rahmen_marker' setzt voraus, dass der Autor die Wechsel
    # ausgezeichnet hat. Beim Buch 1919 tat er das nicht: fuenf Ebenen im
    # Stilprofil, EINE Gruppe ueber 147 Chunks — die deutsche Rueckschau
    # lief also ueber jeden Ebenenwechsel. ebenen.json ist die Antwort
    # darauf, und ein Eintrag, der am falschen Absatz landet, ist
    # schaedlicher als gar keiner.
    try:
        import tempfile
        import vorbereitung as VB
        fehler = []
        paras = ["Ik zet mijn koffer neer en kijk omhoog.",
                 "Het regent nog steeds boven de stad.",
                 "De modder kwam tot aan onze knieen.",
                 "Wij groeven de hele nacht door.",
                 "Ik sta weer op het plein."]
        ebenen = [{"beginn": "Ik zet mijn koffer neer", "ebene": "Rahmen"},
                  {"beginn": "De modder kwam", "ebene": "Rückblende"},
                  {"beginn": "Ik sta weer op het plein", "ebene": "Rahmen"}]

        anfaenge, unbekannt = G.ebenen_anfaenge(paras, ebenen)
        if [i for i, _ in anfaenge] != [0, 2, 4]:
            fehler.append(f"Anfaenge falsch gefunden: {anfaenge}")
        if unbekannt:
            fehler.append(f"gueltige Eintraege gelten als unbekannt: "
                          f"{unbekannt}")
        gruppen, namen = G.ebenen_gruppen(paras, ebenen)
        if [len(g) for g in gruppen] != [2, 2, 1]:
            fehler.append(f"Gruppen falsch geschnitten: "
                          f"{[len(g) for g in gruppen]}")
        if namen != ["Rahmen", "Rückblende", "Rahmen"]:
            fehler.append(f"Ebenennamen falsch: {namen}")

        # Ein 'beginn', den es nicht gibt, MUSS auffallen — sonst saesse
        # die Fuge am falschen Absatz.
        _, fehlt = G.ebenen_anfaenge(paras, [{"beginn": "Er was eens",
                                              "ebene": "Rahmen"}])
        if not fehlt:
            fehler.append("nicht auffindbarer 'beginn' wird verschwiegen")

        # Beginnt der erste Eintrag spaeter, ist das Davor eine eigene,
        # unbenannte Gruppe — und keine, die zur ersten Ebene gehoert.
        g2, n2 = G.ebenen_gruppen(paras, [{"beginn": "De modder kwam",
                                           "ebene": "Rückblende"}])
        if [len(g) for g in g2] != [2, 3] or n2[0] != "":
            fehler.append(f"Vorspann falsch behandelt: "
                          f"{[len(g) for g in g2]}, {n2}")

        # Namen muessen aus stilprofil.json kommen; zwei Schreibweisen
        # derselben Ebene sehen wie zwei Ebenen aus.
        p = {"Rahmen": "erste Person Präsens",
             "Rückblende": "erste Person Präteritum"}
        if G.ebenen_maengel(ebenen, p):
            fehler.append(f"gueltige Datei beanstandet: "
                          f"{G.ebenen_maengel(ebenen, p)}")
        if not G.ebenen_maengel([{"beginn": "x", "ebene": "Traum"}], p):
            fehler.append("unbekannte Ebene wird nicht beanstandet")
        if not G.ebenen_maengel([{"ebene": "Rahmen"}], p):
            fehler.append("fehlendes 'beginn' wird nicht beanstandet")

        # Das Lieferschema muss durch den Anbieter kommen.
        if G.schema_maengel(VB.EBENEN_SCHEMA):
            fehler.append(f"Ebenenschema abgelehnt: "
                          f"{G.schema_maengel(VB.EBENEN_SCHEMA)}")
        # Die Absatzanfaenge muessen durchnummeriert und woertlich sein —
        # das Modell echot sie zurueck, und daran wird wiedergefunden.
        anf = VB.absatzanfaenge(paras)
        if not anf.startswith("1. Ik zet mijn koffer neer"):
            fehler.append(f"Absatzanfaenge falsch aufbereitet: {anf[:40]}")

        # Ohne Datei gilt weiter der Marker — der Rueckfall bleibt.
        leer, leer_n = G.ebenen_gruppen(paras, [])
        if len(leer) != 1 or leer_n != [""]:
            fehler.append("ohne Eintraege wird nicht eine Gruppe geliefert")

        # Diese Datei hat als einzige Referenzdatei eine LISTE an der
        # Wurzel. 'lade_json' liefert dafuer still ein leeres Objekt —
        # ueber lade_json gelesen waere ebenen.json IMMER leer: kein
        # Fehler, keine Meldung, nur keine Fugen. Genau das ist beim
        # Bauen passiert.
        with tempfile.TemporaryDirectory() as tmp:
            pfad = os.path.join(tmp, "ebenen.json")
            with open(pfad, "w", encoding="utf-8") as f:
                json.dump(ebenen, f)
            if len(G.ebenen_lesen(pfad)) != 3:
                fehler.append("Liste an der Wurzel wird nicht gelesen")
            # Ein Modell kann sie auch als Objekt liefern.
            with open(pfad, "w", encoding="utf-8") as f:
                json.dump({"ebenen": ebenen}, f)
            if len(G.ebenen_lesen(pfad)) != 3:
                fehler.append("Objektform wird nicht gelesen")
            with open(pfad, "w", encoding="utf-8") as f:
                f.write("kein json")
            if G.ebenen_lesen(pfad) != []:
                fehler.append("kaputte Datei liefert keine leere Liste")
        # Gegenprobe, dass niemand doch wieder lade_json benutzt. Die
        # Nadel wird zusammengesetzt, sonst findet der Test sich selbst.
        nadel = "lade_json(G.F[" + '"ebenen"' + "]"
        for datei in ("qa.py", "uebersetzung.py", "preflight.py"):
            if nadel in quelltext(datei):
                fehler.append(f"{datei} liest ebenen.json ueber lade_json")

        if fehler:
            b.add("FEHLER", "Erzaehlebenen fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Erzaehlebenen: Fugen sitzen am richtigen Absatz, "
                        "unauffindbare Eintraege werden gemeldet")
    except Exception as e:
        b.add("FEHLER", "Erzaehlebenen nicht pruefbar", repr(e))

    # --- Strukturierte Ausgabe: nur wo sie ausdrueckbar ist ------------
    # Das unterstuetzte Schema-Subset verlangt 'additionalProperties':
    # false und kann damit keine offenen Abbildungen ausdruecken. Genau
    # das sind die Vorbereitungslieferungen (Wort -> Wort). Ein Schema,
    # das der Anbieter ablehnt, faellt sonst erst im Lauf auf — und dann
    # nach dem Bezahlen.
    try:
        import zitatrecherche as Z
        fehler = []
        maengel = G.schema_maengel(Z.BEFUND_SCHEMA)
        if maengel:
            fehler.append(f"Zitatschema abgelehnt: {'; '.join(maengel)}")

        # Gegenproben: der Pruefer muss beide Fallen fangen.
        offen = {"type": "object", "properties": {},
                 "required": []}                       # ohne additionalProps
        if not G.schema_maengel(offen):
            fehler.append("offene Abbildung wird nicht beanstandet")
        grenzen = {"type": "object", "additionalProperties": False,
                   "required": ["n"],
                   "properties": {"n": {"type": "number", "minimum": 0}}}
        if not G.schema_maengel(grenzen):
            fehler.append("Zahlgrenze wird nicht beanstandet")

        # Das Schema muss im Payload ankommen — neben 'effort', nicht
        # statt seiner.
        p = G.AnthropicBackend().payload(cfg, "S", "U", "zitat",
                                         "claude-opus-5",
                                         schema=Z.BEFUND_SCHEMA)
        oc = p.get("output_config", {})
        if oc.get("format", {}).get("type") != "json_schema":
            fehler.append(f"Schema fehlt im Payload: {oc}")
        if not oc.get("effort"):
            fehler.append("Schema verdraengt den Effort")
        ohne = G.AnthropicBackend().payload(cfg, "S", "U", "zitat",
                                            "claude-opus-5")
        if "format" in ohne.get("output_config", {}):
            fehler.append("Payload traegt ein Schema, das keiner bestellt hat")

        # Gemini spricht einen anderen Dialekt: Das Schema darf dort NICHT
        # ankommen, sonst ist der Aufruf ein HTTP 400.
        g = G.GeminiBackend().payload(cfg, "S", "U", "begruendung",
                                      "gemini-3.6-flash")
        if "json_schema" in json.dumps(g):
            fehler.append("Gemini-Payload traegt ein JSON-Schema")

        if fehler:
            b.add("FEHLER", "Strukturierte Ausgabe fehlerhaft",
                  "; ".join(fehler))
        else:
            b.add("OK", "Strukturierte Ausgabe: Schema im Anthropic-Payload "
                        "neben dem Effort, Gemini bleibt unberuehrt")
    except Exception as e:
        b.add("FEHLER", "Strukturierte Ausgabe nicht pruefbar", repr(e))

    # --- Quelldateien nur ueber CODE lesen -----------------------------
    # Im Colab-Betrieb ist das Arbeitsverzeichnis der Drive-Ordner, nicht
    # das Repo. Ein relativ geoeffnetes 'bewertung.py' wirft dort einen
    # FileNotFoundError, und die Pruefung meldet 'nicht pruefbar' statt zu
    # pruefen — sie war monatelang wirkungslos, ohne dass es auffiel.
    try:
        fehler = []
        for datei in ("bewertung.py", "annotation.py", "ABLAUFPLAN.md"):
            if not quelltext(datei):
                fehler.append(f"{datei} nicht ueber CODE lesbar")
        eigen = quelltext(os.path.basename(os.path.abspath(__file__)))
        # Der Fehler ist ein Muster, keine Einzelstelle: relativ
        # geoeffnete Projektdateien im Selbsttest.
        offen = re.findall(r'open\("(\w+\.(?:py|md))"', eigen)
        if offen:
            fehler.append(f"relativ geoeffnet statt ueber CODE: "
                          f"{', '.join(sorted(set(offen)))}")
        if fehler:
            b.add("FEHLER", "Quelldateizugriff fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Selbsttest liest Quelldateien ueber CODE — laeuft "
                        "auch aus einem fremden Arbeitsverzeichnis")
    except Exception as e:
        b.add("FEHLER", "Quelldateizugriff nicht pruefbar", repr(e))

    # --- Empfehlung, Rollen und entfallene Schluessel ------------------
    # Die Empfehlungstabelle ist die Stelle, an der die Modellwahl
    # begruendet steht. Sie ist nur so viel wert, wie sie vollstaendig
    # ist: Eine Rolle ohne Eintrag erscheint in 'pipeline.py modelle' mit
    # leerer Empfehlung — und wer sie dann setzt, raet.
    try:
        import tempfile
        fehler = []
        ohne = [r for r in G.ROLLEN if not G.EMPFEHLUNG.get(r, ("",))[0]]
        if ohne:
            fehler.append(f"ohne Empfehlung: {', '.join(ohne)}")
        fremd = [r for r in G.EMPFEHLUNG if r not in G.ROLLEN]
        if fremd:
            fehler.append(f"Empfehlung fuer unbekannte Rolle: "
                          f"{', '.join(fremd)}")
        for r, (m, e, warum) in G.EMPFEHLUNG.items():
            if e not in G.EFFORT:
                fehler.append(f"{r}: Tiefe '{e}' gibt es nicht")
            if len(warum) < 40:
                fehler.append(f"{r}: Begruendung zu duenn")

        # Die beiden Annotationsarbeiten muessen getrennt routen — sonst
        # war die Trennung Kosmetik.
        probe = dict(G.STANDARD, modell_begruendung="gemini-3.6-flash",
                     modell_screening="gemini-3.1-pro-preview")
        if G.modell_fuer(probe, "begruendung") == \
                G.modell_fuer(probe, "screening"):
            fehler.append("begruendung und screening routen aufs selbe "
                          "Modell")
        quelle = quelltext("annotation.py")
        for soll in ('rolle="begruendung"', 'rolle="screening"'):
            if soll not in quelle:
                fehler.append(f"annotation.py ruft nicht {soll}")
        if 'rolle="annotation"' in quelle:
            fehler.append("annotation.py ruft noch die alte Rolle")

        # Entfallene Schluessel muessen auffallen, saubere nicht.
        class _B:
            def __init__(self): self.meldungen = []

            def add(self, art, thema, text=""):
                self.meldungen.append((art, thema))
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "projekt.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"modell_annotation": "x", "temperature_stil": 1}, f)
            bb = _B()
            pruefe_entfallene_schluessel(bb, p)
            if not any(a == "WARN" for a, _ in bb.meldungen):
                fehler.append("entfallene Schluessel werden nicht gemeldet")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"modell_uebersetzung": "claude-opus-5"}, f)
            bb = _B()
            pruefe_entfallene_schluessel(bb, p)
            if bb.meldungen:
                fehler.append("saubere projekt.json wird beanstandet")

        if fehler:
            b.add("FEHLER", "Empfehlung oder Rollentrennung fehlerhaft",
                  "; ".join(fehler))
        else:
            b.add("OK", f"Empfehlung fuer alle {len(G.ROLLEN)} Rollen, "
                        f"Begruendung und Screening getrennt geroutet")
    except Exception as e:
        b.add("FEHLER", "Empfehlung nicht pruefbar", repr(e))

    # --- SDK-Pfad: derselbe Payload, dieselbe Antwort ------------------
    # Zwei Transportwege sind erlaubt, zwei Wahrheiten nicht. Der Selbsttest
    # prueft den Payload genau einmal; geht die SDK an 'payload' vorbei
    # oder liest sie Antworten selbst, prueft er den Weg, den niemand
    # benutzt. Und die Fehlermeldung muss 'HTTP <code>' behalten, sonst
    # greift der Rueckfall der Cache-Lebensdauer auf dem SDK-Pfad nicht.
    try:
        fehler = []
        b_a = G.AnthropicBackend()
        soll = b_a.payload(cfg, "SYSTEM", "USER", "uebersetzung",
                           "claude-opus-5")

        class _Strom:
            def __init__(self, kw): self.kw = kw

            def __enter__(self): return self

            def __exit__(self, *a): return False

            def get_final_message(self): return _Antwort()

        class _Nachrichten:
            def __init__(self):
                self.gesehen = None
                self.wie = None

            def create(self, **kw):
                self.gesehen, self.wie = kw, "create"
                return _Antwort()

            def stream(self, **kw):
                self.gesehen, self.wie = kw, "stream"
                return _Strom(kw)

        class _Antwort:
            def model_dump(self):
                return {"content": [{"type": "text", "text": "Hallo."}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 7, "output_tokens": 3,
                                  "cache_read_input_tokens": 11,
                                  "cache_creation_input_tokens": 0}}

        class _Klient:
            def __init__(self):
                self.messages = _Nachrichten()
                self.beta = type("B", (), {"messages": _Nachrichten()})()

        klient = _Klient()
        d = G.sdk_antwort(klient, soll)
        if klient.messages.gesehen != soll:
            fehler.append("SDK bekommt einen anderen Payload als requests")
        text, usage = b_a.antwort_lesen(d)
        if text != "Hallo." or usage["cache_lesen"] != 11:
            fehler.append(f"SDK-Antwort falsch gelesen: {text!r}, {usage}")

        # Streamen ist ein Transportdetail, kein zweiter Payload: Dieselbe
        # Anfrage geht raus, dieselbe Nachricht kommt zurueck. Ginge dabei
        # etwas verloren, waere es genau der Weg des Normalbetriebs.
        klient = _Klient()
        d = G.sdk_antwort(klient, soll, streamen=True)
        if klient.messages.wie != "stream":
            fehler.append("'streaming' erreicht die SDK nicht")
        if klient.messages.gesehen != soll:
            fehler.append("der Stream bekommt einen anderen Payload")
        if b_a.antwort_lesen(d)[0] != "Hallo.":
            fehler.append("Streamantwort wird anders gelesen")

        # Betakennwoerter gehen ueber den Namensraum 'beta' — im normalen
        # Namensraum kennt die API sie nicht, und der Aufruf liefe ohne die
        # Betafunktion durch, statt sie zu melden.
        klient = _Klient()
        G.sdk_antwort(klient, soll, betas=[G.BETA_FALLBACK])
        if klient.messages.gesehen is not None:
            fehler.append("Betaaufruf laeuft ueber den normalen Namensraum")
        gesehen = klient.beta.messages.gesehen or {}
        if gesehen.get("betas") != [G.BETA_FALLBACK]:
            fehler.append(f"Betakennwort fehlt im Aufruf: "
                          f"{gesehen.get('betas')}")

        # Fehlerabbildung: Status bleibt lesbar, TTL-Rueckfall greift.
        class _Status(Exception):
            status_code = 400
            body = {"error": {"message": "ttl: unsupported value"}}
        umgesetzt = G.sdk_fehler(G.anthropic_sdk(), _Status("kaputt"))
        if not isinstance(umgesetzt, G.ApiFehler):
            fehler.append("SDK-Fehler wird nicht zu ApiFehler")
        if not G.ttl_abgelehnt(umgesetzt):
            fehler.append(f"TTL-Rueckfall greift auf dem SDK-Pfad nicht: "
                          f"{umgesetzt}")

        class _Auth(Exception):
            status_code = 401
            body = "no key"
        if "401" not in str(G.sdk_fehler(G.anthropic_sdk(), _Auth("x"))):
            fehler.append("Statuscode geht in der Uebersetzung verloren")

        # Der requests-Pfad bleibt der Rueckfall: abgeschaltete oder
        # fehlende SDK darf keinen Klienten liefern.
        if b_a.klient(dict(cfg, sdk_nutzen=False)) is not None:
            fehler.append("'sdk_nutzen: false' wird nicht beachtet")

        if fehler:
            b.add("FEHLER", "SDK-Pfad fehlerhaft", "; ".join(fehler))
        else:
            vorhanden = "vorhanden" if G.anthropic_sdk() else "nicht \
installiert, requests-Pfad"
            b.add("OK", f"SDK-Pfad: derselbe Payload, derselbe Antwortleser, "
                        f"Statuscodes erhalten ({vorhanden})")
    except Exception as e:
        b.add("FEHLER", "SDK-Pfad nicht pruefbar", repr(e))

    # --- Ablehnung, Rueckfall, angehaltene Werkzeugrunde ---------------
    # Drei Faelle, die ein Buchlauf trifft und die frueher alle drei den
    # Lauf gekostet haben: Der Klassifikator lehnt einen Chunk ab (dreimal
    # dieselbe aussichtslose Wiederholung, dann Abbruch bei Chunk 300), die
    # Werkzeugschleife wird angehalten (halbe Antwort, gelesen als
    # Formfehler, Zitat uebersprungen), und die Websuche taucht in keiner
    # Rechnung auf.
    try:
        import contextlib
        import io
        import tempfile
        fehler = []
        b_a = G.AnthropicBackend()
        cfg_f = dict(cfg, fallback_modelle="default", sdk_nutzen=True,
                     streaming=False, cache_ttl="", max_retries=1)

        # (1) Der Rueckfall steht im Payload und im Kopf — und nur dann.
        p = b_a.payload(cfg_f, "S", "U", "uebersetzung", "claude-opus-5")
        if p.get("fallbacks") != "default":
            fehler.append("'fallbacks' fehlt im Payload")
        if b_a.betas(cfg_f) != [G.BETA_FALLBACK]:
            fehler.append(f"Betakennwort fehlt: {b_a.betas(cfg_f)}")
        aus = dict(cfg_f, fallback_modelle="")
        if "fallbacks" in b_a.payload(aus, "S", "U", "uebersetzung", "m") \
                or b_a.betas(aus):
            fehler.append("leeres 'fallback_modelle' schaltet nicht ab")
        # Mehr als drei Modelle nimmt die API nicht an. Gekappt wird hier,
        # damit daraus kein HTTP 400 mitten im Buch wird.
        viele = dict(cfg_f, fallback_modelle=["a", "b", "c", "d"])
        if G.fallbacks_wert(viele) != [{"model": m} for m in ("a", "b", "c")]:
            fehler.append(f"Modelliste nicht gekappt: "
                          f"{G.fallbacks_wert(viele)}")

        # (2) Die Ablehnung wird eng erkannt: das unbekannte Betakennwort
        # ja, ein gewoehnlicher Payloadfehler nicht. Zu weit gefasst
        # schluckte sie echte Fehler und gaebe still ein zweites Mal Geld aus.
        kopffehler = G.ApiFehler(
            "HTTP 400: Unexpected value(s) `server-side-fallback-2026-07-01` "
            "for the `anthropic-beta` header.")
        if not G.fallback_abgelehnt(kopffehler):
            fehler.append("abgelehntes Betakennwort wird nicht erkannt")
        for harmlos in ("HTTP 400: max_tokens: too large",
                        "HTTP 429: rate limited", "Netzwerkfehler: timeout"):
            if G.fallback_abgelehnt(G.ApiFehler(harmlos)):
                fehler.append(f"'{harmlos}' schaltet den Rueckfall ab")

        # (3) Eine Ablehnung nennt Kategorie und Erklaerung. Die Kategorie
        # allein sagt niemandem, warum ausgerechnet dieser Absatz auffiel.
        try:
            b_a.antwort_lesen({"stop_reason": "refusal", "content": [],
                               "stop_details": {
                                   "type": "refusal",
                                   "category": "general_harms",
                                   "explanation": "Beschreibung von Gewalt."}})
            fehler.append("Ablehnung wird nicht gemeldet")
        except G.ApiFehler as e:
            if "general_harms" not in str(e) or "Gewalt" not in str(e):
                fehler.append(f"Ablehnungsgrund unvollstaendig: {e}")

        # (3b) Der eigene Rueckfall, ohne jede Beta. Beim Buch Alexander
        # war die Betafunktion fuer den serverseitigen Rueckfall nicht
        # freigeschaltet — die Absicherung waere sonst ersatzlos
        # verschwunden. Dieser Weg liest 'refusal' und schickt dieselbe
        # Anfrage an das naechste Modell der Liste.
        eigen = dict(cfg_f, fallback_modelle=["claude-sonnet-5"])
        if G.eigene_rueckfaelle(eigen):
            fehler.append("eigener Rueckfall laeuft, obwohl der Server ihn "
                          "schon macht")
        merker = G._FALLBACK_ABGELEHNT
        try:
            G._FALLBACK_ABGELEHNT = True       # Server lehnt ab
            if G.eigene_rueckfaelle(eigen) != ["claude-sonnet-5"]:
                fehler.append("eigener Rueckfall greift nicht, wenn der "
                              "serverseitige abgelehnt wird")
            if G.eigene_rueckfaelle(dict(eigen, fallback_modelle="default")):
                fehler.append("'default' taugt als eigener Rueckfall — "
                              "die Kategorie kennt nur der Anbieter")

            gesehen = []

            class _Kette:
                def create(s, **kw):
                    gesehen.append(kw["model"])
                    if kw["model"] == "claude-opus-5":
                        d = {"content": [], "stop_reason": "refusal",
                             "stop_details": {"category": "general_harms"},
                             "usage": {"input_tokens": 400,
                                       "output_tokens": 0}}
                    else:
                        d = {"content": [{"type": "text", "text": "Ersatz."}],
                             "stop_reason": "end_turn",
                             "usage": {"input_tokens": 400,
                                       "output_tokens": 9}}
                    return type("A", (), {"model_dump":
                                          lambda self, x=d: x})()

            kette = _Kette()
            b_a.klient = lambda cfg_: type(
                "K", (), {"messages": kette,
                          "beta": type("B", (), {"messages": kette})()})()
            with tempfile.TemporaryDirectory() as tmp2:
                alt2 = os.getcwd()
                try:
                    os.chdir(tmp2)
                    G.api_schluessel = lambda *a, **k: "test"
                    with contextlib.redirect_stdout(io.StringIO()):
                        t3, m3 = b_a.chat_meta(eigen, "S", "U",
                                               rolle="uebersetzung",
                                               modell="claude-opus-5")
                    if t3 != "Ersatz.":
                        fehler.append(f"eigener Rueckfall liefert nichts: "
                                      f"{t3!r}")
                    if gesehen != ["claude-opus-5", "claude-sonnet-5"]:
                        fehler.append(f"Modellkette falsch: {gesehen}")
                    if m3.get("modell") != "claude-sonnet-5":
                        fehler.append(f"unter dem falschen Modell gebucht: "
                                      f"{m3.get('modell')}")
                    # Ohne Ersatzmodell bleibt die Ablehnung eine Ablehnung
                    # — verschluckt werden darf sie nie.
                    gesehen.clear()
                    try:
                        with contextlib.redirect_stdout(io.StringIO()):
                            b_a.chat_meta(dict(eigen, fallback_modelle=""),
                                          "S", "U", rolle="uebersetzung",
                                          modell="claude-opus-5")
                        fehler.append("Ablehnung ohne Ersatzmodell wird "
                                      "verschluckt")
                    except G.Ablehnung as e:
                        if e.kategorie != "general_harms":
                            fehler.append(f"Kategorie geht verloren: "
                                          f"{e.kategorie!r}")
                finally:
                    os.chdir(alt2)
        finally:
            G._FALLBACK_ABGELEHNT = merker
            del b_a.klient

        # (4) Wer geantwortet hat, entscheidet die Iterationsliste — nicht
        # der Modellname. Ein Alias loest auf einen datierten Namen auf;
        # danach zu buchen zerlegte die Kostenzeile in zwei halbe.
        alias = {"model": "claude-opus-5-20260801", "usage": {}}
        if G.bedient_von(alias, "claude-opus-5") != "claude-opus-5":
            fehler.append("aufgeloester Alias gilt faelschlich als Rueckfall")

        folge_rueckfall = [{
            "model": "claude-opus-4-8",
            "content": [{"type": "fallback",
                         "from": {"model": "claude-opus-5"},
                         "to": {"model": "claude-opus-4-8"}},
                        {"type": "text", "text": "Ersatzfassung."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 2,
                      "iterations": [
                          {"type": "message", "model": "claude-opus-5",
                           "input_tokens": 5, "output_tokens": 0},
                          {"type": "fallback_message",
                           "model": "claude-opus-4-8",
                           "input_tokens": 5, "output_tokens": 2}]}}]

        # (5) Eine angehaltene Werkzeugrunde wird fortgesetzt, nicht
        # halbiert. Die angehaltene Antwort geht dabei unveraendert
        # zurueck — aber ohne die None-Felder, mit denen die SDK
        # ungesetzte Schluessel fuellt und die die API ablehnt.
        folge_pause = [
            {"content": [{"type": "server_tool_use", "id": "s1",
                          "name": "web_search", "input": None},
                         {"type": "text", "text": "Teil eins. "}],
             "stop_reason": "pause_turn",
             "usage": {"input_tokens": 10, "output_tokens": 2,
                       "server_tool_use": {"web_search_requests": 2}}},
            {"content": [{"type": "text", "text": "Teil zwei.",
                          "citations": [
                              {"type": "web_search_result_location",
                               "url": "https://example.org/a",
                               "title": "Beispielausgabe",
                               "cited_text": "Alles von Wert ist wehrlos."}]}],
             "stop_reason": "end_turn",
             "usage": {"input_tokens": 12, "output_tokens": 4,
                       "server_tool_use": {"web_search_requests": 1}}},
        ]

        class _MM:
            def __init__(s, folge): s.folge, s.gesehen = list(folge), []

            def create(s, **kw):
                s.gesehen.append(kw)
                d = s.folge.pop(0)
                return type("A", (), {"model_dump": lambda self: d})()

        class _KK:
            def __init__(s, folge):
                s.messages = _MM(folge)
                s.beta = type("B", (), {"messages": s.messages})()

        echt_schluessel = G.api_schluessel
        alt_cwd = os.getcwd()
        try:
            G.api_schluessel = lambda *a, **k: "test-schluessel"
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)

                klient = _KK(folge_rueckfall)
                b_a.klient = lambda cfg_: klient
                with contextlib.redirect_stdout(io.StringIO()) as ausgabe:
                    text, meta = b_a.chat_meta(
                        cfg_f, "S", "U", rolle="uebersetzung",
                        modell="claude-opus-5")
                if meta.get("modell") != "claude-opus-4-8":
                    fehler.append(f"Ersatzmodell nicht erkannt: {meta}")
                if "claude-opus-4-8" not in ausgabe.getvalue():
                    fehler.append("Rueckfall laeuft still durch")
                gebucht = G.kosten_schnappschuss()
                if "voll/uebersetzung/claude-opus-4-8" not in gebucht:
                    fehler.append(f"unter dem falschen Modell gebucht: "
                                  f"{sorted(gebucht)}")

                klient = _KK(folge_pause)
                b_a.klient = lambda cfg_: klient
                with contextlib.redirect_stdout(io.StringIO()):
                    text, meta = b_a.chat_meta(
                        cfg_f, "S", "U", rolle="zitat", roh=True,
                        modell="claude-opus-5",
                        werkzeuge=G.websuche_werkzeug(cfg_f))
                if text != "Teil eins. Teil zwei.":
                    fehler.append(f"angehaltene Runde nicht fortgesetzt: "
                                  f"{text!r}")
                if len(klient.messages.gesehen) != 2:
                    fehler.append(f"{len(klient.messages.gesehen)} statt 2 "
                                  f"Aufrufe fuer eine angehaltene Runde")
                else:
                    zweiter = klient.messages.gesehen[1]["messages"]
                    if len(zweiter) != 2 or zweiter[1]["role"] != "assistant":
                        fehler.append("angehaltene Antwort geht nicht zurueck")
                    elif any(v is None for bl in zweiter[1]["content"]
                             for v in bl.values()):
                        fehler.append("None-Felder gehen an die API zurueck")
                # Beide Zusicherungen koennen nacheinander abgelehnt
                # werden. Frueher wurde genau einmal wiederholt: Lehnte der
                # Anbieter erst die Lebensdauer und dann den Rueckfall ab,
                # brach der Lauf ab, obwohl er ohne beide gelaufen waere.
                merker = (G._TTL_ABGELEHNT, G._FALLBACK_ABGELEHNT)
                try:
                    ruf = []

                    class _Zwei:
                        def create(s, **kw):
                            ruf.append(kw)
                            if len(ruf) == 1:
                                raise G.ApiFehler("HTTP 400: ttl: unsupported")
                            if len(ruf) == 2:
                                raise G.ApiFehler("HTTP 400: fallbacks not "
                                                  "enabled")
                            return type("A", (), {"model_dump": lambda self: {
                                "content": [{"type": "text", "text": "Da."}],
                                "stop_reason": "end_turn",
                                "usage": {"input_tokens": 3,
                                          "output_tokens": 1}}})()

                    zwei = _Zwei()
                    b_a.klient = lambda cfg_: type(
                        "K", (), {"messages": zwei,
                                  "beta": type(
                                      "B", (),
                                      {"messages": zwei})()})()
                    with contextlib.redirect_stdout(io.StringIO()):
                        t2, _ = b_a.chat_meta(dict(cfg_f, cache_ttl="1h"),
                                              "S", "U", modell="claude-opus-5")
                    if t2 != "Da." or len(ruf) != 3:
                        fehler.append(f"zwei Ablehnungen ueberleben den Lauf "
                                      f"nicht: {t2!r}, {len(ruf)} Aufrufe")
                    elif "ttl" in str(ruf[2].get("system")) \
                            or "fallbacks" in ruf[2]:
                        fehler.append("aufgegebene Zusicherung steht im "
                                      "neuen Payload")
                finally:
                    G._TTL_ABGELEHNT, G._FALLBACK_ABGELEHNT = merker

                if meta.get("suchen") != 3:
                    fehler.append(f"Suchen falsch gezaehlt: "
                                  f"{meta.get('suchen')}")
                if [x["url"] for x in meta.get("belege") or []] \
                        != ["https://example.org/a"]:
                    fehler.append(f"Belege fehlen: {meta.get('belege')}")
                # Die Suche kostet je Aufruf und muss in der Rechnung
                # stehen. Ohne eigenes Feld waere die Zitatrecherche der
                # einzige Schritt, dessen Preis nicht stimmt.
                zeile = G.kosten_schnappschuss().get(
                    "voll/zitat/claude-opus-5", {})
                if zeile.get("suchen") != 3:
                    fehler.append(f"Suchen nicht gebucht: {zeile}")
                preis = G.kosten_dollar({"ein": 0, "aus": 0, "suchen": 4},
                                        {"ein": 5.0, "aus": 25.0})
                if abs(preis - 0.04) > 1e-9:
                    fehler.append(f"Suchpreis falsch: {preis}")
        finally:
            G.api_schluessel = echt_schluessel
            del b_a.klient
            os.chdir(alt_cwd)

        # (6) Die Werkzeugfassung kommt aus der Konfiguration, nicht aus
        # dem Code. Ein Name im Code laesst den Schritt eines Tages mit
        # veralteter Suche laufen, ohne dass es jemandem auffaellt.
        # Ausgenommen sind die zwei Stellen, an denen der Name hingehoert:
        # die Vorgabe in gemeinsam.STANDARD und dieser Test. Ueberall sonst
        # ist er die Fassung, die niemand mehr aendert — zitatrecherche.py
        # trug bis August 2026 die von Maerz 2025.
        nadel = "web_search_" + "20"
        drin = sorted(os.path.basename(n) for n in _glob_py()
                      if nadel in quelltext(n)
                      and os.path.basename(n) not in ("preflight.py",
                                                      "gemeinsam.py"))
        if drin:
            fehler.append(f"Werkzeugfassung hartkodiert in {', '.join(drin)}")
        w = G.websuche_werkzeug(
            dict(cfg, websuche_werkzeug="web_search_20260209",
                 websuche_filtern=True))
        if w[0].get("allowed_callers"):
            fehler.append("filternde Fassung wird auf direkt gezwungen")
        w = G.websuche_werkzeug(
            dict(cfg, websuche_werkzeug="web_search_20260209",
                 websuche_filtern=False))
        if w[0].get("allowed_callers") != ["direct"]:
            fehler.append("'websuche_filtern: false' wirkt nicht")
        # Die aelteste Fassung kennt den Schluessel nicht und antwortet
        # darauf mit HTTP 400 — sie darf ihn nie bekommen.
        w = G.websuche_werkzeug(
            dict(cfg, websuche_werkzeug="web_search_20250305",
                 websuche_filtern=False))
        if w[0].get("allowed_callers"):
            fehler.append("alte Fassung bekommt 'allowed_callers'")
        if G.websuche_werkzeug(dict(cfg, websuche_werkzeug="")) is not None:
            fehler.append("leeres 'websuche_werkzeug' schaltet nicht ab")

        if fehler:
            b.add("FEHLER", "Rueckfall oder Websuche fehlerhaft",
                  "; ".join(fehler))
        else:
            b.add("OK", "Ablehnung faellt auf ein Ersatzmodell zurueck und "
                        "wird dort gebucht, angehaltene Werkzeugrunden "
                        "laufen weiter, Suchen sind bezahlt")
    except Exception as e:
        b.add("FEHLER", "Rueckfall nicht pruefbar", repr(e))

    # --- Die Vorlage im Repo nennt jede Einstellung -------------------
    # Ein Schluessel, der nur in STANDARD steht, entscheidet sich still:
    # Wer eine projekt.json fuer ein neues Buch durchsieht, sieht ihn gar
    # nicht. Genau so stand 'rahmen_marker' unsichtbar auf '#', waehrend
    # der Autor von 1919 ihn nie benutzt hat.
    try:
        fehler = []
        vorlage = json.load(open(os.path.join(CODE, G.VORLAGE),
                                 encoding="utf-8"))
        fehlt = sorted(k for k in G.STANDARD if k not in vorlage)
        if fehlt:
            fehler.append(f"nicht in der Vorlage: {', '.join(fehlt)}")
        # Umgekehrt: was die Vorlage nennt, muss es auch geben.
        unbekannt = sorted(k for k in vorlage
                           if not k.startswith("_") and k not in G.STANDARD)
        if unbekannt:
            fehler.append(f"Vorlage nennt Unbekanntes: "
                          f"{', '.join(unbekannt)}")
        # Die Schluessel, die ein neues Buch wirklich entscheiden muss,
        # brauchen einen Hinweis daneben — sonst liest sie niemand.
        hinweise = " ".join(str(v) for k, v in vorlage.items()
                            if k.startswith("_"))
        for wort in ("rahmen_marker", "ebenen.json", "NEUES_BUCH.md"):
            if wort not in hinweise:
                fehler.append(f"Vorlage erklaert '{wort}' nicht")
        # Und der Preflight muss melden, wenn der eingestellte Marker im
        # Text gar nicht vorkommt. Das ist die eine Zeile, die den Lauf
        # 1919 verhindert haette.
        class _Sammler:
            def __init__(s): s.zeilen = []

            def abschnitt(s, t): pass

            def add(s, art, t, d=""): s.zeilen.append((art, t))

        with tempfile.TemporaryDirectory() as tmp:
            alt_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                paras = [f"Zin {i} met genoeg woorden hier om te tellen."
                         for i in range(1, 30)]
                probe = dict(cfg, rahmen_marker="#")
                for text, erwartet, was in (
                        ("\n\n".join(paras), "WARN", "fehlender Marker"),
                        ("\n\n".join(paras[:5] + ["#"] + paras[5:]), "OK",
                         "vorhandener Marker")):
                    open(G.F["quelle"], "w", encoding="utf-8").write(text)
                    s = _Sammler()
                    with contextlib.redirect_stdout(io.StringIO()):
                        pruefe_text(probe, s)
                    treffer = [a for a, t in s.zeilen if "ahmenmarker" in t]
                    if treffer != [erwartet]:
                        fehler.append(f"{was}: {treffer} statt "
                                      f"['{erwartet}']")
            finally:
                os.chdir(alt_cwd)

        # Modellnamen in der Doku muessen die eingestellten sein. Die
        # Anleitung zeigte als Beispiel fuer 'technik_ausnahmen'
        # 'modell_uebersetzung: claude-sonnet-5' — in einem Block, den
        # sie selbst zum Kopieren anbietet. Wer ihn uebernahm, tauschte
        # das wichtigste Modell der Pipeline aus, und 'technik_ausnahmen'
        # schuetzte den Fehler dann auch noch vor dem Abgleich.
        # Ausgenommen ist die Historie: ARBEITSAUFTRAG.md haelt den Stand
        # vom Juli 2026 fest und soll ihn festhalten. Ein Dokument, das
        # beschreibt was war, darf nicht mitwandern.
        for d in _glob_md():
            if os.path.basename(d) == "ARBEITSAUFTRAG.md":
                continue
            for rolle, name in re.findall(
                    r'"modell_(\w+)"\s*:\s*"([^"]+)"',
                    quelltext(d)):
                soll = vorlage.get(f"modell_{rolle}")
                if soll and name != soll:
                    fehler.append(
                        f"{os.path.basename(d)}: modell_{rolle} steht dort "
                        f"als '{name}', eingestellt ist '{soll}'")

        # Die Zellnummern in der Doku muessen die des Runners sein. Als
        # die Anmeldezelle dazukam, rutschten alle Zellen um eins, und
        # 27 Verweise in drei Dokumenten zeigten auf die falsche.
        nb = os.path.join(CODE, "colab_runner.ipynb")
        if os.path.exists(nb):
            zellen = json.load(open(nb, encoding="utf-8"))["cells"]
            da = set(re.findall(r"^## (\d+) ", "\n".join(
                "".join(c["source"]) for c in zellen
                if c["cell_type"] == "markdown"), re.M))
            for d in _glob_md():
                falsch = sorted({n for n in re.findall(
                    r"Zelle (\d+)", quelltext(d))} - da)
                if falsch:
                    fehler.append(f"{os.path.basename(d)}: verweist auf "
                                  f"Zelle {', '.join(falsch)} — die gibt es "
                                  f"im Runner nicht")

        # Kein verwaistes Dokument. NEUES_BUCH.md lag ein halbes Jahr im
        # Repo, ohne dass irgendein anderes es erwaehnt haette — die
        # Datei, die man zuerst braucht, war die einzige unauffindbare.
        docs = [os.path.basename(p) for p in _glob_md()]
        texte = {d: quelltext(os.path.join(CODE, d)) for d in docs}
        # Gefragt ist, ob ein ANDERES Dokument darauf zeigt — der eigene
        # Text zaehlt nicht. Die drei Einstiege zeigen auf die anderen,
        # nicht umgekehrt, und sind deshalb ausgenommen.
        verwaist = [d for d in docs
                    if d not in ("README.md", "CLAUDE.md",
                                 "ENTSCHEIDUNGEN.md")
                    and not any(d in t for k, t in texte.items() if k != d)]
        if verwaist:
            fehler.append(f"von keinem anderen Dokument erwaehnt: "
                          f"{', '.join(verwaist)}")

        if fehler:
            b.add("FEHLER", "Vorlage projekt.json unvollstaendig",
                  "; ".join(fehler))
        else:
            b.add("OK", f"Vorlage projekt.json nennt alle "
                        f"{len(G.STANDARD)} Einstellungen, "
                        f"{len(docs)} Dokumente sind verlinkt")
    except Exception as e:
        b.add("FEHLER", "Vorlage nicht pruefbar", repr(e))

    # --- Stapelbetrieb: Ketten, Wellen, halber Tarif -------------------
    # Der Stapel rechnet zum halben Preis und kann genau eines nicht: Ein
    # Chunk sieht die Fassung des vorigen nicht, wenn beide im selben
    # Stapel liegen. Ketten halten das aufrecht; was hier schiefgeht,
    # kostet keine Fehlermeldung, sondern die Anschluesse im ganzen Buch.
    try:
        fehler = []

        # Ketten decken den Text genau einmal ab und schneiden zuerst an
        # den Ebenenfugen — dort setzt die Rueckschau ohnehin zurueck.
        kl = G.ketten(20, {10}, 5)
        flach = [i for k in kl for i in k]
        if flach != list(range(20)):
            fehler.append(f"Ketten decken den Text nicht genau einmal ab: "
                          f"{flach}")
        if [k[0] for k in kl] != [0, 5, 10, 15]:
            fehler.append(f"Kettenanfaenge falsch: {[k[0] for k in kl]}")
        if G.zusatzfugen(kl, {10}) != [5, 15]:
            fehler.append(f"bezahlte Naehte falsch gezaehlt: "
                          f"{G.zusatzfugen(kl, {10})}")
        # kette_max 0: nur die Ebenenfugen, also keine bezahlte Naht.
        if G.zusatzfugen(G.ketten(20, {10}, 0), {10}):
            fehler.append("kette_max 0 erzeugt trotzdem bezahlte Naehte")
        if [len(k) for k in G.ketten(20, {10}, 0)] != [10, 10]:
            fehler.append("kette_max 0 trennt nicht an der Ebenenfuge")
        # Gleichmaessig teilen: eine Restkette mit einem Chunk bestimmt
        # die Wellenzahl genauso wie eine volle und stuende sonst still.
        laengen = [len(k) for k in G.ketten(11, set(), 10)]
        if max(laengen) - min(laengen) > 1:
            fehler.append(f"Ketten ungleich lang: {laengen}")
        w = G.wellen(kl)
        if len(w) != 5 or sorted(i for x in w for i in x) != list(range(20)):
            fehler.append(f"Wellen decken den Text nicht ab: {w}")

        # Was die Stapel-API ablehnt, darf gar nicht erst hinausgehen.
        b_a = G.AnthropicBackend()
        roh = b_a.payload(dict(cfg, fallback_modelle="default"),
                          "S", "U", "uebersetzung", "claude-opus-5")
        gefiltert = G.stapel_payload(dict(roh, stream=True))
        for k in ("fallbacks", "stream"):
            if k in gefiltert:
                fehler.append(f"'{k}' geht in den Stapel")
        if gefiltert.get("model") != "claude-opus-5" \
                or "system" not in gefiltert:
            fehler.append("Stapelpayload verliert den eigentlichen Inhalt")
        if G.stapel_payload({"max_tokens": 0})["max_tokens"] != 1:
            fehler.append("max_tokens 0 wird nicht angehoben")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",
                            G.stapel_id_saeubern("ueb/0007 äöü")):
            fehler.append("custom_id entspricht nicht der Anbieterregel")

        # Halber Tarif, und zwar als eigene Buchungszeile.
        t = {"ein": 5.0, "aus": 25.0, "geprueft": True}
        posten = {"ein": 1000000, "aus": 0}
        if abs(G.kosten_dollar(dict(posten, stapel=True), t)
               - G.kosten_dollar(posten, t) * 0.5) > 1e-9:
            fehler.append("Stapeltarif ist nicht der halbe Preis")
        if G.kosten_schluessel("voll", "uebersetzung", "m", True) == \
                G.kosten_schluessel("voll", "uebersetzung", "m"):
            fehler.append("Stapel und synchron teilen sich eine Zeile")

        # Und der Wellenlauf am kleinen Text: Was innerhalb einer Kette
        # steht, bekommt die eigene Rueckschau; ein Kettenanfang nicht —
        # wohl aber den niederlaendischen Quellschluss, der an keiner
        # Uebersetzung haengt. Das ist der ganze Unterschied zum
        # seriellen Lauf, und er muss genau so gross sein.
        import uebersetzung as U_
        with tempfile.TemporaryDirectory() as tmp:
            alt_cwd, alt_stapel, alt_chat = os.getcwd(), G.Stapel, G.chat
            try:
                os.chdir(tmp)
                paras = [f"Zin {i} met genoeg woorden om te tellen hier."
                         for i in range(1, 41)]
                open(G.F["quelle"], "w", encoding="utf-8").write(
                    "\n\n".join(paras))
                json.dump([{"beginn": "Zin 1 met", "ebene": "Rahmen"},
                           {"beginn": "Zin 21 met", "ebene": "Binnen"}],
                          open(G.F["ebenen"], "w", encoding="utf-8"))
                probe = dict(cfg, chunk_words=20, kette_max=5,
                             revision_pass=False, stapel_takt=0,
                             modell_uebersetzung="claude-opus-5")
                gesendet, einzeln = [], []

                def _uebersetzt(user):
                    roh = user.split(
                        "=== ZU ÜBERSETZENDER TEXT ===")[-1].strip()
                    return "\n\n".join(p.replace("Zin", "Satz")
                                       for p in G.absaetze(roh))

                class _Stapel:
                    def __init__(s, cfg_): pass

                    def senden(s, anfragen):
                        gesendet.append(anfragen)
                        return f"b{len(gesendet):04d}"

                    def stand(s, k): return "ended", {}

                    def ergebnisse(s, k):
                        for cid, p in gesendet[int(k[1:]) - 1]:
                            # Ein Eintrag je Welle laeuft ins Leere — der
                            # synchrone Weg muss ihn auffangen.
                            if cid.endswith("0005"):
                                yield cid, "expired", {}
                                continue
                            u = p["messages"][0]["content"]
                            yield cid, "succeeded", {
                                "content": [{"type": "text",
                                             "text": _uebersetzt(u)}],
                                "stop_reason": "end_turn", "usage": {}}
                G.Stapel = _Stapel
                G.chat = lambda c, s_, u, **k: (einzeln.append(u)
                                                or _uebersetzt(u))
                _, chunks, fugen, ebenen = G.quellchunks(
                    probe, paras, [], 20, drucken=lambda *a: None)
                with contextlib.redirect_stdout(io.StringIO()):
                    U_.wellenlauf(probe, {
                        "chunks": chunks, "fugen": fugen, "ebenen": ebenen,
                        "kapitelzeilen": [""] * len(chunks),
                        "daten": {"glossar": {}, "personen": {},
                                  "figuren": {}, "anrede": {},
                                  "leitmotive": {}, "kapitel": {}},
                        "perspektive": None, "p_ueb": "S", "p_rev": "S",
                        "praefix": "", "revision": False})

                erste = dict(gesendet[0])
                if sorted(erste) != ["ueb-0000", "ueb-0005", "ueb-0010",
                                     "ueb-0015"]:
                    fehler.append(f"erste Welle falsch besetzt: "
                                  f"{sorted(erste)}")
                for cid in erste:
                    u = erste[cid]["messages"][0]["content"]
                    if "DEINE ÜBERSETZUNG" in u:
                        fehler.append(f"{cid}: Kettenanfang hat eine "
                                      f"Rueckschau, die es nicht geben kann")
                # Chunk 5 ist eine bezahlte Naht, keine Ebenenfuge: Der
                # Quellschluss steht dort trotzdem zur Verfuegung.
                if "ORIGINAL (nur Kontext)" not in \
                        erste["ueb-0005"]["messages"][0]["content"]:
                    fehler.append("bezahlte Naht bekommt nicht einmal den "
                                  "Quellschluss")
                # Chunk 10 ist die Ebenenfuge — dort ist auch der
                # Quellschluss falsch, die Ebene wechselt.
                if "ORIGINAL (nur Kontext)" in \
                        erste["ueb-0010"]["messages"][0]["content"]:
                    fehler.append("an der Ebenenfuge blutet der Quellkontext "
                                  "in die naechste Ebene")
                zweite = dict(gesendet[1])
                if "DEINE ÜBERSETZUNG" not in \
                        zweite["ueb-0001"]["messages"][0]["content"]:
                    fehler.append("innerhalb der Kette fehlt die Rueckschau")
                if len(einzeln) != 1:
                    fehler.append(f"abgelaufener Eintrag nicht einzeln "
                                  f"nachgeholt: {len(einzeln)}")

                ganz = G.teile_zusammensetzen("uebersetzung", len(chunks))
                z = G.absaetze(ganz or "")
                if len(z) != len(paras) or any(
                        a.replace("Zin", "Satz") != c
                        for a, c in zip(paras, z)):
                    fehler.append(f"Wellenlauf paart falsch: {len(z)} von "
                                  f"{len(paras)} Absätzen")

                # Resume: ein zweiter Durchgang schickt nichts mehr los,
                # weil alle Teile vorliegen.
                vorher = len(gesendet)
                with contextlib.redirect_stdout(io.StringIO()):
                    U_.wellenlauf(probe, {
                        "chunks": chunks, "fugen": fugen, "ebenen": ebenen,
                        "kapitelzeilen": [""] * len(chunks),
                        "daten": {"glossar": {}, "personen": {},
                                  "figuren": {}, "anrede": {},
                                  "leitmotive": {}, "kapitel": {}},
                        "perspektive": None, "p_ueb": "S", "p_rev": "S",
                        "praefix": "", "revision": False})
                if len(gesendet) != vorher:
                    fehler.append("Resume schickt fertige Chunks erneut los")
            finally:
                G.Stapel, G.chat = alt_stapel, alt_chat
                os.chdir(alt_cwd)

        if fehler:
            b.add("FEHLER", "Stapelbetrieb fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Ketten schneiden an den Ebenenfugen, Wellen decken "
                        "den Text, Stapel zahlt den halben Tarif")
    except Exception as e:
        b.add("FEHLER", "Stapelbetrieb nicht pruefbar", repr(e))

    # --- Eine Quelle fuer die Chunkeinteilung --------------------------
    # Drei Schritte stellen Quelle und Fassung nebeneinander: der Lauf,
    # die Leseausgabe und das Screening. Sie hatten drei Nachbauten der
    # Chunkbildung, die gleich aussahen — bis der Lauf ebenen.json las
    # und die beiden anderen weiter nur den Rahmenmarker. Danach stand
    # ueberall der falsche Absatz neben dem falschen, und keine der
    # beiden Spalten sah fuer sich falsch aus.
    try:
        fehler = []
        # 'rahmen_gruppen' ist der Rueckfallpfad und gehoert nur noch
        # nach gemeinsam. Wer ihn direkt ruft, umgeht ebenen.json.
        drin = sorted(os.path.basename(n) for n in _glob_py()
                      if "rahmen_gruppen(" in quelltext(n)
                      and os.path.basename(n) not in ("gemeinsam.py",
                                                      "preflight.py"))
        if drin:
            fehler.append(f"eigener Nachbau der Gruppierung in "
                          f"{', '.join(drin)}")

        # Und die Einteilung folgt ebenen.json, wo es sie gibt.
        paras = ["Erster Absatz der Rahmenebene, lang genug zum Zaehlen.",
                 "Zweiter Absatz derselben Ebene, ebenfalls lang genug.",
                 "Hier beginnt die Binnenerzaehlung mit eigenen Woertern.",
                 "Und sie geht hier noch ein Stueck weiter, mit Worten."]
        with tempfile.TemporaryDirectory() as tmp:
            alt_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                probe = dict(cfg, chunk_words=6, rahmen_marker="#")
                json.dump([{"beginn": "Erster Absatz der",
                            "ebene": "Rahmen"},
                           {"beginn": "Hier beginnt die",
                            "ebene": "Binnen"}],
                          open(G.F["ebenen"], "w", encoding="utf-8"))
                _, chunks, fugen, ebenen = G.quellchunks(
                    probe, paras, [], 6, drucken=lambda *a: None)
                if set(ebenen) != {"Rahmen", "Binnen"}:
                    fehler.append(f"Ebenen kommen nicht aus ebenen.json: "
                                  f"{ebenen}")
                if not fugen:
                    fehler.append("keine Fuge an der Ebenengrenze")
                # Ohne ebenen.json gilt wieder der Marker — der Rueckfall
                # bleibt, er ist nur nicht mehr die zweite Meinung.
                os.remove(G.F["ebenen"])
                _, _, ohne, _ = G.quellchunks(
                    probe, paras, [], 6, drucken=lambda *a: None)
                if ohne:
                    fehler.append("ohne Marker und ohne ebenen.json "
                                  "entsteht trotzdem eine Fuge")
            finally:
                os.chdir(alt_cwd)

        if fehler:
            b.add("FEHLER", "Chunkeinteilung laeuft auseinander",
                  "; ".join(fehler))
        else:
            b.add("OK", "Lauf, Leseausgabe und Screening teilen den Text "
                        "ueber dieselbe Funktion ein")
    except Exception as e:
        b.add("FEHLER", "Chunkeinteilung nicht pruefbar", repr(e))

    # --- Ueberlaengen: gezaehlt, nicht gekappt -------------------------
    # Kappen waere die naheliegende Reaktion und die falsche: Ein Absatz
    # gehoert zusammen, ein geschuetztes Zitat erst recht. Was bleibt, ist
    # zaehlen — und dabei darf weder ein normaler Chunk als uebergross noch
    # ein wirklich uebergrosser als normal durchgehen.
    try:
        fehler = []
        chunks = [("wort " * 800, False),          # genau Ziel
                  ("wort " * 1001, False),         # ueber 1,25×
                  ("wort " * 999, False),          # knapp darunter
                  ("wort " * 3000, True)]          # geschuetztes Zitat
        lang = G.chunk_ueberlaengen(chunks, 800)
        if [i for i, _, _ in lang] != [2, 4]:
            fehler.append(f"falsche Auswahl: {[i for i, _, _ in lang]}")
        if not any(g for _, _, g in lang):
            fehler.append("geschuetzter Chunk nicht als solcher gemeldet")
        if G.chunk_ueberlaengen([("wort " * 800, False)], 800):
            fehler.append("Chunk auf der Zielmarke gilt als uebergross")
        if fehler:
            b.add("FEHLER", "Ueberlaengenzaehler fehlerhaft",
                  "; ".join(fehler))
        else:
            b.add("OK", "Ueberlaengen werden gezaehlt und benannt, "
                        "geschuetzte Chunks getrennt ausgewiesen")
    except Exception as e:
        b.add("FEHLER", "Ueberlaengenzaehler nicht pruefbar", repr(e))

    # --- 'weiter' gibt Pausen frei, sonst nichts -----------------------
    # Der Befehl hakt einen Schritt als erledigt ab, ohne ihn laufen zu
    # lassen. Das ist bei einer Pause genau richtig und bei allem anderen
    # genau falsch: Ein fehlgeschlagener Volllauf, den 'weiter' abhakt,
    # waere ein halbes Buch, das als fertig gilt.
    try:
        import tempfile
        import pipeline as PL
        fehler = []
        gelaufen = []
        echt_run, alt_cwd = PL.cmd_run, os.getcwd()
        # Der Befehl redet; im Selbsttestbericht hat das nichts zu suchen.
        import contextlib, io
        with tempfile.TemporaryDirectory() as tmp, \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                os.chdir(tmp)
                PL.cmd_run = lambda cfg, args: gelaufen.append(True)

                def stand(bis_zu, status="fertig"):
                    """Manifest, in dem alles vor 'bis_zu' erledigt ist."""
                    s = {}
                    for n in PL.NAMEN[:PL.NAMEN.index(bis_zu)]:
                        s[n] = {"status": "fertig"}
                    s[bis_zu] = {"status": status}
                    with open(G.MANIFEST, "w", encoding="utf-8") as f:
                        json.dump({"schritte": s}, f)

                # Pause: wird freigegeben, danach laeuft es weiter.
                stand("PAUSE_review", "wartet")
                PL.cmd_weiter(cfg, argparse.Namespace(hg=False))
                m = json.load(open(G.MANIFEST, encoding="utf-8"))
                if m["schritte"]["PAUSE_review"]["status"] != "fertig":
                    fehler.append("Pause wird nicht freigegeben")
                if not gelaufen:
                    fehler.append("nach der Freigabe laeuft nichts weiter")
                # Die naechste Pause bleibt zu — freigegeben wird eine.
                if m["schritte"].get("PAUSE_pruefung", {}).get("status") \
                        == "fertig":
                    fehler.append("gibt mehr als eine Pause frei")

                # Gegenprobe: ein fehlgeschlagener Schritt ist keine Pause.
                stand("voll", "fehler")
                gelaufen.clear()
                PL.cmd_weiter(cfg, argparse.Namespace(hg=False))
                m = json.load(open(G.MANIFEST, encoding="utf-8"))
                if m["schritte"]["voll"]["status"] == "fertig":
                    fehler.append("hakt einen fehlgeschlagenen Schritt ab")
                if not gelaufen:
                    fehler.append("laeuft nicht weiter, wenn keine Pause "
                                  "offen ist")
            finally:
                PL.cmd_run = echt_run
                os.chdir(alt_cwd)

        if fehler:
            b.add("FEHLER", "'weiter' fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "'weiter' gibt genau eine Pause frei und hakt "
                        "keinen gescheiterten Schritt ab")
    except Exception as e:
        b.add("FEHLER", "'weiter' nicht pruefbar", repr(e))

    # --- Aktive Rollen gegen die Wirklichkeit -------------------------
    # 'aktive_rollen' ist die Grundlage der Kostenschaetzung und des Pings
    # vor dem Lauf. Eine dort fehlende Rolle heisst: kostenlos und
    # ungeprueft. Genau so sind 'zitat' und 'screening' durchgerutscht,
    # nachdem ihre Schritte laengst gebaut waren.
    try:
        import glob as _glob
        fehler = []
        gerufen = set()
        for pfad in _glob.glob(os.path.join(CODE, "*.py")):
            if os.path.basename(pfad) in ("gemeinsam.py", "preflight.py",
                                          "verifikation.py"):
                continue
            quelle = open(pfad, encoding="utf-8").read()
            for m in re.finditer(r'rolle=["\'](\w+)["\']', quelle):
                if m.group(1) in G.ROLLEN:
                    gerufen.add(m.group(1))
        # Gefunden werden nur woertlich hingeschriebene Rollen; 'stil' und
        # 'korrektorat' kommen in lektorat.py aus einer Variablen. Das ist
        # kein Loch, sondern die Grenze: Die Luecken lagen bisher immer
        # dort, wo ein neuer Schritt seine Rolle woertlich nannte.
        aktiv = set(G.aktive_rollen(G.lade_config(pflicht=False)))
        fehlt = gerufen - aktiv
        if fehlt:
            fehler.append(f"wird gerufen, gilt aber als inaktiv: "
                          f"{', '.join(sorted(fehlt))}")
        # Gegenprobe: keine erfundene Rolle in der Liste.
        erfunden = aktiv - set(G.ROLLEN)
        if erfunden:
            fehler.append(f"unbekannte Rolle: {', '.join(sorted(erfunden))}")
        if fehler:
            b.add("FEHLER", "Aktive Rollen unvollstaendig", "; ".join(fehler))
        else:
            b.add("OK", f"Aktive Rollen decken alle {len(gerufen)} wirklich "
                        f"gerufenen Rollen ab")
    except Exception as e:
        b.add("FEHLER", "Aktive Rollen nicht pruefbar", repr(e))

    # --- Paket 9: der Ablaufplan muss zur Schrittliste passen ----------
    # Ein Plan, der einen Schritt nicht kennt, schickt den Leser ins
    # Leere — und das faellt erst auf, wenn jemand danach arbeitet.
    try:
        import pipeline as PL
        plan = quelltext("ABLAUFPLAN.md")
        fehler = []
        fehlend = [n for n in [s[0] for s in PL.SCHRITTE]
                   if f"`{n}`" not in plan]
        if fehlend:
            fehler.append(f"Schritte fehlen im Ablaufplan: "
                          f"{', '.join(fehlend)}")
        haupt = plan.split("## Anhang")[0]
        if re.search(r"(?m)^\s*!?\s*rm\s|\brm -", haupt):
            fehler.append("Der Plan enthaelt einen rm-Befehl")
        for wort in ("VRAM", "ollama ps", "Instanz zerstoeren"):
            if wort.lower() in haupt.lower():
                fehler.append(f"GPU-Kapitel nicht entfernt: '{wort}'")
        if fehler:
            b.add("FEHLER", "Ablaufplan veraltet", "; ".join(fehler))
        else:
            b.add("OK", f"Ablaufplan kennt alle {len(PL.SCHRITTE)} Schritte, "
                        f"kein rm, keine GPU-Kapitel")
    except Exception as e:
        b.add("WARN", "Ablaufplan nicht pruefbar", repr(e))

    # --- Paket 8: drei Signale, getrennt und richtig beschriftet -------
    try:
        import bewertung as BW
        fehler = []
        c = dict(cfg, modell_uebersetzung="claude-opus-5",
                 modell_judge="gemini-3.1-pro-preview")
        fremd = BW.signal_kopf(c, "judge", "Blindes Urteil")
        eigen = BW.signal_kopf(c, "uebersetzung", "Selbstcheck")
        if "gemini-3.1-pro-preview" not in fremd or "Fremdurteil" not in fremd:
            fehler.append(f"Fremdurteil falsch beschriftet: {fremd}")
        if "claude-opus-5" not in eigen or "nachrangig" not in eigen:
            fehler.append(f"Selbstcheck falsch beschriftet: {eigen}")
        # Judge = uebersetzendes Modell: dann ist es KEIN Fremdurteil, und
        # der Bericht muss das sagen, statt ein starkes Signal vorzutaeuschen.
        gleich = BW.signal_kopf(dict(c, modell_judge="claude-opus-5"),
                                "judge", "Blindes Urteil")
        if "Fremdurteil" in gleich:
            fehler.append("gleiches Modell wird als Fremdurteil ausgegeben")
        # Die Tauschlogik muss mit beliebigen Namen richtig zurueckrechnen:
        # Bei Entwurf/Revision ebenso wie bei Basis/Variante. Ein
        # vertauschtes Etikett dreht das Ergebnis um, ohne aufzufallen.
        for namen in (("entwurf", "revision"), ("A", "C")):
            faelle = [(("A", False), namen[0]), (("B", False), namen[1]),
                      (("A", True), namen[1]), (("B", True), namen[0]),
                      (("gleichwertig", False), "gleichwertig")]
            for (besser, getauscht), soll in faelle:
                ist = BW.zurueckrechnen(besser, getauscht, namen)
                if ist != soll:
                    fehler.append(
                        f"Tauschlogik: {namen}, besser={besser}, "
                        f"getauscht={getauscht} -> {ist} statt {soll}")
        # Der Variantenvergleich muss Dialog UND Erzaehlung beurteilen.
        # Bei NL->DE liegt die Schwaeche im Dialog; ein Vergleich ohne ihn
        # beantwortet die Frage halb und sieht ganz aus.
        #
        # Geprueft wird das Verhalten, nicht der Quelltext: Ein Test auf
        # das Wort 'Dialog' bleibt gruen, solange es irgendwo im Modul
        # steht — auch wenn der Dialogteil nie beurteilt wird.
        import contextlib
        import io
        import tempfile
        etiketten = []

        def _fake_chat(cfg_, system, user, temp, **kw):
            etiketten.append(user[:0])       # Inhalt egal
            return '{"besser": "A", "abstand": "gering", "begruendung": "x"}'

        absatz = ("Hij liep naar het huis en keek naar de tuin achter de "
                  "schuur waar de spade nog stond. " * 3)
        rede = ("'Wil je drinken?' vroeg ze zacht aan hem terwijl de emmer "
                "tussen hen in bleef hangen. " * 3)
        with tempfile.TemporaryDirectory() as tmp:
            alt_cwd, alt_chat = os.getcwd(), G.chat
            try:
                os.chdir(tmp)
                os.makedirs("test")
                os.makedirs("testB")
                paras = [absatz] * 8 + [rede] * 8
                open(G.F["quelle"], "w", encoding="utf-8").write(
                    "\n\n".join(paras))
                for d, wort in (("test", "Haus"), ("testB", "Gebäude")):
                    open(f"{d}/{G.F['uebersetzung']}", "w",
                         encoding="utf-8").write(
                        "\n\n".join([f"Er ging zum {wort} und sah den "
                                     f"Garten hinter dem Schuppen, wo der "
                                     f"Spaten noch stand."] * 8
                                    + [f"»Willst du trinken?«, fragte sie "
                                       f"ihn leise im {wort}."] * 8))
                json.dump({"erzaehlung": 8},
                          open("test/teile.json", "w", encoding="utf-8"))
                BW.G.chat = _fake_chat

                gemerkt = []
                echt_blind = BW.blindbewertung

                def _merke(cfg_, quelle, a, bb, n=4, label="", **kw):
                    gemerkt.append(label)
                    return echt_blind(cfg_, quelle, a, bb, n, label, **kw)

                BW.blindbewertung = _merke
                probe_cfg = dict(cfg, export_bewertung=False,
                                 varianten=[{"name": "B",
                                             "chunk_words": 1600}])
                with contextlib.redirect_stdout(io.StringIO()):
                    BW.variantenvergleich(probe_cfg)
                BW.blindbewertung = echt_blind
                if not any("Erzaehlung" in x for x in gemerkt):
                    fehler.append("Variantenvergleich beurteilt die "
                                  "Erzaehlung nicht")
                if not any("Dialog" in x for x in gemerkt):
                    fehler.append("Variantenvergleich beurteilt den Dialog "
                                  "nicht — die Schwaeche des Sprachpaars "
                                  "bleibt ungeprueft")
            except Exception as e:
                fehler.append(f"Variantenvergleich wirft: {e!r}")
            finally:
                BW.G.chat = alt_chat
                os.chdir(alt_cwd)

        if "namen" not in inspect.signature(BW.blindbewertung).parameters:
            fehler.append("blindbewertung kennt keine Fassungsnamen — "
                          "der Variantenvergleich kann nicht urteilen")

        for wort in ("Diff-Statistik", "Fremdurteil", "Selbstpraeferenz"):
            if wort not in BW.GEWICHTUNG:
                fehler.append(f"Gewichtungshinweis nennt '{wort}' nicht")
        # Die alten Etiketten duerfen nirgends mehr stehen.
        quelle = quelltext("bewertung.py")
        for alt in ("lokalen Modells", "Selbstbewertung ist schwach"):
            if alt in quelle.replace("Frueher stand hier", ""):
                fehler.append(f"altes Etikett '{alt}' steht noch im Bericht")
        if fehler:
            b.add("FEHLER", "Judge-Beschriftung fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Bewertung: drei Signale getrennt, jedes mit dem "
                        "Modell beschriftet, das es geliefert hat")
    except Exception as e:
        b.add("FEHLER", "Judge-Routing nicht pruefbar", repr(e))

    # --- Paket 7: Annotation ist berichtend, nicht editierend ----------
    try:
        import annotation as A
        import diffview as D
        fehler = []

        # Der Nachweis, dass der Schritt keinen Schreibzugriff auf Text
        # hat: Keine Textdatei darf in der Freigabeliste stehen, und der
        # Schreibweg muss alles andere abweisen.
        geschuetzt = [G.F[k] for k in ("quelle", "uebersetzung", "entwurf",
                                       "normalisiert", "lektoriert")]
        drin = [p for p in geschuetzt if p in A.SCHREIBBAR]
        if drin:
            fehler.append(f"Textdateien in SCHREIBBAR: {drin}")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for ziel in geschuetzt + ["lektorat_diff.txt", "projekt.json"]:
                try:
                    A.schreiben(os.path.join(tmp, ziel), "x")
                    fehler.append(f"annotation.py konnte {ziel} schreiben")
                except A.SchreibSperre:
                    pass
            try:
                A.schreiben(os.path.join(tmp, A.SCREENING), "# leer\n")
            except Exception as e:
                fehler.append(f"erlaubtes Ziel abgewiesen: {e!r}")

        # Typografie und Interpunktion werden nicht annotiert.
        for kat in ("Typografie", "Interpunktion"):
            if kat in A.SUBSTANZIELL:
                fehler.append(f"{kat} wird faelschlich annotiert")
        for kat in ("Wort", "Wendung", "Teilsatz"):
            if kat not in A.SUBSTANZIELL:
                fehler.append(f"{kat} fehlt in den annotierten Kategorien")

        # Die Kennung muss stabil sein — sonst sind alle Begruendungen
        # nach dem zweiten Lauf verwaist.
        k1 = A.kennung(7, "Wort", "lief", "ging")
        if k1 != A.kennung(7, "Wort", "lief", "ging"):
            fehler.append("Kennung ist nicht stabil")
        if k1 == A.kennung(8, "Wort", "lief", "ging"):
            fehler.append("Kennung unterscheidet Chunks nicht")

        # Eine Liste mit GENAU EINEM Objekt muss eine Liste bleiben. Vorher
        # lag die geschweifte Klammer innerhalb der eckigen, der Parser
        # probierte sie zuerst und lieferte das Objekt — der Aufrufer
        # erwartet eine Liste und verwarf es. Jeder Befund, der allein in
        # seinem Buendel stand, ging so verloren.
        einer = A.json_lesen('[{"chunk": 3, "art": "x", "befund": "y"}]')
        if not isinstance(einer, list) or len(einer) != 1:
            fehler.append(f"einzelner Befund geht verloren: {einer!r}")
        if not isinstance(A.json_lesen('[{"a":1},{"b":2}]'), list):
            fehler.append("Liste mit zwei Objekten wird nicht gelesen")
        if not isinstance(A.json_lesen('```json\n{"a": 1}\n```'), dict):
            fehler.append("Objekt im Codezaun wird nicht gelesen")

        # Gleichlautende Meldungen fallen im Bericht zusammen. Ein
        # wiederkehrender falscher Freund erzeugt sonst 37 Zeilen, und in
        # eine solche Liste sieht niemand mehr hinein.
        wieder = [{"chunk": 4, "art": "falscher Freund",
                   "befund": "»lopen« als »laufen«"},
                  {"chunk": 40, "art": "Falscher Freund ",
                   "befund": "»lopen« als »laufen«."},
                  {"chunk": 7, "art": "Auslassung", "befund": "Satz fehlt"}]
        if len({A.muster(x) for x in wieder}) != 2:
            fehler.append("gleichlautende Meldungen fallen nicht zusammen")
        # Aber nur woertlich Gleiches. Aehnliches zu verschmelzen hiesse
        # raten, und ein verschmolzener Befund verschwindet ungesehen.
        if A.muster({"art": "a", "befund": "»lopen« als »rennen«"}) == \
                A.muster({"art": "a", "befund": "»lopen« als »laufen«"}):
            fehler.append("verschiedene Befunde werden verschmolzen")

        # Das Gedaechtnis gehoert in den User-Prompt. Im System-Prompt
        # waere es ein wachsendes Praefix und zerstoerte bei jedem Aufruf
        # die Cache-Trefferquote.
        g = A.gedaechtnis(wieder)
        if "»lopen«" not in g:
            fehler.append("Gedaechtnis nennt die bisherigen Muster nicht")
        if "BEREITS GEMELDET" in A.SYSTEM_SCREENING:
            fehler.append("Gedaechtnis steht im System-Prompt")
        if A.gedaechtnis([]) != "":
            fehler.append("leeres Gedaechtnis erzeugt trotzdem einen Block")

        # Und der Bericht zeigt die Begruendung genau dann, wenn es eine
        # gibt — dieselbe Kennung auf beiden Seiten.
        html_mit = D.fmt_html("Wort", 7, "Stil", "er", "lief", "ging", "los",
                              "falscher Freund behoben")
        if "falscher Freund behoben" not in html_mit:
            fehler.append("Begruendung erscheint nicht im HTML-Bericht")
        if "grund" in D.fmt_html("Typografie", 1, "det", "a", "-", "–", "b"):
            fehler.append("leere Begruendung erzeugt trotzdem eine Spalte")

        # Resume, Luecken und dieselbe Chunkeinteilung wie der Lauf.
        with tempfile.TemporaryDirectory() as tmp:
            alt_cwd, alt_chat = os.getcwd(), G.chat
            try:
                os.chdir(tmp)
                quelle = [f"Alinea {i} met genoeg woorden erin om te tellen."
                          for i in range(1, 13)]
                open(G.F["quelle"], "w", encoding="utf-8").write(
                    "\n\n".join(quelle))
                probe = dict(cfg, chunk_words=8, rahmen_marker="#")
                _, ch, _, _ = G.quellchunks(
                    probe, G.absaetze("\n\n".join(quelle)), [], 8,
                    drucken=lambda *a: None)
                for i, (t, _) in enumerate(ch):
                    G.teil_schreiben("uebersetzung", i,
                                     t.replace("Alinea", "Absatz"))
                json.dump({"total": len(ch), "chunk_words": 8},
                          open("uebersetzung_state.json", "w"))

                paare = A.chunkpaare(probe)
                # Die Quellseite muss wirklich die Quelle sein. Vorher
                # baute dieser Schritt sie selbst nach — mit dem
                # Rahmenmarker, waehrend der Lauf laengst ebenen.json las.
                if not paare or "Alinea" not in paare[0][1]:
                    fehler.append(f"Quellchunk fehlt im Paar: {paare[:1]}")

                rufe = []

                def _screen(cfg_, sysp, user, **kw):
                    rufe.append(user)
                    if len(rufe) == 3:
                        raise RuntimeError("Netzwerk weg")
                    return json.dumps([{"chunk": 1, "art": "x",
                                        "befund": "y"}])
                G.chat = _screen
                bef, luecken = A.screenen(probe, paare,
                                          drucken=lambda *a: None)
                if len(bef) != 2 or len(luecken) != A.CHUNKS_JE_AUFRUF:
                    fehler.append(f"gescheitertes Buendel falsch verbucht: "
                                  f"{len(bef)} Befunde, {luecken}")
                if "BEREITS GEMELDET" not in (rufe[1] if len(rufe) > 1
                                              else ""):
                    fehler.append("Gedaechtnis erreicht den Aufruf nicht")

                # Zweiter Lauf: nur das gescheiterte Buendel laeuft noch
                # einmal. Ein Absturz bei Aufruf 30 von 37 darf nicht 30
                # Aufrufe kosten.
                vorher = len(rufe)
                G.chat = lambda *a, **k: (rufe.append(a[2]) or
                                          '[{"chunk": 9, "art": "z", '
                                          '"befund": "w"}]')
                bef2, luecken2 = A.screenen(probe, paare,
                                            drucken=lambda *a: None)
                if len(rufe) - vorher != 1:
                    fehler.append(f"Resume wiederholt fertige Buendel: "
                                  f"{len(rufe) - vorher} Aufrufe")
                if luecken2 or len(bef2) != 3:
                    fehler.append(f"Nachlauf unvollstaendig: {len(bef2)} "
                                  f"Befunde, {luecken2}")

                # Eine Luecke steht im Bericht. Ohne sie sieht er
                # vollstaendig aus, obwohl vier Chunks nie geprueft wurden.
                A.screening_schreiben(bef, luecken)
                text = open(A.SCREENING, encoding="utf-8").read()
                if "Nicht geprüft" not in text:
                    fehler.append("uebersprungene Chunks fehlen im Bericht")

                # Der Zwischenstand liegt unter teile/, nicht neben dem
                # Buch — und 'schreiben' nimmt ihn weiterhin nicht an.
                if not os.path.isdir(os.path.join("teile", "screening")):
                    fehler.append("Zwischenstand liegt nicht in teile/")
                try:
                    A.schreiben("screening_0.json", "[]")
                    fehler.append("schreiben() nimmt den Zwischenstand an")
                except A.SchreibSperre:
                    pass

                # Und eine abweichende Quelle bricht ab, statt fremde
                # Absaetze zu vergleichen.
                open(G.F["quelle"], "a", encoding="utf-8").write(
                    "\n\nAlinea 13 met genoeg woorden erin om te tellen.")
                try:
                    A.chunkpaare(probe)
                    fehler.append("geaenderte Quelle wird nicht gemeldet")
                except G.ChunksWeichenAb:
                    pass
            finally:
                G.chat = alt_chat
                os.chdir(alt_cwd)

        if fehler:
            b.add("FEHLER", "Annotation fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Annotation berichtet nur: kein Schreibzugriff auf "
                        "Text, keine Typografie-Begruendungen")
    except Exception as e:
        b.add("FEHLER", "Annotation nicht pruefbar", repr(e))

    # --- Paket 6: Zitate. Der Kern ist, was NICHT passiert. ------------
    try:
        import zitatrecherche as Z
        fehler = []

        # Nicht-niederlaendisches Zitat: bleibt im Original, keine Freigabe.
        eng = {"index": 3, "text": "Only connect.",
               "attribution": "E. M. Forster"}
        Z.uebernehmen(eng, {"sprache": "englisch",
                            "status": "original_belassen",
                            "konfidenz": 0.95})
        if eng.get("original_deutsch") != "Only connect.":
            fehler.append("fremdsprachiges Zitat wird nicht im Original "
                          "uebernommen")
        if eng.get("freigegeben") != "entfaellt":
            fehler.append("Original-Zitat verlangt faelschlich eine Freigabe")

        # Niederlaendisches Zitat: Vorschlag ja, Einsetzen nein.
        nl = {"index": 5, "text": "Alles van waarde is weerloos.",
              "attribution": "Lucebert"}
        Z.uebernehmen(nl, {"sprache": "niederlaendisch", "status": "gefunden",
                           "vorschlag_de": "Alles von Wert ist wehrlos.",
                           "uebersetzer": "Musterfrau", "quelle": "Ausgabe X",
                           "konfidenz": 0.9})
        if nl.get("original_deutsch"):
            fehler.append("FREIGABE UMGANGEN: Recherche setzt den Wortlaut "
                          "direkt in den Zieltext")
        if nl.get("freigegeben") != "nein" or not nl.get("quelle"):
            fehler.append("Review-Eintrag unvollstaendig")

        # Und in den Text kommt es erst mit Freigabe.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            alt = os.getcwd()
            try:
                os.chdir(tmp)
                Z.review_schreiben([eng, nl])
                import io
                import contextlib
                with contextlib.redirect_stdout(io.StringIO()):
                    g, o = Z.freigabe_einlesen({"sheets_id": ""}, [eng, nl])
                if nl.get("original_deutsch") or o != 1:
                    fehler.append("ohne Freigabe gelangt der Vorschlag in "
                                  "den Text")
                text = open(Z.REVIEW, encoding="utf-8").read()
                if "Musterfrau" not in text or "Ausgabe X" not in text:
                    fehler.append("Quelle fehlt in der Review-Liste")
                # Freigabe erteilen wie ein Mensch: die Zelle in der Spalte
                # 'freigegeben' aendern. Eine feste Position im Zeilentext
                # zu ersetzen hat bei der ersten neuen Spalte still
                # danebengegriffen
                # — und dann prueft der Test die Freigabe nicht mehr.
                i_frei = Z.SPALTEN.index("freigegeben")
                neu = []
                for zeile in text.splitlines():
                    f = [x.strip() for x
                         in zeile.strip().strip("|").split("|")]
                    if zeile.startswith("|") and len(f) == len(Z.SPALTEN) \
                            and f[0].isdigit() and f[i_frei] == "nein":
                        f[i_frei] = "ja"
                        zeile = "| " + " | ".join(f) + " |"
                    neu.append(zeile)
                open(Z.REVIEW, "w", encoding="utf-8").write("\n".join(neu))
                with contextlib.redirect_stdout(io.StringIO()):
                    g, o = Z.freigabe_einlesen({"sheets_id": ""}, [eng, nl])
                if nl.get("original_deutsch") != "Alles von Wert ist "\
                                                 "wehrlos." or g != 1:
                    fehler.append(f"Freigabe wird nicht wirksam "
                                  f"({g} gesetzt, {o} offen)")
            finally:
                os.chdir(alt)

        # Der Tab, aus dem die Freigabe gelesen wird, muss auch
        # geschrieben werden. Sonst steht dort eine leere Tabelle, und
        # die Meldung 'im Spreadsheet zu pflegen' ist unwahr.
        class _Blatt:
            def __init__(s):
                s.werte = []

            def clear(s):
                s.werte = []

            def update(s, a, bb):
                if not isinstance(a, list):
                    raise TypeError("alte gspread-Reihenfolge")
                s.werte = a

        blatt = _Blatt()
        import referenz_sync as RS_
        echt_buch = RS_._buch
        try:
            RS_._buch = lambda cfg_: type("B", (), {"worksheet": lambda s, n:
                                                    blatt})()
            nl["freigegeben"] = "ja"
            Z.review_in_tab({"sheets_id": "x" * 30}, [eng, nl])
        finally:
            RS_._buch = echt_buch
        # Vorlage und Schreiber muessen dieselben Spalten meinen. Sie taten
        # es bis August 2026 nicht: Die Vorlage legte fuenf ausgedachte
        # Ueberschriften an, der Schritt schrieb acht andere hinein — und
        # loeschte den Tab vorher, sodass es nie auffiel.
        import referenz_sync as RS_vorlage
        if list(RS_vorlage.TAB_ZITATE[1]) != list(Z.SPALTEN):
            fehler.append(f"Vorlage und Freigabeliste haben verschiedene "
                          f"Spalten: {RS_vorlage.TAB_ZITATE[1]}")
        if "belege" not in Z.SPALTEN:
            fehler.append("Belege fehlen in der Freigabeliste")
        if not blatt.werte or blatt.werte[0] != Z.SPALTEN:
            fehler.append(f"Tab-Kopfzeile fehlt: {blatt.werte[:1]}")
        elif len(blatt.werte) != 3:
            fehler.append(f"{len(blatt.werte)-1} statt 2 Zeilen im Tab")
        elif blatt.werte[2][-1] != "ja":
            fehler.append("erteilte Freigabe geht beim Schreiben verloren")

        # Der Platzhalter bleibt, solange original_deutsch leer ist.
        marken = {2: {"index": 2, "text": "Alles van waarde…",
                      "attribution": "Lucebert", "original_deutsch": None}}
        ganz, bericht = U.zitate_einsetzen("Erster Absatz.\n\nZweiter.",
                                           marken, [])
        if "[[ZITAT NICHT EINGESETZT" not in ganz:
            fehler.append("ohne Wortlaut wird kein Platzhalter gesetzt")

        if fehler:
            b.add("FEHLER", "Zitatfreigabe fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Zitate: Fremdsprache bleibt Original, Vorschlag "
                        "kommt nur mit Freigabe in den Text")
    except Exception as e:
        b.add("FEHLER", "Zitatrecherche nicht pruefbar", repr(e))

    # --- Sheets-Anbindung: Validierung, Abbildung, Rueckfallpfad -------
    # Alles ohne Netz pruefbar, weil die Pruefung auf gelesenen Zeilen
    # arbeitet und nicht auf gspread.
    try:
        import referenz_sync as RS
        fehler = []

        if RS.aktiv({"sheets_id": ""}) or RS.aktiv({}):
            fehler.append("leere sheets_id gilt faelschlich als aktiv")
        if not RS.aktiv({"sheets_id": "1AbC"}):
            fehler.append("gesetzte sheets_id gilt nicht als aktiv")
        if RS.sicherstellen({"sheets_id": ""}, still=True) is not False:
            fehler.append("sicherstellen() ist ohne sheets_id kein No-op")

        # Der Dateiname als sheets_id war der erste Fehler im Echtbetrieb.
        echt = "1a2B3c4D5e6F7g8H9i0JklMnoPqrStUvWxYz"
        for eingabe in (echt,
                        f"https://docs.google.com/spreadsheets/d/{echt}/edit",
                        f"  {echt}  "):
            if RS.sheet_id(eingabe) != echt:
                fehler.append(f"sheet_id({eingabe[:30]}…) liefert "
                              f"{RS.sheet_id(eingabe)!r}")
        for daneben in ("Bucharbeit.gsheet", "Mein Buch", ""):
            try:
                RS.sheet_id(daneben)
                fehler.append(f"'{daneben}' wird faelschlich als ID "
                              f"akzeptiert")
            except RS.SyncFehler:
                pass

        for tab, spalten, ziel, _, pflicht, _z in RS.TABS:
            if ziel not in G.F:
                fehler.append(f"{tab}: Ziel '{ziel}' steht nicht in G.F")
            for s in pflicht:
                if s not in spalten:
                    fehler.append(f"{tab}: Pflichtspalte '{s}' fehlt "
                                  f"in der Spaltenliste")

        # Zeile 2 gut, Zeile 3 ohne Pronomen, Zeile 4 doppelt.
        zeilen = [(2, {"name": "Bennett", "pronomen": "er/ihn"}),
                  (3, {"name": "Babette", "pronomen": ""}),
                  (4, {"name": "Bennett", "pronomen": "er/ihn"})]
        daten, f = RS._pruefen_und_bauen(
            "Personen", zeilen, lambda z: (z["name"], z["pronomen"]),
            ["name", "pronomen"])
        if len(daten) != 1:
            fehler.append(f"Personen: {len(daten)} statt 1 gueltige Zeile")
        if not any("Zeile 3" in m and "pronomen" in m for m in f):
            fehler.append(f"fehlende Pflichtspalte nicht zeilengenau: {f}")
        if not any("Zeile 4" in m and "Zeile 3" not in m and
                   "schon in Zeile 2" in m for m in f):
            fehler.append(f"Doppeleintrag nennt nicht beide Zeilen: {f}")

        # Die Spalte heisst deutsch_ziel, das Feld heisst deutsch — und
        # block_anrede liest 'deutsch'. Beide Seiten aneinandergehalten.
        # Hin und zurueck: Was der Zerleger ins Sheet schreibt, muss der
        # Zeilenbauer wieder zum selben JSON machen. Sonst verliert die
        # Erstbefuellung genau die Felder, die niemand nachzaehlt.
        beispiel = {
            "glossar":    {"moestuin": "Gemüsegarten"},
            "personen":   {"Bennett": "er/ihn"},
            "figuren":    {"Bennett": {"pronomen": "er/ihn",
                                       "rolle": "Erzähler",
                                       "sprache": "lakonisch"}},
            "anrede":     {"Bennett zu Scott": {"figuren": ["Bennett", "Scott"],
                                                "niederlaendisch": "u",
                                                "deutsch": "Sie",
                                                "hinweis": "bleibt"}},
            "leitmotive": {"geen flauw idee": {"vorschlag": "keine blasse "
                                                            "Ahnung",
                                               "haeufigkeit": 12,
                                               "absicht": "Formel"}},
            "kapitel":    {"23 augustus 1919": "Ankunft in Ypern"},
        }
        for tabname, spalten, ziel, bauer, pflicht, zerleger in RS.TABS:
            k, v = list(beispiel[ziel].items())[0]
            zurueck, f2 = RS._pruefen_und_bauen(
                tabname, [(2, dict(zip(spalten, zerleger(k, v))))],
                bauer, pflicht)
            if f2 or zurueck != beispiel[ziel]:
                fehler.append(f"{tabname}: Hin- und Rueckweg unterscheiden "
                              f"sich — {zurueck} statt {beispiel[ziel]}"
                              + (f" ({f2})" if f2 else ""))

        # Leerer Tab ueber gefuellter Datei: sperren. Sonst ersetzt der
        # erste Schritt nach dem Anlegen der Tabs das Glossar durch {}.
        voll = {G.F["glossar"]: {"moestuin": "Gemüsegarten"}}
        if not RS.leerung_pruefen({"glossar": {}},
                                  lesen=lambda p: voll.get(p, {})):
            fehler.append("leerer Tab ueber gefuellter JSON wird nicht "
                          "bemerkt — der naechste Schritt loescht sie")
        if RS.leerung_pruefen({"glossar": {"a": "b"}},
                              lesen=lambda p: voll.get(p, {})):
            fehler.append("gefuellter Tab wird faelschlich als Leerung "
                          "gemeldet")
        if RS.leerung_pruefen({"glossar": {}}, lesen=lambda p: {}):
            fehler.append("leerer Tab ueber leerer Datei wird gemeldet")
        if RS.leerung_pruefen({"glossar": {}},
                              lesen=lambda p: {"_hinweis": "nur Kommentar"}):
            fehler.append("Unterstrich-Schluessel gelten faelschlich als "
                          "Inhalt")

        # Ein optionaler Tab, den es im Spreadsheet nicht gibt, darf den
        # Schritt nicht abbrechen — sonst legt ein nachtraeglich
        # ergaenzter Tab jede bestehende Einrichtung lahm.
        class _OhneTab:
            def worksheet(s, n):
                raise KeyError(n)

        if RS._tab_lesen(_OhneTab(), "Kapitel", ["ueberschrift"]) is not None:
            fehler.append("fehlender optionaler Tab liefert keine Absage")
        try:
            RS._tab_lesen(_OhneTab(), "Glossar", ["nl"])
            fehler.append("fehlender Pflicht-Tab wird nicht gemeldet")
        except RS.SyncFehler:
            pass

        # Erstbefuellung gegen eine Attrappe: schreibt sie ueberhaupt,
        # und laesst sie gefuellte Tabs in Ruhe? Der erste Echtversuch
        # uebertrug nichts, und ohne diesen Fall bleibt offen, ob es an
        # der Logik lag oder am Aufruf.
        class _Blatt:
            def __init__(s, t, werte=None):
                s.title, s.werte = t, list(werte or [])

            def get_all_values(s):
                return s.werte

            def update(s, a, b):
                if not isinstance(a, list):
                    raise TypeError("alte gspread-Reihenfolge")
                s.werte = a

        class _Buch:
            def __init__(s, voll=()):
                s.blaetter = {t: _Blatt(t, [["kopf"], ["schon", "da"]]
                                        if t in voll else [])
                              for t, *_ in RS.TABS}

            def worksheet(s, n):
                return s.blaetter[n]

        # G.lade_json wird gleich ersetzt. RS.G IST das Modul gemeinsam —
        # die Wiederherstellung muss deshalb das Original von VORHER
        # zurueckschreiben. 'RS.G.lade_json = G.lade_json' im finally sah
        # richtig aus und war ein No-op: G.lade_json ist zu dem Zeitpunkt
        # bereits die Attrappe. Sie blieb danach fuer den ganzen Prozess
        # stehen und hat jede spaetere Pruefung, die JSON liest, entwertet.
        echt, buch = RS._buch, _Buch()
        echt_lade = G.lade_json
        try:
            RS._buch = lambda cfg: buch
            RS.G.lade_json = (lambda p, still=False:
                              {"moestuin": "Gemüsegarten"}
                              if p == G.F["glossar"] else {})
            import io
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                RS.erstbefuellung({"sheets_id": "x" * 30})
            g = buch.blaetter["Glossar"].werte
            if g != [["nl", "de", "hinweis"],
                     ["moestuin", "Gemüsegarten", ""]]:
                fehler.append(f"Erstbefuellung schreibt nicht: {g}")
            voll = _Buch(voll={"Glossar"})
            RS._buch = lambda cfg: voll
            with contextlib.redirect_stdout(io.StringIO()):
                RS.erstbefuellung({"sheets_id": "x" * 30})
            if voll.blaetter["Glossar"].werte != [["kopf"], ["schon", "da"]]:
                fehler.append("Erstbefuellung ueberschreibt gefuellte Tabs")
        finally:
            RS._buch = echt
            RS.G.lade_json = echt_lade

        # Der Tab 'Modelle' wird geschrieben und NIE gelesen. Steht er in
        # TABS, liest ihn 'sync' zurueck und die Modellwahl waere die
        # dritte Quelle neben Repo- und Projekt-projekt.json.
        if any(t[0] == "Modelle" for t in RS.TABS):
            fehler.append("'Modelle' steht in TABS und wird damit gelesen")
        if RS.TAB_MODELLE[0] in RS.OPTIONAL:
            fehler.append("'Modelle' ist als Lesetab markiert")

        class _BuchM:
            def __init__(s): s.blaetter, s.neu = {}, []

            def worksheet(s, n):
                if n not in s.blaetter:
                    raise KeyError(n)
                return s.blaetter[n]

            def add_worksheet(s, title, rows, cols):
                s.neu.append(title)
                s.blaetter[title] = _Blatt(title, [])
                return s.blaetter[title]

        bm = _BuchM()
        echt_buch, alt_cwd2 = RS._buch, os.getcwd()
        try:
            RS._buch = lambda cfg: bm
            os.chdir(tempfile.mkdtemp())
            RS.modelle_schreiben(dict(cfg, sheets_id="x" * 30), still=True)
        finally:
            RS._buch = echt_buch
            os.chdir(alt_cwd2)
        geschrieben = bm.blaetter["Modelle"].werte
        if geschrieben[0] != list(RS.TAB_MODELLE[1]):
            fehler.append(f"Kopfzeile falsch: {geschrieben[:1]}")
        rollen_im_tab = {z[0].split("  ")[0] for z in geschrieben[1:] if z}
        if not set(G.ROLLEN) <= rollen_im_tab:
            fehler.append(f"Rollen fehlen im Tab: "
                          f"{sorted(set(G.ROLLEN) - rollen_im_tab)}")
        if not any("nicht gelesen" in " ".join(z) for z in geschrieben if z):
            fehler.append("der Tab sagt nicht, dass er nicht gelesen wird")
        # Ohne sheets_id ein No-op — der Rueckfallpfad bleibt unberuehrt.
        if RS.modelle_schreiben(dict(cfg, sheets_id=""), still=True):
            fehler.append("schreibt trotz leerer sheets_id")

        tab = [t for t in RS.TABS if t[0] == "Anrede"][0]
        anrede, f = RS._pruefen_und_bauen(
            "Anrede",
            [(2, {"beziehung": "Bennett zu Scott", "figuren": "Bennett, Scott",
                  "niederlaendisch": "u", "deutsch_ziel": "Sie",
                  "hinweis": ""})],
            tab[3], tab[4])
        if f:
            fehler.append(f"gueltige Anredezeile abgelehnt: {f}")
        else:
            # Nicht nur 'Block nicht leer' pruefen: block_anrede baut die
            # Zeile auch dann, wenn das Zielfeld fehlt — dann steht dort
            # 'deutsch ' und nichts dahinter. Der Wert muss ankommen.
            block = U.block_anrede("Bennett sah Scott an.",
                                   {"Bennett": "er/ihn", "Scott": "er/ihn"},
                                   anrede)
            if "Sie" not in block:
                fehler.append("aus dem Sheet gebaute anrede.json traegt "
                              "die Zielanrede nicht in den Prompt — "
                              f"Feldnamen weichen ab: {block!r}")

        # Die Anmeldung der VM ist keine Anmeldung. In Colab findet
        # google.auth.default() immer die Compute-Engine-Anmeldung, an der
        # kein Dienstkonto haengt: Sie laesst sich bauen und scheitert
        # erst beim Zugriff — mit einem 404 auf metadata.google.internal,
        # das nach einem Problem des Spreadsheets aussieht. Genau so ist
        # jemand auf die Suche nach einer Freigabe geschickt worden, die
        # laengst erteilt war.
        import types
        class _CE:
            pass
        ce = types.ModuleType("google.auth.compute_engine")
        ce.Credentials = _CE
        ga = types.ModuleType("google.auth")
        ga.compute_engine = ce
        gg = types.ModuleType("google")
        gg.auth = ga
        alt_module = {k: sys.modules.get(k) for k in
                      ("google", "google.auth", "google.auth.compute_engine")}
        echt_colab = G.ist_colab
        try:
            sys.modules.update({"google": gg, "google.auth": ga,
                                "google.auth.compute_engine": ce})
            G.ist_colab = lambda: True
            if RS.anmeldung_taugt(_CE()):
                fehler.append("Metadaten-Anmeldung der VM gilt in Colab als "
                              "Anmeldung")
            if not RS.anmeldung_taugt(object()):
                fehler.append("echte Anmeldung wird in Colab verworfen")
            # Ausserhalb von Colab ist dieselbe Anmeldung der normale Weg
            # einer GCE-Maschine mit Dienstkonto.
            G.ist_colab = lambda: False
            if not RS.anmeldung_taugt(_CE()):
                fehler.append("Dienstkonto einer echten GCE-Maschine wird "
                              "verworfen")
        finally:
            G.ist_colab = echt_colab
            for k, v in alt_module.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

        # Und die Meldung muss auf die Anmeldung zeigen, nicht auf die
        # Freigabe. Eine falsche Fährte kostet hier eine Stunde.
        quelle_rs = quelltext("referenz_sync.py")
        if "metadata.google.internal" not in quelle_rs:
            fehler.append("der Metadaten-404 wird nicht als fehlende "
                          "Anmeldung erkannt")

        if fehler:
            b.add("FEHLER", "Sheets-Anbindung fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Sheets: Validierung zeilengenau, Spaltenabbildung "
                        "passt zum Leser, leere sheets_id bleibt No-op")
    except Exception as e:
        b.add("FEHLER", "Sheets-Anbindung nicht pruefbar", repr(e))

    # Ein gekuerzter Durchgang bekommt Versuche wie ein Netzfehler.
    try:
        c = dict(cfg)
        c["max_retries"] = 3
        faelle = [(1.00, 1, "ok"), (1.00, 3, "ok"),
                  (0.29, 1, "wiederholen"), (1.14, 2, "wiederholen"),
                  (0.29, 3, "verwerfen"), (0.11, 3, "verwerfen")]
        fehler = [f"r={r} Versuch {v}: {L.pass_urteil(r, c, v)} statt {soll}"
                  for r, v, soll in faelle
                  if L.pass_urteil(r, c, v) != soll]
        if fehler:
            b.add("FEHLER", "Urteil ueber Lektoratsdurchgaenge falsch",
                  "; ".join(fehler))
        else:
            b.add("OK", "Gekuerzter Durchgang wird wiederholt, erst der "
                        "letzte Versuch verwirft")
    except Exception as e:
        b.add("FEHLER", "pass_urteil nicht pruefbar", repr(e))

    # Was ein Schritt als Ergebnis ausweist, muss auch im Paket landen.
    # bericht.html wurde erzeugt, gemeldet — und vom Paket vergessen;
    # gemerkt hat es niemand, weil beide Stellen fuer sich stimmten.
    try:
        import paket as P
        fehlt = [d for d in (L.DIFF, L.BERICHT, G.F["lektoriert"],
                             G.F["uebersetzung"])
                 if d not in P.MITNEHMEN]
        if fehlt:
            b.add("FEHLER", "Ergebnisdateien fehlen im Paket",
                  ", ".join(fehlt))
        else:
            b.add("OK", "Paket enthaelt alle ausgewiesenen Ergebnisdateien")
    except Exception as e:
        b.add("FEHLER", "Paketliste nicht pruefbar", repr(e))

    # Nennt ein Metrikname eine Wortliste, muss sie zur Regex passen.
    # Sonst schickt der Bericht den Leser hinter Woertern her, die gar
    # nicht gezaehlt werden.
    try:
        fehler = []
        for name, pat in Q.REGISTER.items():
            m = re.search(r"\(([^)]*)\)\s*$", name)
            if not m:
                continue
            genannt = {w.strip() for w in m.group(1).split(",")}
            g = re.search(r"\(([^)]*)\)", pat)
            gemessen = set(g.group(1).split("|")) if g else set()
            if genannt != gemessen:
                fehler.append(f"{name}: Name nennt {sorted(genannt)}, "
                              f"Regex zaehlt {sorted(gemessen)}")
        if fehler:
            b.add("FEHLER", "Metrikname und Muster weichen ab",
                  "; ".join(fehler))
        else:
            b.add("OK", "Registermetriken: Name und Muster decken sich")
    except Exception as e:
        b.add("FEHLER", "Registermetrik nicht pruefbar", repr(e))

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

    # Am echten Text gefunden: die Quelle setzt Rede in ‘…’, die
    # Zeichenklasse des Anredefilters kannte nur "…" und »…«. Der Abschnitt
    # blieb leer, obwohl der Text 82 Siez-Formen enthaelt.
    try:
        import konkordanz as K
        saetze = G.saetze_nl(
            "‘Zoekt u de weg, meneer?’ vroeg zij. Hij liep verder. "
            "«Hebt u even?» zei de man. „Uw jas, mevrouw.“")
        n = len(K.anredebelege(saetze))
        if n < 3:
            b.add("FEHLER", f"Anredebelege findet {n} statt 3",
                  "Anfuehrungszeichen der Quelle nicht erkannt — "
                  "G.ANFUEHRUNG pruefen.")
        else:
            b.add("OK", "Anredebelege erkennt ‘…’, «…» und „…“")
    except Exception as e:
        b.add("FEHLER", "Anredebelege wirft Ausnahme", repr(e))

    # --- Leseausgabe: die Ausrichtung, und dass Fehlpaarung auffaellt ---
    # Der gefaehrlichste Fehler dort ist keine Ausnahme, sondern ein
    # Dokument, in dem ab Absatz 40 die falschen Saetze nebeneinander
    # stehen. Beide Waechter werden deshalb hier scharf gehalten.
    try:
        import tempfile
        import leseausgabe as LA
        fehler = []
        quelle = ["Eerste alinea van de bron.",
                  "Tweede alinea, iets langer, met meer woorden erin.",
                  "Derde alinea."]
        deutsch = ["Erster Absatz der Quelle.",
                   "Zweiter Absatz, etwas laenger, mit mehr Woertern darin.",
                   "Dritter Absatz."]
        probe = dict(cfg)
        probe["chunk_words"] = 8          # erzwingt mehrere Chunks

        with tempfile.TemporaryDirectory() as tmp:
            alt = os.getcwd()
            try:
                os.chdir(tmp)
                open(G.F["quelle"], "w", encoding="utf-8").write(
                    "\n\n".join(quelle))
                _, _, chunks = LA.quellchunks(probe)
                for i, (qtext, _) in enumerate(chunks):
                    G.teil_schreiben("uebersetzung", i, "\n\n".join(
                        deutsch[quelle.index(p)] for p in G.absaetze(qtext)))
                ganz = G.teile_zusammensetzen("uebersetzung", len(chunks))
                open(G.F["uebersetzung"], "w", encoding="utf-8").write(ganz)
                with open("uebersetzung_state.json", "w") as fh:
                    json.dump({"total": len(chunks)}, fh)

                zeilen, warnung = LA.zeilen_bauen(probe)
                if warnung:
                    fehler.append(f"intakter Stand warnt trotzdem: {warnung}")
                paare = [(z["quelle"], z["uebersetzung"]) for z in zeilen]
                if paare != list(zip(quelle, deutsch)):
                    fehler.append(f"Ausrichtung falsch: {paare}")

                # Gegenprobe 1 (Quellseite): die Quelle waechst, die
                # Chunkfolge passt nicht mehr zu der, die gelaufen ist.
                # Das ist kein Warnfall — eine verschobene, aber
                # ausgelieferte Leseausgabe ist schlimmer als gar keine.
                open(G.F["quelle"], "a", encoding="utf-8").write(
                    "\n\nVierde alinea, die er nog niet was, met genoeg "
                    "woorden om een eigen chunk te vullen.")
                try:
                    LA.zeilen_bauen(probe)
                    fehler.append("geaenderte Quelle wird nicht gemeldet")
                except G.ChunksWeichenAb:
                    pass

                # Gegenprobe 2 (Zielseite): das Manuskript enthaelt einen
                # Absatz, den die Zielspalte aus teile/ nicht hergibt —
                # so sieht ein nachtraeglich geaendertes zitate.json aus.
                open(G.F["quelle"], "w", encoding="utf-8").write(
                    "\n\n".join(quelle))
                open(G.F["uebersetzung"], "a", encoding="utf-8").write(
                    "\n\nEin Absatz, der nur im Manuskript steht.")
                if not LA.zeilen_bauen(probe)[1]:
                    fehler.append("abweichendes Manuskript wird nicht "
                                  "gemeldet")
            finally:
                os.chdir(alt)

        if fehler:
            for f in fehler:
                b.add("FEHLER", "Leseausgabe", f)
        else:
            b.add("OK", "Leseausgabe: Absaetze richtig gepaart, "
                        "Fehlpaarung wird gemeldet")
    except Exception as e:
        b.add("FEHLER", "Leseausgabe wirft Ausnahme", repr(e))

    selbsttest_backends(b)


# ------------------------------------------------------------------
# Backend-Selbsttest: prueft Payloads und Auswertung gegen Attrappen.
#
# Das ersetzt den Mini-Echtlauf ueberall dort, wo keine Schluessel
# vorliegen — und faengt genau die Fehlerklasse, die beim Lesen unsichtbar
# bleibt: ein Sampling-Parameter, der sich in ein Payload schleicht, kostet
# bei Opus 5 und kuenftigen Gemini-Generationen HTTP 400 mitten im Lauf.
# ------------------------------------------------------------------
SAMPLING = ("temperature", "top_p", "top_k", "topP", "topK",
            "generationConfig")


def _schluessel_tief(obj):
    """Alle Schluessel eines verschachtelten Payloads."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _schluessel_tief(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _schluessel_tief(v)


class _Antwort:
    """Attrappe einer requests-Antwort."""

    def __init__(self, status, koerper=None, kopf=None):
        self.status_code = status
        self._koerper = koerper or {}
        self.headers = kopf or {}
        self.text = json.dumps(self._koerper)

    def json(self):
        return self._koerper


def selbsttest_backends(b):
    cfg = dict(G.STANDARD)
    cfg.update({"modell_uebersetzung": "claude-opus-5",
                "modell_begruendung":  "gemini-3.6-flash",
                "effort_uebersetzung": "hoch",
                "effort_begruendung":  "niedrig"})

    # --- Routing: Rolle -> Modell -> Backend ----------------------------
    try:
        fehler = []
        if G.backend_name(G.modell_fuer(cfg, "uebersetzung")) != "anthropic":
            fehler.append("uebersetzung landet nicht bei Anthropic")
        if G.backend_name(G.modell_fuer(cfg, "begruendung")) != "google":
            fehler.append("begruendung landet nicht bei Google")
        # Eine Rolle ohne Modell muss abbrechen statt still zu ersetzen.
        leer = dict(G.STANDARD)
        leer["modell_stil"] = ""
        try:
            G.modell_fuer(leer, "stil")
            fehler.append("leeres modell_stil wird nicht gemeldet")
        except SystemExit:
            pass
        try:
            G.backend_name("mistral-medium-3.5:128b-q8_0")
            fehler.append("unbekannter Anbieter wird nicht gemeldet")
        except SystemExit:
            pass
        if G.effort_fuer(cfg, "begruendung") != "low":
            fehler.append("Effort 'niedrig' wird nicht auf 'low' abgebildet")
        if fehler:
            b.add("FEHLER", "Rollen-Routing falsch", "; ".join(fehler))
        else:
            b.add("OK", "Rollen-Routing und Effort-Abbildung korrekt")
    except Exception as e:
        b.add("FEHLER", "Rollen-Routing wirft Ausnahme", repr(e))

    # --- Anthropic-Payload ---------------------------------------------
    try:
        p = G.AnthropicBackend().payload(cfg, "SYSTEM", "USER",
                                         "uebersetzung", "claude-opus-5")
        schluessel = set(_schluessel_tief(p))
        fehler = []
        drin = schluessel & set(SAMPLING)
        if drin:
            fehler.append(f"Sampling-Parameter im Payload: {sorted(drin)}")
        if p.get("model") != "claude-opus-5":
            fehler.append("Modell nicht aus der Rolle aufgeloest")
        if p.get("output_config", {}).get("effort") != "high":
            fehler.append("Effort fehlt oder ist nicht abgebildet")
        if not p.get("max_tokens"):
            fehler.append("max_tokens fehlt")
        system = p.get("system")
        if not isinstance(system, list) or not system:
            fehler.append("System-Prompt ist keine Blockliste")
        elif system[-1].get("cache_control", {}).get("type") != "ephemeral":
            fehler.append("Cache-Marker fehlt auf dem letzten System-Block")

        # Cache-Lebensdauer: gesetzt wenn konfiguriert, weg wenn nicht.
        # Ein 'ttl' im Payload, das keiner bestellt hat, kostet beim
        # Schreiben doppelt — das faellt sonst nur auf der Rechnung auf.
        marker = (system or [{}])[-1].get("cache_control", {})
        if marker.get("ttl") != "1h":
            fehler.append(f"cache_ttl '1h' kommt nicht im Payload an: "
                          f"{marker.get('ttl')!r}")
        ohne = dict(cfg, cache_ttl="")
        m2 = G.AnthropicBackend().payload(ohne, "S", "U", "uebersetzung",
                                          "claude-opus-5")
        if "ttl" in m2["system"][-1].get("cache_control", {}):
            fehler.append("leeres cache_ttl setzt trotzdem eine Lebensdauer")

        if fehler:
            b.add("FEHLER", "Anthropic-Payload fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Anthropic-Payload: Cache-Marker mit Lebensdauer und "
                        "Effort gesetzt, keine Sampling-Parameter")
    except Exception as e:
        b.add("FEHLER", "Anthropic-Payload wirft Ausnahme", repr(e))

    # --- Cache-Lebensdauer: Preis und Rueckfall -------------------------
    # Sie ist eine Versicherung, kein Sparposten. Zwei Dinge muessen
    # stimmen: Sie darf einen Lauf nicht abbrechen, und sie muss richtig
    # bepreist werden — eine Stunde kostet beim Schreiben doppelt.
    try:
        fehler = []
        if not G.ttl_abgelehnt(G.ApiFehler(
                "HTTP 400: {'error': {'message': 'ttl: unsupported value'}}")):
            fehler.append("Ablehnung der Lebensdauer wird nicht erkannt")
        # Gegenproben: kein zweiter, bezahlter Versuch bei echten Fehlern.
        for text in ("HTTP 400: temperature is not supported",
                     "HTTP 429: rate limit, ttl exceeded",
                     "HTTP 500: interner Fehler"):
            if G.ttl_abgelehnt(G.ApiFehler(text)):
                fehler.append(f"faengt zu weit: {text[:24]}")

        t = G.tarif("claude-opus-5")
        lang = G.kosten_dollar({"cache_schreiben": 1000,
                                "cache_schreiben_1h": 1000}, t)
        kurz = G.kosten_dollar({"cache_schreiben": 1000}, t)
        if abs(lang - 1000 * t["ein"] * 2.0 / 1e6) > 1e-12:
            fehler.append(f"Stunden-Cache falsch bepreist: {lang}")
        if abs(kurz - 1000 * t["ein"] * 1.25 / 1e6) > 1e-12:
            fehler.append(f"Fuenf-Minuten-Cache falsch bepreist: {kurz}")
        # Gemischt: der Rest der Gesamtzahl zaehlt als kurzlebig.
        gemischt = G.kosten_dollar({"cache_schreiben": 1000,
                                    "cache_schreiben_1h": 400}, t)
        soll = (400 * 2.0 + 600 * 1.25) * t["ein"] / 1e6
        if abs(gemischt - soll) > 1e-12:
            fehler.append(f"Mischung falsch bepreist: {gemischt} statt {soll}")

        # Die Aufschluesselung muss aus der Antwort kommen, nicht geraten.
        _, u = G.AnthropicBackend().antwort_lesen(
            {"content": [{"type": "text", "text": "x"}],
             "usage": {"input_tokens": 1, "output_tokens": 2,
                       "cache_read_input_tokens": 3,
                       "cache_creation_input_tokens": 40,
                       "cache_creation": {"ephemeral_1h_input_tokens": 40}}})
        if u.get("cache_schreiben_1h") != 40:
            fehler.append(f"Cache-Aufschluesselung nicht gelesen: {u}")

        if fehler:
            b.add("FEHLER", "Cache-Lebensdauer fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Cache-Lebensdauer: Ablehnung eng erkannt, "
                        "Schreibpreis nach Lebensdauer getrennt")
    except Exception as e:
        b.add("FEHLER", "Cache-Lebensdauer nicht pruefbar", repr(e))

    # --- Gemini-Payload -------------------------------------------------
    try:
        p = G.GeminiBackend().payload(cfg, "SYSTEM", "USER",
                                      "begruendung", "gemini-3.6-flash")
        schluessel = set(_schluessel_tief(p))
        fehler = []
        drin = schluessel & set(SAMPLING)
        if drin:
            fehler.append(f"Sampling-Parameter im Payload: {sorted(drin)}")
        if "system_instruction" not in p:
            fehler.append("system_instruction fehlt")
        if not p.get("contents"):
            fehler.append("contents fehlt")
        if fehler:
            b.add("FEHLER", "Gemini-Payload fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Gemini-Payload: system_instruction gesetzt, "
                        "keine Sampling-Parameter")
    except Exception as e:
        b.add("FEHLER", "Gemini-Payload wirft Ausnahme", repr(e))

    # --- Antwortauswertung gegen Attrappen ------------------------------
    try:
        fehler = []
        text, u = G.AnthropicBackend().antwort_lesen({
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "Hier ist die Übersetzung:\n"
                                                 "Der Hund schläft."}],
            "usage": {"input_tokens": 120, "output_tokens": 30,
                      "cache_read_input_tokens": 900,
                      "cache_creation_input_tokens": 40}})
        if text != "Der Hund schläft.":
            fehler.append(f"Anthropic-Text falsch gesaeubert: {text!r}")
        if (u["ein"], u["aus"], u["cache_lesen"], u["cache_schreiben"]) \
                != (120, 30, 900, 40):
            fehler.append(f"Anthropic-Usage falsch: {u}")

        text, u = G.GeminiBackend().antwort_lesen({
            "candidates": [{"finishReason": "STOP",
                            "content": {"parts": [{"text": "Die Katze."}]}}],
            "usageMetadata": {"promptTokenCount": 55,
                              "candidatesTokenCount": 12}})
        if text != "Die Katze.":
            fehler.append(f"Gemini-Text falsch: {text!r}")
        if (u["ein"], u["aus"]) != (55, 12):
            fehler.append(f"Gemini-Usage falsch: {u}")

        for name, backend_, antwort in (
                ("Anthropic-Ablehnung", G.AnthropicBackend(),
                 {"stop_reason": "refusal",
                  "stop_details": {"category": "cyber"}, "content": []}),
                ("Gemini-Abbruch", G.GeminiBackend(),
                 {"candidates": [{"finishReason": "SAFETY", "content": {}}]})):
            try:
                backend_.antwort_lesen(antwort)
                fehler.append(f"{name} wird nicht als Fehler gemeldet")
            except G.ApiFehler:
                pass
        if fehler:
            b.add("FEHLER", "Antwortauswertung fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Antwortauswertung: Text, Usage und Ablehnungen "
                        "beider Anbieter korrekt")
    except Exception as e:
        b.add("FEHLER", "Antwortauswertung wirft Ausnahme", repr(e))

    # --- Vorbereitungsprompt und Leser muessen dieselbe Form meinen -----
    # Der erste Lauf lieferte {"paare": [...]} und {"leitmotive": [...]}.
    # block_anrede und block_leitmotive lesen flache Abbildungen und
    # ueberspringen alles andere stillschweigend — die Vorschlaege waeren
    # wirkungslos gewesen, ohne dass irgendwo etwas gemeldet haette.
    try:
        import vorbereitung as V
        alle = " ".join(a for _, _, a, _ in V.LIEFERUNGEN)
        fehlt = [f for f in ("figuren", "niederlaendisch", "deutsch",
                             "vorschlag", "pronomen", "perspektive")
                 if f not in alle]
        if fehlt:
            b.add("FEHLER", "Vorbereitungsprompt nennt Pflichtfelder nicht",
                  f"fehlt: {', '.join(fehlt)}\n"
                  f"           block_anrede/block_leitmotive lesen genau "
                  f"diese Namen.")
        else:
            b.add("OK", "Vorbereitungsprompt beschreibt die Form, die "
                        "uebersetzung.py wirklich liest")
    except Exception as e:
        b.add("WARN", "Vorbereitungsprompt nicht pruefbar", repr(e))

    # --- saeubern darf Codebloecke nicht zerlegen -----------------------
    # vorbereitung.py laesst eine Antwort schreiben, die selbst Codebloecke
    # enthaelt. saeubern() schneidet den aeusseren Zaun ab — richtig fuer
    # uebersetzte Prosa, zerstoerend hier: die inneren Zaeune bleiben
    # unpaarig zurueck und die Datei ist nicht mehr auswertbar.
    try:
        antwort = {"stop_reason": "end_turn", "usage": {},
                   "content": [{"type": "text", "text":
                                "```markdown\n## Übersetzung\n\nRegel.\n```\n"
                                "\n```json\n{\"a\": 1}\n```"}]}
        gesaeubert, _ = G.AnthropicBackend().antwort_lesen(dict(antwort))
        roh, _ = G.AnthropicBackend().antwort_lesen(dict(antwort), roh=True)
        fehler = []
        if len(re.findall(r"(?m)^```", roh)) != 4:
            fehler.append("roh=True veraendert die Zaeune")
        if len(re.findall(r"(?m)^```", gesaeubert)) != 2:
            fehler.append("saeubern schneidet nicht mehr wie bisher")
        if fehler:
            b.add("FEHLER", "Rohausgabe fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "roh=True laesst Codebloecke unangetastet, "
                        "saeubern bleibt fuer Prosa unveraendert")
    except Exception as e:
        b.add("FEHLER", "Rohausgabe wirft Ausnahme", repr(e))

    # --- Der Rueckfallschluessel ist weg, niemand darf ihn noch lesen ---
    # uebersetzung.py meldete im Kopf 'cfg["modell"]' — den Ollama-Namen —
    # obwohl ueber die Rolle laengst Opus 5 lief. Der Lauf war richtig, die
    # Anzeige log. Seit dem Wegfall des Ollama-Pfads gibt es den Schluessel
    # gar nicht mehr: derselbe Zugriff waere jetzt ein KeyError mitten im
    # Lauf. Payloadtests finden so etwas nicht, ein Blick in die Quelle
    # schon.
    # Die erste Fassung sah nur nach cfg['modell'] und nur in
    # print-Zeilen. Damit ist cfg['temperature_uebersetzung'] in
    # bewertung.py durchgerutscht und haette den Export mit einem
    # KeyError beendet. Jetzt: alle entfallenen Schluessel, jede Zeile.
    try:
        schuldig = []
        entfallen = sorted(set(ENTFALLEN)
                           | {"temperature_uebersetzung",
                              "temperature_revision", "temperature_stil",
                              "temperature_korrektorat"})
        for datei in sorted(_glob_py()):
            name = os.path.basename(datei)
            if name in ("preflight.py", "gemeinsam.py"):
                continue          # hier stehen die Listen selbst
            for nr, zeile in enumerate(open(datei, encoding="utf-8"), 1):
                for k in entfallen:
                    if f'cfg["{k}"]' in zeile or f"cfg['{k}']" in zeile:
                        schuldig.append(f"{name}:{nr} -> {k}")
        if schuldig:
            b.add("FEHLER", "Zugriff auf entfallene Konfigurationsschluessel",
                  "\n           ".join(schuldig)
                  + "\n           Die gibt es nicht mehr — der Zugriff ist "
                    "ein KeyError mitten im Lauf.")
        else:
            b.add("OK", f"Kein Skript liest einen der "
                        f"{len(entfallen)} entfallenen Schluessel")
    except Exception as e:
        b.add("FEHLER", "Entfallene Schluessel nicht pruefbar", repr(e))

    # --- Retry und Backoff ----------------------------------------------
    try:
        pausen, versuche = [], []

        def post():
            versuche.append(1)
            if len(versuche) == 1:
                return _Antwort(429, {"error": "rate"}, {"retry-after": "3"})
            if len(versuche) == 2:
                return _Antwort(503, {"error": "weg"})
            return _Antwort(200, {"ok": True})

        r = G.sende(post, 4, schlafen=pausen.append)
        fehler = []
        if r.status_code != 200:
            fehler.append("kein Erfolg nach zwei Wiederholungen")
        if len(pausen) != 2:
            fehler.append(f"{len(pausen)} statt 2 Pausen")
        elif abs(pausen[0] - 3.0) > 0.01:
            fehler.append(f"'retry-after' ignoriert (wartete {pausen[0]:.1f}s)")
        elif not 4.0 <= pausen[1] <= 4.6:
            fehler.append(f"Backoff falsch ({pausen[1]:.1f}s statt ~4s)")

        # 400 ist ein Anwendungsfehler: sofort melden, nicht wiederholen.
        pausen2 = []
        try:
            G.sende(lambda: _Antwort(400, {"error": "kaputt"}), 4,
                    schlafen=pausen2.append)
            fehler.append("HTTP 400 wird nicht sofort gemeldet")
        except G.ApiFehler:
            if pausen2:
                fehler.append("HTTP 400 wird faelschlich wiederholt")
        if fehler:
            b.add("FEHLER", "Retry-Verhalten falsch", "; ".join(fehler))
        else:
            b.add("OK", "Retry: 'retry-after' beachtet, Backoff bei 5xx, "
                        "kein Wiederholen bei 400")
    except Exception as e:
        b.add("FEHLER", "Retry-Selbsttest wirft Ausnahme", repr(e))


# ==================================================================
def pruefe_belegung(cfg, b):
    """Welche Rolle laeuft ueber welches Modell und welchen Anbieter."""
    b.abschnitt("Modellbelegung")
    for rolle in G.aktive_rollen(cfg):
        modell = G.modell_fuer(cfg, rolle)
        anbieter = G.backend_name(modell)
        b.add("INFO", f"  {rolle}",
              f"{modell} ({anbieter}, Effort {G.effort_fuer(cfg, rolle)})")


def pruefe_api(cfg, b, backends, ping):
    """Schluessel und Erreichbarkeit der genutzten API-Anbieter.

    Der Ping schickt genau einen Token — er kostet praktisch nichts und
    faengt abgelaufene Schluessel ab, bevor ein Volllauf startet."""
    b.abschnitt("API-Anbieter")
    if G.ist_colab():
        b.add("INFO", "Laufumgebung", "Google Colab (Secrets ueber userdata)")
    ok = True
    for anbieter in sorted(backends & {"anthropic", "google"}):
        var, secret = G.SCHLUESSEL[anbieter]
        if not G.api_schluessel(anbieter, still=False):
            b.add("FEHLER", f"Schluessel fuer {anbieter} fehlt",
                  f"Colab: Secret '{secret}' hinterlegen und der Zelle "
                  f"Zugriff geben.\n           "
                  f"Sonst: export {var}=...")
            ok = False
            continue
        b.add("OK", f"Schluessel fuer {anbieter} vorhanden")
        if not ping:
            continue
        rolle = next(r for r in G.aktive_rollen(cfg)
                     if G.backend_name(G.modell_fuer(cfg, r)) == anbieter)
        modell = G.modell_fuer(cfg, rolle)
        probe = dict(cfg)
        probe["max_tokens_api"] = 1
        try:
            G.BACKENDS[anbieter].chat(probe, "Antworte mit OK.", "OK",
                                      rolle=rolle, modell=modell)
            b.add("OK", f"{modell} antwortet")
        except SystemExit:
            raise
        except Exception as e:
            if "HTTP 404" in str(e):
                # Ein Modellname, den der Anbieter nicht kennt, scheitert
                # jedes Mal — das darf keinen Volllauf starten lassen.
                b.add("FEHLER", f"Modell '{modell}' existiert nicht",
                      f"Rolle '{rolle}'. Verfuegbare Namen zeigt\n"
                      f"           python3 verifikation.py")
                ok = False
            else:
                # Ein am Limit abgeschnittener Ein-Token-Ping ist kein Fehler.
                b.add("WARN", f"Ping an {modell} ohne verwertbare Antwort",
                      f"{e}\n           Der Schluessel ist da; die Anfrage "
                      f"selbst wird im Lauf erneut versucht.")
    return ok


# Rollen, die das Buch chunkweise durcharbeiten: je Chunk ein Aufruf mit
# demselben System-Prompt. Alle anderen rufen einmal oder wenige Male.
CHUNKROLLEN = ("uebersetzung", "revision", "stil", "korrektorat")

# Rollen, die serverseitige Werkzeuge rufen. Deren Preis haengt nicht an
# Token, sondern an der Zahl der Aufrufe — ohne diese Liste faellt er in
# der Schaetzung unter den Tisch.
SUCHROLLEN = ("zitat",)

# Gemessen am Lauf 1919 (Opus 5, effort 'hoch'): 4110 Ausgabetoken je Chunk
# bei rund 1450 Token deutschem Text. Knapp zwei Drittel der Ausgabe sind
# Denkschritte — und die stehen auf derselben Rechnung wie der Text. Wer
# das weglaesst, schaetzt die Ausgabe um den Faktor drei zu niedrig.
DENKFAKTOR = 2.8

# Referenzbloecke und Rueckschau im User-Prompt, wenn sich der Kopf nicht
# bauen laesst (die JSONs entstehen erst in der Vorbereitung). Gemessen:
# rund 2100 Token je Chunk bei 800 Quellwoertern.
KOPF_TOKEN = 2100


def _kosten_grundlagen(cfg, text):
    """(Chunkzahl, System-Token je Rolle, Token eines Chunks, gezaehlt?).

    Wo der Anbieter zaehlt, wird nicht geschaetzt: 'count_tokens' ist
    kostenlos und kennt den Tokenizer, den das Modell wirklich benutzt."""
    import uebersetzung as U
    import lektorat as L

    chunks = G.chunks_bauen(G.absaetze(text), cfg["chunk_words"])
    n = max(1, len(chunks))
    probe = chunks[0][0] if chunks else text[:4000]

    p_ueb, p_rev = U.prompts(cfg)
    p_stil, p_korr = L.prompts(cfg)
    system = {"uebersetzung": p_ueb, "revision": p_rev,
              "stil": p_stil, "korrektorat": p_korr}

    faktor = G.token_faktor(G.lade_json(G.MANIFEST, still=True))
    gezaehlt = True

    # Getrennt zaehlen statt subtrahieren: einmal der System-Prompt mit
    # einem Alibi-Nutzertext, einmal der Chunk ohne System-Prompt. Die
    # Handvoll Token Nachrichtenruestung faellt gegen 800 Woerter nicht ins
    # Gewicht — eine Differenz aus zwei Schaetzungen dagegen schon.
    z = G.tokens_zaehlen(cfg, "uebersetzung", "-", probe)
    if z is None:
        gezaehlt, chunk_token = False, len(probe.split()) * faktor
    else:
        chunk_token = z

    st = {}
    for rolle, s in system.items():
        z = G.tokens_zaehlen(cfg, rolle, s, "-")
        if z is None:
            gezaehlt = False
            st[rolle] = len(s.split()) * faktor
        else:
            st[rolle] = z
    return n, st, chunk_token, gezaehlt, faktor


def pruefe_kosten(cfg, b, text):
    """Schaetzung vor dem Volllauf. Lieber zu hoch als zu niedrig.

    Drei Dinge, die die frueheren Schaetzungen zu niedrig gemacht haben und
    hier deshalb einzeln stehen: Der System-Prompt geht in JEDEN Chunk (er
    ist zwischengespeichert, aber nicht kostenlos), die Denkschritte machen
    den groesseren Teil der Ausgabe aus, und die Rollen 'zitat' und
    'screening' tauchten gar nicht auf."""
    b.abschnitt("Kostenschaetzung")
    woerter = len(text.split())
    try:
        n, system_token, chunk_token, gezaehlt, faktor = \
            _kosten_grundlagen(cfg, text)
    except Exception as e:
        b.add("WARN", "Kostenschaetzung nicht moeglich", repr(e))
        return

    # Uebergrosse Chunks werden bewusst nicht gekappt (Absatzgrenzen haben
    # Vorrang). Sichtbar muessen sie trotzdem sein: Sie sind die Ursache
    # hinter verworfenen Laengenverhaeltnissen im Lauf.
    lang = G.chunk_ueberlaengen(G.chunks_bauen(G.absaetze(text),
                                               cfg["chunk_words"]),
                                cfg["chunk_words"])
    if lang:
        groesster = max(w for _, w, _ in lang)
        art = ("WARN" if groesster > cfg["chunk_words"] * 1.8 else "INFO")
        b.add(art, f"{len(lang)} uebergrosse Chunks",
              f"ueber {cfg['chunk_words'] * G.UEBERLAENGE:.0f} Woertern, "
              f"groesster {groesster}. Nicht gekappt — ein Absatz gehoert "
              f"zusammen. Erwarte dort eher verworfene "
              f"Laengenverhaeltnisse.")
    else:
        b.add("OK", f"Keine uebergrossen Chunks "
                    f"(ueber {cfg['chunk_words'] * G.UEBERLAENGE:.0f} "
                    f"Woertern)")

    b.add("INFO", "Grundlage",
          f"{n} Chunks à {cfg['chunk_words']} Woerter, "
          + ("Tokenzahlen beim Anbieter gezaehlt"
             if gezaehlt else f"{faktor} Token je Wort geschaetzt "
                              f"(kein Schluessel oder Zaehler nicht "
                              f"erreichbar)"))
    b.add("INFO", "Denkanteil",
          f"Ausgabe = {DENKFAKTOR}× Text. Gemessen am Lauf 1919 unter "
          f"Opus 5 bei effort 'hoch'; fuer andere Stufen ist der Wert "
          f"nicht gemessen.")

    # Nicht jede Rolle sieht das ganze Buch, und bei keiner von ihnen haengt
    # die Ausgabelaenge an der Eingabelaenge: Ein Glossar aus 20 000 Woertern
    # Analysepaket ist zwei Seiten lang, nicht zwanzig. Deshalb stehen
    # Eingabe und Ausgabe hier getrennt.
    # (Aufrufe, Kopf im System-Prompt, Eingabe je Aufruf, Ausgabe je Aufruf)
    # — alles in Quellwoertern, abgelesen am Lauf 1919 und aufgerundet.
    einmalig = {
        # Acht Lieferungen plus Anweisungsentwurf; die Befunde stehen im
        # System-Prompt und sind ab dem zweiten Aufruf zwischengespeichert.
        "vorbereitung": (9, min(woerter, 20000), 400, 1500),
        "zitat":        (1, 0, min(woerter, 4000), 1500),
        # Ein Aufruf ueber die Absatzanfaenge des ganzen Buches.
        "ebenen":       (1, 0, len(G.absaetze(text)) * 12, 300),
        # Je 20 Aenderungen ein Aufruf; grob ein Buendel je zwei Chunks.
        "begruendung":  (max(1, n // 2), 0, 400, 300),
        # Vier Chunkpaare je Aufruf, Quelle und Ziel nebeneinander.
        "screening":    (max(1, n // 4), 0, 8 * cfg["chunk_words"], 200),
        # Vier Absatzpaare je Auszug, zwei Auszuege.
        "judge":        (8, 0, 800, 250),
    }

    summe, unsicher, ohne_tarif = 0.0, False, []
    for rolle in G.aktive_rollen(cfg):
        modell = G.modell_fuer(cfg, rolle)
        t = G.tarif(modell)
        if not t:
            ohne_tarif.append(modell)
            continue
        if rolle in CHUNKROLLEN:
            s = system_token.get(rolle, 0)
            # Der System-Prompt wird einmal geschrieben und n−1 mal gelesen.
            # Je Chunk: Quelltext + Referenzbloecke + Rueckschau (Quelle
            # und eigene Fassung) + Vorwegschau.
            kontext = (2 * cfg["context_words"]
                       + int(cfg.get("context_words_voraus", 0) or 0)) * faktor
            ein = (chunk_token + KOPF_TOKEN + kontext) * n
            schreiben, lesen = s, s * (n - 1)
            aus = chunk_token * n * DENKFAKTOR
            zusatz = f"{n} Chunks, System-Prompt {s:,.0f} Token"
        elif rolle not in einmalig:
            # Ein modellrufender Schritt ohne Umfangsangabe waere hier
            # kostenlos. Melden statt abbrechen — der Preflight soll den
            # Rest trotzdem schaetzen.
            b.add("WARN", f"Rolle '{rolle}' fehlt in der Kostenschaetzung",
                  "Sie ruft ein Modell, taucht hier aber nicht auf. "
                  "Umfang in preflight.pruefe_kosten ergaenzen.")
            continue
        else:
            rufe, kopf, w_ein, w_aus = einmalig[rolle]
            ein = rufe * w_ein * faktor
            schreiben = kopf * faktor
            lesen = kopf * faktor * max(0, rufe - 1)
            aus = rufe * w_aus * faktor * DENKFAKTOR
            zusatz = (f"{rufe} Aufrufe à rund {w_ein} Woerter ein, "
                      f"{w_aus} aus")
        # Die Zitatrecherche zahlt neben den Token je Suche. Bei sechs
        # Suchen je Zitat ist das kein Rundungsfehler mehr, und es ist der
        # einzige Posten, den keine Tokenzahl verraet.
        suchen = 0
        if rolle in SUCHROLLEN:
            w = G.websuche_werkzeug(cfg)
            if w:
                suchen = einmalig[rolle][0] * w[0]["max_uses"]
                zusatz += f", bis zu {suchen} Suchen"
        d = G.kosten_dollar({"ein": ein, "aus": aus, "cache_lesen": lesen,
                             "cache_schreiben": schreiben,
                             "suchen": suchen,
                             "cache_schreiben_1h": schreiben
                             if G.cache_ttl(cfg) == "1h" else 0}, t)
        summe += d
        unsicher = unsicher or not t["geprueft"]
        b.add("INFO", f"  {rolle}", f"{modell}: rund {d:.2f} $  ({zusatz})")

    if ohne_tarif:
        b.add("WARN", "Kein hinterlegter Tarif",
              f"{', '.join(sorted(set(ohne_tarif)))} — Schaetzung "
              f"unvollstaendig. Tarif in gemeinsam.TARIFE ergaenzen.")
    b.add("INFO", "Summe (grob)",
          f"rund {summe:.2f} $ fuer {woerter} Woerter "
          f"({summe / max(1, woerter) * 1000:.2f} $ je 1000 Woerter)")
    # Die Richtung des Fehlers gehoert dazu, sonst liest jemand die Zahl
    # als Punktschaetzung. Nachgerechnet an 1919: die Schaetzung lag rund
    # 20 % ueber der gemessenen Uebersetzung und Revision, im Lektorat
    # mehr, weil dort weder Denkanteil noch Ausgabelaenge gemessen sind.
    b.add("INFO", "Richtung des Fehlers",
          "Die Schaetzung faellt bewusst zu hoch aus. Am Buch 1919 lag "
          "sie fuer Uebersetzung und Revision rund 20 % ueber dem "
          "gemessenen Wert, im Lektorat deutlicher. Was der Lauf "
          "wirklich kostet, steht danach in 'pipeline.py status'.")
    if unsicher:
        b.add("WARN", "Teil der Tarife ist nicht verifiziert",
              "Google-Tarife stehen mit Datum 31.07.2026 vorgemerkt und "
              "werden in Paket 2 gegen die Anbieterdoku geprueft.")


# ==================================================================
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
        # Seit G.absaetze() die Zeilenenden vereinheitlicht, ist das kein
        # Grund mehr fuer eine Fehlmessung — aber die Datei schreibt sich
        # danach mit gemischten Enden weiter, und das sieht in jedem Diff
        # nach einer Aenderung aus, die keine ist.
        b.add("INFO", "Windows-Zeilenenden",
              "Die Absatztrennung kommt damit zurecht. Sauberer wird es "
              "mit:\n           sed -i 's/\\r$//' input.txt")
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
        # Die haeufigste Ursache benennen statt sie raten zu lassen: Ein
        # Text mit vielen Zeilenumbruechen, aber kaum Leerzeilen, ist
        # zeilenweise umbrochen (Word-Export, PDF-Extraktion) — dort
        # trennt keine Leerzeile die Absaetze, und der Hinweis
        # 'muessen durch Leerzeilen getrennt sein' laesst offen, was zu
        # tun ist.
        zeilen = text.count("\n")
        verdacht = ("\n           Der Text hat "
                    f"{zeilen} Zeilenumbrueche, aber nur {len(paras)} "
                    f"Absaetze: Er ist vermutlich zeilenweise umbrochen "
                    f"(Word- oder PDF-Export).\n"
                    "           Absaetze brauchen eine LEERZEILE "
                    "dazwischen, kein einfaches Zeilenende."
                    if zeilen > 4 * len(paras) else "")
        b.add("FEHLER", f"Nur {len(paras)} Absaetze erkannt",
              "Absaetze muessen durch Leerzeilen getrennt sein."
              + verdacht + "\n           head -c 600 input.txt")
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

    # Wie sind die Erzaehlebenen in DIESEM Text ausgezeichnet? Die Frage
    # steht hier, weil sie hier zum ersten Mal beantwortbar ist — und
    # weil sie beim Buch 1919 niemand gestellt hat: fuenf Ebenen im
    # Stilprofil, ein Marker, den der Autor nie benutzt, eine Gruppe ueber
    # 147 Chunks. Die deutsche Rueckschau lief ueber jeden Wechsel hinweg,
    # und keine buchweite Metrik konnte das sehen.
    marker = str(cfg.get("rahmen_marker", "") or "").strip()
    treffer = sum(1 for p in paras if marker and p.strip() == marker)
    if not marker:
        b.add("INFO", "Kein Rahmenmarker eingestellt",
              "Die Erzaehlebenen kommen dann ausschliesslich aus "
              "ebenen.json (vorbereitung.py --nur ebenen).")
    elif treffer:
        b.add("OK", f"Rahmenmarker »{marker}«: {treffer} Wechsel im Text",
              "Er gilt als Rueckfall, wenn ebenen.json fehlt.")
    else:
        b.add("WARN", f"Rahmenmarker »{marker}« kommt im Text nicht vor",
              "Erzaehlebenen koennen dann NUR aus ebenen.json kommen.\n"
              "           Hat der Text mehrere Ebenen (Rahmen, Rueckblende, "
              "Einschub),\n"
              "           entstehen ohne sie null Fugen — Tempus und Person "
              "der einen\n"
              "           Ebene bluten dann in die andere, und keine "
              "buchweite Zahl\n"
              "           zeigt es an. Genau so ist der Lauf 1919 gelaufen.\n"
              "           Siehe NEUES_BUCH.md, Punkt 3.")
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
    "stilprofil": ("'ton' gefuellt, 'perspektive' als Objekt",
                   lambda d: bool(str(d.get("ton", "")).strip())
                   and isinstance(d.get("perspektive", {}), dict)),
    "kapitel":    ("je Ueberschrift eine Zeile", lambda d: all(
        isinstance(v, str) for k, v in d.items() if not k.startswith("_"))),
}


def pruefe_ebenen(cfg, b):
    """ebenen.json gegen Text und Stilprofil — die Pruefung fuer PAUSE_review.

    Sie beantwortet, was sich ohne Lesen entscheiden laesst: Kommt jeder
    'beginn' im Text vor, sind die Namen die des Stilprofils, wie viele
    Fugen entstehen. Ob die Fuge an der RICHTIGEN Stelle sitzt, steht im
    Text und muss gelesen werden — dafuer ist die Pause da."""
    pfad = G.F["ebenen"]
    p = G.lade_json(G.F["stilprofil"], still=True).get("perspektive")
    mehrere = isinstance(p, dict) and len(p) > 1

    if not os.path.exists(pfad):
        if mehrere:
            # Genau der Fall des Buchs 1919: mehrere Ebenen im Profil,
            # keine Fuge im Lauf. Ohne diese Meldung faellt es nirgends
            # auf — die buchweite Perfektquote kann es nicht sehen.
            b.add("WARN", f"{pfad} fehlt, aber das Stilprofil kennt "
                          f"{len(p)} Erzaehlebenen",
                  f"Ohne Fugen laeuft die deutsche Rueckschau ueber jeden "
                  f"Ebenenwechsel hinweg.\n"
                  f"           Erzeugen: python3 vorbereitung.py --nur "
                  f"ebenen\n"
                  f"           Traegt der Text den Marker "
                  f"»{cfg['rahmen_marker']}«, genuegt der auch.")
        else:
            b.add("INFO", f"{pfad} fehlt",
                  "Wird in der Vorbereitung erzeugt; ohne sie gilt der "
                  "rahmen_marker.")
        return

    ebenen = G.ebenen_lesen(pfad)
    maengel = G.ebenen_maengel(ebenen, p)
    if maengel:
        b.add("FEHLER", f"{pfad} fehlerhaft", "\n           ".join(maengel[:8]))
        return
    if not os.path.exists(G.F["quelle"]):
        b.add("INFO", f"{pfad}: {len(ebenen)} Eintraege, "
                      f"Text fehlt zum Abgleich")
        return

    paras = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
    anfaenge, unbekannt = G.ebenen_anfaenge(paras, ebenen)
    if unbekannt:
        b.add("FEHLER", f"{pfad}: {len(unbekannt)} Eintrag/Eintraege "
                        f"kommen so nicht im Text vor",
              "\n           ".join(unbekannt[:6])
              + "\n           'beginn' muss die ersten Woerter eines "
                "Absatzes im Wortlaut der Quelle sein — sonst saesse die "
                "Fuge am falschen Absatz.")
        return
    benannt = sorted({n for _, n in anfaenge})
    ungenutzt = [n for n in (p or {}) if n not in benannt]
    b.add("OK", f"{pfad}: {len(anfaenge)} Fugen, {len(benannt)} Ebenen",
          ", ".join(benannt)
          + (f"\n           Im Stilprofil, aber nicht im Text: "
             f"{', '.join(ungenutzt)}" if ungenutzt else ""))
    if anfaenge and anfaenge[0][0] > 0:
        b.add("INFO", f"Vor der ersten Fuge stehen {anfaenge[0][0]} "
                      f"Absaetze",
              "Sie bilden eine eigene, unbenannte Gruppe. Fehlt dort ein "
              "Eintrag?")


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

    pruefe_ebenen(cfg, b)

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
    unbekannt = [p for p in cfg["lektorat_passes"]
                 if p not in ("det", "stil", "korrektorat")]
    if unbekannt:
        b.add("FEHLER", f"Unbekannte Lektoratsstufe: {', '.join(unbekannt)}")
    else:
        b.add("OK", "Lektoratsfolge: " + " -> ".join(cfg["lektorat_passes"]))
    # Varianten: Ein Schluessel, den 'variante_anwenden' nicht kennt, wird
    # ignoriert. Der Vergleich laeuft dann durch und misst etwas anderes,
    # als er behauptet — deshalb hier, vor dem ersten Modellaufruf.
    for v in G.varianten(cfg):
        maengel = G.variante_maengel(v)
        if maengel:
            b.add("FEHLER", f"Variante {v.get('name', '?')}: unbekannte "
                            f"Schluessel {', '.join(maengel)}",
                  "Sie bewirken nichts — der Vergleich waere ein anderer "
                  "als der beschriebene.\n           Erlaubt sind "
                  "chunk_words, context_words, context_words_voraus, "
                  "rueckschau_quelle,\n           figuren_nachhall, "
                  "revision_pass, lektorat_passes, tempus, diminutive "
                  "sowie modell_<rolle> und effort_<rolle>.")
        else:
            _, cw, besch = G.variante_anwenden(cfg, v)
            b.add("OK", f"Variante {v.get('name', '?')}: {besch}")

    # Transport und Anbieterfassungen. Sie stehen hier, weil sie sonst
    # niemand sieht: Ein abgeschalteter Rueckfall faellt erst auf, wenn ein
    # Chunk abgelehnt wird, und eine veraltete Suchfassung nie.
    rueckfall = G.fallbacks_wert(cfg)
    if rueckfall == "default":
        b.add("OK", "Ablehnung: Ersatzmodell nach Wahl des Anbieters",
              "Erscheint in der Kostenuebersicht als eigene Zeile.")
    elif rueckfall:
        b.add("OK", "Ablehnung: Ersatzmodelle "
              + ", ".join(m["model"] for m in rueckfall))
    else:
        b.add("INFO", "Ablehnung bricht den Chunk ab",
              "'fallback_modelle' ist leer. Eine Ablehnung des "
              "Sicherheitsklassifikators beendet den Lauf; der Resume "
              "setzt an derselben Stelle wieder an.")
    b.add("INFO", "Antworttransport",
          ("Stream" if cfg.get("streaming", True) else "ein Stueck")
          + (", SDK" if cfg.get("sdk_nutzen", True) else ", requests"))
    kmax = int(cfg.get("kette_max", 0) or 0)
    b.add("INFO", "Stapelbetrieb ('uebersetzung.py --stapel')",
          (f"kette_max {kmax} — Ketten werden zusaetzlich zu den "
           f"Ebenenfugen getrennt, jede Trennung ist eine Naht ohne "
           f"Rueckschau." if kmax else
           "kette_max 0 — nur an den Ebenenfugen getrennt, keine "
           "zusaetzlichen Naehte.")
          + " 'pipeline.py wellen' zeigt den Plan.")
    w = G.websuche_werkzeug(cfg)
    if w:
        b.add("INFO", "Websuche der Zitatrecherche",
              f"{w[0]['type']}, hoechstens {w[0]['max_uses']} Suchen je "
              f"Zitat"
              + (", direkt" if w[0].get("allowed_callers") else ", filternd"))
    else:
        b.add("WARNUNG", "Zitatrecherche ohne Websuche",
              "Ohne Suche raet das Modell einen Wortlaut zusammen — genau "
              "das soll der Schritt verhindern.")

    if cfg["ratio_kalibriert"]:
        b.add("OK", f"Prueffgrenzen kalibriert: "
                    f"{cfg['ratio_min']:.2f}–{cfg['ratio_max']:.2f}")
    else:
        b.add("INFO", "Prueffgrenzen noch nicht kalibriert",
              "Werden nach dem Testlauf aus den Messwerten gesetzt.")
    pruefe_entfallene_schluessel(b)
    b.add("INFO", "Konfigurationsfingerabdruck", G.config_hash(cfg))


# Schluessel, die es einmal gab und die heute anders heissen. Eine
# projekt.json wird nie ueberschrieben — der alte Schluessel bleibt also
# stehen und wirkt nicht mehr. Ohne diese Meldung merkt das niemand.
ENTFALLEN = {
    "modell_annotation": "modell_begruendung und modell_screening",
    "effort_annotation": "effort_begruendung und effort_screening",
    "backend":           "der Modellname (das Backend ergibt sich daraus)",
    "modell":            "modell_<rolle>",
    "ollama_host":       "entfallen — Ollama ist zurueckgezogen",
    "num_ctx":           "entfallen — Ollama ist zurueckgezogen",
    "timeout_read":      "timeout_read_api",
}


def pruefe_entfallene_schluessel(b, pfad=None):
    """Meldet Schluessel, die in projekt.json stehen und nichts mehr tun."""
    pfad = pfad or G.CONFIG
    try:
        roh = json.load(open(pfad, encoding="utf-8"))
    except Exception:
        return
    tot = [k for k in ENTFALLEN if k in roh]
    tot += [k for k in roh
            if k.startswith("temperature_") and k not in ENTFALLEN]
    if not tot:
        return
    zeilen = []
    for k in sorted(tot):
        ziel = ENTFALLEN.get(k, "entfallen — es gehen keine "
                                "Sampling-Parameter mehr raus")
        zeilen.append(f"{k}  ->  {ziel}")
    b.add("WARN", f"{len(tot)} entfallene(r) Schluessel in {pfad}",
          "\n".join(zeilen)
          + f"\n\nSie werden nicht mehr gelesen und aendern nichts. Aus "
            f"{pfad}\nentfernen; die Belegung zeigt "
            f"'python3 pipeline.py modelle'.")


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

    # Erst nach dem Selbsttest, nie waehrend --selbsttest: der laeuft ohne
    # Netz. Ohne diesen Aufruf pruefte der Preflight im Sheets-Betrieb die
    # JSONs des letzten Laufs und meldete Ordnung, waehrend im Sheet ein
    # Fehler stand — also genau dort, wo er ihn finden soll.
    import referenz_sync as R
    R.sicherstellen(cfg)

    backends = G.benutzte_backends(cfg)
    pruefe_belegung(cfg, b)

    if backends & {"anthropic", "google"}:
        if not pruefe_api(cfg, b, backends, ping=not args.quick):
            b.schreiben(REPORT)
            sys.exit(1)
    pruefe_begleitdateien(cfg, b, args.streng)      # F4: immer

    if not args.quick:
        pruefe_umgebung(b)
        pruefe_config(cfg, b)
        text = pruefe_text(cfg, b)
        if text:
            finde_zitate(text, b)
            pruefe_kosten(cfg, b, text)

    G.speichere_config(cfg)
    ok = b.schreiben(REPORT)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
