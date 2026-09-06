@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Pripravuji samostatne prostredi Caption Studio...
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Pro spusteni ze zdroju nainstalujte Python 3.11. Balicek EXE jej obsahuje.
    pause
    exit /b 1
  )
)
if not exist ".venv\caption-ready" (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (
    pause
    exit /b 1
  )
  echo ready>.venv\caption-ready
)
start "" ".venv\Scripts\pythonw.exe" "app.py"
