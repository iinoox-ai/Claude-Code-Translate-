#!/usr/bin/env python3
"""
Uebersetzung Niederlaendisch -> Deutsch.

Neu gegenueber der ersten Fassung:
  - Chunk-Ausgaben liegen einzeln in teile/ und werden am Ende
    zusammengesetzt. Resume zaehlt Dateien, Retranslate loescht eine.
  - Zitate werden beim Zusammensetzen eingefuegt, also immer (F6a)
  - Fallenblock pro Chunk: nur die im Abschnitt vorkommenden falschen
    Freunde, Diminutive, zou-Vorkommen (V14)
  - Evidentielles 'zou' als eigene Regel (V13)
  - Erweiterte Liste falscher Freunde (V12)
  - Konfigurationsfingerabdruck im Zustand (F7)

Aufrufe:
    python3 uebersetzung.py --test
    python3 uebersetzung.py --test --variante B     # Chunkgroessen-Vergleich
    python3 uebersetzung.py
    python3 uebersetzung.py --chunk 37              # nur diesen neu
"""

import argparse
import json
import os
import re
import sys
import time

import gemeinsam as G
import referenz_sync as R

WARN = "uebersetzung_warnungen.log"


# ==================================================================
# Falsche Freunde (V12) — bedeutet / nicht verwechseln mit
# ==================================================================
VALSE_VRIENDEN = [
    ("bellen", "anrufen", "bellen"),
    ("deftig", "vornehm", "deftig"),
    ("meer", "See", "Meer"),
    ("slim", "klug", "schlimm"),
    ("aardig", "nett", "artig"),
    ("winkel", "Laden", "Winkel"),
    ("mist", "Nebel", "Mist"),
    ("doof", "taub", "doof"),
    ("eng", "gruselig", "eng"),
    ("schoon", "sauber", "schön"),
    ("lopen", "gehen", "laufen"),
    ("klaar", "fertig", "klar"),
    ("vies", "schmutzig", "fies"),
    ("stout", "frech", "stolz"),
    ("brutaal", "frech", "brutal"),
    ("dapper", "tapfer", "dapper"),
    ("mogen", "mögen / dürfen", "mögen"),
    ("bot", "stumpf / schroff", "Bot"),
    ("net", "gerade / gepflegt", "nett"),
    ("raar", "seltsam", "rar"),
    # V12 — ergaenzt
    ("gekocht", "gekauft (von kopen!)", "gekocht"),
    ("gekookt", "gekocht", "—"),
    ("monster", "Probe / Muster", "Monster"),
    ("wandelen", "spazieren gehen", "wandern"),
    ("hoeven", "brauchen (in Negation)", "Hufe"),
    ("tafel", "Tisch", "Tafel"),
    ("bank", "Sofa / Bank", "Bank"),
    ("enkel", "nur / Knöchel", "Enkel"),
    ("straks", "gleich / nachher", "stracks"),
    ("eventueel", "gegebenenfalls", "eventuell"),
    ("kussen", "Kissen / küssen", "Kissen"),
    ("naar", "nach / unangenehm", "nah"),
    ("flink", "ziemlich / erheblich", "flink"),
    ("kwaad", "wütend / böse", "Quad"),
    ("beleefd", "höflich", "belebt"),
    ("bepaald", "bestimmt", "bepackt"),
    ("kwartier", "Viertelstunde", "Quartier"),
    ("sla", "Salat", "Schlag"),
    ("glad", "glatt / schlüpfrig", "glatt"),
    ("lastig", "schwierig / lästig", "lästig"),
    ("vaak", "oft", "—"),
    ("pas", "erst / gerade", "Pass"),
    ("ooit", "je / einmal", "oft"),
]

DIMINUTIV_NL = re.compile(r"\b(\w{3,}(?:tje|pje|kje|je))s?\b", re.IGNORECASE)
ZOU = re.compile(r"\bzou(den)?\b", re.IGNORECASE)
AAN_HET = re.compile(r"\baan het \w+en\b", re.IGNORECASE)
POSTUUR = re.compile(r"\b(zat|zit|staat|stond|ligt|lag|zitten|staan|liggen)\s+te\s+\w+en\b",
                     re.IGNORECASE)
ER_EXIST = re.compile(r"\ber (is|zijn|was|waren|wordt|werd)\b", re.IGNORECASE)

# Diminutive, die im Niederlaendischen lexikalisiert sind und nichts
# verkleinern — nur zur Aufmerksamkeitslenkung, nicht als Regel.
DIM_LEXIKALISIERT = {"meisje", "kwartje", "sneetje", "beetje", "gezelletje"}


def block_fallen(chunk, cfg):
    """V14: nur die Fallen, die in diesem Abschnitt wirklich vorkommen."""
    low = chunk.lower()
    zeilen = []

    treffer = []
    for nl, bedeutet, nicht in VALSE_VRIENDEN:
        n = len(re.findall(rf"\b{re.escape(nl)}\w{{0,3}}\b", low))
        if n:
            treffer.append((n, nl, bedeutet, nicht))
    treffer.sort(key=lambda t: -t[0])
    for n, nl, bedeutet, nicht in treffer[:10]:
        hinweis = f"»{nl}« ({n}x) = {bedeutet}"
        if nicht != "—":
            hinweis += f", NICHT {nicht}"
        zeilen.append(f"  {hinweis}")

    dim = [w for w in DIMINUTIV_NL.findall(low)
           if w not in DIM_LEXIKALISIERT]
    if dim:
        zeigen = ", ".join(sorted(set(dim))[:8])
        zeilen.append(f"  {len(dim)} Diminutiv(e): {zeigen} — "
                      f"Politik: {cfg['diminutive']}")

    n_zou = len(ZOU.findall(low))
    if n_zou:
        zeilen.append(f"  »zou« {n_zou}x — evidentiell (»soll«) oder "
                      f"konditional (»würde«)? Im Kontext entscheiden.")
    n_aan = len(AAN_HET.findall(low))
    if n_aan:
        zeilen.append(f"  {n_aan}x »aan het + Infinitiv« — auflösen, "
                      f"kein »am …-sein«")
    n_post = len(POSTUUR.findall(low))
    if n_post:
        zeilen.append(f"  {n_post}x »zitten/staan/liggen te« — Körperhaltung "
                      f"nur nennen, wenn bedeutsam")
    n_er = len(ER_EXIST.findall(low))
    if n_er > 2:
        zeilen.append(f"  {n_er}x »er is/zijn« — keine »es gibt«-Schwemme")

    if not zeilen:
        return ""
    return ("=== ACHTUNG IN DIESEM ABSCHNITT ===\n"
            + "\n".join(zeilen) + "\n\n")


