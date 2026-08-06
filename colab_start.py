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

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

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


def _anmeldeprobe(code=CODE, arbeit=None):
    """Sieht ein Unterprozess die Anmeldung — DORT, wo die Schritte laufen?

    Zwei Dinge, die beide schon falsch waren:

    Erstens wird ueber referenz_sync.anmeldung_taugt geprueft und nicht
    ueber 'default() wirft nicht'. In Colab findet default() immer die
    Compute-Engine-Anmeldung der VM, an der kein Dienstkonto haengt.

    Zweitens — und das ist der Fehler, der zuletzt drei Anlaeufe
    gekostet hat — laeuft die Probe im ARBEITSVERZEICHNIS des Laufs,
    nicht im Code-Verzeichnis. Sie stand bisher im Code-Verzeichnis und
    meldete 'SICHTBAR', waehrend der Preflight im Projektordner 'keine
    Anmeldung' bekam. Eine Probe, die woanders steht als der Geprueften,
    prueft nichts. Der Import braucht dann den Pfad ausdruecklich."""
    import subprocess
    import sys
    pruef = (f"import sys; sys.path.insert(0, {code!r})\n"
             "import google.auth, referenz_sync as R\n"
             "try:\n"
             "    creds, _ = google.auth.default()\n"
             "    gut = R.anmeldung_taugt(creds)\n"
             "    print('SICHTBAR' if gut else\n"
             "          'UNSICHTBAR nur die Metadaten-Anmeldung der VM')\n"
             "except Exception as e:\n"
             "    print('UNSICHTBAR', e)\n")
    return subprocess.run([sys.executable, "-c", pruef],
                          capture_output=True, text=True,
                          cwd=arbeit or os.getcwd())


# Wohin die Anmeldung der Zelle geschrieben wird, damit jeder
# Unterprozess sie findet. Nicht ins Code-Verzeichnis (das ist ein
# Git-Auscheck) und nicht nach Drive (das ist der Projektordner, der in
# Exportpakete wandert) — in das temporaere Verzeichnis der VM, das mit
# der Sitzung verschwindet.
ADC_DATEI = os.path.join(tempfile.gettempdir(), "colab_anmeldung.json")


def anmeldung_exportieren():
    """Die Anmeldung des Kernels als Datei, mit absolutem Pfad in der
    Umgebung. Gibt den Pfad zurueck oder '' — dann ging es nicht.

    Der Grund ist gemessen: Dieselbe Anmeldung war aus dem
    Code-Verzeichnis sichtbar und aus dem Projektordner nicht. Was
    google.auth.default() findet, haengt an Dingen, die wir nicht in der
    Hand haben. Ein absoluter Pfad in GOOGLE_APPLICATION_CREDENTIALS
    haengt an nichts: Er wird als erstes geprueft, gilt fuer jedes
    Arbeitsverzeichnis und vererbt sich an jeden Unterprozess.

    Geschrieben wird der 'authorized_user'-Satz — dieselben drei Felder,
    die auch Googles eigene ADC-Datei traegt. Die Datei liegt in /tmp
    der VM, gehoert nur dem Benutzer und verschwindet mit der Sitzung.
    Sie erscheint in keinem Bericht, in keinem Log und in keinem
    Exportpaket."""
    import json
    import stat
    import google.auth
    creds, _ = google.auth.default()
    satz = {"type": "authorized_user",
            "client_id": getattr(creds, "client_id", None),
            "client_secret": getattr(creds, "client_secret", None),
            "refresh_token": getattr(creds, "refresh_token", None)}
    if not all(satz.values()):
        return ""
    with open(ADC_DATEI, "w", encoding="utf-8") as f:
        json.dump(satz, f)
    os.chmod(ADC_DATEI, stat.S_IRUSR | stat.S_IWUSR)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ADC_DATEI
    return ADC_DATEI


