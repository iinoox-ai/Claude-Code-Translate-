# Literarische Übersetzungspipeline

Chunkweise Übersetzung buchlanger literarischer Texte mit einem
Sprachmodell — mit Referenzmaterial, Kontextübergabe, mehrstufigem Lektorat
und Prüfungen, die auf die **charakteristischen Fehler des Sprachpaars**
zugeschnitten sind.

Aktuell konfiguriert für **Niederländisch → Deutsch**. Ein zweiter Satz für
Deutsch → Englisch (UK) existiert separat.

---

## Warum es das gibt

Ein Buch chunkweise durch ein Sprachmodell zu schicken ist einfach. Dabei
Konsistenz, Stimme und Bedeutung zu halten, ist es nicht. Die drei Probleme,
um die sich alles hier dreht:

**Chunk-Isolation.** Das Modell sieht 800 Wörter und weiß nicht, wie es eine
Figur zwei Kapitel früher genannt hat, welches Pronomen sie nimmt oder ob eine
wiederkehrende Wendung Absicht ist. Antwort: Referenzmaterial, das bei jedem
Chunk mitgeht, plus Rückschau auf Quelle *und* eigene Übersetzung.

**Sprachpaarspezifische Fehler.** Jedes Paar hat eine Fehlerklasse, die ein
Modell ohne ausdrückliche Anweisung zuverlässig produziert. Bei nah verwandten
Sprachen sind das Fehler, die **richtig klingen und trotzdem falsch sind**.
Antwort: gezielte Prompts, chunkweise Aufmerksamkeitslenkung, gerichtete
Prüfungen. Siehe `SPRACHPAARE.md`.

**Lektorat, das zu viel tut.** Ein Stildurchgang, der „Wiederholungen
vermeiden" soll, schleift bewusste Stilmittel ab. Ein Korrektorat, das nach
Schulgrammatik arbeitet, hebt die Erzählstimme an. Beides merkt man erst beim
Vergleich mit dem Original. Antwort: Stimmschutz in den Prompts, Registerkontrolle
in der Qualitätsprüfung.

---

## Ablauf

```
 selbsttest      Normalisierer, Metriken, Prompts auf einer Kunstzeile
 preflight       System, Text, Zitaterkennung, Begleitdateien
 konkordanz      Kandidaten mit Belegstellen -> Analysepaket
 ⏸ PAUSE         Glossardateien extern erstellen
 test            Testübersetzung: Erzählpassage + Dialogpassage
 testB           dieselbe Passage mit anderer Chunkgröße
 bewertung       Diff-Statistik, Blindbewertung, Exportpaket
 chunkvergleich  A gegen B
 test_lektorat   Lektorat auf der Testübersetzung
 qa + bewertung  Prüfung und Exportpaket
 ⏸ PAUSE         Berichte prüfen, entscheiden, einspielen
 voll            vollständige Übersetzung
 qa              Notbremse bei harten Defekten
 lektorat        det -> stil -> korrektorat -> det
 qa              Registerkontrolle, Tempus, Diminutive, Zitattreue
 konsistenz      Leitmotive und Terminologie über die Buchlänge
 paket           Archiv zum Download
```

Gesteuert über ein einziges Skript:

```bash
python3 pipeline.py init      # einmal
python3 pipeline.py run --hg  # loslaufen, im Hintergrund
python3 pipeline.py status    # Stand, Chunkzähler, Restzeit, Kosten
python3 pipeline.py weiter    # offene Pause freigeben und weiterlaufen
python3 pipeline.py log -f    # mitlesen
python3 pipeline.py stop      # anhalten
```

`run` macht immer am nächsten offenen Schritt weiter. An den beiden Pausen
gibt `weiter` frei und läuft in einem Zug weiter — genau eine Pause, nie
einen fehlgeschlagenen Schritt. Bei jedem Abbruch ist
derselbe Befehl die Antwort. Das einzige Kommando, das Ergebnisse löscht, ist
`pipeline.py neu`, und es fragt vorher.

Vollständige Anleitung: **`ABLAUFPLAN.md`**

---

## Dateien

### Steuerung

| Datei | Aufgabe |
|---|---|
| `pipeline.py` | Orchestrator: Zustand, Hintergrundlauf, Konfigurationsmerge |
| `projekt.json` | alle Einstellungen — kein Skript wird gepatcht |
| `anweisungen.md` | Sonderanweisungen, drei Abschnitte, wörtlich in die Prompts |
| `manifest.json` | Schrittstatus, wird von `pipeline.py` geführt |

### Arbeitsschritte

