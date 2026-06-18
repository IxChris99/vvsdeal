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


# Underkategorier (p["type"]) udledt fra produktnavnet pr. kategori. Første
# regel der matcher vinder, så stil de mest specifikke øverst. Uden match
# -> "Øvrige". Bruges både til type-dropdown og klikbare chips på forsiden.
_SUBKAT_RAW = {
    "armaturer": [
        ("Termostater", r"thermostat|termostat"),
        ("Brusersæt & stænger", r"brauseset|brusers|brausestange|brusestang|showerpipe|unica|wallbar"),
        ("Hovedbrusere", r"kopfbrause|hovedbruser|overhead|raindance|rainshower|regnbruser|tellerkopf"),
        ("Håndbrusere", r"handbrause|håndbruser|porter|ausziehbrause|schulterbrause"),
        ("Brusearmaturer", r"brausearmatur|brusearmatur|brausemischer|brusebatteri|brausethermostat|brausebatt|dusch"),
        ("Køkkenarmaturer", r"küchen|køkken|spültisch|spueltisch"),
        ("Håndvaskarmaturer", r"waschtisch|håndvask|\bwt-|waschbecken|einlochbatterie|einhebel|sitzwaschbecken|bidet"),
        ("Kararmaturer", r"wannen|kararmatur|karbatteri|bademischer|wannenrand"),
        ("Indbygningsdele", r"ibox|grundkörper|grundkoerper|unterputz|indbygning|einbau"),
    ],
    "keramik": [
        ("Toiletter", r"\bwc\b|toilet|klosett|tiefspül|aquaclean|dusch-?wc|stand-?wc|wand-?wc|closet"),
        ("Cisterner & betjening", r"spülkasten|cisterne|spülrohr|betätig|drücker|trykplade|bedienpanel|wandbedien|drückerplatte"),
        ("Urinaler", r"urinal"),
        ("Bidet", r"bidet"),
        ("Håndvaske", r"waschtisch|waschbecken|håndvask|aufsatz|handwaschbecken|møbelvask|møbelhåndvask"),
    ],
    "badmoebler": [
        ("Spejlskabe", r"spiegelschrank|spejlskab"),
        ("Spejle & belysning", r"spiegel|spejl|beleucht|spejllys"),
        ("Vaskeskabe & møbelsæt", r"waschtischunterschrank|waschplatz|vaskeskab|badmöbel|møbelsæt|waschtisch-set|set\b"),
        ("Underskabe", r"unterschrank|underskab"),
        ("Høj- & midtskabe", r"hochschrank|højskab|mittelschrank|midtskab|seitenschrank|sideskab"),
    ],
    "badekar": [
        ("Fritstående badekar", r"freistehend|fritstående"),
        ("Hjørnebadekar", r"\beck|hjørne"),
        ("Whirlpool & spa", r"whirlpool|\bspa\b"),
        ("Indbygningsbadekar", r"einbau|indbygning|rechteck|rektangul|raumspar|body"),
    ],
    "afloeb": [
        ("Afløbsrender", r"rinne|rende|cera(line|wall|floor)|drainline|drainprofile|designrost|duschrinne|duschprofil"),
        ("Gulvafløb", r"bodenablauf|gulvafløb|punktafløb|bodeneinlauf|wandablauf"),
        ("Sifoner & vandlåse", r"siphon|sifon|geruchsverschluss|vandlås|raumspar"),
        ("Afløbsgarniturer", r"ablaufgarnitur|afløbsgarniture|ablaufventil|tempoplex|push-open|ablaufgeh|ablaufset"),
    ],
    "brusekabiner": [
        ("Brusedøre", r"tür|\bdør|drehtür|schiebetür|pendeltür|nische|gleittür"),
        ("Brusevægge & walk-in", r"\bwand|væg|seitenwand|walk-?in|seitenteil|freistehend"),
        ("Hjørnebrusere", r"\beck|hjørne|runddusche|viertelkreis"),
    ],
    "accessoires": [
        ("Toiletbørster", r"bürstengarnitur|toilettenbürste|toiletbørste|wc-bürste|wc-garnitur|bürstenhalter"),
        ("Toiletrulleholdere", r"papierhalter|rollenhalter|toiletrulle|papirholder|reservepapier|toilettenpapier"),
        ("Håndklædeholdere", r"handtuch|håndklæde|handdoek"),
        ("Knager & kroge", r"haken|knage|krog"),
        ("Sæbe & dispensere", r"seifenspender|seifenschale|sæbe|seife|lotionspender"),
        ("Greb & støttehåndtag", r"haltegriff|støttegreb|stützgriff"),
        ("Hylder & kurve", r"ablage|\bkorb|hylde|glasablage|duschkorb|reling"),
        ("Spejle", r"spiegel|spejl"),
    ],
    "koekkenarmatur": [
        ("Udtræksarmaturer", r"ausziehbar|udtræk|pull-?out|ausziehbrause|ausziehauslauf|udtræksbruser"),
        ("Med brusefunktion", r"brause|spray|bruse|dual"),
        ("Høje tudarmaturer", r"hoher auslauf|profi|professional|gastro|semi-?pro"),
    ],
}
SUBKAT = {cat: [(navn, re.compile(pat, re.I)) for navn, pat in regler]
          for cat, regler in _SUBKAT_RAW.items()}


def tildel_type(data: dict) -> None:
    """Sætter p['type'] (underkategori) udledt fra navnet, pr. kategori."""
    for p in data["produkter"]:
        regler = SUBKAT.get(p.get("cat"))
        nm = ((p.get("navnDE") or "") + " " + (p.get("navn") or ""))
        typ = ""
        if regler:
            for navn, rx in regler:
                if rx.search(nm):
                    typ = navn
                    break
            if not typ:
                typ = "Øvrige"
        p["type"] = typ


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
    tildel_type(data)     # udled underkategori (type) pr. vare

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
