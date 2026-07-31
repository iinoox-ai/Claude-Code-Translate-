# Arbeitsauftrag: Migration der NL→DE-Pipeline auf API-Backends und Colab

**Repo:** https://github.com/iinoox-ai/Claude-Code-Translate-
**Stand der Entscheidungen:** 31.07.2026, abgestimmt mit Ian.
**Begleitdokumente:** `CLAUDE_ERGAENZUNG.md` und `ENTSCHEIDUNGEN_ERGAENZUNG.md`
(im selben Lieferpaket) — beide zuerst in die bestehenden Dateien einarbeiten
(Paket 0), damit jede weitere Sitzung den vollen Kontext hat.

---

## 1 · Ziel

Die bestehende Pipeline (Ollama auf vast.ai-GPU-Instanzen) wird auf
API-Backends umgestellt und läuft künftig in **Google Colab** mit
Datenhaltung in **Google Drive**, bedient von einem Android-Tablet.
Der linguistische Kern (Prompts, QA-Regeln, Kalibrierlogik, Stimmschutz)
bleibt unverändert — migriert wird die Transportschicht, ergänzt werden
vier neue Pipelineschritte.

**Kein Neubau.** Die Architektur, die Schrittfolge und die Entscheidungen in
`ENTSCHEIDUNGEN.md` gelten fort, soweit dieser Auftrag nichts anderes sagt.

---

## 2 · Verbindliche Schutzklauseln

Diese Punkte sind nicht verhandelbar und von jedem Arbeitspaket einzuhalten:

1. **Prompt-Wortlaute unverändert.** Die System-Prompts in `uebersetzung.py`
   und `lektorat.py` (inkl. `STIMMSCHUTZ`) werden nicht umformuliert.
   Erlaubt sind ausschließlich die in diesem Auftrag genannten *additiven*
   Bausteine (Stilprofil, Ebenen-Kennzeichnung, Kapitelkontext).
2. **Kalibrierlogik und `GESCHUETZT`-Schlüssel** (`ratio_min`, `ratio_max`,
   `ratio_kalibriert`, `sprachpaar`) bleiben unangetastet; `merge_config`
   ebenso.
3. **Resume-Prinzip bleibt:** Chunk-Dateien in `teile/` zählen, nicht
   Zustandsdateien. Kein Schritt löscht Ergebnisse; nur `pipeline.py neu`
   löscht, und es fragt vorher. Keine `rm`-Befehle in Doku oder Skripten.
4. **Deterministische Normalisierer** inkl. `HOMOGRAPHEN`-Logik unverändert.
5. **Nach jeder Änderung an Normalisierern, Metriken oder Prompts:**
   `python3 preflight.py --selbsttest`. Neue Metriken bekommen dort einen
   Testfall.
6. **`.gitignore` nicht aufweichen.** `input.txt`, alle Referenz-JSONs und
   jegliche Schlüssel bleiben repo-frei. API-Keys ausschließlich über
   Umgebungsvariablen.
7. **Abhängigkeiten:** Basis bleibt `requests`. In Colab vorinstallierte
   Bibliotheken (`google.colab`, `gspread`, `google-auth`) dürfen genutzt
   werden, aber nur hinter Laufzeit-Erkennung mit Fallback — die Pipeline
   muss ohne sie lauffähig bleiben (VPS-Rückfallpfad). Kein `pip install`
   im Normalbetrieb.
8. **Sprache:** Code, Kommentare, Berichte deutsch; keine Umlaute in
   Bezeichnern; bewusst englische Prompt-Passagen nicht vereinheitlichen.
9. **Git:** kleine, thematische Commits je Arbeitspaket mit deutscher
   Commit-Message. **Kein `git push` ohne ausdrückliche Freigabe von Ian.**

---

## 3 · Zielarchitektur

### 3.1 Modellbelegung (entschieden, nicht neu diskutieren)

