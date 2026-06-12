# -*- coding: utf-8 -*-
"""
sync_rocky.py — Henter alle bad- og køkkenprodukter fra rockyshop.de
og genererer products.js med danske salgspriser.

Prismodel: DKK-pris = EUR-pris x KURS x AVANCE, afrundet til "pæn" pris.
Kør scriptet igen, når priserne skal opdateres (eller sæt det på skema
med Windows Opgavestyring / opdater_priser.bat).
"""
import json
import os
import re
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone

CACHE_FIL = "sync_cache.json"   # delresultater — gør kørslen genoptagelig

KURS = 7.46      # EUR -> DKK
AVANCE = 1.12    # 12% oven i Rockys pris
FORSINKELSE = 0.4    # sekunder mellem requests (vær høflig mod serveren)
MAX_SIDER_PR_KATEGORI = 120

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PrisSync/1.0"

# Kategorier der hentes (kun bad og køkken) -> dansk kategorinøgle
KATEGORIER = [
    ("https://www.rockyshop.de/bad/armaturen/",          "armaturer",      "Armaturer"),
    ("https://www.rockyshop.de/bad/badkeramik/",         "keramik",        "Toiletter & håndvaske"),
    ("https://www.rockyshop.de/bad/badmoebel/",          "badmoebler",     "Badmøbler & spejle"),
    ("https://www.rockyshop.de/bad/badewannen/",         "badekar",        "Badekar"),
    ("https://www.rockyshop.de/bad/duschwannen/",        "brusekar",       "Brusekar"),
    ("https://www.rockyshop.de/bad/duschabtrennungen/",  "brusekabiner",   "Brusekabiner & afskærmning"),
    ("https://www.rockyshop.de/bad/accessoires/",        "accessoires",    "Accessoires"),
    ("https://www.rockyshop.de/bad/sonstige/",           "oevrigt-bad",    "Øvrigt til bad"),
    ("https://www.rockyshop.de/kueche/kuechenarmaturen/","koekkenarmatur", "Køkkenarmaturer"),
    ("https://www.rockyshop.de/kueche/zubehoer/",        "koekkentilbehoer","Køkken-tilbehør"),
]

ITEM_RE = re.compile(
    r'<a href="(?P<url>https://www\.rockyshop\.de/[^"]+\.html)"\s+title="(?P<titel>[^"]+)"\s+class="product-image">'
    r'.*?<img[^>]+src="(?P<billede>[^"]+)"'
    r'.*?Artikelnummer:\s*</span>\s*<span>(?P<varenr>[^<]+)</span>'
    r'.*?itemprop="price"\s+name="price"\s+content="(?P<pris>[\d.]+)"'
    r'(?P<rest>.*?)(?=<li class="item|</ul>)',
    re.DOTALL,
)
OLDPRICE_RE = re.compile(r'old-price.*?class="price">\s*([\d.,]+)\s*&euro;|old-price.*?class="price">\s*([\d.,]+)\s*€', re.DOTALL)
# "Sofort lieferbar" = reelt på lager. Schema-InStock-linket står på ALT
# og kan ikke bruges (lærte vi af første fulde kørsel).
LAGER_TEKST = "Sofort lieferbar"
LEVERINGSTID_RE = re.compile(r'data-delivery="deliveryspeed\d+">Lieferzeit:<span>\s*([^<]+)</span>')

from fordansk import fordansk, fragtklasse

KENDTE_MAERKER = [
    "Hansgrohe", "GROHE", "Grohe", "AXOR", "Burgbad", "Pelipal", "Sprinz",
    "Rocky", "Villeroy", "Geberit", "Duravit", "Kaldewei", "Bette", "Ideal",
    "Keuco", "Emco", "Kludi", "Dornbracht", "Blanco", "Franke", "Hoesch",
    "Koralle", "HSK", "Kermi", "Schulte", "Breuer", "Vigour", "Tece", "Viega",
]


def hent(url: str) -> str:
    """Henter en side — prøver op til 3 gange ved netværksfejl,
    så et kort udfald ikke vælter hele kørslen."""
    sidste_fejl = None
    for forsoeg in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            sidste_fejl = e
            time.sleep(5 * (forsoeg + 1))   # 5s, 10s, (15s)
    raise sidste_fejl


def paen_pris(dkk: float) -> int:
    """Afrund til en pæn dansk butikspris."""
    if dkk < 100:
        return max(1, int(round(dkk)))
    if dkk < 1000:
        return int(round(dkk / 10.0) * 10) - 1     # fx 437 -> 439? nej: 440-1=439
    return int(round(dkk / 50.0) * 50) - 1          # fx 3.412 -> 3.399

def til_eur(s: str) -> float:
    return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)


def afhtml(s: str) -> str:
    for a, b in [("&amp;", "&"), ("&quot;", '"'), ("&#039;", "'"), ("&auml;", "ä"),
                 ("&ouml;", "ö"), ("&uuml;", "ü"), ("&Auml;", "Ä"), ("&Ouml;", "Ö"),
                 ("&Uuml;", "Ü"), ("&szlig;", "ß"), ("&deg;", "°"), ("&sup1;", ""),
                 ("&nbsp;", " ")]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


