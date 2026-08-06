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

import json
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


def sdk_sicherstellen():
    """Installiert die Anbieter-SDK, wenn sie fehlt. Genau dieses eine Paket.

    Die Regel 'kein pip install im Normalbetrieb' entstand gegen litellm
    und bleibt. Die Hersteller-SDK ist die eine benannte Ausnahme
    (ENTSCHEIDUNGEN.md), auf Hauptversion festgelegt, und der Lauf haengt
    nicht daran: Scheitert die Installation, laeuft der requests-Pfad
    unveraendert weiter."""
    if G.anthropic_sdk():
        return "SDK 'anthropic': vorhanden"
    r = _lauf([sys.executable, "-m", "pip", "install", "-q",
               "anthropic>=0.40,<1"])
    G._SDK = None                      # naechster Versuch soll neu laden
    if r.returncode == 0 and G.anthropic_sdk():
        return "SDK 'anthropic': nachinstalliert"
    return ("SDK 'anthropic': nicht installierbar — der Lauf benutzt den "
            "requests-Pfad (kein Streaming, keine Stapelverarbeitung)")


def secrets_laden():
    """Colab-Secrets in die Umgebung. Werte werden nie ausgegeben."""
    stand = {}
    for anbieter in ("anthropic", "google"):
        var, secret = G.SCHLUESSEL[anbieter]
        stand[anbieter] = (var, secret,
                           bool(G.api_schluessel(anbieter, still=False)))
    return stand


def _lies(pfad):
    try:
        return json.load(open(pfad, encoding="utf-8"))
    except Exception:
        return {}


def _technik_melden(ziel, quelle):
    """Meldet, wo die projekt.json technisch hinter dem Repo zurueckliegt.

    Der Ueberschreibschutz ist richtig — er hat aber einen blinden Fleck:
    Ein im Repo korrigierter Modellname erreicht ein laufendes Projekt
    nie, und der Runner meldete bisher nur 'unveraendert uebernommen'.
    Erkannt wird die Abweichung jetzt; uebernommen wird sie nur auf
    ausdrueckliche Ansage."""
    if not os.path.exists(quelle):
        return []
    ab = G.technik_abweichung(_lies(ziel), _lies(quelle))
    if not ab:
        return []
    zeilen = [f"ACHTUNG: {len(ab)} technische Einstellung(en) weichen vom "
              f"Repo ab:"]
    for k, alt, neu in ab:
        zeilen.append(f"    {k}: Projekt {alt!r}  <->  Repo {neu!r}")
    zeilen.append("  Uebernehmen (kalibrierte Werte bleiben unberuehrt):")
    zeilen.append("    colab_start.lauf('pipeline.py', 'technik', "
                  "'--uebernehmen', code=CODE)")
    return zeilen


def sheets_anmelden(code=CODE):
    """Einmal je Sitzung IN EINER ZELLE ausfuehren, nicht im Unterprozess.

    Colab fuehrt die Google-Anmeldung ueber den Kernel-Kanal zur
    Oberflaeche. Den gibt es nur im Notebook-Prozess; die Pipeline
    startet ihre Schritte aber grundsaetzlich als Unterprozess, und dort
    stirbt authenticate_user() mit einem AttributeError statt mit einer
    Aussage.

    Danach wird nachgesehen, ob ein Unterprozess die Anmeldung wirklich
    sieht — sonst haette man eine gruene Zelle und trotzdem keinen
    Zugriff."""
    import subprocess
    import sys
    from google.colab import auth
    auth.authenticate_user()
    print("Angemeldet.")

    # Geprueft wird ueber referenz_sync.anmeldung_taugt und nicht ueber
    # 'default() wirft nicht': In Colab findet default() immer die
    # Compute-Engine-Anmeldung der VM, an der kein Dienstkonto haengt.
    # Diese Zelle haette also 'SICHTBAR' gemeldet, und der Fehler waere
    # erst im Schritt aufgetaucht — als angebliches Problem des
    # Spreadsheets.
    pruef = ("import google.auth, referenz_sync as R\n"
             "try:\n"
             "    creds, _ = google.auth.default()\n"
             "    gut = R.anmeldung_taugt(creds)\n"
             "    print('SICHTBAR' if gut else\n"
             "          'UNSICHTBAR nur die Metadaten-Anmeldung der VM')\n"
             "except Exception as e:\n"
             "    print('UNSICHTBAR', e)\n")
    r = subprocess.run([sys.executable, "-c", pruef],
                       capture_output=True, text=True, cwd=code)
    if "SICHTBAR" in r.stdout:
        print("Unterprozesse sehen die Anmeldung — referenz_sync laeuft "
              "jetzt ueber colab_start.lauf(...).")
        return True
    print("Die Anmeldung gilt nur in dieser Zelle, nicht in "
          "Unterprozessen.\n"
          "Fuer den Sync stattdessen im Kernel arbeiten:\n"
          "    colab_start.sync_im_kernel()")
    print(f"  ({(r.stdout + r.stderr).strip()[:200]})")
    return False


