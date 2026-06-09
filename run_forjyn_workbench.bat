@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist ".venv-gpu\Scripts\python.exe" (
  ".venv-gpu\Scripts\python.exe" -c "import torch_directml; print(torch_directml.device())" >nul 2>nul
  if not errorlevel 1 (
    echo Starting ForJyn with experimental DirectML training runtime.
    set "FORJYN_RUNTIME_MODE=DirectML experimental"
    ".venv-gpu\Scripts\python.exe" "tools\forjyn_workbench_gui.py" %*
    if errorlevel 1 (
      echo ForJyn Workbench GUI failed to start with the experimental DirectML runtime.
      exit /b 1
    )
    exit /b 0
  )
)

echo DirectML training runtime unavailable. Falling back to stable CPU runtime.

if not exist ".venv\Scripts\python.exe" (
  echo No runtime found. Run setup_windows.bat first.
  exit /b 1
)

set "FORJYN_RUNTIME_MODE=Stable CPU"
".venv\Scripts\python.exe" "tools\forjyn_workbench_gui.py" %*
if errorlevel 1 (
  echo ForJyn Workbench GUI failed to start.
  exit /b 1
)
