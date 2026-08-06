# Projektkontext

Chunkweise Übersetzung buchlanger literarischer Texte mit einem Sprachmodell.
Aktuell Niederländisch → Deutsch über API-Backends (Anthropic, Google), Betrieb
in Google Colab mit Datenhaltung in Google Drive. Ein zweiter Satz für
Deutsch → Englisch existiert separat.

Einstieg ist immer `pipeline.py`. Die Einzelskripte sind aufrufbar, werden im
Normalbetrieb aber vom Orchestrator gestartet.

## Vor jeder Verhaltensänderung: ENTSCHEIDUNGEN.md lesen

Mehrere Entscheidungen sehen falsch aus, bis man die Begründung kennt. Die
wichtigsten:

- **Stillektorat läuft VOR dem Korrektorat**, nicht danach. Das weicht von der
  Verlagsreihenfolge ab und ist Absicht.
- **`gross` wird zu `groß` korrigiert, `Gross` nicht.** Schreibungsabhängig,
  weil großgeschrieben ein Nachname sein kann.
- **Verstellbar sind `chunk_words`, `context_words`, `context_words_voraus`
  und `effort_<rolle>`.**
  Sampling-Parameter gibt es nicht mehr: `claude-opus-5` hat
  `temperature`/`top_p`/`top_k` entfernt und antwortet darauf mit HTTP 400,
  Gemini ignoriert sie. Mit dem Rückzug des Ollama-Pfads sind die
  Temperatur-Schlüssel entfallen.
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

Ein Buch kann eine abweichende Modellwahl beanspruchen: Die betroffenen
Schlüssel kommen in `technik_ausnahmen`, dann lässt `pipeline.py technik` sie
in Ruhe und meldet sie nur.

Die Modellbelegung je Rolle steht in `projekt.json` (`modell_<rolle>`,
`effort_<rolle>` für alle zehn Rollen in `gemeinsam.ROLLEN`). Das Backend
ergibt sich aus dem Modellnamen. Bitte keine Modellnamen hartkodieren.

**Die Empfehlung samt Begründung steht in `gemeinsam.EMPFEHLUNG`,
nebeneinandergestellt von `pipeline.py modelle`.** Wer die Belegung ändert,
liest die Begründung genau dann, wenn es darauf ankommt — deshalb steht sie
im Code und nicht in einer Doku. Abweichen ist vorgesehen; damit
`pipeline.py technik` die Abweichung stehen lässt, gehört der Schlüssel in
`technik_ausnahmen`. `effort` wirkt nur bei Anthropic-Modellen; die
Übersicht sagt das dazu, statt jemanden daran drehen zu lassen.

`annotation` war bis August 2026 **eine** Rolle für zwei verschiedene
Arbeiten. Sie ist getrennt in `begruendung` (Massenware, eine Zeile je
Änderung) und `screening` (die eigentliche Qualitätsprüfung gegen das
Original). Ein Modell für beides hieß: entweder zahlt man den Preis der
Prüfung für die Massenware, oder man prüft mit dem Modell der Massenware.

Ein entfallener Schlüssel bleibt in einer bestehenden `projekt.json` stehen
und wirkt nicht mehr — `preflight.py` meldet ihn (`ENTFALLEN`), weil das
sonst niemand bemerkt.

Zwei Eigenheiten, die nicht „repariert" werden dürfen:

- **Keine der beiden APIs bekommt Sampling-Parameter.** Gemini ignoriert
  `temperature`/`top_p`/`top_k` bei 3.6 Flash und wird künftig mit HTTP 400
  antworten; `claude-opus-5` hat sie bereits entfernt und antwortet mit
  HTTP 400. Der Selbsttest prüft beide Payloads darauf. Die Tiefe steuert
  `effort_<rolle>` (deutsch in `projekt.json`, Abbildung auf `low`…`max` in
  `gemeinsam.EFFORT`).
- **Eine Ablehnung des Sicherheitsklassifikators bricht den Lauf nicht ab.**
  `fallbacks` lässt ein Ersatzmodell antworten; gebucht wird unter dem
  Modell, das wirklich geantwortet hat, und damit steht die Stelle als eigene
  Zeile in der Kostenübersicht. Der Beleg für einen Rückfall ist
  `usage.iterations`, **nie** der Modellname — ein Alias löst auf einen
  datierten Namen auf und wäre jedes Mal ein Fehlalarm. Achtung Paket G: Die
  Stapel-API nimmt `fallbacks` nicht an.
  **Der serverseitige Weg ist eine Beta und kann fehlen.** Trägt
  `fallback_modelle` eine **Liste** statt `"default"`, wiederholt der Lauf
  die abgelehnte Anfrage selbst (`eigene_rueckfaelle`) — ohne jede Beta, und
  nur dann, wenn der serverseitige Weg nicht schon läuft. `"default"` lässt
  sich nicht nachbauen: Welches Ersatzmodell zu welcher Kategorie passt,
  weiß nur der Anbieter.
