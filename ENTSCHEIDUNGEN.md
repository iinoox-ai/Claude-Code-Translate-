# Entscheidungen

Warum die Pipeline so gebaut ist, wie sie gebaut ist. Jede Entscheidung hier
hat eine Begründung, die im Code nicht steht — und mehrere davon würde jemand
mit guten Argumenten wieder umdrehen, wenn er sie nicht kennt.

Am Ende steht eine Liste der **verworfenen** Vorschläge. Die ist genauso
wichtig, damit sie nicht in jeder Überarbeitung neu diskutiert werden.

---

## Reihenfolge des Lektorats

**Entschieden:** `det → stil → korrektorat → det`

Das weicht von der Verlagsreihenfolge ab, in der das Korrektorat zuletzt
kommt. Der Grund ist messbar: Der Stildurchgang hat bei einem Testlauf 46
Satzumbauten und 147 Teilsatzänderungen vorgenommen. Wer Sätze umbaut, erzeugt
neue Fehler in Kongruenz, Zeitenfolge und Rektion. Läuft das Korrektorat davor,
bleiben die unentdeckt.

Die naheliegende Gegenüberlegung — Stil zuletzt, damit er die präskriptive
Glättung des Korrektorats wieder ausbügelt — trägt nicht. Der Stildurchgang
sucht nicht danach; er bekommt den Auftrag, Germanismen und Rhythmus zu
bearbeiten. Ob er `as if he were` zurück zu `like he was` dreht, wäre Zufall.
**Vorbeugen ist stärker als Reparieren:** Das Korrektorat bekommt den
Stimmschutz und erzeugt den Schaden gar nicht erst.

Der zweite deterministische Durchgang am Ende kostet nichts und zieht gerade,
was die LLM-Durchgänge an Strichen und Anführungszeichen angefasst haben.

## Korrektorat nur mit Stimmschutz

**Entschieden:** Der `STIMMSCHUTZ`-Block steht in beiden LLM-Prompts, im
Korrektorat zusätzlich mit einer engen Liste dessen, was überhaupt korrigiert
werden darf.

Gemessen an einem Testlauf DE→EN: Von 460 Änderungen des Korrektorats waren
**94 % Typografie und Interpunktion** — Arbeit, die der deterministische
Durchgang kostenlos erledigt. Von den 30 inhaltlichen Eingriffen war ein
erheblicher Teil **schädlich**: siebenmal `like` → `as if`, dazu `was` → `were`
und `he's` → `he has`. Präskriptive Schulgrammatik, angewandt auf die
Ich-Erzählung eines Sechzehnjährigen.

Ohne ausdrückliche Anweisung entscheidet ein Modell im Zweifel für die Norm.
Das ist kein Konfigurationsfehler, das ist der Normalfall.

## Deterministisch vor LLM, wo immer möglich

**Entschieden:** Typografie, Schreibvarianten, ß/ss, Abstände, Dekaden laufen
ohne Modell.

Was ein Skript erledigt, kann das Modell nicht versehentlich umschreiben. Und
es kostet nichts. Der Grundsatz gilt allgemein: **jede Aufgabe, die sich
deterministisch lösen lässt, gehört aus dem LLM heraus.**

## ß-Korrektur schreibungsabhängig

**Entschieden:** Kleingeschriebenes `gross`, `weiss`, `heiss` wird zu `groß`,
`weiß`, `heiß`. Großgeschriebenes `Gross`, `Weiss`, `Ass`, `Masse`, `Busse`
bleibt unangetastet.

Die erste Fassung schützte pauschal und übersah damit die häufigsten echten
Fehler; eine noch frühere Fassung schützte gar nicht und **verfälschte
korrektes Deutsch**: aus `die Masse der Menschen` wurde `die Maße`, aus `die
Busse fuhren` wurde `die Buße`. Niederländisch kennt kein ß, ein Modell mit
viel niederländischem Input schreibt zuverlässig `Strasse` und `draussen` —
deshalb ist die Korrektur nötig, und deshalb muss sie genau sein.

Die Liste in `HOMOGRAPHEN` ist die Stelle, an der bei einem neuen Text
nachgebessert wird.

## Zitatrecherche schreibt `original_deutsch` nie selbst

**Entschieden:** `zitatrecherche.py` füllt `vorschlag_de`, `uebersetzer`,
`quelle` und `konfidenz` — aber **nicht** `original_deutsch`. Genau dieses eine
Feld setzt `uebersetzung.py` in den Zieltext ein, und es wird ausschließlich
von `freigabe_einlesen()` gefüllt, aus der Review-Liste bzw. dem Sheet-Tab.

Die Trennung ist der ganze Punkt des Schritts. Ein Modell, das recherchiert und
gleichzeitig einsetzt, hat die Freigabe strukturell umgangen — und niemand
merkt es, weil das Ergebnis plausibel aussieht. Der Selbsttest prüft deshalb
nicht, ob der Vorschlag gut ist, sondern ob er **ohne Freigabe im Text landet**.
Die Gegenprobe, die `original_deutsch` in der Recherche setzt, meldet
„FREIGABE UMGANGEN".

