# ForJyn

ForJyn is a local Windows/Python workbench for generating and testing ONNX style-transfer models from reference images. It is experimental, local-first, and designed around a practical loop: choose images, train a PyTorch style model, export ONNX, apply it, and review the result.

## What It Does

- Choose a content photo.
- Choose manual style/reference images or generate procedural references locally.
- Train one PyTorch style model per selected reference.
- Export dynamic height/width, shape-preserving ONNX models.
- Validate and apply ONNX models to the content photo.
- Create review sheets for human screening.

## Current Status

ForJyn is a working local workbench, not a finished filter pack. Outputs still need human visual review, and generated models should be treated as candidates until their references, training settings, validation, and license status are documented.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run_forjyn_workbench.bat
```

In the GUI:

1. Choose a content photo.
2. Choose or generate style/reference images.
3. Select Draft, Normal, or Final quality.
4. Start the job.
5. Review outputs in `ForJyn_Workbench/outputs/`.

## Key Features

- Minimal Tkinter GUI.
- Procedural reference generator.
- Draft/Normal/Final training presets.
- Dynamic H/W ONNX export with shape-preserving output.
- ONNX validation and apply workflow.
- Optional DirectML inference path with CPU fallback.
- JPG, PNG, and WebP support when Pillow supports WebP.
- Review sheet creation for completed outputs.

## Documentation

- [Workbench guide](docs/WORKBENCH.md)
- [Project scope](docs/PROJECT_SCOPE.md)
- [Model policy](docs/MODEL_POLICY.md)
- [Third-party notes](docs/THIRD_PARTY.md)
- [Worklog](docs/WORKLOG.md)

## Artifact Policy

Generated checkpoints, ONNX files, `.onnx.data` sidecars, output images, local reports, caches, and workbench files are not committed. When final models are ready to distribute, they should be packaged as release assets rather than written into Git history.

## License And Third-Party

ForJyn is based on `yakhyo/fast-neural-style-transfer`; see [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md) for attribution, dependency notes, and license status. Do not use unclear third-party assets, commercial app presets, copied UI assets, or proprietary model files for training or release work.
