# Ablaufplan — literarische Übersetzung Niederländisch → Deutsch

Betrieben wird in Google Colab. Der Code kommt per `git` in die VM, gearbeitet
wird im Drive-Projektordner. Jeder fertige Abschnitt liegt sofort dauerhaft in
Drive — **ein Abbruch ist ein Nicht-Ereignis.**

Gesteuert wird alles über `pipeline.py`. Es kennt den Ablauf, weiß, wo er
steht, und setzt nach einer Unterbrechung fort. Die Einzelskripte sind
aufrufbar, werden im Normalbetrieb aber vom Orchestrator gestartet.

---

## 1 · Einmal je Sitzung

Notebook `colab_runner.ipynb` öffnen. Die Zellen tragen Nummern; **Zelle 0**
holt den Code, ohne einen Lauf zu starten:

```python
colab_start.lauf("pipeline.py", "status", code=CODE)
```

Zelle 0 gibt zwei Zeilen aus, auf die es ankommt:

```
9dc7af5 Merge pull request #23 …
aktuell mit origin/main
```

Steht dort `ACHTUNG: N Commits hinter origin/main`, läuft alles Folgende gegen
alten Code. Dann erst den Pull klären — jeder weitere Versuch ist verschwendet.

**Secrets** im Colab-Reiter hinterlegen und der Sitzung Zugriff geben:
`ANTHROPIC_API_KEY` und `GoogleKI`. Sie erscheinen nie in Dateien, Logs oder
Berichten.

**Nur im Sheets-Betrieb**, einmal je Sitzung:

```python
colab_start.sheets_anmelden()
```

Die Zelle meldet an und prüft nach, ob ein Unterprozess die Anmeldung sieht.
Sagt sie „Die Anmeldung gilt nur in dieser Zelle", laufen die Sheets-Aufrufe
über `colab_start.sync_im_kernel()` statt über `colab_start.lauf(...)`.

---

## 2 · Ein neues Buch einrichten

1. Drive-Ordner anlegen, `input.txt` hineinlegen.
2. `PROJEKT` in Zelle 0 und Zelle 1 auf diesen Ordner setzen.
3. Zelle 1 einmal starten — sie kopiert `projekt.json` und `anweisungen.md`
   aus dem Repo, wenn dort keine liegen, und sagt es. **Eine vorhandene
   `projekt.json` wird nie überschrieben.**
4. Wer mit Sheets arbeitet: Spreadsheet anlegen, die ID oder die volle Adresse
   als `sheets_id` in `projekt.json` eintragen, dann

```python
colab_start.lauf("referenz_sync.py", "--vorlage", code=CODE)
```

Damit steht die Einrichtung. Alles Weitere macht der Lauf.

---

## 3 · Der Lauf

Zelle 1. Sie mountet Drive, holt den Code, lädt die Secrets, wechselt in den
Projektordner und startet den Lauf im Vordergrund:

```python
colab_start.lauf("pipeline.py", "run", code=CODE)
```

Die laufende Fortschrittsausgabe hält die Sitzung nebenbei wach. Sie ist kein
Beiwerk — ohne sie stuft Colab die Sitzung als untätig ein.

**Bricht etwas ab: Zelle 1 erneut starten.** Der Resume zählt die Dateien in
`teile/` und setzt am nächsten offenen Abschnitt fort. Verloren geht höchstens
der eine Abschnitt, an dem gerade gearbeitet wurde.

### Die Schritte

| Schritt | Was passiert | Modell |
|---|---|:-:|
| `selbsttest` | Normalisierer, Metriken und Prompts prüfen | — |
| `preflight` | Systemprüfung, Textprüfung, Zitaterkennung | — |
| `zitatrecherche` | Zitatnachweise suchen, Freigabeliste erzeugen | ja |
| `konkordanz` | Kandidatenanalyse, Analysepaket | — |
| `vorbereitung` | Referenzdateien und Anweisungsentwurf erzeugen | ja |
| **`PAUSE_review`** | **Referenzdateien und `anweisungen.md` prüfen** | — |
| `test` | Testübersetzung, zwei Auszüge | ja |
| `testB`, `testC` | dieselben Auszüge in den Vergleichsvarianten | ja |
| `bewertung` | Testübersetzung bewerten | ja |
| `variantenvergleich` | Varianten gegen die Basis, mit Kosten je Variante | — |
| `test_lektorat` | Testlektorat | ja |
| `qa_test_lekt` | Qualitätsprüfung des Testlektorats | — |
| `bew_lektorat` | Testlektorat bewerten | ja |
| **`PAUSE_pruefung`** | **Berichte prüfen, entscheiden, einspielen** | — |
| `voll` | vollständige Übersetzung | ja |
| `qa_uebersetzung` | Qualitätsprüfung der Übersetzung | — |
| `lektorat` | vollständiges Lektorat | ja |
| `qa_lektorat` | Qualitätsprüfung des Lektorats | — |
| `annotation` | Begründungen und Volltext-Screening (berichtend) | ja |
| `konsistenz` | globale Konsistenzprüfung über das ganze Buch | — |
| `paket` | Ergebnis paketieren | — |

