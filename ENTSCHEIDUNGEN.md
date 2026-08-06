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

## Tarife werden geholt, aber nur Eindeutiges übernommen

**Entschieden:** `tarife.py` liest die Preisseiten beider Anbieter und schreibt
`tarife.json` — aber nur, wenn im Umfeld des Modellnamens **genau zwei**
Beträge stehen und der kleinere die Eingabe ist. Alles andere wird gemeldet,
der hinterlegte Wert bleibt.

**Keiner der beiden Anbieter veröffentlicht eine Preis-API.** Es gibt HTML für
Menschen, und das ändert jederzeit sein Layout. Ein Auslesen daraus ist eine
Schätzung über eine Textstelle, keine Auskunft. Drei oder mehr Beträge in der
Nähe bedeuten fast immer, dass die Seite Stufen oder Cache-Preise mitführt —
da wird nicht geraten.

Ein vertauschtes Paar (Eingabe teurer als Ausgabe) gilt ausdrücklich als
unklar. Vertauscht ist schlimmer als unbekannt: Unbekannt schreibt „Tarif
unbekannt" in den Bericht, vertauscht schreibt eine falsche Zahl, die niemand
nachrechnet.

`gemeinsam.TARIFE` bleibt die dokumentierte Grundlage; `tarife.json` hat
Vorrang und trägt Quelle und Datum. Geholt wird höchstens einmal pro Woche —
Preise ändern sich nicht täglich, und kein Lauf soll an zwei fremden Servern
hängen.

## Annotation berichtet — und kann gar nicht editieren

**Entschieden:** `annotation.py` schreibt ausschließlich `begruendungen.json`
und `screening_review.md`. Jeder Schreibzugriff geht durch `schreiben()`, und
die Funktion wirft `SchreibSperre`, wenn das Ziel nicht in `SCHREIBBAR` steht.

Die Sperre ist kein Misstrauen gegen den Code von heute, sondern gegen den von
übermorgen. „Der Schritt ist rein berichtend" ist eine Absichtserklärung; sie
hält genau so lange, bis jemand eine naheliegende Zeile ergänzt, die den
gefundenen Fehler gleich behebt. Dann ist aus dem Bericht ein dritter
Editierpass geworden — und der glättet, wie jeder Pass glättet.

Der Selbsttest versucht deshalb, mit `schreiben()` auf `input.txt`,
`uebersetzung_deutsch.txt`, `manuskript_lektoriert.txt`, `lektorat_diff.txt`
und `projekt.json` zuzugreifen, und verlangt fünfmal eine Ausnahme. Die
Gegenprobe mit ausgehängter Sperre meldet alle fünf.

**Typografie und Interpunktion werden nicht annotiert.** Sie stammen aus dem
deterministischen Durchgang, und ihre Begründung wäre „so ist die Regel" —
eine Zeile, die niemand liest, in einer Liste, die dadurch unleserlich wird.

Die Kennung je Änderung ist ein Hash aus Chunk, Kategorie und beiden
Wortlauten. Sie muss stabil sein: Sonst sind nach dem zweiten Lauf alle
Begründungen verwaist, und man bezahlt sie erneut.

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

**Nachtrag August 2026 — die Voraussetzung trug nicht.** Der ganze Mechanismus
setzt voraus, dass der Autor die Ebenenwechsel ausgezeichnet hat. Beim Buch
1919 tat er das nicht:

| | |
|---|---|
| Erzählebenen in `stilprofil.json` | 5, mit drei verschiedenen Tempora |
| Gruppen, die der Marker `#` fand | **1** |
| Chunks | 147 |

Die deutsche Rückschau lief also über **jeden** Ebenenwechsel hinweg — genau
der Fehler, gegen den die Regel geschrieben ist, ausgelöst durch ihre eigene
Voraussetzung. Und er ist nirgends aufgefallen: Die Perfektquote in `qa.py` ist
buchweit, also ein Mittelwert über Ebenen, die sich unterscheiden **sollen**.
Ein Präsens-Rahmen mit Präteritum-Einschlag und ein Präteritum-Rückblick mit
Präsens-Einschlag mitteln sich zu einem unauffälligen Wert.

Die Antwort ist `ebenen.json` (siehe unten). Der Marker bleibt als Rückfall —
ein Text, der seine Wechsel auszeichnet, braucht keinen Modellaufruf.

## Der Variantenvergleich bleibt dauerhaft, die Modellvariante nicht

**Entschieden:** `varianten` steht in der Vorlage auf einer einzigen
Chunkgrößen-Variante. Eine Modellvariante wird bewusst hinzugefügt, wenn es
etwas zu prüfen gibt.

Die Begründung liegt in der Art der Frage. **Die beste Chunkgröße hängt vom
Text ab** — Dialoganteil, Absatzlänge, Satzbau unterscheiden sich von Buch zu
Buch, und die Antwort für das eine gilt nicht fürs nächste. Deshalb läuft
diese Variante bei jedem Buch mit; sie kostet unter einem Dollar auf dem
Testauszug.

**Ob ein anderes Modell besser übersetzt, hängt dagegen nicht vom Buch ab,
sondern von der Modellgeneration.** Diese Frage stellt man, wenn ein neues
Modell erscheint, nicht bei jedem Titel. Und sie ist die teure: Der
Fable-5-Vergleich kostete 2,66 $ gegen 1,04 $ der Basis — aufs Buch
hochgerechnet 97 $ gegen 38 $.

Ein Test, dessen Ergebnis niemand liest, ist schlechter als kein Test: Er
kostet Geld und erzeugt den Anschein von Sorgfalt. Die Sicherung dagegen ist
`PAUSE_pruefung` — der Lauf hält an, und `bewertung_varianten.md` liegt dort,
wo entschieden wird.

**Der Vergleich beurteilt Erzählung und Dialog getrennt.** Die erste Fassung
übergab dem Judge nur die Erzählpassage. Bei NL→DE liegt die Schwäche im
Dialog, wo Anredeform, Modalpartikeln und Diminutive zusammentreffen — ein
Vergleich ohne ihn beantwortet die Frage zur Hälfte und sieht vollständig aus.

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

Die Temperatur-Schlüssel blieben zunächst in der Konfiguration, weil sie den
Ollama-Rückfallpfad bedienten. → Mit dem Rückzug dieses Pfads (August 2026)
sind sie entfallen; siehe „Ollama-Rückfallpfad zurückgezogen".

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

→ Gemessen im August 2026 am Buch 1919; die drei Ergebnisse stehen im
nächsten Eintrag.

## Gemessen unter Opus 5 (August 2026, Buch 1919)

Die drei Werte, die die Migration offengelassen hatte. Alle Zahlen stammen
aus Läufen an diesem Buch — sie gelten für diesen Text und diese
Modellgeneration, nicht als Naturgesetz.

### `revision_pass` bleibt an

**95 Änderungen zwischen Entwurf und Revision, davon 94 substanziell (99 %),
eine einzige Interpunktion.** Das Abschaltkriterium lautet „Änderungen
überwiegend Typografie" — hier ist es das genaue Gegenteil. Das Fremdurteil
ging 3:1 für die Revision.

Was der Durchgang tatsächlich repariert hat: `nicht detonierte Granaten` →
`Blindgänger`, `Grammofonspieler` → `Grammofon` (falscher Freund),
`Toilettenhäuschen` → `Toilettenhaus` (Diminutivpolitik durchgesetzt), und
`keine Ahnung` → `keine blasse Ahnung` — das Leitmotiv wiederhergestellt.

**Unter Mistral erzeugte dieser Pass Tempusfehler; unter Opus 5 räumt er
Terminologie und falsche Freunde auf. Das ist nicht derselbe Durchgang.**

Preis: 18,22 $ gegen 17,71 $ der Übersetzung selbst — die Revision kostet
mehr als das, was sie überarbeitet, weil sie denselben Text noch einmal
vollständig ausgibt.

### `lektorat_passes` bleibt `det → stil → korrektorat → det`

