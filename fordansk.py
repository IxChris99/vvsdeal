# -*- coding: utf-8 -*-
"""
fordansk.py — Fælles modul: tysk→dansk oversættelse af produktnavne
og fragtklasse-tildeling. Bruges af sync_rocky.py og efterbehandl.py.
"""
import re

# Tysk → dansk. Længste udtryk først, så sammensatte ord rammes før delord.
# Oversættelsen er ordbogsbaseret — VVS-fagtermer er forudsigelige nok til,
# at det fanger langt det meste. Originalnavnet gemmes altid i navnDE.
ORDBOG = [
    ("Ab- und Überlaufgarnitur", "af- og overløbsgarniture"),
    ("Ab-u.Überlaufgarnitur", "af- og overløbsgarniture"),
    ("Waschtischunterschrank", "vaskeskab"),
    ("Aufsatzwaschtisch", "bowlevask"),
    ("Handwaschbecken", "lille håndvask"),
    ("Waschtischmischer", "håndvaskarmatur"),
    ("Waschtischarmatur", "håndvaskarmatur"),
    ("Spültischmischer", "køkkenarmatur"),
    ("Küchenmischer", "køkkenarmatur"),
    ("Küchenarmatur", "køkkenarmatur"),
    ("Einhebelmischer", "etgrebsarmatur"),
    ("Wannenmischer", "kararmatur"),
    ("Wannenarmatur", "kararmatur"),
    ("Brausenmischer", "brusearmatur"),
    ("Brausemischer", "brusearmatur"),
    ("Brausearmatur", "brusearmatur"),
    ("Bidetmischer", "bidetarmatur"),
    ("Brausenschlauch", "bruseslange"),
    ("Brauseschlauch", "bruseslange"),
    ("Brausestange", "bruserstang"),
    ("Brausenstange", "bruserstang"),
    ("Wandstange", "vægstang"),
    ("Brausenhalter", "bruserholder"),
    ("Brausehalter", "bruserholder"),
    ("Brausenset", "brusersæt"),
    ("Brauseset", "brusersæt"),
    ("Kopfbrause", "hovedbruser"),
    ("Handbrause", "håndbruser"),
    ("Duschsystem", "brusesystem"),
    ("Duschrinne", "afløbsrende"),
    ("Duschkabine", "brusekabine"),
    ("Duschabtrennung", "bruseafskærmning"),
    ("Duschwanne", "brusekar"),
    ("Duschkorb", "brusekurv"),
    ("Duschtür", "brusedør"),
    ("Eckbadewanne", "hjørnebadekar"),
    ("Raumsparwanne", "pladsbesparende badekar"),
    ("Badewanne", "badekar"),
    ("Wannenträger", "karbærer"),
    ("Wanneneinlauf", "kartilløb"),
    ("Tiefspül-WC", "toilet"),
    ("Wand-WC", "væghængt toilet"),
    ("Stand-WC", "gulvstående toilet"),
    ("WC-Sitz", "WC-sæde"),
    ("spülrandlos", "uden skyllerand"),
    ("wandhängend", "væghængt"),
    ("bodenstehend", "gulvstående"),
    ("freistehend", "fritstående"),
    ("Waschbecken", "håndvask"),
    ("Waschtisch", "håndvask"),
    ("Spiegelschrank", "spejlskab"),
    ("Lichtspiegel", "spejl med lys"),
    ("Spiegel", "spejl"),
    ("Unterschrank", "underskab"),
    ("Hochschrank", "højskab"),
    ("Badmöbel-Set", "badmøbelsæt"),
    ("Badmöbel", "badmøbler"),
    ("Wandablage", "væghylde"),
    ("Toilettenpapierhalter", "toiletrulleholder"),
    ("Reservepapierhalter", "reserverulleholder"),
    ("Vorratsbehälter", "beholder"),
    ("Kompaktschichtstoff", "kompaktlaminat"),
    ("Schichtstoff", "laminat"),
    ("Glasabzieher", "glasskraber"),
    ("Duschablage", "brusehylde"),
    ("Seifenhalter", "sæbeholder"),
    ("Seifenkorb", "sæbekurv"),
    ("Glashalter", "glasholder"),
    ("Becherhalter", "krusholder"),
    ("Handtuchring", "håndklædering"),
    ("Doppelhaken", "dobbeltkrog"),
    ("Wandhaken", "vægkrog"),
    ("Haken", "krog"),
    ("Halterung", "holder"),
    ("Konsole", "konsol"),
    ("Ablage", "hylde"),
    ("Eckregal", "hjørnereol"),
    ("Ersatzglas", "reserveglas"),
    ("Ersatzrolle", "reserverulle"),
    ("Bürste", "børste"),
    ("Stange", "stang"),
    ("Spülkasten", "cisterne"),
    ("Betätigungsplatte", "betjeningsplade"),
    ("Drückerplatte", "betjeningsplade"),
    ("Vorwandelement", "indbygningselement"),
    ("Wandmontage", "vægmontering"),
    ("Bodenmontage", "gulvmontering"),
    ("Deckenmontage", "loftmontering"),
    ("Einbau", "indbygget"),
    ("abnehmbar", "aftagelig"),
    ("hoher", "høj"),
    ("weiss", "hvid"),
    ("Handtuchhalter", "håndklædeholder"),
    ("Badetuchhalter", "badehåndklædeholder"),
    ("Papierrollenhalter", "toiletrulleholder"),
    ("Papierhalter", "toiletrulleholder"),
    ("WC-Bürstengarnitur", "toiletbørstesæt"),
    ("Bürstengarnitur", "toiletbørstesæt"),
    ("Seifenspender", "sæbedispenser"),
    ("Zahnputzbecher", "tandkrus"),
    ("Fertigmontageset", "færdigsæt"),
    ("Fertigset", "færdigsæt"),
    ("Grundkörper", "indbygningsdel"),
    ("Grundset", "indbygningssæt"),
    ("Unterputz", "til indbygning"),
    ("Aufputz", "til synlig montering"),
    ("Verlängerungsset", "forlængersæt"),
    ("Verlängerung", "forlænger"),
    ("Eckventil", "hjørneventil"),
    ("Ablaufgarnitur", "afløbsgarniture"),
    ("Ablaufventil", "afløbsventil"),
    ("Überlauf", "overløb"),
    ("Schlauchanschluss", "slangetilslutning"),
    ("Schlauchanschluß", "slangetilslutning"),
    ("Schnellkupplung", "lynkobling"),
    ("Thermostatgriff", "termostatgreb"),
    ("Thermostat", "termostat"),
    ("Sicherheitsglas", "sikkerhedsglas"),
    ("Klarglas", "klart glas"),
    ("Echtglas", "ægte glas"),
    ("Drehtür", "drejedør"),
    ("Schiebetür", "skydedør"),
    ("Pendeltür", "pendeldør"),
    ("Seitenwand", "sidevæg"),
    ("Seitenteil", "sidedel"),
    ("Ersatzteil", "reservedel"),
    ("Zubehör", "tilbehør"),
    ("Siphon", "vandlås"),
    ("Sifon", "vandlås"),
    ("höhenverstellbar", "højdejusterbar"),
    ("Einhebel", "etgrebs"),
    # farver & materialer
    ("mattschwarz", "mat sort"),
    ("matt schwarz", "mat sort"),
    ("schwarz matt", "mat sort"),
    ("mattweiß", "mat hvid"),
    ("matt weiß", "mat hvid"),
    ("weiß matt", "mat hvid"),
    ("alpinweiß", "alpinhvid"),
    ("verchromt", "forkromet"),
    ("Edelstahl", "rustfrit stål"),
    ("gebürstet", "børstet"),
    ("poliert", "poleret"),
    ("glänzend", "blank"),
    ("schwarz", "sort"),
    ("chrom", "krom"),
    ("weiß", "hvid"),
    ("gold", "guld"),
    ("grau", "grå"),
    ("anthrazit", "antracit"),
    ("Nussbaum", "valnød"),
    ("Eiche", "eg"),
    # småord (med ordgrænser, så de ikke rammer inde i ord)
    ("rechts", "højre"),
    ("links", "venstre"),
    ("ohne", "uden"),
    ("mit", "med"),
    ("für", "til"),
    ("und", "og"),
]
ORDBOG.sort(key=lambda x: -len(x[0]))

