#!/usr/bin/env python3
"""
Konkordanzanalyse NL -> DE.

Niederlaendisch schreibt Substantive klein, die Artikelprobe entfaellt also.
Dafuer: Tussenvoegsels ('van den Berg'), IJ-Ligatur, und die Mehrdeutigkeit
von 'zijn' (Possessiv und Verb) sowie 'ze' (Singular und Plural).

    python3 konkordanz.py
    python3 konkordanz.py --lokal
"""

import argparse, json, os, re, sys, time
from collections import Counter, defaultdict
import gemeinsam as G
from uebersetzung import VALSE_VRIENDEN

EXPORT   = "analysepaket.md"
BRIEFING = "briefing_glossar.md"
MIN_COUNT, BELEGE = 3, 12

TUSSEN = ["van der", "van den", "van de", "van 't", "van het", "in der",
          "in 't", "in het", "op de", "op den", "op 't", "aan de", "aan den",
          "uit de", "uit den", "bij de", "voor de",
          "van", "de", "den", "der", "het", "ten", "ter", "te", "'t"]
TUSSEN.sort(key=len, reverse=True)

TITEL_M = {"meneer","mijnheer","dhr","oom","opa","dominee","ds","pastoor",
           "meester","broeder","vader","neef","kapitein","opoe"}
TITEL_F = {"mevrouw","mevr","mw","juffrouw","juf","mejuffrouw","mej","tante",
           "oma","zuster","moeder","nicht"}
TITEL = TITEL_M | TITEL_F | {"dokter","dr","professor","prof","agent",
                             "rechercheur","sergeant"}

MASK = {"hij","hem","z'n","zijne"}
MASK_UNSICHER = {"zijn"}
FEM = {"zij","haar","d'r","hare"}
FEM_UNSICHER = {"ze"}
VOR_VERB = {"te","zou","zouden","kan","kunnen","moet","moeten","wil","willen",
            "zal","zullen","mag","mogen","om","niet","er","of","dan"}

STOPP = set("""dag nacht jaar jaren tijd uur week maand ochtend avond huis
kamer deur raam straat weg stad land wereld leven dood hand handen oog ogen
hoofd gezicht hart stem woord woorden vraag antwoord blik werk water licht
hemel zon maan lucht vuur aarde vader moeder zoon dochter broer zus vriend
vriendin god hoofdstuk deel boek bladzijde eind begin reden ding dingen
manier plek plaats ruimte mens mensen kind kinderen man vrouw jongen meisje
moment""".split())


def namen_finden(text, min_count=MIN_COUNT):
    tussen_pat = "|".join(re.escape(t) for t in TUSSEN)
    voll = re.compile(
        rf"\b([A-ZÄÖÜÉÈ][a-zäöüéè']+|IJ[a-z]+)\s+((?:{tussen_pat})\s+)"
        rf"([A-ZÄÖÜÉÈ][a-zäöüéè']+|IJ[a-z]+)\b")
    nachnamen = {}
    for m in voll.finditer(text):
        nachnamen.setdefault(m.group(3), m.group(2).strip())

    tokens = re.findall(r"IJ[a-zäöüéè']+|[A-Za-zÄÖÜäöüéèËë']+|[.!?]", text)
    low = [t.lower() for t in tokens]
    total, pos, tm, tf = Counter(), defaultdict(list), Counter(), Counter()
    for i, tok in enumerate(tokens):
        gross = (re.fullmatch(r"[A-ZÄÖÜÉÈ][a-zäöüéè']{1,}", tok)
                 or re.fullmatch(r"IJ[a-zäöüéè']+", tok))
        if not gross or tok.lower() in STOPP or tok.lower() in TITEL:
            continue
        if i > 0 and tokens[i-1] in ".!?":
            continue
        total[tok] += 1
        pos[tok].append(i)
        for back in (1, 2, 3):
            if i - back < 0:
                break
            w = low[i-back].rstrip(".")
            if w in TITEL_M:
                tm[tok] += 1; break
            if w in TITEL_F:
                tf[tok] += 1; break
            if w not in TUSSEN:
                break

    kand = {t: n for t, n in total.items() if n >= min_count}
    zusammen = {}
    for tok in sorted(kand, key=lambda x: -kand[x]):
        basis = tok
        for e in ("s", "'s"):
            if tok.endswith(e) and tok[:-len(e)] in kand:
                basis = tok[:-len(e)]; break
        d = zusammen.setdefault(basis, {"n": 0, "formen": [], "pos": [],
                                        "tm": 0, "tf": 0, "partikel": None})
        d["n"] += kand[tok]; d["formen"].append(tok); d["pos"].extend(pos[tok])
        d["tm"] += tm[tok]; d["tf"] += tf[tok]
        if basis in nachnamen:
            d["partikel"] = nachnamen[basis]

    for basis, d in zusammen.items():
        m = f = 0
        for i in d["pos"]:
            for j in range(max(0, i-40), min(len(low), i+40)):
                w = low[j]
                if w in MASK:
                    m += 2
                elif w in FEM:
                    f += 2
                elif w in MASK_UNSICHER:
                    if j == 0 or low[j-1] not in VOR_VERB:
                        m += 1
                elif w in FEM_UNSICHER:
                    f += 1
        d["mask"], d["fem"] = m + d["tm"]*20, f + d["tf"]*20
    return zusammen