# ==================================================================
def prompts(cfg):
    zb = G.zielbaustein(cfg)
    dim, tempus = G.projektbausteine(cfg)
    zusatz = G.lade_anweisungen("Übersetzung")

    uebersetzen = f"""Du bist eine erfahrene Literaturübersetzerin und \
überträgst ein niederländisches Werk ins Deutsche. Deine Übersetzungen \
erscheinen im Verlag.

DIE BESONDERE GEFAHR DIESER SPRACHRICHTUNG

Niederländisch und Deutsch sind eng verwandt. Verbzweitstellung, \
Verbletztstellung im Nebensatz, Modalpartikeln, Komposition, trennbare Verben \
— alles scheint sich eins zu eins übertragen zu lassen. Genau das ist die \
Falle: Eine wörtliche Übertragung ergibt grammatisch korrektes Deutsch, das \
im Register und in der Idiomatik trotzdem falsch ist, und das fällt beim \
Lesen nicht auf.

Übersetze nach Wirkung, nie nach Formähnlichkeit.

FALSCHE FREUNDE

Der Block ACHTUNG IN DIESEM ABSCHNITT nennt die Fälle, die hier wirklich \
vorkommen. Prüfe jeden einzeln. Besonders tückisch, weil beide Lesarten im \
Kontext funktionieren: »lopen« (gehen, nicht laufen), »mogen« (mögen oder \
dürfen), »gekocht« (gekauft, von kopen — nicht gekocht, das ist gekookt), \
»net« (gerade oder gepflegt), »enkel« (nur oder Knöchel), »naar« (nach oder \
unangenehm).

EVIDENTIELLES »ZOU«

»zou« + Infinitiv markiert im Niederländischen häufig Hörensagen, nicht \
Konditional. »Hij zou ziek zijn« heißt »Er soll krank sein«, nicht »Er wäre \
krank«. Entscheide nach Kontext: Steht die Aussage als Gerücht, Behauptung \
oder Bericht Dritter im Raum, gehört im Deutschen »soll«, »angeblich« oder \
»wie es heißt« hin. Erst wenn wirklich eine Bedingung oder ein Wunsch gemeint \
ist, kommt »würde« infrage. Diese Verwechslung verschiebt die Aussageebene \
des ganzen Absatzes.

DIMINUTIVE

{dim}

ERZÄHLTEMPUS

{tempus}

KONSTRUKTIONEN OHNE DEUTSCHE ENTSPRECHUNG

- »aan het + Infinitiv« als Verlaufsform: auflösen. Das deutsche »am Lesen \
sein« ist rheinisch-umgangssprachlich und in Erzählprosa fehl am Platz. \
Einfaches Präsens oder Präteritum, gegebenenfalls mit »gerade«.
- »zitten/staan/liggen te + Infinitiv«: hat keine deutsche Entsprechung. \
Auflösen; die Körperhaltung nur nennen, wenn sie bedeutsam ist.
- »gaan + Infinitiv« als Futur: deutsches Präsens oder »werden«, nicht »gehen«.
- »er« in Existenzsätzen, als Platzhalter, in Pronominaladverbien: Deutsch \
braucht es viel seltener. Vermeide eine »es gibt«-Schwemme.
- »om te + Infinitiv«: nicht immer »um zu«; oft reicht der bloße Infinitiv.

MODALPARTIKELN

Beide Sprachen haben sie, aber die Pragmatik deckt sich nicht. »toch« ist \
nicht immer »doch«, »wel« nicht »wohl«, »even« nicht »eben«, »maar« nicht \
»aber«, »eens« nicht »einmal«. »hoor« und »zeg« haben gar keine Entsprechung. \
Übersetze die Wirkung — durch Wortstellung, eine andere Partikel, einen \
Tonfall — und lass sie im Zweifel weg.

ANREDE

Vorgabe: »u« → Sie, »jij/je/jullie« → du/ihr. Beachte aber, dass »u« im \
heutigen Niederländisch enger verwendet wird als das deutsche Sie: wo \
Niederländer längst »je« sagen, siezen sich Deutsche noch. Wo die \
Anredematrix eine Abweichung nennt, gilt sie.

HANDWERK

- Bewahre Stimme, Register, Rhythmus und Grad der Förmlichkeit. Ist das \
Original knapp, sei knapp; ist es ausgeschmückt, sei ausgeschmückt.
- Halte die Absatzstruktur exakt ein. Hat der Abschnitt N durch Leerzeilen \
getrennte Absätze, hat deine Übersetzung dieselben N Absätze in derselben \
Reihenfolge. Verschmilz niemals zwei Absätze.
- Kulturgebundene Wörter: eine natürliche deutsche Lösung ist besser als eine \
Fußnote oder ein kursiv gesetztes niederländisches Wort. Behalte das \
Niederländische nur, wo der Text die Fremdheit selbst zum Thema macht.

ZIELFORM
{zb}

REFERENZBLÖCKE

PERSONEN nennt die zu verwendenden Pronomen. GLOSSAR nennt Entsprechungen, \
die durchgehend gelten. ANREDE nennt Abweichungen von der Vorgabe. ACHTUNG IN \
DIESEM ABSCHNITT nennt die Fallen dieses Abschnitts.

Das Ende des vorigen Abschnitts, deine eigene Übersetzung davon und der \
Anfang des nächsten Abschnitts sind NUR KONTEXT: für Konsistenz bei Namen, \
Terminologie, Tempus, Stimme und Stil und für einen nahtlosen Übergang. \
Übersetze den Kontext niemals erneut und wiederhole keinen Teil davon.

Der Block SO GEHT ES DANACH WEITER steht dort, damit du am Abschnittsende \
nicht blind bist: Er zeigt, worauf ein angefangener Satzbogen zuläuft, ob eine \
Figur gleich noch spricht, ob eine Anrede erst danach aufgelöst wird. Er ist \
KEIN Auftrag. Deine Ausgabe endet mit dem letzten Satz des Abschnitts ZU \
ÜBERSETZENDER TEXT — auch dann, wenn der Satzbogen dort mitten in der Bewegung \
abbricht.

Gib AUSSCHLIESSLICH die deutsche Übersetzung des mit ZU ÜBERSETZENDER TEXT \
markierten Abschnitts aus. Keine Vorrede, keine Anmerkungen, kein Kommentar, \
keine umschließenden Anführungszeichen."""

    revidieren = f"""Du bist erfahrene Lektorin für literarische Übersetzung \
ins Deutsche. Du bekommst einen niederländischen Ausgangstext und einen \
deutschen Entwurf dazu.

Überarbeite den Entwurf so, dass er als deutsche Prosa besteht und dem \
Original treu bleibt.

NIEDERLANDISMEN SUCHEN
- Wörtlich übertragene falsche Freunde. Der Block ACHTUNG IN DIESEM ABSCHNITT \
nennt die hier vorkommenden Fälle; prüfe jeden gegen den Entwurf.
- »zou« als Konditional übersetzt, wo es Hörensagen markiert: »Er wäre krank« \
statt »Er soll krank sein«.
- Verlaufsformen, die als »am …-sein« stehen geblieben sind.
- »zitten/staan/liggen te« mechanisch als Körperhaltung übersetzt.
- Eine Häufung von »es gibt« aus niederländischem »er«.
- Modalpartikeln, die nach Formähnlichkeit gesetzt wurden statt nach Wirkung.
- Satzbau, der niederländisch bleibt, obwohl das Deutsche anders gliedert.

DIMINUTIVE
{dim}
Zähle beim Lesen mit: Häufen sich »-chen« und »-lein«, ist mechanisch \
übertragen worden.

TEMPUS
{tempus}

WEITER
- Rhythmus und Kadenz verbessern, Satzlängen variieren.
- Jede Fehlübersetzung, Auslassung oder Hinzufügung gegen das Original prüfen.
- Kasus, Genus, Rektion und Zeitenfolge prüfen.
- Register, Stimme und Absatzstruktur exakt bewahren.
- Nicht umschreiben, nicht zusammenfassen. Jeder Satz des Originals muss \
vertreten sein.

ZIELFORM
{zb}

Ist der Entwurf schon gut, gib ihn mit minimalen Änderungen zurück.

ANSCHLUSS

Steht ein Block ENDE DES VORIGEN ABSCHNITTS, ist er NUR KONTEXT: Er zeigt, \
worauf der erste Satz des Entwurfs antwortet. Prüfe den Übergang — Tempus, \
Anrede, ein aufgenommenes Stichwort — und überarbeite ihn niemals mit. \
Wiederhole keinen Teil davon.

ABSATZSTRUKTUR

Die Zahl der Absätze bleibt, wie sie im Entwurf steht. Absätze \
zusammenzuziehen oder zu teilen macht die Fassung an anderer Stelle \
unbrauchbar, und deine Überarbeitung wird dann verworfen.

Gib AUSSCHLIESSLICH den überarbeiteten deutschen Text aus. Keine Vorrede, \
keine Anmerkungen, kein Kommentar."""

    # Additiv, in dieser Reihenfolge: Erst das Stilprofil als Beschreibung
    # des Werks, dann die Projektanweisungen, die Vorrang haben. Die
    # bestehenden Formulierungen bleiben unangetastet (Schutzklausel 1).
    stil = block_stilprofil(G.lade_json(G.F["stilprofil"], still=True))
    if stil:
        uebersetzen += stil
        revidieren += stil
    if zusatz:
        block = ("\n\nPROJEKTANWEISUNGEN (diese haben Vorrang vor den "
                 f"allgemeinen Regeln)\n\n{zusatz}")
        uebersetzen += block
        revidieren += block
    return uebersetzen, revidieren


