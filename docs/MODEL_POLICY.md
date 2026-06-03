# Model Policy

ForJyn keeps source control clean. Generated model artifacts are local workbench outputs unless a future release process explicitly packages them.

## Do Not Commit

Do not commit:

- PyTorch checkpoints (`.pth`, `.pt`, `.ckpt`)
- generated ONNX files
- `.onnx.data` sidecars
- output images, previews, review sheets, or contact sheets
- local datasets or copied reference images
- logs, caches, zip files, and local reports
- anything under `workbench/`, `.venv/`, or legacy local runtime folders

The inherited upstream `weights/*.onnx` files remain tracked as upstream baseline/demo files. Do not remove or replace them as part of normal Workbench runs.

`workbench/` is the only active local runtime root. Legacy local runtime folders remain ignored only for cleanup compatibility and should not be recreated by active workflows.

## Upstream Baselines

The tracked upstream ONNX weights are useful for compatibility checks, but they are fixed at `1080x1080` spatial size and are not the final ForJyn target.

The ForJyn target remains dynamic height/width ONNX:

```text
input:  1 x 3 x height x width
output: 1 x 3 x height x width
```

Dynamic batch alone is not enough. Shape preservation must hold across height and width.

## Export Shape Correction

The Workbench may use a final dynamic crop to restore the original input height and width after the model's internal stride/upsample path. That crop is shape correction only.

It is not:

- tiling
- patch stitching
- low-resolution upscale

## ForJyn-Owned Models

Before a generated model is treated as a real ForJyn candidate, document:

- reference source and license/provenance
- procedural seed and metadata, if generated
- training dataset source and license/provenance
- training settings
- export settings
- validation result across realistic image sizes
- output examples for visual review
- known limitations

Procedural generated references are project-owned local outputs, but they still need metadata when used for training. Manual references are the user's license responsibility.

## Distribution

Final model assets should be shared through a release mechanism such as GitHub Releases, not committed into Git history. Each shared model should include a model card, attribution notes, validation results, and usage limitations.

ForJyn does not promise byte-identical regeneration. The goal is a documented, reviewable workflow and functionally similar regenerated candidates, not exact binary reproduction.

Human visual review is required before any model is called useful or release-ready.
