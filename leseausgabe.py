#!/usr/bin/env python3
"""
Leseausgabe: Quelle, Entwurf und lektorierte Fassung nebeneinander.

    python3 leseausgabe.py
    python3 leseausgabe.py --test          # die Testauszuege
    python3 leseausgabe.py --datei X.html

Wofuer das da ist: Am Ende eines Laufs liegen drei Berichte nebeneinander
— bericht.html zeigt Aenderungen, screening_review.md Verdachtsstellen,
qa_konsistenz.txt Kennzahlen. Keiner davon ist der deutsche Text neben
dem niederlaendischen, und genau den liest ein Mensch, der das Buch
verantworten soll. Diese Datei erzeugt ihn.

Drei Entscheidungen, die nicht aussehen wie Zufall:

  - Die Zeilen entstehen chunkweise, nicht ueber den ganzen Text. Quelle
    und Zielfassung lassen sich nicht ueber Aehnlichkeit paaren — es sind
    verschiedene Sprachen, ein Textvergleich liefert Rauschen. Bleibt die
    Zuordnung ueber die Position, und die driftet, sobald ein Absatz
    verschmilzt. Chunkgrenzen fangen die Drift ein: was in Chunk 12
    verrutscht, ist in Chunk 13 wieder gerade.
  - Der lektorierte Text wird dagegen ueber Aehnlichkeit zugeordnet
    (diffview.align). Das ist dieselbe Sprache, dort traegt der Vergleich.
  - Aenderungsmarken stehen immer im HTML und werden per CSS ein- und
    ausgeblendet. Zwei Fassungen desselben Absatzes im Dokument waeren
    doppelte Datenmenge und zwei Stellen, die auseinanderlaufen koennen.

Der Schritt liest nur und schreibt genau eine Datei.
"""

import argparse
import difflib
import hashlib
import html
import os
import re
import sys

import gemeinsam as G
import uebersetzung as U

AUSGABE      = "leseausgabe.html"
DIFF         = "lektorat_diff.txt"
BEGRUENDUNGEN = "begruendungen.json"
SCHIRM       = "screening_review.md"

# Ab dieser Breite stehen drei Spalten nebeneinander. Darunter faellt der
# Entwurf in eine eigene Zeile unter das Paar — auf einem Tablet im
# Hochformat sind drei Prosaspalten nicht mehr lesbar.
BREITE_DREI = 1100

# Markdown-Tabellen von annotation.py maskieren Zellentrenner als \| —
# ein naives split("|") zerlegt dann mitten im Befund.
TRENNER = re.compile(r"(?<!\\)\|")

_D = None


def diffview():
    """diffview liegt im Code-, nicht im Arbeitsverzeichnis — und wird
    je Absatz gebraucht, also genau einmal geholt."""
    global _D
    if _D is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import diffview
        _D = diffview
    return _D


# ==================================================================
# Quellen einlesen
# ==================================================================
def quellchunks(cfg, test=False, praefix=""):
    """Baut die Quellchunks genau so, wie uebersetzung.py es tut.

    'Genau so' heisst seit August 2026: ueber dieselbe Funktion. Die
    frueheren zwei Fassungen sahen gleich aus und liefen auseinander,
    sobald der Lauf ebenen.json las und diese hier weiter nur den
    Rahmenmarker — dann stehen in der Leseausgabe fremde Absaetze
    nebeneinander, und niemand sieht es, weil beide Spalten fuer sich
    plausibel aussehen. Genau das steht seit jeher in diesem Docstring;
    die Warnung hat den Fehler nicht verhindert, eine gemeinsame Funktion
    tut es."""
    paras_alle = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
    if test:
        t1, t2, t3, _ = U.testauszuege(
            paras_alle, cfg["test_words_erzaehlung"], cfg["test_words_dialog"],
            int(cfg.get("test_words_fallen", 0) or 0))
        chunks, marken = [], {}
        for gruppe in (t1, t2, t3):
            if gruppe:
                chunks.extend(G.chunks_bauen(gruppe, cfg["chunk_words"]))
        return paras_alle, marken, chunks
    marken, chunks, _, _ = G.quellchunks_wie_lauf(cfg, praefix)
    return paras_alle, marken, chunks


