@echo off
REM Starter en lokal server og aabner admin-prisoverblikket i browseren.
REM Luk vinduet for at stoppe serveren igen.
cd /d "%~dp0"
start "" http://localhost:8742/admin.html
py -m http.server 8742