**55 Änderungen im Testlektorat: 86 % Wort und Wendung, 11 % Interpunktion,
4 % Teilsatz.** Der Mistral-Wert war 94 % Typografie. Auch hier hat sich die
Lage umgedreht.

Die Registerkontrolle blieb im Testlektorat stabil, im Volllauf jedoch nicht:
**verkürzte Formen 45 → 29 (−36 %)**, verteilt auf `halt`, `grad` und `nich`.
Das ist die eine Stelle, an der das Lektorat die Erzählstimme angehoben hat —
kein Grund abzuschalten, aber der Grund, warum diese Messung im Bericht steht.

### `chunk_words` bleibt bei 800 — für dieses Buch

| | A (800) | B (1600) |
|---|---:|---:|
| Fremdurteil | **3** | 1 |
| davon „deutlich" | 2 | 0 |
| Wörter | 2958 | 2947 |
| Absätze | 74 | 74 |
| Kosten | 1,04 $ | 0,85 $ |

B ist nicht kaputt: kein Textverlust, gleiche Absatzzahl, kein Raffen. **Die
Befürchtung aus der Mistral-Ära bestätigt sich bei 1600 Wörtern nicht.** Aber
B ist auch nirgends besser, und beide „deutlich"-Urteile fallen für A.

Die Entscheidung ruht auf **„kein nachweisbarer Vorteil"**, nicht auf
„nachweislich schlechter": Vier Paarurteile sind eine kleine Stichprobe, 3:1
kein starkes Signal. Die Beweislast lag bei der Änderung, und sie ist nicht
erbracht. Der Preisvorteil von 18 % — aufs Buch rund 7 $ — wiegt ein Urteil
nicht auf, das in die andere Richtung zeigt.

**Das gilt für 1919, nicht für das nächste Buch.** Die beste Chunkgröße hängt
vom Text ab; deshalb bleibt die Variante in der Vorlage und wird jedes Mal neu
gemessen.

### Fable 5: verworfen

| | A (Opus 5) | C (Fable 5) |
|---|---:|---:|
| Fremdurteil | **2** | 1 (+1 gleichwertig) |
| Kosten | 1,04 $ | **2,66 $** |

Kein Vorteil bei 2,6-fachem Preis — aufs Buch hochgerechnet 97 $ gegen 38 $.
Nebenbei: höherer Perfektanteil (13,1 % gegen 12,4 %) und mehr Diminutive
(2,0 gegen 1,7 je 1000), beides einen Tick weiter weg von der Projektpolitik.

Damit ist der einmalige Vergleich, den der Arbeitsauftrag verlangt, erledigt.
Er wird nicht dauerhaft mitgeführt: Ob ein anderes Modell besser übersetzt,
hängt von der Modellgeneration ab, nicht vom Buch.

### Was diese Messung nicht abdeckt

Die Chunkgrößen- und Modellurteile stammen aus der **Erzählpassage**. Der
Dialogvergleich ist seit August 2026 eingebaut, lief aber für diese Messung
noch nicht mit. Bei NL→DE liegt die Schwäche im Dialog — wer 1600 Wörter
ernsthaft erwägt, misst dort nach.

## Ollama-Rückfallpfad zurückgezogen

**Entschieden (August 2026):** `OllamaBackend`, die Schlüssel `backend`,
`modell`, `ollama_host`, `num_ctx`, `timeout_read` und die vier
`temperature_*` sind entfernt. `chat()` nimmt keine Sampling-Parameter mehr
entgegen. Eine Rolle ohne `modell_<rolle>` bricht ab, statt still zu ersetzen.

Der Pfad war als Versicherung gedacht: identischer Code auf einem nackten VPS,
falls Colab oder die APIs ausfallen. Nach einem Jahr ist die Bilanz eine
andere. **Er wurde nie ausgeführt und nie geprüft** — kein Selbsttestfall
konnte ihn abdecken, weil er einen laufenden Ollama-Server braucht. Ein
Rückfallpfad, den niemand prüft, ist keine Versicherung, sondern eine
Behauptung.

Dazu kam, was er kostete: acht Konfigurationsschlüssel, die in `projekt.json`
ganz oben standen und einem Leser als Erstes einen Mistral-Namen auf einem
lokalen Port zeigten — während in Wahrheit Opus 5 lief. Ein Parameter
(`temperature`) in jeder der zehn `chat()`-Aufrufstellen, der auf beiden
tatsächlich genutzten APIs wirkungslos ist. Zwei Preflight-Prüfungen für eine
GPU, die es nicht gibt.

**Der stille Ersatz war das eigentliche Argument.** `modell_fuer()` fiel bei
fehlendem Rolleneintrag auf `cfg["modell"]` zurück. Eine vergessene Zeile in
`projekt.json` hätte damit nicht zu einem Abbruch geführt, sondern zu einem
Lauf gegen ein anderes Modell — bemerkbar erst am Kostenbericht. Genau diese
Fehlerklasse hat bei der Auswertung des 1919-Laufs schon einmal zwei Stunden
gekostet.

Der VPS-Betrieb bleibt möglich: derselbe Code, dieselben API-Schlüssel als
Umgebungsvariablen, ohne Colab. Was entfällt, ist der Betrieb *ohne* API.

## Ein Paket darf installiert werden

**Entschieden (August 2026):** Die Regel „Kein `pip install` im Normalbetrieb"
gilt weiterhin — mit genau einer benannten Ausnahme: `anthropic`, die SDK des
Anbieters, auf Hauptversion festgelegt, in der Einrichtungszelle des Runners.

Die Regel entstand gegen litellm, und diese Ablehnung bleibt bestehen: eine
große, schnell drehende Abhängigkeit mit eigenem Abhängigkeitsbaum, bei der
jeder Start die Hoffnung mitbringt, dass die aktuelle Version sich wie erwartet
verhält. Die Hersteller-SDK ist etwas anderes — ein Paket, vom Anbieter
gepflegt, mit dem die API selbst dokumentiert wird.

Was sie bringt, ist nicht Bequemlichkeit: Streaming ohne handgeschriebenen
SSE-Parser, exakte Tokenzählung statt eines Schätzfaktors, strukturierte
Ausgaben statt fünf handgeschriebener JSON-Parser, und den Stapel-Adapter.

Die Bedingung, um die es der Regel eigentlich ging, bleibt gewahrt: Fehlt der
Import, läuft der `requests`-Pfad unverändert weiter. Ohne jede Installation
lauffähig zu sein ist damit weiter gegeben.

---

## Kosten werden je Lauf, Rolle und Modell gebucht

**Entschieden (August 2026), Widerruf der Buchung je Rolle.** `manifest.json`
summierte Token unter dem Rollennamen allein und schrieb bei jedem Aufruf das
zuletzt benutzte Modell in denselben Eintrag. Ein Testlauf mit einem anderen
Modell hat damit die gesamte Rolle auf dieses Modell umetikettiert — Token aus
zwei Modellen in einer Zeile, bewertet mit dem Preis des zuletzt benutzten.

Was das gekostet hat: Der Lauf 1919 wies **109,52 $** aus. Die Rollen
`uebersetzung` und `revision` liefen mit `claude-opus-5`; ein Vergleichslauf am
Testauszug mit `claude-fable-5` (10 $ / 50 $ statt 5 $ / 25 $) hat beide Zeilen
umbeschriftet und den Preis verdoppelt. Der wahre Wert liegt bei rund
**69,7 $**. Die Buchung hat also um 57 % nach oben getäuscht — und zwar in
genau der Zahl, an der Kalibrierungsentscheidungen hängen.

Der Beleg: Für die Buchproduktion sagt die Buchung mit Opus-Tarif 39,81 $ für
`uebersetzung` plus `revision`. Das deckt sich mit der Vorabschätzung von 38 $
in „Gemessen unter Opus 5"; mit Fable-Tarif wären es 79,62 $ — eine Zahl, die
dort nie stand.