def screening_lesen(praefix=""):
    """Verdachtsstellen je Chunknummer aus screening_review.md."""
    pfad = praefix + SCHIRM
    raus = {}
    if not os.path.exists(pfad):
        return raus
    for zeile in open(pfad, encoding="utf-8"):
        if not zeile.startswith("|"):
            continue
        felder = [f.strip().replace("\\|", "|")
                  for f in TRENNER.split(zeile.strip().strip("|"))]
        if len(felder) != 3 or not felder[0].isdigit():
            continue
        raus.setdefault(int(felder[0]), []).append((felder[1], felder[2]))
    return raus


def gruende_lesen(praefix=""):
    """Begruendungen, indiziert ueber (Kategorie, alt, neu).

    begruendungen.json ist ueber die Chunknummer des LEKTORATS-Laufs
    verschluesselt; die Leseausgabe kennt nur ihre eigenen Chunks, und die
    Zaehlung ist eine andere (das Lektorat packt den deutschen Text neu).
    lektorat_diff.txt haelt beides nebeneinander und loest den Umweg auf."""
    roh = G.lade_json(praefix + BEGRUENDUNGEN, still=True)
    diff = praefix + DIFF
    if not roh or not os.path.exists(diff):
        return {}
    D = diffview()

    raus = {}
    for chunk, _name, vorher, nachher in D.read_difffile(diff):
        for a, b in D.align(vorher, nachher):
            for kat, _links, alt, neu, _rechts in D.changes(a, b, 7):
                kennung = hashlib.sha256(
                    f"{chunk}|{kat}|{alt}|{neu}".encode("utf-8")
                ).hexdigest()[:8]
                if kennung in roh:
                    raus[(kat, alt, neu)] = roh[kennung]
    return raus


# ==================================================================
# Zeilen bauen
# ==================================================================
def _zitatzeile(text, z):
    """Eine Zeile fuer einen eingesetzten Zitatabsatz."""
    quelle = ""
    if z:
        attribution = str(z.get("attribution", "")).strip()
        quelle = (attribution if text.strip() == attribution
                  else str(z.get("text", "")).strip())
        if text.startswith("[[Niederländisch:"):
            quelle = ""            # dieser Absatz ist selbst schon die Quelle
    return {"chunk": 0, "quelle": quelle or None, "entwurf": None,
            "uebersetzung": text, "lektoriert": None,
            "zitat": True, "offen": text.startswith("[["), "kapitel": ""}


def chunkprobe(chunks, praefix=""):
    """Passt die hier gebaute Chunkfolge zu der, die gelaufen ist?

    Der gefaehrlichste Fehler dieser Datei ist keine Ausnahme, sondern ein
    Dokument, das gut aussieht und in dem ab Absatz 40 die falschen Saetze
    nebeneinanderstehen. Passiert, sobald sich chunk_words, rahmen_marker
    oder zitate.json seit dem Lauf geaendert haben. uebersetzung_state.json
    haelt die Zahl von damals — also wird sie verglichen."""
    st = G.lade_json(praefix + "uebersetzung_state.json", still=True)
    damals = int(st.get("total") or 0)
    if damals and damals != len(chunks):
        return (f"Chunkzahl weicht ab: der Lauf hatte {damals}, aus der "
                f"aktuellen Konfiguration ergeben sich {len(chunks)}. "
                f"Quelle und Zielfassung stehen dann verschoben "
                f"nebeneinander. Pruefen: chunk_words, rahmen_marker, "
                f"zitate.json.")

    return ""


