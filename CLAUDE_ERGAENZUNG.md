# Ergänzung zu CLAUDE.md — API/Colab-Ära

**Einarbeitungshinweise (für Paket 0 des Arbeitsauftrags):**
1. Im Kopfabsatz von `CLAUDE.md` den Satz „Aktuell Niederländisch → Deutsch,
   lokal über Ollama" ersetzen durch: „Aktuell Niederländisch → Deutsch über
   API-Backends (Anthropic, Google), Betrieb in Google Colab mit Datenhaltung
   in Google Drive; Ollama bleibt als Rückfallpfad erhalten."
2. Den Abschnitt „Abhängigkeiten" durch die gleichnamige Fassung unten
   ersetzen.
3. Die übrigen Abschnitte unten neu einfügen (Position: nach „Sprache").
4. Diese Datei danach löschen.

---

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

## Abhängigkeiten (ersetzt den bisherigen Abschnitt)

Basis bleibt `requests` — beide APIs werden direkt angesprochen, bewusst
ohne litellm (Begründung in `ENTSCHEIDUNGEN.md`). In Colab vorinstallierte
Bibliotheken (`google.colab`, `gspread`, `google-auth`) dürfen genutzt
werden, aber nur hinter Laufzeit-Erkennung mit Fallback: Die Pipeline muss
auf einem nackten VPS mit nur `requests` lauffähig bleiben. Kein
`pip install` im Normalbetrieb.

## Kalibrierung gilt je Modell-Ära

`revision_pass`, `lektorat_passes` und `chunk_words` wurden unter Mistral
gemessen und sind unter Opus 5 **offen**, bis der Testlauf sie neu
entschieden hat. Alte Messwerte nicht als Naturgesetz behandeln, neue
Entscheidungen mit Messung in `ENTSCHEIDUNGEN.md` nachtragen.
