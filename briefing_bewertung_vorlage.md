# Briefing: Testübersetzung bewerten — Niederländisch → Deutsch

Du bekommst eine Testübersetzung in zwei Fassungen (Entwurf und Revision),
dazu die Diff-Statistik und die blinde Selbstbewertung des lokalen Modells.

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

Empfiehl `chunk_words`, `context_words`, `temperature_uebersetzung`,
`temperature_revision`. Begründe jede Abweichung. Andere Parameter nicht
anfassen. Liefere die geänderte `projekt.json` als Codeblock; `ratio_min`,
`ratio_max`, `ratio_kalibriert` und `sprachpaar` unverändert lassen.