# ==================================================================
def vorwegschau(chunks, i, fugen, n_woerter):
    """Der Anfang des naechsten Chunks als Kontext — oder nichts.

    Sie endet an der Ebenenfuge: Dort beginnt eine andere Erzaehlebene mit
    anderem Tempus und anderer Person, und ihr Anfang waere kein Ausblick,
    sondern eine Irrefuehrung. Genau davor schuetzt die Fuge, und die
    Vorwegschau darf sie nicht unterlaufen.

    Ein geschuetztes Zitat wird ebenfalls uebersprungen: Es bleibt im
    Original stehen und sagt ueber die Fortsetzung nichts.

    Spaetere Stapelfugen (Paket G) sind KEINE Ebenenfugen — dort laeuft
    die Vorwegschau weiter, weil sie nur eine technische Grenze ist."""
    if n_woerter <= 0 or i + 1 >= len(chunks):
        return ""
    if (i + 1) in fugen or chunks[i + 1][1]:
        return ""
    return G.anfangswoerter(chunks[i + 1][0], n_woerter)


def figuren_im_chunk(chunk, personen):
    """Namen aus personen.json, die in diesem Chunk vorkommen."""
    return {n for n in personen
            if re.search(r"\b" + re.escape(n) + r"'?s?\b", chunk)}


def block_personen(chunk, personen, figuren, nachhall=()):
    """Personenblock fuer den User-Prompt.

    'nachhall' sind Figuren aus den vorigen Chunks derselben Erzaehlebene.
    Grund: Eine Figur, die in Chunk 12 eingefuehrt und in Chunk 13 nur
    noch »hij« ist, verschwindet sonst aus dem Block — und mit ihr das
    Pronomen und die Sprechweise, die genau dann gebraucht werden. Der
    Nachhall wird an Ebenenfugen zurueckgesetzt und sonst nicht: Innerhalb
    einer Ebene bleibt die Figur dieselbe."""
    da = figuren_im_chunk(chunk, personen)
    treffer = {n: p for n, p in personen.items()
               if n in da or n in nachhall}
    if not treffer:
        return ""
    zeilen = []
    for n, p in sorted(treffer.items()):
        info = figuren.get(n, {}) if isinstance(figuren.get(n), dict) else {}
        z = f"  {n}: {p}"
        rolle = str(info.get("rolle", "")).strip()
        sprache = str(info.get("sprache", "")).strip()
        if rolle:
            z += f" — {rolle[:180]}"
        if sprache:
            z += f" [Sprechweise: {sprache[:140]}]"
        # Wer nur nachhallt, wird als solcher gekennzeichnet: Sonst sucht
        # das Modell den Namen im Abschnitt und findet ihn nicht.
        if n not in da:
            z += " (zuletzt erwähnt, hier nur als Pronomen)"
        zeilen.append(z)
    return "=== PERSONEN ===\n" + "\n".join(zeilen) + "\n\n"


STILFELDER = [("ton", "Ton"), ("register", "Register"),
              ("satzlaenge", "Satzbau"), ("tempus", "Tempusfuehrung")]


def block_stilprofil(stilprofil):
    """Baustein fuer den System-Prompt der Uebersetzung (Paket 4).

    Steht im System-Prompt und nicht im User-Prompt, weil er fuer das
    ganze Buch gilt: Nur so bleibt das zwischengespeicherte Praefix ueber
    alle Chunks identisch."""
    if not isinstance(stilprofil, dict) or not stilprofil:
        return ""
    zeilen = []
    for schluessel, titel in STILFELDER:
        wert = str(stilprofil.get(schluessel, "")).strip()
        if wert:
            zeilen.append(f"  {titel}: {wert}")
    perspektive = stilprofil.get("perspektive")
    if isinstance(perspektive, dict):
        for ebene, form in sorted(perspektive.items()):
            if str(form).strip():
                zeilen.append(f"  Erzählebene {ebene}: {form}")
    if not zeilen:
        return ""
    return ("\n\nSTILPROFIL DIESES WERKS\n\n"
            "Aus der Vorbereitung, gilt für das ganze Buch:\n"
            + "\n".join(zeilen) + "\n")


def kapitel_zuordnen(chunks, kapitel):
    """Je Chunk die zuletzt begonnene Kapitelueberschrift.

    Die Schluessel von kapitel.json sind Ueberschriften im Wortlaut der
    Quelle. Beginnt in einem Chunk ein neues Kapitel, gilt ab dort das
    neue; sonst wirkt das vorige fort. Ohne das Fortwirken bekaeme nur
    der eine Chunk mit der Ueberschrift seine Zeile."""
    aktuell, zuordnung = "", []
    for text, _ in chunks:
        treffer = [(text.rfind(k), k) for k in kapitel if k and k in text]
        if treffer:
            aktuell = max(treffer)[1]
        zuordnung.append(aktuell)
    return zuordnung


def stapel_warten(stapel, kennung, takt=20):
    """Wartet, bis der Stapel 'ended' meldet. Gibt die Zaehlung zurueck.

    Die Zeile bei jedem Blick ist kein Geschwaetz: In Colab haelt sie die
    Sitzung wach, und ohne sie sieht eine halbe Stunde Warten aus wie ein
    Absturz."""
    t0 = time.time()
    while True:
        stand, zahlen = stapel.stand(kennung)
        if stand == "ended":
            return zahlen
        offen = zahlen.get("processing", "?")
        print(f"    Stapel {kennung[-8:]}: {offen} offen, "
                f"{time.time()-t0:.0f}s", flush=True)
        time.sleep(takt)


def stapel_runde(cfg, stapel, auftraege, rolle, system, takt=20):
    """Eine Stapelrunde. auftraege: {kennung: user}. Gibt {kennung: text}.

    Was nicht durchkommt, fehlt im Ergebnis — der Aufrufer holt es
    einzeln nach. Das ist mehr als Aufraeumen: Ein abgelehnter Chunk kann
    auf dem synchronen Weg von einem Ersatzmodell beantwortet werden,
    'fallbacks' nimmt die Stapel-API naemlich nicht an."""
    if not auftraege:
        return {}
    modell = G.modell_fuer(cfg, rolle)
    b = G.BACKENDS["anthropic"]
    anfragen = [(k, b.payload(cfg, system, u, rolle, modell))
                for k, u in sorted(auftraege.items())]
    kennung = stapel.senden(anfragen)
    print(f"    Stapel {kennung[-8:]} abgeschickt: {len(anfragen)} "
          f"{rolle}", flush=True)
    stapel_warten(stapel, kennung, takt)
    raus = {}
    for kid, art, antwort in stapel.ergebnisse(kennung):
        if art != "succeeded":
            print(f"    {kid}: {art} — wird einzeln nachgeholt")
            continue
        try:
            text, usage = b.antwort_lesen(antwort)
        except G.ApiFehler as e:
            print(f"    {kid}: {e}")
            continue
        # Gebucht unter dem Stapeltarif — halbe Preise. In derselben
        # Zeile wie die synchronen Aufrufe waeren es Token zweier Preise.
        G.usage_buchen(rolle, G.bedient_von(antwort, modell), usage,
                       stapel=True)
        raus[kid] = text
    return raus


