# Forjyn

Forjyn is a local GUI workbench for per-style full-frame visual transformation models, especially PyTorch-to-ONNX workflows.

The project is being simplified around a practical workflow: choose a content photo, choose one or more style/reference images, train/export/apply locally, and review the outputs.

## Fork Origin And Attribution

Forjyn is a fork of [`yakhyo/fast-neural-style-transfer`](https://github.com/yakhyo/fast-neural-style-transfer). The original project implements fast neural style transfer inspired by perceptual loss methods and instance normalization, and the upstream README identifies the project as MIT licensed.

This fork keeps attribution to the original upstream project while narrowing its own scope around repeatable model experiments and export validation.

## What This Project Does

- Provides a local workbench for per-style visual transformation models.
- Treats one filter as one trained/exported model.
- Uses the inherited PyTorch training and stylization code as the starting point.
- Targets ONNX export with dynamic full-frame input and output dimensions.
- Keeps generated checkpoints, ONNX files, images, and outputs local.

Target ONNX shape:

- input: `1 x 3 x height x width`
- output: `1 x 3 x height x width`

## What It Does Not Do Yet

- Does not claim final model quality.
- Does not use tiling, patch stitching, or low-resolution upscale as the product solution.
- Does not treat newly generated model weights, datasets, checkpoints, or outputs as source files.

## Current Status

Forjyn is now being simplified around ForJyn Workbench: a local GUI flow for choosing photos and style/reference images, training a PyTorch checkpoint, exporting ONNX, and writing final outputs.

The workbench still does not claim final model quality without human review.

## ForJyn Workbench

The easiest way on Windows is the minimal GUI:

1. Run `run_forjyn_workbench.bat`.
2. Choose a content photo.
3. Choose one or more style/reference images.
4. Press Start.
5. Copy the generated ONNX from `ForJyn_Workbench/outputs/`.

The GUI shows basic CPU/GPU, PyTorch, and ONNX Runtime status before you start.

Step 2 can also generate local project-owned procedural reference-image variations and save selected results into the Workbench reference list.

The GUI can also create a local review sheet from completed outputs so candidates can be screened before slower final training.

For details, read [`docs/WORKBENCH.md`](docs/WORKBENCH.md).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dependencies are intentionally unchanged in this repositioning step. Broad dependency modernization should be handled separately.

## Roadmap

1. Stabilize the Workbench GUI flow.
2. Make training/export/apply understandable for non-technical users.
3. Validate outputs on user-provided local content/style images.
4. Improve model quality after human review.
5. Handle release packaging later, once the workbench is stable.

Forjyn can be used as a model pipeline for downstream projects such as Mixelith, while remaining an independent project.

## Safety And Licensing

Do not commit newly generated model binaries, datasets, checkpoints, generated outputs, or proprietary assets without explicit approval. Do not use models, assets, code, presets, SVGs, or UI extracted from commercial apps.

Every generated model should document its source revision, training data, style reference, training settings, license status, export settings, and validation results before it is shared or considered for downstream use.

See:

- [`docs/WORKBENCH.md`](docs/WORKBENCH.md)
- [`docs/PROJECT_SCOPE.md`](docs/PROJECT_SCOPE.md)
- [`docs/MODEL_POLICY.md`](docs/MODEL_POLICY.md)
- [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md)