| Rolle | Modell | Anbieter | Bemerkung |
|---|---|---|---|
| Übersetzung (Pass 1) | `claude-opus-5` | Anthropic | Effort hoch (im Test kalibrieren) |
| Revision (Pass 2) | `claude-opus-5` | Anthropic | Aktivierung entscheidet der Testlauf |
| Stillektorat | `claude-opus-5` | Anthropic | |
| Korrektorat | `claude-opus-5` | Anthropic | Aktivierung entscheidet der Testlauf |
| Vorbereitung (Glossar etc.) | `claude-opus-5` | Anthropic | ersetzt den bisherigen externen Handschritt |
| Zitatrecherche | `claude-opus-5` + Websuche-Tool | Anthropic | serverseitiges `web_search`-Tool |
| Judge: Urteile (Testphasen, Blindvergleiche) | `gemini-3.1-pro` | Google | wenige Aufrufe, hohe Konsequenz |
| Judge: Selbstcheck Treue | `claude-opus-5` | Anthropic | eigenes Prompt; Gewichtung siehe 3.2 |
| Annotation & Screening | `gemini-3.6-flash` | Google | hohes Volumen, niedriger Effort |
| Modellvergleich (einmalig im Test) | `claude-fable-5` | Anthropic | als dritte Variante, siehe Paket 5 |

Modell-IDs und die genaue Syntax des Effort-Parameters bei Opus 5 **vor
Implementierung gegen die aktuelle Anbieterdokumentation verifizieren**
(docs.claude.com bzw. ai.google.dev) — nicht aus diesem Dokument abschreiben.

### 3.2 Judge-Gewichtung

Entscheidungsgrundlage in `bewertung.py` bleibt dreistufig, neu belegt:
(1) Diff-Statistik (belastbar), (2) Fremdurteil Gemini 3.1 Pro (primäres
Modellsignal), (3) Opus-Selbstcheck (Treue gegen das Original; wegen
Selbstpräferenz nachrangig, so kennzeichnen wie bisher die lokale
Blindbewertung). Die vorhandene Tauschlogik (A/B randomisiert) übernehmen.

### 3.3 Konfigurationsschema (`projekt.json`, additiv)

```
"backend_standard": "anthropic",
"modell_uebersetzung":  "claude-opus-5",
"modell_revision":      "claude-opus-5",
"modell_stil":          "claude-opus-5",
"modell_korrektorat":   "claude-opus-5",
"modell_vorbereitung":  "claude-opus-5",
"modell_judge":         "gemini-3.1-pro",
"modell_annotation":    "gemini-3.6-flash",
"modell_vergleich":     "claude-fable-5",
"effort_uebersetzung":  "hoch",
"effort_annotation":    "niedrig",
"rahmen_marker":        "#",
"sheets_id":            ""            (leer = JSON-Direktbetrieb)
```

Ollama-Schlüssel (`ollama_host`, `num_ctx`, `modell`) bleiben für den
Rückfallpfad erhalten. Die Backend-Wahl je Aufruf leitet sich aus dem
Modellnamen ab (Präfix-Zuordnung), `backend_standard` ist nur der Default.

**Wichtig (Gemini):** Der `GeminiBackend` sendet **keine** Sampling-Parameter
(`temperature`, `top_p`, `top_k`) — die API ignoriert sie bei 3.6 Flash,
künftige Generationen antworten mit HTTP 400. Die vier verstellbaren
Pipeline-Parameter wirken damit nur auf Anthropic-Seite; das ist entschieden
und in `ENTSCHEIDUNGEN.md` dokumentiert.

### 3.4 Umgebungen

- **Colab (Primärbetrieb):** Runner-Notebook, Daten in
  `MeinDrive/uebersetzung/<projekt>/`, Code per `git clone/pull` aus dem Repo
  in die VM. Secrets: `ANTHROPIC_API_KEY` und `GoogleKI` (→ intern auf
  `GEMINI_API_KEY` mappen) über `google.colab.userdata`.
- **VPS/lokal (Rückfall):** identischer Code, Keys aus Umgebungsvariablen,
  Referenzdaten als JSON direkt.
- Colab-Erkennung zentral in `gemeinsam.py` (Import-Probe `google.colab`),
  nicht verstreut.

---

## 4 · Arbeitspakete

Reihenfolge einhalten; jedes Paket endet mit grünem Selbsttest und einem
Commit. Abnahmekriterien sind Teil des Pakets.

### Paket 0 — Dokumentation einarbeiten
`CLAUDE_ERGAENZUNG.md` und `ENTSCHEIDUNGEN_ERGAENZUNG.md` gemäß den darin
enthaltenen Einarbeitungshinweisen in `CLAUDE.md` und `ENTSCHEIDUNGEN.md`
mergen. Die Ergänzungsdateien danach löschen (Inhalt lebt in den Zieldateien).

