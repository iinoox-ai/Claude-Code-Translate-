# Ablaufplan — literarische Übersetzung Niederländisch → Deutsch

Gesteuert über ein einziges Skript. `pipeline.py` kennt den Ablauf, weiß wo er
steht, setzt an der richtigen Stelle fort und löscht nur auf ausdrücklichen
Befehl.

> **Dieser Skriptsatz ist für NL → DE.** Jedes Skript gibt die Sprachrichtung
> in der ersten Zeile aus, `projekt.json` trägt `"sprachpaar": "nl-de"`, und
> der Preflight prüft, ob `input.txt` überhaupt niederländisch ist.

**Zeitbedarf GPU:** ~6,5 h bei 100.000 Wörtern · **Kosten:** ~45 $ auf einer B200
**Prüffenster:** beliebig lang, Instanz auf *Stop* (Cent pro Stunde)

---

## Die fünf Kommandos, die du brauchst

```bash
python3 pipeline.py init         # einmal: Konfiguration anlegen
python3 pipeline.py run --hg     # loslaufen, im Hintergrund
python3 pipeline.py status       # wo stehe ich
python3 pipeline.py log -f       # mitlesen (Strg+C zum Verlassen)
python3 pipeline.py stop         # anhalten
```

`run` macht immer am nächsten offenen Schritt weiter. Bei einem Abbruch —
egal ob Fehler, `stop` oder Instanzneustart — ist derselbe Befehl die Antwort.
**Es gibt kein `rm` im normalen Ablauf.** Das einzige Kommando, das Ergebnisse
löscht, ist `pipeline.py neu`, und es fragt vorher.

---

## Was in dieser Fassung anders ist

**Chunk-Ausgaben liegen einzeln** in `teile/` und werden erst am Ende
zusammengesetzt. Resume zählt Dateien statt einer Zustandsdatei zu vertrauen;
ein einzelner Chunk lässt sich neu rechnen (`uebersetzung.py --chunk 37`).

**`anweisungen.md` hat keine Kommentare in den Abschnitten mehr.** In der
ersten Fassung landeten die Platzhalter-Beispiele wörtlich in den
System-Prompts — das Modell bekam Anweisungen über eine Figur, die es nicht
gibt. Zusätzlich filtert der Loader Kommentare heraus.

**Der Preflight beginnt mit einem Selbsttest**, der jeden Normalisierer und
jeden Prompt auf einer Kunstzeile durchlaufen lässt. Zwei Fehler der ersten
Fassung wären damit sofort aufgefallen.

**Die ß-Ersetzung schützt Homographen.** Vorher wurde `die Masse der Menschen`
zu `die Maße`, `die Busse fuhren` zu `die Buße`. Jetzt schreibungsabhängig:
kleingeschriebenes `gross` wird zu `groß`, großgeschriebenes `Gross` bleibt als
Nachname stehen.

**Der Diminutivzähler zählt richtig.** Vorher galten `sprechen`, `zwischen`,
`Zeichen`, `Kuchen` als Diminutive — zwölf Treffer statt zwei.

**Die Tempusmetrik arbeitet satzweise**, erfasst also die deutsche Verbklammer
(`dass er es gesagt hat`) und produziert keine Falschtreffer mehr.

**Jeder Chunk bekommt einen Fallenblock** mit den falschen Freunden,
Diminutiven und `zou`-Vorkommen, die in *diesem* Abschnitt wirklich stehen —
statt einer Vierundzwanzig-Punkte-Liste im Dauerkontext.

**Epigraph und Attributionszeile** werden gemeinsam ausgeklammert, beim
Zusammensetzen eingefügt und vom Lektorat ausgenommen. Die Qualitätsprüfung
schlägt Alarm, wenn ein Zitat trotzdem verändert wurde.

---

## Schritt 0 — Instanz und Dateien

**Anforderungen:** ≥ 150 GB VRAM auf möglichst wenigen GPUs, ≥ 250 GB Disk.

Im Jupyter-Dateibrowser hochladen: alle `.py`, alle `.md`, `projekt.json` und
das Manuskript als `input.txt`. **Nicht** per Heredoc ins Terminal einfügen.

```bash
cd /workspace
ls -la *.py *.md projekt.json input.txt
ollama pull mistral-medium-3.5:128b-q8_0
python3 pipeline.py init
```

`init` fragt sieben Dinge:

| Frage | Vorgabe |
|---|---|
| Wörtliche Rede | `»Rede«`, innen `›so‹` |
| ß verwenden | ja (bundesdeutsch) |
| Diminutive | auflösen, `-chen` nur bei echter Verkleinerung |
| Erzähltempus | quellnah — Wechsel Präteritum/Perfekt folgen |
| Glossarweg | extern |
| Volltext exportieren | ja |
| Chunkgrößen-Vergleich | ja, 800 gegen 1200 Wörter |

