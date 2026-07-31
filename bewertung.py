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
    python3 bewertung.py --chunkvergleich
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


def blindbewertung(cfg, quelle, a, b, n=4, label=""):
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
                G.chat(cfg, BLIND_SYSTEM, user, 0.2, rolle="judge"))
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
def chunkvergleich(cfg):
    a_p = TESTDIR + "/" + G.F["uebersetzung"]
    b_p = "testB/" + G.F["uebersetzung"]
    if not (os.path.exists(a_p) and os.path.exists(b_p)):
        sys.exit("FEHLER: Beide Varianten fehlen. Erst:\n"
                 "  python3 uebersetzung.py --test\n"
                 "  python3 uebersetzung.py --test --variante B")
    A = open(a_p, encoding="utf-8").read()
    B = open(b_p, encoding="utf-8").read()

    print(f"\n=== Chunkgroessen-Vergleich ===")
    print(f"  Variante A: {cfg['chunk_words']} Woerter/Chunk")
    print(f"  Variante B: {cfg['chunk_words_variante']} Woerter/Chunk\n")
    for name, t in (("A", A), ("B", B)):
        d, _ = G.diminutive_zaehlen(t)
        q, mit, ges = G.perfekt_quote(t)
        w = len(t.split())
        print(f"  {name}: {w} Woerter, {len(G.absaetze(t))} Absaetze, "
              f"{d} Diminutive ({d/max(1,w/1000):.1f}/1000), "
              f"Perfekt {q:.1%}")
    stat, bsp = diffstat(A, B)
    ausgabe_stat(stat, "Unterschied A gegen B")
    print("\nStichprobe der Unterschiede:")
    random.seed(3)
    for k, x, y in random.sample(bsp, min(12, len(bsp))):
        print(f"  [{k[:8]:8s}] {x[:52]:54s} -> {y[:52]}")

    if cfg["export_bewertung"]:
        L = ["# Chunkgroessen-Vergleich A gegen B\n",
             f"- A: {cfg['chunk_words']} Woerter je Chunk",
             f"- B: {cfg['chunk_words_variante']} Woerter je Chunk\n",
             "Beide Fassungen stammen aus demselben Ausgangstext, nur die "
             "Chunkgroesse unterscheidet sich. Sag mir, welche besser ist "
             "und woran du es siehst — besonders an den Nahtstellen zwischen "
             "den Chunks und im Tempus.\n",
             "## Variante A\n```", A, "```\n## Variante B\n```", B, "```"]
        open("bewertung_chunkgroesse.md", "w", encoding="utf-8").write(
            "\n".join(L))
        print("\nExportpaket: bewertung_chunkgroesse.md")


# ==================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lektorat", action="store_true")
    ap.add_argument("--chunkvergleich", action="store_true")
    ap.add_argument("--kein-modell", action="store_true")
    args = ap.parse_args()

    G.kopf("BEWERTUNG")
    cfg = G.lade_config()

    if args.chunkvergleich:
        chunkvergleich(cfg)
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

    blind = []
    if not args.kein_modell and entwurf.strip() != final.strip():
        print("\nBlinde Bewertung durch das lokale Modell ...")
        import uebersetzung as U
        paras = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
        t1, t2, _ = U.testauszuege(paras, cfg["test_words_erzaehlung"],
                                   cfg["test_words_dialog"])
        e1, e2 = teile_trennen(ent_p, teile) if teile else (entwurf, "")
        f1, f2 = teile_trennen(fin_p, teile) if teile else (final, "")
        blind += blindbewertung(cfg, "\n\n".join(t1), e1, f1, 4, "Erzaehlung")
        if e2.strip():
            blind += blindbewertung(cfg, "\n\n".join(t2), e2, f2, 4, "Dialog")
        if blind:
            print("\n  Ergebnis:")
            for teil in ("Erzaehlung", "Dialog"):
                c = Counter(x["_echt"] for x in blind if x["_teil"] == teil)
                if c:
                    print(f"    {teil:12s} "
                          + ", ".join(f"{k}: {v}" for k, v in c.items()))
            print("  (Selbstbewertung ist schwach — als drittes Signal "
                  "lesen.)")

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
        if blind:
            L.append("## Blinde Selbstbewertung des lokalen Modells\n")
            for i, x in enumerate(blind, 1):
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
