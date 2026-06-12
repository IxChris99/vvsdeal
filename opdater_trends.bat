@echo off
REM Ugentlig Google Trends-opdatering (soendag nat kl. 01:30)
REM Registreret i Windows Opgavestyring som "VVS-Trends"
cd /d "%~dp0"
echo. >> sync_log.txt
echo ===== TRENDS-KOERSEL: %date% %time% ===== >> sync_log.txt
py trends_sync.py >> sync_log.txt 2>&1