---

## SITZUNG A

```bash
python3 pipeline.py run --hg
python3 pipeline.py status
```

Die Pipeline arbeitet von selbst durch: Selbsttest, Preflight, Konkordanz —
und hält dann an.

```
PAUSE — Glossardateien extern erstellen und hochladen
```

**→ Instanz STOPPEN.** `analysepaket.md` und `briefing_glossar.md`
herunterladen, zusammen hochladen, die sechs Rückgabedateien nach `/workspace`
legen. Instanz starten, dann:

```bash
python3 pipeline.py reset --ab PAUSE_glossar --fertig
python3 pipeline.py run --hg
```

Der Preflight prüft beim nächsten Schritt, dass die Dateien gültiges JSON sind
und das Glossar nicht leer ist — ein stiller Lauf ohne Terminologie ist damit
ausgeschlossen.

Weiter laufen automatisch: Testübersetzung (zwei Auszüge, Erzählung und
Dialog), dieselbe Passage mit 1200 Wörtern je Chunk, Bewertung,
Chunkgrößen-Vergleich, Testlektorat, Qualitätsprüfung, Lektoratsbewertung.

Am Ende der Testübersetzung werden die **Prüfgrenzen kalibriert** — aus den
gemessenen Verhältnissen statt aus einer Faustregel.

```
PAUSE — Berichte prüfen, entscheiden, Dateien einspielen
```

**→ Instanz STOPPEN.**

---

## PRÜFFENSTER — ohne GPU

Herunterladen: `bewertung_uebersetzung.md`, `bewertung_lektorat.md`,
`bewertung_chunkgroesse.md`, die drei Briefings, `test/qa_lektorat.txt`.

### Selbst prüfen

```bash
python3 diffview.py test/lektorat_diff.txt --html test/bericht.html
python3 diffview.py test/lektorat_diff.txt --only Umbau
python3 diffview.py test/lektorat_diff.txt --stats
```

Worauf du bei dieser Sprachrichtung achtest:

- **Diminutive** — die Bewertung nennt die Zahl je 1000 Wörter und die
  häufigsten Treffer. Über 2,0 bei der Politik „auflösen" ist zu viel.
- **`zou`** — als `würde` übersetzt, wo `soll` gemeint war? Das verschiebt die
  Aussageebene ganzer Absätze.
- **Falsche Freunde** — `Meer` statt See, `laufen` statt gehen, `gekocht`
  statt gekauft, `Tafel` statt Tisch.
- **`am …-sein`** und **`es gibt`-Schwemme**.
- **Tempus** — der Perfektanteil steht in der Bewertung. Trägt der Wechsel im
  Deutschen?
- **Chunkgröße** — 800 gegen 1200: Wo sind die Nahtstellen unauffälliger?

### Externe Bewertung

Pakete und Briefings hochladen. Zurück kommen: Empfehlung zu den Durchgängen,
die ausgefüllte `anweisungen.md`, eine angepasste `projekt.json`, und die
endgültige Formulierung der Tempusanweisung — die hängt davon ab, ob dein Text
eine erste oder dritte Person hat.

### Einspielen

```bash
# angepasste Konfiguration einspielen, statt sie zu überschreiben
python3 pipeline.py config projekt_neu.json
```

Der Merge übernimmt nur Schlüssel, die geändert werden dürfen, und schützt
`ratio_min`, `ratio_max`, `ratio_kalibriert` und `sprachpaar` programmatisch.
Was abgelehnt wurde, wird mit Begründung ausgegeben.

`anweisungen.md` und `zitate.json` einfach hochladen. Bei Epigraphen dort
unter `original_deutsch` den deutschen Wortlaut eintragen — bleibt das Feld
leer, setzt die Übersetzung einen markierten Platzhalter und meldet ihn.

**→ Instanz STARTEN.**

```bash
python3 pipeline.py reset --ab PAUSE_pruefung --fertig
python3 pipeline.py run --hg
```

---

## SITZUNG B

Läuft ohne Zutun durch: Vollübersetzung, Qualitätsprüfung mit Notbremse,
Lektorat, Qualitätsprüfung, globale Konsistenzprüfung, Paket.

Die **Notbremse** hält die Kette an, wenn die Übersetzung unvollständig ist,
die Ausgabe fast leer, das Wortverhältnis außerhalb 0,75–1,45 oder mehr als
15 % der Absätze verloren gingen. Warnungen darunter stoppen nichts.

```bash
python3 pipeline.py status     # Chunkzähler und Restzeit
python3 pipeline.py log -f
```

Bei Abbruch: `python3 pipeline.py run --hg`. Jeder Schritt setzt an seinen
vorhandenen Chunk-Dateien fort.

### Einzelne Stelle nachbessern

Ist ein Chunk misslungen, braucht es keinen Gesamtlauf:

```bash
python3 uebersetzung.py --chunk 37
python3 lektorat.py --chunk 12
```