def anmeldung_faellig(code=CODE):
    """Braucht dieser Projektordner eine Anmeldung, die noch fehlt?

    Die Anmeldung gilt je Colab-SITZUNG, nicht je Buch — nach jedem
    Neustart der Laufzeit ist sie wieder faellig. Wer das nicht weiss,
    startet den Lauf, sieht ihn drei Schritte weit kommen und dann an
    einer Meldung ueber Unterprozesse scheitern.

    Ohne sheets_id ist nichts faellig: Der Rueckfallpfad braucht kein
    Google."""
    import referenz_sync as R
    if not G.ist_colab() or not R.aktiv(G.lade_config(pflicht=False)):
        return False
    return "SICHTBAR" not in _anmeldeprobe(code).stdout


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

    # IMMER weiterreichen, nicht erst wenn die Probe scheitert.
    #
    # Der Export war zuerst ein Notnagel: Probe gruen -> nichts tun.
    # Damit blieb die Anmeldung genau dann verzeichnisabhaengig, wenn sie
    # gerade zufaellig funktionierte — und die Probe sieht nur den
    # Ordner, in dem sie steht. Wer danach auf ein anderes Buch wechselt,
    # steht wieder vor demselben Fehler, und die gruene Zelle von vorhin
    # sagt nichts darueber aus.
    #
    # Eine Anmeldung, die je Sitzung gilt, muss in JEDEM Ordner der
    # Sitzung gelten. Ein absoluter Pfad in
    # GOOGLE_APPLICATION_CREDENTIALS tut das; was google.auth.default()
    # von sich aus findet, tut es nachweislich nicht.
    pfad = anmeldung_exportieren()
    r = _anmeldeprobe(code)
    if "SICHTBAR" in r.stdout:
        print("Unterprozesse sehen die Anmeldung"
              + (f" ueber {os.path.basename(pfad)} — unabhaengig vom "
                 f"Projektordner,\ngilt fuer diese Colab-Sitzung, auch "
                 f"nach einem Wechsel des Buches." if pfad else
                 f" (geprueft in {os.getcwd()})."))
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
    meldungen, erstlauf = [], False
    if not os.path.isdir(projekt):
        os.makedirs(projekt, exist_ok=True)
        meldungen.append(f"Projektordner neu angelegt: {projekt}")

    ziel = os.path.join(projekt, G.CONFIG)
    quelle = os.path.join(code, G.VORLAGE)
    if not os.path.exists(quelle):
        # Aeltere Auschecks fuehren die Vorlage noch unter dem Namen der
        # Arbeitsdatei. Der Rueckfall kostet nichts und verhindert, dass
        # ein halb aktualisierter Stand ohne Konfiguration dasteht.
        quelle = os.path.join(code, G.CONFIG)
    if os.path.exists(ziel):
        meldungen.append(f"{G.CONFIG} im Projektordner vorhanden — "
                         f"unveraendert uebernommen")
        meldungen += _technik_melden(ziel, quelle)
    elif os.path.exists(quelle):
        shutil.copy2(quelle, ziel)
        erstlauf = True
        meldungen.append(f"{G.CONFIG} aus {os.path.basename(quelle)} "
                         f"angelegt (Erstlauf).")
        meldungen.append(f"  Ab jetzt gilt {ziel} — "
                         f"sheets_id, rahmen_marker und alles Weitere")
        meldungen.append(f"  dort aendern, nicht im Repo.")
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
    return meldungen, erstlauf


# ==================================================================
def vorbereiten(projekt=PROJEKT_STANDARD, code=CODE, still=False):
    """Mountet Drive, aktualisiert das Repo, laedt Secrets, wechselt ins
    Arbeitsverzeichnis. Gibt die Eckdaten als dict zurueck.

    'bereit' im Rueckgabewert ist False, wenn projekt.json gerade erst
    angelegt wurde. Dann ist noch nichts eingetragen — und die Zelle
    darf den Lauf nicht starten (siehe erstlauf_hinweis)."""
    frisch = drive_mounten()
    zweig, commit, git_hinweis = repo_aktualisieren(code)
    meldungen, erstlauf = projektordner_richten(projekt, code)
    meldungen.append(sdk_sicherstellen())
    schluessel = secrets_laden()
    os.chdir(projekt)

    # Erst nach dem os.chdir: 'anmeldung_faellig' liest die projekt.json
    # des Buches, und die steht im Arbeitsverzeichnis.
    faellig = not erstlauf and anmeldung_faellig(code)

    stand = {"code": code, "arbeit": projekt, "zweig": zweig,
             "commit": commit, "drive_frisch_gemountet": frisch,
             "schluessel": schluessel, "meldungen": meldungen,
             "erstlauf": erstlauf, "anmeldung_faellig": faellig,
             "bereit": not erstlauf and not faellig}
    if not still:
        bericht(stand, git_hinweis)
        if erstlauf:
            erstlauf_hinweis(projekt)
        elif faellig:
            print(ANMELDUNG_FAELLIG)
    return stand


ANMELDUNG_FAELLIG = """
==============================================================
  ZELLE 1 FEHLT — Google-Anmeldung
==============================================================

Dieses Buch arbeitet mit einem Spreadsheet ('sheets_id' ist gesetzt),
und in dieser Colab-Sitzung ist niemand bei Google angemeldet. Der Lauf
startet deshalb NICHT — er kaeme drei Schritte weit und scheiterte dann
an einer Meldung ueber Unterprozesse.

Die Anmeldung gilt je SITZUNG, nicht je Buch: Nach jedem Neustart der
Laufzeit ist sie wieder faellig, auch bei einem Ordner, der gestern noch
lief.

  Zelle 1 ausfuehren, danach diese hier erneut.

(Soll das Buch ohne Spreadsheet laufen, 'sheets_id' in projekt.json
leeren — dann werden die Referenzdaten als JSON-Dateien gepflegt.)
"""