- **Der System-Prompt trägt einen Cache-Marker** (Anthropic
  `cache_control`). Wer Prompt-Bausteine umsortiert, zerstört unbemerkt die
  Cache-Trefferquote — identische Präfixe sind Geld. Die Lebensdauer steht in
  `cache_ttl` (Standard `1h`) und ist eine Versicherung gegen längere Pausen
  zwischen zwei Chunks, keine Kostenmaßnahme: Die gemessene Trefferquote lag
  bereits bei 96 %. Schreiben mit einer Stunde kostet doppelt; `kosten_dollar`
  rechnet die Anteile getrennt. Lehnt der Anbieter die Lebensdauer ab, läuft
  der Lauf ohne sie weiter, statt abzubrechen.

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
- **Ein Selbsttest über eine Colab-Verzweigung stellt beide Äste
  ausdrücklich ein** (`G.ist_colab = lambda: True` / `False`, mit
  `finally`). Gegen die ambiente Umgebung geprüft, läuft er auf dem
  Entwicklungsrechner durch und schlägt in Colab fehl — die eine
  Umgebung, in der er zählt. Ein Ast, den kein Test sieht, ist
  ungeprüft.
- Secrets: `ANTHROPIC_API_KEY` und `GoogleKI` (intern `GEMINI_API_KEY`)
  über `google.colab.userdata`; außerhalb Colab normale
  Umgebungsvariablen. Keys erscheinen nie in Dateien, Logs oder Berichten.

## Vorbereitung erzeugt die Referenzdateien

`vorbereitung.py` läuft als Pipelineschritt zwischen `konkordanz` und dem
Testlauf und erzeugt aus dem Analysepaket Glossar, Personen, Figurenblatt,
Anrede, Leitmotive, `stilprofil.json`, `kapitel.json` und einen Entwurf von
`anweisungen.md`. Dazu `ebenen.json` — die eine Lieferung, die den Quelltext
liest statt der Befunde, und deshalb einen eigenen Aufruf mit eigenem Prompt
bekommt (Rolle `ebenen`). Danach hält die Pipeline bei `PAUSE_review`.

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

**Der Tab `Modelle` ist die eine Ausnahme in der Richtung.** Er wird
geschrieben (`referenz_sync.py --modelle`) und **nie zurückgelesen**:
Modellnamen sind Code-Daten, sie wandern mit dem Repo (`gemeinsam.TECHNIK`),
Referenzdaten wandern mit dem Buch. Ein zurückgelesener Tab machte die
Modellwahl zur dritten Quelle neben Repo- und Projekt-`projekt.json`.
Sichtbar im Spreadsheet, geändert in `projekt.json`.

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

**`belege` ist etwas anderes als `quelle`.** Die Belege kommen aus den
Zitatmarken der Websuche — URL, Titel, belegter Wortlaut, abgerufen.
`uebersetzer` und `quelle` schreibt das Modell. Wer freigibt, soll den
Unterschied sehen; deshalb stehen sie getrennt. Die Spalten der Review-Liste
werden über `SPALTEN` gebaut **und über `SPALTEN.index(...)` wieder gelesen**
— eine feste Position hat bei der ersten neuen Spalte still die falsche
Zelle getroffen, und `freigegeben` ist die eine Spalte, bei der das einen
ungeprüften Wortlaut in den Text setzt.

## Kontext in beide Richtungen

Ein Chunk sieht zurück (`context_words`, Quelle und eigene Fassung) **und nach
vorn** (`context_words_voraus`, der Anfang des nächsten Chunks). Drei Regeln,
die keine Details sind:

- Der Ausblick **endet an der Ebenenfuge** — dort beginnt eine andere Ebene,
  und ihr Anfang wäre eine Irreführung. Stapelfugen (Paket G) sind keine
  Ebenenfugen; dort läuft er weiter.
- Er steht **vor** dem Auftrag im Prompt. Was zuletzt dasteht, liest ein Modell
  als das, was zu tun ist.
- Er schneidet an der Satzgrenze (`G.anfangswoerter`).

Die Rückschau steht auch im **Revisionsbody** — sonst glättet Pass 2 die
Anschlüsse weg, die Pass 1 hergestellt hat. `rueckschau_quelle` schaltet um,
ob sie aus der Revision oder dem Entwurf kommt; gemessen ist das noch nicht.