Seither ist der Buchungsschlüssel `lauf/rolle/modell`. Der Lauf kommt aus dem
Ausgabepräfix (`''`, `test/`, `testB/`), damit die Zuordnung an derselben
Stelle steht wie die Dateiablage. Testläufe erscheinen in der Übersicht
getrennt: Sie kosten Geld, aber sie gehören nicht in den Preis des Buches.

Zwei Dinge, die daran hängen und nicht wieder auseinanderlaufen dürfen:

- **Eine Preisformel für alle Auswertungen** (`gemeinsam.kosten_dollar`). Die
  Variantenkosten in `bewertung.py` rechneten ohne Cache und lagen dadurch zu
  niedrig — zwei Formeln waren zwei Wahrheiten.
- **Altes Format bleibt lesbar.** Ein Manifest ohne Laufkennung wird gezeigt,
  aber unter „Lauf nicht zugeordnet" — es behauptet nicht, die Buchproduktion
  gewesen zu sein.

Der Selbsttest hält den Fall fest: zwei Buchungen derselben Rolle mit
verschiedenen Modellen müssen zwei Zeilen ergeben, nicht eine.

---

## Cache-Lebensdauer eine Stunde — als Versicherung, nicht als Ersparnis

**Entschieden (August 2026).** `cache_ttl: "1h"` in `projekt.json`.

Zuerst die Zahl, die *gegen* die naheliegende Begründung spricht. Die
Vermutung war, die Trefferquote des Prompt-Caches sei niedrig und eine längere
Lebensdauer bringe Geld. Der Lauf 1919 sagt etwas anderes:

| Rolle | gelesen | geschrieben | Trefferquote |
|---|---|---|---|
| `uebersetzung` | 901 965 | 36 131 | 96 % |
| `revision` | 677 380 | 28 001 | 96 % |

Bei 154 beziehungsweise 147 Aufrufen sind das rund sechs Neuschreibungen je
Rolle — genau die Zahl der Colab-Sitzungen, in denen das Buch entstanden ist.
Der Cache ist also nicht abgelaufen, er wurde kalt gestartet. Die Ersparnis
liegt bereits bei 13,10 $, rund 16 % der Rechnung. **Als Kostenmaßnahme ist
die Stunde damit verworfen.**

Was bleibt, ist der Grund, aus dem sie trotzdem gesetzt wird: Sie ist eine
Versicherung gegen alles, was den Abstand zwischen zwei Chunks über fünf
Minuten treibt — größere Chunks, ein langsamer Durchgang, ein Blick in den
Zwischenbericht, eine Wartezeit im Stapelbetrieb. Tritt das nicht ein, kostet
sie fast nichts; tritt es ein, spart sie das Neuschreiben des ganzen Präfixes.

Der Preis ist bekannt und wird jetzt auch richtig abgerechnet: Schreiben mit
einer Stunde Lebensdauer kostet das Doppelte des Eingabepreises statt des
1,25-fachen. Die Antwort liefert die Aufschlüsselung (`cache_creation`), und
`kosten_dollar` rechnet beide Anteile getrennt — geschätzt wird nichts.

**Sie darf keinen Lauf abbrechen.** Lehnt der Anbieter die Lebensdauer ab
(HTTP 400 mit `ttl` in der Meldung), meldet der Lauf das einmal und läuft ohne
sie weiter. Die Erkennung ist bewusst eng gefasst: Ein zu weiter Fang würde
echte Payloadfehler verschlucken und still ein zweites Mal Geld ausgeben. Der
Selbsttest hält drei Gegenproben dagegen (`temperature`-Fehler, 429, 500).

---

## Die Modellwahl bekommt eine Stelle: `EMPFEHLUNG` und `pipeline.py modelle`

**Entschieden (August 2026).** Modell und Denktiefe stehen je Rolle in
`projekt.json`; die **Empfehlung samt Begründung** steht in
`gemeinsam.EMPFEHLUNG`, und `pipeline.py modelle` stellt beides
nebeneinander — dazu, was die Rolle im letzten Lauf wirklich gekostet hat.

Die Begründung steht bewusst im Code und nicht in einer Doku. Wer die
Belegung ändert, liest sie genau in dem Moment, in dem es darauf ankommt.
Eine Empfehlung ohne Begründung ist eine Zahl, die man entweder befolgt oder
ignoriert; mit Begründung ist sie eine Entscheidung, die man nachvollziehen
und begründet verwerfen kann. Abweichen ist vorgesehen —
`technik_ausnahmen` hält die Abweichung fest, damit `pipeline.py technik`
sie stehen lässt.

Der Befehl schreibt nichts. Ein Kommando, das die Modellwahl eines
laufenden Buchs verstellen kann, wird irgendwann versehentlich getippt.

**`effort` wirkt nur bei Anthropic-Modellen.** Gemini bekommt den Schlüssel
gar nicht erst geschickt. `effort_screening` zu ändern hat dort keine
Wirkung, und das gehört dazugesagt (`EFFORT_WIRKT`), statt dass jemand
daran dreht und auf eine Änderung wartet.

### Drei geänderte Voreinstellungen

| Rolle | vorher | jetzt | Grund |
|---|---|---|---|
| `korrektorat` | `claude-opus-5` / `hoch` | `claude-sonnet-5` / `mittel` | Regelanwendung, kein Sprachgefühl — und der Pass läuft über das ganze Buch |
| `vorbereitung` | `claude-opus-5` / `hoch` | `claude-fable-5` / `sehr_hoch` | Neun Aufrufe, an denen alles Spätere hängt; der Aufpreis fällt nicht ins Gewicht, ein Fehler dort steht in jedem Chunk |
| `screening` | (war `annotation`) | `gemini-3.1-pro-preview` / `hoch` | Fremdurteil ist nur eines, wenn es von einem anderen Anbieter kommt |

Für `korrektorat` steht die Messung **aus**. Wird der Diff dünn oder greift
er daneben, zurück auf `claude-opus-5` — das ist der eine Wert dieser Liste,
der auf einer Vermutung beruht statt auf einer Zahl.

---

## `annotation` war eine Rolle für zwei Arbeiten

**Entschieden (August 2026), Widerruf der gemeinsamen Rolle.** Der Schritt
`annotation.py` liefert zwei Berichte, und sie haben nichts miteinander zu
tun außer dem Zeitpunkt:

- **Begründungen** — eine Zeile je Lektoratsänderung, zwanzig Stück je
  Aufruf, rein berichtend. Der Leser überfliegt sie.
- **Screening** — liest das ganze Buch gegen das Original und sucht, was
  vier Durchgänge übersehen haben. Das ist die eigentliche
  Qualitätsprüfung.

Unter einer Rolle gab es nur zwei Möglichkeiten, und beide sind falsch: den
Preis der Prüfung für die Massenware zahlen, oder mit dem Modell der
Massenware prüfen. Der Lauf 1919 hat das Zweite getan — 61 Aufrufe
`gemini-3.6-flash` für beides.

Seither sind es `begruendung` und `screening`, mit eigenem Modell und
eigener Tiefe. Der Selbsttest prüft, dass sie wirklich getrennt routen;
sonst wäre die Trennung Kosmetik.

**Ein entfallener Schlüssel bleibt stehen.** `projekt.json` wird nie
überschrieben, also wirkt `modell_annotation` in einem laufenden Projekt
einfach nicht mehr — ohne dass etwas kaputtgeht und ohne dass es auffällt.
`preflight.ENTFALLEN` sammelt diese Schlüssel und meldet sie mit dem Namen
ihres Nachfolgers. Dieselbe Liste trägt die Reste des Ollama-Rückzugs und
die Temperatur-Schlüssel.

---

## Strukturierte Ausgaben: nur die Zitatrecherche, und das ist kein Versehen

**Entschieden (August 2026).** `output_config.format` mit JSON-Schema wird an
genau einer Stelle benutzt: `zitatrecherche.py`. Der Mechanismus ist allgemein
gebaut (`G.chat(..., schema=…)`), angewendet wird er dort — und die Begründung
für das *Nicht*-Anwenden ist der eigentliche Inhalt dieser Entscheidung.

