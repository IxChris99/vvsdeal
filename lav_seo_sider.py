# -*- coding: utf-8 -*-
"""
lav_seo_sider.py — Genererer statiske SEO-produktsider + sitemap.

For hver vare i products.js laves produkt/<varenr>.html med:
  • dansk titel/meta-beskrivelse
  • JSON-LD Product-schema (Google Shopping/rige resultater)
  • billede, pris, specifikationer og "Læg i kurv"-link til shoppen

Desuden genereres sitemap.xml og robots.txt.
VIGTIGT: Ret DOMAIN til dit rigtige domæne før upload.
Kør efter hver katalog-synkronisering (efter efterbehandl.py).
"""
import json
import os
import sys
import html as H

DOMAIN = "https://www.vvsdeal.dk"
SHOPNAVN = "VVSdeal"

SIDE = """<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titel} | {shop}</title>
<meta name="description" content="{beskrivelse}">
<link rel="canonical" href="{domain}/produkt/{filid}.html">
<script type="application/ld+json">{jsonld}</script>
<style>
  body {{ font-family: "Segoe UI", system-ui, sans-serif; color: #21303d; max-width: 900px; margin: 0 auto; padding: 24px; line-height: 1.6; }}
  a {{ color: #0e3a5c; }}
  .top a {{ text-decoration: none; font-weight: 700; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin-top: 20px; }}
  img {{ max-width: 100%; max-height: 420px; object-fit: contain; }}
  h1 {{ color: #0e3a5c; font-size: 1.5rem; line-height: 1.3; }}
  .pris {{ font-size: 1.8rem; font-weight: 800; color: #0e3a5c; margin: 12px 0 2px; }}
  .moms {{ color: #64748b; font-size: .85rem; margin-bottom: 16px; }}
  ul {{ padding-left: 0; list-style: none; }}
  li {{ padding: 6px 0; border-bottom: 1px dashed #e4ebf2; font-size: .92rem; }}
  .knap {{ display: inline-block; background: #ff7a1a; color: #fff; font-weight: 700; padding: 14px 32px; border-radius: 999px; text-decoration: none; margin-top: 18px; }}
  @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<p class="top"><a href="{domain}/">&larr; {shop} — alt til bad &amp; køkken</a></p>
<div class="grid">
  <div><img src="{billede}" alt="{titel}"></div>
  <div>
    <h1>{titel}</h1>
    <p style="color:#64748b;font-size:.85rem">Varenr. {id} · {maerke}</p>
    <div class="pris">{pris} kr.</div>
    <div class="moms">Inkl. 25% moms · {fragttekst}</div>
    <ul>
      <li><b>Mærke:</b> {maerke}</li>
      <li><b>Kategori:</b> {kategori}</li>
      {farvelinje}
      <li><b>Lagerstatus:</b> {lagertekst}</li>
      <li><b>Garanti:</b> Fuld producentgaranti</li>
    </ul>
    <a class="knap" href="{domain}/index.html?vare={id}">Se i shoppen &amp; læg i kurv →</a>
  </div>
</div>
</body>
</html>
"""

FRAGT_TEKST = {"pakke": "Fri fragt over 999 kr.", "tung": "Levering til døren",
               "fragtmand": "Leveres med fragtmand"}


def fil_id(varenr: str) -> str:
    """Varenumre kan indeholde / \\ : m.m. — gør dem filnavn-sikre."""
    import re
    return re.sub(r"[^A-Za-z0-9._-]", "-", varenr)


def main() -> None:
    with open("products.js", encoding="utf-8") as f:
        t = f.read()
    i = t.index("const SHOP_DATA = ") + len("const SHOP_DATA = ")
    data = json.loads(t[i:t.rindex(";")])

    os.makedirs("produkt", exist_ok=True)
    urls = []
    for p in data["produkter"]:
        kategori = data["kategorier"].get(p["cat"], p["cat"])
        jsonld = json.dumps({
            "@context": "https://schema.org", "@type": "Product",
            "name": p["navn"], "sku": p["id"], "image": p["billede"],
            "brand": {"@type": "Brand", "name": p["maerke"]},
            "offers": {
                "@type": "Offer", "priceCurrency": "DKK", "price": p["pris"],
                "availability": "https://schema.org/" + ("InStock" if p.get("lager") else "BackOrder"),
                "url": f"{DOMAIN}/produkt/{fil_id(p['id'])}.html",
            },
        }, ensure_ascii=False)
        navn = H.escape(p["navn"])
        side = SIDE.format(
            titel=navn, shop=SHOPNAVN, domain=DOMAIN, id=p["id"], filid=fil_id(p["id"]),
            beskrivelse=H.escape(f"Køb {p['navn']} til {p['pris']} kr. hos {SHOPNAVN}. "
                                 f"Original {p['maerke']} — hurtig levering i hele Danmark."),
            jsonld=jsonld, billede=p["billede"], maerke=H.escape(p["maerke"]),
            kategori=H.escape(kategori), pris=f"{p['pris']:,}".replace(",", "."),
            fragttekst=FRAGT_TEKST.get(p.get("fragt", "pakke"), ""),
            farvelinje=f"<li><b>Farve:</b> {H.escape(p['farve'])}</li>" if p.get("farve") else "",
            lagertekst="På lager — sendes inden for 1 hverdag" if p.get("lager")
                       else "Skaffevare — se leveringstid i shoppen",
        )
        with open(f"produkt/{fil_id(p['id'])}.html", "w", encoding="utf-8") as f:
            f.write(side)
        urls.append(f"{DOMAIN}/produkt/{fil_id(p['id'])}.html")

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.write(f"<url><loc>{DOMAIN}/</loc><changefreq>daily</changefreq></url>\n")
        for u in urls:
            f.write(f"<url><loc>{u}</loc><changefreq>weekly</changefreq></url>\n")
        f.write("</urlset>\n")

    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nDisallow: /admin.html\n\nSitemap: {DOMAIN}/sitemap.xml\n")

    print(f"Genereret: {len(urls)} produktsider i produkt/ + sitemap.xml + robots.txt")
    if "DITDOMAENE" in DOMAIN:
        print("HUSK: Ret DOMAIN i lav_seo_sider.py til dit rigtige domæne!")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
