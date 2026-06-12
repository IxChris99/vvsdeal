@echo off
REM ============================================================
REM  nat_automatik.bat - koeres automatisk hver nat kl. 02:00
REM  (registreret i Windows Opgavestyring som "VVS-NatSync")
REM
REM  Kaeden (alt logges i sync_log.txt):
REM   1. Pristest: 800 varer (nye foerst, derefter aeldst tjekkede)
REM   2. Katalog-sync fra rockyshop.de (genoptagelig)
REM   3. Efterbehandling (danske navne, fragtklasser, komprimering)
REM   4. Genberegn priser (10%% under konkurrent, gulv Rocky+12%%)
REM   5. SEO-produktsider + sitemap
REM ============================================================
cd /d "%~dp0"
echo. >> sync_log.txt
echo ===== NATKOERSEL START: %date% %time% ===== >> sync_log.txt

echo --- 1/5 Pristest --- >> sync_log.txt
py pristester.py --antal 800 --nye --opdater >> sync_log.txt 2>&1

echo --- 2/5 Katalog-sync --- >> sync_log.txt
py sync_rocky.py >> sync_log.txt 2>&1

echo --- 3/5 Efterbehandling --- >> sync_log.txt
py efterbehandl.py >> sync_log.txt 2>&1

echo --- 4/5 Genberegn priser --- >> sync_log.txt
py genberegn_priser.py >> sync_log.txt 2>&1

echo --- 5/5 SEO-sider --- >> sync_log.txt
py lav_seo_sider.py >> sync_log.txt 2>&1

echo ===== NATKOERSEL SLUT: %date% %time% ===== >> sync_log.txt
