# Ein neues Buch übersetzen — Schritt für Schritt

Alle Codeblöcke sind zum Kopieren. Sie gehören in eine Colab-Zelle und werden
**einzeln** ausgeführt, nicht alle auf einmal.

Der ganze Ablauf besteht aus zwei Hälften: einer Einrichtung, die einmal
stattfindet, und einem Lauf, der von selbst an zwei Stellen anhält und auf
dich wartet.

---

## Teil 1 — Einrichten

### 1 · Ordner und Text

Im Google Drive einen Ordner für das Buch anlegen, zum Beispiel
`MyDrive/uebersetzung/neuesbuch`, und `input.txt` hineinlegen — den
niederländischen Volltext als reine Textdatei.

### 2 · Notebook auf das Buch zeigen lassen

`colab_runner.ipynb` öffnen. In **Zelle 0 und Zelle 1** jeweils die erste
Zeile ändern:

```python
PROJEKT = "/content/drive/MyDrive/uebersetzung/neuesbuch"
```

### 3 · Code laden

**Zelle 0** ausführen. Sie holt den Code und gibt zwei Zeilen aus:

```
a1b2c3d Letzter Commit
aktuell mit origin/main
```

Steht dort `ACHTUNG: N Commits hinter origin/main`, läuft alles Folgende gegen
alten Stand. Dann erst das klären — jeder weitere Versuch ist verschwendet.

### 4 · Projektordner einrichten

**Zelle 1** einmal ausführen. Sie mountet Drive, lädt die Secrets und kopiert
`projekt.json` und `anweisungen.md` aus dem Repo in den Projektordner. Eine
vorhandene `projekt.json` wird nie überschrieben.

Der Lauf startet dabei gleich mit — das ist in Ordnung, er hält beim ersten
Modellschritt ohnehin nicht lange auf. Wer das nicht will, bricht die Zelle
nach der Ordnermeldung ab.

### 5 · `projekt.json` anpassen

Die Datei liegt jetzt im Drive-Ordner und lässt sich im Colab-Dateibrowser
öffnen. Drei Dinge kommen infrage:

**Spreadsheet** (empfohlen, wenn du die Referenzdaten in Tabellen pflegen
willst) — die ID oder die volle Adresse aus der Browserzeile:

```json
"sheets_id": "1a2B3c4D5e6F7g8H9i0JklMnoPqrStUvWxYz"
```

**Ein anderes Modell für dieses Buch** — beide Rollen setzen, sonst übersetzt
das eine und revidiert das andere:

```json
"modell_uebersetzung": "claude-sonnet-5",
"modell_revision": "claude-sonnet-5",
"technik_ausnahmen": ["modell_uebersetzung", "modell_revision"]
```

Ohne `technik_ausnahmen` zieht der Technik-Abgleich die Werte aus dem Repo
nach und setzt deine Wahl still zurück.

**Rahmenmarker**, falls das Buch keine `#`-Zeilen als Ebenenwechsel benutzt:

```json
"rahmen_marker": ""
```

### 6 · Bei Google anmelden

Nur im Sheets-Betrieb, einmal je Colab-Sitzung:

```python
colab_start.sheets_anmelden()
```

Sagt die Ausgabe „Die Anmeldung gilt nur in dieser Zelle", laufen die
Sheets-Aufrufe über `colab_start.sync_im_kernel()` statt über
`colab_start.lauf(...)`. Im Normalfall steht dort „Unterprozesse sehen die
Anmeldung".

### 7 · Tabs im Spreadsheet anlegen

```python
colab_start.lauf("referenz_sync.py", "--vorlage", code=CODE)
```

Legt `Glossar`, `Personen`, `Figurenblatt`, `Anrede`, `Kapitel`, `Leitmotive`
und `ZitateReview` mit Kopfzeilen an. Vorhandene Tabs bleiben unberührt.

### 8 · Technikstand ansehen

```python
colab_start.lauf("pipeline.py", "technik", code=CODE)
```

Hier siehst du, ob deine Modellwahl als „von diesem Buch beansprucht" geführt
wird. Weicht etwas anderes ab, mit `--uebernehmen` nachziehen:

```python
colab_start.lauf("pipeline.py", "technik", "--uebernehmen", code=CODE)
```

