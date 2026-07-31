# Projektkontext

Chunkweise Übersetzung buchlanger literarischer Texte mit einem Sprachmodell.
Aktuell Niederländisch → Deutsch über API-Backends (Anthropic, Google), Betrieb
in Google Colab mit Datenhaltung in Google Drive; Ollama bleibt als Rückfallpfad
erhalten. Ein zweiter Satz für Deutsch → Englisch existiert separat.

Einstieg ist immer `pipeline.py`. Die Einzelskripte sind aufrufbar, werden im
Normalbetrieb aber vom Orchestrator gestartet.

## Vor jeder Verhaltensänderung: ENTSCHEIDUNGEN.md lesen

Mehrere Entscheidungen sehen falsch aus, bis man die Begründung kennt. Die
wichtigsten:

- **Stillektorat läuft VOR dem Korrektorat**, nicht danach. Das weicht von der
  Verlagsreihenfolge ab und ist Absicht.
- **`gross` wird zu `groß` korrigiert, `Gross` nicht.** Schreibungsabhängig,
  weil großgeschrieben ein Nachname sein kann.
- **Nur vier Parameter sind verstellbar**: `chunk_words`, `context_words`,
  `temperature_uebersetzung`, `temperature_revision`. `repeat_penalty` über 1,0
  wäre bei diesem Text sogar schädlich.
- **Die lokale Blindbewertung bleibt trotz methodischer Schwäche.** Sie ist das
  dritte Signal, nicht die Entscheidungsgrundlage.
- **Der Anredecheck ist ein Näherungsmaß** und produziert Falschmeldungen. Das
  steht so auch im Bericht.

Am Ende der Datei stehen verworfene Vorschläge mit Begründung. Bitte nicht neu
aufwerfen, ohne sie gelesen zu haben.

## Sprache

Code, Kommentare, Berichte und Prompts sind deutsch. Die englischen Passagen in
den Prompts sind bewusst englisch, wo das Modell darauf besser reagiert — nicht
vereinheitlichen.

Umlaute in Bezeichnern und Kommentaren werden vermieden (`saeubern`,
`schlusswoerter`), in Ausgabetexten für den Benutzer nicht.

## Backends und Modelle

Die Modellbelegung je Rolle steht in `projekt.json`
(`modell_uebersetzung`, `modell_revision`, `modell_stil`,
`modell_korrektorat`, `modell_vorbereitung`, `modell_judge`,
`modell_annotation`, `modell_vergleich`). Das Backend ergibt sich aus dem
Modellnamen. Bitte keine Modellnamen hartkodieren.

Zwei Eigenheiten, die nicht „repariert" werden dürfen:

- **Gemini bekommt keine Sampling-Parameter.** Die API ignoriert
  `temperature`/`top_p`/`top_k` bei 3.6 Flash; künftige Generationen
  antworten mit HTTP 400. Der Selbsttest prüft, dass das Payload sauber ist.
  Die vier verstellbaren Pipeline-Parameter wirken nur auf Anthropic-Seite.
- **Der System-Prompt trägt einen Cache-Marker** (Anthropic
  `cache_control`). Wer Prompt-Bausteine umsortiert, zerstört unbemerkt die
  Cache-Trefferquote — identische Präfixe sind Geld.

Judge-Gewichtung in `bewertung.py`: Diff-Statistik → Gemini-3.1-Pro-Urteil →
Opus-Selbstcheck (nachrangig wegen Selbstpräferenz). Reihenfolge ist
Absicht, Begründung in `ENTSCHEIDUNGEN.md`.

## Colab-Betrieb

Primärbetrieb ist Google Colab: Code kommt per `git pull` in die VM,
gearbeitet wird im Drive-Projektordner (`os.chdir`), jeder Chunk ist damit
sofort dauerhaft. Ein VM-Abbruch ist ein Nicht-Ereignis — der Resume zählt
Dateien in `teile/`.

- `pipeline.py run --hg` ist in Colab gesperrt; der Lauf gehört in den
  Vordergrund der Zelle. Die Chunk-Fortschrittsausgabe verhindert nebenbei
  die Idle-Einstufung — nicht „aufräumen".
- Colab-Erkennung zentral in `gemeinsam.py`, nirgendwo sonst.
- Secrets: `ANTHROPIC_API_KEY` und `GoogleKI` (intern `GEMINI_API_KEY`)
  über `google.colab.userdata`; außerhalb Colab normale
  Umgebungsvariablen. Keys erscheinen nie in Dateien, Logs oder Berichten.

## Referenzdaten: Sheets sind die Quelle, JSONs sind Artefakte

Bei gesetzter `sheets_id` werden Glossar, Personen, Figurenblatt, Anrede,
Leitmotive und die Zitat-Review-Liste im Google-Spreadsheet gepflegt;
`referenz_sync` erzeugt daraus die JSONs mit zeilengenauer Validierung,
bevor Modellkosten entstehen. Die JSONs von Hand zu editieren ist im
Sheets-Betrieb sinnlos — sie werden überschrieben. Ohne `sheets_id` gilt
das alte JSON-Direktverhalten (Rückfallpfad, nicht entfernen).

## Zitate: nichts ohne Freigabe

`zitatrecherche` schlägt vor, der Mensch gibt frei
(`freigegeben = ja` in der Review-Liste). Automatische Übernahme ist
ausdrücklich verworfen — Abdruckrechte etablierter Übersetzungen und der
Grundsatz „lieber markierte Lücke als erfundener Wortlaut". Eingesetzte
Zitate bleiben vom Lektorat ausgenommen.

