# ForJyn

ForJyn is a local Windows/Python workbench for generating and testing ONNX style-transfer models from reference images. It is experimental, local-first, and organized around one runtime folder: `workbench/`.

## What It Does

- Choose a content photo from any local path.
- Choose manual style/reference images or generate procedural references locally.
- Train one PyTorch style model per selected reference.
- Export dynamic height/width, shape-preserving ONNX models.
- Validate and apply ONNX models to the content photo.
- Create review sheets for human screening.

## Fresh Clone Workflow

```powershell
git clone <repo-url>
cd forjyn
setup_windows.bat
run_forjyn_workbench.bat
```

In the GUI:

1. Choose a content photo.
2. Choose or generate style/reference images.
3. Select Draft, Normal, or Final quality.
4. Start the job.
5. Review outputs in `workbench/outputs/`.

`setup_windows.bat` creates `.venv/`, installs `requirements.txt`, and prints the launcher command. It does not start training.

## Runtime Layout

`workbench/` is ignored by Git and can be recreated after a clean clone.

```text
workbench/
  manual-references/
  final-candidates/
  generated-references/
    saved/
    contact-sheets/
  outputs/
  reviews/
  _runtime/
    cache/
    torch/
    onnx/
    models/
    reports/
    logs/
```

Normal users work mainly in `manual-references/`, `generated-references/`, `outputs/`, and `reviews/`. `_runtime/` stores technical files such as caches, checkpoints, ONNX exports, reports, and logs.
The VGG/Torch cache is stored at `workbench/_runtime/cache/torch/`.

## Current Status

ForJyn is a working local workbench, not a finished filter pack. Outputs still need human visual review, and generated models should be treated as candidates until their references, training settings, validation, and license status are documented.

## Key Features

- Minimal Tkinter GUI.
- Procedural reference generator with traceable seeds and metadata.
- Draft/Normal/Final training presets.
- Dynamic H/W ONNX export with shape-preserving output.
- ONNX validation and apply workflow.
- Optional DirectML ONNX inference path with CPU fallback.
- JPG, PNG, and WebP support when Pillow supports WebP.
- Review sheet creation for completed outputs.

## Reproducibility Note

ForJyn does not guarantee byte-identical ONNX reproduction. Procedural seeds and metadata make generated references traceable, but training output can vary by environment, PyTorch build, device, and dependency versions. The goal is a functionally reproducible workflow: clone, set up, run the GUI, generate or choose references, train/export ONNX, and review outputs.

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
