#!/usr/bin/env python3
"""
Vorbereitung des Colab-Laufs — Drive, Repo, Secrets, Arbeitsverzeichnis.

Wird aus der ersten Zelle von colab_runner.ipynb aufgerufen. Die Logik
steht bewusst hier und nicht in der Zelle: Notebook-Zellen lassen sich
weder testen noch sinnvoll diffen.

    import colab_start
    colab_start.vorbereiten()                       # Standardprojekt
    colab_start.vorbereiten("/content/drive/MyDrive/uebersetzung/andere")

Trennung der Verzeichnisse (Auftrag Paket 2, Punkt 4):

    Code   liegt in der VM      — kommt per git, ist jederzeit wegwerfbar
    Daten  liegen in Drive      — Arbeitsverzeichnis, ueberleben die VM

Alles, was der Lauf schreibt, entsteht relativ zum Arbeitsverzeichnis und
liegt damit sofort dauerhaft in Drive.
"""

import os
import shutil
import subprocess
import sys

import gemeinsam as G

PROJEKT_STANDARD = "/content/drive/MyDrive/uebersetzung/1919"
MOUNT            = "/content/drive"
REPO             = "https://github.com/iinoox-ai/Claude-Code-Translate-.git"

CODE = os.path.dirname(os.path.abspath(__file__))


def _lauf(befehl, cwd=None):
    return subprocess.run(befehl, cwd=cwd, capture_output=True,
                          text=True, timeout=300)


# ==================================================================
def drive_mounten(mount=MOUNT):
    """Idempotent: ein bereits gemounteter Drive wird nicht neu gemountet."""
    if os.path.isdir(os.path.join(mount, "MyDrive")):
        return False
    if not G.ist_colab():
        sys.exit(f"FEHLER: {mount} ist nicht gemountet und dies ist kein "
                 f"Colab-Notebook.")
    from google.colab import drive
    drive.mount(mount)
    return True


def repo_aktualisieren(code=CODE):
    """Zieht den aktuellen Stand, wenn das Code-Verzeichnis ein Repo ist.

    Der Klon selbst passiert im Bootstrap der Zelle — dieses Modul liegt
    ja bereits im Repo, wenn es importiert werden kann."""
    if not os.path.isdir(os.path.join(code, ".git")):
        return None, None, "kein Repo"
    r = _lauf(["git", "pull", "--ff-only"], cwd=code)
    if r.returncode != 0:
        hinweis = f"git pull fehlgeschlagen: {r.stderr.strip()[:200]}"
    else:
        hinweis = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    zweig = _lauf(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                  cwd=code).stdout.strip()
    commit = _lauf(["git", "log", "-1", "--format=%h %s"],
                   cwd=code).stdout.strip()
    return zweig, commit, hinweis


def secrets_laden():
    """Colab-Secrets in die Umgebung. Werte werden nie ausgegeben."""
    stand = {}
    for anbieter in ("anthropic", "google"):
        var, secret = G.SCHLUESSEL[anbieter]
        stand[anbieter] = (var, secret,
                           bool(G.api_schluessel(anbieter, still=False)))
    return stand


def projektordner_richten(projekt, code=CODE):
    """Ordner anlegen, falls er fehlt; projekt.json beim Erstlauf kopieren.

    Eine vorhandene projekt.json wird NIE ueberschrieben — sie traegt die
    kalibrierten Pruefgrenzen des laufenden Projekts."""
    meldungen = []
    if not os.path.isdir(projekt):
        os.makedirs(projekt, exist_ok=True)
        meldungen.append(f"Projektordner neu angelegt: {projekt}")

    ziel = os.path.join(projekt, G.CONFIG)
    quelle = os.path.join(code, G.CONFIG)
    if os.path.exists(ziel):
        meldungen.append(f"{G.CONFIG} im Projektordner vorhanden — "
                         f"unveraendert uebernommen")
    elif os.path.exists(quelle):
        shutil.copy2(quelle, ziel)
        meldungen.append(f"{G.CONFIG} aus dem Repo kopiert (Erstlauf). "
                         f"Aenderungen bitte hier vornehmen, nicht im Repo.")
    else:
        meldungen.append(f"WARNUNG: weder {ziel} noch {quelle} vorhanden — "
                         f"'python3 pipeline.py init' anlegen")
    return meldungen


# ==================================================================
def vorbereiten(projekt=PROJEKT_STANDARD, code=CODE, still=False):
    """Mountet Drive, aktualisiert das Repo, laedt Secrets, wechselt ins
    Arbeitsverzeichnis. Gibt die Eckdaten als dict zurueck."""
    frisch = drive_mounten()
    zweig, commit, git_hinweis = repo_aktualisieren(code)
    meldungen = projektordner_richten(projekt, code)
    schluessel = secrets_laden()
    os.chdir(projekt)

    stand = {"code": code, "arbeit": projekt, "zweig": zweig,
             "commit": commit, "drive_frisch_gemountet": frisch,
             "schluessel": schluessel, "meldungen": meldungen}
    if not still:
        bericht(stand, git_hinweis)
    return stand


def bericht(stand, git_hinweis=""):
    G.kopf("COLAB-RUNNER")
    print(f"Code:    {stand['code']}")
    if stand["zweig"]:
        print(f"         {stand['zweig']} — {stand['commit']}")
    if git_hinweis:
        print(f"         {git_hinweis}")
    print(f"Arbeit:  {stand['arbeit']}")
    print(f"         {'neu gemountet' if stand['drive_frisch_gemountet'] else 'Drive war bereits gemountet'}")
    print()
    for m in stand["meldungen"]:
        print(f"  {m}")
    for anbieter, (var, secret, da) in sorted(stand["schluessel"].items()):
        if da:
            print(f"  Schluessel {anbieter}: vorhanden")
        else:
            print(f"  Schluessel {anbieter}: FEHLT — Colab-Secret "
                  f"'{secret}' anlegen und der Zelle Zugriff geben")
    quelle = os.path.join(stand["arbeit"], G.F["quelle"])
    if os.path.exists(quelle):
        w = len(open(quelle, encoding="utf-8", errors="replace").read().split())
        print(f"  {G.F['quelle']}: {w} Woerter")
    else:
        print(f"  {G.F['quelle']}: fehlt im Projektordner")
    print()


def lauf(skript="pipeline.py", *argumente, code=CODE):
    """Startet ein Skript im Vordergrund und reicht jede Zeile sofort durch.

    '-u' schaltet die Pufferung ab: die Chunk-Fortschrittsausgabe muss
    laufend sichtbar sein, sonst stuft Colab die Sitzung als untaetig ein.
    Rueckgabe ist der Rueckgabewert des Skripts."""
    befehl = [sys.executable, "-u", os.path.join(code, skript), *argumente]
    p = subprocess.Popen(befehl, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        for zeile in p.stdout:
            print(zeile, end="", flush=True)
    except KeyboardInterrupt:
        p.terminate()
        print("\nAbgebrochen. Der naechste Lauf setzt am offenen Chunk fort.")
        raise
    return p.wait()


if __name__ == "__main__":
    vorbereiten(sys.argv[1] if len(sys.argv) > 1 else PROJEKT_STANDARD)