ERSTLAUF = """
==============================================================
  ERSTLAUF — projekt.json ist neu und noch leer
==============================================================

Der Lauf startet absichtlich NICHT. Was jetzt einzutragen ist, wird
gleich zu Beginn gelesen: 'sheets_id' braucht die Vorbereitung, um die
Referenzdaten ins Spreadsheet zu stellen, und 'rahmen_marker' entscheidet
ueber die Chunkgrenzen. Beides nachtraeglich zu setzen heisst, die
betroffenen Schritte zu wiederholen.

  {ziel}

Einzutragen:

  sheets_id       Die ID aus der Adresse des Spreadsheets — der Teil
                  zwischen '/d/' und '/edit'. Leer lassen heisst: die
                  JSON-Dateien sind die Quelle, ohne Google.
  rahmen_marker   Das Zeichen, mit dem der Autor die Erzaehlebenen
                  auszeichnet. Steht keines im Text, leer lassen — die
                  Vorbereitung erzeugt dann ebenen.json. Abschnitt 5a in
                  NEUES_BUCH.md stellt die Frage ausfuehrlich.
  modell_<rolle>  Nur, wenn dieses Buch von der Empfehlung abweichen soll.
                  'pipeline.py modelle' stellt beides nebeneinander.

Im Sheets-Betrieb ausserdem: Das Spreadsheet ist noch leer, und das ist
richtig so. Die Tabs legt

  colab_start.lauf("referenz_sync.py", "--vorlage", code=CODE)

an; gefuellt werden sie von der Vorbereitung, nicht von Hand. Danach
gehoert die Pflege ins Spreadsheet, nicht in die JSON-Dateien.

Wenn das steht: Zelle 2 einfach noch einmal ausfuehren.
"""


def erstlauf_hinweis(projekt):
    """Was beim Erstlauf einzutragen ist, bevor der erste Schritt laeuft.

    Frueher legte die Zelle projekt.json an und startete den Lauf in
    derselben Ausfuehrung. Damit gab es fuer ein neues Buch keinen
    Zeitpunkt, zu dem sich 'sheets_id' eintragen liess: Die Datei entstand
    und wurde im selben Atemzug benutzt. Wer den Sheets-Betrieb wollte,
    merkte es erst, als die Vorbereitung die Referenzdaten schon in die
    JSONs geschrieben hatte."""
    print(ERSTLAUF.format(ziel=os.path.join(projekt, G.CONFIG)))


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


def _merkmal(wert):
    """Was sich ueber einen Schluessel sagen laesst, ohne ihn zu zeigen.

    Laenge, Praefix und ein kurzer Fingerabdruck. Der Fingerabdruck
    dient genau einem Zweck: Zwei Werte vergleichen, ohne einen davon zu
    sehen. Der Wert selbst erscheint nirgends — nicht im Notebook, nicht
    im Log, nicht im Bericht."""
    if not wert:
        return "fehlt"
    roh = str(wert)
    sauber = "".join(roh.split())
    fp = hashlib.sha256(sauber.encode("utf-8")).hexdigest()[:8]
    hinweise = []
    if roh != sauber:
        hinweise.append(f"enthaelt {len(roh) - len(sauber)} Leerzeichen "
                        f"oder Umbrueche")
    if any(ord(z) > 126 for z in sauber):
        hinweise.append("enthaelt Zeichen ausserhalb von ASCII")
    return (f"{len(sauber)} Zeichen, beginnt mit "
            f"{sauber[:7]!r}, Fingerabdruck {fp}"
            + ("  ACHTUNG: " + "; ".join(hinweise) if hinweise else ""))


