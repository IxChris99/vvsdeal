# -*- coding: utf-8 -*-
"""
trends_sync.py — Henter danske Google Trends-data og genererer trends.js

Måler 12 måneders dansk søgeinteresse (geo=DK) for:
  • farver        ("sort vandhane", "guld vandhane", ...)
  • mærker        ("hansgrohe", "grohe", "burgbad", ...)
  • produkttyper  ("regnbruser", "fritstående badekar", ...)

Hvert emne får en boost-faktor 0,70–1,50:
  > 1  = trender (vises højere på siden)
  < 1  = falder i interesse
Faktoren kombinerer momentum (seneste kvartal vs. hele året)
og niveau (interesse ift. de andre ord i samme gruppe).

Kør fx ugentligt:  py trends_sync.py
"""
import json
import sys
import time
from datetime import datetime, timezone

from pytrends.request import TrendReq

GEO = "DK"
TIMEFRAME = "today 12-m"
PAUSE = 8          # sekunder mellem opslag — Google smider 429 ved hastværk
FORSOEG = 3

# Grupper på max 5 søgeord (Google normaliserer internt i en gruppe).
# mapping: søgeord -> liste af (felt, nøgle) som boostet skal gælde for.
GRUPPER = [
    {
        "navn": "farver",
        "ord": ["sort vandhane", "guld vandhane", "hvid vandhane", "krom vandhane"],
        "mapping": {
            "sort vandhane": [("farver", "Mat sort"), ("farver", "Børstet sort krom")],
            "guld vandhane": [("farver", "Guld & messing")],
            "hvid vandhane": [("farver", "Mat hvid"), ("farver", "Hvid")],
            "krom vandhane": [("farver", "Krom"), ("farver", "Børstet krom")],
        },
    },
    {
        "navn": "maerker-1",
        "ord": ["hansgrohe", "grohe", "geberit", "duravit", "burgbad"],
        "mapping": {
            "hansgrohe": [("maerker", "Hansgrohe"), ("maerker", "AXOR")],
            "grohe": [("maerker", "Grohe")],
            "geberit": [("maerker", "Geberit")],
            "duravit": [("maerker", "Duravit")],
            "burgbad": [("maerker", "Burgbad")],
        },
    },
    {
        "navn": "typer-1",
        "ord": ["regnbruser", "fritstående badekar", "væghængt toilet",
                "brusekabine", "badeværelsesmøbler"],
        "mapping": {
            "regnbruser": [("kategorier", "armaturer")],
            "fritstående badekar": [("kategorier", "badekar")],
            "væghængt toilet": [("kategorier", "keramik")],
            "brusekabine": [("kategorier", "brusekabiner"), ("kategorier", "brusekar")],
            "badeværelsesmøbler": [("kategorier", "badmoebler")],
        },
    },
    {
        "navn": "typer-2",
        "ord": ["køkkenarmatur", "håndvask", "bruseslange"],
        "mapping": {
            "køkkenarmatur": [("kategorier", "koekkenarmatur"), ("kategorier", "koekkentilbehoer")],
            "håndvask": [("kategorier", "accessoires")],
            "bruseslange": [("kategorier", "oevrigt-bad")],
        },
    },
]


def klamp(x, lo=0.70, hi=1.50):
    return max(lo, min(hi, x))


def hent_gruppe(pt, ord_liste):
    """Returnerer DataFrame med ugentlig interesse for op til 5 ord."""
    for forsoeg in range(FORSOEG):
        try:
            pt.build_payload(ord_liste, timeframe=TIMEFRAME, geo=GEO)
            df = pt.interest_over_time()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"  forsøg {forsoeg + 1} fejlede: {e}", flush=True)
        time.sleep(PAUSE * (forsoeg + 2))
    return None


def indlaes_eksisterende():
    """Læser tidligere trends.js, så en fejlet gruppe ikke sletter gamle data."""
    try:
        with open("trends.js", encoding="utf-8") as f:
            t = f.read()
        i = t.index("const TRENDS_DATA = ") + len("const TRENDS_DATA = ")
        gammel = json.loads(t[i:t.rindex(";")])
        return ({"farver": gammel.get("farver", {}),
                 "maerker": gammel.get("maerker", {}),
                 "kategorier": gammel.get("kategorier", {})},
                gammel.get("soegeord", {}))
    except (FileNotFoundError, ValueError):
        return {"farver": {}, "maerker": {}, "kategorier": {}}, {}


def main() -> None:
    pt = TrendReq(hl="da-DK", tz=-60)
    resultat, raadata = indlaes_eksisterende()

    # Opvarmning: første kald i en frisk session får ofte 429.
    # Et "offer-kald" varmer cookies op, så de rigtige grupper går igennem.
    try:
        pt.build_payload(["vvs"], timeframe=TIMEFRAME, geo=GEO)
        pt.interest_over_time()
    except Exception:
        pass
    time.sleep(PAUSE)

    for gruppe in GRUPPER:
        print(f"Henter gruppe: {gruppe['navn']} ({', '.join(gruppe['ord'])})", flush=True)
        df = hent_gruppe(pt, gruppe["ord"])
        if df is None:
            print("  SPRUNGET OVER (ingen data)", flush=True)
            continue

        # niveau: gennemsnit seneste 13 uger ift. gruppens middel
        seneste = df.tail(13)
        gruppemiddel = max(seneste[gruppe["ord"]].mean().mean(), 1e-9)

        for ord_ in gruppe["ord"]:
            if ord_ not in df.columns:
                continue
            aar_snit = max(float(df[ord_].mean()), 1e-9)
            kvartal_snit = float(seneste[ord_].mean())
            momentum = kvartal_snit / aar_snit          # >1 = stigende
            momentum = max(0.5, min(1.6, momentum))     # dæmp ekstremer
            niveau = kvartal_snit / gruppemiddel        # >1 = mere søgt end de andre
            if kvartal_snit < 5:
                boost = 1.0   # for lille søgevolumen -> hverken boost eller straf
            else:
                boost = klamp(0.6 * momentum + 0.4 * niveau)
            raadata[ord_] = {
                "momentum": round(momentum, 3),
                "niveau": round(niveau, 3),
                "boost": round(boost, 3),
            }
            for felt, noegle in gruppe["mapping"].get(ord_, []):
                resultat[felt][noegle] = round(boost, 3)
            print(f"  {ord_:28} momentum {momentum:5.2f} | niveau {niveau:5.2f} "
                  f"| boost {boost:.2f}", flush=True)
        time.sleep(PAUSE)

    data = {
        "genereret": datetime.now(timezone.utc).isoformat(),
        "kilde": f"Google Trends (geo={GEO}, {TIMEFRAME})",
        **resultat,
        "soegeord": raadata,
    }
    with open("trends.js", "w", encoding="utf-8") as f:
        f.write("// Genereret af trends_sync.py — danske Google Trends-data.\n")
        f.write("// Kør 'py trends_sync.py' for at opdatere (fx ugentligt).\n")
        f.write("const TRENDS_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\ntrends.js gemt — {len(raadata)} søgeord, "
          f"{sum(len(v) for v in resultat.values())} boost-regler")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