**Das unterstützte Schema-Subset verlangt `additionalProperties: false`.** Damit
lassen sich nur Objekte mit **fester Schlüsselliste** ausdrücken. Sieben der
acht Vorbereitungslieferungen sind aber offene Abbildungen:

| Lieferung | Form | ausdrückbar? |
|---|---|---|
| `glossar` | niederländisches Wort → deutsches Wort | nein |
| `personen` | Figurenname → Pronomen | nein |
| `kapitel` | Überschrift im Quellwortlaut → Zusammenfassung | nein |
| `figurenblatt`, `anrede`, `leitmotive` | Name/Wendung → Objekt | nein |
| `stilprofil` | feste Schlüssel — aber `perspektive` ist wieder offen | nein |
| Zitatbefund | `sprache`, `status`, `vorschlag_de`, … | **ja** |

Die naheliegende Reaktion wäre, die Lieferungen als Listen von
`{schluessel, wert}`-Objekten zu modellieren. Das ist verworfen: Die JSONs
werden von Menschen gelesen und im Spreadsheet gepflegt, und eine Abbildung, die
als Liste von Paaren daherkommt, ist an beiden Stellen schlechter. Der Gewinn
wäre auch klein — die **Formprüfung je Lieferung** fängt eine falsche Form
bereits ab, und zwar bevor geschrieben wird. Ein Schema würde sie nicht
ersetzen: Es garantiert die Form, nicht den Inhalt.

Warum gerade die Zitatrecherche: Dort ist eine unlesbare Antwort am teuersten.
Sie hieß bisher, dass das Zitat übersprungen wird — und ein übersprungenes Zitat
ist eine Lücke, die später jemand von Hand sucht. Feste Schlüssel hat der Befund
ohnehin.

**Gemini bekommt kein Schema.** Der Anbieter spricht einen anderen Dialekt
(OpenAPI-Subset statt JSON Schema); ein durchgereichtes Schema wäre dort ein
HTTP 400. `G.chat` meldet das einmal und läuft ohne — dieselbe Haltung wie bei
den serverseitigen Werkzeugen. Der Selbsttest prüft beide Richtungen.

**Der Parser bleibt überall.** Ohne Schlüssel, auf einem anderen Anbieter oder
wenn ein Modell die Form künftig nicht mehr erzwingt, trägt er weiter. Ein
Schema ist eine Zusicherung, keine Ersetzung.

`gemeinsam.schema_maengel()` hält das Subset fest und meldet, was der Anbieter
ablehnen würde — offene Abbildungen, fehlendes `required`, Zahl- und
Längengrenzen. Ein Schema, das erst im Lauf abgelehnt wird, kostet den Schritt
**nach** dem Bezahlen.

---

## Der Tab `Modelle` wird geschrieben und nie gelesen

**Entschieden (August 2026).** `referenz_sync.py --modelle` spiegelt die
Modellbelegung ins Spreadsheet — Rolle, Ist-Modell, Tiefe, Empfehlung,
Begründung und was die Rolle im letzten Lauf gekostet hat. Zurückgelesen wird
der Tab **nicht**.

Der naheliegende Wunsch ist, ihn editierbar zu machen: Referenzdaten werden im
Spreadsheet gepflegt, warum nicht auch die Modellwahl? Weil die beiden nicht
dasselbe sind. **Modellnamen sind Code-Daten** — sie stehen in
`gemeinsam.TECHNIK` und wandern mit dem Repo, damit eine Umbenennung beim
Anbieter alle Bücher erreicht. **Referenzdaten sind Projektdaten** und wandern
mit dem Buch.

Ein zurückgelesener Tab machte daraus eine **dritte Quelle** neben
Repo-`projekt.json` und Projekt-`projekt.json`. Bei drei Quellen weiß niemand
mehr, welcher Wert gilt — und `pipeline.py technik` könnte einen im Repo
korrigierten Modellnamen nicht mehr nachziehen, weil der Tab ihn beim nächsten
Sync wieder überschreibt.

Die Sichtbarkeit, um die es ging, bleibt: Die Belegung steht im Spreadsheet
neben Glossar und Figurenblatt, und die letzte Zeile des Tabs sagt, dass
Änderungen dort nicht wirken. Geändert wird in `projekt.json`; `pipeline.py
modelle` zeigt dasselbe im Terminal.

Der Selbsttest hält drei Dinge fest: `Modelle` steht nicht in `TABS` (sonst
läse `sync` ihn zurück), nicht in `OPTIONAL`, und ohne `sheets_id` schreibt der
Schritt gar nichts — der Rückfallpfad bleibt unberührt.

---

## `ebenen.json`: die Erzählebenen aus dem Text lesen, nicht aus dem Marker

**Entschieden (August 2026).** Eine neunte Vorbereitungslieferung findet die
Ebenenwechsel im Quelltext und schreibt sie nach `ebenen.json`. Ist die Datei
da, bestimmt sie die Chunkgruppen; sonst gilt weiter der `rahmen_marker`.

Der Grund steht im Nachtrag zu „Rahmenwechsel als harte Chunkgrenze": Beim Buch
1919 fand der Marker über 147 Chunks **eine** Gruppe, obwohl das Stilprofil fünf
Ebenen mit drei Tempora beschreibt. Für das nächste Buch ist die Annahme, dass
`input.txt` keine Marker trägt.

### Warum Textanfänge und keine Absatznummern

Ein Eintrag ist `{"beginn": …, "ebene": …}`; `beginn` sind die ersten Wörter des
Absatzes **im Wortlaut der Quelle** — dieselbe Idee wie bei den Überschriften in
`kapitel.json`. Absatznummern wären kürzer und wären beim ersten korrigierten
Absatz **alle** falsch. Ein `beginn`, der im Text nicht vorkommt, wird gemeldet
und die Datei gar nicht erst geschrieben: Die Fuge säße sonst am falschen
Absatz, und das ist schädlicher als eine fehlende Fuge.

### Warum ein eigener Aufruf mit eigenem Prompt

Die anderen acht Lieferungen lesen das Analysepaket, das im System-Prompt steht
und ab dem zweiten Aufruf zwischengespeichert ist. Diese liest den **Quelltext**
— sie träfe den Cache ohnehin nicht, und stünde sie in `LIEFERUNGEN`, zerstörte
ihr abweichender System-Prompt das Präfix der anderen acht.

Gegeben werden nicht die 118.000 Wörter, sondern die **ersten zwölf Wörter jedes
Absatzes**, durchnummeriert — ein Zwanzigstel des Buches, rund 4.800 Wörter bei
1.176 Absätzen. Ein Ebenenwechsel ist am Absatzanfang sichtbar: neue Szene,
neues Tempus, neue Zeitangabe. Was dadurch nicht gesehen wird, ist ein Wechsel
mitten im Absatz — den gäbe es aber auch als Chunkgrenze nicht, weil
Absatzgrenzen Vorrang haben.

### Modellwahl: abweichend vom Plan

Der Plan sah `gemini-3.6-flash` vor. Die Empfehlung steht auf
`claude-opus-5`/`hoch`, weil das Ergebnis **jede** Chunkgrenze und jeden
Rückschau-Reset des Buches bestimmt und der Unterschied unter einem halben
Dollar für ein ganzes Buch liegt — 0,11 $ gegen 0,03 $. Das ist die falsche
Stelle zum Sparen. Die Messung steht aus; `pipeline.py modelle` zeigt beides
nebeneinander.

### Was sich daran ändert, was nicht

- **`qa.py` misst das Tempus je Ebene**, nicht mehr nur buchweit, und warnt,
  wenn sich die Ebenen **nicht** unterscheiden. Genau dafür gibt es die Fugen.
- **`preflight` meldet den Fall 1919**: mehrere Ebenen im Stilprofil, aber keine
  `ebenen.json` und kein Marker im Text. Ohne diese Meldung fällt es nirgends
  auf.
- **Der Marker bleibt.** Zwei Quellen gleichzeitig wären eine zu viel; die Datei
  hat Vorrang, der Marker ist der Rückfall.

