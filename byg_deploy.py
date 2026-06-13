# -*- coding: utf-8 -*-
"""
byg_deploy.py — Bygger den OFFENTLIGE udgave af shoppen i dist/.

VIGTIGT: Fjerner alt forretningsfølsomt før upload:
  • eur-feltet (din indkøbspris hos Rocky) strippes fra products.js
  • admin.html, konkurrenter.js, prisrapport m.m. udelades helt

dist/ er det ENESTE, der må lægges på en offentlig server.
"""
import base64
import copy
import json
import os
import shutil
import sys

UD = "dist"
KOPIER = ["index.html", "tak.html", "om-os.html", "kontakt.html", "shared.css", "trends.js", "sitemap.xml", "robots.txt", "logo-icon.png", "favicon.png"]
KOPIER_MAPPER = ["produkt"]
ADMIN_ENC_FIL = "admin_enc.html"   # krypteret, committet genbrugskopi (sikker i offentligt repo)


def main() -> None:
    shutil.rmtree(UD, ignore_errors=True)
    os.makedirs(UD)

    # products.js — fuld udgave (MED eur) bevares kun i hukommelsen til den krypterede admin
    with open("products.js", encoding="utf-8") as f:
        t = f.read()
    i = t.index("const SHOP_DATA = ") + len("const SHOP_DATA = ")
    fuld_data = json.loads(t[i:t.rindex(";")])

    # Offentlig udgave: strip indkøbspris og leverandørlink
    data = copy.deepcopy(fuld_data)
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
    byg_admin(fuld_data)

    antal = sum(len(fs) for _, _, fs in os.walk(UD))
    print(f"dist/ bygget: {antal} filer — klar til upload (UDEN indkøbspriser i klartekst)")


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

        # Hero-sektion: egen overskrift, tekst og brand-chip pr. kategori
        html = html.replace(
            '<div class="brand-chip">⭐ Hansgrohe · Grohe · Burgbad · Pelipal · Sprinz</div>\n'
            '      <h1>Alt til bad &amp; køkken — <span>tysk kvalitet til danske priser</span></h1>\n'
            '      <p class="lead">Armaturer, badmøbler, brusekabiner, badekar og '
            'køkkenarmaturer fra Tysklands førende producenter. Bestil online — '
            'vi klarer import, fragt og dansk support.</p>',
            f'<div class="brand-chip">⭐ {navn} i tysk kvalitet</div>\n'
            f'      <h1>{navn} — <span>tysk kvalitet til danske priser</span></h1>\n'
            f'      <p class="lead">Se hele udvalget af {navn.lower()} fra Hansgrohe, Grohe, '
            f'Burgbad m.fl. — leveret direkte fra vores tyske lager med fuld producentgaranti.</p>',
        )
        html = html.replace(
            '<a href="#produkter" class="btn btn-accent">Se alle produkter</a>',
            f'<a href="#produkter" class="btn btn-accent">Se alle {navn.lower()}</a>',
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


# ---------------------------------------------------------------------------
#  Krypteret admin (online prisoverblik bag adgangskode)
# ---------------------------------------------------------------------------

def _laes_konkurrenter() -> dict:
    """Læser konkurrentpriserne fra konkurrenter.js (genereret af pristester.py)."""
    if not os.path.exists("konkurrenter.js"):
        return {"genereret": None, "priser": {}}
    with open("konkurrenter.js", encoding="utf-8") as f:
        t = f.read()
    i = t.index("= ") + 2
    return json.loads(t[i:t.rindex(";")])


def _krypter_blob(plain: str, password: str) -> dict:
    """Gzip → AES-256-GCM med nøgle udledt via PBKDF2-HMAC-SHA256. Returnerer base64-felter."""
    import gzip
    import hashlib
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    iters = 250_000
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters, dklen=32)
    pakket = gzip.compress(plain.encode("utf-8"), 9)            # JSON komprimerer kraftigt
    ct = AESGCM(key).encrypt(iv, pakket, None)                  # ciphertext + 16-byte tag
    b = lambda raw: base64.b64encode(raw).decode("ascii")
    return {"salt": b(salt), "iv": b(iv), "ct": b(ct), "iters": iters, "gz": True}


# JavaScript der låser data op i browseren (Web Crypto). Ingen f-streng → ingen { }-konflikt.
_UNLOCK_JS = """
async function _unlock(pw){
  try{
    const dec = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
    const baseKey = await crypto.subtle.importKey(
      "raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveKey"]);
    const key = await crypto.subtle.deriveKey(
      { name:"PBKDF2", salt: dec(ENC.salt), iterations: ENC.iters, hash:"SHA-256" },
      baseKey, { name:"AES-GCM", length:256 }, false, ["decrypt"]);
    const buf = await crypto.subtle.decrypt(
      { name:"AES-GCM", iv: dec(ENC.iv) }, key, dec(ENC.ct));
    let text;
    if (ENC.gz) {
      const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
      text = await new Response(stream).text();
    } else {
      text = new TextDecoder().decode(buf);
    }
    const obj = JSON.parse(text);
    window.SHOP_DATA = obj.shop;
    window.KONKURRENT_DATA = obj.konk;
    return true;
  } catch(e){ return false; }
}
"""

