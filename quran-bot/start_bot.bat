@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Pehle install.bat chalayein.
  pause
  exit /b 1
)
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
set PYTHONWARNINGS=ignore
.venv\Scripts\python server.py
pause