def belege(text, name, partikel=None, k=BELEGE):
    saetze = re.split(r'(?<=[.!?"”»])\s+', text)
    such = (rf"\b{re.escape(partikel)}\s+{re.escape(name)}\b|\b{re.escape(name)}(\'?s)?\b"
            if partikel else rf"\b{re.escape(name)}(\'?s)?\b")
    pat = re.compile(such)
    tr = [re.sub(r"\s+", " ", s).strip() for s in saetze if pat.search(s)]
    mark = re.compile(r"\b(hij|hem|zijn|z'n|zij|ze|haar|d'r|meneer|mevrouw|"
                      r"juffrouw|oom|tante|opa|oma|vader|moeder|broer|zus)\b")
    tr.sort(key=lambda s: -len(mark.findall(s)))
    return [s[:340] for s in tr[:k]]


def anredebelege(text, k=40):
    saetze = re.split(r'(?<=[.!?"”»])\s+', text)
    u = re.compile(r"\b(u|uw|Uw)\b")
    return [re.sub(r"\s+", " ", s).strip()[:300] for s in saetze
            if u.search(s) and re.search(r'["„“«»]', s)][:k]


def wendungen(text, k=25):
    w = re.findall(r"[a-zäöüéèï']+", text.lower())
    out = []
    for n in (6, 5, 4):
        c = Counter(tuple(w[i:i+n]) for i in range(len(w)-n))
        for g, anz in c.most_common(80):
            if anz < 3:
                continue
            s = " ".join(g)
            if any(s in v for _, v in out):
                continue
            out.append((anz, s))
            if len(out) >= k:
                return out
    return out


FELDER = {
    "Wasser, Meer": r"\b(water|zee|meer|rivier|gracht|regen|nat|golf)",
    "Land, Polder": r"\b(land|polder|dijk|weiland|akker|boerderij|molen)",
    "Licht, Dunkel": r"\b(licht|donker|schemer|schaduw|glans|zon)",
    "Kälte, Wind": r"\b(koud|kou|wind|waai|storm|vries|ijs)",
    "Tod, Krankheit": r"\b(dood|dode|sterv|stierf|ziek|begraf|graf)",
    "Enge, Weite": r"\b(eng|nauw|wijd|ver|horizon|grens)",
    "Zeit, Erinnerung": r"\b(vroeger|herinner|verleden|toen|ooit)",
}


