# Sprachpaare

Das linguistische Kapital dieser Pipeline. Der Code ist austauschbar; das hier
ist der Teil, den man nicht in einem Repo findet.

Jedes Sprachpaar hat eine **charakteristische Fehlerklasse**, die ein Modell
ohne ausdrückliche Anweisung zuverlässig produziert. Sie zu benennen ist die
eigentliche Arbeit beim Anlegen eines neuen Paars.

---

## Der Grundsatz

Es gibt zwei Arten von Übersetzungsfehlern, und sie brauchen entgegengesetzte
Behandlung:

**Hörbare Fehler.** Der Zieltext klingt falsch — fremde Satzarchitektur,
unidiomatische Wendungen. Die fallen beim Lesen auf und lassen sich durch
Lektorat finden.

**Unhörbare Fehler.** Der Zieltext klingt einwandfrei und sagt etwas anderes
als das Original. Falsche Freunde, verschobene Aussageebenen, falsche
Pronomenbezüge. Die findet nur, wer das Original danebenlegt — oder wer die
Stellen vorher markiert.

**Je näher die Sprachen verwandt sind, desto mehr verschiebt sich das
Verhältnis zur zweiten Klasse.** Das ist der Grund, warum NL→DE schwieriger
abzusichern ist als DE→EN, obwohl es leichter aussieht.

---

## Niederländisch → Deutsch

Eng verwandt: Verbzweitstellung, Verbletztstellung im Nebensatz,
Modalpartikeln, Komposition, trennbare Verben. Eine wörtliche Übertragung
ergibt **grammatisch korrektes Deutsch, das trotzdem falsch ist**.

### Die acht Fallen

**1. Falsche Freunde** — die dichteste Sammlung zwischen zwei Sprachen
überhaupt.

| NL | bedeutet | nicht |
|---|---|---|
| bellen | anrufen | bellen |
| deftig | vornehm | deftig |
| meer | See | Meer |
| slim | klug | schlimm |
| aardig | nett | artig |
| winkel | Laden | Winkel |
| mist | Nebel | Mist |
| doof | taub | doof |
| eng | gruselig | eng |
| schoon | sauber | schön |
| lopen | gehen | laufen |
| klaar | fertig | klar |
| vies | schmutzig | fies |
| stout | frech | stolz |
| brutaal | frech | brutal |
| **gekocht** | **gekauft** (von *kopen*) | gekocht (= *gekookt*) |
| monster | Probe, Muster | Monster |
| wandelen | spazieren gehen | wandern |
| tafel | Tisch | Tafel |
| bank | Sofa | Bank |
| enkel | nur, Knöchel | Enkel |
| straks | gleich, nachher | stracks |
| eventueel | gegebenenfalls | eventuell |
| kussen | Kissen *und* küssen | Kissen |
| naar | nach *und* unangenehm | nah |
| flink | ziemlich, erheblich | flink |
| kwaad | wütend, böse | — |
| beleefd | höflich | belebt |
| kwartier | Viertelstunde | Quartier |
| net | gerade, gepflegt | nett |
| raar | seltsam | rar |

Die tückischsten sind die, bei denen **beide Lesarten im Kontext
funktionieren**: `lopen`, `mogen`, `net`, `enkel`, `naar`, `gekocht`. Ein
falsch übersetztes `gekocht` entstellt eine ganze Szene, ohne dass irgendetwas
auffällt.

**2. Evidentielles `zou`.** `Hij zou ziek zijn` heißt „Er soll krank sein",
nicht „Er wäre krank". Das Niederländische markiert damit Hörensagen. Die
Verwechslung verschiebt die **Aussageebene** ganzer Absätze — aus einem Gerücht
wird eine Behauptung des Erzählers. Bei Dorfklatsch- oder Berichtspassagen
systematisch.

**3. Diminutive.** `-je`, `-tje`, `-pje`, `-kje` sind hochfrequent und meist
nicht verkleinernd, sondern affektiv oder lexikalisiert: `een biertje`, `een
uurtje`, `een kopje koffie`. Deutsches `-chen`/`-lein` ist viel markierter.
Mechanische Übertragung erzeugt penetrant verniedlichtes Deutsch — der
sichtbarste Einzelfehler eines unbeaufsichtigten Laufs.

**4. Tempusverteilung.** Beide Sprachen haben Präteritum und Perfekt, verteilen
sie aber anders. Niederländische Erzählprosa wechselt freier. Eins-zu-eins
erzeugt ein Deutsch, das ständig springt.

