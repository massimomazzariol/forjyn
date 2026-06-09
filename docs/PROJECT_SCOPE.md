# Project Scope

ForJyn is a local workbench for creating and testing ONNX style-transfer models from content photos and style/reference images.

ForJyn is not a full Photoshop-like editor and not a cloud service. It does not promise automatic final visual quality. The project is a local model workflow that still depends on legal inputs, explicit validation, and human visual review.

## In Scope

- Generate procedural reference images locally.
- Use manual local reference images when their license/provenance is clear.
- Train per-style PyTorch models.
- Export dynamic H/W, shape-preserving ONNX models.
- Validate and apply ONNX models locally.
- Create review sheets for candidate screening.
- Keep DirectML training experimental and opt-in unless a separate benchmark task proves it should change.
- Keep generated artifacts under ignored `workbench/` unless a release process explicitly packages them.
- Keep CI and local tests lightweight: path checks, CLI smoke checks, generator smoke checks, and repository hygiene only.

## Out Of Scope

- Full image-editor tooling.
- Cloud hosting or managed training.
- Tiling, patch stitching, or low-resolution upscale as the final product solution.
- Committing generated checkpoints, ONNX models, `.onnx.data` sidecars, outputs, caches, or local workbench files.
- Creating active runtime artifacts outside `workbench/`.
- Claiming final model quality without human review and documented validation.

## Model Direction

ForJyn follows a one filter equals one model approach. The target runtime contract is:

```text
input:  1 x 3 x height x width
output: 1 x 3 x height x width
```

Height and width should be dynamic for Workbench exports, and applying a model should preserve the original content image dimensions.

The active local runtime path is `workbench/`; technical internals live under `workbench/_runtime/`.
CI and tests may redirect that runtime with `FORJYN_WORKBENCH_ROOT` so checks do not write into a user's real workbench.

## Release Direction

Release packaging is deferred. When models are good enough to share, release assets should be prepared outside Git history with model cards, attribution, validation results, and known limitations.
