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
- **Verstellbar sind `chunk_words`, `context_words` und `effort_<rolle>`.** Die
  Temperatur-Schlüssel wirken seit der API-Umstellung nur noch auf dem
  Ollama-Rückfallpfad — `claude-opus-5` hat `temperature`/`top_p`/`top_k`
  entfernt und antwortet darauf mit HTTP 400. `repeat_penalty` über 1,0 wäre
  bei diesem Text ohnehin schädlich.
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

- **Keine der beiden APIs bekommt Sampling-Parameter.** Gemini ignoriert
  `temperature`/`top_p`/`top_k` bei 3.6 Flash und wird künftig mit HTTP 400
  antworten; `claude-opus-5` hat sie bereits entfernt und antwortet mit
  HTTP 400. Der Selbsttest prüft beide Payloads darauf. Die Tiefe steuert
  `effort_<rolle>` (deutsch in `projekt.json`, Abbildung auf `low`…`max` in
  `gemeinsam.EFFORT`).
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

- Einstieg ist `colab_runner.ipynb`; die Logik der Zellen steht in
  `colab_start.py`, damit sie testbar und diffbar bleibt. Zellen selbst
  bleiben kurz.
- **Code- und Datenverzeichnis sind getrennt.** `pipeline.py` ruft
  Schrittskripte über `CODE` auf, nie relativ zum Arbeitsverzeichnis —
  sonst findet der Lauf seine eigenen Skripte nicht. Datenpfade bleiben
  relativ (Drive), Vorlagenpfade laufen über `__file__`.
- `pipeline.py run --hg` ist in Colab gesperrt; der Lauf gehört in den
  Vordergrund der Zelle. Die Chunk-Fortschrittsausgabe verhindert nebenbei
  die Idle-Einstufung — nicht „aufräumen". PID-Datei nur außerhalb Colab.
- Eine vorhandene `projekt.json` im Projektordner wird nie überschrieben;
  beim Erstlauf kopiert der Runner die aus dem Repo und sagt es.
- Colab-Erkennung zentral in `gemeinsam.py`, nirgendwo sonst.
- Secrets: `ANTHROPIC_API_KEY` und `GoogleKI` (intern `GEMINI_API_KEY`)
  über `google.colab.userdata`; außerhalb Colab normale
  Umgebungsvariablen. Keys erscheinen nie in Dateien, Logs oder Berichten.

## Vorbereitung erzeugt die Referenzdateien

`vorbereitung.py` läuft als Pipelineschritt zwischen `konkordanz` und dem
Testlauf und erzeugt aus dem Analysepaket Glossar, Personen, Figurenblatt,
Anrede, Leitmotive, `stilprofil.json`, `kapitel.json` und einen Entwurf von
`anweisungen.md`. Danach hält die Pipeline bei `PAUSE_review`.

Drei Dinge, die nicht „aufgeräumt" werden dürfen:

- **Je Lieferung ein eigener Aufruf.** Die Befunde stehen im System-Prompt und
  sind ab dem zweiten Aufruf zwischengespeichert; acht kleine Aufrufe kosten
  weniger als einer mit acht Dateien, und jede Lieferung ist einzeln prüfbar
  und über `--nur <name>` einzeln nachziehbar.
- **Vorhandene Dateien werden nie überschrieben.** Hat die Zieldatei Inhalt,
  geht die Lieferung nach `<datei>.neu` — wie in `konkordanz.py`. Für
  `anweisungen.md` gilt dasselbe über `anweisungen_vorschlag.md`.
- **Die Formprüfung je Lieferung ist die Frage, die der Leser stellt.** Ein
  Vorschlag in falscher Form wird gar nicht erst geschrieben, statt später
  stillschweigend übersprungen zu werden.

`stilprofil.json` geht als eigener Baustein in den System-Prompt der
Übersetzung (gilt fürs ganze Buch, deshalb dort und nicht im User-Prompt —
sonst zerfällt das zwischengespeicherte Präfix). Die Kapitelzeile des
aktuellen Chunks steht im User-Prompt; die Schlüssel von `kapitel.json` sind
Überschriften **im Wortlaut der Quelle**, und das laufende Kapitel wirkt bis
zur nächsten Überschrift fort.

## Referenzdaten: Sheets sind die Quelle, JSONs sind Artefakte

