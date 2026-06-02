# ForJyn Workbench Guide

ForJyn Workbench is the simple Windows-first way to create a local per-style ONNX candidate from a content photo and one or more style/reference images.

## Easy GUI Workflow

1. Double click `run_forjyn_workbench.bat`.
2. Click `Choose content photo`.
3. Select the photo you want to transform, for example `amber.jpg`.
4. Click `Choose style/reference images`.
5. Select one or more style images, for example `rain-princess.jpg`.
6. Choose quality.
7. Click `Start`.
8. Wait.
9. Click `Open output folder`.

The GUI also shows a compact status area with:

- Workbench readiness.
- CPU/GPU availability.
- PyTorch version.
- ONNX Runtime providers.
- Output folder path.

ForJyn uses GPU only if the local PyTorch/CUDA environment supports it. If the GUI shows `CPU only`, that is not necessarily a bug; it can simply mean the installed PyTorch build is CPU-only or CUDA is unavailable on the machine.

## What You Get

For each style/reference image, ForJyn creates one output folder containing:

- ONNX model ready to copy.
- `.onnx.data` if generated.
- Styled output image.
- Validation metadata.
- Training log.
- Export metadata.
- Model card.
- Output README.

Output folders use this shape:

```text
ForJyn_Workbench/outputs/YYYYMMDD-HHMMSS-style-name/
```

Example:

```text
ForJyn_Workbench/outputs/20260602-181530-rain-princess/
```

## Important Clarification

- ONNX is not trained directly.
- ForJyn trains a PyTorch checkpoint first.
- Then it exports ONNX.
- Then it validates ONNX.
- Then it applies ONNX to the content photo.
- The output image keeps the original width and height.

Internal flow:

```text
content image + style/reference image
-> train PyTorch TransformerNet
-> checkpoint .pth
-> export ONNX dynamic H/W shape-preserving
-> validate ONNX
-> apply ONNX to the content image
-> save output + ONNX + metadata
```

## Quality Modes

- Quick test - 200 steps
  Fast smoke test, not final quality.
- Normal - 800 steps
  First real pilot.
- Better quality - 2000 steps
  Slower, better candidate.

ForJyn output quality depends on the style image, content photo, training steps, and local environment. Review generated results before sharing them.

## Where Files Are Stored

User-facing outputs:

```text
ForJyn_Workbench/outputs/
```

Technical files:

```text
ForJyn_Workbench/technical/
```

The GUI can choose input files from any local path. Optional convenience folders are:

```text
ForJyn_Workbench/inputs/
ForJyn_Workbench/references/
```

## Backend Command

The GUI calls the backend command once for each selected style/reference image:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py run-job --content "C:\path\amber.jpg" --style "C:\path\rain-princess.jpg" --name "rain-princess" --steps 800 --output-root "ForJyn_Workbench\outputs"
```

The backend prints a final machine-readable line:

```text
FORJYN_OUTPUT_DIR=C:\...\ForJyn_Workbench\outputs\YYYYMMDD-HHMMSS-style-name
```

## Regeneration

Regeneration is intended to be functionally similar, not byte-for-byte identical. Quick tests are not final-quality models.

## Release

Release packaging is not handled yet. It will be done later, after the workbench is stable and generates good ONNX model candidates.
