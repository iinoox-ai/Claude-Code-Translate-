#!/usr/bin/env python3
"""
Lesbarer Diff-Betrachter fuer Lektoratslaeufe.

Das Problem am bisherigen Format: unified_diff arbeitet absatzweise. Bei
einem 200-Wort-Absatz siehst du zwei fast identische Textwuesten und musst
die geaenderte Stelle selbst suchen.

Dieses Werkzeug macht stattdessen einen Wortdiff und zeigt nur die
Aenderung mit ein paar Woertern Kontext:

    [Chunk 13 · Stil]  … caught myself [-sneaking looks-]{+stealing glances+} at him …

Aufrufe:
    python3 diffview.py lektorat_diff.txt
    python3 diffview.py lektorat_diff.txt --pass Stil
    python3 diffview.py lektorat_diff.txt --skip-typo
    python3 diffview.py lektorat_diff.txt --min 2 --context 6
    python3 diffview.py vorher.txt nachher.txt        # zwei Dateien vergleichen
    python3 diffview.py lektorat_diff.txt --html bericht.html
    python3 diffview.py lektorat_diff.txt --stats
"""

import argparse
import difflib
import hashlib
import html
import json
import os
import re
import sys

DASH = re.compile(r"[\u2014\u2013]")
QUOTE = re.compile(r"[\u2018\u2019\u201c\u201d«»„‚]")


# ==================================================================
# Einlesen
# ==================================================================
def read_difffile(path):
    """Parst die von lektorat*.py erzeugte Diff-Datei."""
    txt = open(path, encoding="utf-8").read()
    parts = re.split(r"\n=+\nChunk (\d+) - (\S+)\n=+\n", txt)
    out = []
    for i in range(1, len(parts) - 2, 3):
        chunk, name, body = int(parts[i]), parts[i + 1], parts[i + 2]
        before = [l[1:] for l in body.split("\n")
                  if l.startswith("-") and not l.startswith("--- ")]
        after = [l[1:] for l in body.split("\n")
                 if l.startswith("+") and not l.startswith("+++ ")]
        out.append((chunk, name, before, after))
    return out


def read_two_files(a, b):
    """Vergleicht zwei Volltexte absatzweise."""
    pa = [p.strip() for p in re.split(r"\n\s*\n", open(a, encoding="utf-8").read()) if p.strip()]
    pb = [p.strip() for p in re.split(r"\n\s*\n", open(b, encoding="utf-8").read()) if p.strip()]
    return [(0, "Datei", pa, pb)]


# ==================================================================
# Absaetze paarweise zuordnen
# ==================================================================
def align(before, after):
    """Ordnet Absaetze einander zu. Bei ungleicher Anzahl wird nicht
    stumpf gezippt (das erzeugt Unsinn), sondern ueber Aehnlichkeit
    zugeordnet; Ueberzaehlige werden als Zugang/Wegfall gemeldet."""
    if len(before) == len(after):
        return [(b, a) for b, a in zip(before, after)]

    sm = difflib.SequenceMatcher(None,
                                 [p[:80] for p in before],
                                 [p[:80] for p in after])
    pairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                pairs.append((before[i1 + k], after[j1 + k]))
        elif tag == "replace":
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                pairs.append((before[i1 + k], after[j1 + k]))
            for k in range(n, i2 - i1):
                pairs.append((before[i1 + k], None))
            for k in range(n, j2 - j1):
                pairs.append((None, after[j1 + k]))
        elif tag == "delete":
            for k in range(i1, i2):
                pairs.append((before[k], None))
        elif tag == "insert":
            for k in range(j1, j2):
                pairs.append((None, after[k]))
    return pairs