---

## Teil 2 — Der Lauf

### 9 · Starten

**Zelle 1.** Von hier an arbeitet die Pipeline durch: Selbsttest, Tarifabgleich,
Preflight, Zitatrecherche, Konkordanzanalyse, Vorbereitung. Dann hält sie an.

**Bricht etwas ab: Zelle 1 erneut starten.** Der Resume zählt die fertigen
Abschnitte in `teile/` und macht dort weiter. Verloren geht höchstens der eine
Abschnitt, an dem gerade gearbeitet wurde.

Stand ansehen, solange Zelle 1 nicht läuft:

```python
colab_start.lauf("pipeline.py", "status", code=CODE)
```

### 10 · Erster Halt: `PAUSE_review`

Die Vorbereitung hat Glossar, Personen, Figurenblatt, Anrede, Leitmotive,
Stilprofil und Kapitel erzeugt. Jetzt liest ein Mensch drüber.

**Im Spreadsheet** (oder in den JSON-Dateien, wenn keine `sheets_id` gesetzt
ist) prüfen und korrigieren. Zwei Dinge, die dort nicht stehen:

- `stilprofil.json` hat bewusst keinen Tab — als Datei öffnen. Die
  Reihenfolge unter `perspektive` ist die des ersten Auftretens im Buch; der
  zuerst genannte Eintrag ist die Ebene, auf der der Text beginnt.
- `anweisungen.md` als Datei lesen und schärfen. Sie geht **wörtlich** in die
  System-Prompts: nur Anweisungen, keine Erläuterungen. Was vor der ersten
  `##`-Zeile steht, wird nie gelesen.

Prüfen, ob die Kapitelschlüssel wirklich im Quelltext vorkommen — sonst greift
die Zeile nie:

```python
import json
t = open("kapitel.json", encoding="utf-8").read()
k = json.loads(t)
q = open("input.txt", encoding="utf-8").read()
fehlt = [s for s in k if s not in q]
print(f"{len(k)} Kapitel, davon {len(fehlt)} nicht im Text gefunden")
for s in fehlt[:10]: print("  ", s)
```

Dann die Referenzdaten validieren, bevor Modellkosten entstehen:

```python
colab_start.lauf("referenz_sync.py", "--pruefen", code=CODE)
```

Fehler kommen zeilengenau in Spreadsheet-Zählung — Kopfzeile ist Zeile 1:

```
FEHLER: Referenzdaten fehlerhaft:
  Personen, Zeile 8: pronomen fehlt
```

Wenn alles stimmt, Pause schließen:

```python
colab_start.lauf("pipeline.py", "reset", "--ab", "PAUSE_review", "--fertig", code=CODE)
```

Danach **Zelle 1** erneut.

### 11 · Zweiter Halt: `PAUSE_pruefung`

Jetzt liegen Testübersetzung, Variantenvergleich und Testlektorat vor. Zu
lesen sind:

| Datei | Beantwortet |
|---|---|
| `bewertung_uebersetzung.md` | Lohnt der Revisionsdurchgang? Trägt die Tonlage? |
| `bewertung_varianten.md` | Welche Chunkgröße? Welches Modell? |
| `bewertung_lektorat.md` | Welche Lektoratsstufen lohnen? |
| `qa_*.txt` | Vollständigkeit, Register, Tempus, Typografie |

Der Bewertungsbericht weist bis zu drei Signale getrennt aus, jeweils mit dem
Modell in der Überschrift. Die Reihenfolge ihrer Belastbarkeit steht im
Bericht selbst: Diff-Statistik, dann Fremdurteil, dann Selbstcheck.

Entscheidungen kommen nach `projekt.json` — typisch `chunk_words`,
`revision_pass`, `lektorat_passes`. Dann:

```python
colab_start.lauf("pipeline.py", "reset", "--ab", "PAUSE_pruefung", "--fertig", code=CODE)
```

Danach **Zelle 1** erneut. Ab hier läuft alles durch: Volltext, Lektorat,
Qualitätsprüfungen, Annotation, Konsistenz, Paket.

Größenordnung für 110.000 Wörter: ein Arbeitstag Maschinenzeit, rund 60 $.

---

## Teil 3 — Danach