**Nicht-niederländische Zitate sind der Sonderfall ohne Entscheidung.** Ein
englisches Motto in einem niederländischen Roman steht auch in der deutschen
Ausgabe englisch. Status `original_belassen`, `original_deutsch` = das Original,
`freigegeben` = `entfaellt`. Hier gibt es nichts freizugeben, und eine Zeile in
der Liste, die auf eine Entscheidung wartet, die niemand treffen kann, ist
Ballast.

**Die Websuche ist kein Beiwerk, sie ist der Zweck.** Ohne sie reimt sich das
Modell einen Wortlaut zusammen — also genau der Fehler, den der Schritt
verhindern soll. Serverseitige Werkzeuge gibt es nur auf dem Anthropic-Pfad;
ist die Rolle auf ein anderes Backend gelegt, läuft der Aufruf mit Hinweis ohne
Suche, statt mit einer Payload, die der Anbieter ablehnt.

Die Konfidenzschwelle markiert, sie entscheidet nicht. Ein unsicherer Vorschlag
wird gezeigt und als unsicher gekennzeichnet — der Mensch entscheidet, nicht
die Zahl.

## Rahmenwechsel: Markerzeile bleibt im Text, Ebene kommt aus dem Stilprofil

**Entschieden:** An jeder Zeile, die dem `rahmen_marker` entspricht, endet die
Chunkgruppe. Die Markerzeile **beginnt die neue Gruppe und bleibt stehen** —
sie ist die Gliederung des Autors, nicht unsere.

Der Schnitt setzt die Rückschau zurück, weil die Fuge zwischen zwei Gruppen
schon vorher ein Kontext-Reset war. Ohne ihn bekäme der erste Chunk nach dem
Wechsel die letzten Sätze der vorigen Ebene als Vorbild — und Tempus und
Person bluten hinüber. Genau dafür ist die Regel da.

Die **Benennung der Ebene** kommt aus `stilprofil.json`, nicht aus dem Code.
Ein hartkodiertes „dritte Person Präsens" wäre beim nächsten Buch falsch, und
niemand würde es hier suchen. Drei Fälle, in dieser Reihenfolge: Die
Markerzeile nennt die Ebene (`# Krieg`) → die gilt. Nackter Marker und genau
zwei Ebenen → die jeweils **andere als zuletzt**, nicht „gerade/ungerade";
nach einer benannten Gruppe wäre das versetzt. Alles andere → keine Benennung.

**Lieber schweigen als raten:** Eine falsch benannte Erzählebene im Prompt ist
schädlicher als gar keine. Bei drei oder mehr Ebenen lässt sich die Zuordnung
aus einem nackten `#` nicht ableiten, also unterbleibt sie.

Die Reihenfolge in `perspektive` ist die des ersten Auftretens im Buch, nicht
die alphabetische. Die erste Fassung sortierte und wies damit dem Textanfang
die alphabetisch erste Ebene zu — im Testfall „Krieg" statt „Rahmen 1919".

## Varianten unterscheiden sich in Chunkgröße ODER Modell

**Entschieden:** `testB`/`chunkvergleich` sind zu einem generischen
Variantenvergleich verallgemeinert. Eine Variante trägt einen Namen und, was
abweicht: `chunk_words`, `modell_uebersetzung` oder beides.

Beides stellt dieselbe Frage — wird der Text dadurch besser? — also gehört es
in dieselbe Mechanik. Zwei getrennte Apparate für „Chunkgröße prüfen" und
„Modell prüfen" wären derselbe Code zweimal, und der zweite würde beim ersten
Umbau vergessen.

Die Schrittnamen bleiben stabil (`testB`, `testC`), weil das Manifest sie als
Schlüssel führt; die Schrittliste selbst entsteht aus `projekt.json`.

**Kosten je Variante** kommen aus einer Differenz: Das Manifest bucht nach
Rolle, nicht nach Variante. Vor und nach dem Lauf ein Schnappschuss, die
Differenz landet als `kosten.json` neben dem Ergebnis. Ohne das ließe sich
„Kosten je Variante" nur schätzen, und eine geschätzte Zahl in einem Bericht,
der Entscheidungen trägt, ist schlimmer als keine.

## Vorbereitung: je Lieferung ein Aufruf, Befunde im System-Prompt

**Entschieden:** `vorbereitung.py` macht acht kleine Modellaufrufe statt einen
großen, und die Konkordanzbefunde stehen im System-Prompt statt im
User-Prompt.

