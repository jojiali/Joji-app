@echo off
setlocal
cd /d "%~dp0"
echo ====== Quran Bot install ======
echo Install ho raha hai, 5-10 minute lag sakte hain. Yeh window band na karein...
call :main > install_log.txt 2>&1
if errorlevel 1 (
  echo.
  echo Install nahi hua. Wajah Notepad mein khul rahi hai ^(install_log.txt^).
  start notepad "%~dp0install_log.txt"
) else (
  echo.
  echo Install mukammal! Ab start_bot.bat chalayein.
)
pause
exit /b

:main
if not exist requirements.txt (
  echo MASLA: ZIP file ke andar se chala rahe hain. Pehle ZIP par Right-click karke "Extract All" karein,
  echo phir nikle hue folder ke andar quran-bot\install.bat chalayein.
  exit /b 1
)

rem Whisper ki libraries Python 3.9 se 3.13 tak chalti hain; 3.12 sab se behtar
set "PY="
for %%V in (3.12 3.11 3.13 3.10) do (
  if not defined PY py -%%V -c "pass" >nul 2>nul && set "PY=py -%%V"
)
rem Python installed without "Add to PATH" still sits in its default folder
for %%V in (312 311 313 310) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe""
  if not defined PY if exist "%ProgramFiles%\Python%%V\python.exe" set "PY="%ProgramFiles%\Python%%V\python.exe""
)
if not defined PY python -c "pass" >nul 2>nul && set "PY=python"
if not defined PY (
  echo MASLA: Python 3.10-3.13 nahi mila.
  echo Is computer par yeh Python mile:
  py -0p
  where python
  dir /b "%LOCALAPPDATA%\Programs\Python"
  echo.
  echo https://www.python.org/downloads/release/python-3129/ se "Windows installer (64-bit)" download karein.
  echo Install ke pehle screen par neeche "Add python.exe to PATH" par tick lagayein.
  exit /b 1
)
echo Python mila: %PY%
%PY% --version
%PY% -c "import sys; sys.exit(0 if (3,9) <= sys.version_info[:2] <= (3,13) else 1)"
if errorlevel 1 (
  echo MASLA: Yeh Python version Whisper ke saath nahi chalta. Python 3.12 bhi install karein:
  echo https://www.python.org/downloads/release/python-3129/  ^(Windows installer 64-bit^)
  echo Purana Python hatane ki zaroorat nahi. Install ke baad install.bat dobara chalayein.
  exit /b 1
)

if exist .venv rmdir /s /q .venv
%PY% -m venv .venv
if errorlevel 1 (
  echo MASLA: .venv nahi bana.
  exit /b 1
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo MASLA: libraries install nahi huin. Upar ka error dekhein.
  exit /b 1
)
.venv\Scripts\python -c "import faster_whisper, pypdfium2, scipy, rapidfuzz; print(\"Sab libraries theek hain.\")"
if errorlevel 1 exit /b 1
exit /b 0
