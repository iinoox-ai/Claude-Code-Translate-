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

**Noch nicht nachvollzogen.**

Ian fährt die Probe in Colab und meldet die Ausgabe zurück; Datum,
Chunkstand vor und nach dem Abbruch sowie das Ergebnis werden hier
eingetragen. Bis dahin gilt die Abnahme von Paket 2 als offen — ein Haken
ohne durchgeführte Probe wäre wertlos.