MAERKE_ALIAS = {
    "HG": "Hansgrohe", "VB": "Villeroy & Boch", "Villeroy": "Villeroy & Boch",
    "GROHE": "Grohe", "diverser": "Diverse", "Ideal": "Ideal Standard",
}


def find_maerke(titel: str) -> str:
    t = titel.lower()
    for m in KENDTE_MAERKER:
        if t.startswith(m.lower()):
            return MAERKE_ALIAS.get(m, m)
    foerste = titel.split(" ", 1)[0][:20]
    return MAERKE_ALIAS.get(foerste, foerste)


# Farve aflæses fra det tyske produktnavn. Farver markeret trend=True
# er dem, der trender i badindretning lige nu (mat sort, messing/guld,
# mat hvid, børstet sort krom) — de boostes på siden.
FARVER = [
    (("schwarz chrom", "black chrome", "schwarz chrom gebürstet"), "Børstet sort krom", True),
    (("mattschwarz", "matt schwarz", "schwarz matt", "schwarzmatt", "schwarz gebürstet", "schwarz"), "Mat sort", True),
    (("brushed bronze", "bronze", "messing", "gold optic", "gold-optik", "gold"), "Guld & messing", True),
    (("mattweiß", "matt weiß", "weiß matt", "matt white"), "Mat hvid", True),
    (("edelstahl", "steel", "stahl gebürstet", "rostfrei"), "Rustfrit stål", False),
    (("chrom gebürstet", "brushed chrome"), "Børstet krom", False),
    (("chrom",), "Krom", False),
    (("weiß", "alpin"), "Hvid", False),
]


def find_farve(titel: str):
    t = titel.lower()
    for noegler, navn, trend in FARVER:
        if any(n in t for n in noegler):
            return navn, trend
    return "", False


def parse_side(html: str, katnoegle: str, produkter: dict) -> int:
    """Parser én listeside; returnerer antal NYE produkter."""
    nye = 0
    for m in ITEM_RE.finditer(html):
        varenr = afhtml(m.group("varenr"))
        if varenr in produkter:
            continue
        titel = afhtml(m.group("titel"))
        eur = float(m.group("pris"))
        rest = m.group("rest")
        gammel = OLDPRICE_RE.search(rest or "")
        foer = None
        if gammel:
            g = gammel.group(1) or gammel.group(2)
            try:
                foer = paen_pris(til_eur(g) * KURS * AVANCE)
            except ValueError:
                foer = None
        farve, trend = find_farve(titel)
        lt = LEVERINGSTID_RE.search(rest or "")
        leveringstid = afhtml(lt.group(1)) if lt else ""
        produkter[varenr] = {
            "id": varenr,
            "navn": fordansk(titel),
            "navnDE": titel,
            "cat": katnoegle,
            "maerke": find_maerke(titel),
            "eur": eur,
            "pris": paen_pris(eur * KURS * AVANCE),
            "foerPris": foer,
            "billede": m.group("billede"),
            "url": m.group("url"),
            "lager": LAGER_TEKST in (rest or ""),
            "leveringstid": "" if LAGER_TEKST in (rest or "") else leveringstid,
            "farve": farve,
            "trend": trend,
            "fragt": fragtklasse(katnoegle, titel),
        }
        nye += 1
    return nye


SORTERING = "sort-by=popularity&sort-direction=desc"   # mest populære først


def crawl_kategori(basisurl: str, katnoegle: str, produkter: dict, dybde: int = 0) -> None:
    """Crawler en kategori. Har siden ingen produkter (landingsside),
    findes underkategorierne i stedet og crawles rekursivt.
    Produktlister hentes sorteret efter popularitet, så rækkefølgen
    (= pop-rang) afspejler, hvad der faktisk sælger hos leverandøren."""
    try:
        html = hent(basisurl)
    except Exception as e:
        print(f"  FEJL {basisurl}: {e}", flush=True)
        return

    har_produkter = 'class="product-image"' in html

    if not har_produkter and dybde < 2:
        # Landingsside -> find underkategorier under samme sti
        boern = sorted(set(re.findall(
            r'href="(' + re.escape(basisurl) + r'[a-z0-9\-]+/)"', html)))
        for b in boern:
            crawl_kategori(b, katnoegle, produkter, dybde + 1)
            time.sleep(FORSINKELSE)
        return

    # Produktliste -> hent side 1 igen, nu sorteret efter popularitet
    try:
        html = hent(f"{basisurl}filter_{SORTERING}/")
    except Exception:
        pass   # fallback: brug den usorterede side
    parse_side(html, katnoegle, produkter)

    side = 2
    while side <= MAX_SIDER_PR_KATEGORI:
        if (f"filter_page={side}/" not in html) and (f"filter_page={side}&" not in html):
            break
        try:
            html = hent(f"{basisurl}filter_page={side}&{SORTERING}/")
        except Exception as e:
            print(f"  FEJL side {side} {basisurl}: {e}", flush=True)
            break
        if parse_side(html, katnoegle, produkter) == 0:
            break
        side += 1
        time.sleep(FORSINKELSE)