## Rahmenwechsel (`rahmen_marker`)

An jeder Marker-Zeile (Standard `#`): harte Chunkgrenze, Rückschau-Reset,
Ebenen-Kennzeichnung im User-Prompt aus `stilprofil.json`. Wer Chunking
anfasst, hält diese Regel und den zugehörigen Selbsttestfall am Leben.
Grund: Tempus und Person der einen Erzählebene dürfen nicht in die andere
bluten.

## Kosten sind Teil des Ergebnisses

Jeder API-Aufruf meldet seine Token-Usage; `manifest.json` summiert je
Rolle, der Preflight schätzt vor dem Volllauf. Neue modellrufende Schritte
ohne Usage-Erfassung gelten als unfertig.

## Kalibrierung gilt je Modell-Ära

`revision_pass`, `lektorat_passes` und `chunk_words` wurden unter Mistral
gemessen und sind unter Opus 5 **offen**, bis der Testlauf sie neu
entschieden hat. Alte Messwerte nicht als Naturgesetz behandeln, neue
Entscheidungen mit Messung in `ENTSCHEIDUNGEN.md` nachtragen.

## Nach jeder Änderung an Normalisierern, Metriken oder Prompts

```bash
python3 preflight.py --selbsttest
```

Läuft ohne Modell und ohne GPU. Die zwei schwersten Fehler dieses Projekts
waren Laufzeitfehler, die kein Lesen gefunden hat:

- ein `\u`-Escape in einem Raw-String als `re.subn`-Ersetzung
- eine ß-Ersetzung, die `die Masse der Menschen` zu `die Maße` machte

Beide hätte der Selbsttest in Sekunden gemeldet. Wer eine neue Regel in
`normalisieren()` oder eine neue Metrik einbaut, ergänzt dort einen Testfall.

## Was niemals ins Repo gehört

`input.txt` und alle Referenz-JSONs (`glossar.json`, `personen.json`,
`figurenblatt.json`, `anrede.json`, `leitmotive.json`, `zitate.json`) sind
urheberrechtlich geschütztes Material bzw. projektspezifisch. Die `.gitignore`
deckt das ab — bitte nicht aufweichen.

Ebenso wenig: API-Schlüssel. Die gehören in eine Umgebungsvariable, nicht in
`projekt.json`, weil diese Datei in Exportpakete wandert.

## Abhängigkeiten

Basis bleibt `requests` — beide APIs werden direkt angesprochen, bewusst
ohne litellm (Begründung in `ENTSCHEIDUNGEN.md`). In Colab vorinstallierte
Bibliotheken (`google.colab`, `gspread`, `google-auth`) dürfen genutzt
werden, aber nur hinter Laufzeit-Erkennung mit Fallback: Die Pipeline muss
auf einem nackten VPS mit nur `requests` lauffähig bleiben. Kein
`pip install` im Normalbetrieb.

## Testen ohne GPU

Alles außer den eigentlichen Modellaufrufen lässt sich lokal prüfen:

```bash
python3 preflight.py --selbsttest
python3 -c "import lektorat as L, gemeinsam as G; \
  print(L.normalisieren('Testzeile', dict(G.STANDARD))[0])"
python3 diffview.py beispiel_diff.txt --stats
```

`konkordanz.py` läuft ohne Modell, wenn `glossar_quelle: extern` gesetzt ist —
es erzeugt dann nur das Analysepaket.

## Prompt-Änderungen

**Alles, was in `anweisungen.md` steht, landet wörtlich im System-Prompt.**
Erläuterungen gehören vor den ersten `##` — dort werden sie nie gelesen. Der
Loader filtert HTML-Kommentare, aber verlass dich nicht darauf.

Prompts sind in `uebersetzung.py` und `lektorat.py` als Modulkonstanten
aufgebaut, nicht verteilt. Wer sie umbaut, prüft anschließend mit dem
Selbsttest, dass alle vier weiterhin baubar sind.

## Zustandsverwaltung

Chunk-Ausgaben liegen einzeln in `teile/`. Resume zählt Dateien statt einer
Zustandsdatei zu vertrauen. Das ist Absicht — Zustandsdateien lügen nach einem
Absturz, Verzeichnisinhalte nicht.

`pipeline.py neu` ist das einzige Kommando, das Ergebnisse löscht, und es fragt
vorher. Bitte keine `rm`-Befehle in Dokumentation oder Skripte einbauen. Der
frühere Ablaufplan hatte `rm -f state.json` im Startblock und daneben den
Hinweis „bei Abbruch denselben Befehl erneut" — das kostete Stunden Arbeit.

## Wenn eine Prüfung Falschmeldungen produziert

Erst messen, dann anpassen. Der Diminutivzähler zählte in der ersten Fassung
zwölf statt zwei Treffer, weil `\w{3,}(chen|lein)` auch `sprechen`, `zwischen`
und `Zeichen` matcht. Solche Fehler zeigen sich nur an echtem Text.

Die Ausschlusslisten (`NICHT_DIMINUTIV`, `HOMOGRAPHEN`, `STOPP`) sind die
Stellen, an denen bei einem neuen Text nachgebessert wird — nicht die Regeln
selbst.

## Ein neues Sprachpaar

Kopie mit ausgetauschten Sprachdaten. Was sich unterscheidet, steht in
`SPRACHPAARE.md`; die Reihenfolge der Arbeit beginnt bei der Fehlerklasse und
endet beim Code, nicht umgekehrt.
