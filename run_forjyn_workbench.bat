@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found.
  echo.
  echo Run setup_windows.bat first:
  echo.
  echo   setup_windows.bat
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
