# -*- coding: utf-8 -*-
"""
efterbehandl.py — Efterbehandler products.js:
  1. Oversætter produktnavne til dansk (original gemmes i navnDE)
  2. Tilføjer fragtklasse (pakke/tung/fragtmand)
  3. Komprimerer filen (fjerner tomme felter og overflødig formatering)

Kør efter en katalog-synkronisering. Kan køres flere gange uden skade.
"""
import json
import re
import sys

from fordansk import fordansk, fragtklasse

# Afløb, afløbsrender, gulvrender og tilhørende dele havner fejlagtigt under
# "Brusekar" (de skrabes fra rockyshops duschwannen-side). Flyt dem til en
# egen kategori, så Brusekar kun rummer rigtige brusekar.
AFLOEB_RE = re.compile(
    r"afløb|ablauf|rinne|rende|cera(line|wall|floor)|drain|tempoplex|"
    r"schallschutz|abdeckung|gehäuse|dallflex|drainprofile|ablaufgarnitur|"
    r"geruchsverschluss|gulvrende|gulvafløb",
    re.I,
)


def rekategoriser(data: dict) -> None:
    """Flytter afløbsvarer fra 'brusekar' til en ny kategori 'afloeb'."""
    flyttet = 0
    for p in data["produkter"]:
        if p.get("cat") != "brusekar":
            continue
        navn = (p.get("navnDE") or "") + " " + (p.get("navn") or "")
        if AFLOEB_RE.search(navn):
            p["cat"] = "afloeb"
            flyttet += 1
    if not flyttet:
        return
    # Indsæt ny kategori lige efter 'brusekar' i visningsrækkefølgen
    ny = {}
    for k, v in data.get("kategorier", {}).items():
        ny[k] = v
        if k == "brusekar":
            ny["afloeb"] = "Afløb & render"
    ny.setdefault("afloeb", "Afløb & render")
    data["kategorier"] = ny
    print(f"Rekategoriseret: {flyttet} afløbsvarer flyttet fra Brusekar -> Afløb & render")


# Lavt-efterspurgte varegrupper i DK (bidet, urinal) ryddes op: fjern de fleste,
# behold kun de N mest populære "hovedprodukter" (skåle/vandhaner/sæt).
#   match = produktet hører til gruppen
#   ikke  = generiske flerbrugs-dele der ikke er gruppen (fx fælles patron)
#   del   = dele/tilbehør der ikke må beholdes som "populært" (kun hovedprodukter)
FAMILIER = [
    ("Bidet", 3,
     re.compile(r"wandbidet|standbidet|wand-?bidet|stand-?bidet|bidetarmatur|"
                r"bidetbatt|bidetmischer|bidetsiphon|bidetventil|bidette|\bbidet\b", re.I),
     re.compile(r"køkken|kartusche|adapter", re.I),
     re.compile(r"siphon|stopfen|zugstange|vandlås|ventil|schallschutz", re.I)),
    ("Urinal", 5,
     re.compile(r"urinal", re.I),
     re.compile(r"køkken|kartusche|adapter", re.I),
     re.compile(r"schallschutz|befestigung|trennwand|druckspüler|spülrohr|"
                r"ersatzdeckel|nur deckel|siphon|sifon|membran", re.I)),
]


def ryd_familier(data: dict) -> None:
    """Fjerner de fleste varer i lavt-efterspurgte grupper (bidet, urinal),
    men beholder de mest populære hovedprodukter."""
    def n(p):
        return (p.get("navnDE") or "") + " " + (p.get("navn") or "")
    fjern_alle = set()
    for navn, behold_n, match_re, ikke_re, del_re in FAMILIER:
        gruppe = [p for p in data["produkter"]
                  if match_re.search(n(p)) and not ikke_re.search(n(p))]
        if not gruppe:
            continue
        behold_kand = [p for p in gruppe if not del_re.search(n(p))]
        behold = {id(p) for p in sorted(behold_kand, key=lambda x: x.get("pop", 99999))[:behold_n]}
        fjernes = {id(p) for p in gruppe if id(p) not in behold}
        fjern_alle |= fjernes
        print(f"{navn}-oprydning: fjernet {len(fjernes)} (beholdt {len(behold)} mest populære)")
    if fjern_alle:
        data["produkter"] = [p for p in data["produkter"] if id(p) not in fjern_alle]


def main() -> None:
    with open("products.js", encoding="utf-8") as f:
        t = f.read()
    i = t.index("const SHOP_DATA = ") + len("const SHOP_DATA = ")
    data = json.loads(t[i:t.rindex(";")])

    import re as _re
    foer_antal = len(data["produkter"])
    data["produkter"] = [p for p in data["produkter"]
                         if not _re.match(r"main\d+", (p.get("navnDE") or p["navn"]).strip(), _re.I)
                         and "diverser" not in (p.get("navnDE") or p["navn"]).lower()]
    if foer_antal != len(data["produkter"]):
        print(f"Fjernet {foer_antal - len(data['produkter'])} pladsholdervarer (main####/diverser)")

    rekategoriser(data)   # flyt afløb ud af Brusekar FØR fragt beregnes
    ryd_familier(data)    # ryd op i bidet/urinal (behold kun de mest populære)

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
