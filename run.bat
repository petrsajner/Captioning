@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Preparing the Caption Studio environment...
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Install Python 3.11 to run from source. The EXE package includes Python.
    pause
    exit /b 1
  )
)
rem Reinstall whenever the validated runtime pins change.
fc /b requirements-lock.txt .venv\caption-ready >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
  if errorlevel 1 (
    pause
    exit /b 1
  )
  copy /y requirements-lock.txt .venv\caption-ready >nul
)
start "" ".venv\Scripts\pythonw.exe" "app.py"
