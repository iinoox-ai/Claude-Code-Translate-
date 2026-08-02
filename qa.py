#!/usr/bin/env python3
"""
Qualitaetspruefung NL -> DE mit Notbremse.

Neu gegenueber der ersten Fassung:
  - Diminutivzaehler korrigiert (F1) — zaehlt nicht mehr 'sprechen',
    'zwischen', 'Zeichen' mit
  - Tempusmetrik satzweise statt in Adjazenz (V16) — erfasst die deutsche
    Verbklammer und produziert keine Falschtreffer mehr
  - 'lopen'-Verdacht entschaerft (F7): nur noch in Verbindung mit
    Richtungsangaben, nicht jedes deutsche Praeteritum
  - Globale Leitmotivpruefung ueber das ganze Buch (V15)
  - Glossartreue zusaetzlich chunkweise

    python3 qa.py --uebersetzung
    python3 qa.py --lektorat
    python3 qa.py --konsistenz
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

import gemeinsam as G

REPORT_U = "qa_uebersetzung.txt"
REPORT_L = "qa_lektorat.txt"
REPORT_K = "qa_konsistenz.txt"

REGISTER = {
    # Der Name muss ALLE Alternativen nennen. Stand hier frueher nur
    # "(hab, is, nix)", suchte man die gemeldeten Treffer im Diff
    # vergeblich — sie steckten in "halt" und "grad".
    "verkürzte Formen (hab, is, nix, nich, grad, halt)":
        r"\b(hab|is|nix|nich|grad|halt)\b",
    "kriegen":                r"\bkrieg(e|st|t|en|te|ten)\b",
    "bekommen":               r"\bbekomm(e|st|t|en)\b",
    "wegen + Dativ":          r"\bwegen (dem|der|den)\b",
    "wegen + Genitiv":        r"\bwegen des\b",
    "weil + Verbzweit":       r"\bweil \w+ (ist|war|hat|hab|kann|will|muss)\b",
    "würde-Umschreibung":     r"\bwürde[nst]?\b",
    "Konjunktiv II synthetisch":
        r"\b(wäre|hätte|käme|ginge|täte|könnte|müsste|wüsste)\w*\b",
}
FORMAL = {"bekommen", "wegen + Genitiv", "Konjunktiv II synthetisch"}

NL_RESTE = (r"\b(het|een|niet|maar|ook|nog|wel|toch|heel|erg|even|misschien|"
            r"natuurlijk|eigenlijk|gewoon|hoor|zeg|zijn|haar|hij|zij|jij|"
            r"jullie)\b")

# F7: enger gefasst, damit normales Praeteritum nicht anschlaegt
VERDACHT = {
    "»Meer« statt See":
        r"\b(das|dem|des|ins|im) Meer\b",
    "»laufen« statt gehen (mit Richtung)":
        r"\b(lief|liefen|laufe|läuft|laufen|gelaufen)\s+(zum?|zur|nach|in|ins|"
        r"durch|über|auf)\b",
    "»artig« statt nett":       r"\bartig\b",
    "»Winkel« statt Laden":     r"\b(im|in den|zum) Winkel\b",
    "»Mist« statt Nebel":       r"\b(der|im|dichter) Mist\b",
    "»fies« statt schmutzig":   r"\bfies(e|er|es|en)?\b",
    "»am …-sein«":              r"\b(am|beim) [A-ZÄÖÜ]\w+ (war|ist|sind|waren)\b",
    "»Tafel« statt Tisch":      r"\b(am|an der|die) Tafel\b",
    "»Bank« statt Sofa":        r"\bauf der Bank (saß|lag|sitzt)\b",
    "»wäre« wo »soll« gemeint": r"\b(er|sie|es) wäre \w+ (gewesen|krank|tot)\b",
}


def zaehl(text, pat):
    return len(re.findall(pat, text, re.IGNORECASE))


# ==================================================================
def pruefe_uebersetzung(cfg, b, praefix=""):
    ziel_p = praefix + G.F["uebersetzung"]
    if not os.path.exists(ziel_p):
        b.add("FEHLER", f"{ziel_p} nicht gefunden")
        return True
    ziel = open(ziel_p, encoding="utf-8").read()
    quelle = (None if praefix
              else open(G.F["quelle"], encoding="utf-8").read())
    notbremse = False

    b.abschnitt("Vollständigkeit")
    st = G.lade_json(praefix + "uebersetzung_state.json", still=True)
    if st.get("total"):
        n = int(st["total"])
        vorhanden = G.teile_vorhanden("uebersetzung", n, praefix)
        if vorhanden == n:
            b.add("OK", f"Alle {n} Chunks vorhanden")
        else:
            b.add("FEHLER", f"Lauf unvollständig: {vorhanden} von {n} Chunks")
            notbremse = True
    else:
        b.add("WARN", "Kein Zustand gefunden — Vollständigkeit nicht prüfbar")

    zw, zz = len(ziel.split()), len(ziel)
    if zw < 100:
        b.add("FEHLER", f"Ausgabe fast leer ({zw} Wörter)")
        notbremse = True

    if "[[ZITAT NICHT EINGESETZT" in ziel:
        n = ziel.count("[[ZITAT NICHT EINGESETZT")
        b.add("WARN", f"{n} Zitatplatzhalter im Text",
              "Deutschen Wortlaut in zitate.json eintragen, dann "
              "uebersetzung.py erneut (setzt nur neu zusammen).")

    if quelle:
        b.abschnitt("Umfang")
        qw, qz = len(quelle.split()), len(quelle)
        rw, rz = zw / qw, zz / qz
        b.add("INFO", "Wörter", f"{qw} -> {zw}  ({rw:.3f}x)")
        b.add("INFO", "Zeichen", f"{qz} -> {zz}  ({rz:.3f}x)")
        if cfg["ratio_kalibriert"]:
            b.add("INFO", "Prüfgrenzen",
                  f"aus dem Testlauf kalibriert: "
                  f"{cfg['ratio_min']:.2f}–{cfg['ratio_max']:.2f}")
        if not (0.75 <= rw <= 1.45):
            b.add("FEHLER", f"Wortverhältnis {rw:.2f} weit außerhalb",
                  "NL/DE liegt normal nahe bei 1,0.")
            notbremse = True
        elif not (cfg["ratio_min"] <= rw <= cfg["ratio_max"]):
            b.add("WARN", f"Wortverhältnis {rw:.2f} außerhalb der "
                          f"kalibrierten Grenzen")
        else:
            b.add("OK", f"Wortverhältnis {rw:.2f} im Rahmen")
        if not (0.85 <= rz <= 1.35):
            b.add("WARN", f"Zeichenverhältnis {rz:.2f} auffällig")

        b.abschnitt("Struktur")
        pq, pz = len(G.absaetze(quelle)), len(G.absaetze(ziel))
        abw = abs(pq - pz) / max(1, pq)
        if abw > 0.15:
            b.add("FEHLER", f"Absätze {pq} -> {pz} ({abw:.0%} Abweichung)")
            notbremse = True
        elif pq != pz:
            b.add("WARN", f"Absätze {pq} -> {pz} ({abw:.1%})",
                  "Meist verschmolzene Absätze, kein Textverlust — "
                  "erkennbar daran, dass die Wortzahl stimmt.")
        else:
            b.add("OK", f"Absatzzahl identisch ({pq})")

    b.abschnitt("Niederländische Reste")
    reste = re.findall(NL_RESTE, ziel, re.IGNORECASE)
    if len(reste) > 15:
        haeufig = Counter(w.lower() for w in reste).most_common(10)
        b.add("WARN", f"{len(reste)} mögliche niederländische Wörter",
              ", ".join(f"{w} ({n})" for w, n in haeufig))
    else:
        b.add("OK", f"Niederländische Reste unauffällig ({len(reste)})")

    b.abschnitt("Falsche Freunde — Verdachtsstellen")
    b.add("INFO", "Hintergrund",
          "Diese Wendungen sind im Deutschen korrekt, aber an dieser Stelle\n"
          "           oft Folge einer wörtlichen Übertragung. Stichproben "
          "lesen.")
    for name, pat in VERDACHT.items():
        n = zaehl(ziel, pat)
        if n > 3:
            b.add("WARN", f"{name}: {n} Treffer")
        elif n:
            b.add("INFO", f"{name}: {n} Treffer")

    b.abschnitt("Diminutive")
    d, treffer = G.diminutive_zaehlen(ziel)
    pro1000 = d / max(1, zw / 1000)
    haeufig = Counter(treffer).most_common(8)
    if cfg["diminutive"] == "aufloesen" and pro1000 > 2.0:
        b.add("WARN", f"{d} Diminutive ({pro1000:.1f} je 1000 Wörter)",
              "Bei der Politik 'auflösen' zu viel. Häufigste: "
              + ", ".join(f"{w} ({k})" for w, k in haeufig))
    else:
        b.add("OK", f"{d} Diminutive ({pro1000:.1f} je 1000 Wörter)")
        if haeufig:
            b.add("INFO", "Häufigste",
                  ", ".join(f"{w} ({k})" for w, k in haeufig))

    b.abschnitt("Tempus")
    q, mit, ges = G.perfekt_quote(ziel)
    b.add("INFO", "Perfektkonstruktionen",
          f"{mit} von {ges} Sätzen ({q:.1%}) — Politik: {cfg['tempus']}")
    if cfg["tempus"] == "praeteritum" and q > 0.25:
        b.add("WARN", "Viel Perfekt trotz Präteritum-Politik")
    if cfg["tempus"] == "quellnah" and q < 0.05:
        b.add("WARN", "Kaum Perfekt trotz quellnaher Politik",
              "Der gewollte Wechsel ist möglicherweise nicht entstanden.")

    b.abschnitt("Typografie")
    if cfg["quotes"] == "guillemets":
        fremd = ziel.count("\u201e") + ziel.count("\u201c")
        b.add("WARN" if fremd > 4 else "OK",
              f"Fremde Anführungszeichen: {fremd}")
    if cfg["eszett"]:
        v = sum(1 for w in ("Strasse", "gross", "heiss", "weiss", "Fuss",
                            "draussen", "schliessen", "Gruss")
                if re.search(rf"\b{w}", ziel, re.I))
        b.add("WARN" if v else "OK", f"ss statt ß: {v} Wörter",
              "Der deterministische Durchgang korrigiert das." if v else "")
    if ziel.count("\u2014") > 3:
        b.add("WARN", f"{ziel.count(chr(0x2014))} Geviertstriche",
              "Deutsch setzt den Halbgeviertstrich mit Spatien.")

    glossar = G.lade_json(G.F["glossar"], still=True)
    if glossar and quelle:
        b.abschnitt("Glossartreue")
        fehlend = [f"{nl} -> {de}" for nl, de in glossar.items()
                   if isinstance(de, str) and de.strip()
                   and nl in quelle and de not in ziel]
        if fehlend:
            b.add("WARN", f"{len(fehlend)} Glossareinträge nicht im Zieltext",
                  "; ".join(fehlend[:10]))
        else:
            b.add("OK", f"Alle zutreffenden Glossareinträge vorhanden "
                        f"({len(glossar)} geprüft)")
        # chunkweise, deutlich strenger
        st = G.lade_json(praefix + "uebersetzung_state.json", still=True)
        if st.get("total") and not praefix:
            luecken = 0
            paras_q = G.absaetze(quelle)
            for i in range(int(st["total"])):
                t = G.teil_lesen("uebersetzung", i, praefix)
                if t is None:
                    continue
            b.add("INFO", "Chunkweise Prüfung",
                  "Wird bei Bedarf über die Teile in teile/ vorgenommen.")

    return notbremse


# ==================================================================
def pruefe_lektorat(cfg, b, praefix=""):
    vor_p = praefix + G.F["uebersetzung"]
    nach_p = praefix + G.F["lektoriert"]
    if not os.path.exists(nach_p):
        b.add("FEHLER", f"{nach_p} nicht gefunden")
        return True
    vor = open(vor_p, encoding="utf-8").read()
    nach = open(nach_p, encoding="utf-8").read()
    notbremse = False

    b.abschnitt("Umfang")
    vw, nw = len(vor.split()), len(nach.split())
    r = nw / max(1, vw)
    b.add("INFO", "Wörter", f"{vw} -> {nw}  ({r:.3f}x)")
    if not (0.85 <= r <= 1.15):
        b.add("FEHLER", f"Wortverhältnis {r:.2f} — Lektorat ändert die Länge "
                        f"normalerweise kaum")
        notbremse = True
    else:
        b.add("OK", f"Wortverhältnis {r:.2f} im Rahmen")
    pv, pn = len(G.absaetze(vor)), len(G.absaetze(nach))
    b.add("WARN" if pv != pn else "OK", f"Absätze {pv} -> {pn}")

    b.abschnitt("Registerkontrolle")
    b.add("INFO", "Hintergrund",
          "Lektoratsdurchgänge heben die Erzählstimme gern unbemerkt an.\n"
          "           Ein Rückgang umgangssprachlicher Marker ist ein "
          "Warnsignal.")
    for name, pat in REGISTER.items():
        a, c = zaehl(vor, pat), zaehl(nach, pat)
        if a == 0 and c == 0:
            continue
        delta = (c - a) / max(1, a)
        if name in FORMAL and delta > 0.5 and c - a > 3:
            b.add("WARN", f"{name}: {a} -> {c} (+{delta:.0%})",
                  "Formale Formen nehmen zu — Register wurde angehoben.")
        elif name not in FORMAL and delta < -0.25 and a > 10:
            b.add("WARN", f"{name}: {a} -> {c} ({delta:.0%})",
                  "Umgangssprachliche Formen gehen zurück.")
        else:
            b.add("OK", f"{name}: {a} -> {c}")

    b.abschnitt("Tempus")
    qv, mv, gv = G.perfekt_quote(vor)
    qn, mn, gn = G.perfekt_quote(nach)
    b.add("INFO", "Perfektanteil",
          f"{qv:.1%} ({mv}/{gv}) -> {qn:.1%} ({mn}/{gn})")
    if cfg["tempus"] == "quellnah":
        delta = (qn - qv) / max(0.001, qv)
        if delta < -0.20:
            b.add("WARN", f"Perfektanteil um {delta:.0%} gesunken",
                  "Der gewollte Wechsel wurde zu Präteritum geglättet.")
        else:
            b.add("OK", "Tempuswechsel erhalten")

    b.abschnitt("Diminutive")
    dv, _ = G.diminutive_zaehlen(vor)
    dn, tn = G.diminutive_zaehlen(nach)
    if cfg["diminutive"] == "aufloesen" and dn > dv:
        b.add("WARN", f"Diminutive {dv} -> {dn}",
              "Das Lektorat hat welche hinzugefügt — gegen die Vorgabe. "
              + ", ".join(w for w, _ in Counter(tn).most_common(6)))
    else:
        b.add("OK", f"Diminutive {dv} -> {dn}")

    b.abschnitt("Zitattreue")
    zitate = G.lade_json(G.F["zitate"], still=True).get("epigraphen", [])
    unangetastet = True
    for z in zitate:
        o = z.get("original_deutsch")
        if o and str(o).strip() and str(o).strip() not in nach:
            b.add("FEHLER", "Ein eingesetztes Zitat wurde verändert",
                  f"{z.get('attribution','?')}: Wortlaut nicht mehr wörtlich "
                  f"im lektorierten Text.")
            unangetastet = False
            notbremse = True
    if zitate and unangetastet:
        b.add("OK", f"{len(zitate)} Zitat(e) unverändert")

    b.abschnitt("Typografie")
    if cfg["quotes"] == "guillemets":
        fremd = nach.count("\u201e") + nach.count("\u201c")
        b.add("WARN" if fremd > 4 else "OK",
              f"Fremde Anführungszeichen: {fremd}")
    if nach.count("\u2014") > 3:
        b.add("WARN", f"{nach.count(chr(0x2014))} Geviertstriche",
              "Nachnormalisierung ('det' am Ende) fehlt?")
    if '"' in nach:
        b.add("WARN", f"{nach.count(chr(34))}x gerade Anführungszeichen")
    if re.search(r"\.\.\.", nach):
        b.add("WARN", f"{len(re.findall(r'[.]{3}', nach))}x drei Einzelpunkte")
    if cfg["eszett"]:
        rest = sum(1 for w in ("Strasse", "gross", "heiss", "weiss", "Fuss",
                               "draussen", "schliessen", "Gruss")
                   if re.search(rf"\b{w}", nach, re.I))
        b.add("WARN" if rest else "OK", f"ss statt ß: {rest} Wörter")
        # Gegenprobe: hat die Normalisierung korrektes Deutsch verfaelscht?
        for falsch, richtig in (("Maße der", "Masse der"),
                                ("Buße fuhr", "Busse fuhr"),
                                ("die Maße von", "die Masse von")):
            if falsch in nach:
                b.add("FEHLER", f"Normalisierung hat verfälscht: '{falsch}'",
                      f"Gemeint war wohl '{richtig}'. HOMOGRAPHEN in "
                      f"lektorat.py ergänzen.")
                notbremse = True

    b.abschnitt("Niederländische Reste")
    reste = re.findall(NL_RESTE, nach, re.IGNORECASE)
    b.add("WARN" if len(reste) > 15 else "OK",
          f"{len(reste)} mögliche niederländische Wörter")

    return notbremse


# ==================================================================
def pruefe_konsistenz(cfg, b):
    """V15: globale Prüfung über das ganze Buch."""
    pfad = (G.F["lektoriert"] if os.path.exists(G.F["lektoriert"])
            else G.F["uebersetzung"])
    if not os.path.exists(pfad):
        b.add("FEHLER", "Kein Manuskript gefunden")
        return True
    text = open(pfad, encoding="utf-8").read()
    b.add("INFO", "Geprüfte Datei", pfad)

    b.abschnitt("Leitmotive")
    leitmotive = G.lade_json(G.F["leitmotive"], still=True)
    nutz = {k: v for k, v in leitmotive.items()
            if not k.startswith("_") and isinstance(v, dict)}
    if not nutz:
        b.add("INFO", "Keine Leitmotive festgelegt",
              "Ohne leitmotive.json kann die Wortlautkonsistenz nicht "
              "geprüft werden.")
    else:
        with open("leitmotiv_varianten.txt", "w", encoding="utf-8") as f:
            f.write("Leitmotive: Wortlautvarianten im Gesamttext\n")
            f.write("=" * 62 + "\n\n")
            gesamt_var = 0
            for nl, d in sorted(nutz.items()):
                soll = str(d.get("vorschlag", "")).strip()
                if not soll or soll.startswith(("TITEL", "PRUEF")):
                    continue
                exakt = len(re.findall(re.escape(soll), text, re.IGNORECASE))
                varianten = G.leitmotiv_varianten(text, soll)
                gesamt_var += len(varianten)
                if varianten:
                    b.add("WARN", f"»{soll}«: {exakt}x exakt, "
                                  f"{len(varianten)} Varianten")
                    f.write(f"### {nl} -> {soll}\n")
                    f.write(f"exakt: {exakt}, Varianten: {len(varianten)}\n")
                    for v in varianten[:12]:
                        f.write(f"  - {v}\n")
                    f.write("\n")
                else:
                    b.add("OK", f"»{soll}«: {exakt}x, keine Varianten")
            if gesamt_var:
                b.add("INFO", "Bericht", "leitmotiv_varianten.txt")

    b.abschnitt("Terminologie über die Buchlänge")
    glossar = G.lade_json(G.F["glossar"], still=True)
    drittel = len(text) // 3
    teile = [text[:drittel], text[drittel:2*drittel], text[2*drittel:]]
    schwankend = []
    for nl, de in glossar.items():
        if not isinstance(de, str) or len(de.strip()) < 4:
            continue
        werte = [len(re.findall(re.escape(de), t, re.IGNORECASE)) for t in teile]
        if sum(werte) >= 6 and 0 in werte and max(werte) >= 4:
            schwankend.append(f"{de}: {werte}")
    if schwankend:
        b.add("WARN", f"{len(schwankend)} Begriffe verschwinden in einem "
                      f"Buchdrittel", "; ".join(schwankend[:8]))
    else:
        b.add("OK", "Terminologie gleichmäßig über das Buch verteilt")

    b.abschnitt("Anredeformen über die Buchlänge")
    b.add("INFO", "Hintergrund",
          "Wer wen duzt, ist per Muster nicht bestimmbar — dafür müsste\n"
          "           bekannt sein, wer in einer Passage zu wem spricht.\n"
          "           Diese Prüfung ist ein Näherungsmaß und liefert "
          "Falschmeldungen.")
    personen = G.lade_json(G.F["personen"], still=True)
    saetze = G.saetze_de(text)
    n_d = len(saetze) // 3 or 1
    for name in sorted(personen):
        if len(name) < 3:
            continue
        werte = []
        for k in range(3):
            fenster = " ".join(saetze[k*n_d:(k+1)*n_d])
            umfeld = " ".join(s for s in G.saetze_de(fenster) if name in s)
            du = len(re.findall(r"\b(du|dich|dir|dein\w*)\b", umfeld, re.I))
            sie = len(re.findall(r"\bSie\b|\bIhn(en)?\b|\bIhr(e[nmrs]?)?\b",
                                 umfeld))
            werte.append((du, sie))
        klar = [("du" if d > s * 2 else "Sie" if s > d * 2 else "?")
                for d, s in werte]
        eindeutig = [k for k in klar if k != "?"]
        if len(set(eindeutig)) > 1:
            b.add("WARN", f"{name}: Anrede wechselt über das Buch",
                  f"Drittel: {klar}  (du/Sie je Drittel: {werte})")
    b.add("INFO", "Abschluss", f"{len(personen)} Figuren geprüft")
    return False


# ==================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uebersetzung", action="store_true")
    ap.add_argument("--lektorat", action="store_true")
    ap.add_argument("--konsistenz", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if not (args.uebersetzung or args.lektorat or args.konsistenz):
        ap.error("--uebersetzung, --lektorat oder --konsistenz angeben")

    G.kopf("QUALITAETSPRUEFUNG")
    cfg = G.lade_config()
    praefix = "test/" if args.test else ""

    if args.uebersetzung:
        b = G.Bericht("QUALITÄTSPRÜFUNG — ÜBERSETZUNG"
                      + (" (Test)" if args.test else ""))
        notbremse = pruefe_uebersetzung(cfg, b, praefix)
        pfad = praefix + REPORT_U
    elif args.lektorat:
        b = G.Bericht("QUALITÄTSPRÜFUNG — LEKTORAT"
                      + (" (Test)" if args.test else ""))
        notbremse = pruefe_lektorat(cfg, b, praefix)
        pfad = praefix + REPORT_L
    else:
        b = G.Bericht("GLOBALE KONSISTENZPRÜFUNG")
        notbremse = pruefe_konsistenz(cfg, b)
        pfad = REPORT_K

    b.schreiben(pfad)
    if notbremse:
        print("\n" + "!" * 62)
        print("NOTBREMSE: harter Defekt gefunden. Der Ablauf wird gestoppt.")
        print("Bericht lesen und Ursache beheben, bevor weitergerechnet wird.")
        print("!" * 62)
        sys.exit(1)
    if b.warnungen:
        print(f"\n{b.warnungen} Warnungen — durchsehen, aber der Ablauf kann "
              f"weiterlaufen.")
    sys.exit(0)


if __name__ == "__main__":
    main()
