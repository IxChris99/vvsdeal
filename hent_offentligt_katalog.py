# -*- coding: utf-8 -*-
"""
hent_offentligt_katalog.py — Henter den OFFENTLIGE products.js fra den
live side (uden indkøbspriser) som hurtigt udgangspunkt på en ny PC.

Nok til at arbejde med layout/forside. Skal du bruge priser/avance
(pristester, genberegn), så kør 'py sync_rocky.py' for at bygge den
fulde products.js med eur-indkøbspriser lokalt.
"""
import sys
import urllib.request

URL = "https://www.vvsdeal.dk/products.js"


def main() -> None:
    print(f"Henter {URL} ...")
    req = urllib.request.Request(URL, headers={"User-Agent": "VVSdeal-setup/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open("products.js", "wb") as f:
        f.write(data)
    print(f"products.js hentet ({len(data) / 1e6:.1f} MB) — siden kan nu vises lokalt.")
    print("Bemærk: denne udgave er UDEN indkøbspriser. Kør 'py sync_rocky.py' "
          "for den fulde version med avance-data.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
