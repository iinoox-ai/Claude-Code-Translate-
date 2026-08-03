#!/usr/bin/env python3
"""
Ergebnis paketieren.  Aufraeumen macht 'pipeline.py neu'.

    python3 paket.py
"""
import os, shutil, sys, tarfile
import gemeinsam as G

ARCHIV, ORDNER = "ergebnis.tar.gz", "ergebnis"
PFLICHT = [G.F["quelle"], G.F["uebersetzung"]]

MITNEHMEN = [
    G.CONFIG, G.ANWEISUNGEN, G.MANIFEST,
    G.F["quelle"], G.F["glossar"], G.F["personen"], G.F["figuren"],
    G.F["anrede"], G.F["leitmotive"], G.F["zitate"],
    G.F["entwurf"], G.F["uebersetzung"], G.F["normalisiert"], G.F["lektoriert"],
    "preflight_report.txt", "qa_uebersetzung.txt", "qa_lektorat.txt",
    "qa_konsistenz.txt", "leitmotiv_varianten.txt",
    # bericht.html gehoert dazu: Es ist die Fassung des Diffs, die ein
    # Mensch tatsaechlich liest. Sie fehlte bis zum ersten Volllauf.
    "normalisierung_report.txt", "lektorat_diff.txt", "bericht.html",
    "pipeline.log", "uebersetzung_warnungen.log", "lektorat_warnungen.log",
    "zitate_verdacht.txt", "zitate_review.md", "analysepaket.md",
    "bewertung_uebersetzung.md", "bewertung_lektorat.md",
    "bewertung_varianten.md",
]


def main():
    G.kopf("PAKET")
    fehlt = [p for p in PFLICHT if not os.path.exists(p)]
    if fehlt:
        sys.exit("FEHLER: es fehlen " + ", ".join(fehlt))

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
    cfg = G.lade_config(pflicht=False)
    # Ein Modell zu entladen gibt es nur auf dem Ollama-Rueckfallpfad —
    # bei API-Backends laeuft nichts, das Speicher belegt.
    if "ollama" in G.benutzte_backends(cfg):
        print("\nModell entladen:")
        print(f"  curl -s {cfg['ollama_host']}/api/generate "
              f"-d '{{\"model\":\"{cfg['modell']}\",\"keep_alive\":0}}'")


if __name__ == "__main__":
    main()
