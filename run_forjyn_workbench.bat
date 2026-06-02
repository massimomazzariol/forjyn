@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found. Please create/install .venv first.
  echo.
  echo   python -m venv .venv
  echo   .venv\Scripts\python -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" "tools\forjyn_workbench_gui.py"
if errorlevel 1 (
  echo.
  echo ForJyn Workbench GUI failed to start.
  echo.
  pause
  exit /b 1
)
