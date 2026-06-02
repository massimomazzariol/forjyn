# Project Scope

Forjyn is a local GUI workbench for per-style full-frame visual transformation models.

The active goal is a simple user-facing workflow: choose a content photo, choose one or more style/reference images, train local PyTorch checkpoints, export dynamic H/W shape-preserving ONNX, and write final transformed images plus model artifacts to an output folder.

## Model Direction

Forjyn follows a one filter = one model approach. Each style image maps to its own trained/exported model instead of a shared runtime preset system.

The target is full-frame visual transformation. The intended ONNX contract is:

- input: `1 x 3 x height x width`
- output: `1 x 3 x height x width`

Height and width should be dynamic for Workbench exports. Applying a model to a content image should preserve the original content image dimensions.

## Upstream Baseline Versus Forjyn Target

The inherited upstream ONNX weights are useful as a CPU smoke-test baseline. Initial validation showed that they run at fixed `1080x1080` input/output size, but they do not provide dynamic H/W behavior.

Forjyn's target is a shape-preserving ONNX model whose height and width are dynamic. A model that only declares a dynamic batch dimension is not sufficient for the project target.

A final dynamic crop back to the original input height and width is acceptable as a technical shape-preservation step when the model's internal stride/upsample path rounds dimensions upward. This crop must only restore the original frame dimensions; it is not a substitute for full-frame inference and must not become tiling, patch stitching, or low-resolution upscaling.

## Non-Goals

Forjyn should not treat any of the following as the product solution:

- tiling
- patch stitching
- preview-only fixed `224`, `384`, or `512` input/output sizes
- upscaling low-resolution output into a final image

These techniques may be useful for tests or diagnostics, but they are not the target product behavior for this project.

## Workbench Scope

The Workbench user-facing folders are:

- `ForJyn_Workbench/inputs/`
- `ForJyn_Workbench/references/`
- `ForJyn_Workbench/outputs/`

Technical files stay under `ForJyn_Workbench/technical/` and are not committed.

Release packaging is out of scope until the Workbench is stable.
