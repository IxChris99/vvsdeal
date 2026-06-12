# -*- coding: utf-8 -*-
"""Hurtigt kvalitetstjek af products.js efter fuld synkronisering."""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
t = open("products.js", encoding="utf-8").read()
i = t.index("const SHOP_DATA = ") + len("const SHOP_DATA = ")
d = json.loads(t[i:t.rindex(";")])
ps = d["produkter"]

print("varer i alt:", len(ps))
print("med pop-felt:", sum(1 for p in ps if "pop" in p))
print("med billede:", sum(1 for p in ps if p.get("billede")))
print("på lager:", sum(1 for p in ps if p.get("lager")))
print("med farve:", sum(1 for p in ps if p.get("farve")))
print("trendfarve:", sum(1 for p in ps if p.get("trend")))
print("\npr. kategori:")
for k, n in Counter(p["cat"] for p in ps).most_common():
    print(f"  {d['kategorier'].get(k, k):28} {n:>6}")
print("\ntop-10 mærker:")
for m, n in Counter(p["maerke"] for p in ps).most_common(10):
    print(f"  {m:20} {n:>6}")
print("\nprisspænd:", min(p["pris"] for p in ps), "-", max(p["pris"] for p in ps), "kr.")