def spielprobe(zeilen, praefix=""):
    """Reproduziert die gebaute Zielspalte das Manuskript Absatz fuer Absatz?

    Die Chunkzahl allein reicht als Probe nicht: Verschiebt sich nur die
    Zusammensetzung — ein geaendertes zitate.json genuegt dafuer —, bleibt
    sie gleich und die Paare sind trotzdem falsch. Ein Laengenvergleich
    hilft auch nicht, weil ein Versatz um eine Position aehnlich lange
    Absaetze gegeneinanderstellt.

    Exakt ist nur der Abgleich mit dem, was der Lauf geschrieben hat:
    uebersetzung_deutsch.txt ist die zusammengesetzte Wahrheit. Was die
    Leseausgabe aus teile/ und zitate.json baut, muss genau das ergeben."""
    pfad = praefix + G.F["uebersetzung"]
    if not os.path.exists(pfad):
        return ""
    gebaut = [z["uebersetzung"] for z in zeilen if z["uebersetzung"]]
    echt = G.absaetze(open(pfad, encoding="utf-8").read())
    if gebaut == echt:
        return ""
    hinweis = ("Quelle und Zielfassung stehen dann verschoben "
               "nebeneinander. Pruefen: chunk_words, rahmen_marker, "
               "zitate.json — und ob teile/ noch zum Lauf gehoert.")
    if len(gebaut) != len(echt):
        return (f"Die Zielspalte hat {len(gebaut)} Absaetze, "
                f"{G.F['uebersetzung']} hat {len(echt)}. {hinweis}")
    erste = next(i for i, (a, b) in enumerate(zip(gebaut, echt)) if a != b)
    return (f"Die Zielspalte weicht ab Absatz {erste + 1} von "
            f"{G.F['uebersetzung']} ab. {hinweis}")


def zeilen_bauen(cfg, praefix="", test=False):
    """Eine Zeile je Absatz: Quelle, Entwurf, Uebersetzung, Chunknummer."""
    paras_alle, marken, chunks = quellchunks(cfg, test, praefix)
    warnung = chunkprobe(chunks, praefix)
    zeilen = []
    for i, (qtext, _geschuetzt) in enumerate(chunks):
        q = G.absaetze(qtext)
        d = G.absaetze(G.teil_lesen("uebersetzung", i, praefix) or "")
        e = G.absaetze(G.teil_lesen("entwurf", i, praefix) or "")
        for k in range(max(len(q), len(d))):
            zeilen.append({
                "chunk":        i + 1,
                "quelle":       q[k] if k < len(q) else None,
                "entwurf":      e[k] if k < len(e) else None,
                "uebersetzung": d[k] if k < len(d) else None,
                "lektoriert":   None,
                "zitat":        False,
                "kapitel":      "",
            })

    if not any(marken.values()):
        return zeilen, warnung or spielprobe(zeilen, praefix)

    # Zitate holt sich die Leseausgabe von der Funktion, die sie auch ins
    # Manuskript schreibt — nicht durch Nachbauen des Wortlauts. Ein
    # Platzhalter ist dort zwei Absaetze lang und formuliert anders; eine
    # zweite Fassung hier waere beim naechsten Umbau still falsch.
    de = [z["uebersetzung"] for z in zeilen if z["uebersetzung"] is not None]
    mit_zitaten, _ = U.zitate_einsetzen("\n\n".join(de), marken, paras_alle)
    neu = G.absaetze(mit_zitaten)

    # Einfuegestelle -> Zitat, mit derselben Rechnung wie zitate_einsetzen().
    zitat_je_stelle = {}
    for idx in sorted(k for k, v in marken.items() if v):
        stelle = min(sum(1 for j in range(idx) if j not in marken), len(de))
        zitat_je_stelle[stelle] = marken[idx]

    raus, j, p = [], 0, 0          # j laeuft ueber 'neu', p ueber 'de'
    for zeile in zeilen:
        if zeile["uebersetzung"] is None:
            raus.append(zeile)
            continue
        while j < len(neu) and neu[j] != zeile["uebersetzung"]:
            raus.append(_zitatzeile(neu[j], zitat_je_stelle.get(p)))
            j += 1
        raus.append(zeile)
        j += 1
        p += 1
    while j < len(neu):
        raus.append(_zitatzeile(neu[j], zitat_je_stelle.get(p)))
        j += 1
    return raus, warnung or spielprobe(raus, praefix)