### 12 · Ergebnis herunterladen

`ergebnis.tar.gz` liegt im Projektordner. Im Dateibrowser rechtsklicken →
Download. **Vor dem Schließen der Sitzung** — die VM ist flüchtig.

Darin: die deutsche Fassung, die unlektorierte Übersetzung daneben, der
Änderungsbericht `bericht.html` mit Begründungsspalte, alle Prüfberichte, die
Referenzdaten und die Kostenabrechnung.

### 13 · Was zu lesen bleibt

- **`screening_review.md`** — Verdachtsstellen über das ganze Buch mit
  Chunknummer. Falschmeldungen sind eingeplant; die Liste sagt das selbst.
- **`bericht.html`** — jede Lektoratsänderung mit einer Zeile Begründung.
  Interessant sind die Zeilen, die einen Eingriff infrage stellen.
- **`qa_konsistenz.txt`** — Leitmotive, Terminologie über die Buchlänge,
  Anredeverläufe. Die Anredeprüfung ist ein Näherungsmaß und produziert
  Fehlalarme; das steht so im Bericht.

---

## Zitate

Kommen im Buch Mottos oder zitierte Zeilen vor, hat `zitatrecherche` sie
gesucht und **nicht eingesetzt**. Der Vorschlag steht mit Übersetzer,
Fundstelle und Konfidenz im Tab `ZitateReview` bzw. in `zitate_review.md`.

Eingesetzt wird ausschließlich, was in der Spalte `freigegeben` ein `ja`
trägt. Nach dem Eintragen:

```python
colab_start.lauf("zitatrecherche.py", "--uebernehmen", code=CODE)
```

Ohne Freigabe bleibt an der Stelle eine markierte Lücke. Das ist Absicht: Ein
rückübersetztes Motto ist ein Satz, den der zitierte Autor nie geschrieben
hat. Nicht-niederländische Zitate bleiben im Original und brauchen keine
Freigabe.

---

## Wenn etwas klemmt

| Meldung | Was hilft |
|---|---|
| `ANTHROPIC_API_KEY fehlt` | Colab-Reiter „Secrets", Schalter für dieses Notebook |
| `Schluessel google: fehlt` | Secret muss `GoogleKI` heißen |
| HTTP 429 | nichts tun — die Pipeline wartet und wiederholt |
| `unrecognized arguments: --…` | Code ist alt: Zelle 0, auf „aktuell mit origin/main" achten |
| `module … has no attribute …` | Kernel hält alte Importe: Zelle 0 leert sie |
| „Verbindung wird wiederhergestellt" | meist nur der Browser; `teile/` prüfen, ob Dateien wachsen |
| Laufzeit weg | Zelle 1 erneut — der Resume zählt `teile/` |
| `Referenzdaten fehlerhaft: …, Zeile N` | im Spreadsheet korrigieren, Schritt erneut |
| `Das Spreadsheet wuerde vorhandene Daten loeschen` | erst `referenz_sync.py --erstbefuellung` |
| `Verhältnis 0.29 -> Durchgang verworfen` | passiert; der Chunk wird wiederholt |
| `Keine Eingabe moeglich` bei `neu` | denselben Aufruf mit `--ja` wiederholen |

Ergebnisse löscht **nur** `pipeline.py neu`, und es zeigt vorher die Liste.
Drei Abstufungen: `--nur-test` räumt die Testauszüge, `--nur-teile`
zusätzlich die Chunks des Volllaufs, ohne Argument alles bis auf Quelltext,
Konfiguration und Referenzdateien.

---

## Der ganze Ablauf auf einen Blick

```
Zelle 0            Code laden, Stand prüfen
Zelle 1            einrichten und starten
                   ↓
   selbsttest · tarife · preflight · zitatrecherche · konkordanz · vorbereitung
                   ↓
PAUSE_review       Referenzdaten und anweisungen.md prüfen        ← du
                   ↓
   test · testB · bewertung · variantenvergleich · test_lektorat · qa · bewertung
                   ↓
PAUSE_pruefung     Berichte lesen, entscheiden                    ← du
                   ↓
   voll · qa · lektorat · qa · annotation · konsistenz · paket
                   ↓
ergebnis.tar.gz    herunterladen
```
