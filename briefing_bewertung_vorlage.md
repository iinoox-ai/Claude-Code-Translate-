# Briefing: Testübersetzung bewerten — Niederländisch → Deutsch

Du bekommst eine Testübersetzung in zwei Fassungen (Entwurf und Revision),
dazu die Diff-Statistik und ein blindes Urteil.

Zu den Urteilen: Das Bewertungspaket weist bis zu **drei Signale getrennt**
aus, und die Überschrift nennt jeweils das Modell, von dem sie stammen.

1. **Diff-Statistik** — auszählbar, kein Urteil, und deshalb das belastbarste.
2. **Blindes Urteil** eines Fremdmodells — es hat keinen Grund, die eigene
   Arbeit zu bevorzugen.
3. **Selbstcheck** desselben Modells, das übersetzt hat. Steht dort
   »Selbstcheck, nachrangig«, ist das ernst gemeint: Modelle bevorzugen ihre
   eigenen Formulierungen, auch blind.

Zähle die Urteile nicht zusammen. Widersprechen sie einander, gilt die
Reihenfolge oben.

**Der Testauszug besteht aus zwei Teilen**, getrennt ausgewiesen: eine
Erzählpassage und eine dialoglastige Passage. Bewerte beide getrennt. Bei
diesem Sprachpaar ist die Schwäche im Dialog zu erwarten, weil dort
Modalpartikeln, Diminutive und Anredeform zusammentreffen.

Liegt ein **Chunkgrößen-Vergleich** bei (Variante A und B derselben Passage),
sag mir, welche Größe das bessere Ergebnis liefert und woran du es siehst.

## Erste Aufgabe: lohnt der Revisionspass?

Der zweite Durchgang verdoppelt die Laufzeit. Sag klar, ob er das wert ist,
getrennt für Erzählung und Dialog — womöglich lohnt er nur für einen Teil.

Die Diff-Statistik ist das belastbarste Signal: Ein Durchgang, dessen
Änderungen überwiegend Typografie sind, verdient seine Zeit nicht.

## Zweite Aufgabe: die acht Fallen prüfen

Suche gezielt nach falschen Freunden, mechanisch übertragenen Diminutiven,
Verlaufsformen als »am …-sein«, Körperhaltungsverben, `es gibt`-Schwemme,
Modalpartikeln nach Formähnlichkeit — und besonders nach **`zou` als
Konditional übersetzt, wo Hörensagen gemeint war**.

Zum **Tempus**: Das Projekt will den quellnahen Wechsel zwischen Präteritum
und Perfekt. Prüfe, ob er im Deutschen grammatisch trägt, und sag mir, ob der
Text eine erste oder dritte Person hat. Empfiehl daraufhin die endgültige
Formulierung der Tempusanweisung.

## Dritte Aufgabe: `anweisungen.md` schreiben

Liefere die Datei vollständig als Codeblock, mit den Abschnitten
`## Übersetzung`, `## Stillektorat`, `## Korrektorat`. Auf Deutsch. Sie wird
wörtlich an die System-Prompts angehängt — präzise und knapp, keine
Erläuterungen, keine HTML-Kommentare.

Achte besonders auf bewusste Wiederholungen, die geschützt werden müssen, und
auf Marker der Figurenstimme, die das Korrektorat nicht anfassen darf.

## Vierte Aufgabe: Parameter

Empfiehl `chunk_words`, `context_words` und die `effort_<rolle>`-Stufen
(`niedrig`, `mittel`, `hoch`, `sehr_hoch`, `maximal`). Begründe jede
Abweichung. Andere Parameter nicht anfassen.

**Keine Temperaturempfehlung.** Die `temperature_*`-Schlüssel wirken im
API-Betrieb nicht: `claude-opus-5` hat den Parameter entfernt und lehnt ihn
mit HTTP 400 ab, Gemini nimmt ihn an und ignoriert ihn. Sie stehen nur noch
für den Ollama-Rückfallpfad in der Konfiguration. Wer die Streuung
beeinflussen will, tut das über `effort` oder über die Anweisungen.

Liefere die geänderte `projekt.json` als Codeblock; `ratio_min`, `ratio_max`,
`ratio_kalibriert` und `sprachpaar` unverändert lassen.