**Abnahme:** Beide Zieldateien enthalten die neuen Abschnitte; keine
Dopplungen; die zwei annotierten „Verworfen"-Einträge sind aktualisiert.

### Paket 1 — Backend-Adapter und Preflight-Weiche
1. `AnthropicBackend` und `GeminiBackend` als Unterklassen des bestehenden
   `Backend` in `gemeinsam.py`, nur `requests`. Anthropic: Messages-API,
   System-Prompt mit `cache_control` (Caching des identischen System-Prompts
   über alle Chunks), Effort-Parameter, Retry mit Backoff auf 429/5xx,
   Timeout ≤ 10 min. Gemini: `generateContent`, `system_instruction`,
   keine Sampling-Parameter (3.3).
2. Modell-Routing: `chat()` erhält die Rolle (uebersetzung/revision/…) und
   löst Modell + Backend + Effort aus der Konfiguration auf.
3. Token-Zählung: Usage aus den Responses je Rolle aufsummieren
   (`manifest.json`), am Laufende Kostenübersicht ausgeben.
4. Preflight: bei Nicht-Ollama-Backends entfallen GPU-/Ollama-Prüfungen;
   stattdessen Key-Präsenz, 1-Token-Ping je genutztem Anbieter und eine
   **Kostenschätzung** (Wortzahl × aktive Pässe × Tarif) vor dem Volllauf.
   Tarife als Konstanten mit Datumskommentar.
5. Selbsttest erweitern: Prompt-Bauer aller Rollen baubar; Gemini-Payload
   nachweislich ohne Sampling-Parameter (Testfall prüft das Payload-Dict).

**Abnahme:** Selbsttest grün ohne Netz; fehlender Key erzeugt klare
Fehlermeldung mit Abhilfe; ein Mini-Echtlauf (1 Chunk Testtext) über beide
Anbieter liefert Text und Usage-Zahlen.

### Paket 2 — Colab-Runner und Drive-Betrieb
1. Runner-Notebook `colab_runner.ipynb` im Repo: eine Zelle — Drive mounten,
   Repo klonen/aktualisieren, Secrets → Umgebungsvariablen, `os.chdir` in den
   Drive-Projektordner, `pipeline.py run` starten. Zweite Zelle: `status`.
2. `pipeline.py`: in Colab `--hg` ablehnen (Hinweistext: Vordergrundlauf ist
   in Colab der richtige Modus); PID-Logik nur außerhalb Colab.
3. Fortschrittsausgabe je Chunk beibehalten (verhindert Idle-Einstufung).
4. Pfadlogik: Arbeitsverzeichnis = Projektordner in Drive; Code-Verzeichnis
   getrennt (VM). Alle bestehenden relativen Pfade müssen das überleben.
5. Abbruchprobe dokumentieren: Lauf starten, VM trennen, neue VM, Runner
   erneut — Fortsetzung am nächsten offenen Chunk ohne Datenverlust.

**Abnahme:** Die Abbruchprobe (5.) ist im Repo als kurze Notiz mit Datum
dokumentiert und von Ian einmal selbst nachvollzogen worden.

### Paket 3 — Google-Sheets-Anbindung
1. Ein Spreadsheet je Projekt (`sheets_id` in `projekt.json`), Tabs:
   `Glossar` (nl | de | hinweis), `Personen` (name | pronomen),
   `Figurenblatt` (name | pronomen | rolle | sprache),
   `Anrede` (beziehung | figuren | niederlaendisch | deutsch_ziel | hinweis),
   `Leitmotive` (wendung | vorschlag | haeufigkeit | absicht),
   `ZitateReview` (siehe Paket 6).
