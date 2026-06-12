# VVSdeal — webshop & automatik

Dropshipping-webshop for bad og køkken. Produkter hentes fra rockyshop.de,
oversættes til dansk, prissættes (10 % under danske konkurrenter, aldrig
under Rocky + 12 %) og vises på en statisk side. Alt kører automatisk i
GitHub Actions hver nat og deployes til **www.vvsdeal.dk**.

## Opsætning på en ny PC

1. **Installer forudsætninger** (hvis ikke til stede):
   - [Git](https://git-scm.com/download/win)
   - [Python 3.12+](https://www.python.org/downloads/) — kald den med `py`
   - `py -m pip install pytrends` (kun nødvendigt for trends_sync.py)

2. **Klon repoet:**
   ```
   git clone https://github.com/IxChris99/vvsdeal.git
   cd vvsdeal
   ```

3. **Hent produktkataloget** (ligger ikke i git — indeholder indkøbspriser):
   ```
   py hent_offentligt_katalog.py     # hurtigt: offentlig udgave uden indkøbspriser
   ```
   eller, for den fulde version med avance-data (tager 1-2 timer):
   ```
   py sync_rocky.py
   ```

4. **Se siden lokalt:**
   ```
   py -m http.server 8742
   ```
   Åbn så http://localhost:8742/index.html (shoppen) eller
   http://localhost:8742/admin.html (prisoverblik — kun lokalt!).

## Filoversigt

| Fil | Rolle |
|-----|-------|
| `index.html` | Selve webshoppen (statisk) |
| `admin.html` | Internt prisoverblik (Rocky vs. dig vs. konkurrenter) — ALDRIG offentlig |
| `products.js` | Produktdata (gitignored — indeholder eur-indkøbspriser) |
| `sync_rocky.py` | Henter hele kataloget fra rockyshop.de |
| `efterbehandl.py` | Danske navne, fragtklasser, komprimering |
| `pristester.py` | Tjekker priser hos danske konkurrenter |
| `genberegn_priser.py` | Genberegner priser efter reglen |
| `trends_sync.py` | Danske Google Trends → trends.js |
| `lav_seo_sider.py` | Genererer SEO-produktsider + sitemap |
| `byg_deploy.py` | Bygger dist/ UDEN indkøbspriser til offentlig server |
| `fordansk.py` | Tysk→dansk ordbog + fragtklasser (delt modul) |

## Automatik

- **GitHub Actions** (`.github/workflows/nat.yml`) kører hele kæden hver nat
  og deployer til GitHub Pages → www.vvsdeal.dk. Kører i skyen — PC kan være slukket.
- `.github/workflows/trends.yml` opdaterer Google Trends ugentligt.
- Lokale `.bat`-filer + Windows Opgavestyring gør det samme, hvis man vil køre lokalt.

## Prisregel (vigtig)

`ny pris = 10 % under billigste danske konkurrent`, men **aldrig** under
`gulv = Rocky EUR × 7,46 × 1,12`. Gulvet vinder altid.
