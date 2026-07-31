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

---

## Verworfen — und warum

**API-Frontier-Modell als Primärübersetzer** (zunächst). Die Kostenrechnung
sprach dafür, die Entscheidung fiel trotzdem für lokales Hosting. Beim Wechsel
gilt: Die `chat()`-Abstraktion ist dafür gebaut, der Eingriff ist klein.

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
