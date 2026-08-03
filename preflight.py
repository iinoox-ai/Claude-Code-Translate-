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

    # --- Paket 9: der Ablaufplan muss zur Schrittliste passen ----------
    # Ein Plan, der einen Schritt nicht kennt, schickt den Leser ins
    # Leere — und das faellt erst auf, wenn jemand danach arbeitet.
    try:
        import pipeline as PL
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ABLAUFPLAN.md")
        plan = open(pfad, encoding="utf-8").read()
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
        for wort in ("Diff-Statistik", "Fremdurteil", "Selbstpraeferenz"):
            if wort not in BW.GEWICHTUNG:
                fehler.append(f"Gewichtungshinweis nennt '{wort}' nicht")
        # Die alten Etiketten duerfen nirgends mehr stehen.
        quelle = open("bewertung.py", encoding="utf-8").read()
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

        # Und der Bericht zeigt die Begruendung genau dann, wenn es eine
        # gibt — dieselbe Kennung auf beiden Seiten.
        html_mit = D.fmt_html("Wort", 7, "Stil", "er", "lief", "ging", "los",
                              "falscher Freund behoben")
        if "falscher Freund behoben" not in html_mit:
            fehler.append("Begruendung erscheint nicht im HTML-Bericht")
        if "grund" in D.fmt_html("Typografie", 1, "det", "a", "-", "–", "b"):
            fehler.append("leere Begruendung erzeugt trotzdem eine Spalte")

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
                # Freigabe erteilen und erneut einlesen.
                open(Z.REVIEW, "w", encoding="utf-8").write(
                    text.replace("| 0.9 | nein |", "| 0.9 | ja |"))
                with contextlib.redirect_stdout(io.StringIO()):
                    g, o = Z.freigabe_einlesen({"sheets_id": ""}, [eng, nl])
                if nl.get("original_deutsch") != "Alles von Wert ist "\
                                                 "wehrlos." or g != 1:
                    fehler.append(f"Freigabe wird nicht wirksam "
                                  f"({g} gesetzt, {o} offen)")
            finally:
                os.chdir(alt)

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

        echt, buch = RS._buch, _Buch()
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
            RS.G.lade_json = G.lade_json

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
                "modell_annotation":   "gemini-3.6-flash",
                "effort_uebersetzung": "hoch",
                "effort_annotation":   "niedrig"})

    # --- Routing: Rolle -> Modell -> Backend, inklusive Rueckfallpfad ----
    try:
        fehler = []
        if G.backend_name(G.modell_fuer(cfg, "uebersetzung")) != "anthropic":
            fehler.append("uebersetzung landet nicht bei Anthropic")
        if G.backend_name(G.modell_fuer(cfg, "annotation")) != "google":
            fehler.append("annotation landet nicht bei Google")
        # Leerer Schluessel muss auf Ollama zurueckfallen (VPS-Rueckfallpfad).
        if G.backend_name(G.modell_fuer(dict(G.STANDARD), "stil")) != "ollama":
            fehler.append("leeres modell_stil faellt nicht auf Ollama zurueck")
        if G.effort_fuer(cfg, "annotation") != "low":
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
        if fehler:
            b.add("FEHLER", "Anthropic-Payload fehlerhaft", "; ".join(fehler))
        else:
            b.add("OK", "Anthropic-Payload: Cache-Marker und Effort gesetzt, "
                        "keine Sampling-Parameter")
    except Exception as e:
        b.add("FEHLER", "Anthropic-Payload wirft Ausnahme", repr(e))

    # --- Gemini-Payload -------------------------------------------------
    try:
        p = G.GeminiBackend().payload(cfg, "SYSTEM", "USER",
                                      "annotation", "gemini-3.6-flash")
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

    # --- Anzeige darf nicht den Rueckfallschluessel nennen ---------------
    # uebersetzung.py meldete im Kopf 'cfg["modell"]' — den Ollama-Namen —
    # obwohl ueber die Rolle laengst Opus 5 lief. Der Lauf war richtig, die
    # Anzeige log. Payloadtests finden so etwas nicht, ein Blick in die
    # Quelle schon.
    try:
        hier = os.path.dirname(os.path.abspath(__file__))
        schuldig = []
        for datei in ("uebersetzung.py", "lektorat.py", "konkordanz.py",
                      "bewertung.py", "qa.py"):
            pfad = os.path.join(hier, datei)
            if not os.path.exists(pfad):
                continue
            for nr, zeile in enumerate(open(pfad, encoding="utf-8"), 1):
                if "print(" not in zeile:
                    continue
                if "cfg['modell']" in zeile or 'cfg["modell"]' in zeile:
                    schuldig.append(f"{datei}:{nr}")
        if schuldig:
            b.add("FEHLER", "Anzeige nennt den Ollama-Rueckfallschluessel",
                  f"{', '.join(schuldig)}\n"
                  f"           Im API-Betrieb stimmt cfg['modell'] nie. "
                  f"G.modell_fuer(cfg, rolle) benutzen.")
        else:
            b.add("OK", "Kein Skript zeigt cfg['modell'] statt des "
                        "Rollenmodells an")
    except Exception as e:
        b.add("WARN", "Anzeigepruefung nicht durchfuehrbar", repr(e))

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
        zusatz = (f", Effort {G.effort_fuer(cfg, rolle)}"
                  if anbieter != "ollama" else "")
        b.add("INFO", f"  {rolle}", f"{modell} ({anbieter}{zusatz})")


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
                                      0.0, rolle=rolle, modell=modell)
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


