@echo off
REM Opdaterer produkter og priser fra rockyshop.de
REM Koer denne fil manuelt - eller saet den paa skema i Windows Opgavestyring:
REM   schtasks /create /tn "RockySync" /tr "C:\Users\chj\Desktop\VVS\opdater_priser.bat" /sc daily /st 06:00
cd /d "%~dp0"
py sync_rocky.py
echo.
echo Faerdig! Tryk paa en tast for at lukke.
pause >nul
