@echo off
cd /d "%~dp0"
echo Quran Bot install ho raha hai...
where py >/dev/null 2>/dev/null && (set PY=py -3) || (set PY=python)
%PY% --version >/dev/null 2>/dev/null || (
  echo Python nahi mila. https://www.python.org/downloads/ se Python 3.11 ya naya install karein
  echo Install karte waqt "Add python.exe to PATH" par tick lagayein, phir dobara chalayein.
  pause
  exit /b 1
)
%PY% -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Install mein masla aaya. Upar ka error dekhein.
  pause
  exit /b 1
)
echo.
echo Install mukammal. Ab start_bot.bat chalayein.
pause
