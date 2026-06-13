@echo off
REM ============================================================
REM  byg_admin.bat - bygger den KRYPTEREDE online-admin lokalt.
REM
REM  Brug den til at offentliggoere prisoverblikket med det samme
REM  (uden at vente paa den natlige GitHub-koersel).
REM
REM  1) Indtast den SAMME adgangskode som du gemmer i GitHub
REM     (Settings -> Secrets -> Actions -> ADMIN_PASSWORD).
REM  2) Filen "admin_enc.html" genereres - commit + push den,
REM     og koer "Hurtig deploy" under Actions-fanen.
REM ============================================================
cd /d "%~dp0"
set "ADMIN_PASSWORD="
set /p ADMIN_PASSWORD=Indtast admin-adgangskode (samme som i GitHub):
if "%ADMIN_PASSWORD%"=="" (
  echo Ingen adgangskode indtastet - afbryder.
  pause
  exit /b 1
)
py byg_deploy.py
set "ADMIN_PASSWORD="
echo.
echo ============================================================
echo  Faerdig. "admin_enc.html" er bygget (krypteret med din kode).
echo  Naeste skridt: commit + push den, og koer "Hurtig deploy".
echo ============================================================
pause
