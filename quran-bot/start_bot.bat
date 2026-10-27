@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Pehle install.bat chalayein.
  pause
  exit /b 1
)
.venv\Scripts\python server.py
pause