2. Neuer Baustein `referenz_sync`: liest vor jedem Schritt, der
   Referenzdaten braucht, die Tabs (gspread, Colab-Auth) und erzeugt die
   JSONs — **mit Validierung und zeilengenauen Fehlermeldungen**
   („Personen, Zeile 14: Pronomen fehlt"). Ungültige Zeilen brechen den
   Schritt ab, bevor Modellkosten entstehen.
3. Fallback: `sheets_id` leer oder gspread nicht verfügbar → JSONs werden
   direkt gelesen (heutiges Verhalten).
4. Schreibrichtung: Die Vorbereitung (Paket 4) befüllt Sheets **und** JSONs.

**Abnahme:** Absichtlich fehlerhafte Sheet-Zeile erzeugt die erwartete
Meldung; leere `sheets_id` verhält sich exakt wie heute.

### Paket 4 — Schritt `vorbereitung` (ersetzt den externen Handschritt)
1. Neuer Pipelineschritt zwischen `konkordanz` und Testlauf: Opus 5 erhält
   `analysepaket.md` plus das Briefing (Basis:
   `briefing_glossar_vorlage.md`, erweitert um zwei neue Lieferungen) und
   erzeugt die sechs Referenzdateien direkt. Die Entscheidung „Konkordanzen
   statt Volltext" gilt fort.
2. Neue Lieferungen: **`stilprofil.json`** (Ton, Registerbeschreibung,
   Satzlängencharakteristik, Erzählperspektive je Ebene, Tempusempfehlung)
   und **`kapitel.json`** (eine Zeile Zusammenfassung je Kapitel).
3. Prompt-Einspeisung (additiv, Schutzklausel 1 beachten): Stilprofil als
   eigener Baustein im System-Prompt der Übersetzung; Kapitelzeile des
   aktuellen Chunks im User-Prompt.
4. **`anweisungen.md` gehört zu den Lieferungen — mit Überschreibschutz:**
   Die Vorbereitung erzeugt einen Erstentwurf der drei Abschnitte. Existiert
   die Datei bereits mit gefüllten Abschnitten (aktuelles Buch!), wird sie
   **nicht angetastet**; die Vorschläge landen dann in
   `anweisungen_vorschlag.md` zum manuellen Übernehmen — analog zur
   `.neu`-Konvention von `konkordanz.py`. Nach dem Testlauf liefert die
   Bewertung (Paket 8) wie bisher eine nachgeschärfte Fassung, ebenfalls nur
   als Vorschlagsdatei; eingespielt wird ausschließlich vom Menschen im
   Prüffenster.
5. Aus `PAUSE_glossar` wird `PAUSE_review`: Mensch prüft und editiert in
   Sheets bzw. `anweisungen.md`, dann weiter.

**Abnahme:** Ein Lauf am Testbuch erzeugt alle Lieferdateien; Preflight
validiert sie im Quick-Modus; Stilprofil erscheint nachweislich im gebauten
Prompt (Selbsttestfall); eine vorhandene gefüllte `anweisungen.md` bleibt
byte-identisch erhalten (Testfall), Vorschläge erscheinen separat.

### Paket 5 — Rahmenwechsel-Chunking und Variantenvergleich
1. **`#`-Regel:** An jeder Zeile, die dem `rahmen_marker` entspricht, wird
   eine Chunkgrenze erzwungen und die Kontextrückschau zurückgesetzt (wie an
   der Testauszug-Fuge). Im User-Prompt wird die Erzählebene benannt
   (Haupterzählung: dritte Person Präsens / Rahmenerzähler: erste Person
   Präteritum — Formulierung aus `stilprofil.json` beziehen, nicht
   hartkodieren).
2. `testB`/`chunkvergleich` zu einem generischen **Variantenvergleich**
   verallgemeinern: Varianten unterscheiden sich in Chunkgröße *oder*
   Modell. Konkret anzulegende Testmatrix: Basis (Opus 5, 800) gegen
   (Opus 5, 1600) gegen (Fable 5, beste Chunkgröße) — Fable einmalig.
3. Bewertung der Varianten über den Judge-Pfad (Gemini 3.1 Pro) plus
   Diff-Statistik; Ergebnisbericht wie bisher als Markdown-Paket.

**Abnahme:** Ein synthetischer Text mit `#`-Zeilen erzeugt Chunkgrenzen
exakt dort (Selbsttestfall); der Variantenvergleich läuft mit drei Varianten
durch und weist Kosten je Variante aus.

### Paket 6 — Schritt `zitatrecherche`
1. Neuer Schritt nach `preflight`: je erkanntem Epigraph/bestätigtem Zitat
   ein Opus-Aufruf mit aktiviertem Websuche-Tool. Ablauf je Zitat:
   Sprache bestimmen → **nicht Niederländisch: unverändert übernehmen**
   (Status `original_belassen`) → Niederländisch oder Drittsprache mit
   etablierter deutscher Fassung: anerkannte Übersetzung ermitteln, mit
   Übersetzer, Quelle/Fundstelle und Konfidenz.
2. Ergebnis in den Tab `ZitateReview`
   (index | sprache | original | vorschlag_de | uebersetzer | quelle |
   konfidenz | freigegeben) bzw. als `zitate_review.md` im JSON-Betrieb.
   **Keine automatische Übernahme:** Eingesetzt wird nur, was
   `freigegeben = ja` trägt — die Freigabe erfolgt im Prüffenster.
3. Unterhalb der Konfidenzschwelle oder ohne Freigabe gilt weiter „lieber
   markierte Lücke als erfundener Wortlaut" (Platzhalterverfahren
   unverändert). Eingesetzte Zitate bleiben vom Lektorat ausgenommen.

