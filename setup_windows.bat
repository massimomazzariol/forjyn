@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "CPU_READY=unavailable"
set "ONNX_DIRECTML=unavailable"
set "GPU_READY=unavailable"

echo ForJyn Windows setup
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python for Windows, then run this setup again.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating stable CPU runtime in .venv...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv.
    exit /b 1
  )
) else (
  echo Stable CPU runtime found in .venv.
)

echo Updating stable runtime pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to update pip in .venv.
  exit /b 1
)

echo Removing standard onnxruntime package if present...
".venv\Scripts\python.exe" -m pip uninstall -y onnxruntime >nul 2>nul

echo Installing stable ForJyn requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install stable requirements.
  exit /b 1
)

set "CPU_READY=ready"
call :check_onnx_directml
if /I not "%ONNX_DIRECTML%"=="available" (
  echo Repairing ONNX Runtime DirectML in stable runtime...
  ".venv\Scripts\python.exe" -m pip install --force-reinstall --no-deps onnxruntime-directml==1.24.4
  if errorlevel 1 (
    echo Failed to install ONNX Runtime DirectML in .venv.
    exit /b 1
  )
  call :check_onnx_directml
)

echo.
echo Checking optional Python 3.12 runtime for experimental DirectML training...
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found. Experimental GPU runtime skipped. CPU runtime remains available.
  goto setup_summary
)

py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 not found. Experimental GPU runtime skipped. CPU runtime remains available.
  goto setup_summary
)

if not exist ".venv-gpu\Scripts\python.exe" (
  echo Creating experimental DirectML training runtime in .venv-gpu...
  py -3.12 -m venv .venv-gpu
  if errorlevel 1 (
    echo Failed to create .venv-gpu. CPU runtime remains available.
    goto setup_summary
  )
) else (
  echo Experimental DirectML runtime found in .venv-gpu.
)

echo Updating experimental runtime pip...
".venv-gpu\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to update pip in .venv-gpu. CPU runtime remains available.
  goto setup_summary
)

echo Installing torch-directml experimental runtime...
".venv-gpu\Scripts\python.exe" -m pip install torch-directml
if errorlevel 1 (
  echo Failed to install torch-directml. CPU runtime remains available.
  goto setup_summary
)

echo Installing non-torch ForJyn dependencies in .venv-gpu...
".venv-gpu\Scripts\python.exe" -m pip install numpy==2.4.6 pillow==12.2.0 onnx==1.21.0 onnxscript==0.7.0 onnxruntime-directml==1.24.4 psutil==7.2.2
if errorlevel 1 (
  echo Failed to install experimental runtime dependencies. CPU runtime remains available.
  goto setup_summary
)

".venv-gpu\Scripts\python.exe" -c "import torch_directml; print(torch_directml.device())" >nul 2>nul
if errorlevel 1 (
  echo torch-directml check failed. CPU runtime remains available.
  goto setup_summary
)

set "GPU_READY=ready"

:setup_summary
echo.
echo ForJyn setup summary
echo Stable CPU runtime: %CPU_READY%
echo ONNX DirectML apply: %ONNX_DIRECTML%
echo Experimental DirectML training runtime: %GPU_READY%
echo Launcher: auto-select DirectML runtime when available, otherwise CPU fallback
echo.
echo Start ForJyn with:
echo   run_forjyn_workbench.bat
exit /b 0

:check_onnx_directml
set "ONNX_DIRECTML=unavailable"
set "FORJYN_ORT_CHECK=%TEMP%\forjyn_ort_%RANDOM%.txt"
".venv\Scripts\python.exe" -c "import onnxruntime as ort; providers=ort.get_available_providers(); print('available' if 'DmlExecutionProvider' in providers or 'DirectMLExecutionProvider' in providers else 'unavailable')" > "%FORJYN_ORT_CHECK%" 2>nul
if not errorlevel 1 (
  set /p ONNX_DIRECTML=<"%FORJYN_ORT_CHECK%"
)
del "%FORJYN_ORT_CHECK%" >nul 2>nul
exit /b 0