def schreibe_export(cfg, text, kand, args):
    paras = G.absaetze(text)
    laengen = sorted(len(p.split()) for p in paras)
    dialog = sum(1 for p in paras if p.lstrip()[:1] in "„“«»'\"‘—–")
    low = text.lower()
    L = []; A = L.append
    A("# Analysepaket — Glossarerstellung Niederländisch → Deutsch\n")
    A("Erzeugt von `konkordanz.py`. Zusammen mit `briefing_glossar.md` "
      "hochladen.\n")
    A("## Eckdaten\n")
    A(f"- Umfang: **{len(text.split())} Wörter**, {len(paras)} Absätze")
    A(f"- Absatzlänge: Median {laengen[len(laengen)//2]}, "
      f"Mittel {sum(laengen)/len(laengen):.0f}, Maximum {laengen[-1]}")
    A(f"- Absätze mit Redebeginn: {dialog} ({dialog/len(paras):.0%})")
    A(f"- Zielform: {cfg['varietaet']}, "
      f"{'»…«' if cfg['quotes']=='guillemets' else '„…“'}, "
      f"{'mit ß' if cfg['eszett'] else 'ohne ß'}")
    A(f"- Diminutivpolitik: **{cfg['diminutive']}**")
    A(f"- Erzähltempus: **{cfg['tempus']}**")
    A(f"- Anrede: {cfg['anrede_vorgabe']}")
    A(f"- Volltext beigefügt: {'ja' if cfg['export_glossar'] else 'nein'}\n")
    dim = len(re.findall(r"\b\w{3,}(?:tje|pje|kje|je)s?\b", low))
    u = len(re.findall(r"\bu\b", low))
    jij = len(re.findall(r"\b(jij|je|jou|jouw|jullie)\b", low))
    zou = len(re.findall(r"\bzou(den)?\b", low))
    A(f"- Diminutive: {dim} ({dim/max(1,len(text.split())/1000):.1f} je 1000)")
    A(f"- Anredeformen: `u` {u}×, `jij/je` {jij}×")
    A(f"- `zou`: {zou}× — jedes Vorkommen braucht die Entscheidung "
      f"evidentiell (»soll«) oder konditional (»würde«)\n")

    A("## Namenskandidaten\n")
    A("Niederländisch schreibt Substantive klein, großgeschriebene Wörter "
      "sind also Namenskandidaten. `Partikel` zeigt ein erkanntes "
      "Tussenvoegsel. `m`/`f` zählen Pronomen im Umfeld — dabei ist `zijn` "
      "auch das Verb *sein*, `ze` mehrdeutig, `haar` auch *Haar*.\n")
    A("| Kandidat | n | Formen | Partikel | Titel m/f | m | f |")
    A("|---|---:|---|---|---|---:|---:|")
    for basis, d in sorted(kand.items(), key=lambda kv: -kv[1]["n"])[:args.max_terms]:
        formen = "+".join(d["formen"]) if len(d["formen"]) > 1 else "—"
        A(f"| {basis} | {d['n']} | {formen} | {d['partikel'] or '—'} | "
          f"{d['tm']}/{d['tf']} | {d['mask']} | {d['fem']} |")
    A("")

    A("## Belegstellen\n")
    for basis, d in sorted(kand.items(), key=lambda kv: -kv[1]["n"])[:args.max_terms]:
        titel = f"{d['partikel']} {basis}" if d["partikel"] else basis
        A(f"### {titel} ({d['n']}×)\n")
        for s in belege(text, basis, d["partikel"]):
            A(f"- {s}")
        A("")

    A("## Anredebelege (Siezen mit `u`)\n")
    for s in anredebelege(text):
        A(f"- {s}")
    A("")
    A("## Wiederkehrende Wendungen\n")
    for anz, s in wendungen(text):
        A(f"- {anz}× — {s}")
    A("")
    A("## Bildfelder\n\n| Feld | Belege |\n|---|---:|")
    for name, pat in FELDER.items():
        A(f"| {name} | {len(re.findall(pat, low))} |")
    A("")
    A("## Falsche Freunde im Text\n")
    A("| NL | bedeutet | nicht | Vorkommen |\n|---|---|---|---:|")
    for nl, bed, falsch in VALSE_VRIENDEN:
        n = len(re.findall(rf"\b{nl}\w{{0,3}}\b", low))
        if n:
            A(f"| {nl} | {bed} | {falsch} | {n} |")
    A("")
    zitate = G.lade_json(G.F["zitate"], still=True).get("epigraphen", [])
    if zitate:
        A("## Ausgeklammerte Zitate\n")
        for z in zitate:
            A(f"- **{z['attribution']}** — {z['text'][:300]}")
        A("")
    if cfg["export_glossar"]:
        A("---\n## Volltext\n```")
        A(text); A("```")
    open(EXPORT, "w", encoding="utf-8").write("\n".join(L))
    return EXPORT