def pruefe_kosten(cfg, b, woerter):
    """Schaetzung vor dem Volllauf. Lieber zu hoch als zu niedrig."""
    b.abschnitt("Kostenschaetzung")
    faktor = G.token_faktor()
    b.add("INFO", "Annahme", f"{faktor} Token je Quellwort (konservativ; "
                             f"wird nach dem ersten Lauf an der gemessenen "
                             f"Usage kalibriert)")
    # Nicht jede Rolle sieht das ganze Buch: Judge und Vorbereitung arbeiten
    # am Testauszug beziehungsweise an Konkordanzen, nicht am Volltext.
    auszug = cfg["test_words_erzaehlung"] + cfg["test_words_dialog"]
    umfang = {"judge": auszug, "vorbereitung": min(woerter, 20000)}

    summe, unsicher, ohne_tarif = 0.0, False, []
    for rolle in G.aktive_rollen(cfg):
        modell = G.modell_fuer(cfg, rolle)
        if G.backend_name(modell) == "ollama":
            continue
        t = G.tarif(modell)
        if not t:
            ohne_tarif.append(modell)
            continue
        n = umfang.get(rolle, woerter)
        # Je Pass geht der Quelltext einmal rein und einmal (bearbeitet) raus;
        # Kontextrueckschau und Prompt-Kopf schlagen grob als Aufschlag zu.
        ein = n * faktor * 1.4
        aus = n * faktor
        d = (ein * t["ein"] + aus * t["aus"]) / 1e6
        summe += d
        unsicher = unsicher or not t["geprueft"]
        b.add("INFO", f"  {rolle}", f"{modell}: rund {d:.2f} $ "
                                    f"({n} Woerter)")
    if ohne_tarif:
        b.add("WARN", "Kein hinterlegter Tarif",
              f"{', '.join(sorted(set(ohne_tarif)))} — Schaetzung "
              f"unvollstaendig. Tarif in gemeinsam.TARIFE ergaenzen.")
    b.add("INFO", "Summe (grob)", f"rund {summe:.2f} $ fuer {woerter} Woerter")
    if unsicher:
        b.add("WARN", "Teil der Tarife ist nicht verifiziert",
              "Google-Tarife stehen mit Datum 31.07.2026 vorgemerkt und "
              "werden in Paket 2 gegen die Anbieterdoku geprueft.")


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
    "stilprofil": ("'ton' gefuellt, 'perspektive' als Objekt",
                   lambda d: bool(str(d.get("ton", "")).strip())
                   and isinstance(d.get("perspektive", {}), dict)),
    "kapitel":    ("je Ueberschrift eine Zeile", lambda d: all(
        isinstance(v, str) for k, v in d.items() if not k.startswith("_"))),
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
    if "ollama" in G.benutzte_backends(cfg) \
            and cfg["chunk_words"] * 4 > cfg["num_ctx"]:
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

    # Erst nach dem Selbsttest, nie waehrend --selbsttest: der laeuft ohne
    # Netz. Ohne diesen Aufruf pruefte der Preflight im Sheets-Betrieb die
    # JSONs des letzten Laufs und meldete Ordnung, waehrend im Sheet ein
    # Fehler stand — also genau dort, wo er ihn finden soll.
    import referenz_sync as R
    R.sicherstellen(cfg)

    # Die Pruefungen richten sich nach den tatsaechlich benutzten Anbietern:
    # ohne Ollama-Rolle gibt es weder GPU- noch VRAM-Frage.
    backends = G.benutzte_backends(cfg)
    pruefe_belegung(cfg, b)

    if "ollama" in backends:
        if not pruefe_ollama(cfg, b):
            b.schreiben(REPORT)
            sys.exit(1)
        pruefe_gpu(cfg, b)
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
            pruefe_kosten(cfg, b, len(text.split()))

    G.speichere_config(cfg)
    ok = b.schreiben(REPORT)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
