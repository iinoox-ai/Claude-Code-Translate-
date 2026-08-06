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

**Absätze werden durch Leerzeilen getrennt.** Viele Exporte liefern
stattdessen eine Zeile je Absatz ohne Leerzeile dazwischen; für die Pipeline
ist das *ein* Absatz, und die Chunkeinteilung hat dann nichts, woran sie
schneiden kann. Der Preflight erkennt den Fall und unterscheidet ihn von einem
Text, der mitten im Satz umbrochen ist (PDF-Extraktion). Im ersten Fall hilft
**Zelle 8**, im zweiten nur ein besserer Export — dort sind die Absatzgrenzen
nicht mehr im Text enthalten.

### 2 · Notebook auf das Buch zeigen lassen

`colab_runner.ipynb` öffnen. In **Zelle 0** die erste Zeile ändern — das ist
die einzige Stelle im Notebook, die ein neues Buch braucht:

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

**Zelle 2** einmal ausführen. Sie mountet Drive, lädt die Secrets und legt
`projekt.json` und `anweisungen.md` im Projektordner an — die Konfiguration
aus `projekt_vorlage.json` des Repos.

**Ab hier gilt die Datei im Drive-Ordner.** Sie wird nie überschrieben, und
alles Weitere — `sheets_id`, `rahmen_marker`, die Modellwahl — wird dort
geändert. Das Repo fasst man für ein neues Buch nicht mehr an. Die Vorlage
bleibt unverändert liegen und ist beim nächsten Buch wieder der Ausgangspunkt.

**Beim Erstlauf startet die Zelle den Lauf nicht.** Sie legt die Datei an und
hält an, mit der Liste dessen, was jetzt einzutragen ist. Das ist der einzige
Zeitpunkt, zu dem das geht: `sheets_id` liest die Vorbereitung, um die
Referenzdaten ins Spreadsheet zu stellen, und `rahmen_marker` entscheidet über
die Chunkgrenzen. Beides nachträglich zu setzen heißt, die betroffenen Schritte
zu wiederholen.

Nach dem Eintragen (Abschnitt 5) einfach **Zelle 2 erneut** ausführen — dann
läuft sie durch.

### 5 · `projekt.json` anpassen

Die Datei liegt jetzt im Drive-Ordner und lässt sich im Colab-Dateibrowser
öffnen. Drei Dinge kommen infrage:

**Spreadsheet** (empfohlen, wenn du die Referenzdaten in Tabellen pflegen
willst) — die ID oder die volle Adresse aus der Browserzeile:

```json
"sheets_id": "1a2B3c4D5e6F7g8H9i0JklMnoPqrStUvWxYz"
```

**Das Spreadsheet bleibt dabei leer, und das ist richtig so.** Die Tabs werden
nicht von Hand gefüllt — sie werden angelegt und dann von der Vorbereitung
beschrieben. Anlegen:

```python
colab_start.sheets_anmelden(code=CODE)                       # zuerst!
colab_start.lauf("referenz_sync.py", "--vorlage", code=CODE)
```

**Nötig ist das nicht** — jeder Schritt, der in einen Tab schreibt, legt ihn
an, wenn er fehlt. `--vorlage` nimmt es nur vorweg, damit die Struktur schon
im Spreadsheet steht, bevor der Lauf beginnt. Wer es überspringt, verliert
nichts.

**Die Anmeldung dagegen ist Pflicht, und zwar vor jedem Sheets-Aufruf** — sie
gilt je Colab-Sitzung, nicht je Buch. Ohne sie bricht der Schritt mit
`Keine Google-Anmeldung vorhanden` ab (Abschnitt 6 erklärt, warum die Meldung
so genau ist).

Das legt jeden fehlenden Tab mit seiner Kopfzeile an und lässt vorhandene in
Ruhe. Gefüllt werden sie später: `vorbereitung.py` erzeugt Glossar, Personen,
Figurenblatt, Anrede, Leitmotive und Kapitel aus dem Analysepaket und trägt sie
ins Spreadsheet ein (`erstbefuellung`, nur in leere Tabs). Erst **ab
`PAUSE_review`** ist das Spreadsheet die Quelle: Was du dort änderst, holt
`referenz_sync` in die JSON-Dateien zurück. Sie von Hand zu editieren ist ab
dann sinnlos — sie werden überschrieben.

Ohne `sheets_id` gilt derselbe Ablauf ohne Google: Die Vorbereitung schreibt
die JSON-Dateien, und die pflegst du direkt.

