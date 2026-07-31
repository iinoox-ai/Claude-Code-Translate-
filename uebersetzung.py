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

Das Ende des vorigen Abschnitts und deine eigene Übersetzung davon sind NUR \
KONTEXT: für Konsistenz bei Namen, Terminologie, Tempus, Stimme und Stil und \
für einen nahtlosen Übergang. Übersetze den Kontext niemals erneut und \
wiederhole keinen Teil davon.

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

Gib AUSSCHLIESSLICH den überarbeiteten deutschen Text aus. Keine Vorrede, \
keine Anmerkungen, kein Kommentar."""

    if zusatz:
        block = ("\n\nPROJEKTANWEISUNGEN (diese haben Vorrang vor den "
                 f"allgemeinen Regeln)\n\n{zusatz}")
        uebersetzen += block
        revidieren += block
    return uebersetzen, revidieren


# ==================================================================
def block_personen(chunk, personen, figuren):
    treffer = {n: p for n, p in personen.items()
               if re.search(r"\b" + re.escape(n) + r"'?s?\b", chunk)}
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
        zeilen.append(z)
    return "=== PERSONEN ===\n" + "\n".join(zeilen) + "\n\n"


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


def testauszuege(paras, n_erzaehlung, n_dialog):
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
    return teil1, teil2, bester_wert


def zitat_absaetze(zitate):
    """Die Absaetze, die ausgeklammert werden — Zitat UND Attribution (F3)."""
    raus = {}
    for z in zitate:
        raus[z["index"]] = z
        if "index_attribution" in z:
            raus[z["index_attribution"]] = None      # nur entfernen
    return raus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--variante", default="A", choices=["A", "B"],
                    help="B nutzt chunk_words_variante, schreibt nach testB/")
    ap.add_argument("--no-revision", action="store_true")
    ap.add_argument("--chunk", type=int, default=None,
                    help="nur diesen Chunk neu rechnen (1-basiert)")
    args = ap.parse_args()

    G.kopf("UEBERSETZUNG" + (f" (Test {args.variante})" if args.test else ""))
    cfg = G.lade_config()
    revision = cfg["revision_pass"] and not args.no_revision
    chunk_words = (cfg["chunk_words_variante"] if args.variante == "B"
                   else cfg["chunk_words"])

    if not os.path.exists(G.F["quelle"]):
        sys.exit(f"FEHLER: {G.F['quelle']} nicht gefunden.")
    paras_alle = G.absaetze(open(G.F["quelle"], encoding="utf-8").read())
    zitate = G.lade_json(G.F["zitate"], still=True).get("epigraphen", [])

    if args.test:
        praefix = ("test" if args.variante == "A" else "testB") + "/"
        os.makedirs(praefix, exist_ok=True)
        t1, t2, dichte = testauszuege(paras_alle,
                                      cfg["test_words_erzaehlung"],
                                      cfg["test_words_dialog"])
        print(f"Teil 1 (Erzählung): {sum(len(p.split()) for p in t1)} Wörter, "
              f"{len(t1)} Absätze")
        print(f"Teil 2 (Dialog):    {sum(len(p.split()) for p in t2)} Wörter, "
              f"{len(t2)} Absätze, Redeanteil {dichte:.0%}")
        print(f"Chunkgröße:         {chunk_words} Wörter\n")
        gruppen = [t1, t2]
        marken = {}
    else:
        praefix = ""
        marken = zitat_absaetze(zitate)
        gruppen = [[p for i, p in enumerate(paras_alle) if i not in marken]]

    # Chunks je Gruppe; Fugen merken (Kontext dort zuruecksetzen)
    chunks, fugen = [], set()
    for gruppe in gruppen:
        teil = G.chunks_bauen(gruppe, chunk_words)
        if chunks:
            fugen.add(len(chunks))
        chunks.extend(teil)

    n = len(chunks)
    glossar = G.lade_json(G.F["glossar"])
    personen = G.lade_json(G.F["personen"])
    figuren = G.lade_json(G.F["figuren"])
    anrede = G.lade_json(G.F["anrede"])
    leitmotive = G.lade_json(G.F["leitmotive"])
    p_ueb, p_rev = prompts(cfg)
    fingerprint = G.config_hash(cfg)

    # Nicht cfg['modell'] anzeigen — das ist der Ollama-Rueckfallschluessel
    # und stimmt im API-Betrieb nie. Was zaehlt, ist das Modell der Rolle.
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
        vorige = G.teil_lesen("uebersetzung", zu_tun[0] - 1, praefix)
        if vorige and zu_tun[0] not in fugen:
            letzte = G.schlusswoerter(vorige, cfg["context_words"])

    start = time.time()
    messwerte = []

    for zaehler, i in enumerate(zu_tun, 1):
        quelle, geschuetzt = chunks[i]
        if geschuetzt:
            G.teil_schreiben("uebersetzung", i, quelle, praefix)
            G.teil_schreiben("entwurf", i, quelle, praefix)
            print(f"[{i+1}/{n}] geschützter Absatz, unverändert übernommen")
            continue

        if i in fugen:
            letzte, vorher = "", ""
            print("--- Auszugswechsel: Kontext zurückgesetzt ---")
        else:
            vorher = (G.schlusswoerter(chunks[i-1][0], cfg["context_words"])
                      if i > 0 and not chunks[i-1][1] else "")

        print(f"[{i+1}/{n}] {len(quelle.split())} Wörter", flush=True)
        t0 = time.time()

        for versuch in range(1, cfg["max_retries"] + 1):
            try:
                kopf = (block_fallen(quelle, cfg)
                        + block_personen(quelle, personen, figuren)
                        + block_glossar(quelle, glossar)
                        + block_anrede(quelle, personen, anrede)
                        + block_leitmotive(quelle, leitmotive))
                user = kopf
                if vorher:
                    user += ("=== ENDE DES VORIGEN ABSCHNITTS, ORIGINAL "
                             "(nur Kontext) ===\n" + vorher + "\n\n")
                if letzte:
                    user += ("=== ENDE DES VORIGEN ABSCHNITTS, DEINE "
                             "ÜBERSETZUNG (nur Kontext, nicht wiederholen) "
                             "===\n" + letzte + "\n\n")
                user += "=== ZU ÜBERSETZENDER TEXT ===\n" + quelle

                entwurf = G.chat(cfg, p_ueb, user,
                                 cfg["temperature_uebersetzung"],
                                 rolle="uebersetzung")
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

                endfassung = entwurf
                if revision:
                    t1 = time.time()
                    body = (kopf
                            + "=== NIEDERLÄNDISCHER AUSGANGSTEXT ===\n"
                            + quelle + "\n\n"
                            + "=== DEUTSCHER ENTWURF ===\n" + entwurf)
                    rev = G.chat(cfg, p_rev, body,
                                 cfg["temperature_revision"],
                                 rolle="revision")
                    r2 = G.verhaeltnis(quelle, rev)
                    if rev and cfg["ratio_min"] <= r2 <= cfg["ratio_max"]:
                        endfassung = rev
                        print(f"    Pass 2  {time.time()-t1:5.0f}s  "
                              f"({r2:.2f}x)", flush=True)
                    else:
                        warnen(f"Chunk {i+1}: Revision verworfen ({r2:.2f}x)")

                messwerte.append(G.verhaeltnis(quelle, endfassung))
                na, nb = len(G.absaetze(quelle)), len(G.absaetze(endfassung))
                if na != nb:
                    warnen(f"Chunk {i+1}: Absätze {na} -> {nb}")

                G.teil_schreiben("entwurf", i, entwurf, praefix)
                G.teil_schreiben("uebersetzung", i, endfassung, praefix)
                letzte = G.schlusswoerter(endfassung, cfg["context_words"])
                json.dump({"total": n, "fingerprint": fingerprint,
                           "chunk_words": chunk_words, "rev": revision},
                          open(state_p, "w"))
                print("    " + G.fortschritt(zaehler, len(zu_tun), start,
                                             "fertig") + "\n", flush=True)
                break

            except Exception as e:
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
