#!/usr/bin/env python3
"""
Bewertung der Testlaeufe NL -> DE.

Neu gegenueber der ersten Fassung:
  - Absaetze werden ueber Aehnlichkeit ausgerichtet statt stumpf gezippt
    (F7) — bei verschmolzenen Absaetzen verglich die alte Fassung Unsinn
  - Chunkgroessen-Vergleich A gegen B (V9)
  - Erzaehlung und Dialog getrennt ausgewiesen

    python3 bewertung.py
    python3 bewertung.py --lektorat
    python3 bewertung.py --variantenvergleich
"""

import argparse
import difflib
import json
import os
import random
import re
import sys
from collections import Counter

import gemeinsam as G

TESTDIR = "test"


# ==================================================================
def kategorie(alt, neu):
    if re.search(r"[\u2014\u2013]", alt + neu):
        return "Typografie"
    if re.sub(r"[^\w]", "", alt).lower() == re.sub(r"[^\w]", "", neu).lower():
        return "Interpunktion"
    a, n = len(alt.split()), len(neu.split())
    if a <= 1 and n <= 1:
        return "Wort"
    if a <= 4 and n <= 4:
        return "Wendung"
    if a <= 10 and n <= 10:
        return "Teilsatz"
    return "Umbau"


def ausrichten(pa, pb):
    """F7: Absaetze ueber Aehnlichkeit paaren statt stumpf zippen."""
    if len(pa) == len(pb):
        return list(zip(pa, pb))
    sm = difflib.SequenceMatcher(None, [p[:80] for p in pa],
                                 [p[:80] for p in pb])
    paare = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            paare += [(pa[i1 + k], pb[j1 + k]) for k in range(i2 - i1)]
        elif tag == "replace":
            m = min(i2 - i1, j2 - j1)
            paare += [(pa[i1 + k], pb[j1 + k]) for k in range(m)]
    return paare


def diffstat(vorher, nachher):
    paare = ausrichten(G.absaetze(vorher), G.absaetze(nachher))
    stat, beispiele = {}, []
    for a, b in paare:
        if a == b:
            continue
        aw, bw = a.split(), b.split()
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, aw, bw).get_opcodes():
            if tag == "equal":
                continue
            alt, neu = " ".join(aw[i1:i2]), " ".join(bw[j1:j2])
            k = kategorie(alt, neu)
            stat[k] = stat.get(k, 0) + 1
            if k not in ("Typografie", "Interpunktion"):
                beispiele.append((k, alt[:80], neu[:80]))
    return stat, beispiele


def ausgabe_stat(stat, titel):
    gesamt = sum(stat.values()) or 1
    subst = sum(v for k, v in stat.items()
                if k not in ("Typografie", "Interpunktion"))
    print(f"\n=== {titel}: {gesamt} Aenderungen ===")
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print(f"  {k:16s} {v:5d}  {v/gesamt:5.0%}")
    print(f"  {'davon substanziell':16s} {subst:5d}  {subst/gesamt:5.0%}")
    return gesamt, subst


