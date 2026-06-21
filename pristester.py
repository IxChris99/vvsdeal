# -*- coding: utf-8 -*-
"""
pristester.py — Tjekker dine priser mod danske VVS-forhandlere.

Slår hvert varenummer op hos LavprisVVS, BilligVVS og CompletVVS,
finder laveste konkurrentpris og foreslår en ny pris efter reglen:

    ny pris = ca. 10% under billigste danske konkurrent
    MEN ALDRIG under gulvet: Rockys EUR-pris x 7,46 x 1,12

Brug:
    py pristester.py              -> tjekker de 200 dyreste varer
    py pristester.py --antal 50   -> tjekker de 50 dyreste
    py pristester.py --alle       -> tjekker alle varer (tager timer!)
    py pristester.py --varenr 31806000 27267000   -> tjekker bestemte varer
    py pristester.py --opdater    -> skriver de nye priser til
                                     prisjusteringer.json OG products.js

Resultatet gemmes altid i prisrapport.csv (kan åbnes i Excel).
prisjusteringer.json bruges af sync_rocky.py, så justerede priser
overlever næste katalog-synkronisering.
"""
import argparse
import csv
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request

KURS = 7.46
AVANCE = 1.12          # gulv: Rocky + 12% — sælg ALDRIG under dette
UNDERBUD = 0.90        # læg dig ~10% under billigste danske konkurrent
MAX_KONK_FAKTOR = 5    # en konkurrentpris over 5x Rocky-gulv = fejl-match -> ignoreres


def konkurrent_plausibel(eur: float, konkurrentpris: float) -> bool:
    """En konkurrentpris er kun troværdig hvis den ikke er absurd høj ift.
    vores Rocky-kost (fanger gamle fejl-match som €92-vare -> 12.199 kr)."""
    return konkurrentpris <= eur * KURS * AVANCE * MAX_KONK_FAKTOR
FORSINKELSE = 0.6      # sekunder mellem opslag (vær høflig)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SHOPS = [
    ("LavprisVVS", "https://www.lavprisvvs.dk/search?q={q}"),
    ("BilligVVS",  "https://www.billigvvs.dk/search?q={q}"),
    ("CompletVVS", "https://www.completvvs.dk/search?q={q}"),
]

JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def hent(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "da-DK,da"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def gulv_pris(eur: float) -> float:
    """Den absolutte minimumspris i DKK (Rocky + 12%)."""
    return eur * KURS * AVANCE


def paen_pris_op(mindst: float) -> int:
    """Mindste 'pæne' butikspris, der IKKE er under gulvet."""
    if mindst <= 100:
        return math.ceil(mindst)
    if mindst <= 1000:
        p = math.ceil(mindst / 10.0) * 10 - 1
        return p if p >= mindst else p + 10
    p = math.ceil(mindst / 50.0) * 50 - 1
    return p if p >= mindst else p + 50


def paen_pris_ned(hoejst: float) -> int:
    """Største 'pæne' butikspris, der ikke er over loftet."""
    if hoejst <= 100:
        return max(1, math.floor(hoejst))
    if hoejst <= 1000:
        p = math.floor(hoejst / 10.0) * 10 - 1
        return p if p <= hoejst else p - 10
    p = math.floor(hoejst / 50.0) * 50 - 1
    return p if p <= hoejst else p - 50


def kun_cifre(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def kandidat_former(varenr: str):
    """Søge-varianter af varenummeret. Danske shops bruger ofte producentens
    format MED separatorer (fx Geberit 146.210.11.1), mens Rocky har 146210111."""
    former = [varenr]
    d = kun_cifre(varenr)
    if len(d) == 9:                                   # Geberit-format
        former.append(f"{d[0:3]}.{d[3:6]}.{d[6:8]}.{d[8:9]}")
    return former


def find_konkurrentpris(html: str, varenr: str):
    """Finder produktpris i sidens JSON-LD — KUN ved sikker validering, så vi
    aldrig får en forkert pris. Returnerer (pris, navn) eller None."""
    vdig = kun_cifre(varenr)
    produkter = []
    for m in JSONLD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for d in (data if isinstance(data, list) else [data]):
            if not isinstance(d, dict) or d.get("@type") != "Product":
                continue
            offers = d.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            pris = offers.get("price")
            if pris is None:
                continue
            sku = kun_cifre(str(d.get("sku") or d.get("mpn") or d.get("gtin13") or ""))
            produkter.append((float(pris), d.get("name", ""), sku))

    # 1) Eksakt artikel-match på sku/mpn/gtin (cifre — uafhængigt af punktum-format)
    if vdig:
        for pris, navn, sku in produkter:
            if sku and sku == vdig:
                return pris, navn

    # 2) Søgningen ramte præcis ÉT produkt OG varenummeret står på siden
    #    (i en af de kendte former) -> sikker kobling, ingen gætteri.
    if len(produkter) == 1 and len(vdig) >= 6:
        if any(form in html for form in kandidat_former(varenr)):
            return produkter[0][0], produkter[0][1]
    return None


def skriv_konkurrenter_js(rapport):
    """Gemmer konkurrentpriser i konkurrenter.js (bruges af admin.html).
    Fletter med eksisterende data, så flere kørsler akkumulerer viden."""
    from datetime import datetime, timezone
    try:
        with open("konkurrenter.js", encoding="utf-8") as f:
            t = f.read()
        i = t.index("const KONKURRENT_DATA = ") + len("const KONKURRENT_DATA = ")
        priser = json.loads(t[i:t.rindex(";")]).get("priser", {})
    except (FileNotFoundError, ValueError):
        priser = {}
    for r in rapport:
        priser[r["varenr"]] = {
            "LavprisVVS": r["LavprisVVS"] or None,
            "BilligVVS": r["BilligVVS"] or None,
            "CompletVVS": r["CompletVVS"] or None,
            "billigste": r["billigsteKonkurrent"] or None,
            "status": r["status"],
            "tjekket": datetime.now(timezone.utc).isoformat()[:10],
        }
    with open("konkurrenter.js", "w", encoding="utf-8") as f:
        f.write("// Genereret af pristester.py — konkurrentpriser til admin.html.\n")
        f.write("const KONKURRENT_DATA = ")
        json.dump({"genereret": datetime.now(timezone.utc).isoformat(),
                   "priser": priser}, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"konkurrenter.js opdateret ({len(priser)} varer med konkurrentdata)")


def indlaes_products_js():
    with open("products.js", encoding="utf-8") as f:
        tekst = f.read()
    i = tekst.index("const SHOP_DATA = ") + len("const SHOP_DATA = ")
    j = tekst.rindex(";")
    return json.loads(tekst[i:j]), tekst[:i], tekst[j:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--antal", type=int, default=200, help="antal varer (dyreste først)")
    ap.add_argument("--alle", action="store_true", help="tjek alle varer")
    ap.add_argument("--varenr", nargs="*", default=None, help="tjek kun disse varenumre")
    ap.add_argument("--opdater", action="store_true",
                    help="skriv nye priser til prisjusteringer.json og products.js")
    ap.add_argument("--nye", action="store_true",
                    help="spring varer over, der allerede ligger i konkurrenter.js")
    arg = ap.parse_args()

    data, praefix, suffiks = indlaes_products_js()
    produkter = data["produkter"]

    tjekkede = {}
    if arg.nye:
        try:
            with open("konkurrenter.js", encoding="utf-8") as f:
                t = f.read()
            i = t.index("const KONKURRENT_DATA = ") + len("const KONKURRENT_DATA = ")
            tjekkede = {k: v.get("tjekket", "") for k, v in
                        json.loads(t[i:t.rindex(";")]).get("priser", {}).items()}
            print(f"Springer {len(tjekkede)} allerede tjekkede varer over")
        except (FileNotFoundError, ValueError):
            pass

    if arg.varenr:
        udvalg = [p for p in produkter if p["id"] in arg.varenr]
    elif arg.alle:
        udvalg = [p for p in sorted(produkter, key=lambda p: -p["pris"]) if p["id"] not in tjekkede]
    else:
        udvalg = [p for p in sorted(produkter, key=lambda p: -p["pris"]) if p["id"] not in tjekkede][:arg.antal]
        # Rullende opdatering: er alle varer tjekket, genopfriskes de ældste,
        # så priserne aldrig bliver mere end nogle uger gamle.
        rest = arg.antal - len(udvalg)
        if arg.nye and rest > 0 and tjekkede:
            aeldste = sorted((p for p in produkter if p["id"] in tjekkede),
                             key=lambda p: tjekkede[p["id"]])[:rest]
            udvalg += aeldste
            if aeldste:
                print(f"Genopfrisker desuden de {len(aeldste)} ældst tjekkede varer")

    print(f"Tjekker {len(udvalg)} varer mod {len(SHOPS)} danske forhandlere...\n", flush=True)

    rapport = []
    justeringer = {}
    for nr, p in enumerate(udvalg, 1):
        gulv = gulv_pris(p["eur"])
        gulv_paen = paen_pris_op(gulv)
        priser = {}
        for shopnavn, skabelon in SHOPS:
            for form in kandidat_former(p["id"]):     # prøv flere varenr-formater
                try:
                    fund = find_konkurrentpris(hent(skabelon.format(q=urllib.parse.quote(form))), p["id"])
                    if fund:
                        priser[shopnavn] = fund[0]
                        break
                except Exception:
                    pass
                time.sleep(FORSINKELSE)

        if priser:
            billigste = min(priser.values())
            maal = paen_pris_ned(billigste * UNDERBUD)
            if maal >= billigste:
                maal = int(billigste) - 1
            ny_pris = max(maal, gulv_paen)
            status = "OK: under konkurrent" if ny_pris < billigste else "GULV: kan ikke matche"
            # Kun konkurrent-bakkede justeringer gemmes (ellers fastfryses fejlpriser)
            if ny_pris != p["pris"]:
                justeringer[p["id"]] = ny_pris
        else:
            billigste = None
            ny_pris = gulv_paen   # ingen konkurrent -> ren Rocky-mark, INGEN justering
            status = "ingen konkurrentpris fundet"

        rapport.append({
            "varenr": p["id"], "navn": p["navn"], "maerke": p["maerke"],
            "rockyEUR": p["eur"], "gulvDKK": round(gulv, 2),
            "nuvaerende": p["pris"],
            "LavprisVVS": priser.get("LavprisVVS", ""),
            "BilligVVS": priser.get("BilligVVS", ""),
            "CompletVVS": priser.get("CompletVVS", ""),
            "billigsteKonkurrent": billigste or "",
            "nyPris": ny_pris, "status": status,
        })
        maerkat = f"{billigste:.0f} kr." if billigste else "—"
        print(f"[{nr}/{len(udvalg)}] {p['id']} {p['navn'][:45]:45} "
              f"din: {p['pris']:>6} | konkurrent: {maerkat:>9} | ny: {ny_pris:>6}  {status}",
              flush=True)

    # CSV-rapport (semikolon + BOM, så dansk Excel åbner den pænt)
    with open("prisrapport.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rapport[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rapport)
    print(f"\nRapport gemt i prisrapport.csv ({len(rapport)} varer)")

    skriv_konkurrenter_js(rapport)

    aendringer = [r for r in rapport if r["nyPris"] != r["nuvaerende"]]
    paa_gulv = [r for r in rapport if r["status"].startswith("GULV")]
    print(f"Prisændringer foreslået: {len(aendringer)} | varer låst på gulvpris: {len(paa_gulv)}")

    if arg.opdater and justeringer:
        # Gem justeringer så sync_rocky.py kan genbruge dem
        try:
            with open("prisjusteringer.json", encoding="utf-8") as f:
                gamle = json.load(f)
        except FileNotFoundError:
            gamle = {}
        gamle.update(justeringer)
        with open("prisjusteringer.json", "w", encoding="utf-8") as f:
            json.dump(gamle, f, ensure_ascii=False, indent=1)

        # Skriv også direkte til products.js
        for p in produkter:
            if p["id"] in justeringer:
                p["pris"] = justeringer[p["id"]]
        with open("products.js", "w", encoding="utf-8") as f:
            f.write(praefix)
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write(suffiks)
        print(f"Opdateret: {len(justeringer)} priser skrevet til products.js "
              f"og prisjusteringer.json")
    elif justeringer:
        print("Kør igen med --opdater for at skrive de nye priser til shoppen.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