def wellenlauf(cfg, L):
    """Der Buchlauf ueber den Stapel, in Wellen. Gibt die Messwerte.

    Innerhalb einer Kette bleibt alles wie im seriellen Lauf: Rueckschau,
    Vorwegschau, Figurennachhall, Absatzpruefung. Was fehlt, ist die
    deutsche Rueckschau am ANFANG jeder Kette — dort gab es keinen
    Vorgaenger im selben Stapel. Der niederlaendische Quellschluss steht
    trotzdem da: Er haengt an keiner Uebersetzung.

    Was der Stapel nicht kann, holt der synchrone Weg: abgelehnte,
    abgelaufene und fehlerhafte Eintraege laufen einzeln nach. Das ist
    nicht nur Aufraeumen — auf dem synchronen Weg greift der
    Ablehnungsrueckfall, den die Stapel-API nicht annimmt."""
    chunks, fugen = L["chunks"], L["fugen"]
    praefix, revision = L["praefix"], L["revision"]
    n = len(chunks)
    kmax = int(cfg.get("kette_max", 0) or 0)
    kettenliste = G.ketten(n, fugen, kmax)
    extra = G.zusatzfugen(kettenliste, fugen)
    tiefe = max((len(k) for k in kettenliste), default=0)
    breit = max((len(w) for w in G.wellen(kettenliste)), default=0)
    print(f"Stapel:     {len(kettenliste)} Ketten, {tiefe} Wellen, "
          f"breiteste {breit}")
    print(f"            {len(extra)} zusätzliche Nähte ohne Rückschau "
            f"(kette_max {kmax or '—'})")

    stapel = G.Stapel(cfg)
    voraus_n = int(cfg.get("context_words_voraus", 0) or 0)
    nachhall_tiefe = int(cfg.get("figuren_nachhall", 0) or 0)
    zustand = [{"letzte": "", "nachhall": []} for _ in kettenliste]
    messwerte = []

    for t in range(tiefe):
        auftraege, ctx = {}, {}
        for ki, kette in enumerate(kettenliste):
            if t >= len(kette):
                continue
            i = kette[t]
            z = zustand[ki]
            quelle, geschuetzt = chunks[i]
            if geschuetzt:
                G.teil_schreiben("uebersetzung", i, quelle, praefix)
                G.teil_schreiben("entwurf", i, quelle, praefix)
                continue
            if i in fugen:
                z["letzte"] = ""
                z["nachhall"].clear()
            fertig = G.teil_lesen("uebersetzung", i, praefix)
            if fertig is not None:
                # Schon uebersetzt. Der Zustand der Kette muss trotzdem
                # weiterlaufen, sonst faengt der naechste Chunk ohne
                # Rueckschau an — der Resume kostete sonst Qualitaet.
                z["letzte"] = G.schlusswoerter(fertig, cfg["context_words"])
                if nachhall_tiefe:
                    z["nachhall"].append(
                        figuren_im_chunk(quelle, L["daten"]["personen"]))
                    del z["nachhall"][:-nachhall_tiefe]
                continue
            erinnert = set().union(*z["nachhall"]) if z["nachhall"] else set()
            kopf = referenzkopf(cfg, quelle, L["ebenen"][i],
                                L["kapitelzeilen"][i], erinnert, L["daten"],
                                L["perspektive"])
            # Der Quellschluss steht auch am Kettenanfang zur Verfuegung:
            # Er ist Original und haengt an keiner Uebersetzung. Nur die
            # eigene Fassung fehlt dort.
            vorher = (G.schlusswoerter(chunks[i-1][0], cfg["context_words"])
                      if i > 0 and i not in fugen and not chunks[i-1][1]
                      else "")
            kid = f"ueb-{i:04d}"
            auftraege[kid] = nutzerprompt(
                kopf, quelle, vorher, z["letzte"],
                vorwegschau(chunks, i, fugen, voraus_n))
            ctx[kid] = (ki, i, kopf, quelle)

        if not auftraege:
            continue
        print(f"\nWelle {t+1}/{tiefe}: {len(auftraege)} Chunks", flush=True)
        entwuerfe = stapel_runde(cfg, stapel, auftraege, "uebersetzung",
                                 L["p_ueb"])
        # Was der Stapel nicht geliefert hat, einzeln nachholen.
        for kid in sorted(set(auftraege) - set(entwuerfe)):
            print(f"    {kid} einzeln …", flush=True)
            try:
                entwuerfe[kid] = G.chat(cfg, L["p_ueb"], auftraege[kid],
                                        rolle="uebersetzung")
            except Exception as e:
                print(f"    {kid}: auch einzeln gescheitert — {e}")

        rev_auftraege = {}
        for kid, entwurf in sorted(entwuerfe.items()):
            ki, i, kopf, quelle = ctx[kid]
            r = G.verhaeltnis(quelle, entwurf)
            if not entwurf or not (cfg["ratio_min"] <= r <= cfg["ratio_max"]):
                print(f"    Chunk {i+1}: Verhältnis {r:.2f} übernommen")
            if revision:
                rev_auftraege[kid] = revisionsbody(
                    kopf, quelle, entwurf, zustand[ki]["letzte"])

        revisionen = (stapel_runde(cfg, stapel, rev_auftraege, "revision",
                                   L["p_rev"]) if rev_auftraege else {})

        for kid, entwurf in sorted(entwuerfe.items()):
            ki, i, _, quelle = ctx[kid]
            na = len(G.absaetze(quelle))
            endfassung = entwurf
            rev = revisionen.get(kid)
            if rev:
                r2 = G.verhaeltnis(quelle, rev)
                n_rev = len(G.absaetze(rev))
                if not (cfg["ratio_min"] <= r2 <= cfg["ratio_max"]):
                    print(f"    Chunk {i+1}: Revision verworfen "
                            f"({r2:.2f}x)")
                elif n_rev != na:
                    print(f"    Chunk {i+1}: Revision verworfen, "
                            f"Absätze {na} -> {n_rev}")
                else:
                    endfassung = rev
            nb = len(G.absaetze(endfassung))
            if na != nb:
                # Im seriellen Lauf wird hier wiederholt. In der Welle
                # waere das eine zweite Runde fuer einen einzelnen Chunk —
                # billiger und genauso richtig ist der synchrone Weg.
                print(f"    Chunk {i+1}: Absätze {na} -> {nb}, "
                        f"einzeln wiederholt")
                try:
                    endfassung = G.chat(cfg, L["p_ueb"], auftraege[kid],
                                        rolle="uebersetzung")
                except Exception as e:
                    print(f"    Chunk {i+1}: Wiederholung gescheitert — {e}")
            messwerte.append(G.verhaeltnis(quelle, endfassung))
            G.teil_schreiben("entwurf", i, entwurf, praefix)
            G.teil_schreiben("uebersetzung", i, endfassung, praefix)
            rueck = (entwurf if cfg.get("rueckschau_quelle") == "entwurf"
                     else endfassung)
            zustand[ki]["letzte"] = G.schlusswoerter(rueck,
                                                     cfg["context_words"])
            if nachhall_tiefe:
                zustand[ki]["nachhall"].append(
                    figuren_im_chunk(quelle, L["daten"]["personen"]))
                del zustand[ki]["nachhall"][:-nachhall_tiefe]
        print(f"  Welle {t+1} fertig: {len(entwuerfe)} Chunks",
              flush=True)
    return messwerte