def paen_pris_op(mindst: float) -> int:
    """Mindste 'pæne' pris der ikke er under gulvet (Rocky + avance)."""
    import math
    if mindst <= 100:
        return math.ceil(mindst)
    if mindst <= 1000:
        p = math.ceil(mindst / 10.0) * 10 - 1
        return p if p >= mindst else p + 10
    p = math.ceil(mindst / 50.0) * 50 - 1
    return p if p >= mindst else p + 50


def anvend_prisjusteringer(produkter: dict) -> int:
    """Anvender priser fra pristester.py (prisjusteringer.json).
    Gulvreglen håndhæves altid: aldrig under Rocky + 12%."""
    try:
        with open("prisjusteringer.json", encoding="utf-8") as f:
            justeringer = json.load(f)
    except FileNotFoundError:
        return 0
    antal = 0
    for varenr, oensket in justeringer.items():
        p = produkter.get(varenr)
        if not p:
            continue
        gulv = paen_pris_op(p["eur"] * KURS * AVANCE)
        p["pris"] = max(int(oensket), gulv)
        antal += 1
    return antal


def main() -> None:
    # Genoptag fra cache, hvis en tidligere kørsel blev afbrudt
    produkter, faerdige = {}, []
    if os.path.exists(CACHE_FIL):
        with open(CACHE_FIL, encoding="utf-8") as f:
            cache = json.load(f)
        produkter, faerdige = cache["produkter"], cache["faerdige"]
        print(f"Genoptager: {len(produkter)} varer fra cache "
              f"({', '.join(faerdige)} allerede færdige)", flush=True)

    for basisurl, katnoegle, katnavn in KATEGORIER:
        if katnoegle in faerdige:
            continue
        set_foer = len(produkter)
        crawl_kategori(basisurl, katnoegle, produkter)
        print(f"{katnavn}: {len(produkter) - set_foer} produkter", flush=True)
        faerdige.append(katnoegle)
        with open(CACHE_FIL, "w", encoding="utf-8") as f:
            json.dump({"faerdige": faerdige, "produkter": produkter}, f, ensure_ascii=False)
        time.sleep(FORSINKELSE)

    # Popularitets-rang: 1 = mest populær i sin kategori (= crawl-rækkefølgen)
    taeller = {}
    for p in produkter.values():
        taeller[p["cat"]] = taeller.get(p["cat"], 0) + 1
        p["pop"] = taeller[p["cat"]]

    justeret = anvend_prisjusteringer(produkter)
    if justeret:
        print(f"Prisjusteringer fra pristester anvendt på {justeret} varer (gulv håndhævet)")

    # Sikring: overskriv aldrig et godt katalog med et halvt et
    # (fx hvis netværket røg undervejs). Behold den gamle fil,
    # hvis den nye kørsel gav under 60% af de eksisterende varer.
    try:
        with open("products.js", encoding="utf-8") as f:
            t = f.read()
        eksisterende = t.count('"id":')
    except FileNotFoundError:
        eksisterende = 0
    if eksisterende and len(produkter) < eksisterende * 0.6:
        print(f"\nAFBRUDT: kun {len(produkter)} varer hentet, men products.js "
              f"har {eksisterende}. Filen er IKKE overskrevet — tjek "
              f"internetforbindelsen og kør scriptet igen.")
        return

    data = {
        "genereret": datetime.now(timezone.utc).isoformat(),
        "kilde": "rockyshop.de",
        "kurs": KURS,
        "avance": AVANCE,
        "kategorier": {k: n for _, k, n in KATEGORIER},
        "produkter": sorted(produkter.values(), key=lambda p: (p["cat"], p["pop"])),
    }
    # Fjern tomme felter og skriv kompakt — sparer flere MB på 12.000+ varer
    for p in data["produkter"]:
        for felt, tomt in (("foerPris", None), ("farve", ""), ("trend", False),
                           ("leveringstid", "")):
            if p.get(felt) == tomt and felt in p:
                del p[felt]
        if p.get("navnDE") == p.get("navn"):
            del p["navnDE"]
    with open("products.js", "w", encoding="utf-8") as f:
        f.write("// Genereret af sync_rocky.py — redigér ikke i hånden.\n")
        f.write("// Kør 'py sync_rocky.py' for at opdatere priser fra rockyshop.de.\n")
        f.write("const SHOP_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    if os.path.exists(CACHE_FIL):
        os.remove(CACHE_FIL)   # færdig — cachen er ikke længere nødvendig
    print(f"\nI alt {len(produkter)} produkter gemt i products.js")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        main()
    except Exception:
        # Sørg for at et crash altid efterlader et synligt spor i loggen
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        raise