**Eine Falle, die beim Bauen zugeschnappt ist:** `ebenen.json` ist die einzige
Referenzdatei mit einer **Liste** an der Wurzel (die Reihenfolge ist die
Information). `gemeinsam.lade_json` liefert für alles, was kein JSON-Objekt ist,
still ein leeres Objekt zurück — über `lade_json` gelesen wäre die Datei immer
leer gewesen: kein Fehler, keine Meldung, nur keine Fugen. Deshalb
`ebenen_lesen()`, und deshalb ein Selbsttestfall, der genau diesen Rückschritt
fängt.

---

## Der Chunk bekommt Kontext in beide Richtungen

**Entschieden (August 2026), Paket C.** Bis hierher sah ein Chunk nur nach
hinten: das Ende des vorigen Quellabschnitts und die eigene Übersetzung davon.
Nach vorn war er blind — und zwar genau an der Stelle, an der er eine
Entscheidung treffen muss, die erst der nächste Abschnitt auflöst.

### `context_words_voraus` (150)

Der Anfang des nächsten Chunks steht als **Ausblick** im User-Prompt. Er zeigt,
worauf ein angefangener Satzbogen zuläuft, ob eine Figur gleich noch spricht,
ob eine Anrede erst danach aufgelöst wird.

Drei Regeln, die keine Details sind:

- **Er endet an der Ebenenfuge.** Dort beginnt eine andere Erzählebene mit
  anderem Tempus und anderer Person; ihr Anfang wäre kein Ausblick, sondern
  eine Irreführung. Genau davor schützt die Fuge, und der Ausblick darf sie
  nicht unterlaufen. Spätere **Stapelfugen** (Paket G) sind keine Ebenenfugen —
  dort läuft er weiter, weil sie nur eine technische Grenze sind.
- **Er steht VOR dem Auftrag, nicht dahinter.** Was zuletzt im Prompt steht,
  liest ein Modell als das, was zu tun ist. Hinter „ZU ÜBERSETZENDER TEXT" wäre
  der Ausblick eine Einladung, weiterzuübersetzen — und die Längenprüfung
  verwürfe den Chunk.
- **Er schneidet an der Satzgrenze.** Ein mitten im Satz endender Ausblick
  liest sich wie ein abgebrochener Auftrag.

Geschützte Zitatchunks werden übersprungen: Sie bleiben im Original stehen und
sagen über die Fortsetzung nichts.

### Die Rückschau gehört auch in die Revision

Pass 2 sah bisher nur Quelle und Entwurf. Er wusste damit nicht, worauf der
erste Satz antwortet — und glättete genau die Anschlüsse weg, die Pass 1
mühsam hergestellt hatte. Der Block steht jetzt auch im Revisionsbody, mit
derselben Kennzeichnung als reiner Kontext.

### `figuren_nachhall` (3)

Eine Figur, die in Chunk 12 eingeführt wird und in Chunk 13 nur noch »hij« ist,
verschwand aus dem Personenblock — mitsamt Pronomen und Sprechweise, also genau
dann, wenn beides gebraucht wird. Sie hallt jetzt drei Chunks nach und ist im
Block als **»zuletzt erwähnt, hier nur als Pronomen«** gekennzeichnet; sonst
sucht das Modell den Namen im Abschnitt und findet ihn nicht.

**Zurückgesetzt wird der Nachhall nur an Ebenenfugen.** Innerhalb einer
Erzählebene bleibt die Figur dieselbe; über die Fuge hinweg wäre sie eine Figur
der falschen Ebene. Beim Fortsetzen eines abgebrochenen Laufs wird der Nachhall
aus den vorhandenen Quellchunks rekonstruiert — sonst finge ein
wiederaufgenommener Lauf ohne Gedächtnis an.

### Eine verschobene Absatzzahl löst einen neuen Versuch aus

Bisher nur eine Warnung. Das war zu wenig: Die Leseausgabe stellt Quelle und
Fassung **absatzweise** nebeneinander, die Zitate werden nach Absatzposition
eingesetzt, und `qa.py` misst das Tempus je Ebene über die Absatzzuordnung.
Alles drei verrutscht ab einem verschobenen Chunk.

**Die Revision wird verworfen, der Entwurf wiederholt.** Bricht Pass 2 die
Absatzzahl, ist Verwerfen billiger und zielgenauer als ein neuer Versuch — der
Entwurf liegt vor und ist brauchbar. Bricht Pass 1 sie, hilft nur der neue
Versuch. Beide Prompts sagen die Regel jetzt ausdrücklich.

### `rueckschau_quelle`: offen, deshalb ein Schalter

Woraus die Rückschau gebildet wird, ist **nicht entschieden**. Die Revision ist
die bessere Prosa; der Entwurf ist das, woran der nächste Chunk stilistisch
tatsächlich anschließt, wenn die Revision einmal verworfen wird. Voreinstellung
`revision`, umschaltbar auf `entwurf`.

Gemessen ist das noch nicht. Vergleichbar wird es, sobald die Varianten des
Testlaufs beliebige Schalter tragen (Paket D) — heute tragen sie nur
`chunk_words` und Modellnamen. Bis dahin ist es ein Schalter ohne Messung, und
das steht hier, damit niemand die Voreinstellung für ein Ergebnis hält.

### Was noch aussteht

`ratio_min` und `ratio_max` sind unter den alten Prompts kalibriert. Der
Ausblick verändert weder Quelle noch Zieltext, wohl aber die Neigung des
Modells, am Chunkende auszuholen. **Nach dem nächsten Testlauf neu
kalibrieren** — `uebersetzung.py --test` setzt die Grenzen selbst, wenn
mindestens drei Chunks verwertbar sind.

---

## Was der Testlauf messen kann (Paket D)

**Entschieden (August 2026).** Drei Erweiterungen, die alle dasselbe Problem
haben: Bis hierher ließ sich vieles verstellen und wenig vergleichen.

### Varianten tragen jeden Schalter

Eine Variante trug `chunk_words` und Modellnamen. Damit ließen sich die
Schalter aus Paket C — Vorwegschau, Rückschauquelle, Figurennachhall — gar
nicht messen, und `rueckschau_quelle` wäre eine Voreinstellung ohne Begründung
geblieben. Erlaubt sind jetzt zusätzlich `context_words`,
`context_words_voraus`, `rueckschau_quelle`, `figuren_nachhall`,
`revision_pass`, `lektorat_passes`, `tempus`, `diminutive` sowie jedes
`modell_<rolle>` und `effort_<rolle>`.

**Bewusst eine Liste und kein „alles außer `name`".** Ein Tippfehler
(`rueckschau_qelle`) erzeugte sonst still eine Einstellung, die nichts tut —
und der Vergleich liefe durch und maße etwas anderes, als er behauptet. Der
Preflight meldet unbekannte Schlüssel **vor** dem ersten Modellaufruf.

`modell_uebersetzung` zieht `modell_revision` weiterhin mit, wenn dieses nicht
eigens genannt ist: Ein Vergleich, der Pass 1 umstellt und Pass 2 beim alten
Modell lässt, misst eine Mischung.

### `lektorat.py --test --variante` und `bewertung.py --lektorat --variante`

Die Frage „braucht das Korrektorat wirklich Opus" ist eine Lektoratsfrage und
war bisher nicht zu beantworten — die Varianten endeten bei der Übersetzung.
`--variante` gilt beim Lektorat nur mit `--test`; der Variantenvergleich der
Übersetzung behält `test/` als Bezugspunkt, sonst verschöbe sich die Basis.

### Der dritte Testauszug: die Fallenpassage

Erzählung und Dialog messen, ob der Text als deutsche Prosa besteht. Ob die
Warnungen aus dem Fallenblock **ankommen**, messen sie nicht — in einem ruhigen
Erzählabschnitt kommen die Fallen gar nicht vor, und genau dort liegt die
Schwäche dieser Sprachrichtung.

Der dritte Auszug sucht deshalb die Stelle mit der höchsten **Fallendichte**,
gemessen aus denselben Mustern, die `block_fallen` im Prompt ausweist:
falsche Freunde, Diminutive, `zou`, `aan het`, `zitten te`, `er is`. Er
überschneidet die anderen beiden nicht — sonst urteilte der Judge zweimal über
denselben Text.