**Abnahme:** Nicht-niederländisches Testzitat wird unverändert markiert;
niederländisches Testzitat erzeugt einen Review-Eintrag mit Quelle; nichts
gelangt ohne Freigabe in den Zieltext (Testfall).

### Paket 7 — Schritt `annotation`
1. Nach dem Lektorat: Wortdiff-Paare aus der `diffview`-Struktur bündeln
   (nur Kategorien Wort/Wendung/Teilsatz/Umbau/Absatz), Gemini 3.6 Flash
   liefert eine Ein-Zeilen-Begründung je Änderung (gebündelte Aufrufe,
   JSON-Antwort). Typografie/Interpunktion werden nicht annotiert.
2. `diffview.py --html` erhält eine Begründungsspalte; Konsole optional
   (`--begruendung`).
3. Der Lektoratspass selbst bleibt unangetastet — Begründung ist ein
   nachgelagerter Schritt, keine Doppelaufgabe des Editiermodells.

**Abnahme:** HTML-Bericht zeigt Begründungen nur bei substanziellen
Änderungen; Kosten des Schritts erscheinen in der Kostenübersicht.

### Paket 8 — Judge-Routing in `bewertung.py`
Blindbewertung von „lokales Modell" auf `modell_judge` umstellen
(Tauschlogik übernehmen), Opus-Selbstcheck als drittes Signal ergänzen,
Gewichtungshinweis gemäß 3.2 in die Berichte. Briefing-Vorlagen
(`briefing_bewertung_vorlage.md`, `briefing_lektorat_vorlage.md`) auf die
neue Signalzusammensetzung anpassen.

**Abnahme:** Bewertungsbericht weist alle drei Signale getrennt und korrekt
beschriftet aus.

### Paket 9 — `ABLAUFPLAN.md` neu
Vollständige Neufassung für den Colab-Betrieb: Runner statt Terminalbefehle,
neue Schrittliste (inkl. `vorbereitung`, `PAUSE_review`, `zitatrecherche`,
`annotation`), Sheets-Workflow, Kostenübersicht, Störungstabelle
(Key fehlt, 429, VM getrennt, Sheet-Validierung schlägt fehl). Die
GPU-Kapitel (VRAM, Stop/Destroy, `ollama ps`) entfallen; der VPS-Rückfall
bekommt einen kurzen Anhang.

**Abnahme:** Der Plan enthält keinen Befehl mehr, der in Colab nicht
funktioniert, und kein `rm`.

---

## 5 · Nicht Teil dieses Auftrags

- Änderungen am DE→EN-Skriptsatz.
- Neuentscheidung von `revision_pass`, `lektorat_passes`, `chunk_words`:
  Diese werden **nach** der Migration im Testlauf unter Opus 5 kalibriert —
  die Mistral-Ära-Werte gelten als offen, nicht als gesetzt.
- Die zwei offenen Projektentscheidungen in `anweisungen.md`
  (`Zomerdate`, `smilede`) — entscheidet Ian vor dem Volllauf.
- Jegliches `git push` — nur nach Freigabe.

## 6 · Rückfragen-Regel

Bei Widersprüchen zwischen diesem Auftrag und `ENTSCHEIDUNGEN.md` gilt
dieser Auftrag; der Widerspruch wird aber gemeldet statt still aufgelöst.
Bei Unklarheiten in API-Details (Effort-Syntax, Websuche-Tool-Parameter,
Sheets-Auth) gilt: aktuelle Anbieterdokumentation prüfen, Entscheidung im
Commit-Text dokumentieren.