| Datei | Aufgabe |
|---|---|
| `gemeinsam.py` | Backend-Adapter, Chunking, Metriken, Berichte |
| `preflight.py` | Selbsttest, System-, Text- und Dateiprüfung |
| `konkordanz.py` | Namenserkennung, Belegstellen, Analysepaket |
| `uebersetzung.py` | Übersetzung mit Referenzblöcken und Revisionspass |
| `lektorat.py` | Normalisierung, Stillektorat, Korrektorat |
| `qa.py` | Qualitätsprüfung mit Notbremse, globale Konsistenz |
| `bewertung.py` | Testläufe auswerten, Exportpakete |
| `diffview.py` | wortweiser Änderungsbericht, HTML oder Terminal |
| `leseausgabe.py` | Quelle, Entwurf und lektorierte Fassung nebeneinander |
| `paket.py` | Ergebnis archivieren |

### Referenzmaterial (entsteht unterwegs)

`glossar.json` · `personen.json` · `figurenblatt.json` · `anrede.json` ·
`leitmotive.json` · `zitate.json`

### Briefings für die externe Auswertung

`briefing_glossar_vorlage.md` · `briefing_bewertung_vorlage.md` ·
`briefing_lektorat_vorlage.md`

Diese werden beim jeweiligen Schritt mit ausgegeben und zusammen mit dem
Analysepaket hochgeladen. Sie funktionieren auch in einer frischen
Unterhaltung ohne Vorwissen.

### Dokumentation

| Datei | Inhalt |
|---|---|
| `ABLAUFPLAN.md` | Schritt für Schritt, mit Befehlen |
| `ENTSCHEIDUNGEN.md` | **warum es so gebaut ist** — vor jedem Umbau lesen |
| `SPRACHPAARE.md` | die Fehlerklassen je Sprachpaar, neues Paar anlegen |

---

## Was diese Pipeline anders macht

**Referenzmaterial pro Chunk, nicht global.** Glossar, Personen, Anrede,
Leitmotive und die sprachpaarspezifischen Fallen werden gefiltert: Nur was im
aktuellen Abschnitt vorkommt, geht in den Prompt. Eine
Vierundzwanzig-Punkte-Liste im Dauerkontext wird bei Chunk 84 nicht mehr
gelesen; drei gezielte Zeilen schon.

**Kontextübergabe in beide Richtungen.** Jeder Chunk sieht das Ende des vorigen
Quelltexts *und* der eigenen Übersetzung davon. Der zweite Teil ist der
wichtigere — er zeigt dem Modell, wie es gerade geklungen hat.

**Prüfgrenzen aus dem Testlauf.** Statt Faustregeln wird das Längenverhältnis
am konkreten Text gemessen und die Toleranz darum gelegt.

**Zwei getrennte Testauszüge.** Erzählpassage und dialogdichteste Stelle,
getrennt ausgewertet. Bei nah verwandten Sprachpaaren liegt die Schwäche im
Dialog, wo Modalpartikeln, Diminutive und Anredeform zusammentreffen.

**Deterministisch, wo immer möglich.** Typografie, Schreibvarianten, ß/ss
laufen ohne Modell — kostenlos, in Sekunden, ohne Risiko der Umformulierung.

**Prüfungen, die auf Schaden zielen, nicht auf Vollständigkeit.**
Registerkontrolle (wurde die Erzählstimme angehoben?), Diminutivzähler (wurde
mechanisch übertragen?), Tempuskontrolle (wurde der gewollte Wechsel
geglättet?), Zitattreue (blieb der verbürgte Wortlaut stehen?).

**Selbsttest vor jedem Modellaufruf.** Die zwei schwersten Fehler des Projekts
waren Laufzeitfehler, die kein Lesen gefunden hat. Schlägt der Selbsttest fehl,
gibt es keinen Modellaufruf.

**Chunk-Ausgaben einzeln.** Resume zählt Dateien; ein misslungener Chunk wird
mit `--chunk 37` einzeln neu gerechnet.

---

## Konfiguration

Alles in `projekt.json`. Kein Skript wird je gepatcht.

Beim Einspielen einer extern angepassten Konfiguration:

```bash
python3 pipeline.py config projekt_neu.json
```

Der Merge übernimmt nur Schlüssel aus `AENDERBAR` und schützt
`ratio_min`, `ratio_max`, `ratio_kalibriert`, `sprachpaar` programmatisch.
Abgelehntes wird mit Begründung ausgegeben.

**Sinnvoll verstellbar sind vier Parameter:** `chunk_words`, `context_words`,
`context_words_voraus` und `effort_<rolle>`. Sampling-Parameter nehmen beide APIs nicht mehr an.
Warum nicht mehr, steht in `ENTSCHEIDUNGEN.md`.

---