def schluessel_diagnose(code=CODE):
    """Warum weist der Anbieter den Schluessel zurueck?

    Beantwortet drei Fragen, die die Fehlermeldung des Anbieters offen
    laesst, und keine davon zeigt den Schluessel:

      1. Was steht in der Umgebung, was im Colab-Secret — und ist es
         dasselbe? Die Umgebung hat Vorrang. Ein einmal falsch gesetzter
         Wert bleibt die ganze Sitzung und verdeckt das richtige Secret.
      2. Sieht ein Unterprozess dasselbe? Die Schritte laufen alle als
         Unterprozess.
      3. Antwortet der Anbieter, wenn der Wert DIREKT aus dem Secret
         kommt, an unserem Lesepfad vorbei? Das trennt 'der Schluessel
         ist ungueltig' von 'unser Code verdirbt ihn unterwegs'."""
    G.kopf("SCHLUESSEL-DIAGNOSE")
    for anbieter, (var, secret) in sorted(G.SCHLUESSEL.items()):
        print(f"\n--- {anbieter}  (Umgebung {var}, Secret {secret})")
        aus_umgebung = os.environ.get(var)
        print(f"  Umgebung: {_merkmal(aus_umgebung)}")
        aus_secret = None
        try:
            from google.colab import userdata
            aus_secret = userdata.get(secret)
        except Exception as e:
            print(f"  Secret:   nicht lesbar — {e}")
        else:
            print(f"  Secret:   {_merkmal(aus_secret)}")
        if aus_umgebung and aus_secret:
            gleich = "".join(str(aus_umgebung).split()) == \
                "".join(str(aus_secret).split())
            print(f"  Gleich:   {'ja' if gleich else 'NEIN'}")
            if not gleich:
                print(f"            Die Umgebung hat Vorrang. Ein Wert, der "
                      f"einmal falsch\n"
                      f"            hineingeraten ist, bleibt die ganze "
                      f"Sitzung und verdeckt\n"
                      f"            das Secret. Abhilfe:\n"
                      f"                import os; "
                      f"os.environ.pop({var!r}, None)\n"
                      f"            danach diese Diagnose erneut.")
        form = G.schluesselform(anbieter, "".join(str(aus_secret or "").split()))
        if form:
            print(f"  Form:     {form}")

    # Was der Unterprozess sieht. Alle Schritte laufen als Unterprozess,
    # und dort gibt es kein google.colab.userdata — nur die Umgebung.
    print("\n--- Was ein Unterprozess sieht")
    pruef = (
        "import hashlib, os\n"
        "for var in ('ANTHROPIC_API_KEY', 'GEMINI_API_KEY'):\n"
        "    w = ''.join((os.environ.get(var) or '').split())\n"
        "    fp = hashlib.sha256(w.encode()).hexdigest()[:8] if w else '-'\n"
        "    print(f'  {var}: {len(w)} Zeichen, Fingerabdruck {fp}')\n")
    r = _lauf([sys.executable, "-c", pruef], cwd=code)
    print((r.stdout or r.stderr).rstrip() or "  keine Ausgabe")

    # Und jetzt die Matrix: dieselbe Anfrage auf den Wegen, die unser
    # Code wirklich geht. Genau einer davon scheitert, und welcher es
    # ist, sagt keine Fehlermeldung des Anbieters.
    print("\n--- Dieselbe Anfrage auf vier Wegen")
    try:
        from google.colab import userdata
        roh = "".join(str(userdata.get("ANTHROPIC_API_KEY") or "").split())
    except Exception as e:
        print(f"  Secret nicht lesbar — {e}")
        return
    if not roh:
        print("  Kein Secret ANTHROPIC_API_KEY vorhanden.")
        return

    import requests
    nachricht = {"model": "claude-opus-5", "max_tokens": 4,
                 "messages": [{"role": "user", "content": "OK"}]}
    kopf = {"x-api-key": roh, "anthropic-version": "2023-06-01",
            "content-type": "application/json"}

    def melde(name, fn):
        try:
            print(f"  {name:<34} {fn()}")
        except Exception as ex:
            print(f"  {name:<34} {type(ex).__name__}: "
                  f"{str(ex)[:120]}")

    melde("requests, ohne Beta", lambda: "HTTP " + str(requests.post(
        G.BACKENDS['anthropic'].URL, json=nachricht, headers=kopf,
        timeout=(10, 60)).status_code))
    melde("requests, mit Beta-Kopfzeile", lambda: "HTTP " + str(requests.post(
        G.BACKENDS['anthropic'].URL,
        json=dict(nachricht, fallbacks=[{"model": "claude-sonnet-5"}]),
        headers=dict(kopf, **{"anthropic-beta": G.BETA_FALLBACK}),
        timeout=(10, 60)).status_code))

    sdk = G.anthropic_sdk()
    if not sdk:
        print("  SDK nicht installiert — die beiden SDK-Wege entfallen.")
        return
    klient = sdk.Anthropic(api_key=roh, timeout=60, max_retries=0)
    melde("SDK, messages.create",
          lambda: "ok, " + klient.messages.create(**nachricht).model)
    melde("SDK, beta.messages.create",
          lambda: "ok, " + klient.beta.messages.create(
              **dict(nachricht, fallbacks=[{"model": "claude-sonnet-5"}]),
              betas=[G.BETA_FALLBACK]).model)

    print("\n  Scheitert nur eine Zeile, steht dort die Ursache. Scheitert "
          "keine,\n  liegt es am Unterprozess (siehe darueber) und nicht "
          "am Aufruf.")


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