`figuren_nachhall` hält eine einmal genannte Figur drei Chunks im
Personenblock, gekennzeichnet als »zuletzt erwähnt«. Zurückgesetzt **nur an
Ebenenfugen**.

Eine verschobene Absatzzahl ist kein Schönheitsfehler: Leseausgabe,
Zitateinsatz und Tempusmessung hängen an der Absatzzuordnung. Bricht die
Revision sie, wird die Revision verworfen; bricht der Entwurf sie, wird der
Chunk wiederholt.

## Erzählebenen: `ebenen.json` zuerst, `rahmen_marker` als Rückfall

An jeder Fuge: harte Chunkgrenze, Rückschau-Reset, Ebenen-Kennzeichnung im
User-Prompt aus `stilprofil.json`. Grund: Tempus und Person der einen
Erzählebene dürfen nicht in die andere bluten.

**Woher die Fugen kommen, hat sich im August 2026 geändert.** Der Marker
setzt voraus, dass der Autor die Wechsel auszeichnet. Beim Buch 1919 tat er
das nicht: fünf Ebenen im Stilprofil, **eine** Gruppe über 147 Chunks — die
Rückschau lief über jeden Wechsel hinweg, und die buchweite Perfektquote
konnte das nicht sehen. Deshalb liest `uebersetzung.ebenengruppen` zuerst
`ebenen.json`; der Marker bleibt der Rückfall. Zwei Quellen gleichzeitig
wären eine zu viel.

- `ebenen.json` ist eine **Liste** — die Reihenfolge ist die Information.
  Sie wird über `G.ebenen_lesen()` gelesen, **nie** über `lade_json`: das
  liefert für Nicht-Objekte still `{}`, und die Datei wäre immer leer.
- `beginn` sind die ersten Wörter des Absatzes **im Wortlaut der Quelle**
  (wie die Überschriften in `kapitel.json`). Ein `beginn`, der nicht
  vorkommt, wird gemeldet und die Datei nicht geschrieben — die Fuge säße
  sonst am falschen Absatz.
- `qa.py` misst das Tempus **je Ebene** und warnt, wenn die Ebenen sich
  nicht unterscheiden. `preflight` meldet den Fall 1919.

Wer Chunking anfasst, hält diese Regel und die zugehörigen Selbsttestfälle
am Leben.

## Die Chunkeinteilung kommt aus `gemeinsam.quellchunks`

Der Lauf, die Leseausgabe und das Screening stellen Quelle und Fassung
nebeneinander und müssen deshalb **dieselben** Chunks bekommen. Sie hatten
drei Nachbauten, die gleich aussahen — bis Paket C den Lauf auf `ebenen.json`
umstellte und die beiden Leser weiter nur den Rahmenmarker lasen. Danach stand
überall der falsche Absatz neben dem falschen, und keine Spalte sah für sich
falsch aus.

`rahmen_gruppen` steht deshalb nur noch in `gemeinsam`; ein Selbsttest
verbietet den direkten Aufruf in jedem anderen Skript. Die beiden Leser gehen
über `quellchunks_wie_lauf()`: Sie nimmt `chunk_words` aus
`uebersetzung_state.json` (nicht aus der aktuellen Konfiguration) und prüft
die Chunkzahl gegen `total`. Weicht sie ab, **bricht der Schritt ab** —
`ChunksWeichenAb`. Eine verschobene, aber ausgelieferte Leseausgabe ist
schlimmer als gar keine.

## Annotation und Screening fassen den Text nicht an

`annotation.py` läuft nach dem Lektorat und liefert zwei Berichte: eine Zeile
Begründung je substanzieller Änderung (`begruendungen.json`, erscheint als
Spalte in `bericht.html`) und ein Screening über das ganze Buch
(`screening_review.md`).

**Der Schritt kann nicht editieren, nicht nur „soll nicht":** Jeder
Schreibzugriff geht durch `annotation.schreiben()`, und die Funktion kennt
genau zwei erlaubte Ziele. Der einzige weitere Schreibweg ist
`annotation.teil_schreiben()`, und der führt ausschließlich nach
`teile/screening/`. Wer das aufweicht, macht aus einem Bericht einen dritten
Editierpass — und jeder Pass glättet.

