# -*- coding: utf-8 -*-
"""Konverterer prisrapport.csv -> konkurrenter.js (til admin.html).
Bruges kun, hvis rapporten er lavet med en ældre pristester —
nyere kørsler skriver selv konkurrenter.js."""
import csv
import sys

from pristester import skriv_konkurrenter_js


def tal(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return ""


def main() -> None:
    with open("prisrapport.csv", encoding="utf-8-sig") as f:
        raekker = list(csv.DictReader(f, delimiter=";"))
    rapport = [{
        "varenr": r["varenr"],
        "LavprisVVS": tal(r.get("LavprisVVS")),
        "BilligVVS": tal(r.get("BilligVVS")),
        "CompletVVS": tal(r.get("CompletVVS")),
        "billigsteKonkurrent": tal(r.get("billigsteKonkurrent")),
        "status": r.get("status", ""),
    } for r in raekker]
    skriv_konkurrenter_js(rapport)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