**Die Modellwahl für dieses Buch festhalten.** Übersetzung und Revision laufen
mit `claude-opus-5` — dort wird nicht gespart, weil jeder Fehler dieses Passes
durch alles Weitere getragen wird. Wer verhindern will, dass eine spätere
Repo-Änderung sie nachzieht, beansprucht sie für dieses Buch:

```json
"modell_uebersetzung": "claude-opus-5",
"modell_revision": "claude-opus-5",
"technik_ausnahmen": ["modell_uebersetzung", "modell_revision"]
```

Ohne `technik_ausnahmen` zieht der Technik-Abgleich die Werte aus dem Repo
nach und setzt deine Wahl still zurück. Mit ihr bleiben sie stehen.

**Wer wirklich andere Modelle will**, ersetzt die Namen — aber dann bitte
beide: Sonst übersetzt das eine Modell und revidiert das andere. Was die
Belegung je Rolle kostet und warum sie so ist, zeigt

```python
colab_start.lauf("pipeline.py", "modelle", code=CODE)
```

Und Vorsicht: `technik_ausnahmen` **schützt** die Abweichung. Ein aus Versehen
übernommener Wert bleibt damit auch bei `pipeline.py technik --uebernehmen`
stehen.

**Rahmenmarker** — dazu gleich mehr, siehe den nächsten Abschnitt.

### 5a · Die eine Frage, die dieses Buch beantworten muss

> **Wie sind die Erzählebenen in diesem Text ausgezeichnet?**

Ein Roman mit Rahmenhandlung, Rückblenden oder Einschüben hat Ebenen mit
verschiedenem Tempus und verschiedener Person. An jeder Fuge zwischen ihnen
muss die deutsche Rückschau zurückgesetzt werden — sonst bluten Tempus und
Person der einen Ebene in die andere.

Es gibt zwei Quellen, und sie schließen einander aus:

| Der Autor zeichnet die Wechsel aus | Der Autor zeichnet sie nicht aus |
|---|---|
| `rahmen_marker` auf das Zeichen setzen — ein Absatz, der **nur** daraus besteht | `ebenen.json` erzeugen; das macht die Vorbereitung von selbst |

`ebenen.json` hat Vorrang, der Marker ist der Rückfall. Benutzt das Buch keine
`#`-Zeilen und soll ausschließlich `ebenen.json` gelten:

```json
"rahmen_marker": ""
```

**Warum das hier steht und nicht weiter hinten.** Beim Buch 1919 kannte das
Stilprofil fünf Ebenen. Der Marker stand auf `#`, und der Autor hatte ihn nie
benutzt. Ergebnis: **eine** Gruppe über 147 Chunks, keine einzige Fuge — die
Rückschau lief über jeden Ebenenwechsel hinweg. Gesehen hat es niemand, weil
die buchweite Perfektquote über die Ebenen mittelt.

Seither prüft der Preflight es für dich und meldet:

```
WARN  Rahmenmarker »#« kommt im Text nicht vor
```

Diese Zeile ist keine Formalie. Kommt sie und hat das Buch mehrere Ebenen,
dann hängt alles an `ebenen.json` — und die gehört im ersten Halt gelesen.

### 6 · Bei Google anmelden

Nur im Sheets-Betrieb, einmal je Colab-Sitzung:

```python
colab_start.sheets_anmelden()
```

Sagt die Ausgabe „Die Anmeldung gilt nur in dieser Zelle", laufen die
Sheets-Aufrufe über `colab_start.sync_im_kernel()` statt über
`colab_start.lauf(...)`. Im Normalfall steht dort „Unterprozesse sehen die
Anmeldung".

**Dieser Schritt ist nicht optional, und er gilt je Sitzung.** Wird er
vergessen, meldet der Preflight:

```
Keine Google-Anmeldung — die ID und die Freigabe sind nicht das Problem.
```

Vor August 2026 stand dort stattdessen „Spreadsheet … nicht erreichbar —
stimmt die ID, und ist das Dokument freigegeben?", zusammen mit einem
Fehler von `metadata.google.internal`. Beides zeigte in die falsche
Richtung: Was da antwortete, war der Metadatendienst der Colab-VM, nicht
Google Sheets.

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

**Zelle 2.** Von hier an arbeitet die Pipeline durch: Selbsttest, Tarifabgleich,
Preflight, Zitatrecherche, Konkordanzanalyse, Vorbereitung. Dann hält sie an.