_REGLER = [(re.compile(r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(de) + r"(?![a-zäöüß])",
                       re.IGNORECASE), da) for de, da in ORDBOG]


def _bevar_stort(kilde: str, erstatning: str) -> str:
    if kilde[:1].isupper() and erstatning[:1].islower():
        return erstatning[0].upper() + erstatning[1:]
    return erstatning


def fordansk(navn: str) -> str:
    """Oversætter et tysk produktnavn til dansk (ordbogsbaseret)."""
    ud = navn
    for regel, da in _REGLER:
        ud = regel.sub(lambda m: _bevar_stort(m.group(0), da), ud)
    return re.sub(r"\s+", " ", ud).strip()


# ---------- Fragtklasser ----------
# pakke      = alm. GLS-pakke (armaturer, tilbehør, reservedele)
# tung       = tung pakke (toiletter, håndvaske, keramik)
# fragtmand  = palle-/speditionsgods (badekar, brusekar, kabiner, møbler)
PAKKE_NOEGLER = ("wc-sitz", "wc-sæde", "sitzbankauflage", "deckel",
                 "befestigung", "dämpfer", "scharnier")


def fragtklasse(cat: str, navn: str) -> str:
    n = navn.lower()
    if cat in ("badekar", "brusekar", "brusekabiner"):
        return "fragtmand"
    if cat == "badmoebler":
        return "pakke" if any(k in n for k in ("halter", "holder", "hylde", "ablage", "regal")) else "fragtmand"
    if cat == "keramik":
        return "pakke" if any(k in n for k in PAKKE_NOEGLER) else "tung"
    return "pakke"
