# Briefing: Glossar und Referenzmaterial — Niederländisch → Deutsch

Du bekommst ein Analysepaket zu einem niederländischen literarischen Werk, das
ins Deutsche übersetzt werden soll. Erstelle daraus das Referenzmaterial, das
die maschinelle Übersetzung Chunk für Chunk mitgeliefert bekommt.

## Was du liefern sollst

Sechs Dateien, jeweils als eigener Codeblock:

**`glossar.json`** — `{"niederländisch": "deutsch"}`
Eigennamen, Ortsnamen, Institutionen, Titel, erfundene Begriffe,
Fachvokabular, kulturgebundene Wörter. Nur Einträge, bei denen Konsistenz
zählt.

**`personen.json`** — `{"Name": "er/ihn/sein"}`
Nur Personen. Bei Nachnamen für mehrere Figuren getrennte Einträge mit Anrede.
Kurzformen und Spitznamen als eigene Einträge.

**`figurenblatt.json`** — je Figur `pronomen`, `rolle`, `sprache`

**`anrede.json`** — Vorgabe ist `u` → `Sie` und `jij/je` → `du`. Diese Datei
regelt nur die **Abweichungen**. Wichtig: `u` wird im heutigen Niederländisch
enger verwendet als das deutsche `Sie`. Wo Niederländer längst `je` sagen,
siezen sich Deutsche noch — unter Kollegen, gegenüber Ladenpersonal, bei losen
Bekanntschaften. Prüfe die Anredebelege daraufhin und benenne jede Beziehung,
in der die mechanische Zuordnung falsch wäre. Format je Eintrag:
`{"Beziehung": {"niederlaendisch": "je", "deutsch": "Sie", "figuren": ["Name"]}}`

**`leitmotive.json`** — wiederkehrende Wendungen und Bildfelder mit fester
deutscher Entsprechung. Format: `{"nl Wendung": {"n": 12, "vorschlag":
"deutsche Wendung", "art": "Geste|Bildfeld|Erzählformel", "absicht":
"ja|unklar"}}`. Der Wortlaut in `vorschlag` wird später gegen den fertigen Text
geprüft — er muss deshalb genau die Formulierung sein, die im Deutschen stehen
soll.

**`anweisungen.md`** — Freitext mit den Abschnitten `## Übersetzung`,
`## Stillektorat`, `## Korrektorat`. Auf Deutsch. Nur Anweisungen, keine
Erläuterungen, keine HTML-Kommentare.

## Die acht Fallen dieser Sprachrichtung

Niederländisch und Deutsch sind so nah verwandt, dass wörtliche Übertragung
grammatisch funktioniert und trotzdem falsch ist. Achte auf:

**Falsche Freunde.** Das Paket listet die Vorkommen. Besonders tückisch, weil
beide Lesarten im Kontext funktionieren: `lopen` (gehen, nicht laufen),
`mogen` (mögen oder dürfen), `gekocht` (gekauft, von *kopen* — gekocht wäre
*gekookt*), `net` (gerade oder gepflegt), `enkel` (nur oder Knöchel), `naar`
(nach oder unangenehm), `monster` (Probe), `tafel` (Tisch), `bank` (Sofa),
`kwartier` (Viertelstunde), `straks` (gleich), `eventueel` (gegebenenfalls),
`kussen` (Kissen und küssen).

**Evidentielles `zou`.** `Hij zou ziek zijn` heißt »Er soll krank sein«, nicht
»Er wäre krank«. Das Paket nennt die Zahl der Vorkommen. Sag mir, ob der Text
Gerüchte-, Klatsch- oder Berichtspassagen hat, in denen das systematisch
auftritt.

**Diminutive.** Die Politik steht in den Eckdaten. Bei `auflösen` gehört eine
klare Anweisung nach `## Übersetzung`. Nenne die Fälle, in denen das Diminutiv
doch stehen bleiben soll.

**Tempus.** Die Politik steht in den Eckdaten. Bei `quellnah` prüfe, ob der
Text eine erste oder dritte Person hat: Perfekt in deutscher Erzählprosa
klingt gesprochen und süddeutsch gefärbt. Bei einem umgangssprachlichen
Ich-Erzähler ist das richtig, bei distanzierter dritter Person unbeholfen.
**Sag mir, wie der Text erzählt ist, und empfiehl daraufhin die endgültige
Formulierung der Tempusanweisung.**

**Progressivkonstruktionen.** `aan het + Infinitiv`, `zitten/staan/liggen te +
Infinitiv`, `gaan` als Futur. Keine hat eine standardsprachliche deutsche
Entsprechung.

**Das Wörtchen `er`.** Existenzsätze, Platzhalter, Pronominaladverbien. Die
mechanische Übertragung erzeugt eine `es gibt`-Schwemme.

**Modalpartikeln.** Beide Sprachen haben sie, die Pragmatik deckt sich nicht.
`toch` ist nicht immer `doch`, `wel` nicht `wohl`, `even` nicht `eben`. `hoor`
hat gar keine Entsprechung.

**Kulturgebundene Wörter.** `gezellig`, `lekker`, `borrel`, `uitwaaien`,
`polder`, `gedogen`, `tussendoortje`. Projektentscheidung im Glossar, keine
Einzelfallübersetzung — `lekker` allein kommt in einem Roman leicht
zweihundertmal vor.

## Weiter zu beachten

**Bewusste Wiederholung.** Prüfe die Liste der wiederkehrenden Wendungen. Was
Stilmittel ist, muss in `anweisungen.md` ausdrücklich geschützt werden — sonst
schleift es der Lektoratslauf ab.

**Zitate und Motti.** Wo ausgeklammerte Zitate stehen, ermittle den deutschen
Wortlaut: bei deutschsprachigem Original den echten, sonst die etablierte
deutsche Übersetzung. Wenn du einen Wortlaut nicht sicher verifizieren kannst,
setze **keinen** Text ein, sondern einen markierten Platzhalter mit deinen
Kandidaten.

## Was du außerdem sagen sollst

Eine Empfehlung zu `chunk_words`, `context_words`, `temperature_uebersetzung`
und `temperature_revision`, hergeleitet aus Absatzlänge, Dialoganteil und
Satzbau. Andere Parameter nicht anfassen. Liefere die Änderungen als
vollständige `projekt.json` im Codeblock — die Schlüssel `ratio_min`,
`ratio_max`, `ratio_kalibriert` und `sprachpaar` dabei unverändert lassen,
sie werden von der Pipeline gesetzt und beim Einspielen ohnehin geschützt.

Und eine kurze Liste dessen, was die Übersetzung erschweren wird.