def lektorat_anhaengen(zeilen, praefix=""):
    """Haengt die lektorierte Fassung an. True, wenn sie vorliegt.

    Hier ist der Aehnlichkeitsvergleich richtig: beide Seiten sind
    deutsch, und das Lektorat verschiebt Absaetze allenfalls einzeln."""
    pfad = praefix + G.F["lektoriert"]
    if not os.path.exists(pfad):
        return False
    D = diffview()

    vorher = [z["uebersetzung"] or "" for z in zeilen]
    nachher = G.absaetze(open(pfad, encoding="utf-8").read())
    stelle = 0
    for a, b in D.align(vorher, nachher):
        if a is None:                 # Zugang im Lektorat, keiner Zeile eigen
            continue
        if stelle < len(zeilen):
            zeilen[stelle]["lektoriert"] = b
        stelle += 1
    return True


def kapitel_zuordnen(zeilen, kapitel):
    """Je Zeile die zuletzt begonnene Kapitelueberschrift.

    Laengster Treffer gewinnt: Eine kurze Ueberschrift, die in einer
    langen als Teilzeichenkette steckt, darf sie nicht verdraengen."""
    aktuell = ""
    for z in zeilen:
        q = z.get("quelle") or ""
        treffer = [k for k in kapitel if k and k in q]
        if treffer:
            aktuell = max(treffer, key=len)
        z["kapitel"] = aktuell


# ==================================================================
# Darstellung
# ==================================================================
def wortdiff(alt, neu):
    """Der neue Absatz mit Marken an den geaenderten Stellen.

    Getilgtes bleibt als <del> stehen — wer prueft, muss sehen, was
    verschwunden ist, nicht nur was dazukam."""
    e = html.escape
    if neu is None:
        return ""
    if alt is None or alt == neu:
        return e(neu)
    a, b = alt.split(), neu.split()
    stuecke = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        weg, hin = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if tag == "equal":
            stuecke.append(e(hin))
        elif tag == "insert":
            stuecke.append(f"<ins>{e(hin)}</ins>")
        elif tag == "delete":
            stuecke.append(f"<del>{e(weg)}</del>")
        else:
            stuecke.append(f"<del>{e(weg)}</del> <ins>{e(hin)}</ins>")
    return " ".join(s for s in stuecke if s)