Die aktuelle Liste mit Restzeiten und Chunkstand:

```python
colab_start.lauf("pipeline.py", "status", code=CODE)
```

Solange Zelle 1 läuft, wird diese Zelle nur eingereiht. Den Chunkstand liest
man während eines Laufs an der Ausgabe von Zelle 1 ab.

---

## 4 · Die beiden Pausen

Der Lauf hält von selbst an und sagt, was zu tun ist.

### `PAUSE_review` — nach der Vorbereitung

Zu prüfen sind Glossar, Personen, Figurenblatt, Anrede, Leitmotive,
Stilprofil und Kapitel — im Spreadsheet oder als Dateien im Projektordner.
Dateien auf `.neu` sind **Vorschläge neben vorhandenen Daten**; sie werden
nicht von selbst übernommen.

Dann `anweisungen.md` lesen und schärfen. Sie geht wörtlich in die
System-Prompts: nur Anweisungen, keine Erläuterungen. Was vor der ersten
`##`-Zeile steht, wird nie gelesen.

Weiter mit:

```python
colab_start.lauf("pipeline.py", "reset", "--ab", "PAUSE_review", "--fertig", code=CODE)
```

Danach Zelle 1 erneut.

### `PAUSE_pruefung` — nach dem Testlauf

Zu lesen sind `bewertung_uebersetzung.md`, `bewertung_lektorat.md`,
`bewertung_varianten.md` und die QA-Berichte. Die Entscheidungen, die hier
fallen: Lohnt der Revisionsdurchgang? Welche Chunkgröße? Welches Modell?
Trägt die Tonlage?

Angepasste Werte kommen nach `projekt.json`. Weiter mit:

```python
colab_start.lauf("pipeline.py", "reset", "--ab", "PAUSE_pruefung", "--fertig", code=CODE)
```

---

## 5 · Referenzdaten im Spreadsheet

Bei gesetzter `sheets_id` ist das Spreadsheet die Quelle; die JSONs sind
erzeugte Artefakte und werden überschrieben. Sie von Hand zu editieren ist
dann sinnlos.

Tabs: `Glossar`, `Personen`, `Figurenblatt`, `Anrede`, `Kapitel`,
`Leitmotive`, `ZitateReview`. `stilprofil.json` hat bewusst keinen Tab — es
ist kein Datensatz, sondern ein Steckbrief, und bleibt eine Datei.

Vorhandene JSONs einmalig ins Spreadsheet übertragen:

```python
colab_start.lauf("referenz_sync.py", "--erstbefuellung", code=CODE)
```

Vor einem Lauf prüfen, ohne etwas zu schreiben:

```python
colab_start.lauf("referenz_sync.py", "--pruefen", code=CODE)
```

Die Prüfung meldet **zeilengenau in Spreadsheet-Zählung** — Kopfzeile ist
Zeile 1, der erste Datensatz Zeile 2:

```
FEHLER: Referenzdaten fehlerhaft:
  Personen, Zeile 8: pronomen fehlt
```

Ohne `sheets_id` bleibt alles wie früher: Die JSONs werden direkt gelesen.

---

## 6 · Zitate

`zitatrecherche` sucht zu jedem erkannten Zitat die anerkannte deutsche
Fassung — und **setzt sie nicht ein.** Der Vorschlag landet mit Übersetzer,
Fundstelle und Konfidenz in `zitate_review.md` bzw. im Tab `ZitateReview`.

Eingesetzt wird ausschließlich, was in der Spalte `freigegeben` ein `ja`
trägt. Nach dem Eintragen:

```python
colab_start.lauf("zitatrecherche.py", "--uebernehmen", code=CODE)
```

Ohne Freigabe bleibt an der Stelle eine markierte Lücke. Das ist Absicht: Ein
rückübersetztes Motto ist ein Satz, den der zitierte Autor nie geschrieben
hat, und das fällt im Druck auf. Nicht-niederländische Zitate bleiben im
Original und brauchen keine Freigabe.

