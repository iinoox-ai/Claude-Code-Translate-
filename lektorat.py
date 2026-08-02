#!/usr/bin/env python3
"""
Lektorat des deutschen Manuskripts.

Vier Stufen ueber 'lektorat_passes' in projekt.json:
  det -> stil -> korrektorat -> det

Neu gegenueber der ersten Fassung:
  - ß-Ersetzung mit Homographenschutz: 'Masse', 'Busse', 'ass', 'Weiss'
    werden NICHT mehr zu 'Maße', 'Buße', 'aß', 'Weiß' (Fehler der ersten
    Fassung, der korrektes Deutsch verfaelschte)
  - Eingesetzte Zitate werden vom Lektorat ausgenommen (F6b)
  - Chunk-Ausgaben liegen einzeln in teile/lektorat
  - Retranslate einzelner Chunks

Aufrufe:
    python3 lektorat.py --test
    python3 lektorat.py
    python3 lektorat.py --nur det
    python3 lektorat.py --chunk 12
"""

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time

import gemeinsam as G

DIFF    = "lektorat_diff.txt"
WARN    = "lektorat_warnungen.log"
BERICHT = "bericht.html"
NORMBER = "normalisierung_report.txt"


# ==================================================================
# ß / ss
# ==================================================================
# Woerter, die zwingend ß tragen.
ESZETT_WOERTER = [
    "Straße", "Straßen", "Straßenbahn", "groß", "große", "großen", "großer",
    "großes", "größer", "größte", "größten", "Größe", "großzügig",
    "Großmutter", "Großvater", "Großeltern",
    "heiß", "heiße", "heißen", "heißer", "heißt",
    "weiß", "weiße", "weißen", "weißer", "weißes", "weißt",
    "Fuß", "Füße", "Füßen", "Fußball", "Fußboden",
    "Spaß", "Späße", "süß", "süße", "süßen", "süßer",
    "außen", "draußen", "außer", "außerdem", "außerhalb",
    "äußern", "äußert", "äußerte", "äußerst",
    "schließen", "schließt", "schließlich", "beschließen", "entschließen",
    "verschließen", "aufschließen", "abschließen", "Schließfach",
    "gießen", "gießt", "fließen", "fließt", "genießen", "genießt",
    "beißen", "beißt", "reißen", "reißt", "zerreißen", "abreißen",
    "hinreißend", "heißen", "bloß", "stoßen", "stößt",
    "Gruß", "Grüße", "grüßen", "grüßt", "grüßte",
    "Schoß", "Fleiß", "Kloß", "Stoß",
    "gemäß", "einigermaßen", "maßlos",
    "verließ", "hieß", "ließ", "ließen", "saß", "saßen", "vergaß",
]

# Diese ss-Formen sind eigenstaendige, korrekte deutsche Woerter und duerfen
# NICHT in ß-Formen umgeschrieben werden. Ohne diesen Schutz wurde aus
# 'die Masse der Menschen' -> 'die Maße' und aus 'die Busse' -> 'die Buße'.
#
# Der Schutz ist schreibungsabhaengig: 'gross' und 'weiss' in Kleinschreibung
# sind fast immer die Falschschreibung von 'groß'/'weiß' und werden korrigiert;
# grossgeschrieben sind es Nachnamen und bleiben stehen.
HOMOGRAPHEN = {
    # immer schuetzen, in jeder Schreibung
    "masse", "massen", "musse", "busse", "bussen",
    "fluss", "flusses", "kuss", "kusses", "schloss", "schlosses",
    "hass", "pass", "passe", "klasse", "presse", "messe", "russ",
    # nur grossgeschrieben schuetzen (Nachnamen, Substantive)
    "Gross", "Weiss", "Ass", "Asse", "Grosse", "Weisse",
}


def _geschuetzt(form):
    """Kleinschreibung wird ueber die kleingeschriebene Menge geprueft,
    Grossschreibung zusaetzlich exakt."""
    return form in HOMOGRAPHEN or form.lower() in {
        h for h in HOMOGRAPHEN if h.islower()}


