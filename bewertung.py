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
    """Zerlegt eine Testfassung in ihre Auszuege.

    Ohne teile.json wird geraten — die alte Fassung schnitt bei der
    Haelfte der Absaetze und verglich damit Erzaehlung gegen Dialog,
    sobald die Auszuege verschieden viele Absaetze hatten. Seit
    uebersetzung.py die Datei schreibt, ist das nur noch der Rueckfall.

    Gibt immer drei Teile zurueck; der dritte ist leer, wenn es keine
    Fallenpassage gibt."""
    paras = G.absaetze(open(pfad, encoding="utf-8").read())
    n1 = min(int(teile.get("erzaehlung", len(paras) // 2)), len(paras))
    n2 = min(n1 + int(teile.get("dialog", len(paras) - n1)), len(paras))
    return ("\n\n".join(paras[:n1]), "\n\n".join(paras[n1:n2]),
            "\n\n".join(paras[n2:]))


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


def zurueckrechnen(besser, getauscht, namen):
    """Welche Fassung meint das Modell, wenn es 'A' oder 'B' sagt?

    Eigene Funktion, damit sie pruefbar ist. Ein vertauschtes Etikett
    dreht das Ergebnis um, ohne dass irgendwo etwas auffaellt — das ist
    keine Stelle fuer eine Zeile mitten im Ablauf."""
    if besser not in ("A", "B"):
        return "gleichwertig"
    return ({"A": namen[1], "B": namen[0]} if getauscht
            else {"A": namen[0], "B": namen[1]})[besser]


def blindbewertung(cfg, quelle, a, b, n=4, label="", rolle="judge",
                   namen=("entwurf", "revision")):
    """Blindes Paarurteil. 'namen' benennt die beiden Fassungen — fuer
    Entwurf gegen Revision ebenso wie fuer Basis gegen Variante. Die
    Tauschlogik bleibt dieselbe: Welche Fassung als A erscheint,
    entscheidet der Zufall, sonst urteilt das Modell nach Position."""
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
                G.chat(cfg, BLIND_SYSTEM, user, rolle=rolle))
            if not d:
                raise RuntimeError("kein JSON")
            besser = d.get("besser")
            echt = zurueckrechnen(besser, getauscht, namen)
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
    for _, _, modell, e in G.kosten_posten({"kosten": d}):
        aufrufe += int(e.get("aufrufe", 0))
        dollar = G.kosten_dollar(e, G.tarif(modell))
        if dollar is None:
            unsicher = True
        else:
            summe += dollar
    return (f"{aufrufe} Aufrufe, {summe:.2f} $"
            + (" (unvollstaendig, Tarif unbekannt)" if unsicher else ""))


FUGE_SYSTEM = """Du bist eine erfahrene Literaturlektorin. Du siehst das \
Ende eines Abschnitts und den Anfang des folgenden, aus derselben deutschen \
Uebersetzung.

Beurteile AUSSCHLIESSLICH den Uebergang zwischen beiden, nicht ihre Qualitaet \
im Uebrigen:

1. Tempus und Person — bricht die Erzaehlhaltung an der Naht?
2. Anrede und Register — springt das Du/Sie, springt die Stilhoehe?
3. Wiederaufnahme — wird ein Pronomen benutzt, dessen Bezug nur im ersten \
Teil steht und dort verlorengeht?
4. Wiederholung — wird etwas erklaert, das schon dastand?
5. Terminologie — dasselbe Ding, zwei Woerter?

Ein unauffaelliger Uebergang ist das Normale und ein gutes Ergebnis.

Antworte NUR mit einem JSON-Objekt:
{"bruch": "keiner" | "leicht" | "deutlich",
 "art": "…", "stelle": "…", "begruendung": "…"}
Keine Codefences, kein Kommentar."""


def fugenurteil(cfg, praefix=TESTDIR + "/", n=8, kontext=120):
    """Wie teuer ist ein Kontext-Reset? Misst die Naht zwischen Chunks.

    Das ist die Zahl hinter 'kette_max': Im Stapelbetrieb (Paket G) laeuft
    die Kette nur so lange, wie ein Chunk auf den vorigen warten kann.
    Kuerzere Ketten heissen mehr Fugen, und ob das schadet, ist keine
    Geschmacksfrage — hier steht, wie oft eine Naht wirklich bricht.

    Verglichen wird die vorhandene Testuebersetzung mit sich selbst: Jede
    Chunkgrenze ist eine Naht, die MIT Rueckschau entstanden ist. Bricht
    sie schon dort, ist eine Kette ohne Rueckschau erst recht zu kurz."""
    st = G.lade_json(praefix + "uebersetzung_state.json", still=True)
    total = int(st.get("total") or 0)
    if total < 2:
        print(f"  Kein Testlauf in {praefix} — erst uebersetzung.py --test")
        return []
    stuecke = [G.teil_lesen("uebersetzung", i, praefix) for i in range(total)]
    stuecke = [s for s in stuecke if s and s.strip()]
    if len(stuecke) < 2:
        print("  Zu wenige Chunks für ein Fugenurteil")
        return []

    random.seed(23)
    fugen = list(range(1, len(stuecke)))
    random.shuffle(fugen)
    ergebnisse = []
    for nr, i in enumerate(fugen[:n], 1):
        vorher = G.schlusswoerter(stuecke[i - 1], kontext)
        nachher = G.anfangswoerter(stuecke[i], kontext)
        user = (f"=== ENDE DES ABSCHNITTS ===\n{vorher}\n\n"
                f"=== ANFANG DES FOLGENDEN ===\n{nachher}")
        try:
            d = G.json_aus_antwort(G.chat(cfg, FUGE_SYSTEM, user,
                                          rolle="judge"))
            if not d:
                raise RuntimeError("kein JSON")
            d["_fuge"] = i
            ergebnisse.append(d)
            print(f"  Fuge nach Chunk {i}: {d.get('bruch', '?')} "
                  f"({d.get('art', '')[:40]})")
        except Exception as e:
            print(f"  Fuge nach Chunk {i} fehlgeschlagen: {e}")
    return ergebnisse


def fugen_auswerten(ergebnisse):
    """Eine Zahl und eine Empfehlung fuer 'kette_max'."""
    if not ergebnisse:
        return
    zaehl = Counter(str(d.get("bruch", "?")) for d in ergebnisse)
    ges = sum(zaehl.values())
    schlecht = zaehl.get("deutlich", 0)
    leicht = zaehl.get("leicht", 0)
    print(f"\n=== Fugenurteil: {ges} Nähte ===")
    for k in ("keiner", "leicht", "deutlich"):
        if zaehl.get(k):
            print(f"  {k:10s} {zaehl[k]:3d}  {zaehl[k]/ges:5.0%}")
    quote = (schlecht + 0.5 * leicht) / ges
    print(f"\n  Bruchmaß {quote:.0%} "
          f"(deutlich zählt voll, leicht zur Hälfte)")
    # Die Marken sind Konvention, nicht Messung — sie machen aus einer
    # Zahl eine Entscheidung und stehen deshalb hier und nicht im Kopf
    # des Lesers.
    if quote < 0.10:
        print("  Die Nähte halten. Kurze Ketten im Stapelbetrieb sind "
              "vertretbar;\n  'kette_max' darf klein sein.")
    elif quote < 0.25:
        print("  Die Nähte halten überwiegend. 'kette_max' mittelgroß "
              "wählen und\n  nach dem ersten Stapellauf erneut messen.")
    else:
        print("  Die Nähte brechen zu oft. Der Kontext-Reset kostet hier "
              "wirklich etwas —\n  'kette_max' groß wählen oder auf "
              "Stapelverarbeitung verzichten.")


def variantenvergleich(cfg, kein_modell=False):
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

    urteile = {}
    if not kein_modell:
        import uebersetzung as U
        paras = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
        t1, t2, t3, _ = U.testauszuege(
            paras, cfg["test_words_erzaehlung"], cfg["test_words_dialog"],
            int(cfg.get("test_words_fallen", 0) or 0))
        # Erzaehlung UND Dialog, getrennt. Bei NL->DE liegt die Schwaeche
        # im Dialog — ein Vergleich, der ihn auslaesst, beantwortet die
        # Frage nur zur Haelfte und sieht trotzdem vollstaendig aus.
        teile = G.lade_json(TESTDIR + "/teile.json", still=True)
        basis1, basis2, basis3 = (teile_trennen(basis_p, teile) if teile
                                  else (basis, "", ""))
        print(f"\n{signal_kopf(cfg, 'judge', 'Blindes Urteil je Variante')}")
        for name, _, t in texte:
            pfad = f"test{name}/" + G.F["uebersetzung"]
            v1, v2, v3 = (teile_trennen(pfad, teile) if teile
                          else (t, "", ""))
            ergebnisse = blindbewertung(cfg, "\n\n".join(t1), basis1, v1, 4,
                                        f"{name} Erzaehlung",
                                        namen=("A", name))
            if v2.strip() and t2:
                ergebnisse += blindbewertung(cfg, "\n\n".join(t2), basis2,
                                             v2, 4, f"{name} Dialog",
                                             namen=("A", name))
            # Der dritte Auszug ist der, an dem sich die Sprachrichtung
            # entscheidet: Wenn eine Variante die Fallen besser trifft,
            # zeigt es sich hier und nicht in der ruhigen Erzaehlung.
            if v3.strip() and t3:
                ergebnisse += blindbewertung(cfg, "\n\n".join(t3), basis3,
                                             v3, 4, f"{name} Fallen",
                                             namen=("A", name))
            urteile[name] = {
                teil: Counter(x["_echt"] for x in ergebnisse
                              if x["_teil"].endswith(teil))
                for teil in ("Erzaehlung", "Dialog", "Fallen")}
            for teil, c in urteile[name].items():
                if c:
                    print(f"  A gegen {name}, {teil:11s} "
                          + ", ".join(f"{k}: {v}" for k, v in c.items()))

    if cfg["export_bewertung"]:
        L = ["# Variantenvergleich\n",
             f"- A ({basis_b}) ist die Basis"]
        L += [f"- {n} ({b})" for n, b, _ in texte]
        if urteile:
            L.append("\n## Blindes Urteil (Paarvergleich gegen die Basis)\n")
            L.append("Erzaehlung und Dialog getrennt — bei diesem Sprachpaar "
                     "liegt die Schwaeche im Dialog.\n")
            L.append("| Variante | Teil | Urteile |\n|---|---|---|")
            for name, teile_c in urteile.items():
                for teil, c in teile_c.items():
                    L.append(f"| {name} | {teil} | "
                             + (", ".join(f"{k}: {v}" for k, v in c.items())
                                or "kein Urteil") + " |")
            L.append("")
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
    ap.add_argument("--fugen", action="store_true",
                    help="beurteilt die Naehte zwischen den Chunks — die "
                         "Zahl hinter 'kette_max' im Stapelbetrieb")
    ap.add_argument("--variante", default="A",
                    help="mit --lektorat: die Variante beurteilen, die "
                         "'lektorat.py --test --variante X' erzeugt hat")
    args = ap.parse_args()

    G.kopf("BEWERTUNG")
    cfg = G.lade_config()

    # Der Variantenvergleich stellt die Varianten GEGEN die Basis; sein
    # Bezugspunkt muss 'test/' bleiben. '--variante' gilt deshalb nur fuer
    # das Lektoratsurteil, wo es eine einzelne Variante beurteilt.
    if args.variante != "A":
        if not args.lektorat:
            sys.exit("FEHLER: --variante gilt nur zusammen mit --lektorat.\n"
                     "  Uebersetzungen vergleicht: "
                     "python3 bewertung.py --variantenvergleich")
        if not any(v["name"] == args.variante for v in G.varianten(cfg)):
            moeglich = ", ".join(v["name"] for v in G.varianten(cfg)) or "keine"
            sys.exit(f"FEHLER: Variante '{args.variante}' steht nicht in "
                     f"projekt.json.\n  Moeglich: {moeglich}")
        globals()["TESTDIR"] = "test" + args.variante
        cfg, _, beschreibung = G.variante_anwenden(
            cfg, next(v for v in G.varianten(cfg)
                      if v["name"] == args.variante))
        print(f"Variante {args.variante}: {beschreibung}")
        print(f"Verzeichnis: {TESTDIR}/\n")
    # Die Bewertung urteilt ausschliesslich ueber die Testauszuege; ihre
    # Urteilsaufrufe gehoeren damit zur Testrechnung, nicht zum Buch.
    G.lauf_setzen(TESTDIR)

    if args.variantenvergleich:
        variantenvergleich(cfg, kein_modell=args.kein_modell)
        return

    if args.fugen:
        if args.kein_modell:
            sys.exit("FEHLER: --fugen braucht ein Modell.")
        print(f"\n{signal_kopf(cfg, 'judge', 'Fugenurteil')}")
        fugen_auswerten(fugenurteil(cfg))
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
            v1, v2, v3 = teile_trennen(vor_p, teile)
            n1, n2, n3 = teile_trennen(nach_p, teile)
            for name, a, b in (("Erzaehlung", v1, n1), ("Dialog", v2, n2),
                               ("Fallen", v3, n3)):
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
            e1, e2, e3 = teile_trennen(ent_p, teile)
            f1, f2, f3 = teile_trennen(fin_p, teile)
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
        t1, t2, t3, _ = U.testauszuege(
            paras, cfg["test_words_erzaehlung"], cfg["test_words_dialog"],
            int(cfg.get("test_words_fallen", 0) or 0))
        e1, e2, e3 = (teile_trennen(ent_p, teile) if teile
                      else (entwurf, "", ""))
        f1, f2, f3 = (teile_trennen(fin_p, teile) if teile
                      else (final, "", ""))
        blind += blindbewertung(cfg, "\n\n".join(t1), e1, f1, 4, "Erzaehlung")
        if e2.strip():
            blind += blindbewertung(cfg, "\n\n".join(t2), e2, f2, 4, "Dialog")
        if e3.strip() and t3:
            blind += blindbewertung(cfg, "\n\n".join(t3), e3, f3, 4, "Fallen")
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
        t1, t2, t3, kennzahlen = U.testauszuege(
            paras, cfg["test_words_erzaehlung"], cfg["test_words_dialog"],
            int(cfg.get("test_words_fallen", 0) or 0))
        dichte = kennzahlen["dialogdichte"]
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
             f"{cfg['context_words']}, Vorwegschau "
             f"{cfg.get('context_words_voraus', 0)}, Denktiefe "
             f"{cfg.get('effort_uebersetzung', '?')}/"
             f"{cfg.get('effort_revision', '?')}",
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
        e1, e2, e3 = (teile_trennen(ent_p, teile) if teile
                      else (entwurf, "", ""))
        f1, f2, f3 = (teile_trennen(fin_p, teile) if teile
                      else (final, "", ""))
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