## Backend wechseln

`gemeinsam.py` kapselt den Modellzugriff in `Backend`. Ein neuer Anbieter ist
eine Unterklasse:

```python
class MeinBackend(Backend):
    def chat(self, cfg, system, user, rolle, modell, roh=False):
        ...
    def verfuegbare_modelle(self, cfg):
        ...

BACKENDS["mein"] = MeinBackend()
```

Ein Präfix in `PRAEFIXE` ordnet die Modellnamen des Anbieters zu — das
Backend ergibt sich aus dem Modellnamen, nicht aus einem Schalter. Kein
anderes Skript ändert sich.

Zwei Eigenheiten, die nicht „repariert" werden dürfen:

- **Keine Sampling-Parameter.** `claude-opus-5` hat `temperature`, `top_p`
  und `top_k` entfernt und antwortet darauf mit HTTP 400; Gemini ignoriert
  sie. Die Tiefe steuert `effort_<rolle>`. Der Selbsttest prüft beide
  Payloads darauf.
- **Zwei Transportwege, ein Payload.** Ist die SDK `anthropic` installiert,
  geht der Anthropic-Verkehr über sie, sonst über `requests`; beide bauen
  denselben Payload und lesen die Antwort mit derselben Funktion. Ohne die
  SDK läuft alles weiter — nur ohne Streaming und Stapelverarbeitung.
- **Der System-Prompt trägt einen Cache-Marker.** Er ist über alle Chunks
  byteweise identisch. Wer Bausteine umsortiert, zerstört die Trefferquote
  unbemerkt — identische Präfixe sind Geld.
- **Die Cache-Lebensdauer (`cache_ttl`, Standard `1h`) ist eine
  Versicherung.** Sie hält das Präfix über eine Pause zwischen zwei Chunks
  hinweg. Als Sparmaßnahme taugt sie nicht: Die gemessene Trefferquote lag
  schon bei 96 %. Schreiben mit einer Stunde kostet doppelt statt des
  1,25-fachen; abgerechnet wird nach der Aufschlüsselung aus der Antwort.
  Lehnt der Anbieter sie ab, meldet der Lauf das einmal und geht ohne sie
  weiter.

**Was nicht parallelisierbar ist:** Für den Übersetzungspass hängt Chunk *n*
an der Übersetzung von *n−1*. Parallel geht nur, wer auf die Rückschau
verzichtet — und das kostet Konsistenz. Siehe `ENTSCHEIDUNGEN.md`.

---

## Ein neues Sprachpaar

Der bestehende Satz ist eine Kopie mit ausgetauschten Sprachdaten. Was sich
unterscheidet:

- **Prompts** in `uebersetzung.py` und `lektorat.py`
- **Wortlisten**: falsche Freunde, Homographen, Registermarker, Stoppwörter
- **Namenserkennung** in `konkordanz.py` (Groß-/Kleinschreibung,
  Namenspartikel, Pronomen-Mehrdeutigkeit)
- **Normalisierer** in `lektorat.py` (Zieltypografie, Orthografie)
- **Metriken** in `gemeinsam.py` und `qa.py`

Was gleich bleibt: Chunking, Kontextübergabe, Referenzblöcke, Zustands\
verwaltung, Orchestrator, Berichtswesen, Zitatbehandlung, Notbremse.

Die Reihenfolge, in der sich die Arbeit lohnt, steht in `SPRACHPAARE.md`.

---

## Bekannte Grenzen

**Der Anredecheck ist ein Näherungsmaß.** Wer wen duzt, ist per Muster nicht
bestimmbar. Die Prüfung zählt Formen im Umfeld von Figurennamen und liefert
Falschmeldungen. Der Bericht sagt das selbst.

**Die Glossartreue wird global geprüft**, nicht pro Chunk. Eine chunkweise
Prüfung wäre strenger und ist mit den Einzeldateien in `teile/` möglich, aber
noch nicht gebaut.

**Die lokale Blindbewertung ist schwach.** Ein Modell beurteilt seinen eigenen
Entwurf gegen seine eigene Revision. Sie bleibt als drittes Signal neben der
Diff-Statistik und dem eigenen Urteil, nicht als Entscheidungsgrundlage.

**Absätze werden gelegentlich verschmolzen.** Bei einem Lauf verlor ein Text
55 von 1430 Absätzen — ohne Textverlust, die Wortzahl stimmte. Die Prüfung
meldet es; verhindern lässt es sich nur durch die Prompt-Anweisung, die
bereits drinsteht.

**Kein Streaming.** Eine hängende Anfrage blockiert bis zum Timeout
(`timeout_read`, Vorgabe 15 Minuten), erst dann greift der Retry.
