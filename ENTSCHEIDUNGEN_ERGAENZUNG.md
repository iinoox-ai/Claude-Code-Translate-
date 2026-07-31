# Ergänzung zu ENTSCHEIDUNGEN.md — Entscheidungen der API-Migration (Juli 2026)

**Einarbeitungshinweise (für Paket 0 des Arbeitsauftrags):**
1. Die Abschnitte unter „Neue Einträge" vor dem Kapitel „Verworfen — und
   warum" anfügen.
2. Im Kapitel „Verworfen" die zwei Einträge **„API-Frontier-Modell als
   Primärübersetzer"** und **„Modell-Heterogenität"** jeweils um die unter
   „Annotationen" angegebene Schlusszeile ergänzen (Einträge selbst stehen
   lassen — die Historie ist Absicht).
3. Der Eintrag „Zwei GPU-Sitzungen mit einem Prüffenster" bleibt unverändert
   (er kündigt seinen eigenen Wegfall bereits an).
4. Diese Datei danach löschen.

---

## Neue Einträge

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

## Annotationen an bestehenden „Verworfen"-Einträgen

**An „API-Frontier-Modell als Primärübersetzer (zunächst)" anfügen:**
„→ Juli 2026 umgesetzt; siehe ‚API-Backends statt lokalem Hosting'."

**An „Modell-Heterogenität" anfügen:**
„→ Juli 2026 in abgewandelter Form umgesetzt: nicht für die textberührenden
Pässe (alle Opus 5), sondern als Fremd-Judge-Routing; siehe ‚Modellbelegung
und Judge-Routing'."
