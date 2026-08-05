#!/usr/bin/env python3
"""
Ergebnis paketieren.  Aufraeumen macht 'pipeline.py neu'.

    python3 paket.py
"""
import os, shutil, subprocess, sys, tarfile
import gemeinsam as G

ARCHIV, ORDNER = "ergebnis.tar.gz", "ergebnis"
PFLICHT = [G.F["quelle"], G.F["uebersetzung"]]

# Der Code liegt im Colab-Betrieb nicht im Arbeitsverzeichnis.
CODE = os.path.dirname(os.path.abspath(__file__))

MITNEHMEN = [
    G.CONFIG, G.ANWEISUNGEN, G.MANIFEST,
    G.F["quelle"], G.F["glossar"], G.F["personen"], G.F["figuren"],
    G.F["anrede"], G.F["leitmotive"], G.F["zitate"], G.F["ebenen"],
    G.F["entwurf"], G.F["uebersetzung"], G.F["normalisiert"], G.F["lektoriert"],
    "preflight_report.txt", "qa_uebersetzung.txt", "qa_lektorat.txt",
    "qa_konsistenz.txt", "leitmotiv_varianten.txt",
    # bericht.html gehoert dazu: Es ist die Fassung des Diffs, die ein
    # Mensch tatsaechlich liest. Sie fehlte bis zum ersten Volllauf.
    "normalisierung_report.txt", "lektorat_diff.txt", "bericht.html",
    "pipeline.log", "uebersetzung_warnungen.log", "lektorat_warnungen.log",
    "tarife.json", "zitate_verdacht.txt", "zitate_review.md", "screening_review.md",
    "begruendungen.json", "analysepaket.md",
    "bewertung_uebersetzung.md", "bewertung_lektorat.md",
    "bewertung_varianten.md",
    # Die Leseausgabe ist das Stueck, mit dem ein Mensch das Buch
    # tatsaechlich durchgeht — sie wird unten miterzeugt.
    "leseausgabe.html",
]


def leseausgabe_bauen():
    """Erzeugt die Leseausgabe gleich mit.

    Wie bei bericht.html in lektorat.py: Der Schritt, der ausliefert,
    erzeugt auch das, was ausgeliefert wird — sonst steht am Ende ein
    Befehl da, den jemand von Hand abtippen soll."""
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(CODE, "leseausgabe.py")],
            capture_output=True, text=True, timeout=600)
    except Exception as e:
        print(f"  WARNUNG: Leseausgabe nicht erzeugt — {e}")
        return
    if r.returncode != 0:
        print(f"  WARNUNG: Leseausgabe nicht erzeugt — "
              f"{(r.stderr or '').strip()[:300]}")
        return
    # Meldet die Leseausgabe eine verschobene Zuordnung, darf das nicht in
    # der abgefangenen Ausgabe des Unterprozesses verschwinden.
    for zeile in (r.stdout or "").splitlines():
        if zeile.startswith("WARNUNG:"):
            print(f"  Leseausgabe: {zeile}")


def main():
    G.kopf("PAKET")
    fehlt = [p for p in PFLICHT if not os.path.exists(p)]
    if fehlt:
        sys.exit("FEHLER: es fehlen " + ", ".join(fehlt))

    leseausgabe_bauen()

    if os.path.isdir(ORDNER):
        shutil.rmtree(ORDNER)
    os.makedirs(ORDNER)
    dabei = []
    for f in MITNEHMEN:
        if os.path.exists(f):
            shutil.copy2(f, ORDNER); dabei.append(f)
    for d in ["test"] + [f"test{v['name']}"
                         for v in G.varianten(G.lade_config(pflicht=False))]:
        if os.path.isdir(d):
            shutil.copytree(d, os.path.join(ORDNER, d),
                            ignore=shutil.ignore_patterns("teile"))
            dabei.append(d + "/")

    with tarfile.open(ARCHIV, "w:gz") as t:
        t.add(ORDNER)
    shutil.rmtree(ORDNER)

    print(f"{ARCHIV}  ({os.path.getsize(ARCHIV)/1e6:.1f} MB, "
          f"{len(dabei)} Eintraege)\n")
    for f in dabei:
        print(f"  {f}")
    print(f"\nJetzt im Jupyter-Dateibrowser {ARCHIV} rechtsklicken -> Download.")
    print("Nach geprueftem Download aufraeumen mit:")
    print("  python3 pipeline.py neu")


if __name__ == "__main__":
    main()