---

## 7 · Kosten

Jeder Modellaufruf meldet seine Token-Usage; `manifest.json` summiert je
Rolle. Am Ende eines Laufs erscheint die Übersicht von selbst. Zwischendurch:

```python
colab_start.lauf("pipeline.py", "status", code=CODE)
```

Vor einem teuren Schritt lohnt der Blick ohne Kosten:

```python
colab_start.lauf("vorbereitung.py", "--nur-anzeigen", code=CODE)
```

```python
colab_start.lauf("annotation.py", "--nur-anzeigen", code=CODE)
```

Größenordnung für ein Buch von rund 110.000 Wörtern, gemessen am ersten
Volllauf: Übersetzung mit Revision rund 36 $, Lektorat rund 23 $,
Vorbereitung rund 1 $. Die Werte hängen am Modell und an der Chunkgröße —
`variantenvergleich` weist sie je Variante getrennt aus.

---

## 8 · Wenn etwas klemmt

| Meldung | Was los ist | Was hilft |
|---|---|---|
| `ANTHROPIC_API_KEY fehlt` | Secret nicht hinterlegt oder der Sitzung nicht freigegeben | Colab-Reiter „Secrets", Schalter für dieses Notebook |
| `Schluessel google: fehlt` | Secret heißt nicht `GoogleKI` | umbenennen, Zelle 1 erneut |
| HTTP 429 | Ratenlimit des Anbieters | nichts tun — die Pipeline wartet und wiederholt bis `max_retries` |
| HTTP 400 bei einem Modell | Modellname veraltet oder Parameter abgelehnt | `pipeline.py technik --uebernehmen`, dann erneut |
| Zelle bricht ab, „Verbindung wird wiederhergestellt" | Browser hat die Verbindung verloren, die VM läuft meist weiter | Dateien in `teile/` ansehen; wachsen sie, nur neu verbinden |
| Laufzeit wirklich weg | VM recycelt | Zelle 1 erneut — der Resume zählt `teile/` |
| `Referenzdaten fehlerhaft: …, Zeile N` | Sheet-Zeile unvollständig oder doppelt | im Spreadsheet korrigieren, denselben Schritt erneut |
| `Das Spreadsheet wuerde vorhandene Daten loeschen` | Tabs leer, JSONs gefüllt | erst `referenz_sync.py --erstbefuellung` |
| `Tab 'X' fehlt im Spreadsheet` | Tabname vertippt oder Tab fehlt | Namen prüfen, sonst `referenz_sync.py --vorlage` |
| `Verhältnis 0.29 -> Durchgang verworfen` | Antwort kam gekürzt zurück | passiert; der Chunk wird bis zu `max_retries` wiederholt |
| `unrecognized arguments: --…` | Code in der VM ist alt | Zelle 0, auf „aktuell mit origin/main" achten |
| `module … has no attribute …` | Kernel hält alte Importe | Zelle 0 leert sie und importiert neu |

Ergebnisse löscht **nur** `pipeline.py neu`, und es fragt vorher. Drei
Abstufungen: `--nur-test` räumt die Testauszüge (nötig vor einem
Variantenvergleich, damit die Basis unter denselben Vorgaben neu entsteht),
`--nur-teile` zusätzlich die Chunks des Volllaufs, ohne Argument alles bis auf
Quelltext, Konfiguration und Referenzdateien.

---

## Anhang · Betrieb ohne Colab

Die Pipeline läuft auf jedem Server, auf dem `python3` und `requests`
vorhanden sind. Es entfallen Drive-Mount und Colab-Secrets; die Schlüssel
kommen aus Umgebungsvariablen:

```bash
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
```

Gearbeitet wird im Projektordner, gestartet direkt:

```bash
python3 pipeline.py run
```

`--hg` startet den Lauf im Hintergrund und legt eine PID-Datei an; in Colab
ist das gesperrt, weil der Lauf dort in den Vordergrund der Zelle gehört.

Für den Sheets-Zugriff braucht es dann ein Dienstkonto in
`GOOGLE_APPLICATION_CREDENTIALS`. Ohne das bleibt `sheets_id` leer, und die
Referenz-JSONs werden direkt gepflegt — der Rückfallpfad ist vollwertig und
wird nicht entfernt.

Der Ollama-Rückfall existiert weiter: Bleibt `modell_<rolle>` leer, greift
`backend`/`modell` aus `projekt.json`. Gedacht ist er für den Fall, dass eine
API ausfällt, nicht für den Normalbetrieb.
