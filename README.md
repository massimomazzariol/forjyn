# Forjyn

Forjyn is a fork-based model experimentation lab for per-style full-frame visual transformation models, especially PyTorch-to-ONNX workflows.

The project is being repositioned as a clean, public, CV-friendly space for training, exporting, and validating one-filter-one-model visual transformations. The first milestone is to validate a small CPU smoke test and dynamic ONNX export.

## Fork Origin And Attribution

Forjyn is a fork of [`yakhyo/fast-neural-style-transfer`](https://github.com/yakhyo/fast-neural-style-transfer). The original project implements fast neural style transfer inspired by perceptual loss methods and instance normalization, and the upstream README identifies the project as MIT licensed.

This fork keeps attribution to the original upstream project while narrowing its own scope around repeatable model experiments and export validation.

## What This Project Does

- Provides a lab for per-style visual transformation models.
- Treats one filter as one trained/exported model.
- Uses the inherited PyTorch training and stylization code as the starting point.
- Targets ONNX export with dynamic full-frame input and output dimensions.
- Documents model, licensing, and downstream integration policies before adding new training work.

Target ONNX shape:

- input: `1 x 3 x height x width`
- output: `1 x 3 x height x width`

## What It Does Not Do Yet

- Does not claim final model quality.
- Does not claim verified full-resolution success.
- Does not implement new training changes yet.
- Does not use tiling, patch stitching, or low-resolution upscale as the product solution.
- Does not treat newly generated model weights, datasets, checkpoints, or outputs as source files.

## Current Status

Forjyn is in project-positioning mode. Documentation, ignore rules, and model artifact policy are being established before any training or export changes.

The next technical milestone is a CPU-first smoke test followed by dynamic ONNX export validation.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dependencies are intentionally unchanged in this repositioning step. Broad dependency modernization should be handled separately.

## Roadmap

1. Run a CPU smoke test with the existing code.
2. Validate dynamic ONNX export with input `1 x 3 x height x width`.
3. Validate local ONNX inference on CPU.
4. Create the first project-owned style reference.
5. Train the first Forjyn-owned per-style model.
6. Export and validate the model as ONNX.
7. Package validated model metadata for downstream consumers.

Forjyn can be used as a model pipeline for downstream projects such as Mixelith, while remaining an independent project.

## Safety And Licensing

Do not commit newly generated model binaries, datasets, checkpoints, generated outputs, or proprietary assets without explicit approval. Do not use models, assets, code, presets, SVGs, or UI extracted from commercial apps.

Every generated model should document its source revision, training data, style reference, training settings, license status, export settings, and validation results before it is shared or considered for downstream use.

See:

- [`docs/PROJECT_SCOPE.md`](docs/PROJECT_SCOPE.md)
- [`docs/MODEL_POLICY.md`](docs/MODEL_POLICY.md)
- [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md)
