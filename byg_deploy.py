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
KOPIER = ["index.html", "tak.html", "trends.js", "sitemap.xml", "robots.txt", "logo-icon.png", "favicon.png"]
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

    byg_kategori_sider(data.get("kategorier", {}))

    antal = sum(len(fs) for _, _, fs in os.walk(UD))
    print(f"dist/ bygget: {antal} filer — klar til upload (UDEN indkøbspriser og admin)")


def byg_kategori_sider(kategorier: dict) -> None:
    """Bygger egne sider for hver kategori (dist/kategori/<key>.html),
    så hver kategori får sin egen URL, titel og meta-beskrivelse til SEO."""
    if not os.path.exists("index.html"):
        return
    with open("index.html", encoding="utf-8") as f:
        skabelon = f.read()

    ud_mappe = os.path.join(UD, "kategori")
    os.makedirs(ud_mappe, exist_ok=True)

    for k, navn in kategorier.items():
        html = skabelon

        # Titel og meta-beskrivelse
        html = html.replace(
            "<title>VVSdeal — Alt til bad &amp; køkken i tysk kvalitet</title>",
            f"<title>{navn} — VVSdeal</title>",
        )
        html = html.replace(
            '<meta name="description" content="Armaturer, badmøbler, brusekabiner, badekar og '
            'køkkenarmaturer fra Hansgrohe, Grohe, Burgbad m.fl. Tysk kvalitet — leveret i Danmark.">',
            f'<meta name="description" content="{navn} fra Hansgrohe, Grohe, Burgbad m.fl. '
            f'Tysk kvalitet til danske priser — fri fragt over 999 kr. og 30 dages returret.">\n'
            f'<link rel="canonical" href="https://www.vvsdeal.dk/kategori/{k}.html">',
        )

        # Overskrift og tekst i produktsektionen
        html = html.replace(
            "<h2>Hele sortimentet til bad &amp; køkken</h2>",
            f"<h2>{navn}</h2>",
        )
        html = html.replace(
            "<p>Søg blandt tusindvis af originale mærkevarer — alle leveres direkte fra vores "
            "tyske lager med fuld producentgaranti.</p>",
            f"<p>Se hele udvalget af {navn.lower()} — leveres direkte fra vores tyske lager "
            f"med fuld producentgaranti.</p>",
        )

        # Forvalgt kategori + relative stier til produktdata (siden ligger i kategori/)
        html = html.replace(
            '<script src="products.js"></script>',
            f'<script>const PRESET_KAT = "{k}";</script>\n<script src="../products.js"></script>',
        )
        html = html.replace(
            '<script src="trends.js"></script>',
            '<script src="../trends.js"></script>',
        )

        with open(os.path.join(ud_mappe, f"{k}.html"), "w", encoding="utf-8") as f:
            f.write(html)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