Bei gesetzter `sheets_id` werden Glossar, Personen, Figurenblatt, Anrede,
Leitmotive, Kapitel und die Zitat-Review-Liste im Google-Spreadsheet gepflegt;
`referenz_sync` erzeugt daraus die JSONs mit zeilengenauer Validierung,
bevor Modellkosten entstehen. Die JSONs von Hand zu editieren ist im
Sheets-Betrieb sinnlos — sie werden überschrieben. Ohne `sheets_id` gilt
das alte JSON-Direktverhalten (Rückfallpfad, nicht entfernen).

**Zwei Ausnahmen.** `stilprofil.json` hat kein Tab und bekommt keines: Es ist
kein Datensatz, sondern ein halbes Dutzend benannter Felder plus die
verschachtelte `perspektive`. In eine Tabelle gepresst wäre es unlesbar und
fehleranfällig — es bleibt eine Datei und wird von Hand gepflegt. Und Tabs in
`referenz_sync.OPTIONAL` dürfen in einem älteren Spreadsheet **fehlen**; dann
bleibt die JSON-Datei die Quelle, statt dass jeder Schritt abbricht. Ohne das
hätte ein nachträglich ergänzter Tab jede bestehende Einrichtung lahmgelegt.

## Zitate: nichts ohne Freigabe

`zitatrecherche` schlägt vor, der Mensch gibt frei
(`freigegeben = ja` in `zitate_review.md` oder im Tab `ZitateReview`; bei
gesetzter `sheets_id` schreibt der Schritt den Tab und liest ihn beim
nächsten Aufruf zurück). Der
Schritt füllt `vorschlag_de` und die Quellenangaben, **nie `original_deutsch`**
— dieses eine Feld setzt nur `freigabe_einlesen()`, und nur nach Freigabe.
Nicht-niederländische Zitate bleiben im Original (`original_belassen`) und
brauchen keine Freigabe. Automatische Übernahme ist ausdrücklich verworfen — Abdruckrechte etablierter Übersetzungen und der
Grundsatz „lieber markierte Lücke als erfundener Wortlaut". Eingesetzte
Zitate bleiben vom Lektorat ausgenommen.

## Rahmenwechsel (`rahmen_marker`)

An jeder Marker-Zeile (Standard `#`): harte Chunkgrenze, Rückschau-Reset,
Ebenen-Kennzeichnung im User-Prompt aus `stilprofil.json`. Wer Chunking
anfasst, hält diese Regel und den zugehörigen Selbsttestfall am Leben.
Grund: Tempus und Person der einen Erzählebene dürfen nicht in die andere
bluten.

## Annotation und Screening fassen den Text nicht an

`annotation.py` läuft nach dem Lektorat und liefert zwei Berichte: eine Zeile
Begründung je substanzieller Änderung (`begruendungen.json`, erscheint als
Spalte in `bericht.html`) und ein Screening über das ganze Buch
(`screening_review.md`).

**Der Schritt kann nicht editieren, nicht nur „soll nicht":** Jeder
Schreibzugriff geht durch `annotation.schreiben()`, und die Funktion kennt
genau zwei erlaubte Ziele. Wer das aufweicht, macht aus einem Bericht einen
dritten Editierpass — und jeder Pass glättet.

## Kosten sind Teil des Ergebnisses

Jeder API-Aufruf meldet seine Token-Usage; `manifest.json` summiert je
Rolle, der Preflight schätzt vor dem Volllauf. Neue modellrufende Schritte
ohne Usage-Erfassung gelten als unfertig.

## Kalibrierung gilt je Modell-Ära

`revision_pass`, `lektorat_passes` und `chunk_words` sind unter Opus 5
gemessen und entschieden — die Zahlen stehen in `ENTSCHEIDUNGEN.md` unter
„Gemessen unter Opus 5". Kurzfassung: Revision bleibt an (99 % substanzielle
Änderungen), Lektoratsfolge bleibt (86 % Wort und Wendung), `chunk_words`
bleibt bei 800 (Fremdurteil 3:1), Fable 5 verworfen (kein Vorteil bei
2,6-fachem Preis).

**Die Werte gelten für 1919 und für diese Modellgeneration**, nicht als
Naturgesetz. Die beste Chunkgröße hängt vom Text ab; die Variante bleibt
deshalb in `projekt.json` und wird bei jedem Buch neu gemessen. Neue
Entscheidungen mit Messung nachtragen.

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
vorher. In Colab läuft jeder Schritt als Unterprozess ohne Terminal; die
Rückfrage wandert dort auf ein ausdrückliches `--ja`. Ohne Bestätigung wird
die Liste gezeigt und **nichts** angefasst — der Schritt endet mit
Rückgabewert 1, nicht mit einem stillen Erfolg. Bitte keine `rm`-Befehle in Dokumentation oder Skripte einbauen. Der
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