Der System-Prompt trägt den Cache-Marker. Stehen die Befunde dort und ändert
sich zwischen den Aufrufen nur der Auftrag, zahlt der erste Aufruf die Befunde
und die sieben weiteren treffen den Cache. Eine einzige große Antwort wäre
teurer, weil die Ausgabe die teure Seite ist und acht Dateien am Stück eine
lange Ausgabe ergeben.

Der zweite Grund wiegt schwerer: **Jede Lieferung ist einzeln prüfbar und
einzeln nachziehbar.** Kommt das Stilprofil in falscher Form, wird genau diese
Datei nicht geschrieben und `--nur stilprofil` holt sie nach — statt dass ein
Formfehler in einem von acht Blöcken den ganzen Aufruf entwertet.

Die Formprüfung je Lieferung ist dieselbe Frage, die der Leser im Prompt
stellt. Das ist die Lehre aus dem ersten Vorbereitungslauf: Damals lieferte
das Modell `{"paare": [...]}`, `block_anrede` las flache Abbildungen, und der
Vorschlag wurde stillschweigend übersprungen. Jetzt wird er gar nicht erst
geschrieben.

## Sheets-Sync validiert vor dem ersten Modellaufruf

**Entschieden:** `referenz_sync` liest, validiert und schreibt die JSONs am
Anfang jedes Schritts, der Referenzdaten braucht — nicht beim Zugriff auf den
einzelnen Wert.

Ein Tippfehler in Zeile 14 des Glossars soll auffallen, bevor 135 Chunks
gerechnet sind. Deshalb sammelt die Prüfung **alle** Fehler und meldet sie
zeilengenau in einem Durchgang: Wer ein Sheet korrigiert, will die Liste, nicht
einen Fehler pro Anlauf.

Die Zeilennummern sind die des Spreadsheets — Kopfzeile 1, erster Datensatz 2.
Alles andere zwingt den Menschen zum Umrechnen.

**Fehlende Spalten sind ein Fehler, zusätzliche nicht.** Sonst bricht das Sheet,
sobald jemand eine Notizspalte anhängt — und genau das tut man in einem
Spreadsheet.

Die Spaltennamen des Auftrags sind nicht überall die JSON-Feldnamen:
`deutsch_ziel` im Tab wird zu `deutsch` im JSON, weil `block_anrede` diesen
Namen liest. Ein Selbsttestfall hält beide Seiten aneinander und prüft, dass
der **Wert** im Prompt ankommt — nicht bloß, dass ein Block entsteht. Die erste
Fassung des Tests prüfte nur auf „nicht leer" und blieb grün, als ich die
Abbildung zur Gegenprobe entfernte: `block_anrede` baut die Zeile auch mit
leerem Zielfeld.

## Spatium vor Auslassungspunkten bleibt stehen

**Entschieden:** `…` fällt aus der Zeichenklasse der Regel „kein Leerzeichen
vor Satzzeichen". Komma, Punkt, Semikolon, Doppelpunkt, Frage- und
Ausrufezeichen behalten sie.

Im Deutschen hängt das Spatium davon ab, was ausgelassen wird: Steht `…` für
ein ganzes Wort, gehört eines davor (`Meine Eltern sind … nicht`); ist ein
Wort abgebrochen, entfällt es (`Verd…`). Welcher Fall vorliegt, entscheidet
der Satz und kein Muster — also bleibt stehen, was das Korrektorat gesetzt
hat.