KOPF = """<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(titel)s</title><style>
:root{--bg:#fbfaf8;--fg:#1a1a1a;--matt:#6b6b6b;--linie:#e2ded6;--karte:#fff;
--marke:#8a6d3b;--ins:#0a5a0a;--insbg:#dff3df;--del:#8b0000;--delbg:#fbe3e3;
--zitat:#7a5c9e;--offen:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#16171a;--fg:#e6e4e0;
--matt:#9a978f;--linie:#2f3136;--karte:#1c1e22;--marke:#c9a227;--ins:#7fd07f;
--insbg:#1d2f1d;--del:#e08a8a;--delbg:#341d1d;--zitat:#b498d8;--offen:#ff8a80}}
*{box-sizing:border-box}
body{font:16px/1.7 Georgia,"Iowan Old Style",serif;margin:0;
background:var(--bg);color:var(--fg)}
header{position:sticky;top:0;z-index:5;background:var(--bg);
border-bottom:1px solid var(--linie);padding:.7rem 1rem .6rem}
h1{font-size:1.15rem;margin:0 0 .2rem;font-weight:600}
.meta{color:var(--matt);font-size:.8rem;font-family:system-ui,sans-serif}
.regler{margin-top:.5rem;font:13px/1.5 system-ui,sans-serif;color:var(--matt);
display:flex;flex-wrap:wrap;gap:.9rem;align-items:center}
.regler label{cursor:pointer;user-select:none}
nav{font:13px/1.9 system-ui,sans-serif;padding:.8rem 1rem;
border-bottom:1px solid var(--linie)}
nav a{color:var(--matt);text-decoration:none;margin-right:1rem;
white-space:nowrap}
nav a:hover{color:var(--fg);text-decoration:underline}
main{padding:0 1rem 4rem}
h2{font-size:1rem;font-family:system-ui,sans-serif;font-weight:600;
margin:2.4rem 0 .2rem;padding-top:.6rem;border-top:2px solid var(--linie)}
h2 .fass{display:block;font-weight:400;color:var(--matt);font-size:.85rem;
margin-top:.15rem}
.zeile{display:grid;gap:0 1.6rem;padding:.5rem 0;
border-bottom:1px solid var(--linie);
grid-template-columns:1fr 1fr 1fr;
grid-template-areas:"q e l"}
.q{grid-area:q}.e{grid-area:e}.l{grid-area:l}
.q{color:var(--matt);font-size:.94rem}
.e{color:var(--matt);font-size:.94rem}
.nr{font:11px/1 system-ui,sans-serif;color:var(--linie);
float:right;margin-left:.5rem}
ins{background:var(--insbg);color:var(--ins);text-decoration:none;
padding:0 .12em;border-radius:2px}
del{background:var(--delbg);color:var(--del);padding:0 .12em;border-radius:2px}
.notizen{margin:.45rem 0 .2rem;font:13px/1.5 system-ui,sans-serif}
.notiz{border-left:3px solid var(--marke);padding:.2rem .6rem;margin:.25rem 0;
background:var(--karte);border-radius:0 3px 3px 0}
.notiz b{color:var(--marke);font-weight:600}
.notiz.grund{border-left-color:var(--matt)}
.zitat .l,.zitat .q{color:var(--zitat);font-style:italic}
.zitat.luecke .l{color:var(--offen);font-style:normal;font-weight:600}
.leer{color:var(--linie)}
.warnung{margin-top:.55rem;padding:.4rem .7rem;border-left:3px solid var(--offen);
background:var(--karte);font:13px/1.5 system-ui,sans-serif;border-radius:0 3px 3px 0}
.warnung b{color:var(--offen)}
/* Regler: eine Darstellung, per CSS gefiltert */
body.ohne-marken ins{background:none;color:inherit;padding:0}
body.ohne-marken del{display:none}
body.ohne-notizen .notizen{display:none}
body.ohne-entwurf .zeile{grid-template-columns:1fr 1fr;
grid-template-areas:"q l"}
body.ohne-entwurf .e{display:none}
body.nur-befunde .zeile:not(.hat-befund){display:none}
body.nur-geaendert .zeile:not(.hat-aenderung){display:none}
@media (max-width:%(breite)spx){
.zeile{grid-template-columns:1fr 1fr;grid-template-areas:"q l" "e e"}
.e{padding-top:.4rem;border-top:1px dotted var(--linie)}}
@media print{header,nav,.regler{position:static}
body{background:#fff;color:#000;font-size:10pt}
.zeile{break-inside:avoid}}
</style>
"""

REGLER = [("entwurf",   "ohne-entwurf",   "Entwurf",            True),
          ("marken",    "ohne-marken",    "Änderungen markiert", True),
          ("notizen",   "ohne-notizen",   "Randnotizen",        True),
          ("befunde",   "nur-befunde",    "nur mit Befund",     False),
          ("geaendert", "nur-geaendert",  "nur geändert",       False)]

SKRIPT = """
<script>
var b=document.body;
document.querySelectorAll('.regler input').forEach(function(k){
  k.addEventListener('change',function(){
    b.classList.toggle(k.dataset.klasse, k.dataset.invers ? k.checked : !k.checked);
  });
});
// Auf schmalen Geraeten faengt die Ausgabe ohne Entwurfsspalte an.
if (window.innerWidth < %(breite)s) {
  var e=document.querySelector('.regler input[data-name=entwurf]');
  if (e) { e.checked=false; e.dispatchEvent(new Event('change')); }
}
</script>
"""