def teile_trennen(pfad, teile):
    paras = G.absaetze(open(pfad, encoding="utf-8").read())
    n1 = teile.get("erzaehlung", len(paras) // 2)
    n1 = min(n1, len(paras))
    return "\n\n".join(paras[:n1]), "\n\n".join(paras[n1:])


# ==================================================================
BLIND_SYSTEM = """Du bist eine erfahrene Literaturlektorin. Du siehst einen \
niederlaendischen Ausgangstext und zwei deutsche Uebersetzungen davon, mit A \
und B bezeichnet. Du weisst nicht, wie sie entstanden sind.

Beurteile nach:
1. Natuerlichkeit — deutsche Prosa oder uebersetztes Deutsch?
2. Treue — falsch uebersetzt, ausgelassen, hinzugefuegt?
3. Stimme — Register von Erzaehler und Figuren erhalten?
4. Rhythmus — Satzvielfalt, Kadenz, keine Monotonie.
5. Niederlandismen — falsche Freunde, uebertragene Verlaufsformen,
   "es gibt"-Schwemme, mechanische Diminutive, "zou" als Konditional statt
   als Hoerensagen.

Sei konkret. Nenne Stellen. Sind beide gleichwertig, sag das klar.

Antworte NUR mit einem JSON-Objekt:
{"besser": "A" | "B" | "gleichwertig",
 "abstand": "deutlich" | "gering" | "keiner",
 "begruendung": "…",
 "niederlandismen_A": ["…"], "niederlandismen_B": ["…"],
 "empfehlung": "…"}
Keine Codefences, kein Kommentar."""


GEWICHTUNG = (
    "Die drei Signale sind nicht gleich viel wert. In dieser Reihenfolge:\n\n"
    "1. **Diff-Statistik** — auszaehlbar, kein Urteil. Ein Durchgang, dessen "
    "Aenderungen ueberwiegend Typografie sind, verdient seine Zeit nicht.\n"
    "2. **Fremdurteil** — ein anderes Modell als das uebersetzende. Es hat "
    "keinen Grund, die eigene Arbeit zu bevorzugen.\n"
    "3. **Selbstcheck** — dasselbe Modell, das uebersetzt hat, prueft die "
    "Treue gegen das Original. **Nachrangig wegen Selbstpraeferenz**: "
    "Modelle bevorzugen ihre eigenen Formulierungen, auch blind.\n")


def signal_kopf(cfg, rolle, was):
    """Beschriftet ein Modellsignal mit dem Modell, das es geliefert hat.

    Frueher stand hier 'lokales Modell' und 'Selbstbewertung' — beides
    war nach der API-Umstellung falsch und hat einen Leser in die Irre
    gefuehrt, der die Staerke des Signals daran ablas."""
    modell = G.modell_fuer(cfg, rolle) or cfg.get("modell", "?")
    fremd = modell != (G.modell_fuer(cfg, "uebersetzung")
                       or cfg.get("modell", ""))
    art = "Fremdurteil" if fremd else "Selbstcheck, nachrangig"
    return f"{was} — {modell} ({art})"


def blindbewertung(cfg, quelle, a, b, n=4, label="", rolle="judge"):
    pq = G.absaetze(quelle)
    paare_ab = ausrichten(G.absaetze(a), G.absaetze(b))
    kandidaten = []
    for q, (x, y) in zip(pq, paare_ab):
        if x != y and len(q.split()) > 30:
            kandidaten.append((q, x, y))
    if not kandidaten:
        print(f"  {label}: keine vergleichbaren Absaetze")
        return []
    random.seed(11)
    ergebnisse = []
    for i, (q, x, y) in enumerate(
            random.sample(kandidaten, min(n, len(kandidaten))), 1):
        getauscht = random.random() < 0.5
        A, B = (y, x) if getauscht else (x, y)
        user = (f"=== NIEDERLAENDISCHER AUSGANGSTEXT ===\n{q}\n\n"
                f"=== UEBERSETZUNG A ===\n{A}\n\n=== UEBERSETZUNG B ===\n{B}")
        try:
            d = G.json_aus_antwort(
                G.chat(cfg, BLIND_SYSTEM, user, 0.2, rolle=rolle))
            if not d:
                raise RuntimeError("kein JSON")
            besser = d.get("besser")
            if besser in ("A", "B"):
                echt = ({"A": "revision", "B": "entwurf"} if getauscht
                        else {"A": "entwurf", "B": "revision"})[besser]
            else:
                echt = "gleichwertig"
            d["_echt"], d["_teil"] = echt, label
            ergebnisse.append(d)
            print(f"  {label} Paar {i}: {echt} ({d.get('abstand','?')})")
        except Exception as e:
            print(f"  {label} Paar {i} fehlgeschlagen: {e}")
    return ergebnisse


def briefing(name):
    hier = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(hier, f"briefing_{name}_vorlage.md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


# ==================================================================
def kosten_zeile(pfad):
    """Kosten dieser Variante aus der Differenzdatei neben dem Ergebnis."""
    if not os.path.exists(pfad):
        return "Kosten nicht erfasst"
    try:
        d = json.load(open(pfad, encoding="utf-8"))
    except Exception:
        return "Kosten nicht lesbar"
    summe, aufrufe, unsicher = 0.0, 0, False
    for rolle, e in d.items():
        t = G.tarif(e.get("modell", ""))
        aufrufe += int(e.get("aufrufe", 0))
        if not t:
            unsicher = True
            continue
        summe += (e.get("ein", 0) * t["ein"] + e.get("aus", 0) * t["aus"]) / 1e6
    return (f"{aufrufe} Aufrufe, {summe:.2f} $"
            + (" (unvollstaendig, Tarif unbekannt)" if unsicher else ""))


def variantenvergleich(cfg):
    """Vergleicht alle vorhandenen Varianten gegen die Basis (Paket 5).

    Varianten unterscheiden sich in Chunkgroesse ODER Modell — die Frage
    ist dieselbe, also ist es dieselbe Mechanik."""
    basis_p = TESTDIR + "/" + G.F["uebersetzung"]
    if not os.path.exists(basis_p):
        sys.exit("FEHLER: Die Basis fehlt. Erst:\n"
                 "  python3 uebersetzung.py --test")
    basis = open(basis_p, encoding="utf-8").read()

    da, fehlt = [], []
    for v in G.varianten(cfg):
        pfad = f"test{v['name']}/" + G.F["uebersetzung"]
        (da if os.path.exists(pfad) else fehlt).append((v, pfad))
    if not da:
        sys.exit("FEHLER: Keine Variante vorhanden. Erst:\n"
                 + "\n".join(f"  python3 uebersetzung.py --test --variante "
                             f"{v['name']}" for v, _ in fehlt))
    for v, _ in fehlt:
        print(f"Variante {v['name']}: nicht gerechnet, wird uebersprungen")

    def steckbrief(name, t, kosten):
        d, _ = G.diminutive_zaehlen(t)
        q, _, _ = G.perfekt_quote(t)
        w = len(t.split())
        return (f"  {name}: {w} Woerter, {len(G.absaetze(t))} Absaetze, "
                f"{d} Diminutive ({d/max(1,w/1000):.1f}/1000), "
                f"Perfekt {q:.1%}\n      {kosten}")

    print("\n=== Variantenvergleich ===")
    _, _, basis_b = G.variante_anwenden(cfg, {"name": "A"})
    print(steckbrief(f"A ({basis_b})", basis,
                     kosten_zeile(TESTDIR + "/kosten.json")))
    texte = []
    for v, pfad in da:
        t = open(pfad, encoding="utf-8").read()
        _, _, b = G.variante_anwenden(cfg, v)
        print(steckbrief(f"{v['name']} ({b})", t,
                         kosten_zeile(f"test{v['name']}/kosten.json")))
        texte.append((v["name"], b, t))

    for name, _, t in texte:
        stat, bsp = diffstat(basis, t)
        ausgabe_stat(stat, f"Unterschied A gegen {name}")
        if bsp:
            print(f"\nStichprobe A gegen {name}:")
            random.seed(3)
            for k, x, y in random.sample(bsp, min(8, len(bsp))):
                print(f"  [{k[:8]:8s}] {x[:52]:54s} -> {y[:52]}")

    if cfg["export_bewertung"]:
        L = ["# Variantenvergleich\n",
             f"- A ({basis_b}) ist die Basis"]
        L += [f"- {n} ({b})" for n, b, _ in texte]
        L += ["\nAlle Fassungen stammen aus demselben Ausgangstext. Sag mir, "
              "welche die beste ist und woran du es siehst — besonders an "
              "den Nahtstellen zwischen den Chunks, im Tempus und in der "
              "Figurenrede. Nenne die Variante beim Namen.\n",
              "## Variante A\n```", basis, "```"]
        for n, b, t in texte:
            L += [f"## Variante {n} — {b}\n```", t, "```"]
        open("bewertung_varianten.md", "w", encoding="utf-8").write(
            "\n".join(L))
        print("\nExportpaket: bewertung_varianten.md")


# ==================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lektorat", action="store_true")
    ap.add_argument("--variantenvergleich", "--chunkvergleich",
                    dest="variantenvergleich", action="store_true")
    ap.add_argument("--kein-modell", action="store_true")
    args = ap.parse_args()

    G.kopf("BEWERTUNG")
    cfg = G.lade_config()

    if args.variantenvergleich:
        variantenvergleich(cfg)
        return

    teile = G.lade_json(TESTDIR + "/teile.json", still=True)

    if args.lektorat:
        vor_p = TESTDIR + "/" + G.F["uebersetzung"]
        nach_p = TESTDIR + "/" + G.F["lektoriert"]
        if not os.path.exists(nach_p):
            sys.exit(f"FEHLER: {nach_p} fehlt. Erst lektorat.py --test.")
        vor = open(vor_p, encoding="utf-8").read()
        nach = open(nach_p, encoding="utf-8").read()
        stat, bsp = diffstat(vor, nach)
        ausgabe_stat(stat, "Lektorat gesamt")
        if teile:
            v1, v2 = teile_trennen(vor_p, teile)
            n1, n2 = teile_trennen(nach_p, teile)
            for name, a, b in (("Erzaehlung", v1, n1), ("Dialog", v2, n2)):
                s, _ = diffstat(a, b)
                if s:
                    ausgabe_stat(s, f"Lektorat — {name}")
        print("\nStichprobe substanzieller Aenderungen:")
        random.seed(5)
        for k, a, n in random.sample(bsp, min(12, len(bsp))):
            print(f"  [{k[:8]:8s}] {a[:52]:54s} -> {n[:52]}")

        if cfg["export_bewertung"]:
            gesamt = sum(stat.values()) or 1
            L = ["# Bewertungspaket — Testlektorat (deutsches Manuskript)\n",
                 f"- Stufenfolge: {' -> '.join(cfg['lektorat_passes'])}",
                 f"- Zielform: {cfg['varietaet']}, "
                 f"{'»…«' if cfg['quotes']=='guillemets' else '„…“'}",
                 f"- Diminutivpolitik: {cfg['diminutive']}",
                 f"- Tempuspolitik: {cfg['tempus']}\n",
                 "## Diff-Statistik\n\n| Kategorie | n | Anteil |\n|---|---:|---:|"]
            for k, v in sorted(stat.items(), key=lambda x: -x[1]):
                L.append(f"| {k} | {v} | {v/gesamt:.0%} |")
            L.append("")
            for datei, titel in (
                    (TESTDIR + "/normalisierung_report.txt",
                     "Deterministische Normalisierung"),
                    (TESTDIR + "/lektorat_warnungen.log", "Warnungen"),
                    (TESTDIR + "/qa_lektorat.txt", "Qualitaetspruefung")):
                if os.path.exists(datei):
                    L.append(f"## {titel}\n```")
                    L.append(open(datei, encoding="utf-8").read()[:4000])
                    L.append("```\n")
            if os.path.exists(TESTDIR + "/lektorat_diff.txt"):
                L.append("## Vollstaendiger Diff\n```")
                L.append(open(TESTDIR + "/lektorat_diff.txt",
                              encoding="utf-8").read()[:60000])
                L.append("```\n")
            L += ["---\n## Vor dem Lektorat\n```", vor,
                  "```\n## Nach dem Lektorat\n```", nach, "```"]
            open("bewertung_lektorat.md", "w", encoding="utf-8").write(
                "\n".join(L))
            t = briefing("lektorat")
            if t:
                open("briefing_lektorat.md", "w", encoding="utf-8").write(t)
            print("\nExportpaket: bewertung_lektorat.md")
            print("Briefing:    briefing_lektorat.md")
        # Der HTML-Bericht entsteht schon in lektorat.py; hier nur der Pfad.
        print(f"\nBericht:  {TESTDIR}/bericht.html")
        return

    # --- Testuebersetzung ---
    ent_p = TESTDIR + "/" + G.F["entwurf"]
    fin_p = TESTDIR + "/" + G.F["uebersetzung"]
    if not os.path.exists(fin_p):
        sys.exit(f"FEHLER: {fin_p} fehlt. Erst uebersetzung.py --test.")
    entwurf = open(ent_p, encoding="utf-8").read()
    final = open(fin_p, encoding="utf-8").read()

    if entwurf.strip() == final.strip():
        print("Entwurf und Endfassung identisch — offenbar ohne "
              "Revisionspass.")
        stat, bsp = {}, []
    else:
        stat, bsp = diffstat(entwurf, final)
        ausgabe_stat(stat, "Entwurf -> Revision, gesamt")
        if teile:
            e1, e2 = teile_trennen(ent_p, teile)
            f1, f2 = teile_trennen(fin_p, teile)
            for name, a, b in (("Erzaehlung", e1, f1), ("Dialog", e2, f2)):
                s, _ = diffstat(a, b)
                if s:
                    ausgabe_stat(s, f"Entwurf -> Revision, {name}")
        print("\nStichprobe substanzieller Aenderungen:")
        random.seed(5)
        for k, a, n in random.sample(bsp, min(14, len(bsp))):
            print(f"  [{k[:8]:8s}] {a[:52]:54s} -> {n[:52]}")

    # Kennzahlen
    print("\n=== Kennzahlen der Endfassung ===")
    d, tr = G.diminutive_zaehlen(final)
    w = len(final.split())
    q, mit, ges = G.perfekt_quote(final)
    print(f"  Diminutive: {d} ({d/max(1,w/1000):.1f} je 1000 Woerter), "
          f"Politik {cfg['diminutive']}")
    if tr:
        print(f"    haeufigste: "
              + ", ".join(f"{x} ({k})" for x, k in Counter(tr).most_common(6)))
    print(f"  Perfektanteil: {q:.1%} ({mit} von {ges} Saetzen), "
          f"Politik {cfg['tempus']}")

    blind, selbst = [], []
    if not args.kein_modell and entwurf.strip() != final.strip():
        print(f"\n{signal_kopf(cfg, 'judge', 'Blindes Urteil')} ...")
        import uebersetzung as U
        paras = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
        t1, t2, _ = U.testauszuege(paras, cfg["test_words_erzaehlung"],
                                   cfg["test_words_dialog"])
        e1, e2 = teile_trennen(ent_p, teile) if teile else (entwurf, "")
        f1, f2 = teile_trennen(fin_p, teile) if teile else (final, "")
        blind += blindbewertung(cfg, "\n\n".join(t1), e1, f1, 4, "Erzaehlung")
        if e2.strip():
            blind += blindbewertung(cfg, "\n\n".join(t2), e2, f2, 4, "Dialog")
        def ergebnis(liste, titel):
            if not liste:
                return
            print(f"\n  {titel}:")
            for teil in ("Erzaehlung", "Dialog"):
                c = Counter(x["_echt"] for x in liste if x["_teil"] == teil)
                if c:
                    print(f"    {teil:12s} "
                          + ", ".join(f"{k}: {v}" for k, v in c.items()))

        ergebnis(blind, "Ergebnis Fremdurteil")

        # Drittes Signal: dasselbe Modell, das uebersetzt hat. Getrennt
        # ausgewiesen, weil es wegen Selbstpraeferenz schwaecher ist —
        # zusammengezaehlt waere es ein verstecktes Uebergewicht.
        if G.modell_fuer(cfg, "uebersetzung") != G.modell_fuer(cfg, "judge"):
            print(f"\n{signal_kopf(cfg, 'uebersetzung', 'Selbstcheck')} ...")
            selbst += blindbewertung(cfg, "\n\n".join(t1), e1, f1, 2,
                                     "Erzaehlung", rolle="uebersetzung")
            if e2.strip():
                selbst += blindbewertung(cfg, "\n\n".join(t2), e2, f2, 2,
                                         "Dialog", rolle="uebersetzung")
            ergebnis(selbst, "Ergebnis Selbstcheck (nachrangig)")

    if cfg["export_bewertung"]:
        import uebersetzung as U
        paras = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
        t1, t2, dichte = U.testauszuege(paras, cfg["test_words_erzaehlung"],
                                        cfg["test_words_dialog"])
        gesamt = sum(stat.values()) or 1
        subst = sum(v for k, v in stat.items()
                    if k not in ("Typografie", "Interpunktion"))
        L = ["# Bewertungspaket — Testuebersetzung Niederlaendisch -> Deutsch\n",
             f"- Zielform: {cfg['varietaet']}, "
             f"{'»…«' if cfg['quotes']=='guillemets' else '„…“'}, "
             f"{'mit ß' if cfg['eszett'] else 'ohne ß'}",
             f"- Diminutivpolitik: **{cfg['diminutive']}** — gemessen: "
             f"{d} ({d/max(1,w/1000):.1f} je 1000 Woerter)",
             f"- Tempuspolitik: **{cfg['tempus']}** — gemessener "
             f"Perfektanteil: {q:.1%}",
             f"- Anrede: {cfg['anrede_vorgabe']}",
             f"- chunk_words {cfg['chunk_words']}, context_words "
             f"{cfg['context_words']}, temp {cfg['temperature_uebersetzung']}/"
             f"{cfg['temperature_revision']}",
             f"- Prueffgrenzen kalibriert: {cfg['ratio_min']:.2f}–"
             f"{cfg['ratio_max']:.2f}\n",
             f"## Diff-Statistik Entwurf -> Revision\n",
             f"{gesamt} Aenderungen, davon {subst} substanziell "
             f"({subst/gesamt:.0%}).\n",
             "| Kategorie | n | Anteil |\n|---|---:|---:|"]
        for k, v in sorted(stat.items(), key=lambda x: -x[1]):
            L.append(f"| {k} | {v} | {v/gesamt:.0%} |")
        L.append("")
        L += ["## Wie die Signale zu gewichten sind\n", GEWICHTUNG]
        for liste, rolle, titel in ((blind, "judge", "Blindes Urteil"),
                                    (selbst, "uebersetzung", "Selbstcheck")):
            if not liste:
                continue
            L.append(f"## {signal_kopf(cfg, rolle, titel)}\n")
            for i, x in enumerate(liste, 1):
                L.append(f"**{x.get('_teil')} {i}** — besser: "
                         f"{x.get('_echt')} (Abstand {x.get('abstand','?')})  \n"
                         f"{str(x.get('begruendung',''))[:400]}\n")
        wlog = TESTDIR + "/uebersetzung_warnungen.log"
        if os.path.exists(wlog):
            L += ["## Warnungen aus dem Lauf\n```",
                  open(wlog, encoding="utf-8").read()[:3000], "```\n"]
        e1, e2 = teile_trennen(ent_p, teile) if teile else (entwurf, "")
        f1, f2 = teile_trennen(fin_p, teile) if teile else (final, "")
        L += ["---\n# TEIL 1 — ERZAEHLPASSAGE\n",
              "## Niederlaendischer Ausgangstext\n```", "\n\n".join(t1),
              "```\n## Entwurf\n```", e1, "```\n## Nach Revision\n```", f1,
              "```\n",
              f"---\n# TEIL 2 — DIALOGPASSAGE (Redeanteil {dichte:.0%})\n",
              "## Niederlaendischer Ausgangstext\n```", "\n\n".join(t2),
              "```\n## Entwurf\n```", e2, "```\n## Nach Revision\n```", f2,
              "```"]
        open("bewertung_uebersetzung.md", "w", encoding="utf-8").write(
            "\n".join(L))
        t = briefing("bewertung")
        if t:
            open("briefing_bewertung.md", "w", encoding="utf-8").write(t)
        print("\nExportpaket: bewertung_uebersetzung.md")
        print("Briefing:    briefing_bewertung.md")


if __name__ == "__main__":
    main()