def referenzkopf(cfg, quelle, ebene, kapitelzeile, erinnert, daten,
                 perspektive):
    """Die Referenzbloecke dieses Chunks, in fester Reihenfolge.

    'daten' buendelt Glossar, Personen, Figurenblatt, Anrede, Leitmotive
    und Kapitel — sechs Argumente, die immer zusammen gereicht werden.
    Die Reihenfolge der Bloecke ist Prompt und nicht Geschmack: Wer sie
    umsortiert, aendert den Prompt fuer jeden Chunk."""
    return (block_ebene(ebene, perspektive)
            + block_kapitel(kapitelzeile, daten["kapitel"])
            + block_fallen(quelle, cfg)
            + block_personen(quelle, daten["personen"], daten["figuren"],
                             erinnert)
            + block_glossar(quelle, daten["glossar"])
            + block_anrede(quelle, daten["personen"], daten["anrede"])
            + block_leitmotive(quelle, daten["leitmotive"]))


def nutzerprompt(kopf, quelle, vorher, letzte, voraus):
    """Der User-Prompt eines Uebersetzungschunks.

    Die Reihenfolge traegt Bedeutung: Die Vorwegschau steht VOR dem
    Auftrag, nicht dahinter. Was zuletzt im Prompt steht, liest ein
    Modell als das, was zu tun ist — hinter dem Auftrag waere sie eine
    Einladung, einfach weiterzuuebersetzen.

    Die Funktion steht hier und nicht in der Schleife, weil zwei Wege sie
    brauchen: der serielle Lauf und der Wellenlauf ueber den Stapel. Zwei
    Montagen waeren zwei Prompts, und nur einer wuerde geprueft."""
    user = kopf
    if vorher:
        user += ("=== ENDE DES VORIGEN ABSCHNITTS, ORIGINAL "
                 "(nur Kontext) ===\n" + vorher + "\n\n")
    if letzte:
        user += ("=== ENDE DES VORIGEN ABSCHNITTS, DEINE ÜBERSETZUNG "
                 "(nur Kontext, nicht wiederholen) ===\n" + letzte + "\n\n")
    if voraus:
        user += ("=== SO GEHT ES DANACH WEITER (nur Kontext, "
                 "NICHT übersetzen) ===\n" + voraus + "\n\n")
    return user + "=== ZU ÜBERSETZENDER TEXT ===\n" + quelle


def revisionsbody(kopf, quelle, entwurf, letzte):
    """Der User-Prompt der Revision.

    Die Rueckschau gehoert auch hierher. Ohne sie glaettet Pass 2 genau
    die Anschluesse weg, die Pass 1 muehsam hergestellt hat: Der Reviser
    sieht sonst nur Quelle und Entwurf und weiss nicht, worauf der erste
    Satz antwortet."""
    body = kopf
    if letzte:
        body += ("=== ENDE DES VORIGEN ABSCHNITTS, DEINE ÜBERSETZUNG "
                 "(nur Kontext, nicht wiederholen) ===\n" + letzte + "\n\n")
    return (body + "=== NIEDERLÄNDISCHER AUSGANGSTEXT ===\n" + quelle
            + "\n\n=== DEUTSCHER ENTWURF ===\n" + entwurf)


def block_ebene(name, perspektive):
    """Nennt die Erzaehlebene des Abschnitts im User-Prompt (Paket 5).

    Formulierung kommt aus stilprofil.json, nicht aus dem Code — ein
    hartkodiertes 'dritte Person Praesens' waere beim naechsten Buch
    falsch und niemand suchte es hier."""
    if not name:
        return ""
    form = str((perspektive or {}).get(name, "")).strip()
    if not form:
        return ""
    return f"=== ERZÄHLEBENE ===\n  {name}: {form}\n\n"


def block_kapitel(ueberschrift, kapitel):
    if not ueberschrift:
        return ""
    zeile = str(kapitel.get(ueberschrift, "")).strip()
    if not zeile:
        return ""
    return f"=== KAPITEL ===\n  {ueberschrift}: {zeile}\n\n"


def block_glossar(chunk, glossar):
    treffer = {k: v for k, v in glossar.items() if k in chunk}
    if not treffer:
        return ""
    return ("=== GLOSSAR (diese Entsprechungen verwenden) ===\n"
            + "\n".join(f"  {k} -> {v}" for k, v in sorted(treffer.items()))
            + "\n\n")


def block_anrede(chunk, personen, anrede):
    if not anrede:
        return ""
    anwesend = {n for n in personen
                if re.search(r"\b" + re.escape(n) + r"'?s?\b", chunk)}
    zeilen = []
    for name, d in anrede.items():
        if name.startswith("_") or not isinstance(d, dict):
            continue
        if set(d.get("figuren", [])) & anwesend:
            zeilen.append(f"  {name}: niederländisch "
                          f"{d.get('niederlaendisch', '?')} -> deutsch "
                          f"{d.get('deutsch', '')}")
    return ("=== ANREDE (Abweichungen von der Vorgabe) ===\n"
            + "\n".join(zeilen) + "\n\n") if zeilen else ""


def block_leitmotive(chunk, leitmotive):
    if not leitmotive:
        return ""
    zeilen = []
    for k, d in leitmotive.items():
        if k.startswith("_") or not isinstance(d, dict):
            continue
        v = str(d.get("vorschlag", "")).strip()
        if v and k.lower() in chunk.lower() and not v.startswith(("TITEL", "PRUEF")):
            zeilen.append(f"  {k} -> {v}")
    return ("=== LEITMOTIVE (durchgehend gleich übersetzen) ===\n"
            + "\n".join(zeilen) + "\n\n") if zeilen else ""


# ==================================================================
REDE = tuple("„“«»'\"\u2018\u2014\u2013")


def fallendichte(text):
    """Fallen je 1000 Woerter — falsche Freunde, Diminutive, zou, aan het.

    Deterministisch aus denselben Mustern, die 'block_fallen' im Prompt
    ausweist. Der Auszug, der danach ausgewaehlt wird, ist damit genau
    der, in dem die Warnungen am dichtesten stehen — und damit der, an dem
    sich zeigt, ob sie wirken."""
    low = text.lower()
    w = max(1, len(text.split()))
    n = sum(len(re.findall(rf"\b{re.escape(nl)}\w{{0,3}}\b", low))
            for nl, _, _ in VALSE_VRIENDEN)
    n += len([x for x in DIMINUTIV_NL.findall(low)
              if x not in DIM_LEXIKALISIERT])
    n += len(ZOU.findall(low)) + len(AAN_HET.findall(low))
    n += len(POSTUUR.findall(low)) + len(ER_EXIST.findall(low))
    return n / (w / 1000)