# ==================================================================
# Wortdiff mit Kontext
# ==================================================================
def classify(old, new):
    if old is None or new is None:
        return "Absatz"
    o, n = old.strip(), new.strip()
    if DASH.search(o) or DASH.search(n):
        return "Typografie"
    if QUOTE.search(o) or QUOTE.search(n):
        if re.sub(r"[^\w\s]", "", o).strip() == re.sub(r"[^\w\s]", "", n).strip():
            return "Typografie"
    if re.sub(r"[^\w]", "", o).lower() == re.sub(r"[^\w]", "", n).lower():
        return "Interpunktion"
    no, nn = len(o.split()), len(n.split())
    if no <= 1 and nn <= 1:
        return "Wort"
    if no <= 4 and nn <= 4:
        return "Wendung"
    if no <= 10 and nn <= 10:
        return "Teilsatz"
    return "Umbau"


def changes(before, after, ctx):
    """Liefert (Kategorie, Kontext-links, alt, neu, Kontext-rechts)."""
    if before is None:
        return [("Absatz", "", "", after[:150], " …")]
    if after is None:
        return [("Absatz", "", before[:150], "", " …")]

    bw, aw = before.split(), after.split()
    sm = difflib.SequenceMatcher(None, bw, aw)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old = " ".join(bw[i1:i2])
        new = " ".join(aw[j1:j2])
        left = " ".join(bw[max(0, i1 - ctx):i1])
        right = " ".join(bw[i2:i2 + ctx])
        out.append((classify(old, new), left, old, new, right))
    return out


# ==================================================================
# Ausgabe
# ==================================================================
COL = {"Wort": "\033[36m", "Wendung": "\033[36m", "Teilsatz": "\033[33m",
       "Umbau": "\033[31m", "Typografie": "\033[90m",
       "Interpunktion": "\033[90m", "Absatz": "\033[35m"}
RESET = "\033[0m"


def fmt_text(kat, chunk, name, left, old, new, right, color):
    head = f"[{chunk:>3} · {name[:4]}·{kat[:4]}]"
    if color:
        head = COL.get(kat, "") + head + RESET
        body = (f"…{left} \033[41;97m{old}\033[0m → "
                f"\033[42;30m{new}\033[0m {right}…")
    else:
        body = f"…{left} [-{old}-] {{+{new}+}} {right}…"
    return f"{head} {body}"


HTML_HEAD = """<!doctype html><meta charset="utf-8">
<title>Lektorat — Änderungen</title><style>
body{font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
max-width:52rem;margin:0 auto;padding:1.2rem;color:#1a1a1a;background:#fbfaf8}
h1{font-size:1.3rem;margin:0 0 .3rem}
.meta{color:#777;font-size:.85rem;margin-bottom:1.4rem}
.row{padding:.6rem .7rem;margin:.35rem 0;border-left:3px solid #ddd;background:#fff;
border-radius:0 4px 4px 0}
.row:hover{background:#fffdf6}
.tag{display:inline-block;font-size:.68rem;letter-spacing:.04em;text-transform:uppercase;
color:#888;margin-right:.5rem;font-weight:600}
del{background:#ffe0e0;color:#8b0000;text-decoration:none;padding:0 .15em;border-radius:2px}
ins{background:#d8f5d8;color:#0a5a0a;text-decoration:none;padding:0 .15em;border-radius:2px}
.ctx{color:#888}
.grund{color:#4a6; font-size:0.9em; margin-top:.3em; padding-left:1em;
       border-left:2px solid #4a6}
.Umbau{border-left-color:#c33}.Teilsatz{border-left-color:#e8a33d}
.Wort,.Wendung{border-left-color:#3a7bbf}
.Typografie,.Interpunktion{border-left-color:#ccc}
.Absatz{border-left-color:#9b59b6}
</style>
"""


def fmt_html(kat, chunk, name, left, old, new, right, grund=""):
    e = html.escape
    zeile = (f'<div class="row {kat}">'
             f'<span class="tag">{chunk} · {e(name)} · {kat}</span>'
             f'<span class="ctx">…{e(left)}</span> '
             f'<del>{e(old)}</del> <ins>{e(new)}</ins> '
             f'<span class="ctx">{e(right)}…</span>')
    if grund:
        zeile += f'<div class="grund">{e(grund)}</div>'
    return zeile + "</div>"


