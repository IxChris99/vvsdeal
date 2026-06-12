# -*- coding: utf-8 -*-
"""
byg_deploy.py — Bygger den OFFENTLIGE udgave af shoppen i dist/.

VIGTIGT: Fjerner alt forretningsfølsomt før upload:
  • eur-feltet (din indkøbspris hos Rocky) strippes fra products.js
  • admin.html, konkurrenter.js, prisrapport m.m. udelades helt

dist/ er det ENESTE, der må lægges på en offentlig server.
"""
import json
import os
import shutil
import sys

UD = "dist"
KOPIER = ["index.html", "tak.html", "trends.js", "sitemap.xml", "robots.txt"]
KOPIER_MAPPER = ["produkt"]


def main() -> None:
    shutil.rmtree(UD, ignore_errors=True)
    os.makedirs(UD)

    # products.js uden indkøbspriser
    with open("products.js", encoding="utf-8") as f:
        t = f.read()
    i = t.index("const SHOP_DATA = ") + len("const SHOP_DATA = ")
    data = json.loads(t[i:t.rindex(";")])
    for p in data["produkter"]:
        p.pop("eur", None)        # indkøbspris — ALDRIG offentlig
        p.pop("url", None)        # direkte leverandørlink — heller ikke
    with open(os.path.join(UD, "products.js"), "w", encoding="utf-8") as f:
        f.write("const SHOP_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    for fil in KOPIER:
        if os.path.exists(fil):
            shutil.copy2(fil, UD)
    for mappe in KOPIER_MAPPER:
        if os.path.isdir(mappe):
            shutil.copytree(mappe, os.path.join(UD, mappe))

    antal = sum(len(fs) for _, _, fs in os.walk(UD))
    print(f"dist/ bygget: {antal} filer — klar til upload (UDEN indkøbspriser og admin)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