def testauszuege(paras, n_erzaehlung, n_dialog, n_fallen=0):
    laengen = [len(p.split()) for p in paras]
    gesamt = sum(laengen)

    lauf, start = 0, 0
    for i, w in enumerate(laengen):
        lauf += w
        if lauf >= gesamt // 2 - n_erzaehlung // 2:
            start = i
            break
    teil1, n = [], 0
    for p in paras[start:]:
        teil1.append(p)
        n += len(p.split())
        if n >= n_erzaehlung:
            break
    ende1 = start + len(teil1)

    def ist_rede(p):
        return p.lstrip()[:1] in REDE

    bestes, bester_wert, i = 0, -1.0, 0
    while i < len(paras):
        j, w, rede = i, 0, 0
        while j < len(paras) and w < n_dialog:
            w += laengen[j]
            rede += laengen[j] if ist_rede(paras[j]) else 0
            j += 1
        if w >= n_dialog * 0.7 and not (i < ende1 and j > start):
            wert = rede / max(1, w)
            if wert > bester_wert:
                bester_wert, bestes = wert, i
        i += 3

    teil2, n = [], 0
    for p in paras[bestes:]:
        teil2.append(p)
        n += len(p.split())
        if n >= n_dialog:
            break
    ende2 = bestes + len(teil2)

    # Dritter Auszug: die Fallenpassage. Erzaehlung und Dialog messen, ob
    # der Text als deutsche Prosa besteht; dieser misst, ob die
    # Warnungen aus dem Fallenblock ankommen. Das ist die Schwaeche
    # dieser Sprachrichtung, und sie faellt in einem ruhigen
    # Erzaehlabschnitt gar nicht auf.
    teil3, dichte3 = [], 0.0
    if n_fallen > 0:
        belegt = set(range(start, ende1)) | set(range(bestes, ende2))
        bester3, wert3, i = None, -1.0, 0
        while i < len(paras):
            j, w = i, 0
            while j < len(paras) and w < n_fallen:
                w += laengen[j]
                j += 1
            if w >= n_fallen * 0.7 and not (belegt & set(range(i, j))):
                d = fallendichte("\n\n".join(paras[i:j]))
                if d > wert3:
                    wert3, bester3 = d, i
            i += 3
        if bester3 is not None:
            n = 0
            for p in paras[bester3:]:
                teil3.append(p)
                n += len(p.split())
                if n >= n_fallen:
                    break
            dichte3 = wert3
    return teil1, teil2, teil3, {"dialogdichte": bester_wert,
                                 "fallendichte": dichte3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--variante", default="A",
                    help="Name aus 'varianten' in projekt.json; A ist die "
                         "Basis und schreibt nach test/")
    ap.add_argument("--no-revision", action="store_true")
    ap.add_argument("--stapel", action="store_true",
                    help="ueber die Stapel-API in Wellen (halber Preis, "
                         "zusaetzliche Naehte — 'pipeline.py wellen' zeigt "
                         "den Plan)")
    ap.add_argument("--chunk", type=int, default=None,
                    help="nur diesen Chunk neu rechnen (1-basiert)")
    args = ap.parse_args()

    G.kopf("UEBERSETZUNG" + (f" (Test {args.variante})" if args.test else ""))
    cfg = G.lade_config()
    R.sicherstellen(cfg)          # No-op ohne sheets_id
    revision = cfg["revision_pass"] and not args.no_revision
    chunk_words, beschreibung = cfg["chunk_words"], "Basis"
    if args.variante != "A":
        v = next((x for x in G.varianten(cfg)
                  if x["name"] == args.variante), None)
        if not v:
            moeglich = ", ".join(["A"] + [x["name"] for x in G.varianten(cfg)])
            sys.exit(f"FEHLER: Variante '{args.variante}' steht nicht in "
                     f"projekt.json.\n  Moeglich: {moeglich}")
        cfg, chunk_words, beschreibung = G.variante_anwenden(cfg, v)

    if not os.path.exists(G.F["quelle"]):
        sys.exit(f"FEHLER: {G.F['quelle']} nicht gefunden.")
    paras_alle = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
    zitate = G.lade_json(G.F["zitate"], still=True).get("epigraphen", [])

    if args.test:
        praefix = ("test" if args.variante == "A"
                   else "test" + args.variante) + "/"
        os.makedirs(praefix, exist_ok=True)
        t1, t2, t3, kennzahlen = testauszuege(
            paras_alle, cfg["test_words_erzaehlung"], cfg["test_words_dialog"],
            int(cfg.get("test_words_fallen", 0) or 0))
        print(f"Teil 1 (Erzählung): {sum(len(p.split()) for p in t1)} Wörter, "
              f"{len(t1)} Absätze")
        print(f"Teil 2 (Dialog):    {sum(len(p.split()) for p in t2)} Wörter, "
              f"{len(t2)} Absätze, Redeanteil "
              f"{kennzahlen['dialogdichte']:.0%}")
        if t3:
            print(f"Teil 3 (Fallen):    {sum(len(p.split()) for p in t3)} "
                  f"Wörter, {len(t3)} Absätze, "
                  f"{kennzahlen['fallendichte']:.0f} Fallen je 1000 Wörter")
        print(f"Variante {args.variante}:         {beschreibung}\n")
        gruppen = [g for g in (t1, t2, t3) if g]
        marken = {}
        # Wo die Auszuege im Ergebnis aneinanderstossen, muss die
        # Bewertung wissen — sonst trennt sie bei 'Haelfte der Absaetze'
        # und vergleicht Erzaehlung gegen Dialog. Die Absatzzahl ist
        # belastbar, seit ein Chunk mit verschobener Absatzzahl
        # wiederholt wird.
        os.makedirs(praefix, exist_ok=True)
        with open(praefix + "teile.json", "w", encoding="utf-8") as f:
            json.dump({"erzaehlung": len(t1), "dialog": len(t2),
                       "fallen": len(t3)}, f, ensure_ascii=False, indent=2)
        # Der Testlauf schneidet Auszuege statt Erzaehlebenen; die
        # Chunkbildung darunter ist dieselbe, nur ohne Ebenennamen.
        G.lauf_setzen(praefix)
        chunks, fugen, ebene_je_chunk = [], set(), []
        for gruppe in gruppen:
            teil = G.chunks_bauen(gruppe, chunk_words)
            if chunks:
                fugen.add(len(chunks))
            chunks.extend(teil)
            ebene_je_chunk.extend([""] * len(teil))
    else:
        # Der Buchlauf und die beiden Leser (Leseausgabe, Screening)
        # bauen ihre Quellchunks ueber DIESELBE Funktion. Zwei Wege
        # dorthin sind auseinandergelaufen, sobald einer ebenen.json las
        # und der andere nicht — und dann steht ueberall der falsche
        # Absatz neben dem falschen, ohne dass es auffaellt.
        praefix = ""
        G.lauf_setzen(praefix)
        marken, chunks, fugen, ebene_je_chunk = G.quellchunks(
            cfg, paras_alle, zitate, chunk_words)

    n = len(chunks)
    perspektive = G.lade_json(G.F["stilprofil"], still=True).get("perspektive")
    G.ueberlaengen_melden(chunks, chunk_words)
    glossar = G.lade_json(G.F["glossar"])
    personen = G.lade_json(G.F["personen"])
    figuren = G.lade_json(G.F["figuren"])
    anrede = G.lade_json(G.F["anrede"])
    leitmotive = G.lade_json(G.F["leitmotive"])
    kapitel = G.lade_json(G.F["kapitel"], still=True)
    # Die sechs Referenzdateien werden immer zusammen gereicht; als
    # Buendel bleibt die Signatur von 'referenzkopf' lesbar.
    daten = {"glossar": glossar, "personen": personen, "figuren": figuren,
             "anrede": anrede, "leitmotive": leitmotive, "kapitel": kapitel}
    kapitel_je_chunk = kapitel_zuordnen(chunks, kapitel)
    p_ueb, p_rev = prompts(cfg)
    fingerprint = G.config_hash(cfg)

    m_ueb = G.modell_fuer(cfg, "uebersetzung")
    print(f"Modell:     {m_ueb} ({G.backend_name(m_ueb)}, "
          f"Effort {G.effort_fuer(cfg, 'uebersetzung')})")
    m_rev = G.modell_fuer(cfg, "revision")
    if revision and m_rev != m_ueb:
        print(f"  Revision: {m_rev} ({G.backend_name(m_rev)}, "
              f"Effort {G.effort_fuer(cfg, 'revision')})")
    print(f"Zielform:   {cfg['varietaet']}, "
          f"{'»…«' if cfg['quotes']=='guillemets' else '„…“'}, "
          f"{'mit ß' if cfg['eszett'] else 'ohne ß'}")
    print(f"Diminutive: {cfg['diminutive']}   Tempus: {cfg['tempus']}")
    print(f"Eingabe:    {sum(len(c) for c, _ in chunks)} Zeichen in {n} Chunks")
    print(f"Glossar {len(glossar)} | Personen {len(personen)} | "
          f"Anrede {len(anrede)} | Leitmotive {len(leitmotive)}")
    stil = G.lade_json(G.F["stilprofil"], still=True)
    print(f"Stilprofil: {'ja' if block_stilprofil(stil) else 'nein'}   "
          f"Kapitel: {len(kapitel)}")
    print(f"Revision:   {'ja' if revision else 'nein'}")
    if marken:
        print(f"Zitate:     {len([k for k,v in marken.items() if v])} "
              f"ausgeklammert")
    print(f"Fingerprint:{fingerprint}\n")

    state_p = praefix + "uebersetzung_state.json"
    state = G.lade_json(state_p, still=True)
    if state and state.get("fingerprint") not in (None, fingerprint):
        print("WARNUNG: Konfiguration oder anweisungen.md haben sich seit dem "
              "letzten Lauf geändert.")
        print("Die bereits übersetzten Chunks stammen aus anderen Vorgaben.")
        print("Entweder zurücksetzen (pipeline.py reset --ab voll) oder "
              "bewusst weiterlaufen lassen.\n")

    def warnen(msg):
        print(f"    {msg}")
        with open(praefix + WARN, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    # --- Retranslate einzelner Chunk (V11b) ---
    if args.chunk is not None:
        i = args.chunk - 1
        if not (0 <= i < n):
            sys.exit(f"FEHLER: Chunk {args.chunk} liegt nicht in 1..{n}")
        for art in ("uebersetzung", "entwurf"):
            p = G.teil_pfad(art, i, praefix)
            if os.path.exists(p):
                os.remove(p)
        print(f"Chunk {args.chunk} wird neu gerechnet.\n")
        zu_tun = [i]
    else:
        offen = G.teile_vorhanden("uebersetzung", n, praefix)
        if offen:
            print(f"{offen} Chunks liegen vor, Fortsetzung ab {offen+1}.\n")
        zu_tun = list(range(offen, n))

    letzte = ""
    if zu_tun and zu_tun[0] > 0:
        art = ("entwurf" if cfg.get("rueckschau_quelle") == "entwurf"
               else "uebersetzung")
        vorige = G.teil_lesen(art, zu_tun[0] - 1, praefix)
        if vorige and zu_tun[0] not in fugen:
            letzte = G.schlusswoerter(vorige, cfg["context_words"])

    # Figurennachhall: Namen aus den letzten Chunks DERSELBEN Ebene. Beim
    # Fortsetzen wird er aus den vorhandenen Quellchunks rekonstruiert —
    # sonst faengt ein wiederaufgenommener Lauf ohne Gedaechtnis an.
    nachhall_tiefe = int(cfg.get("figuren_nachhall", 0) or 0)
    nachhall = []
    if nachhall_tiefe and zu_tun:
        letzte_fuge = max([f for f in fugen if f <= zu_tun[0]], default=0)
        ab = max(letzte_fuge, zu_tun[0] - nachhall_tiefe)
        for k in range(ab, zu_tun[0]):
            if not chunks[k][1]:
                nachhall.append(figuren_im_chunk(chunks[k][0], personen))

    voraus_n = int(cfg.get("context_words_voraus", 0) or 0)
    if voraus_n and not args.test:
        print(f"Vorwegschau:        {voraus_n} Wörter, endet an jeder Fuge")

    kosten_vorher = G.kosten_schnappschuss() if praefix else None
    start = time.time()
    messwerte = []

    if args.stapel and G.backend_name(m_ueb) != "anthropic":
        sys.exit(f"FEHLER: {m_ueb} hat keine Stapel-API.\n"
                 f"  Der Stapelbetrieb gilt nur fuer den Anthropic-Pfad; "
                 f"ohne '--stapel' laeuft alles wie bisher.")
    if args.stapel:
        # Der Wellenlauf hat seinen eigenen Zustand je Kette und liest
        # fertige Chunks selbst — 'zu_tun', 'letzte' und 'nachhall' oben
        # gelten fuer den seriellen Weg.
        messwerte = wellenlauf(cfg, {
            "chunks": chunks, "fugen": fugen, "ebenen": ebene_je_chunk,
            "kapitelzeilen": kapitel_je_chunk, "daten": daten,
            "perspektive": perspektive, "p_ueb": p_ueb, "p_rev": p_rev,
            "praefix": praefix, "revision": revision})
        zu_tun = []

    for zaehler, i in enumerate(zu_tun, 1):
        quelle, geschuetzt = chunks[i]
        if geschuetzt:
            G.teil_schreiben("uebersetzung", i, quelle, praefix)
            G.teil_schreiben("entwurf", i, quelle, praefix)
            print(f"[{i+1}/{n}] geschützter Absatz, unverändert übernommen")
            continue

        if i in fugen:
            letzte, vorher = "", ""
            nachhall.clear()          # neue Ebene, neues Figurengedaechtnis
            print("--- Ebenenfuge: Kontext und Figurengedächtnis "
                  "zurückgesetzt ---")
        else:
            vorher = (G.schlusswoerter(chunks[i-1][0], cfg["context_words"])
                      if i > 0 and not chunks[i-1][1] else "")

        voraus = vorwegschau(chunks, i, fugen, voraus_n)

        print(f"[{i+1}/{n}] {len(quelle.split())} Wörter", flush=True)
        t0 = time.time()

        for versuch in range(1, cfg["max_retries"] + 1):
            try:
                erinnert = set().union(*nachhall) if nachhall else set()
                kopf = referenzkopf(cfg, quelle, ebene_je_chunk[i],
                                    kapitel_je_chunk[i], erinnert, daten,
                                    perspektive)
                user = nutzerprompt(kopf, quelle, vorher, letzte, voraus)

                entwurf = G.chat(cfg, p_ueb, user, rolle="uebersetzung")
                if not entwurf:
                    raise RuntimeError("leere Antwort in Pass 1")

                r = G.verhaeltnis(quelle, entwurf)
                if not (cfg["ratio_min"] <= r <= cfg["ratio_max"]):
                    if versuch < cfg["max_retries"]:
                        warnen(f"Chunk {i+1}: Verhältnis {r:.2f} -> "
                               f"neuer Versuch")
                        raise RuntimeError("Längenprüfung")
                    warnen(f"Chunk {i+1}: Verhältnis {r:.2f} übernommen")
                print(f"    Pass 1  {time.time()-t0:5.0f}s  ({r:.2f}x)",
                      flush=True)

                na = len(G.absaetze(quelle))
                endfassung = entwurf
                if revision:
                    t1 = time.time()
                    # Die Rueckschau gehoert auch in die Revision. Ohne
                    # sie glaettet Pass 2 genau die Anschluesse weg, die
                    # Pass 1 muehsam hergestellt hat: Der Reviser sieht
                    # nur Quelle und Entwurf und weiss nicht, worauf der
                    # erste Satz antwortet.
                    body = revisionsbody(kopf, quelle, entwurf, letzte)
                    rev = G.chat(cfg, p_rev, body, rolle="revision")
                    r2 = G.verhaeltnis(quelle, rev)
                    # Die Revision wird verworfen, wenn sie das Verhaeltnis
                    # ODER die Absatzzahl verletzt. Verwerfen ist hier
                    # billiger als der neue Versuch weiter unten: Der
                    # Entwurf liegt schon vor und ist brauchbar.
                    n_rev = len(G.absaetze(rev)) if rev else 0
                    if not rev or not (cfg["ratio_min"] <= r2
                                       <= cfg["ratio_max"]):
                        warnen(f"Chunk {i+1}: Revision verworfen ({r2:.2f}x)")
                    elif n_rev != na:
                        warnen(f"Chunk {i+1}: Revision verworfen, "
                               f"Absätze {na} -> {n_rev}")
                    else:
                        endfassung = rev
                        print(f"    Pass 2  {time.time()-t1:5.0f}s  "
                              f"({r2:.2f}x)", flush=True)

                nb = len(G.absaetze(endfassung))
                if na != nb:
                    # Eine verschobene Absatzzahl ist kein Schoenheits-
                    # fehler: Die Leseausgabe stellt Quelle und Fassung
                    # absatzweise nebeneinander, die Zitate werden nach
                    # Absatzposition eingesetzt, und qa.py misst das
                    # Tempus je Ebene ueber die Absatzzuordnung. Alles
                    # drei verrutscht ab hier. Deshalb ein neuer Versuch,
                    # solange einer uebrig ist.
                    if versuch < cfg["max_retries"]:
                        warnen(f"Chunk {i+1}: Absätze {na} -> {nb} -> "
                               f"neuer Versuch")
                        raise RuntimeError("Absatzzahl")
                    warnen(f"Chunk {i+1}: Absätze {na} -> {nb} übernommen")
                messwerte.append(G.verhaeltnis(quelle, endfassung))

                G.teil_schreiben("entwurf", i, entwurf, praefix)
                G.teil_schreiben("uebersetzung", i, endfassung, praefix)
                # Woraus die Rueckschau gebildet wird, ist eine offene
                # Frage: die Revision ist besser, der Entwurf ist das,
                # woran der naechste Chunk stilistisch anschliesst.
                # Umschaltbar, gemessen wird im Testlauf.
                rueck = (entwurf if cfg.get("rueckschau_quelle") == "entwurf"
                         else endfassung)
                letzte = G.schlusswoerter(rueck, cfg["context_words"])
                if nachhall_tiefe:
                    nachhall.append(figuren_im_chunk(quelle, personen))
                    del nachhall[:-nachhall_tiefe]
                json.dump({"total": n, "fingerprint": fingerprint,
                           "chunk_words": chunk_words, "rev": revision},
                          open(state_p, "w"))
                print("    " + G.fortschritt(zaehler, len(zu_tun), start,
                                             "fertig") + "\n", flush=True)
                break

            except Exception as e:
                # Ein erschoepftes Kontingent aendert sich durch
                # Wiederholen nicht — sofort abbrechen, mit dem Grund
                # statt mit dreimal demselben API-Rohtext.
                if G.kontingent_erschoepft(e):
                    sys.exit(G.kontingent_text(e)
                             + f"\n\n  Abbruch bei Chunk {i+1}.")
                print(f"    Versuch {versuch}/{cfg['max_retries']}: {e}")
                if versuch == cfg["max_retries"]:
                    sys.exit(f"\nAbbruch bei Chunk {i+1}. "
                             f"Neustart setzt hier fort.")
                time.sleep(5 * versuch)

    # --- Zusammensetzen; Zitate immer einfuegen (F6a) ---
    for art, datei in (("uebersetzung", G.F["uebersetzung"]),
                       ("entwurf", G.F["entwurf"])):
        ganz = G.teile_zusammensetzen(art, n, praefix)
        if ganz is None:
            print(f"WARNUNG: {art} noch unvollständig, nicht zusammengesetzt.")
            continue
        if art == "uebersetzung" and marken:
            ganz, bericht = zitate_einsetzen(ganz, marken, paras_alle)
            print("\nZitate:")
            for z in bericht:
                print("  " + z)
        open(praefix + datei, "w", encoding="utf-8").write(ganz + "\n")

    # Die Kalibrierung liest ALLE vorliegenden Chunks, nicht nur die in
    # diesem Aufruf gerechneten. Sonst entscheidet der Zufall mit: Wird der
    # Testlauf unterbrochen und setzt fort, blieben sonst zu wenige
    # Messwerte uebrig und die Grenzen blieben still uneingemessen — genau
    # das ist bei der Abbruchprobe am 31.07.2026 passiert.
    if args.test and args.variante == "A":
        messwerte = []
        for i in range(n):
            fertig = G.teil_lesen("uebersetzung", i, praefix)
            if fertig and not chunks[i][1]:      # geschuetzte Absaetze nicht
                messwerte.append(G.verhaeltnis(chunks[i][0], fertig))

    if args.test and len(messwerte) >= 3 and args.variante == "A":
        messwerte.sort()
        med = messwerte[len(messwerte)//2]
        spanne = max(0.10, (messwerte[-1] - messwerte[0]) * 0.8)
        cfg["ratio_min"] = round(max(0.70, med - spanne), 2)
        cfg["ratio_max"] = round(min(1.60, med + spanne), 2)
        cfg["ratio_kalibriert"] = True
        G.speichere_config(cfg)
        print(f"\nPrüfgrenzen kalibriert: Median {med:.2f}, Bereich "
              f"{cfg['ratio_min']:.2f}–{cfg['ratio_max']:.2f} "
              f"({len(messwerte)} Chunks)")
    elif args.test and args.variante == "A":
        print(f"\nPrüfgrenzen NICHT kalibriert: nur {len(messwerte)} "
              f"verwertbare Chunks, mindestens 3 nötig.")

    if kosten_vorher is not None:
        G.kosten_differenz_schreiben(kosten_vorher,
                                     praefix + "kosten.json")
    print(f"\nFertig nach {(time.time()-start)/60:.0f} min.")
    print(f"  Endfassung: {praefix + G.F['uebersetzung']}")
    print(f"  Entwurf:    {praefix + G.F['entwurf']}")


def zitate_einsetzen(zieltext, marken, paras_alle):
    """Setzt Zitat und Attribution an ihrer Position ein. Idempotent:
    laeuft auf dem zusammengesetzten Text, also bei jedem Aufruf gleich."""
    bericht = []
    paras = G.absaetze(zieltext)
    # Position im Zieltext = Anzahl nicht ausgeklammerter Absaetze davor
    for idx in sorted([k for k, v in marken.items() if v], reverse=True):
        z = marken[idx]
        davor = sum(1 for i in range(idx) if i not in marken)
        original = z.get("original_deutsch")
        if original and str(original).strip():
            eintrag = str(original).strip()
            bericht.append(f"eingesetzt: {z['attribution']}")
        else:
            eintrag = (f"[[ZITAT NICHT EINGESETZT — deutscher Wortlaut fehlt "
                       f"in {G.F['zitate']}]]\n\n"
                       f"[[Niederländisch: {z['text'][:200]}]]")
            bericht.append(f"PLATZHALTER: {z['attribution']} — "
                           f"original_deutsch ist leer")
        stelle = min(davor, len(paras))
        paras.insert(stelle, z["attribution"])
        paras.insert(stelle, eintrag)
    return "\n\n".join(paras), bericht


if __name__ == "__main__":
    main()