ESZETT_MAP = {}
for _w in ESZETT_WOERTER:
    _ss = _w.replace("ß", "ss")
    if _ss == _w or _geschuetzt(_ss):
        continue
    ESZETT_MAP[_ss] = _w

NL_RESTE = re.compile(
    r"\b(het|een|niet|maar|zijn|haar|hij|zij|jij|jullie|ook|nog|wel|toch|"
    r"heel|erg|even|misschien|natuurlijk|eigenlijk|gewoon|hoor|zeg)\b")


def normalisieren(text, cfg):
    z = {}

    def zaehl(k, n):
        if n:
            z[k] = z.get(k, 0) + n

    n = text.count("...")
    text = text.replace("...", "\u2026")
    zaehl("Auslassungspunkte (... -> …)", n)

    EN = "\u2013"
    text, n = re.subn(r"\s*\u2014\s*", f" {EN} ", text)
    zaehl("Geviert- zu Halbgeviertstrich", n)
    text, n = re.subn(r"(\w)\s*--\s*(\w)", "\\1 " + EN + " \\2", text)
    zaehl("Doppelbindestrich zu Halbgeviertstrich", n)
    text, n = re.subn(r"(\w)\u2013(\w)", "\\1 " + EN + " \\2", text)
    zaehl("Spatien um den Gedankenstrich", n)

    if cfg["quotes"] == "guillemets":
        auf, zu = "\u00bb", "\u00ab"
        n = text.count("\u201e") + text.count("\u201c") + text.count("\u201d")
        text = (text.replace("\u201e", auf).replace("\u201c", zu)
                    .replace("\u201d", zu))
    else:
        auf, zu = "\u201e", "\u201c"
        n = text.count("\u00bb") + text.count("\u00ab")
        text = text.replace("\u00bb", auf).replace("\u00ab", zu)
    zaehl("Anführungszeichen vereinheitlicht", n // 2 if n else 0)

    if text.count('"') >= 2 and text.count('"') % 2 == 0:
        teile = text.split('"')
        neu = teile[0]
        for i in range(1, len(teile)):
            neu += (auf if i % 2 == 1 else zu) + teile[i]
        zaehl("gerade Anführungszeichen", text.count('"') // 2)
        text = neu

    text, n = re.subn(r"(?<=\w)'(?=\w)", "\u2019", text)
    zaehl("Apostrophe", n)

    if cfg["eszett"]:
        for falsch, richtig in ESZETT_MAP.items():
            text, n = re.subn(rf"\b{re.escape(falsch)}\b", richtig, text)
            zaehl("ss -> ß korrigiert", n)
            kap = falsch[0].upper() + falsch[1:]
            if kap != falsch and not _geschuetzt(kap):
                ziel = richtig[0].upper() + richtig[1:]
                text, n = re.subn(rf"\b{re.escape(kap)}\b", ziel, text)
                zaehl("ss -> ß korrigiert", n)
    else:
        text, n = re.subn("ß", "ss", text)
        zaehl("ß -> ss (schweizerisch)", n)

    for abk, ziel in (("z.B.", "z. B."), ("d.h.", "d. h."),
                      ("u.a.", "u. a."), ("v.Chr.", "v. Chr."),
                      ("n.Chr.", "n. Chr.")):
        text, n = re.subn(re.escape(abk) + r"(?! )", ziel, text)
        zaehl("Abkürzungen mit Leerzeichen", n)

    text, n = re.subn(r"[ \t]{2,}", " ", text)
    zaehl("mehrfache Leerzeichen", n)
    # \u2026 gehoert NICHT in diese Klasse. Auslassungspunkte, die fuer ein
    # ausgelassenes Wort stehen, tragen im Deutschen ein Spatium davor
    # ("Meine Eltern sind \u2026 nicht"); nur beim abgebrochenen Wort ("Verd\u2026")
    # entfaellt es. Was davon gilt, entscheidet der Satz, nicht ein Muster \u2014
    # also bleibt hier stehen, was das Korrektorat gesetzt hat. Vorher hat
    # diese Zeile im Testlektorat sechs Spatien getilgt und damit eine
    # Anweisung ueberstimmt, die genau das verbot.
    text, n = re.subn(r"\s+([,.;:!?])", r"\1", text)
    zaehl("Leerzeichen vor Satzzeichen", n)
    text, n = re.subn(r"([\u00bb\u201e\u203a])\s+", r"\1", text)
    zaehl("Leerzeichen nach öffnendem Zeichen", n)
    text, n = re.subn(r"(?m)[ \t]+$", "", text)
    zaehl("Leerzeichen am Zeilenende", n)

    reste = NL_RESTE.findall(text)
    if reste:
        z[f"HINWEIS: {len(reste)} mögliche niederländische Reste"] = len(reste)
    return text, z


# ==================================================================
STIMMSCHUTZ = """STIMMSCHUTZ — ZUERST LESEN

Dies ist literarische Prosa. Ich-Erzählung und Dialog sind Figurenrede, kein \
Fehler. Korrigiere sie NICHT in Richtung Schulgrammatik:

- Umgangssprachliche Formen bleiben: »hab« statt »habe«, »is« statt »ist«, \
»nix«, »kriegen« statt »bekommen«, Dativ nach »wegen«, »weil« mit \
Verbzweitstellung im Dialog.
- Ellipsen und Satzfragmente bleiben.
- Der Wechsel zwischen Präteritum und Perfekt ist eine bewusste Entscheidung \
dieses Projekts. Glätte ihn nicht zu durchgehendem Präteritum, solange jede \
Form für sich korrekt ist.
- Bewusste Wiederholung bleibt. Kehrt eine Geste, Wendung oder ein Satzmuster \
wieder, ist es das Mittel der Autorin, bis dir etwas anderes gesagt wird.
- Das Register anzuheben ist ein Mangel, keine Verbesserung.

Korrigiere nur, was tatsächlich falsch ist, nicht was bloß umgangssprachlich \
ist."""


def prompts(cfg):
    zb = G.zielbaustein(cfg)
    dim, tempus = G.projektbausteine(cfg)
    zusatz_stil = G.lade_anweisungen("Stillektorat")
    zusatz_korr = G.lade_anweisungen("Korrektorat")

    stil = f"""Du bist erfahrene Stillektorin in einem Literaturverlag. Das \
Manuskript ist eine Übersetzung aus dem Niederländischen. Deine Aufgabe ist, \
dass es aufhört, übersetzt zu klingen.

{STIMMSCHUTZ}

NIEDERLANDISMEN SUCHEN

Falsche Freunde, die wörtlich stehen geblieben sind: »bellen« für anrufen, \
»deftig« für vornehm, »Meer« für See, »schlimm« für klug, »artig« für nett, \
»Winkel« für Laden, »Mist« für Nebel, »doof« für taub, »eng« für gruselig, \
»schön« für sauber, »laufen« für gehen, »klar« für fertig, »fies« für \
schmutzig, »stolz« für frech, »brutal« für frech, »rar« für seltsam, »nett« \
für gepflegt, »gekocht« für gekauft, »Tafel« für Tisch, »Bank« für Sofa, \
»Enkel« für nur, »stracks« für gleich, »Quartier« für Viertelstunde.

Konditional statt Evidentialität: Wo im Deutschen »wäre« oder »würde« steht, \
das Original aber ein Gerücht oder eine Behauptung Dritter meinte, gehört \
»soll«, »angeblich« oder »wie es heißt« hin.

Verlaufsformen. »am Lesen sein«, »beim Essen sein« sind rheinisch-umgangs\
sprachlich und in Erzählprosa fehl am Platz. Auflösen.

Körperhaltungsverben. Wo »er saß und las« oder »sie stand zu warten« steht, \
ist eine niederländische Konstruktion durchgerutscht.

»Es gibt«-Schwemme aus niederländischem »er«.

Modalpartikeln nach Formähnlichkeit: »doch« für toch, »wohl« für wel, »eben« \
für even. Prüfe die Wirkung und streiche, was nichts trägt.

Satzbau, der niederländisch bleibt: andere Gliederung, andere \
Klammerstruktur, andere Stellung der Angaben.

DIMINUTIVE

{dim}
Achte auf die Dichte: Häufen sich »-chen« und »-lein«, ist mechanisch \
übertragen worden.

TEMPUS

{tempus}

RHYTHMUS UND DIKTION
- Satzlängen variieren. Übersetzte Prosa fällt leicht in Monotonie.
- Das konkrete Wort dem abstrakten vorziehen, wo das Register es erlaubt.
- Adverbien streichen, die schwache Verben stützen.
- Auf Passiv achten, das aus dem Niederländischen mitgekommen ist.

ZIELFORM
{zb}

STRIKTE GRENZEN
- Nicht zusammenfassen, nicht ausweiten, nichts hinzufügen oder streichen.
- Eigennamen und festgelegte Terminologie nicht ändern.
- Die Absatzeinteilung exakt bewahren.
- Ist eine Stelle schon gut, lass sie in Ruhe. Die beste Korrektur ist oft \
keine.

Gib AUSSCHLIESSLICH den überarbeiteten Text aus. Keine Vorrede, keine \
Anmerkungen, kein Kommentar, keine Auszeichnungen."""

    korrektorat = f"""Du bist Korrektorin in einem deutschen Literaturverlag \
und arbeitest nach der geltenden amtlichen Rechtschreibung und den Satzregeln \
des deutschen Buchdrucks.

{STIMMSCHUTZ}

NUR DIESES KORRIGIEREN

Grammatik, die in jedem Register falsch ist:
- Kasus und Rektion: Präpositionen, Verbrektion.
- Genus und Numerus, Kongruenz in Nominalgruppen.
- Zeitenfolge, wo sie einen Widerspruch erzeugt.
- Hilfsverb bei den zusammengesetzten Zeiten (haben/sein).
- Bezugsfehler bei Pronomen und Relativsätzen.
- Fehlende oder falsch gesetzte Kommas nach den Regeln zu Nebensatz, \
Infinitivgruppe und Apposition.

Rechtschreibung und Konsistenz:
{zb}
- Getrennt- und Zusammenschreibung.
- Groß- und Kleinschreibung, besonders substantivierte Verben und Adjektive.
- Eigennamen durchgehend gleich geschrieben.

Typografie, die der automatische Durchgang nicht beurteilen kann:
- Anführungszeichen um die richtige Spanne.
- Satzzeichen innerhalb oder außerhalb der Anführung nach deutscher Regel.
- Apostroph nur, wo er hingehört.

NICHT ANFASSEN
- Stil, Wortwahl, Satzrhythmus, Satzlänge.
- Alles, was bloß umgangssprachlich oder wiederholend ist.
- Grammatik in der direkten Rede.
- Den Wechsel zwischen Präteritum und Perfekt, solange beide Formen korrekt \
sind.
- Die Absatzeinteilung.

Gib AUSSCHLIESSLICH den korrigierten Text aus. Keine Vorrede, keine \
Anmerkungen, kein Kommentar."""

    if zusatz_stil:
        stil += "\n\nPROJEKTANWEISUNGEN (diese haben Vorrang)\n\n" + zusatz_stil
    if zusatz_korr:
        korrektorat += ("\n\nPROJEKTANWEISUNGEN (diese haben Vorrang)\n\n"
                        + zusatz_korr)
    return stil, korrektorat


# ==================================================================
class Verworfen(RuntimeError):
    """Ein Durchgang kam gekuerzt zurueck und wird wiederholt."""


def pass_urteil(r, cfg, versuch):
    """Was mit dem Ergebnis eines LLM-Durchgangs geschieht.

    Frueher galt: Verhaeltnis ausserhalb der Grenzen -> sofort verwerfen,
    ohne zweiten Anlauf. Ein Netzfehler bekam drei Versuche, eine
    abgeschnittene Antwort keinen — dabei ist sie genauso gut
    wiederholbar. Gemessen am Volllauf 1919: Chunk 152 lieferte im
    Stillektorat erst 0.37, beim naechsten Anlauf 1.01; Chunk 150 lief
    beim zweiten Mal vollstaendig durch. Erst der letzte Versuch
    verwirft."""
    if cfg["lektorat_ratio_min"] <= r <= cfg["lektorat_ratio_max"]:
        return "ok"
    return "verwerfen" if versuch >= cfg["max_retries"] else "wiederholen"


def diff_schreiben(fh, titel, vorher, nachher):
    a = [p.strip() for p in G.absaetze(vorher)]
    b = [p.strip() for p in G.absaetze(nachher)]
    d = list(difflib.unified_diff(a, b, lineterm="", n=0,
                                  fromfile="vorher", tofile="nachher"))
    if len(d) > 2:
        fh.write(f"\n{'='*66}\nChunk {titel}\n{'='*66}\n")
        fh.write("\n".join(d) + "\n")
        fh.flush()


def geschuetzte_absaetze():
    """F6b: eingesetzte Zitate und ihre Attribution werden nicht lektoriert."""
    raus = set()
    for z in G.lade_json(G.F["zitate"], still=True).get("epigraphen", []):
        o = z.get("original_deutsch")
        if o and str(o).strip():
            raus.add(str(o).strip())
        if z.get("attribution"):
            raus.add(str(z["attribution"]).strip())
        raus.add("[[ZITAT NICHT EINGESETZT")
    return raus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--nur", default=None, choices=["det", "stil", "korrektorat"])
    ap.add_argument("--chunk", type=int, default=None)
    args = ap.parse_args()

    G.kopf("LEKTORAT" + (" (Test)" if args.test else ""))
    cfg = G.lade_config()
    praefix = "test/" if args.test else ""
    quelle = praefix + G.F["uebersetzung"]
    ziel_datei = praefix + G.F["lektoriert"]

    if not os.path.exists(quelle):
        sys.exit(f"FEHLER: {quelle} nicht gefunden.")

    folge = [args.nur] if args.nur else list(cfg["lektorat_passes"])
    p_stil, p_korr = prompts(cfg)
    PASS = {"stil": (p_stil, cfg["temperature_stil"], "Stillektorat"),
            "korrektorat": (p_korr, cfg["temperature_korrektorat"],
                            "Korrektorat")}

    text = open(quelle, encoding="utf-8").read()
    print(f"Quelle: {quelle}\nFolge:  {' -> '.join(folge)}")
    for stufe in [s for s in folge if s in PASS]:
        m = G.modell_fuer(cfg, stufe)
        print(f"  {PASS[stufe][2]:<14} {m} ({G.backend_name(m)}, "
              f"Effort {G.effort_fuer(cfg, stufe)})")
    print()

    while folge and folge[0] == "det":
        folge.pop(0)
        text, z = normalisieren(text, cfg)
        zeilen = [f"Deterministische Normalisierung — {sum(z.values())} "
                  f"Änderungen", "=" * 56]
        zeilen += [f"  {v:6d}  {k}"
                   for k, v in sorted(z.items(), key=lambda x: -x[1])]
        open(praefix + NORMBER, "w", encoding="utf-8").write(
            "\n".join(zeilen) + "\n")
        print("\n".join(zeilen) + "\n")
        open(praefix + G.F["normalisiert"], "w", encoding="utf-8").write(text)

    llm = [s for s in folge if s in PASS]
    nach_det = bool(folge) and folge[-1] == "det"

    if not llm:
        if nach_det:
            text, _ = normalisieren(text, cfg)
        open(ziel_datei, "w", encoding="utf-8").write(text)
        print(f"Nur deterministisch. Ergebnis: {ziel_datei}")
        return

    schutz = geschuetzte_absaetze()
    paras = G.absaetze(text)
    chunks, buf, n_w = [], [], 0
    for p in paras:
        if any(p.startswith(s) or p == s for s in schutz):
            if buf:
                chunks.append(("\n\n".join(buf), False)); buf, n_w = [], 0
            chunks.append((p, True))
            continue
        w = len(p.split())
        if buf and n_w + w > cfg["chunk_words"] - 100:
            chunks.append(("\n\n".join(buf), False)); buf, n_w = [], 0
        buf.append(p); n_w += w
    if buf:
        chunks.append(("\n\n".join(buf), False))

    n = len(chunks)
    fingerprint = G.config_hash(cfg)
    print(f"{sum(len(c.split()) for c, _ in chunks)} Wörter in {n} Chunks")
    print(f"LLM-Durchgänge: {' -> '.join(PASS[s][2] for s in llm)}")
    geschuetzt_n = sum(1 for _, g in chunks if g)
    if geschuetzt_n:
        print(f"Geschützt (Zitate): {geschuetzt_n} Absätze")
    print()

    if args.chunk is not None:
        i = args.chunk - 1
        if not (0 <= i < n):
            sys.exit(f"FEHLER: Chunk {args.chunk} liegt nicht in 1..{n}")
        p = G.teil_pfad("lektorat", i, praefix)
        if os.path.exists(p):
            os.remove(p)
        print(f"Chunk {args.chunk} wird neu bearbeitet.\n")
        zu_tun = [i]
    else:
        offen = G.teile_vorhanden("lektorat", n, praefix)
        if offen:
            print(f"{offen} Chunks liegen vor, Fortsetzung ab {offen+1}.\n")
        zu_tun = list(range(offen, n))

    letzte = ""
    if zu_tun and zu_tun[0] > 0:
        v = G.teil_lesen("lektorat", zu_tun[0] - 1, praefix)
        if v:
            letzte = G.schlusswoerter(v, cfg["context_words"])

    def warnen(msg):
        print(f"    {msg}")
        with open(praefix + WARN, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    start = time.time()
    with open(praefix + DIFF, "a" if zu_tun and zu_tun[0] else "w",
              encoding="utf-8") as fd:

        for zaehler, i in enumerate(zu_tun, 1):
            aktuell, geschuetzt = chunks[i]
            if geschuetzt:
                G.teil_schreiben("lektorat", i, aktuell, praefix)
                print(f"[{i+1}/{n}] geschützter Absatz, unverändert")
                continue

            print(f"[{i+1}/{n}] {len(aktuell.split())} Wörter", flush=True)
            t0 = time.time()

            for versuch in range(1, cfg["max_retries"] + 1):
                # Jeder Versuch beginnt beim unbearbeiteten Chunk, und der
                # Diff wird erst nach dem ganzen Chunk geschrieben. Sonst
                # liefe nach einem Fehler in der zweiten Stufe die erste
                # ein zweites Mal auf ihrem eigenen Ergebnis, und der
                # Bericht zeigte die verworfenen Anlaeufe mit an.
                aktuell = chunks[i][0]
                gepuffert = []
                try:
                    for stufe in llm:
                        system, temp, label = PASS[stufe]
                        t1 = time.time()
                        body = ""
                        if letzte:
                            body += ("=== ENDE DES VORIGEN, BEREITS "
                                     "BEARBEITETEN ABSCHNITTS (nur Kontext, "
                                     "nicht wiedergeben) ===\n"
                                     + letzte + "\n\n")
                        body += "=== ZU BEARBEITENDER TEXT ===\n" + aktuell

                        neu = G.chat(cfg, system, body, temp, rolle=stufe)
                        if not neu:
                            raise RuntimeError(f"leere Antwort ({stufe})")

                        r = G.verhaeltnis(aktuell, neu)
                        urteil = pass_urteil(r, cfg, versuch)
                        if urteil == "wiederholen":
                            print(f"    {label:14s} "
                                  f"{time.time()-t1:5.0f}s  ({r:.2f}x)",
                                  flush=True)
                            raise Verworfen(f"{label} bei {r:.2f}x")
                        if urteil == "verwerfen":
                            warnen(f"Chunk {i+1} [{stufe}]: Verhältnis "
                                   f"{r:.2f} -> Durchgang verworfen "
                                   f"(nach {versuch} Versuchen)")
                        else:
                            na, nb = (len(G.absaetze(aktuell)),
                                      len(G.absaetze(neu)))
                            if na != nb:
                                warnen(f"Chunk {i+1} [{stufe}]: Absätze "
                                       f"{na} -> {nb}")
                            gepuffert.append((f"{i+1} - {label}", aktuell, neu))
                            aktuell = neu
                        print(f"    {label:14s} {time.time()-t1:5.0f}s  "
                              f"({r:.2f}x)", flush=True)

                    for titel, vorher, nachher in gepuffert:
                        diff_schreiben(fd, titel, vorher, nachher)
                    G.teil_schreiben("lektorat", i, aktuell, praefix)
                    letzte = G.schlusswoerter(aktuell, cfg["context_words"])
                    json.dump({"total": n, "fingerprint": fingerprint,
                               "folge": llm},
                              open(praefix + "lektorat_state.json", "w"))
                    print("    " + G.fortschritt(zaehler, len(zu_tun), start,
                                                 "fertig") + "\n", flush=True)
                    break

                except Verworfen as e:
                    print(f"    Versuch {versuch}/{cfg['max_retries']}: "
                          f"{e} -> Chunk neu")
                    time.sleep(2)

                except Exception as e:
                    print(f"    Versuch {versuch}/{cfg['max_retries']}: {e}")
                    if versuch == cfg["max_retries"]:
                        sys.exit(f"\nAbbruch bei Chunk {i+1}. "
                                 f"Neustart setzt hier fort.")
                    time.sleep(5 * versuch)

    ganz = G.teile_zusammensetzen("lektorat", n, praefix)
    if ganz is None:
        print("WARNUNG: noch unvollständig, nicht zusammengesetzt.")
        return

    if nach_det:
        ganz, z = normalisieren(ganz, cfg)
        print(f"\nNachnormalisierung: {sum(z.values())} Änderungen")
        for k, v in sorted(z.items(), key=lambda x: -x[1])[:8]:
            print(f"  {v:6d}  {k}")

    open(ziel_datei, "w", encoding="utf-8").write(ganz + "\n")
    print(f"\nFertig nach {(time.time()-start)/60:.0f} min.")
    print(f"  Ergebnis:   {ziel_datei}")
    print(f"  Änderungen: {praefix + DIFF}")
    bericht = bericht_bauen(praefix)
    if bericht:
        print(f"  Bericht:    {bericht}")


def bericht_bauen(praefix):
    """Erzeugt den HTML-Bericht gleich mit.

    Der Schritt, der den Diff schreibt, schreibt auch den Bericht — sonst
    steht am Ende ein Befehl da, den jemand von Hand abtippen soll. Der
    Aufruf geht ueber diffview.py im Code-Verzeichnis, damit dessen Logik
    die einzige bleibt."""
    diff = praefix + DIFF
    if not os.path.exists(diff):
        return None
    ziel = praefix + BERICHT
    code = os.path.dirname(os.path.abspath(__file__))
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(code, "diffview.py"), diff,
             "--html", ziel],
            capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"  WARNUNG: Bericht nicht erzeugt — "
                  f"{(r.stderr or '').strip()[:200]}")
            return None
    except Exception as e:
        print(f"  WARNUNG: Bericht nicht erzeugt — {e}")
        return None
    return ziel


if __name__ == "__main__":
    main()