**Gemessen** am Testlektorat vom 31.07.2026: sechs getilgte Spatien, darunter
`sind … nicht` → `sind… nicht` und `für das Vaterland …` → `Vaterland…`. Die
`anweisungen.md` des Projekts verbot das ausdrücklich („Vorhandene Spatien vor
… nicht entfernen"), konnte sich aber nicht durchsetzen: Der deterministische
Durchgang läuft zuletzt und liest keine Anweisungen.

Das ist der allgemeine Fall, der hier interessiert: **Eine deterministische
Regel schlägt jede Anweisung, weil sie danach kommt.** Wo beide dasselbe
Feld beanspruchen, muss die Regel nachgeben oder die Anweisung
verschwinden — eine Anweisung ohne Wirkung ist schlimmer als keine, weil
niemand merkt, dass sie nicht gilt.

Der Selbsttest prüft seither beide Richtungen: Spatium vor `…` erhalten,
Spatium vor Komma und Semikolon getilgt.

## Bewusste Wiederholung ist geschützt

**Entschieden:** Der Stimmschutz weist beide LLM-Durchgänge an, wiederkehrende
Gesten, Wendungen und Satzmuster nicht zu variieren.

Anlass war ein konkreter Fund: Ein Roman enthielt auf 97.000 Wörter rund **115
wiederholte Körpergesten** — 55-mal Achselzucken, 60-mal Kopfschütteln. Bei
einem Ich-Erzähler, der nicht über Gefühle spricht, ist das kein Versehen,
sondern das Mittel. Die Standardanweisung „Wiederholungen vermeiden" hätte es
stillschweigend abgeschliffen, und man merkt es erst beim Vergleich mit dem
Original.

Die Gegenprobe steht in `qa.py`: Gestenzähler und Diminutivzähler vor und nach
dem Lektorat.

## Konkordanzen statt Volltext für die Glossaranalyse

**Entschieden:** `konkordanz.py` extrahiert Kandidaten mit Belegstellen; das
externe Modell liest diese statt der Prosa.

Der Grund ist nicht Sparsamkeit, sondern Qualität. 100.000 Wörter sind rund
150.000 Token und liegen damit im Bereich, in dem Modelle nachweislich
unzuverlässig werden — Messungen zeigen 10–25 % Informationsverlust in der
Mitte langer Kontexte, mit plötzlichem statt allmählichem Abfall. Für ein
Glossar ist Vollständigkeit die einzige Eigenschaft, die zählt.

20.000 Token konzentrierter Belegstellen enthalten praktisch das gesamte
Signal. Das Verfahren **verdichtet** die Evidenz, statt sie zu strecken.

Der Volltext wird zusätzlich mitgeschickt, wenn `export_glossar: true` — dann
kann das Modell Zweifelsfälle am Kontext prüfen. Bei vertraulichen Texten
schaltet man ihn ab.

## Was die Konkordanzanalyse gefunden hat, was kein Skript findet

Als Beleg dafür, dass diese Stufe ihren Aufwand wert ist — fünf Befunde aus
einem realen Buch, die jede Heuristik falsch gemacht hätte:

- Der Erzähler hatte **drei Namen** (Vollform, zwei Kurzformen), und die
  Verteilung war Figurenzeichnung: eine Kurzform benutzte nur eine einzige
  Figur.
- Eine Figur trat unter **zwei Identitäten** auf (Bühnenpersona). Die
  Pronomenwahl ist dort eine Projektentscheidung, keine Grammatikfrage.
- Ein Nachname stand für **zwei verschiedene Personen** — ein Eintrag hätte
  die Hälfte der Pronomen verdorben.
- Zwei Figuren erschienen im Text durchgehend mit **Artikel vor dem
  Nachnamen** (umgangssprachlich) und fielen dadurch aus der Namensliste.
- Das **Fachvokabular des Milieus** lag komplett außerhalb jeder
  Namensheuristik, weil es hinter Artikeln steht — und war genau der Teil, bei
  dem Inkonsistenz am schnellsten auffällt.

## Lokale Blindbewertung bleibt, trotz Schwäche

**Entschieden:** `bewertung.py` lässt das lokale Modell Entwurf und Revision
blind vergleichen, obwohl Selbstbewertung methodisch schwach ist.

Sie ist das **dritte** Signal neben der Diff-Statistik (belastbar) und dem
eigenen Urteil (maßgeblich). Die Tauschlogik randomisiert, welche Fassung als
A und welche als B erscheint, und die Auswertung rechnet zurück. Das nimmt
zumindest die Positionsverzerrung heraus.

Der Code sagt selbst, dass das Signal schwach ist. Das ist Absicht — die
Warnung gehört in den Bericht, nicht ins Kleingedruckte.

## Prüfgrenzen aus dem Testlauf kalibrieren

**Entschieden:** `ratio_min` und `ratio_max` werden nach dem Testlauf aus den
gemessenen Verhältnissen gesetzt, nicht aus einer Faustregel.

Bei NL→DE liegen Quell- und Zielsprache so dicht beieinander, dass feste
Grenzen entweder zu weit (nutzlos) oder zu eng (Rauschen) wären. Die gemessene
Verteilung des konkreten Textes ist der bessere Maßstab.

Diese Schlüssel stehen deshalb in `GESCHUETZT` und können von einer
eingespielten Konfiguration nicht überschrieben werden.

## Kontext-Reset an der Fuge der Testauszüge

**Entschieden:** Der Testlauf nimmt zwei getrennte Auszüge (Erzählung und
Dialog). An der Nahtstelle wird die Rückschau zurückgesetzt.

Ohne das reicht das Skript Kontext über eine Stelle hinweg, die im Buch gar
nicht zusammenhängt — und erzeugt dort einen künstlichen Bruch, den man beim
Prüfen fälschlich als Qualitätsproblem liest.

Die getrennte Auswertung von Erzählung und Dialog ist bei NL→DE besonders
wichtig: Im Dialog treffen Modalpartikeln, Diminutive und Anredeform
zusammen — dort ist die Schwäche zu erwarten.

## Chunk-Ausgaben einzeln speichern

**Entschieden:** Jeder Chunk landet als eigene Datei in `teile/`, der
Gesamttext wird am Ende zusammengesetzt.

Das löst drei Probleme auf einmal: Resume zählt Dateien statt einer
Zustandsdatei zu vertrauen; ein einzelner Chunk lässt sich neu rechnen
(`--chunk 37`) ohne Gesamtlauf; und die Zitateinsetzung beim Zusammensetzen ist
idempotent — sie passiert bei jedem Aufruf, auch nach einem Absturz kurz vor
Schluss.

## Kein `rm` im normalen Ablauf

**Entschieden:** Nur `pipeline.py neu` löscht Ergebnisse, und es fragt vorher.

Der frühere Ablaufplan hatte `rm -f state.json …` im Startblock von Sitzung B
und weiter unten den Hinweis „bei Abbruch denselben Befehl erneut". Wer den
Block kopierte, verlor Stunden Arbeit. Das war ein Datenverlustrisiko durch
Dokumentation, nicht durch Code — und genau deshalb gefährlich.

## `anweisungen.md` ohne Kommentare in den Abschnitten

**Entschieden:** Die Erläuterungen stehen **vor** dem ersten `##`. Zusätzlich
filtert der Loader HTML-Kommentare heraus.

In der ersten Fassung standen Platzhalter-Beispiele als `<!-- ... -->`
innerhalb der Abschnitte. `lade_anweisungen()` gab sie ungefiltert zurück — das
Modell bekam bei jedem Chunk Anweisungen über eine Figur, die es nicht gibt,
und der Preflight meldete die Abschnitte fälschlich als „mit Inhalt". Der
Fehler lief unbemerkt durch mehrere Testläufe.

**Merksatz:** Alles, was in eine Prompt-Datei geschrieben wird, landet
irgendwann im Prompt. Erläuterungen gehören woanders hin.

## Selbsttest vor jedem Modellaufruf

**Entschieden:** `preflight.py` startet mit einem Selbsttest aller
Normalisierer, Metriken und Prompt-Bauer auf einer Kunstzeile. Schlägt er fehl,
gibt es keinen Modellaufruf.

Zwei der schlimmsten Fehler des Projekts waren **Laufzeitfehler**, die kein
Lesen gefunden hat: ein `\u`-Escape in einem Raw-String als
`re.subn`-Ersetzung, und die ß-Kollision. Beide hätte der Selbsttest in
Sekunden gemeldet.

## Chunkgröße 800, nicht 2500

**Entschieden:** Die Vorgabe bleibt bei 800 Wörtern; 1200 wird im Testlauf
gegengeprüft, statt größere Werte zu setzen.

Das Argument für große Chunks — weniger Nahtstellen, mehr Zusammenhang — ist
richtig. Aber die Grenze ist nicht das Kontextfenster, sondern die **Ausdauer
beim Generieren**: Ab etwa 2.000 Ausgabetokens fangen Modelle an zu raffen,
Nebensätze fallen weg, Beschreibungen werden knapper. 2.500 Quellwörter
bedeuten rund 3.500 Ausgabetokens.

Dazu kommt der Lost-in-the-middle-Effekt: Bei großen Chunks sackt die Qualität
im mittleren Drittel ab, und genau das sieht man beim Lesen nicht, weil man
oben anfängt.

Der wirksamere Hebel gegen Nahtstellen ist `context_words`, nicht
`chunk_words`.

## Nur vier Parameter sind sinnvoll verstellbar

**Entschieden:** `chunk_words`, `context_words`,
`temperature_uebersetzung`, `temperature_revision`. Alles andere bleibt.

`top_p`, `top_k`, `repeat_penalty` sind auf den Herstellerempfehlungen am
besten aufgehoben. `repeat_penalty` über 1,0 wäre bei einem Text mit bewussten
Wiederholungen sogar schädlich — es bekämpft genau das, was geschützt werden
soll.

Die Empfehlung für die vier leitet sich aus der Absatzstatistik ab
(Median-Absatzlänge, Dialoganteil, Satzlängenverteilung), nicht aus einer
Gattungsschublade.

## Zitate: lieber eine Lücke als ein erfundener Wortlaut

**Entschieden:** Lässt sich der Originalwortlaut eines Epigraphs nicht sicher
verifizieren, setzt die Pipeline einen **markierten Platzhalter** statt eines
Kandidaten.

Ein rückübersetztes Motto erzeugt einen Text, den der zitierte Autor nie
geschrieben hat. Das fällt bei einer Veröffentlichung sofort auf. Eine
sichtbare Lücke ist der geringere Schaden.

Eingesetzte Zitate sind zusätzlich vom Lektorat ausgenommen, und `qa.py` prüft
nach, ob sie unangetastet blieben.

## Der Anredecheck ist ein Näherungsmaß

**Entschieden:** `qa.py --konsistenz` zählt du/Sie-Formen im Umfeld jedes
Figurennamens über drei Buchdrittel und meldet Kippen. Der Bericht sagt selbst,
dass er Falschmeldungen produziert.

Wer wen duzt, ist per Muster **nicht** bestimmbar — dafür müsste bekannt sein,
wer in einer Passage zu wem spricht. Das leistet keine Regex. Die Näherung ist
trotzdem ein echtes Signal, aber sie darf nicht als Befund gelesen werden.

Die Leitmotivprüfung im selben Schritt ist dagegen exakt: Für jeden
festgelegten Wortlaut werden Sätze gesucht, die alle Inhaltswörter enthalten,
aber nicht die vorgeschriebene Formulierung.

## Kein litellm, sondern ein eigener Adapter

**Entschieden:** `gemeinsam.Backend` mit einer Unterklasse je Anbieter, rund
sechzig Zeilen.

litellm löst dasselbe Problem und mehr, ist aber eine große, schnell drehende
Abhängigkeit. Für eine Pipeline, die auf frisch gemieteten Instanzen laufen
muss, bedeutet das bei jedem Start ein `pip install` und die Hoffnung, dass die
aktuelle Version sich wie erwartet verhält. Der eigene Adapter hat keine
Überraschungen.

## Zwei GPU-Sitzungen mit einem Prüffenster

**Entschieden:** Alles Manuelle ist in ein Fenster gebündelt; die Instanz steht
währenddessen auf *Stop*.

Der Grund ist rein ökonomisch: GPU-Miete kostet 6,32 $/h, *Stop* kostet Cent.
Bei einem halben Tag Prüfzeit sind das 70–80 $.

**Dieser Punkt entfällt beim Wechsel auf API-Modelle.** Ohne Instanz gibt es
keine Stop/Destroy-Ökonomie, keinen GPU-Preflight und kein `num_ctx`-Limit. Die
Architektur wird dann deutlich einfacher, nicht komplizierter.

## API-Backends statt lokalem Hosting

**Entschieden (Juli 2026):** Alle textberührenden Pässe laufen über
`claude-opus-5`; Ollama bleibt als Rückfallpfad im Code.

Drei Gründe, in dieser Reihenfolge: Erstens Qualität — ein Frontier-Modell
gegen ein lokal gehostetes 128B-Modell ist bei literarischer Nuancierung
kein knapper Vergleich. Zweitens war das Vertraulichkeitsargument für
lokales Rechnen im eigenen Workflow längst aufgegeben: `export_glossar:
true` schickte den Volltext ohnehin extern. Drittens die Ökonomie: Der
komplette API-Volllauf kostet weniger als die bisherige GPU-Miete eines
einzelnen Laufs, bei Wegfall von Modell-Download, VRAM-Preflight und
Stop/Destroy-Verwaltung.

## Modellbelegung und Judge-Routing

**Entschieden:** Opus 5 übersetzt, revidiert und lektoriert. Urteile mit
Konsequenzen (Blindvergleiche der Testphasen, Variantenvergleich) fällt
`gemini-3.1-pro`; Massenaufgaben (Änderungsbegründungen, Screening)
erledigt `gemini-3.6-flash`. Opus prüft zusätzlich die Treue gegen das
Original — als nachrangiges Signal.

Ein Modell, das den eigenen Output benotet, bevorzugt ihn; dieselbe
Schwäche ist bei der lokalen Blindbewertung dokumentiert. Deshalb ist das
primäre Modellurteil ein Fremdmodell. Die Pro/Flash-Aufteilung folgt der
Konsequenz der Entscheidung, nicht dem Volumen: Die wenigen teuren Urteile
bekommen die Pro-Klasse (Mehrkosten unter einem Dollar), die hunderten
billigen Aufgaben das Flash-Modell. Erwartung ehrlich benannt: Der Mehrwert
der Judges ist indirekt — bessere Kalibrierungsentscheidungen, nicht
bessere Übersetzung.

## Gemini ohne Sampling-Parameter

**Entschieden:** Der `GeminiBackend` sendet keine `temperature`/`top_p`/
`top_k`; ein Selbsttestfall prüft das Payload.

Die Gemini-API ignoriert diese Parameter ab 3.6 Flash und soll bei
künftigen Generationen mit HTTP 400 antworten. Die vier verstellbaren
Pipeline-Parameter wirken damit nur auf Anthropic-Seite. Das ist kein
Fehler, sondern Anbieterverhalten — nicht umgehen, nicht „reparieren".

## Colab als Laufumgebung, unterbrechbar by design

**Entschieden:** Primärbetrieb in Google Colab; alle Daten leben im
Drive-Projektordner, Code kommt per `git pull` aus dem Repo in die VM.

Colab-Laufzeiten enden bei Inaktivität und haben harte Obergrenzen — das
ist bekannt und akzeptiert, weil das Design Abbrüche entwertet: Jeder Chunk
liegt sofort dauerhaft in Drive, der Resume zählt Dateien, ein Neustart ist
ein Klick im Runner-Notebook. `--hg` ist in Colab gesperrt, weil detachte
Prozesse in einer VM ohne Persistenz nichts bedeuten. Der VPS bleibt als
Rückfall dokumentiert; parallel betrieben wird er nicht.

## Sheets als Editieroberfläche, JSONs als generierte Artefakte

**Entschieden:** Referenzdaten werden im Google-Spreadsheet gepflegt;
`referenz_sync` validiert zeilengenau und erzeugt die JSONs, bevor
Modellkosten entstehen. Ohne `sheets_id` gilt der JSON-Direktbetrieb.

Rohe JSON-Dateien am Tablet zu editieren war die fehleranfälligste Stelle
des Workflows: ein verlorenes Komma, und `lade_json` verwirft still die
ganze Datei. Ein Tabellen-Tab macht Strukturfehler unmöglich und ist auf
Android ausgereift. Die Validierung bricht vor dem ersten API-Aufruf ab —
ein fünfstündiger Lauf ohne Glossar ist der teuerste stille Fehler der
Pipeline.

## Zitatübernahme nur nach menschlicher Freigabe

**Entschieden:** `zitatrecherche` ermittelt für niederländische Zitate die
etablierte deutsche Fassung mit Übersetzer und Fundstelle und schreibt eine
Review-Liste; eingesetzt wird nur, was ausdrücklich freigegeben ist.
Nicht-niederländische Zitate werden unverändert übernommen.

Etablierte Übersetzungen sind ihrerseits geschützt — die Abdruckfrage klärt
der Verlag, und dafür braucht er die Fundstelle, nicht nur den Wortlaut.
Der Grundsatz „lieber markierte Lücke als erfundener Wortlaut" bleibt für
alles Unverifizierte in Kraft.

## Rahmenwechsel als harte Chunkgrenze

**Entschieden:** An jeder `rahmen_marker`-Zeile (Standard `#`) endet der
Chunk, die Kontextrückschau wird zurückgesetzt, und der User-Prompt
benennt die Erzählebene aus dem Stilprofil.

Der konkrete Text wechselt zwischen Haupterzählung (dritte Person,
Präsens) und Rahmenerzähler (erste Person, Präteritum). Rollt die
Rückschau über diese Grenze, blutet Tempus und Person der einen Ebene in
die andere — genau die Fehlerklasse, die beim Lesen nicht auffällt. Die
Mechanik existierte bereits als Fugen-Reset der Testauszüge und wird nur
verallgemeinert.

## Keine Sampling-Parameter, auch nicht bei Anthropic

**Entschieden (31.07.2026):** Beide API-Backends senden weder `temperature`
noch `top_p` oder `top_k`. Ein Selbsttestfall prüft beide Payloads. Die
verstellbaren Parameter der API-Ära sind `chunk_words`, `context_words` und
`effort_<rolle>`.

Der Arbeitsauftrag ging davon aus, dass die Sampling-Parameter „nur auf
Anthropic-Seite" wirken. Das gilt seit `claude-opus-5` nicht mehr: Das Modell
hat `temperature`, `top_p` und `top_k` entfernt und antwortet darauf mit
HTTP 400 — dieselbe Eigenschaft, die für Gemini schon dokumentiert war. Damit
schrumpfen die vier verstellbaren Parameter im API-Betrieb auf zwei, und die
Steuerung der Denktiefe wandert vollständig zu `effort`.

Die Temperatur-Schlüssel bleiben trotzdem in der Konfiguration. Sie sind kein
toter Code, sondern der Ollama-Rückfallpfad, und wer sie entfernt, nimmt dem
VPS-Betrieb seine einzige Stellschraube für die Streuung.

Der Widerspruch wurde gemeldet und vor der Umsetzung entschieden, nicht still
aufgelöst.

**Am lebenden Objekt gemessen (31.07.2026):** `verifikation.py` schickt das
echte Payload einmal mit `temperature` an beide APIs. Die Antworten fallen
unterschiedlich aus, und das ist der Grund, warum diese Notiz hier steht:

- `claude-opus-5` antwortet mit **HTTP 400**. Der Parameter ist entfernt.
- `gemini-3.1-pro-preview` antwortet mit **HTTP 200** und ignoriert ihn.

Die Doktrin gilt für beide, aber aus verschiedenen Gründen: bei Anthropic
scheitert der Aufruf, bei Google wirkt er nur nicht — bis eine künftige
Generation ebenfalls mit 400 antwortet. Wer die Gemini-Seite später
„repariert", indem er `temperature` wieder einbaut, bekommt kein
Fehlersignal und glaubt, es hätte Wirkung. Genau davor steht dieser Absatz.

Die Messung läuft bei jeder Verifikation mit und meldet, wenn ein Anbieter
seine Haltung ändert.

## Der Judge heißt `gemini-3.1-pro-preview`, nicht `gemini-3.1-pro`

**Entschieden (31.07.2026):** `modell_judge` trägt den API-Namen
`gemini-3.1-pro-preview`. Die Rolle und die Begründung dahinter ändern sich
nicht — es ist dasselbe Modell, das der Arbeitsauftrag benennt.

Der Preisname und der API-Name fallen bei Google auseinander: Die Preisseite
führt das Modell als `gemini-3.1-pro`, `ListModels` kennt unter `v1beta` nur
`gemini-3.1-pro-preview`. Ein Aufruf unter dem Preisnamen antwortet mit
HTTP 404. Aufgefallen ist das im Colab-Lauf der Verifikation, nicht beim
Lesen — die Payloadtests gegen Attrappen können einen Namen nicht prüfen,
den nur der Anbieter kennt.

Zwei Folgen, die bewusst so stehen:

- **Das Modell ist ein Preview.** Preview-Namen können verschwinden oder in
  die allgemeine Verfügbarkeit umziehen (dann vermutlich ohne Suffix). Der
  Preflight wertet ein 404 deshalb als Fehler und nicht als Warnung: Der
  Lauf soll an der Stelle stehenbleiben, an der der Name falsch wird, und
  nicht Stunden später bei der Bewertung.
- **Auf die Pro-Klasse wird nicht verzichtet.** Naheliegend wäre gewesen,
  auf ein allgemein verfügbares Flash-Modell auszuweichen. Das würde die
  Pro/Flash-Aufteilung aushebeln, deren ganzer Punkt ist, dass die wenigen
  folgenreichen Urteile die stärkere Klasse bekommen.

`TARIFE` trägt beide Schlüssel, damit der Preisbeleg und der benutzte Name
nebeneinander stehen.

## Kalibrierungen gelten je Modell-Ära

**Entschieden:** `revision_pass`, `lektorat_passes` und `chunk_words`
werden unter Opus 5 im Testlauf neu entschieden; die Mistral-Messwerte
sind Ausgangspunkt, nicht Ergebnis.

Die Abschaltgründe (Revision erzeugte Tempusfehler, das Korrektorat fand
nichts und beschädigte trotzdem) und die 800-Wörter-Begründung („Ausdauer
beim Generieren") sind Messungen über ein bestimmtes Modell. Ein anderes
Modell verdient eine neue Messung — die Mechanik dafür (Testlauf,
Variantenvergleich) existiert und kostet im Testauszug wenige Dollar.
Dazu gehört der einmalige Fable-5-Vergleich: lieber einmal messen, ob die
Mythos-Klasse bei diesem Text sichtbar besser übersetzt, als es dauerhaft
zu vermuten.

---

## Verworfen — und warum

**API-Frontier-Modell als Primärübersetzer** (zunächst). Die Kostenrechnung
sprach dafür, die Entscheidung fiel trotzdem für lokales Hosting. Beim Wechsel
gilt: Die `chat()`-Abstraktion ist dafür gebaut, der Eingriff ist klein.
→ Juli 2026 umgesetzt; siehe „API-Backends statt lokalem Hosting".

**Parallelisierung der Lektoratspässe.** Der Vorschlag war, als Kontext den
*unbearbeiteten* Vorgänger-Chunk zu nehmen, weil der von Anfang an vorliegt.
Das untergräbt aber genau den Mechanismus: Der Wert der Rückschau liegt darin,
dass das Lektorat sieht, wie es selbst eine wiederkehrende Wendung behandelt
hat. Mit dem unbearbeiteten Vorgänger ist die Konsistenz weg. Auf einer
einzelnen GPU wäre der Gewinn ohnehin bescheiden, weil Ollama serialisiert.

**Modell-Heterogenität** (verschiedene Modelle für Übersetzung und Lektorat).
Die Begründung ist gut — dekorrelierte Fehlerprofile sind ein billiger
Qualitätshebel. Ohne API scheitert es an der Praxis: Modellwechsel pro Chunk
kostet zwei bis drei Minuten Ladezeit, passweise Wechsel bräuchte ein zweites
Modell auf der Platte. **Beim Wechsel auf API wird das wieder interessant.**
→ Juli 2026 in abgewandelter Form umgesetzt: nicht für die textberührenden
Pässe (alle Opus 5), sondern als Fremd-Judge-Routing; siehe „Modellbelegung
und Judge-Routing".

**DeepL als Primärengine.** Ohne System-Prompt-Steuerung wären Stimmschutz,
Diminutivpolitik und Tempusanweisung nicht durchsetzbar — der gesamte
Prompt-Apparat wäre wirkungslos.

**LangGraph oder Snakemake als Orchestrator-Unterbau.** Der schlanke
Zustandsansatz plus `pipeline.py` ist wartbarer als ein Framework-Umbau. Make
kann Resume *innerhalb* eines Schritts nicht abbilden, und genau das brauchen
Chunk-Läufe.

**Kontextfenster hochsetzen, um den ganzen Text auf einmal zu verarbeiten.**
Messungen zeigen, dass Modelle 30–40 % vor ihrer angegebenen Grenze einbrechen
und der Abfall plötzlich statt allmählich erfolgt. Ein größeres Fenster löst
das Problem nicht, es verschiebt es.
