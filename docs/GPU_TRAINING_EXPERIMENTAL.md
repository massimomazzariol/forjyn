# Experimental DirectML Training

DirectML training is an experimental opt-in path for AMD/Windows testing. The stable ForJyn training path remains CPU, and ONNX apply/validation still uses ONNX Runtime DirectML when available in the stable `.venv`.

Do not install these packages into `.venv`. Keep the GPU experiment isolated in `.venv-gpu`.

## Current Status

- Stable default training: CPU.
- Experimental training option: DirectML through `torch-directml`.
- Tested spike environment: Python 3.12, `torch-directml 0.2.5.dev240914`, `torch 2.4.1+cpu`.
- DirectML device name reported by PyTorch: `privateuseone:0`.
- Known warning: Adam may fall back to CPU for `aten::lerp.Scalar_out`.
- Speedup is not guaranteed. The spike micro benchmark was too small to justify changing the default.
- ROCm Windows was evaluated but not integrated for this GPU path.

## Create The Separate Environment

From the repository root:

```powershell
py -3.12 -m venv .venv-gpu
.\.venv-gpu\Scripts\python.exe -m pip install --upgrade pip
.\.venv-gpu\Scripts\python.exe -m pip install torch-directml
```

Install the non-torch ForJyn runtime dependencies without replacing the `torch-directml` PyTorch build:

```powershell
.\.venv-gpu\Scripts\python.exe -m pip install numpy==2.4.6 pillow==12.2.0 onnx==1.21.0 onnxscript==0.7.0 onnxruntime-directml==1.24.4 psutil==7.2.2
```

Do not run `setup_windows.bat` for `.venv-gpu`; that script owns the stable `.venv` setup.

## Verify DirectML

```powershell
.\.venv-gpu\Scripts\python.exe -c "import torch; print(torch.__version__)"
.\.venv-gpu\Scripts\python.exe -c "import torch_directml; print(torch_directml.device())"
.\.venv-gpu\Scripts\python.exe tools\forjyn_workbench_gui.py --check
```

The GUI check should report:

```text
DirectML training experimental: yes
```

If `torch_directml` is missing, ForJyn keeps DirectML training hidden in the GUI and `--device directml` fails with a clear error.

## Run The GUI With DirectML Training

Launch the GUI from the isolated environment:

```powershell
.\.venv-gpu\Scripts\python.exe tools\forjyn_workbench_gui.py
```

Then choose `DirectML experimental` in the training device control. Keep Draft runs short while testing. Outputs still go under ignored `workbench/`.

Backend equivalent:

```powershell
.\.venv-gpu\Scripts\python.exe tools\forjyn_workbench.py run-job --content "C:\path\photo.jpg" --style "C:\path\reference.png" --name "reference" --steps 300 --device directml
```

## Return To The Stable Path

Use the normal stable environment:

```powershell
.\run_forjyn_workbench.bat
```

or:

```powershell
.\.venv\Scripts\python.exe tools\forjyn_workbench_gui.py
```

The stable environment should continue to report CPU training and ONNX Runtime DirectML apply when available.

## Known Limits

- DirectML training is not stable project guidance.
- CPU remains the default.
- Some optimizer operations may fall back to CPU.
- Results and speed can vary by driver, Python version, PyTorch version, image size, and step count.
- Long benchmarks should be run only as a separate task with a fixed dataset and clear timing method.
