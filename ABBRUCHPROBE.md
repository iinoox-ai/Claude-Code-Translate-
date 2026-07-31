# Abbruchprobe — Colab

Der Colab-Betrieb ist darauf gebaut, dass ein Abbruch nichts kostet: Jeder
fertige Chunk liegt sofort in Drive, der Resume zählt Dateien in `teile/`
statt einer Zustandsdatei zu glauben. Diese Notiz hält fest, wie das
nachgeprüft wird — und was dabei herauskam.

## Voraussetzung

Die Probe braucht einen Schritt, der **Chunks übersetzt** — `test` oder
`voll`. Ein Abbruch an einer Pause oder zwischen zwei Schritten belegt nur
den Resume auf Schrittebene, und den kann das Manifest allein leisten.

## Ablauf

1. **Lauf starten.** Zelle 1 ausführen. Sobald der Übersetzungsschritt
   beginnt, meldet er `Eingabe: … in N Chunks` — diese Zahl merken.
2. **Mitlesen.** Jeder fertige Chunk erzeugt zwei Zeilen:

       [3/5] 812 Wörter
           Pass 1     34s  (1.08x)
           [3/5] fertig  (Rest ca. 2 min)

   Warten, bis **mindestens drei** Chunks fertig sind. Den Stand aus der
   letzten `fertig`-Zeile notieren.

   Nicht über Zelle 4 (`status`) gehen: Colab arbeitet Zellen nacheinander
   ab, sie würde nur eingereiht und liefe erst nach dem Lauf.
3. **VM hart trennen.** Laufzeit → *Sitzung beenden*. Nicht nur den Tab
   schließen — der Abbruch soll unangekündigt kommen.
4. **Neue VM.** Notebook erneut öffnen, Laufzeit verbinden.
5. **Zelle 1 erneut ausführen.** Sonst nichts. Kein `reset`, kein `neu`,
   keine Handgriffe im Dateibrowser.

## Erwartet

- Der Runner mountet Drive neu, holt den Code frisch in die VM und findet
  den Projektordner samt `projekt.json` unverändert vor.
- Die Ausgabe meldet `projekt.json im Projektordner vorhanden — unverändert
  übernommen`. Wird stattdessen „aus dem Repo kopiert" gemeldet, zeigt der
  Runner auf den falschen Ordner — **abbrechen und Pfad prüfen.**
- Der Übersetzungsschritt meldet wörtlich:

      3 Chunks liegen vor, Fortsetzung ab 4.

  **Das ist der Kernsatz der Probe.** Er kommt aus `teile_vorhanden()`,
  das Dateien zählt statt einer Zustandsdatei zu glauben.
- Der Zähler beginnt bei `n+1`, die bereits übersetzten Chunks werden
  nicht neu gerechnet — kein Datenverlust, keine doppelten Kosten.

## Was ein Fehlschlag bedeuten würde

| Beobachtung | Ursache |
|---|---|
| Lauf beginnt wieder bei Chunk 1 | `teile/` liegt nicht in Drive — Arbeitsverzeichnis prüfen |
| `projekt.json` wurde überschrieben | Überschreibschutz in `colab_start.projektordner_richten` defekt |
| Einzelne Chunkdateien fehlen oder sind leer | `os.replace` auf dem FUSE-Mount unzuverlässig — die Verifikation (Zelle 3, Schritt 1) hätte das gemeldet |
| „Es läuft bereits ein Lauf (PID …)" | PID-Sperre greift fälschlich in Colab |

## Ergebnis

### 31.07.2026 — Verifikation bestanden (Ian, Colab)

`verifikation.py` im Projektordner, alle vier konfigurierten Modelle:

| | |
|---|---|
| `claude-opus-5` | antwortet; Mini-Echtlauf sauber, 149 ein / 101 aus |
| `gemini-3.1-pro-preview` | antwortet; Mini-Echtlauf sauber, 83 ein / 47 aus |
| `claude-fable-5` (Paket 5) | antwortet |
| `gemini-3.6-flash` (Paket 7) | antwortet |
| Sampling | Opus 5 lehnt `temperature` mit HTTP 400 ab; Gemini akzeptiert und ignoriert (HTTP 200) |
| Google-Tarife | beide auf der Preisseite belegt |

Ergebnis: 0 Fehler, 1 Warnung (die Gemini-Beobachtung), **BESTANDEN**.

### 31.07.2026 — Abbruchprobe teilweise nachvollzogen (Ian, Colab)

Laufzeit gelöscht, neue VM, Zelle 1 erneut. Was dabei belegt ist:

| | |
|---|---|
| Drive-Mount und Code-Klon | neu gemountet, `main — 2ba0ef4`, `Already up to date` |
| Arbeitsverzeichnis | `/content/drive/MyDrive/uebersetzung/1919` |
| `projekt.json` | „im Projektordner vorhanden — unverändert übernommen" — der Überschreibschutz greift |
| Quelltext | `input.txt`: 109.192 Wörter, gefunden |
| Schreibsemantik | `fsync` + `os.replace` + Zurücklesen auf dem Drive-Mount fehlerfrei |
| Resume auf Schrittebene | `selbsttest`, `preflight` und `konkordanz` wurden **nicht** wiederholt; der Lauf setzte am nächsten offenen Schritt an |

**Damals noch offen:** Der Lauf stand bei `PAUSE_glossar`, also vor dem
ersten Übersetzungsschritt. Belegt war damit nur der Resume auf
Schrittebene.

### 31.07.2026 — Abbruchprobe vollständig nachvollzogen (Ian, Colab)

Abbruch während `test` nach 3 von 5 Chunks, Laufzeit gelöscht, neue VM,
nur Zelle 1 erneut. Die Ausgabe des Testschritts nach dem Neustart:

```
3 Chunks liegen vor, Fortsetzung ab 4.

[4/5] 726 Wörter
    Pass 1     40s  (0.98x)
    Pass 2     55s  (0.98x)
    [1/2] fertig  (Rest ca. 2 min)

[5/5] 83 Wörter
    …
Fertig nach 2 min.
```

Der Zähler setzt bei 4 an, die drei fertigen Chunks werden nicht neu
gerechnet, `projekt.json` blieb unverändert. Die Restzeitschätzung zählt
korrekt die **verbliebenen** zwei Chunks (`[1/2]`, `[2/2]`), nicht alle
fünf.

**Damit ist die Abnahme von Paket 2 erfüllt:** Drive-Mount,
Überschreibschutz, Schreibsemantik, Resume auf Schritt- und auf
Chunkebene.

### Ein Fund am Rande

Der Kopf des Testlaufs meldete `Modell: mistral-medium-3.5:128b-q8_0` —
den Ollama-Rückfallschlüssel. Gelaufen ist der Chunk über
`claude-opus-5`; in Colab existiert kein Ollama, ein echter Aufruf dorthin
wäre an der Verbindung gescheitert. Es war ausschließlich die Anzeige.

Behoben, und der Selbsttest prüft jetzt, dass kein Skript `cfg["modell"]`
statt des Rollenmodells ausgibt. Payloadtests finden so etwas nicht — sie
prüfen, was rausgeht, nicht was auf dem Schirm steht.
