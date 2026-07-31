# Abbruchprobe — Colab

Der Colab-Betrieb ist darauf gebaut, dass ein Abbruch nichts kostet: Jeder
fertige Chunk liegt sofort in Drive, der Resume zählt Dateien in `teile/`
statt einer Zustandsdatei zu glauben. Diese Notiz hält fest, wie das
nachgeprüft wird — und was dabei herauskam.

## Ablauf

1. **Lauf starten.** Zelle 1 des `colab_runner.ipynb` ausführen und warten,
   bis mindestens drei Chunks durch sind (die Fortschrittszeile zeigt
   `[n/m] … fertig`).
2. **Chunkstand notieren.** Zelle 2 (`status`) in einer zweiten Ausführung
   starten; die Zahl hinter dem Schrittnamen ist der Stand, etwa `4/121`.
3. **VM hart trennen.** Laufzeit → *Sitzung beenden* (nicht nur den Tab
   schließen — das Trennen soll unangekündigt kommen).
4. **Neue VM.** Notebook erneut öffnen, Laufzeit verbinden.
5. **Zelle 1 erneut ausführen.** Sonst nichts. Kein `reset`, kein `neu`,
   keine Handgriffe im Dateibrowser.

## Erwartet

- Der Runner mountet Drive neu, holt den Code frisch in die VM und findet
  den Projektordner samt `projekt.json` unverändert vor.
- Die Ausgabe meldet `projekt.json im Projektordner vorhanden — unverändert
  übernommen`. Wird stattdessen „aus dem Repo kopiert" gemeldet, zeigt der
  Runner auf den falschen Ordner — **abbrechen und Pfad prüfen.**
- Der Lauf setzt am ersten offenen Chunk fort. Die in Schritt 2 notierten
  Chunks werden **nicht** neu gerechnet; der Zähler beginnt bei `n+1`.
- Kein Datenverlust in `teile/`, keine doppelten Kosten für bereits
  übersetzte Chunks.

## Was ein Fehlschlag bedeuten würde

| Beobachtung | Ursache |
|---|---|
| Lauf beginnt wieder bei Chunk 1 | `teile/` liegt nicht in Drive — Arbeitsverzeichnis prüfen |
| `projekt.json` wurde überschrieben | Überschreibschutz in `colab_start.projektordner_richten` defekt |
| Einzelne Chunkdateien fehlen oder sind leer | `os.replace` auf dem FUSE-Mount unzuverlässig — die Verifikation (Zelle 3, Schritt 1) hätte das gemeldet |
| „Es läuft bereits ein Lauf (PID …)" | PID-Sperre greift fälschlich in Colab |

## Ergebnis

### 31.07.2026 — teilweise nachvollzogen (Ian, Colab)

Laufzeit gelöscht, neue VM, Zelle 1 erneut. Was dabei belegt ist:

| | |
|---|---|
| Drive-Mount und Code-Klon | neu gemountet, `main — 2ba0ef4`, `Already up to date` |
| Arbeitsverzeichnis | `/content/drive/MyDrive/uebersetzung/1919` |
| `projekt.json` | „im Projektordner vorhanden — unverändert übernommen" — der Überschreibschutz greift |
| Quelltext | `input.txt`: 109.192 Wörter, gefunden |
| Schreibsemantik | `fsync` + `os.replace` + Zurücklesen auf dem Drive-Mount fehlerfrei |
| Resume auf Schrittebene | `selbsttest`, `preflight` und `konkordanz` wurden **nicht** wiederholt; der Lauf setzte am nächsten offenen Schritt an |

**Was noch aussteht:** Der Lauf stand bei `PAUSE_glossar`, also **vor** dem
ersten Übersetzungsschritt. Damit ist der Resume auf *Schrittebene* belegt,
der auf *Chunkebene* — das Zählen der Dateien in `teile/` — aber noch nicht.
Genau das ist die tragende Zusage des Entwurfs.

Die Probe ist deshalb zu wiederholen, sobald `test` oder `voll` läuft:
mindestens drei Chunks abwarten, Stand notieren, Laufzeit löschen, Zelle 1
erneut — und prüfen, dass der Zähler bei `n+1` weitermacht statt bei 1.

**Die Abnahme von Paket 2 bleibt bis dahin offen.**
