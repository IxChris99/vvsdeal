# -*- coding: utf-8 -*-
"""
genberegn_priser.py — Genberegner salgspriser OFFLINE ud fra de
konkurrentpriser, der allerede ligger i konkurrenter.js (ingen nye opslag).

Regel:  ny pris = UNDERBUD x billigste danske konkurrent (pænt afrundet)
        MEN ALDRIG under gulvet = Rocky EUR x KURS x AVANCE.

Opdaterer products.js + prisjusteringer.json. Kan køres igen og igen.
"""
import json
import sys

from pristester import (KURS, AVANCE, UNDERBUD, gulv_pris, konkurrent_plausibel,
                        paen_pris_op, paen_pris_ned, indlaes_products_js)


def main() -> None:
    data, praefix, suffiks = indlaes_products_js()
    with open("konkurrenter.js", encoding="utf-8") as f:
        t = f.read()
    i = t.index("const KONKURRENT_DATA = ") + len("const KONKURRENT_DATA = ")
    konk = json.loads(t[i:t.rindex(";")])["priser"]

    try:
        with open("prisjusteringer.json", encoding="utf-8") as f:
            justeringer = json.load(f)
    except FileNotFoundError:
        justeringer = {}

    aendret = laast = under = 0
    for p in data["produkter"]:
        k = konk.get(p["id"])
        if not k or not k.get("billigste"):
            continue
        billigste = float(k["billigste"])
        if not konkurrent_plausibel(p["eur"], billigste):
            continue   # urealistisk høj konkurrentpris (fejl-match) -> spring over
        gulv_paen = paen_pris_op(gulv_pris(p["eur"]))
        maal = paen_pris_ned(billigste * UNDERBUD)
        if maal >= billigste:
            maal = int(billigste) - 1
        ny = max(maal, gulv_paen)
        k["status"] = "OK: under konkurrent" if ny < billigste else "GULV: kan ikke matche"
        if ny < billigste:
            under += 1
        else:
            laast += 1
        if ny != p["pris"]:
            p["pris"] = ny
            justeringer[p["id"]] = ny
            aendret += 1

    with open("products.js", "w", encoding="utf-8") as f:
        f.write(praefix)
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(suffiks)
    with open("prisjusteringer.json", "w", encoding="utf-8") as f:
        json.dump(justeringer, f, ensure_ascii=False, indent=1)
    # gem opdaterede statusser i konkurrenter.js
    with open("konkurrenter.js", "w", encoding="utf-8") as f:
        f.write("// Genereret af pristester.py — konkurrentpriser til admin.html.\n")
        f.write("const KONKURRENT_DATA = ")
        json.dump({"genereret": json.loads(t[i:t.rindex(";")])["genereret"], "priser": konk},
                  f, ensure_ascii=False, indent=1)
        f.write(";\n")

    print(f"Regel: {round((1 - UNDERBUD) * 100)}% under billigste konkurrent, gulv = Rocky + {round((AVANCE - 1) * 100)}%")
    print(f"Priser ændret: {aendret}")
    print(f"Du underbyder nu konkurrenten på: {under} varer")
    print(f"Låst på gulvpris (kan ikke matche): {laast} varer")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