**Bricht etwas ab: Zelle 2 erneut starten.** Der Resume zählt die fertigen
Abschnitte in `teile/` und macht dort weiter. Verloren geht höchstens der eine
Abschnitt, an dem gerade gearbeitet wurde.

Stand ansehen, solange Zelle 2 nicht läuft:

```python
colab_start.lauf("pipeline.py", "status", code=CODE)
```

### 10 · Erster Halt: `PAUSE_review`

Die Vorbereitung hat Glossar, Personen, Figurenblatt, Anrede, Leitmotive,
Stilprofil, Kapitel und `ebenen.json` erzeugt. Jetzt liest ein Mensch drüber.

**Im Spreadsheet** (oder in den JSON-Dateien, wenn keine `sheets_id` gesetzt
ist) prüfen und korrigieren. Drei Dinge, die dort nicht stehen:

- `stilprofil.json` hat bewusst keinen Tab — als Datei öffnen. Die
  Reihenfolge unter `perspektive` ist die des ersten Auftretens im Buch; der
  zuerst genannte Eintrag ist die Ebene, auf der der Text beginnt.
- **`ebenen.json` ist die wichtigste Datei dieses Halts** (siehe 5a). Sie ist
  eine **Liste**, und die Reihenfolge ist die Information. Jeder Eintrag
  nennt unter `beginn` die ersten Wörter des Absatzes **im Wortlaut der
  Quelle** und unter `ebene` den Namen aus dem Stilprofil. Zu prüfen ist
  nicht die Form — das tut der Preflight —, sondern ob die Fuge am
  **richtigen** Absatz sitzt. Dafür ist diese Pause da.
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

Danach **Zelle 2** erneut.

### 11 · Zweiter Halt: `PAUSE_pruefung`

Jetzt liegen Testübersetzung, Variantenvergleich und Testlektorat vor. Zu
lesen sind:

| Datei | Beantwortet |
|---|---|
| `bewertung_uebersetzung.md` | Lohnt der Revisionsdurchgang? Trägt die Tonlage? |
| `bewertung_varianten.md` | Welche Chunkgröße? Welches Modell? |
| `bewertung_lektorat.md` | Welche Lektoratsstufen lohnen? |
| `qa_*.txt` | Vollständigkeit, Register, Tempus, Typografie |

Der Testlauf schneidet **drei** Auszüge: Erzählung, Dialog und die
Fallenpassage — die Stelle mit der höchsten Dichte an falschen Freunden,
Diminutiven, `zou` und Verlaufsformen. Die ersten beiden beantworten, ob der
Text als deutsche Prosa besteht; der dritte, ob die Warnungen aus dem
Fallenblock überhaupt ankommen. Im Bericht steht er unter „Fallen".

Der Bewertungsbericht weist bis zu drei Signale getrennt aus, jeweils mit dem
Modell in der Überschrift. Die Reihenfolge ihrer Belastbarkeit steht im
Bericht selbst: Diff-Statistik, dann Fremdurteil, dann Selbstcheck.

Wer über den Stapel laufen lassen will (Schritt 11a), sollte hier zusätzlich
die **Nähte** messen — sie sind der Preis dieses Wegs:

```python
colab_start.lauf("bewertung.py", "--fugen", code=CODE)
```

Acht Stichproben an Chunkübergängen, je 120 Wörter um die Naht, Urteil
bruchlos/holprig/Bruch. Über 10 % holprig ist eine Marke, keine Note.

Entscheidungen kommen nach `projekt.json` — typisch `chunk_words`,
`revision_pass`, `lektorat_passes`. Dann:

```python
colab_start.lauf("pipeline.py", "reset", "--ab", "PAUSE_pruefung", "--fertig", code=CODE)
```

Danach **Zelle 2** erneut. Ab hier läuft alles durch: Volltext, Lektorat,
Qualitätsprüfungen, Annotation, Konsistenz, Paket.

Größenordnung für 110.000 Wörter: ein Arbeitstag Maschinenzeit, rund 60 $.

### 11a · Optional: den Volltext über den Stapel

`uebersetzung.py --stapel` schickt den Volllauf über die Stapel-API. Das
kostet **die Hälfte**, und statt 147 Aufrufen nacheinander laufen mehrere
Ketten nebeneinander.