Die Projektentscheidung (`quellnah` oder `praeteritum`) hängt an der
Erzählperspektive: **Perfekt in deutscher Erzählprosa klingt gesprochen und
süddeutsch gefärbt.** Bei umgangssprachlichem Ich-Erzähler richtig, bei
distanzierter dritter Person unbeholfen.

**5. Progressivkonstruktionen.** Keine hat eine standardsprachliche deutsche
Entsprechung:
- `aan het lezen zijn` → „am Lesen sein" ist rheinisch-umgangssprachlich
- `zitten/staan/liggen te lezen` → gar keine Entsprechung
- `gaan` als Futur → Präsens oder „werden", nicht „gehen"

**6. Das Wörtchen `er`.** Existenzsätze, Platzhalter, Pronominaladverbien,
quantifizierendes Element. Deutsch braucht es viel seltener; mechanische
Übertragung erzeugt eine `es gibt`-Schwemme.

**7. Modalpartikeln.** Hier liegt der Unterschied zu DE→EN: **Beide Sprachen
haben sie.** Das Problem ist Scheinäquivalenz. `toch` ist nicht immer `doch`,
`wel` nicht `wohl`, `even` nicht `eben`, `maar` nicht `aber`, `eens` nicht
`einmal`. `hoor` und `zeg` haben gar keine Entsprechung. Nach Wirkung
übersetzen, im Zweifel weglassen.

**8. Kulturgebundene Wörter.** `gezellig`, `lekker`, `borrel`, `uitwaaien`,
`polder`, `gedogen`, `tussendoortje`. Brauchen eine Projektentscheidung im
Glossar, keine Einzelfallübersetzung — `lekker` allein kommt in einem Roman
leicht zweihundertmal vor.

### Besonderheiten der Quellseite

**Kleinschreibung.** Niederländisch schreibt Substantive klein wie das
Englische. Die Artikelprobe, die für deutsche Quelltexte nötig ist, entfällt —
großgeschriebene Wörter sind Namenskandidaten.

**Tussenvoegsels.** `Jan van den Berg`, `Marieke de Vries`, `Piet ten Hoeve`.
Die Partikel steht klein mitten im Namen, alleinstehend aber groß (`De Vries
zei…`). Ohne Behandlung zerfällt jeder Name in Fragmente.

**IJ-Ligatur.** `IJsselmeer`, `IJmuiden` — beide Buchstaben groß.

**Pronomen-Mehrdeutigkeit.** `zijn` ist Possessivpronomen *und* das Verb
*sein*; `ze` ist Singular *und* Plural; `haar` ist Possessiv *und* das
Substantiv *Haar*. Die Geschlechtsauszählung muss das trennen, sonst wird jede
Figur männlich.

### Besonderheiten der Zielseite

Deutsche Typografie: Guillemets nach innen `»…«` mit `›…‹` innen,
Halbgeviertstrich mit Spatien, `…` als ein Zeichen, Abkürzungen mit
Leerzeichen (`z. B.`).

**ß/ss ist der kritische Punkt.** Niederländisch kennt kein ß; ein Modell mit
viel niederländischem Input schreibt zuverlässig `Strasse`, `gross`,
`draussen`. Die Korrektur ist nötig — aber sie muss Homographen schützen,
sonst wird aus `die Masse der Menschen` ein `die Maße`. Siehe
`ENTSCHEIDUNGEN.md`.

Registermarker für die Kontrolle: `hab`/`is`/`nix`, `kriegen` gegen
`bekommen`, `wegen` mit Dativ, `weil` mit Verbzweitstellung, `würde`-Umschreibung
gegen synthetischen Konjunktiv, Diminutivdichte.

---

## Deutsch → Englisch (UK)

Weiter entfernt, deshalb überwiegend **hörbare** Fehler.

### Die Fallen

**Satzarchitektur.** Deutsche Hypotaxe mit verbfinalen Nebensätzen erzeugt eine
Suspension, die Englisch nicht durch Nachahmung reproduzieren kann. Ein Satz
kann tadelloses Englisch und trotzdem deutsch gebaut sein. Umbauen, nicht
übertragen.

**Nominalstil.** „die Durchführung der Untersuchung" → „investigating".
Deutsch bevorzugt Nominalisierungen, Englisch Verben.

**Komposita.** Nie calquen. Englische Phrase finden oder den Satz umbauen.

**Modalpartikeln.** Hier ist das Problem umgekehrt zu NL→DE: Englisch hat
**keine**. Übersetzer polstern sie aus mit `indeed`, `actually`, `well`,
`after all`, `of course`, `just`, `really`. Die Wirkung gehört über
Wortstellung, Kontraktion oder Tag-Question hergestellt — oder gar nicht.

