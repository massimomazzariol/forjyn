# ForJyn Workbench

ForJyn Workbench is the main user-facing workflow for local style-transfer model experiments. It runs on your machine, writes artifacts under `ForJyn_Workbench/`, and keeps generated files out of Git.

## GUI Workflow

Start the GUI on Windows:

```powershell
.\run_forjyn_workbench.bat
```

Then follow the four steps:

1. Choose a content photo.
2. Choose one or more style/reference images, or generate procedural references.
3. Pick a quality mode.
4. Start the job.

Use `Open output folder` after a run finishes. Use `Create review sheet` after one or more runs to compare completed outputs visually.

## Content Photo

The content photo is the image ForJyn transforms. It can be selected from any local folder. Supported formats are JPG, JPEG, PNG, and WebP when the current Pillow build supports WebP.

Optional convenience folder:

```text
ForJyn_Workbench/inputs/
```

## Style And Reference Images

You can select manual local references or use the procedural generator. Manual references are the user's license responsibility. Generated procedural references are local ForJyn workbench artifacts and are not committed.

Generated references are stored under:

```text
ForJyn_Workbench/generated_references/
```

Useful generated references can be saved into:

```text
ForJyn_Workbench/generated_references/saved/
```

The generator can create multiple presets and records metadata for generated images. Good references usually have structure, contrast, color variation, and readable edge detail.

## Quality Modes

- Draft: fast screening for multiple references.
- Normal: a stronger candidate pass for promising references.
- Final: slower training for selected winners.

The mode changes training time and candidate quality. It does not remove the need for human review.

## Outputs

Each completed job writes a folder under:

```text
ForJyn_Workbench/outputs/YYYYMMDD-HHMMSS-style-name/
```

Typical contents include:

- styled output image
- exported ONNX model
- `.onnx.data` sidecar when produced by the exporter
- validation metadata
- training/export logs and summaries
- model card or output notes

The technical training/export workspace is under:

```text
ForJyn_Workbench/technical/
```

Checkpoints are PyTorch `.pth` files. ONNX files are exported runtime models. `.onnx.data` files are sidecars used by some ONNX exports and must stay next to their ONNX file.

## Review Sheet

`Create review sheet` builds a local comparison sheet from completed outputs. It does not train, export ONNX, or process new content.

Latest review output:

```text
ForJyn_Workbench/reviews/latest-review-sheet.jpg
```

Use review sheets to decide which references deserve slower Final runs.

## Clean Temporary References

The backend can remove temporary generated-reference sessions:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py cleanup-temp
```

This keeps saved references, starter packs, outputs, models, reports, reviews, `.venv`, `.local`, and `weights`.

## CPU, GPU, And DirectML

Training uses PyTorch CPU or CUDA, depending on the installed PyTorch build and local hardware. If the GUI reports CPU only, that is not automatically a bug.

DirectML is optional and applies only to ONNX Runtime inference/validation in this workbench. If DirectML is missing, incompatible, or slower on a local machine, ForJyn keeps CPU fallback available.

## WebP

ForJyn accepts WebP only when Pillow reports WebP support in the current environment. If WebP fails, convert the image to JPG or PNG and rerun the job.

## Backend Command

The GUI calls the backend per selected reference. A representative command is:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py run-job --content "C:\path\photo.jpg" --style "C:\path\reference.png" --name "reference" --steps 800 --output-root "ForJyn_Workbench\outputs"
```

The backend prints a final `FORJYN_OUTPUT_DIR=...` line for GUI and script integration.

## Troubleshooting

Training completed but export failed: use `recover-job` with the existing model directory and content image. Recovery exports ONNX from the checkpoint, validates it, and applies it without retraining.

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py recover-job --model-dir "ForJyn_Workbench\technical\models\YYYYMMDD-HHMMSS-style-name" --content "C:\path\content.jpg" --output-dir "ForJyn_Workbench\outputs\YYYYMMDD-HHMMSS-style-name"
```

CPU only: install a CUDA-capable PyTorch build if you expect GPU training and your machine supports it. DirectML availability does not accelerate PyTorch training here.

WebP unsupported: convert the file to JPG or PNG.

Checkpoint recovery: keep the local `ForJyn_Workbench/technical/models/...` folder until you know the output folder is complete and usable.