def html_bauen(zeilen, kapitel, befunde, gruende, titel,
               mit_lektorat, warnung=""):
    e = html.escape
    teile = [KOPF % {"titel": e(titel), "breite": BREITE_DREI}]

    # --- Kopf mit Kennzahlen und Reglern ---------------------------------
    n_geaendert = sum(1 for z in zeilen
                      if z["lektoriert"] and z["lektoriert"] != z["uebersetzung"])
    n_befunde = sum(len(befunde.get(c, []))
                    for c in {z["chunk"] for z in zeilen if z["chunk"]})
    n_kapitel = len({z["kapitel"] for z in zeilen if z["kapitel"]})
    teile.append("<header>")
    teile.append(f"<h1>{e(titel)}</h1>")
    teile.append(f'<div class="meta">{len(zeilen)} Absätze · '
                 f'{n_kapitel or "keine"} Kapitel · '
                 f'{n_geaendert} lektoriert · '
                 f'{n_befunde} Verdachtsstellen'
                 + ("" if mit_lektorat else
                    " · <b>noch ohne lektorierte Fassung</b>") + "</div>")
    teile.append('<div class="regler">')
    for name, klasse, beschriftung, an in REGLER:
        invers = "" if an else ' data-invers="1"'
        teile.append(f'<label><input type="checkbox" data-name="{name}" '
                     f'data-klasse="{klasse}"{invers}'
                     f'{" checked" if an else ""}> {e(beschriftung)}</label>')
    teile.append("</div>")
    if warnung:
        teile.append(f'<div class="warnung"><b>Achtung</b> {e(warnung)}</div>')
    teile.append("</header>")

    # --- Kapitelnavigation ----------------------------------------------
    reihenfolge = []
    for z in zeilen:
        if z["kapitel"] and z["kapitel"] not in reihenfolge:
            reihenfolge.append(z["kapitel"])
    if reihenfolge:
        teile.append("<nav>")
        for nr, k in enumerate(reihenfolge, 1):
            teile.append(f'<a href="#k{nr}">{e(k[:60])}</a>')
        teile.append("</nav>")

    # --- Der Text --------------------------------------------------------
    teile.append("<main>")
    aktuell, gesehen = None, set()
    for z in zeilen:
        if z["kapitel"] != aktuell:
            aktuell = z["kapitel"]
            if aktuell:
                nr = reihenfolge.index(aktuell) + 1
                fass = str(kapitel.get(aktuell, "")).strip()
                teile.append(f'<h2 id="k{nr}">{e(aktuell)}'
                             + (f'<span class="fass">{e(fass)}</span>'
                                if fass else "") + "</h2>")

        # Screening-Befunde haengen am Chunk, nicht am Absatz — sie stehen
        # deshalb einmal beim ersten Absatz des Chunks.
        marken = []
        if z["chunk"] and z["chunk"] not in gesehen:
            gesehen.add(z["chunk"])
            for art, befund in befunde.get(z["chunk"], []):
                marken.append(f'<div class="notiz"><b>{e(art)}</b> '
                              f'{e(befund)}</div>')
        # Begruendungen zu den Aenderungen dieses Absatzes.
        gruende_hier = []
        if gruende and z["lektoriert"] and z["uebersetzung"]:
            for kat, _l, alt, neu, _r in _aenderungen(z["uebersetzung"],
                                                      z["lektoriert"]):
                grund = gruende.get((kat, alt, neu))
                if grund:
                    gruende_hier.append(
                        f'<div class="notiz grund"><b>{e(kat)}</b> '
                        f'{e(grund)}</div>')
        notizen = marken + gruende_hier

        klassen = ["zeile"]
        if z["zitat"]:
            klassen.append("zitat")
            if z.get("offen"):
                klassen.append("luecke")
        # 'nur mit Befund' meint die Verdachtsstellen des Screenings. Eine
        # Begruendung ist keiner — sonst filtert der Regler jede lektorierte
        # Zeile mit ein und zeigt nichts mehr an.
        if marken:
            klassen.append("hat-befund")
        if z["lektoriert"] and z["lektoriert"] != z["uebersetzung"]:
            klassen.append("hat-aenderung")

        ziel = z["lektoriert"] if mit_lektorat else z["uebersetzung"]
        rechts = (wortdiff(z["uebersetzung"], ziel) if mit_lektorat
                  else e(z["uebersetzung"] or ""))
        nr = (f'<span class="nr">{z["chunk"]}</span>' if z["chunk"] else "")

        teile.append(f'<div class="{" ".join(klassen)}">')
        teile.append(f'<div class="q">{e(z["quelle"] or "") or "&nbsp;"}</div>')
        teile.append(f'<div class="e">{e(z["entwurf"] or "") or "&nbsp;"}</div>')
        teile.append(f'<div class="l">{nr}{rechts or "&nbsp;"}'
                     + (f'<div class="notizen">{"".join(notizen)}</div>'
                        if notizen else "") + "</div>")
        teile.append("</div>")
    teile.append("</main>")
    teile.append(SKRIPT % {"breite": BREITE_DREI})
    return "\n".join(teile)