**Das Screening verdichtet, merkt sich und meldet Lücken.** Gleichlautende
Meldungen fallen im Bericht in eine Zeile (`muster()`); die bisherigen Muster
gehen als Baustein in den **User-Prompt**, nie in den System-Prompt — der ist
das zwischengespeicherte Präfix. Ein gescheitertes Bündel wird nicht mehr
verschluckt: Die Chunknummern stehen im Bericht, und die fertigen Bündel
liegen in `teile/screening/`, sodass ein erneuter Aufruf nur das Fehlende
nachholt.

## Stapelbetrieb: Wellen über Ketten

`uebersetzung.py --stapel` läuft über die Stapel-API — halber Preis, aber ein
Chunk sieht die Fassung des vorigen **nur innerhalb seiner Kette**. Deshalb
Ketten: seriell innen, nebeneinander außen; je Welle ein Chunk jeder Kette in
einem Stapel.

- **Geschnitten wird zuerst an den Ebenenfugen** — dort setzt die Rückschau
  ohnehin zurück, diese Schnitte kosten nichts. Erst `kette_max` erzwingt
  weitere, und jeder davon ist eine Naht ohne Rückschau. Standard ist `0`.
- **Der Quellschluss steht auch am Kettenanfang** (Original, hängt an keiner
  Übersetzung) — **außer an der Ebenenfuge**, dort wäre er eine Irreführung.
- **`stapel_payload()` ist ein Filter über `payload()`, kein zweiter Bauer.**
  `STAPEL_VERBOTEN` nennt, was die API ablehnt; `fallbacks` ist dabei.
- **Was der Stapel nicht liefert, holt der synchrone Weg** — und dort greift
  der Ablehnungsrückfall dann doch.
- Gebucht wird unter `…/stapel` mit `STAPEL_FAKTOR`; eine gemeinsame Zeile
  wären Token zu zwei Preisen.

`pipeline.py wellen` zeigt den Handel vor dem Lauf, `bewertung.py --fugen`
misst ihn danach.

## Kosten sind Teil des Ergebnisses

Jeder API-Aufruf meldet seine Token-Usage; `manifest.json` bucht je
**Lauf, Rolle und Modell** — nicht je Rolle allein, sonst etikettiert ein
Testlauf mit anderem Modell die ganze Rolle um (das hat den Lauf 1919 um 57 %
zu teuer ausgewiesen). Testläufe erscheinen getrennt vom Buchpreis. Der
Preis kommt aus genau einer Formel (`gemeinsam.kosten_dollar`); der Preflight
schätzt vor dem Volllauf. Die Preise hält `tarife.py`
gegen die Preisseiten — übernommen wird nur ein eindeutiges Paar, sonst bleibt
der hinterlegte Wert (Begründung in `ENTSCHEIDUNGEN.md`). Neue modellrufende Schritte
ohne Usage-Erfassung gelten als unfertig.

Das gilt auch für Werkzeuge, die kein Modell sind: Die serverseitige Websuche
kostet je Aufruf, nicht je Token, und wird als `suchen` gebucht
(`gemeinsam.SUCHE_DOLLAR`). Ohne eigenes Feld wäre die Zitatrecherche der
einzige Schritt, dessen Rechnung nicht aufgeht.

## Was der Testlauf messen kann

Drei Auszüge: Erzählung, Dialog und die **Fallenpassage** — die Stelle mit der
höchsten Dichte an falschen Freunden, Diminutiven, `zou` und
Verlaufsformen. Die ersten beiden messen, ob der Text als deutsche Prosa
besteht; der dritte, ob die Warnungen aus `block_fallen` ankommen. Er
überschneidet die anderen nicht. `teile.json` hält die Absatzzahl je Auszug —
ohne sie schneidet `bewertung` bei der Hälfte und vergleicht Erzählung gegen
Dialog.

Eine **Variante** darf jeden Schalter aus `gemeinsam.VARIANTENSCHALTER`
tragen, nicht nur `chunk_words` und Modellnamen. Die Liste ist bewusst
geschlossen: Ein Tippfehler erzeugte sonst still eine Einstellung, die nichts
tut, und der Vergleich liefe durch. `preflight` meldet unbekannte Schlüssel
vor dem ersten Modellaufruf.

`lektorat.py --test --variante X` und `bewertung.py --lektorat --variante X`
ziehen die Variante bis ins Lektorat durch — die Frage »braucht das
Korrektorat wirklich Opus« ist eine Lektoratsfrage.

`bewertung.py --fugen` beurteilt die **Nähte** zwischen Chunks und fragt
ausschließlich nach dem Übergang. Das ist die Zahl hinter `kette_max` im
Stapelbetrieb: Kürzere Ketten heißen mehr Fugen.

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