def sync_im_kernel(projekt=PROJEKT_STANDARD, code=CODE, vorlage=False,
                   nur_pruefen=False):
    """Rueckfall: den Sync im Notebook-Prozess laufen lassen.

    Nur fuer den Sheets-Zugriff gedacht. Alles andere gehoert weiter in
    den Unterprozess — dort ist ausgeschlossen, dass ein zwischenzeitlich
    geholter Codestand von einem alten Import verdeckt wird."""
    import os
    import sys
    os.chdir(projekt)
    if code not in sys.path:
        sys.path.insert(0, code)
    for name, modul in list(sys.modules.items()):
        if (getattr(modul, "__file__", None) or "").startswith(code):
            del sys.modules[name]
    import gemeinsam as G
    import referenz_sync as R
    cfg = G.lade_config()
    if not R.aktiv(cfg):
        print("sheets_id ist leer — Rueckfallpfad aktiv, nichts zu tun.")
        return
    try:
        if vorlage:
            R.vorlage(cfg)
        else:
            R.sync(cfg, schreiben=not nur_pruefen)
            if nur_pruefen:
                print("Nur geprueft — keine Datei geschrieben.")
    except R.SyncFehler as e:
        print(f"FEHLER: {e}")


def technik_uebernehmen(projekt=PROJEKT_STANDARD, code=CODE):
    """Uebertraegt NUR die technischen Schluessel aus dem Repo.

    Gleichwertig zu 'pipeline.py technik --uebernehmen'; im Notebook ist
    das Unterkommando der sicherere Weg, weil es als eigener Prozess
    laeuft und damit nie einen veralteten Modulimport erwischt."""
    ab = G.technik_schreiben(os.path.join(projekt, G.CONFIG),
                             os.path.join(code, G.CONFIG))
    if not ab:
        print("Keine technische Abweichung — nichts zu tun.")
        return []
    for k, alt_, neu_ in ab:
        print(f"  {k}: {alt_!r} -> {neu_!r}")
    print(f"\n{len(ab)} Einstellung(en) uebernommen. Kalibrierte Werte "
          f"blieben unberuehrt.")
    return ab


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
        meldungen += _technik_melden(ziel, quelle)
    elif os.path.exists(quelle):
        shutil.copy2(quelle, ziel)
        meldungen.append(f"{G.CONFIG} aus dem Repo kopiert (Erstlauf). "
                         f"Aenderungen bitte hier vornehmen, nicht im Repo.")
    else:
        meldungen.append(f"WARNUNG: weder {ziel} noch {quelle} vorhanden — "
                         f"'python3 pipeline.py init' anlegen")

    # anweisungen.md gehoert zum Buch, nicht zum Code: sie wird ueber einen
    # relativen Pfad aus dem Arbeitsverzeichnis gelesen. Ohne Kopie laeuft
    # ein neues Projekt still mit leeren Anweisungsabschnitten.
    a_ziel = os.path.join(projekt, G.ANWEISUNGEN)
    a_quelle = os.path.join(code, G.ANWEISUNGEN)
    if os.path.exists(a_ziel):
        gefuellt = [n for n in ("Übersetzung", "Stillektorat", "Korrektorat")
                    if G.lade_anweisungen(n, a_ziel)]
        meldungen.append(
            f"{G.ANWEISUNGEN} vorhanden — Abschnitte mit Inhalt: "
            f"{', '.join(gefuellt) or 'keine (Standardvorgaben)'}")
    elif os.path.exists(a_quelle):
        shutil.copy2(a_quelle, a_ziel)
        meldungen.append(f"{G.ANWEISUNGEN} als Vorlage kopiert — die drei "
                         f"Abschnitte sind leer und werden nach dem "
                         f"Testlauf gefuellt.")
    return meldungen


# ==================================================================
def vorbereiten(projekt=PROJEKT_STANDARD, code=CODE, still=False):
    """Mountet Drive, aktualisiert das Repo, laedt Secrets, wechselt ins
    Arbeitsverzeichnis. Gibt die Eckdaten als dict zurueck."""
    frisch = drive_mounten()
    zweig, commit, git_hinweis = repo_aktualisieren(code)
    meldungen = projektordner_richten(projekt, code)
    meldungen.append(sdk_sicherstellen())
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


def lauf(skript="pipeline.py", *argumente, code=CODE, projekt=None):
    """Startet ein Skript im Vordergrund und reicht jede Zeile sofort durch.

    '-u' schaltet die Pufferung ab: die Chunk-Fortschrittsausgabe muss
    laufend sichtbar sein, sonst stuft Colab die Sitzung als untaetig ein.
    Rueckgabe ist der Rueckgabewert des Skripts.

    Das Arbeitsverzeichnis wird ausdruecklich gesetzt statt geerbt. Wer
    nur die Nachlade-Zelle ausgefuehrt hat, steht sonst in /content, und
    die Skripte finden weder projekt.json noch die Referenzdateien —
    ohne dass jemand danach sucht."""
    befehl = [sys.executable, "-u", os.path.join(code, skript), *argumente]
    p = subprocess.Popen(befehl, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1,
                         cwd=projekt or os.getcwd())
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