Die Auszüge stehen jetzt auf 2500/2500/2000 statt 1500/1500. Sechs
Urteilspaare statt vier, und der Testlauf kostet entsprechend mehr; dafür
beantwortet er die Frage, für die es ihn gibt.

**`teile.json` wird jetzt wirklich geschrieben.** Sie wurde gelesen und
nirgends erzeugt — `teile_trennen` schnitt deshalb bei der Hälfte der Absätze
und verglich Erzählung gegen Dialog, sobald die Auszüge verschieden viele
Absätze hatten. Belastbar ist die Absatzzahl erst, seit ein Chunk mit
verschobener Absatzzahl wiederholt wird (Paket C).

### Das Fugenurteil: die Zahl hinter `kette_max`

Im Stapelbetrieb (Paket G) läuft die Kette nur so lange, wie ein Chunk auf den
vorigen warten kann. Kürzere Ketten heißen mehr Fugen — und ob das schadet,
war bisher eine Vermutung.

`bewertung.py --fugen` legt dem Judge das Ende eines Chunks und den Anfang des
folgenden vor und fragt **ausschließlich** nach dem Übergang: Tempus, Anrede,
Wiederaufnahme, Wiederholung, Terminologie. Nicht nach der Qualität im Übrigen
— sonst misst es dasselbe wie das Blindurteil und nichts über die Naht.

Verglichen werden Nähte, die **mit** Rückschau entstanden sind. Bricht es schon
dort, ist eine Kette ohne Rückschau erst recht zu kurz. Das Bruchmaß (deutlich
zählt voll, leicht zur Hälfte) mündet in eine Empfehlung; die Marken 10 % und
25 % sind Konvention und keine Messung — sie machen aus einer Zahl eine
Entscheidung und stehen deshalb im Code und nicht im Kopf des Lesers.

---

## Eine Ablehnung bricht den Lauf nicht mehr ab

**Entschieden (August 2026).** `claude-opus-5` und `claude-fable-5` tragen
Sicherheitsklassifikatoren, die eine Anfrage ablehnen können. Das ist kein
Fehler und kein HTTP-Status, sondern eine gültige Antwort mit
`stop_reason: "refusal"` und leerem `content`.

Was bis jetzt passierte: `antwort_lesen` warf einen `ApiFehler`, die
Chunkschleife fing ihn wie jeden anderen, wiederholte dreimal denselben
Aufruf — jedes Mal mit demselben Ergebnis, weil ein Klassifikatorurteil
nicht würfelt — und beendete den Lauf mit „Abbruch bei Chunk 300".

Das ist kein hypothetischer Fall. Die Kategorien heißen `general_harms`,
`cyber`, `bio`, `frontier_llm` und `reasoning_extraction`, und die
Dokumentation sagt zu dreien ausdrücklich, dass auch harmlose Arbeit sie
auslösen kann. Ein Roman von 1919 handelt von Krieg, Krankheit und Gewalt.
Über 147 Chunks ist die Frage nicht ob, sondern wann.

Seither steht `fallbacks: "default"` im Payload und
`server-side-fallback-2026-07-01` im Kopf: Der Anbieter beantwortet den
abgelehnten Chunk mit dem Modell, das er für diese Ablehnungskategorie
empfiehlt — in derselben Anfrage, ohne dass der Lauf etwas tun muss.
`fallback_modelle` in `projekt.json` nimmt auch eine eigene Liste von bis zu
drei Modellen oder schaltet den Rückfall mit `""` ab.

Drei Dinge, die daran nicht wegvereinfacht werden dürfen:

- **Gebucht wird unter dem Modell, das geantwortet hat.** Der Rückfall ist
  eine stille Modelländerung mitten im Buch, und für eine literarische
  Übersetzung ist das keine Kleinigkeit. Die Kostenübersicht zeigt sie als
  eigene Zeile (`voll/uebersetzung/claude-opus-4-8`) — damit ist sie
  gleichzeitig gebucht *und* auffindbar, ohne dass es eine zweite Liste
  braucht. Das ist derselbe Grundsatz, an dem die Buchung schon einmal
  gescheitert ist: Token des einen Modells zum Preis des anderen.
- **Der Beleg ist die Iterationsliste, nicht der Modellname.** Ein Alias
  löst auf einen datierten Namen auf; wer den Namen vergleicht, meldet bei
  jeder Antwort einen Rückfall und zerlegt nebenbei jede Kostenzeile in zwei
  halbe. `rueckfall_gelaufen()` liest `usage.iterations` und findet dort
  `fallback_message`. Der Eintrag steht auch dann da, wenn die API wegen
  einer früheren Ablehnung gleich an das Ersatzmodell geleitet hat und gar
  kein Übergabeblock entsteht.
- **Die Erkennung der Ablehnung ist eng gefasst.** `fallback_abgelehnt()`
  greift nur bei HTTP 400 mit „fallback" im Wortlaut, wie `ttl_abgelehnt()`
  bei der Cache-Lebensdauer. Ein weiterer Fang verschluckte echte
  Payloadfehler und gäbe still ein zweites Mal Geld aus.

Lehnt der Anbieter den Rückfall ab (unbekanntes Betakennwort, keine
Freischaltung), meldet der Lauf das einmal und läuft ohne ihn weiter — dann
gilt wieder das alte Verhalten. Für **Paket G** steht die Einschränkung im
Code: Die Stapel-API nimmt `fallbacks` nicht an, der Stapeladapter muss das
Feld entfernen statt es zu erben.

---

## Die Websuche wird bezahlt, belegt und aktuell gehalten

**Entschieden (August 2026).** Drei Befunde an einem Schritt.

**Die Fassung stand im Code und war anderthalb Jahre alt.**
`zitatrecherche.py` rief `web_search_20250305`, während es inzwischen
`web_search_20260209` (filtert Treffer, bevor sie ins Kontextfenster wandern)
und `web_search_20260318` gibt. Gemerkt hätte das niemand: Eine alte Fassung
antwortet, sie bricht nicht ab. Die Fassung steht jetzt in `projekt.json`
(`websuche_werkzeug`), und ein Selbsttest verbietet den Namen in jedem Skript
außer `gemeinsam.STANDARD` und dem Test selbst.

**Die Suche tauchte in keiner Rechnung auf.** Sie kostet 10 $ je 1000 Suchen,
also bei sechs Suchen je Zitat rund 6 Cent — kein großer Posten, aber der
einzige, den keine Tokenzahl verrät. `USAGE_FELDER` hat deshalb ein Feld
`suchen`, `kosten_dollar` rechnet es mit, und der Preflight schätzt es vorab.
Der Grundsatz „neue modellrufende Schritte ohne Usage-Erfassung gelten als
unfertig" gilt auch für Werkzeuge, die kein Modell sind.

**`pause_turn` wurde nicht behandelt.** Hält die API eine lange Suchschleife
an, kommt eine gültige, aber unfertige Antwort zurück. Der JSON-Parser fand
darin keine Struktur, meldete einen Formfehler — und ein übersprungenes Zitat
ist eine Lücke, die später jemand von Hand suchen muss. `chat_meta` schickt
die angehaltene Antwort jetzt zurück und lässt die Runde weiterlaufen,
höchstens `PAUSEN_MAX` mal. Die `None`-Felder, mit denen die SDK ungesetzte
Schlüssel füllt, werden dabei entfernt; unverändert zurückgeschickt lehnt die
API sie ab.

Dazu eine Verbesserung, die nicht aus einem Fehler kam: **Die Antwort trägt
Belege.** Jeder Textblock, den ein Treffer gestützt hat, bringt URL, Titel
und den belegten Wortlaut mit. Das ist etwas anderes als die Felder
`uebersetzer` und `quelle`, die das Modell selbst formuliert — die eine
Angabe ist abgerufen, die andere geschrieben. Für einen Schritt, dessen
ganzer Zweck „erfinde nichts" ist, ist dieser Unterschied das Wichtigste, was
die Antwort zu bieten hat. Die Belege stehen jetzt in `zitate_review.md` und
im Tab `ZitateReview`, getrennt von der Quellenangabe.