def lokal_glossar(cfg, text, kand, args):
    namen = [b for b, _ in sorted(kand.items(), key=lambda kv: -kv[1]["n"])][:args.max_terms]
    SYS = ("You are a literary translator preparing reference material for a "
           "Dutch novel being translated into German. You answer with valid "
           "JSON and nothing else.")
    print(f"{len(namen)} Kandidaten, {(len(namen)-1)//25+1} Bloecke.\n")
    eintraege, start = {}, time.time()
    for i in range(0, len(namen), 25):
        block = namen[i:i+25]
        teil = []
        for b in block:
            d = kand[b]
            t = f"{d['partikel']} {b}" if d["partikel"] else b
            teil.append(f"### {t} ({d['n']}x, Titel {d['tm']}m/{d['tf']}f, "
                        f"m={d['mask']} f={d['fem']})")
            for s in belege(text, b, d["partikel"], k=6):
                teil.append(f"- {s}")
        user = ("For each candidate below, decide from the evidence:\n"
                "  typ:      person | place | institution | title | thing | not_a_name\n"
                "  pronoun:  er/ihn/sein | sie/ihr | sie/ihnen (plural) | null\n"
                "  deutsch:  the German rendering to use consistently\n"
                "  hinweis:  one short note if anything is unusual\n\n"
                "Dutch surnames often carry a tussenvoegsel (van, de, van der, "
                "ten). Keep it as part of the name. Personal names stay "
                "unchanged; place names take an established German form only "
                "where one exists. Beware that Dutch 'zijn' is both a "
                "possessive and the verb 'to be', and 'ze' is ambiguous "
                "between singular and plural.\n\n" + "\n".join(teil) +
                '\n\nRespond with a JSON object: {"Name": {"typ": …, '
                '"pronoun": …, "deutsch": …, "hinweis": …}, …}. No fences.')
        for versuch in (1, 2):
            try:
                d = G.json_aus_antwort(
                    G.chat(cfg, SYS, user, 0.2, rolle="vorbereitung"))
                if not d:
                    raise RuntimeError("kein JSON")
                eintraege.update(d)
                print(f"  Block {i//25+1}: {len(d)} Eintraege "
                      f"({time.time()-start:.0f}s)")
                break
            except Exception as e:
                print(f"  Block {i//25+1} Versuch {versuch}: {e}")
                time.sleep(3)

    glossar, personen, figuren = {}, {}, {}
    for name, d in eintraege.items():
        if not isinstance(d, dict) or str(d.get("typ","")).lower() == "not_a_name":
            continue
        de = d.get("deutsch")
        if de and str(de).strip() and str(de).strip() != name:
            glossar[name] = str(de).strip()
        pr = d.get("pronoun")
        if str(d.get("typ","")).lower() == "person" and pr \
           and str(pr).lower() not in ("null","none"):
            personen[name] = str(pr)
            figuren[name] = {"pronomen": str(pr),
                             "rolle": str(d.get("hinweis") or "").strip(),
                             "sprache": ""}
    for pfad, daten in ((G.F["glossar"], glossar), (G.F["personen"], personen),
                        (G.F["figuren"], figuren)):
        if os.path.exists(pfad):
            print(f"  {pfad} existiert — schreibe {pfad}.neu")
            pfad += ".neu"
        json.dump(daten, open(pfad, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2, sort_keys=True)
    for pfad in (G.F["anrede"], G.F["leitmotive"]):
        if not os.path.exists(pfad):
            json.dump({}, open(pfad, "w", encoding="utf-8"), indent=2)
    print(f"\nGlossar {len(glossar)} | Personen {len(personen)} | "
          f"Figuren {len(figuren)}")
    print("Anredematrix und Leitmotive bleiben leer — die lassen sich lokal "
          "nicht zuverlaessig ableiten.")


BRIEFING_TEXT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "briefing_glossar_vorlage.md"),
                     encoding="utf-8").read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "briefing_glossar_vorlage.md")) else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lokal", action="store_true")
    ap.add_argument("--extern", action="store_true")
    ap.add_argument("--min", type=int, default=MIN_COUNT)
    ap.add_argument("--max-terms", type=int, default=220)
    args = ap.parse_args()

    G.kopf("KONKORDANZANALYSE")
    cfg = G.lade_config()
    if args.lokal:
        cfg["glossar_quelle"] = "lokal"
    if args.extern:
        cfg["glossar_quelle"] = "extern"
    if not os.path.exists(G.F["quelle"]):
        sys.exit(f"FEHLER: {G.F['quelle']} nicht gefunden.")
    text = open(G.F["quelle"], encoding="utf-8").read()

    print("Analysiere Kandidaten ...")
    kand = namen_finden(text, args.min)
    mit_p = sum(1 for d in kand.values() if d["partikel"])
    print(f"{len(kand)} Kandidaten ab {args.min} Vorkommen, "
          f"davon {mit_p} mit Tussenvoegsel.\n")

    if cfg["glossar_quelle"] == "lokal":
        lokal_glossar(cfg, text, kand, args)
    else:
        pfad = schreibe_export(cfg, text, kand, args)
        if BRIEFING_TEXT:
            open(BRIEFING, "w", encoding="utf-8").write(BRIEFING_TEXT)
        print(f"Analysepaket: {pfad} ({os.path.getsize(pfad)/1e6:.1f} MB)")
        if BRIEFING_TEXT:
            print(f"Briefing:     {BRIEFING}")


if __name__ == "__main__":
    main()