Basis bleibt `requests`; beide APIs lassen sich damit direkt ansprechen, und
der Pfad bleibt als Rückfall bestehen. Ollama ist im August 2026 entfernt
worden — ein Rückfallpfad, den kein Selbsttest prüfen kann, ist keiner. In Colab vorinstallierte
Bibliotheken (`google.colab`, `gspread`, `google-auth`) dürfen genutzt
werden, aber nur hinter Laufzeit-Erkennung mit Fallback: Die Pipeline muss
auf einem nackten VPS mit nur `requests` lauffähig bleiben. Kein
`pip install` im Normalbetrieb — mit genau einer benannten Ausnahme:
`anthropic`, die SDK des Anbieters, auf Hauptversion festgelegt, in der
Einrichtungszelle des Runners. Fehlt der Import, trägt der `requests`-Pfad
weiter. Die Ablehnung von litellm bleibt bestehen (Begründung in
`ENTSCHEIDUNGEN.md`).

**Strukturierte Ausgaben nur, wo die Form ausdrückbar ist.** `G.chat(...,
schema=…)` legt ein JSON-Schema in `output_config.format`. Das Subset verlangt
`additionalProperties: false` und kann damit **keine offenen Abbildungen**
ausdrücken — genau das sind die Vorbereitungslieferungen (Wort → Wort). Benutzt
wird es deshalb in `zitatrecherche.py`, wo der Befund feste Schlüssel hat.
Gemini bekommt nie ein Schema (anderer Dialekt, HTTP 400); `schema_maengel()`
meldet vor dem Lauf, was der Anbieter ablehnen würde. Der Parser bleibt überall
— ein Schema ist eine Zusicherung, keine Ersetzung.

**Beide Transportwege teilen sich `payload()` und `antwort_lesen()`.** Zwei
Wege sind erlaubt, zwei Wahrheiten darüber, was rausgeht, nicht — der
Selbsttest prüft den Payload genau einmal. `sdk_fehler()` behält den
Wortlaut `HTTP <code>`, sonst greift der Rückfall der Cache-Lebensdauer auf
dem SDK-Pfad nicht. `sdk_nutzen: false` erzwingt `requests`.

**Streaming gibt es nur auf dem SDK-Pfad** (`streaming`, Standard an).
`get_final_message()` liefert dieselbe Nachricht wie ein Aufruf ohne Stream
— der Stream ist ein Transportdetail, kein zweiter Payload. Der
`requests`-Pfad bekommt bewusst keines: ein handgeschriebener SSE-Parser
wäre ein Rückfallpfad, den kein Selbsttest prüfen kann.

**Die Fassung der Websuche steht in `projekt.json`** (`websuche_werkzeug`),
nicht im Code — ein Name im Code lässt die Zitatrecherche eines Tages mit
veralteter Suche laufen, ohne dass es auffällt; ein Selbsttest verbietet ihn
außerhalb von `gemeinsam.STANDARD`. Die Suche kostet je Aufruf und wird als
`suchen` gebucht. `pause_turn` wird fortgesetzt, nicht als Formfehler
gelesen.

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

`pipeline.py weiter` gibt die nächste offene Pause frei und läuft weiter — ein
Befehl statt `reset --ab NAME --fertig` plus `run`. Es hakt immer nur eine
Pause ab und **nie** einen fehlgeschlagenen Schritt; `reset` bleibt für das,
was es wirklich kann: einen gelaufenen Schritt wieder öffnen.

Übergroße Chunks werden **gezählt, nicht gekappt** (`chunk_ueberlaengen`,
Marke 1,25 × `chunk_words`). Ein Absatz gehört zusammen, ein geschütztes Zitat
erst recht. Gemeldet werden sie in der Vorabprüfung und beim Chunkbau, weil sie
die Ursache hinter verworfenen Längenverhältnissen sind.

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

## Ein neues Buch, ein neues Sprachpaar

**Buch:** `NEUES_BUCH.md` führt von der Textdatei bis zum Paket. Abschnitt 5a
stellt die eine Frage, die jedes Buch beantworten muss — *wie sind die
Erzählebenen ausgezeichnet?* Der Preflight meldet inzwischen, wenn der
eingestellte `rahmen_marker` im Text nicht vorkommt; die Vorlage
`projekt.json` im Repo nennt jede Einstellung ausdrücklich, damit sich
keine mehr still entscheidet (Selbsttest hält beides fest).

**Sprachpaar:** Kopie mit ausgetauschten Sprachdaten. Was sich unterscheidet,
steht in `SPRACHPAARE.md`; die Reihenfolge der Arbeit beginnt bei der
Fehlerklasse und endet beim Code, nicht umgekehrt.