Dabei fiel auf, dass `review_lesen()` die Spalte `freigegeben` über eine feste
Position las (`felder[-1]`). Die neue Spalte hätte still die falsche Zelle
getroffen — und `freigegeben` ist die eine Spalte, bei der ein Lesefehler
einen ungeprüften Wortlaut in den Text setzt. Gelesen wird jetzt über
`SPALTEN.index(...)`, und der Selbsttest erteilt die Freigabe so, wie ein
Mensch es täte: in der Spalte, nicht an einer Textstelle.

---

## Streaming: ja, aber nur auf dem SDK-Pfad

**Entschieden (August 2026), Widerruf von „Kein Streaming".** Ohne Stream
hängt eine stockende Anfrage bis zum Lesetimeout — zehn Minuten, in denen
nichts ankommt und niemand weiß, ob noch etwas kommt. Erst danach greift der
Retry. Mit Stream hält die Verbindung sich selbst am Leben, und die SDK
verlangt ihn ohnehin, sobald `max_tokens` groß genug ist, dass die Antwort
das HTTP-Zeitfenster sprengen könnte — bei `max_tokens_api: 32000` und
`effort: high` ist das keine ferne Grenze.

Der `requests`-Pfad bekommt **kein** Streaming. Er bräuchte einen
handgeschriebenen SSE-Parser mit eigener Fehlerbehandlung, eigenem
Zusammenbau der Blöcke und eigener Fehlerklasse für `event: error` — also
genau die Art Rückfallpfad, die kein Selbsttest prüfen kann und die deshalb
schon Ollama gekostet hat.

Was den Preis dieser Entscheidung klein hält: `stream.get_final_message()`
liefert dieselbe Nachricht wie ein Aufruf ohne Stream. Es bleibt bei einem
Payloadbauer und einem Antwortleser; der Stream ist ein Transportdetail und
keine zweite Wahrheit. Der Selbsttest prüft genau das — derselbe Payload
geht raus, dieselbe Antwort kommt an.

---

## Die Chunkeinteilung hat eine Stelle, nicht drei

**Entschieden (August 2026), nach einem Fehler, den Paket C verursacht hat.**

Drei Schritte stellen Quelle und Fassung nebeneinander: der Lauf selbst, die
Leseausgabe und das Screening. Alle drei bauten die Quellchunks nach —
`rahmen_gruppen` plus `chunks_bauen`, dreimal derselbe Dreizeiler. Solange
alle drei denselben Weg gingen, fiel das nicht auf.

Paket C hat `uebersetzung.ebenengruppen` eingeführt: Der Lauf liest seither
zuerst `ebenen.json` und nimmt den Rahmenmarker nur noch als Rückfall. Die
beiden Leser wurden nicht mitgeändert. Ab da teilte der Lauf den Text an den
Ebenenfugen ein und die Leser nicht.

Gemessen an einem Text mit drei Ebenen über 40 Absätze: **8 Chunks gegen 9,
und 6 der 9 stimmen im Inhalt nicht überein.** Was das heißt:

- Die **Leseausgabe** stellt den falschen Quellabsatz neben den deutschen. Der
  Docstring von `quellchunks` warnte seit jeher genau davor — „niemand sieht
  es, weil beide Spalten für sich plausibel aussehen". Die Warnung hat den
  Fehler nicht verhindert.
- Das **Screening** vergleicht niederländischen Chunk 40 gegen deutschen Chunk
  43 und meldet Auslassungen, die keine sind. Solche Befunde muss ein Mensch
  einzeln nachschlagen, um sie zu verwerfen — teurer als gar kein Bericht.

Seither gibt es `gemeinsam.quellchunks()`, und alle drei rufen sie. Der
Rückfallpfad `rahmen_gruppen` steht nur noch in `gemeinsam`; ein Selbsttest
verbietet ihn in jedem anderen Skript. Ein Kommentar hätte das nicht
verhindert, eine gemeinsame Funktion tut es.

Dazu `quellchunks_wie_lauf()` für die beiden Leser. Sie nimmt `chunk_words`
aus `uebersetzung_state.json` statt aus der aktuellen Konfiguration — wer die
Chunkgröße nach dem Lauf verstellt, bekäme sonst eine andere Einteilung als
die, die übersetzt wurde. Und sie **prüft die Zahl gegen `total`**. Diese
Prüfung ist der eigentliche Zweck: Eine abweichende Einteilung fällt sonst
nirgends auf.

Weicht sie ab, brechen Leseausgabe und Screening ab, statt zu warnen. Eine
verschobene, aber ausgelieferte Leseausgabe ist schlimmer als gar keine — sie
wird gelesen.

---

## Das Screening bekommt ein Gedächtnis, einen Resume und Lücken im Bericht

**Entschieden (August 2026).** Drei Dinge am selben Schritt.

**Wiederkehrende Befunde füllten die Liste.** Ein falscher Freund, der im
ganzen Buch vorkommt, wird in jedem Bündel neu gemeldet — über 37 Aufrufe
werden daraus 37 Zeilen, die dasselbe sagen. Das ist derselbe Schaden, den
der System-Prompt mit „erfinde nichts" abwehren soll, nur von der anderen
Seite: In eine Liste, die zu neun Zehnteln aus Wiederholungen besteht, sieht
niemand mehr hinein.

Verdichtet wird **lokal**, im Bericht: Gleichlautende Meldungen fallen in eine
Zeile, die Spalte `Chunks` nennt alle Fundstellen. Verdichtet wird nur, was
wörtlich gleich lautet — Ähnliches zusammenzuziehen hieße raten, und ein
fälschlich verschmolzener Befund verschwindet, ohne dass jemand ihn gesehen
hat.

Zusätzlich sieht das Modell die bisher gemeldeten Muster. Dieser Baustein
steht im **User-Prompt**, nicht im System-Prompt: Der System-Prompt ist das
zwischengespeicherte Präfix und muss über alle Aufrufe byteweise identisch
bleiben. Er spart Ausgabe und Aufmerksamkeit, mehr nicht — die Verdichtung im
Bericht hängt nicht daran.

**Ein gescheiterter Aufruf wurde verschluckt.** `AlleFehlgeschlagen` bricht
ab, wenn schon der *erste* Aufruf scheitert. Scheiterte der dreißigste, wurde
das gedruckt und vergessen: Der Bericht sah vollständig aus, obwohl vier
Chunks nie geprüft worden waren. Übersprungene Chunknummern kommen jetzt
zurück und stehen im Bericht.

**Und es gab keinen Resume.** 37 Aufrufe mit einem Prüfmodell sind Geld; ein
Absturz beim dreißigsten kostete alle dreißig. Die Befunde je Bündel liegen
jetzt in `teile/screening/`, gezählt werden Dateien — dieselbe Regel wie beim
Chunklauf, aus demselben Grund: Zustandsdateien lügen nach einem Absturz,
Verzeichnisinhalte nicht.

Dabei fiel ein dritter Fehler auf, älter als die anderen: `json_lesen`
probierte `{…}` vor `[…]`. Bei einer Liste mit **genau einem** Objekt liegt
die geschweifte Klammer innerhalb der eckigen — der Parser lieferte das
Objekt, der Aufrufer erwartete eine Liste und verwarf es. Jeder Befund, der
allein in seinem Bündel stand, ging so verloren. Bei zwei Befunden schlug der
Versuch fehl (`Extra data`) und der zweite griff; deshalb hat es nie jemand
bemerkt. Probiert wird jetzt in der Reihenfolge, in der die Klammern im Text
vorkommen.

---

## Der Stapel läuft in Wellen über Ketten, nicht über das Buch

**Entschieden (August 2026).** Die Stapel-API rechnet alles zum halben Preis
— Eingabe, Ausgabe, Cache. Bei rund 40 $ für Übersetzung und Revision des
Buches 1919 sind das 20 $, und die Wartezeit ist kein Argument dagegen: Die
meisten Stapel sind in unter einer Stunde fertig, ein serieller Lauf über 147
Chunks dauert drei.

