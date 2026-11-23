@echo off
title Gemeentebelangen Instagram-generator
cd /d "%~dp0"

rem --- Wachtwoord voor het formulier (leeg laten = geen wachtwoord) ---
set GB_WACHTWOORD=

rem --- Python zoeken ---
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python is niet gevonden.
  echo  Installeer Python via https://www.python.org/downloads/
  echo  en vink tijdens de installatie "Add python.exe to PATH" aan.
  echo.
  pause
  exit /b 1
)

rem --- Eerste keer: omgeving maken en onderdelen installeren ---
if not exist "venv\Scripts\python.exe" (
  echo Eerste keer opstarten: onderdelen worden geinstalleerd, even geduld...
  %PY% -m venv venv
  if errorlevel 1 goto fout
  "venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  "venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fout
)

rem --- Browser openen en starten ---
start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:8080"
"venv\Scripts\python.exe" start.py
pause
exit /b 0

:fout
echo.
echo  Er ging iets mis bij het installeren. Controleer je internetverbinding
echo  en probeer het opnieuw. Verwijder eventueel eerst de map "venv".
pause
exit /b 1