Der Preis sind **Nähte ohne deutsche Rückschau**: Ein Chunk sieht die Fassung
des vorigen nur innerhalb seiner Kette. Geschnitten wird zuerst an den
Ebenenfugen — dort setzt die Rückschau ohnehin zurück, diese Schnitte kosten
nichts. Erst `kette_max` erzwingt weitere.

Erst den Plan ansehen:

```python
colab_start.lauf("pipeline.py", "wellen", code=CODE)
```

```
 kette_max   Ketten   Wellen   breiteste   Nähte
         —        3       37           3       0  <- eingestellt
        20        6       19           6       3
        10       11       10          11       8
```

`kette_max: 0` (Vorgabe) ist die Zeile ohne Qualitätskosten. Jeder größere
Wert ist eine Abwägung — und was eine Naht wirklich wert ist, sagt nicht
diese Tabelle, sondern `bewertung.py --fugen` aus Schritt 11.

Was der Stapel nicht liefert — abgelehnt, abgelaufen, fehlerhaft —, holt der
Lauf einzeln nach. Erst dort greift der Ablehnungsrückfall; die Stapel-API
kennt ihn nicht.

---

## Teil 3 — Danach

### 12 · Ergebnis herunterladen

`ergebnis.tar.gz` liegt im Projektordner. Im Dateibrowser rechtsklicken →
Download. **Vor dem Schließen der Sitzung** — die VM ist flüchtig.

Darin: die deutsche Fassung, die unlektorierte Übersetzung daneben, der
Änderungsbericht `bericht.html` mit Begründungsspalte, alle Prüfberichte, die
Referenzdaten und die Kostenabrechnung.

### 13 · Was zu lesen bleibt

- **`screening_review.md`** — Verdachtsstellen über das ganze Buch.
  Gleichlautende Meldungen stehen in **einer** Zeile; die Spalte `Chunks`
  nennt alle Fundstellen und die Spalte daneben, wie oft. Eine Zeile mit
  vierzig Fundstellen ist die interessanteste der Liste: Das ist ein Fehler,
  der sich durchzieht. Falschmeldungen sind eingeplant; die Liste sagt das
  selbst. Steht oben ein Kasten „**Nicht geprüft:** N Chunks", sind einzelne
  Aufrufe gescheitert — `annotation.py --nur screening` holt sie nach, die
  fertigen Bündel laufen nicht noch einmal.
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

Daneben steht die Spalte `belege`: die URLs der Treffer, auf die sich die
Antwort stützt. Sie sind **abgerufen**, während `uebersetzer` und `quelle` das
Modell formuliert hat. Beim Freigeben ist das der Unterschied, auf den es
ankommt — vollständig, mit Titel und belegtem Wortlaut, stehen sie im
Abschnitt „Befunde im Einzelnen".

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
| Laufzeit weg | Zelle 2 erneut — der Resume zählt `teile/` |
| `Referenzdaten fehlerhaft: …, Zeile N` | im Spreadsheet korrigieren, Schritt erneut |
| `Das Spreadsheet wuerde vorhandene Daten loeschen` | erst `referenz_sync.py --erstbefuellung` |
| `Verhältnis 0.29 -> Durchgang verworfen` | passiert; der Chunk wird wiederholt |
| `Keine Eingabe moeglich` bei `neu` | denselben Aufruf mit `--ja` wiederholen |
| `Keine Google-Anmeldung — die ID und die Freigabe sind nicht das Problem` | `colab_start.sheets_anmelden()` in einer Zelle, dann den Schritt erneut |
| `Rahmenmarker »#« kommt im Text nicht vor` | kein Fehler, aber lesen: Abschnitt 5a |
| `N nachgebaute Quellchunks, aber der Lauf hatte M` | `input.txt`, `ebenen.json` oder `zitate.json` haben sich seit dem Lauf geändert — zurücksetzen oder den Lauf wiederholen |
| „Nicht geprüft: N Chunks" im Screening | `annotation.py --nur screening` erneut |
| `… hat keine Stapel-API` | `--stapel` gilt nur für Anthropic-Modelle |

Ergebnisse löscht **nur** `pipeline.py neu`, und es zeigt vorher die Liste.
Drei Abstufungen: `--nur-test` räumt die Testauszüge, `--nur-teile`
zusätzlich die Chunks des Volllaufs, ohne Argument alles bis auf Quelltext,
Konfiguration und Referenzdateien.

---

## Der ganze Ablauf auf einen Blick

```
Zelle 0            Code laden, Stand prüfen
Zelle 2            einrichten und starten
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