Der Haken ist nicht der Preis und nicht die Zeit. **Ein Chunk kann die
deutsche Fassung des vorigen nicht sehen, wenn beide im selben Stapel
liegen.** Wer das ganze Buch in einen Stapel legt, spart die Hälfte und wirft
die Rückschau weg — und die Rückschau ist der Grund, warum die Anschlüsse
zwischen den Chunks überhaupt halten. Das wäre kein Handel, sondern ein
anderes Verfahren.

Deshalb Ketten. Innerhalb einer Kette bleibt alles seriell; die Ketten laufen
nebeneinander. Je Welle geht der nächste Chunk jeder Kette in denselben
Stapel. Bei drei Ketten sind das 3 Chunks gleichzeitig, bei elf Ketten elf.

**Geschnitten wird zuerst an den Ebenenfugen, und diese Schnitte kosten
nichts.** Dort setzt die Rückschau ohnehin zurück — das ist genau der Punkt
von `ebenen.json`. Erst wenn ein Abschnitt länger als `kette_max` ist, wird
zusätzlich getrennt, und **jeder dieser Schnitte ist eine Naht ohne deutsche
Rückschau**. Der Standard ist deshalb `kette_max: 0`: nur die freien
Schnitte. Wer schneller fertig sein will, entscheidet das mit
`pipeline.py wellen` vor Augen — die Tabelle stellt Wellen und Nähte
nebeneinander, damit niemand nur die halbe Rechnung sieht.

Was die Nähte wirklich kosten, sagt keine Tabelle, sondern `bewertung.py
--fugen` (Paket D). Die beiden Pakete gehören zusammen: Das eine erzeugt die
Nähte, das andere misst sie.

Drei Dinge, die nicht wegvereinfacht werden dürfen:

- **Der niederländische Quellschluss steht auch am Kettenanfang zur
  Verfügung.** Er ist Original und hängt an keiner Übersetzung. Nur die
  eigene Fassung fehlt dort. Das halbiert den Schaden einer bezahlten Naht,
  und es kostet nichts.
- **An der Ebenenfuge entfällt auch der Quellschluss.** Dort beginnt eine
  andere Erzählebene; ihr Vorgänger wäre eine Irreführung, keine Hilfe. Der
  Selbsttest prüft beide Fälle getrennt, weil sie sich im Code um eine
  Bedingung unterscheiden.
- **Ein Payloadbauer.** `stapel_payload()` ist ein Filter über das Ergebnis
  von `payload()`, kein zweiter Bauer. Was die Stapel-API ablehnt, steht in
  `STAPEL_VERBOTEN` — allen voran `fallbacks`: Der serverseitige Rückfall aus
  Paket E ist auf diesem Weg nicht zu haben.

Und daraus folgt etwas Nützliches: **Was der Stapel nicht liefert, holt der
synchrone Weg.** Abgelehnte, abgelaufene und fehlerhafte Einträge laufen
einzeln nach — und dort greift der Rückfall dann doch. Der Stapel verliert
also nicht die Absicherung aus Paket E, er verschiebt sie auf den Nachlauf.

**Gebucht wird unter einem eigenen Schlüssel** (`…/stapel`), weil der Stapel
einen eigenen Tarif hat. In derselben Zeile summiert wären es Token zu zwei
Preisen, und die Zeile ließe sich nicht mehr rechnen — derselbe Grund, aus
dem der Schlüssel überhaupt drei Teile hat statt einem.

---

## Ein neues Buch: die Frage steht vor der Anleitung

**Entschieden (August 2026).** `NEUES_BUCH.md` gab es schon — als Anleitung,
die den Weg von der Textdatei bis zum Paket beschreibt. Was fehlte, war die
Stelle, an der ein neues Buch etwas *entscheiden* muss.

Die wichtigste dieser Entscheidungen ist eine einzige Frage: **Wie sind die
Erzählebenen in diesem Text ausgezeichnet?** Sie steht jetzt als Abschnitt 5a
mitten in der Einrichtung, vor dem ersten Modellaufruf, mit dem Befund von
1919 daneben: fünf Ebenen im Stilprofil, ein Marker, den der Autor nie benutzt
hat, eine Gruppe über 147 Chunks.

Drei Dinge, die aus einer Erinnerung eine Prüfung machen:

- **Der Preflight meldet, wenn der eingestellte `rahmen_marker` im Text nicht
  vorkommt.** Das ist die eine Zeile, die den Lauf 1919 verhindert hätte, und
  sie kostet nichts: Der Text liegt zu diesem Zeitpunkt ohnehin geladen da.
  Die Meldung nennt die Folge, nicht nur den Befund.
- **Die Vorlage `projekt.json` im Repo nennt jede Einstellung ausdrücklich.**
  Vier Schlüssel fehlten und fielen still auf `gemeinsam.STANDARD` zurück —
  darunter `rahmen_marker`. Wer eine `projekt.json` für ein neues Buch
  durchsieht, sieht einen fehlenden Schlüssel nicht; er entscheidet sich
  hinter dem Rücken. Ein Selbsttest hält die Vorlage vollständig.
- **Modellnamen in der Doku sind die eingestellten.** Die Anleitung zeigte als
  Beispiel für `technik_ausnahmen` die Rolle `modell_uebersetzung` mit dem
  Korrektoratsmodell besetzt — in einem Block, den sie selbst zum Kopieren
  anbietet. Wer ihn übernahm, tauschte das wichtigste Modell der Pipeline
  gegen ein schwächeres, und `technik_ausnahmen` schützte den Fehler dann
  auch noch vor `pipeline.py technik --uebernehmen`, weil genau das seine
  Aufgabe ist. Für Übersetzung und Revision steht in `EMPFEHLUNG` „hier wird
  nicht gespart"; das Beispiel sagte das Gegenteil.

  Ein Selbsttest vergleicht jetzt jede Modellzuweisung in der Doku mit der
  Vorlage. Ausgenommen ist `ARBEITSAUFTRAG.md` — ein Dokument, das
  beschreibt, was war, darf nicht mitwandern. Nicht ausgenommen ist diese
  Datei hier: Der Test kann Beleg und Anweisung nicht unterscheiden und soll
  es nicht, deshalb steht der falsche Name oben in Prosa statt in JSON.
- **Kein verwaistes Dokument.** `NEUES_BUCH.md` lag ein halbes Jahr im Repo,
  ohne dass irgendein anderes Dokument es erwähnt hätte — ausgerechnet die
  Datei, die man zuerst braucht, war die einzige unauffindbare. Ein
  Selbsttest prüft jetzt, dass jedes Dokument von einem anderen aus erreichbar
  ist. Dabei kamen drei weitere zutage: `VERLAG.md`, `ABBRUCHPROBE.md` und
  `ARBEITSAUFTRAG.md`.

Warum kein zweites Dokument mit dem Titel „Checkliste": Es gibt bereits vier
Einstiege (`README`, `NEUES_BUCH`, `ABLAUFPLAN`, `ENTSCHEIDUNGEN`), und ein
fünftes hätte dieselbe Halbwertszeit gehabt wie das erste, das niemand
verlinkt hat. Die Entscheidungen stehen dort, wo sie anfallen — im Ablauf.

---

## Verworfen — und warum

**API-Frontier-Modell als Primärübersetzer** (zunächst). Die Kostenrechnung
sprach dafür, die Entscheidung fiel trotzdem für lokales Hosting. Beim Wechsel
gilt: Die `chat()`-Abstraktion ist dafür gebaut, der Eingriff ist klein.
→ Juli 2026 umgesetzt; siehe „API-Backends statt lokalem Hosting".

**Ollama als Rückfallpfad.** → August 2026 zurückgezogen; siehe oben. Die
Begründung von damals (Vertraulichkeit, Unabhängigkeit von der API) war
bereits mit `export_glossar: true` hinfällig geworden.

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
