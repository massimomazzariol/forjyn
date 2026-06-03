@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found.
  echo Run setup_windows.bat first:
  echo.
  echo   setup_windows.bat
  exit /b 1
)

echo Running ForJyn unit tests...
".venv\Scripts\python.exe" -m unittest discover -s tests
if errorlevel 1 exit /b 1

echo Running py_compile on ForJyn tools...
".venv\Scripts\python.exe" -m py_compile tools\forjyn_workbench.py tools\forjyn_workbench_gui.py tools\forjyn_reference_generator.py tools\forjyn_paths.py
if errorlevel 1 exit /b 1

echo ForJyn tests passed.
