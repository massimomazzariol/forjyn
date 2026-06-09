# ForJyn Workbench

ForJyn Workbench is the main local workflow for style-transfer model experiments. It writes runtime artifacts under `workbench/`, which is ignored by Git and can be recreated after a clean clone.

## Fresh Clone Workflow

```powershell
git clone <repo-url>
cd forjyn
setup_windows.bat
run_forjyn_workbench.bat
```

`setup_windows.bat` creates the stable `.venv` runtime first. If Python 3.12 is available, it also attempts to create `.venv-gpu` for experimental DirectML training. `run_forjyn_workbench.bat` checks the GPU runtime automatically and falls back to `.venv` with a clear console message when DirectML training is unavailable.

Then in the GUI:

1. Choose a content photo.
2. Choose one or more style/reference images, or generate procedural references.
3. Pick Draft, Normal, or Final.
4. Start.
5. Review outputs in `workbench/outputs/`.

## Runtime Layout

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

Normal users should focus on:

- `workbench/manual-references/`
- `workbench/generated-references/`
- `workbench/outputs/`
- `workbench/reviews/`

Technical files live under `workbench/_runtime/`.
The VGG/Torch cache is stored at `workbench/_runtime/cache/torch/`.

Automated tests and CI may redirect the runtime root with:

```text
FORJYN_WORKBENCH_ROOT
```

This is only for isolation. The normal local user runtime remains `workbench/`.

## Content Photo

The content photo is the image ForJyn transforms. It can be selected from any local path. Supported formats are JPG, JPEG, PNG, and WebP when the current Pillow build supports WebP.

## Style And Reference Images

Manual local references can be selected from any folder. The convenience folder is:

```text
workbench/manual-references/
```

Manual references are the user's license responsibility.

The procedural generator writes selected references here:

```text
workbench/generated-references/saved/
```

Reference contact sheets are written here:

```text
workbench/generated-references/contact-sheets/
```

Generator metadata and temporary sessions are technical runtime files under `workbench/_runtime/`.

## Quality Modes

- Draft: fast screening for multiple references.
- Normal: a stronger candidate pass for promising references.
- Final: slower training for selected winners.

The mode changes training time and candidate quality. It does not remove the need for human review.

## Run Monitor And Cancellation

The Workbench keeps the main run monitor intentionally compact. The always-visible counters show run state, current stage, elapsed time, total CPU load, process RAM in MB, style progress, and the output folder.

Use `Run details` for job ID, PID, process CPU cores, ONNX provider, last ONNX apply time, and DirectML details. Live GPU utilization is not shown because it is not reliable without external tooling, and ONNX apply/validation can be too brief for a stable live reading.

`Stop current job` cancels only the active backend job and its child processes. It should not close the GUI or terminate unrelated Python processes.

## Outputs

Each completed job writes a folder under:

```text
workbench/outputs/YYYYMMDD-HHMMSS-style-name/
```

Typical contents include:

- styled output image
- exported ONNX model
- `.onnx.data` sidecar when produced by the exporter
- validation metadata
- training/export logs and summaries
- model card or output notes

Runtime model/checkpoint files are stored under:

```text
workbench/_runtime/models/
```

Checkpoints are PyTorch `.pth` files. ONNX files are exported runtime models. `.onnx.data` files are sidecars used by some ONNX exports and must stay next to their ONNX file.

## Review Sheet

`Create review sheet` builds a local comparison sheet from completed outputs. It does not train, export ONNX, or process new content.

Latest review output:

```text
workbench/reviews/latest-review-sheet.jpg
```

Use review sheets to decide which references deserve slower Final runs.

## Clean Temporary References

The backend can remove temporary generated-reference sessions:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py cleanup-temp
```

This keeps saved references, final candidates, contact sheets, outputs, models, reports, reviews, `.venv`, `weights`, and the main `workbench/` structure.

## CPU, GPU, And DirectML

Training defaults to PyTorch CPU in the stable runtime. CUDA can still be requested from the backend with a CUDA-capable PyTorch build.

DirectML has two separate roles:

- ONNX Runtime DirectML is used for inference/validation and ONNX apply when available, with CPU fallback preserved.
- PyTorch DirectML training is experimental and opt-in only. It requires `torch-directml` in the active Python environment and must be selected explicitly in the GUI or requested with `--device directml` from the backend.

If the GUI reports CPU only, that is not automatically a bug. Keep CPU as the stable fallback unless a local isolated benchmark proves DirectML training is faster and stable for the chosen job size.

Manual setup and test commands for the separate `.venv-gpu` experiment are in [Experimental DirectML Training](GPU_TRAINING_EXPERIMENTAL.md).

ONNX export supports both newer PyTorch builds with `dynamic_shapes` and older compatible builds with legacy `dynamic_axes`. If training completes but export/apply fails, use `recover-job` with the existing checkpoint instead of retraining.

The tested AMD configuration for the experimental path is AMD Radeon RX 6900 XT on Windows 11 with Python 3.12.10, PyTorch `2.4.1+cpu`, `torch-directml 0.2.5.dev240914`, ONNX Runtime DirectML `1.24.4`, and DirectML device `privateuseone:0`. This is not a guarantee for all AMD GPUs.

## WebP

ForJyn accepts WebP only when Pillow reports WebP support in the current environment. If WebP fails, convert the image to JPG or PNG and rerun the job.

## Backend Command

The GUI calls the backend per selected reference. A representative command is:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py run-job --content "C:\path\photo.jpg" --style "C:\path\reference.png" --name "reference" --steps 800 --output-root "workbench\outputs"
```

The backend prints a final `FORJYN_OUTPUT_DIR=...` line for GUI and script integration.

## Troubleshooting

Training completed but export failed: use `recover-job` with the existing model directory and content image. Recovery exports ONNX from the checkpoint, validates it, and applies it without retraining.

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py recover-job --model-dir "workbench\_runtime\models\YYYYMMDD-HHMMSS-style-name" --content "C:\path\content.jpg" --output-dir "workbench\outputs\YYYYMMDD-HHMMSS-style-name"
```

CPU only: install a CUDA-capable PyTorch build if you expect CUDA training and your machine supports it. DirectML training appears only when `torch-directml` is installed in the active environment, and it remains experimental.

WebP unsupported: convert the file to JPG or PNG.

Checkpoint recovery: keep the local `workbench/_runtime/models/...` folder until you know the output folder is complete and usable.

## Reproducibility Note

ForJyn does not guarantee byte-identical ONNX reproduction. Procedural seeds and metadata make generated references traceable, but training can vary across machines, dependency versions, devices, and PyTorch builds. The intended guarantee is functional reproducibility of the workflow: setup, GUI launch, reference generation/selection, train/export, apply, and review.

## Local Tests

Run the lightweight local checks with:

```powershell
scripts\run_tests.bat
```

The tests use temporary runtime folders, do not train, and do not generate ONNX.