_GATE_HTML = """
<div id="gate" style="position:fixed;inset:0;z-index:9999;background:#0f1722;
     display:flex;align-items:center;justify-content:center;">
  <form id="gateForm" style="background:#1a2533;border:1px solid #2e405a;border-radius:14px;
       padding:30px;width:min(360px,90vw);text-align:center;">
    <div style="font-size:2rem">🔒</div>
    <h2 style="color:#e6edf5;margin:6px 0 4px;font-size:1.2rem">Prisoverblik</h2>
    <p style="color:#8aa0b8;font-size:.85rem;margin-bottom:16px">Indtast adgangskode for at låse op</p>
    <input id="pw" type="password" autofocus autocomplete="current-password"
       style="width:100%;padding:11px 13px;border-radius:9px;border:1px solid #2e405a;
       background:#0f1722;color:#e6edf5;font-size:1rem;font-family:inherit">
    <button style="width:100%;margin-top:12px;padding:11px;border:none;border-radius:9px;
       background:#ff7a1a;color:#fff;font-weight:700;font-size:1rem;cursor:pointer;font-family:inherit">
       Lås op</button>
    <p id="gateErr" style="color:#ff6b6b;font-size:.85rem;margin-top:10px;min-height:1.2em"></p>
  </form>
</div>
"""

_GATE_WIRING_JS = """
document.getElementById("gateForm").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = e.target.querySelector("button");
  const err = document.getElementById("gateErr");
  btn.disabled = true; err.textContent = "Låser op…";
  const ok = await _unlock(document.getElementById("pw").value);
  if(!ok){ err.textContent = "Forkert adgangskode"; btn.disabled = false;
           document.getElementById("pw").select(); return; }
  document.getElementById("gate").remove();
  bootAdmin();
});
"""


def _byg_admin_html(enc: dict) -> str:
    """Laver en selvstændig, krypteret admin-side ud fra admin.html-skabelonen."""
    with open("admin.html", encoding="utf-8") as f:
        html = f.read()

    # Fjern de eksterne data-scripts (data kommer nu fra den krypterede blok)
    html = html.replace('<script src="products.js"></script>\n', "")
    html = html.replace('<script src="konkurrenter.js"></script>\n', "")
    html = html.replace('<script src="products.js"></script>', "")
    html = html.replace('<script src="konkurrenter.js"></script>', "")

    # Udtræk hovedscriptet (det sidste <script> … </script>)
    start = html.rindex("<script>")
    slut = html.index("</script>", start)
    admin_js = html[start + len("<script>"):slut]

    # Byg bootstrap: ENC-data + oplåsning + admin-kode pakket i bootAdmin()
    boot = (
        "<script>\n"
        "const ENC = " + json.dumps(enc) + ";\n"
        + _UNLOCK_JS
        + "\nfunction bootAdmin(){\n" + admin_js + "\n}\n"
        + _GATE_WIRING_JS
        + "</script>"
    )

    html = html[:start] + boot + html[slut + len("</script>"):]
    html = html.replace("<body>", "<body>\n" + _GATE_HTML, 1)
    return html


def byg_admin(fuld_data: dict) -> None:
    """Bygger dist/admin.html som KRYPTERET online-prisoverblik.

    • Med ADMIN_PASSWORD + indkøbspriser (eur): krypter på ny og gem en genbrugskopi
      (admin_enc.html), som kan committes — sikker i offentligt repo, da den er krypteret.
    • Uden: genbrug en tidligere committet admin_enc.html, så frontend-deploys bevarer siden.
    """
    password = os.environ.get("ADMIN_PASSWORD")
    har_eur = any("eur" in p for p in fuld_data.get("produkter", []))

    if password and har_eur and os.path.exists("admin.html"):
        # Kun de felter admin faktisk bruger — holder siden let (vigtigt på mobil)
        felter = ("id", "navn", "maerke", "cat", "billede", "url", "eur", "pris")
        slim = {
            "genereret": fuld_data.get("genereret"),
            "kategorier": fuld_data.get("kategorier", {}),
            "produkter": [{k: p.get(k) for k in felter} for p in fuld_data["produkter"]],
        }
        nyttelast = json.dumps(
            {"shop": slim, "konk": _laes_konkurrenter()},
            ensure_ascii=False, separators=(",", ":"),
        )
        try:
            enc = _krypter_blob(nyttelast, password)
        except ImportError:
            print("  ! 'cryptography' mangler — kør: pip install cryptography (admin sprunget over)")
            return
        side = _byg_admin_html(enc)
        with open(os.path.join(UD, "admin.html"), "w", encoding="utf-8") as f:
            f.write(side)
        with open(ADMIN_ENC_FIL, "w", encoding="utf-8") as f:   # committes til genbrug
            f.write(side)
        print(f"  admin.html: krypteret online-version bygget ({len(enc['ct'])//1024} KB data)")
    elif os.path.exists(ADMIN_ENC_FIL):
        shutil.copy2(ADMIN_ENC_FIL, os.path.join(UD, "admin.html"))
        print("  admin.html: genbrugte tidligere krypteret version")
    else:
        print("  admin.html sprunget over (ingen ADMIN_PASSWORD/eur og ingen tidligere version)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