---

## Abschluss

```bash
cat qa_uebersetzung.txt
cat qa_lektorat.txt
cat qa_konsistenz.txt
python3 diffview.py lektorat_diff.txt --html bericht.html
```

`qa_lektorat.txt` enthält vier Prüfungen, die beim Lesen leicht untergehen:

- **Registerkontrolle** — `hab`, `kriegen`, `wegen dem`, `weil` mit
  Verbzweitstellung vor und nach dem Lektorat
- **Tempuskontrolle** — ob der gewollte Wechsel geglättet wurde
- **Diminutivzähler** — ob das Lektorat welche hinzugefügt hat
- **Zitattreue** — ob eingesetzte Originalzitate unangetastet blieben

`qa_konsistenz.txt` prüft über die ganze Buchlänge: Leitmotive auf
Wortlautvarianz (Bericht in `leitmotiv_varianten.txt`), Terminologie auf
Begriffe, die in einem Buchdrittel verschwinden, und näherungsweise die
Anredeformen je Figur.

Zur Anredeprüfung gehört ein Vorbehalt, der auch im Bericht steht: Wer wen
duzt, ist per Muster nicht bestimmbar — dafür müsste bekannt sein, wer in
einer Passage zu wem spricht. Die Prüfung ist ein Näherungsmaß und liefert
Falschmeldungen.

### Herunterladen

```bash
python3 paket.py
```

`ergebnis.tar.gz` im Dateibrowser rechtsklicken → **Download**, auf dem
eigenen Gerät entpacken und prüfen. Erst danach:

```bash
python3 pipeline.py neu
```

Das Kommando listet auf, was es löschen würde, und verlangt die Eingabe `ja`.
`input.txt`, `projekt.json`, `anweisungen.md`, die Glossardateien und alle
`.py` bleiben unangetastet.

**Erst dann die Instanz zerstören.**

---

## Haltepunkte

| Punkt | Instanz | Grund |
|---|---|---|
| `PAUSE_glossar` | **Stop** | Wartezeit auf die Glossardateien |
| `PAUSE_pruefung` | **Stop** | das große Prüffenster |
| nach dem Download | **Destroy** | erst wenn das Archiv geprüft ist |

*Stop* erhält die Platte und kostet nur Speichergebühr. *Destroy* löscht
alles — dann sind 138 GB Modell neu zu ziehen.

---

## Alle Kommandos

| Aktion | Befehl |
|---|---|
| Konfiguration anlegen | `python3 pipeline.py init` |
| Weiterlaufen | `python3 pipeline.py run --hg` |
| Stand ansehen | `python3 pipeline.py status` |
| Log lesen | `python3 pipeline.py log -n 60` |
| Log mitlesen | `python3 pipeline.py log -f` |
| Anhalten | `python3 pipeline.py stop` |
| Schrittliste | `python3 pipeline.py schritte` |
| Konfiguration einspielen | `python3 pipeline.py config datei.json` |
| Schritt wieder öffnen | `python3 pipeline.py reset --ab NAME` |
| Pause als erledigt | `python3 pipeline.py reset --ab NAME --fertig` |
| Chunk-Dateien verwerfen | `python3 pipeline.py neu --nur-teile` |
| Alles verwerfen | `python3 pipeline.py neu` |
| Einzelnen Chunk neu | `python3 uebersetzung.py --chunk N` |
| Nur Selbsttest | `python3 preflight.py --selbsttest` |
| Modell im VRAM? | `ollama ps` — muss `100% GPU` zeigen |

## Wenn etwas schiefgeht

| Symptom | Ursache | Abhilfe |
|---|---|---|
| `projekt.json ist für 'de-en'` | falscher Skriptsatz | NL→DE-Satz hochladen |
| `Text sieht nicht niederländisch aus` | falsche Datei | `input.txt` prüfen |
| Selbsttest schlägt fehl | Skript beim Paste zerstört | über den Editor neu hochladen |
| `401 Unauthorized` | vast.ai-Proxy | `ss -tlnp \| grep ollama`, Port in `projekt.json` |
| Extrem langsam | Modell nicht ganz im VRAM | `ollama ps`, `num_ctx` senken |
| `glossar.json ist leer` | Rückgabedateien fehlen | die sechs Dateien hochladen |
| Notbremse ausgelöst | siehe `qa_uebersetzung.txt` | Ursache beheben, `run` |
| Fingerabdruck geändert | `anweisungen.md` mitten im Lauf geändert | `reset --ab voll` oder bewusst weiterlaufen |
| Diminutivschwemme | Politik greift nicht | `## Übersetzung` schärfen |
| Tempus geglättet | Korrektorat zu eifrig | `## Korrektorat` füllen |
| Zitat verändert | Schutz griff nicht | `zitate.json` prüfen, `lektorat.py --chunk N` |
