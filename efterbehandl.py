# -*- coding: utf-8 -*-
"""
efterbehandl.py — Efterbehandler products.js:
  1. Oversætter produktnavne til dansk (original gemmes i navnDE)
  2. Tilføjer fragtklasse (pakke/tung/fragtmand)
  3. Komprimerer filen (fjerner tomme felter og overflødig formatering)

Kør efter en katalog-synkronisering. Kan køres flere gange uden skade.
"""
import json
import sys

from fordansk import fordansk, fragtklasse


def main() -> None:
    with open("products.js", encoding="utf-8") as f:
        t = f.read()
    i = t.index("const SHOP_DATA = ") + len("const SHOP_DATA = ")
    data = json.loads(t[i:t.rindex(";")])

    oversat = 0
    for p in data["produkter"]:
        original = p.get("navnDE") or p["navn"]
        dansk = fordansk(original)
        if dansk != original:
            p["navnDE"] = original
            p["navn"] = dansk
            oversat += 1
        p["fragt"] = fragtklasse(p["cat"], original)
        # Fjern tomme felter — sparer megabytes på 12.000+ varer
        for felt, tomt in (("foerPris", None), ("farve", ""), ("trend", False)):
            if p.get(felt) == tomt and felt in p:
                del p[felt]

    foer_mb = len(t) / 1e6
    with open("products.js", "w", encoding="utf-8") as f:
        f.write("// Genereret af sync_rocky.py + efterbehandl.py — redigér ikke i hånden.\n")
        f.write("const SHOP_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    import os
    efter_mb = os.path.getsize("products.js") / 1e6
    print(f"Oversat: {oversat} af {len(data['produkter'])} navne")
    print(f"Filstørrelse: {foer_mb:.1f} MB -> {efter_mb:.1f} MB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
