@echo off
setlocal
cd /d "%~dp0"
echo ====== Quran Bot install ======
echo.
if not exist requirements.txt (
  echo ZIP file ke andar se chala rahe hain. Pehle ZIP par Right-click karke "Extract All" karein,
  echo phir nikle hue folder ke andar quran-bot\install.bat chalayein.
  pause
  exit /b 1
)

rem Whisper ki libraries Python 3.9 se 3.13 tak chalti hain; 3.12 sab se behtar
set "PY="
for %%V in (3.12 3.11 3.13 3.10) do (
  if not defined PY py -%%V -c "pass" >nul 2>nul && set "PY=py -%%V"
)
if not defined PY python -c "pass" >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python nahi mila.
  echo https://www.python.org/downloads/release/python-3129/ se "Windows installer (64-bit)" download karein.
  echo Install ke pehle screen par neeche "Add python.exe to PATH" par tick lagayein.
  pause
  exit /b 1
)
echo Python mila:
%PY% --version
%PY% -c "import sys; sys.exit(0 if (3,9) <= sys.version_info[:2] <= (3,13) else 1)"
if errorlevel 1 (
  echo.
  echo Yeh Python version Whisper ke saath nahi chalta. Python 3.12 bhi install karein:
  echo https://www.python.org/downloads/release/python-3129/  ^(Windows installer 64-bit^)
  echo Purana Python hatane ki zaroorat nahi. Install ke baad yeh file dobara chalayein.
  pause
  exit /b 1
)

if exist .venv rmdir /s /q .venv
echo.
echo Alag mahol ^(.venv^) bana raha hoon...
%PY% -m venv .venv
if errorlevel 1 (
  echo .venv nahi bana. Upar ka error ka screenshot bhejein.
  pause
  exit /b 1
)
.venv\Scripts\python -m pip install --upgrade pip
echo.
echo Libraries install ho rahi hain ^(5-10 minute, internet chahiye^)...
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install mein masla aaya. Is window ke aakhri hisse ka screenshot bhejein.
  pause
  exit /b 1
)
.venv\Scripts\python -c "import faster_whisper, pypdfium2, scipy, rapidfuzz; print(\"Sab libraries theek hain.\")"
echo.
echo Install mukammal. Ab start_bot.bat chalayein.
pause