# ==================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="Diff-Datei oder zwei Textdateien")
    ap.add_argument("--pass", dest="which", default=None,
                    help="nur Durchgaenge, deren Name damit beginnt (z.B. Stil)")
    ap.add_argument("--skip-typo", action="store_true",
                    help="Typografie und reine Interpunktion ausblenden")
    ap.add_argument("--only", default=None,
                    help="nur diese Kategorie (Wort/Wendung/Teilsatz/Umbau/Absatz)")
    ap.add_argument("--min", type=int, default=0,
                    help="Mindestzahl geaenderter Woerter")
    ap.add_argument("--context", type=int, default=7, help="Kontextwoerter")
    ap.add_argument("--chunk", type=int, default=None, help="nur dieser Chunk")
    ap.add_argument("--stats", action="store_true", help="nur Statistik")
    ap.add_argument("--html", metavar="DATEI", help="HTML-Bericht schreiben")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--begruendungen", metavar="DATEI", default=None,
                    help="Begruendungen aus annotation.py einblenden")
    ap.add_argument("--begruendung", action="store_true",
                    help="Begruendungen auch auf der Konsole zeigen")
    args = ap.parse_args()

    if len(args.files) == 2:
        data = read_two_files(*args.files)
    else:
        data = read_difffile(args.files[0])

    color = sys.stdout.isatty() and not args.no_color and not args.html

    rows, stats = [], {}
    for chunk, name, before, after in data:
        if args.which and not name.lower().startswith(args.which.lower()):
            continue
        if args.chunk is not None and chunk != args.chunk:
            continue
        for b, a in align(before, after):
            for kat, left, old, new, right in changes(b, a, args.context):
                stats.setdefault(name, {}).setdefault(kat, 0)
                stats[name][kat] += 1
                if args.skip_typo and kat in ("Typografie", "Interpunktion"):
                    continue
                if args.only and kat != args.only:
                    continue
                if max(len(old.split()), len(new.split())) < args.min:
                    continue
                rows.append((kat, chunk, name, left, old, new, right))

    if args.stats or not rows:
        for name in stats:
            tot = sum(stats[name].values())
            print(f"\n=== {name}: {tot} Aenderungen ===")
            for k, n in sorted(stats[name].items(), key=lambda x: -x[1]):
                print(f"  {k:16s} {n:5d}  {n/tot:5.0%}")
        if args.stats:
            return

    gruende = {}
    if args.begruendungen and os.path.exists(args.begruendungen):
        try:
            gruende = json.load(open(args.begruendungen, encoding="utf-8"))
        except Exception as e:
            print(f"WARNUNG: {args.begruendungen} nicht lesbar — {e}")

    def grund_fuer(chunk, kat, alt, neu):
        if not gruende:
            return ""
        roh = f"{chunk}|{kat}|{alt}|{neu}"
        return gruende.get(
            hashlib.sha256(roh.encode("utf-8")).hexdigest()[:8], "")

    if args.html:
        body = "".join(fmt_html(k, c, n, l, o, nw, r,
                                grund_fuer(c, k, o, nw))
                       for k, c, n, l, o, nw, r in rows)
        summary = " · ".join(f"{nm}: {sum(v.values())}" for nm, v in stats.items())
        open(args.html, "w", encoding="utf-8").write(
            HTML_HEAD + f"<h1>Lektorat — Änderungen</h1>"
            f'<div class="meta">{len(rows)} angezeigt · {summary}</div>' + body)
        print(f"{len(rows)} Aenderungen -> {args.html}")
        return

    for k, c, n, l, o, nw, r in rows:
        print(fmt_text(k, c, n, l, o, nw, r, color))
        if args.begruendung:
            g = grund_fuer(c, k, o, nw)
            if g:
                print(f"      -> {g}")
    print(f"\n{len(rows)} Aenderungen angezeigt.")


if __name__ == "__main__":
    main()