**Passiv und `man`.** Deutsch verwendet beides weit häufiger.

**du/Sie.** Englisch hat die Unterscheidung nicht. Die Distanz muss über
Anredeform, Kontraktionen und Syntax entstehen. Der interessanteste Fall: eine
Figur, die siezt und dabei angreift — die Spannung trägt im Deutschen das
Pronomen, im Englischen nur die Wortwahl.

**Konjunktiv I.** Keine englische Entsprechung; Standardzeitenfolge verwenden.

**Tempus.** Deutsches Erzähl-Präteritum → englisches simple past. Deutsches
Perfekt nicht als present perfect übertragen.

**Falsche Freunde.** `aktuell` ≠ actual, `eventuell` ≠ eventual, `bekommen` ≠
become, `sensibel` ≠ sensible, `also` ≠ also, `Gift` ≠ gift, `Chef` ≠ chef,
`brav` ≠ brave, `Konzept` ≠ concept, `Figur` ≠ figure.

**Das deutsche Komma.** `He said, that he would come` — Deutsch setzt ein Komma
vor jeden Nebensatz, Englisch nicht. Der klarste Verräter; `grep -c ', that'`
sollte 0 ergeben.

### Besonderheiten der Quellseite

**Großschreibung aller Substantive.** Die Namenserkennung braucht die
Artikelprobe: Was regelmäßig hinter `der/die/das/ein/im/zum` steht, ist ein
Gattungswort.

Die Probe hat eine bekannte Lücke: **umgangssprachliches `der Schmidt`**.
Artikel vor dem Nachnamen ist in Schülersprache und regional verbreitet, und
solche Namen fallen aus der Liste. Gegenmittel: Titel in der Umgebung
(`Herr`, `Frau`) als Rettungssignal.

**Sprachliche Markierung, die verschwindet.** Figuren, die im Original
fremdsprachig markiert sind — etwa jemand, der Englisch mit deutschem Einschlag
spricht —, verlieren diese Markierung in der Zielsprache vollständig. Der
klassische Verlustfall bei Übersetzung *in* die Sprache, die im Original die
fremde ist. Braucht eine bewusste Entscheidung.

### Besonderheiten der Zielseite

BE/AE-Entscheidung mit vier Unterfragen: Schreibvariante (`-ise`/`-ize`),
Anführungszeichen, Gedankenstrichstil, Oxford-Komma.

Bei der BE/AE-Wortliste sind **Homonyme** die Gefahr: `flat`, `story`, `check`,
`post`, `queue`, `torch` sind in beiden Varianten korrekte Wörter mit
verschiedener Bedeutung. Rückrichtung nur bei eindeutigen Fällen.

Registermarker: Kontraktionen, `like` gegen `as if`, `got`, `who` gegen `whom`,
Satzfragmente.

---

## Ein neues Sprachpaar anlegen

Die Reihenfolge, in der sich die Arbeit lohnt:

**1. Die charakteristische Fehlerklasse bestimmen.** Sind die Sprachen nah
verwandt? Dann liegt das Risiko bei unhörbaren Fehlern, und die Prüfungen
müssen auf Bedeutung zielen, nicht auf Wohlklang. Sind sie entfernt? Dann
überwiegen Strukturübertragungen, und der Stildurchgang trägt die Hauptlast.

**2. Die Liste falscher Freunde aufbauen.** Nicht vollständig, sondern nach
Schadenspotenzial. Ein Wort, bei dem beide Lesarten im Kontext funktionieren,
ist wichtiger als zehn offensichtliche.

**3. Grammatische Kategorien vergleichen, die nur eine Seite hat.** Genus,
Anredeformen, Modalpartikeln, Aspekt, Evidentialität, Diminutive, Höflichkeits\
ebenen. Jede Asymmetrie ist eine Regel im Prompt.

**4. Die Quellseite instrumentieren.** Wie erkennt man Eigennamen? Welche
Pronomen sind mehrdeutig? Gibt es orthografische Eigenheiten (Ligaturen,
Namenspartikel, Schreibungsvarianten)?

**5. Die Zielseite instrumentieren.** Typografie, Orthografievarianten,
Registermarker für die Kontrolle vor und nach dem Lektorat.

**6. Die Längenverhältnisse kalibrieren** statt sie zu schätzen — der Testlauf
liefert bessere Werte als jede Faustregel.

**7. Erst danach den Code anfassen.** Die Struktur trägt; was sich unterscheidet,
sind Prompts, Wortlisten und Metriken.