def _aenderungen(alt, neu):
    return diffview().changes(alt, neu, 7)


# ==================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true",
                    help="die Testauszuege statt des ganzen Buchs")
    ap.add_argument("--datei", default=None, help="Zieldatei")
    args = ap.parse_args()

    G.kopf("LESEAUSGABE")
    cfg = G.lade_config()
    praefix = "test/" if args.test else ""
    ziel = args.datei or (praefix + AUSGABE)

    if not os.path.exists(G.F["quelle"]):
        sys.exit(f"FEHLER: {G.F['quelle']} nicht gefunden.")

    # Eine abweichende Chunkfolge ist kein Warnfall: Die Leseausgabe ist
    # das Dokument, an dem ein Mensch Absatz gegen Absatz liest. Eine
    # verschobene, aber ausgelieferte Fassung ist schlimmer als gar keine
    # — beide Spalten sehen fuer sich plausibel aus.
    try:
        zeilen, warnung = zeilen_bauen(cfg, praefix, args.test)
    except G.ChunksWeichenAb as e:
        sys.exit(f"FEHLER: {e}\n  Die Leseausgabe wurde nicht geschrieben.")
    if not zeilen:
        sys.exit("FEHLER: keine Chunks gefunden. Lief die Uebersetzung schon?")
    mit_lektorat = lektorat_anhaengen(zeilen, praefix)

    kapitel = G.lade_json(G.F["kapitel"], still=True)
    kapitel_zuordnen(zeilen, kapitel)
    befunde = screening_lesen(praefix)
    gruende = gruende_lesen(praefix)

    ohne_ziel = sum(1 for z in zeilen if not z["uebersetzung"])
    print(f"Absaetze:    {len(zeilen)}"
          + (f"   ({ohne_ziel} ohne deutsche Entsprechung)"
             if ohne_ziel else ""))
    print(f"Kapitel:     {len({z['kapitel'] for z in zeilen if z['kapitel']})}"
          + ("" if kapitel else "   (kapitel.json fehlt oder ist leer)"))
    print(f"Lektorat:    {'ja' if mit_lektorat else 'nein, noch nicht gelaufen'}")
    print(f"Befunde:     {sum(len(v) for v in befunde.values())} aus "
          f"{len(befunde)} Chunks")
    print(f"Begruendungen: {len(gruende)}")
    if warnung:
        print(f"\nWARNUNG: {warnung}")

    titel = ("Leseausgabe — Testauszüge" if args.test
             else "Leseausgabe — Niederländisch neben Deutsch")
    open(ziel, "w", encoding="utf-8").write(
        html_bauen(zeilen, kapitel, befunde, gruende, titel,
                   mit_lektorat, warnung))
    print(f"\n{ziel}  ({os.path.getsize(ziel)/1e6:.1f} MB)")
    print("Im Dateibrowser rechtsklicken -> Download, oder direkt oeffnen.")


if __name__ == "__main__":
    main()
