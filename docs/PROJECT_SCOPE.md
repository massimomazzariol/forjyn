# Project Scope

Forjyn is a fork-based model lab for experimenting with per-style full-frame visual transformation models.

The first technical goal is a CPU/small smoke test that proves the inherited pipeline can still run in a controlled local setup. Training changes, long training runs, model quality claims, and downstream app integration are out of scope until that baseline is validated.

## Model Direction

Forjyn follows a one filter = one model approach. Each style or visual transformation should map to its own trained/exported model instead of a shared runtime preset system.

The target is full-frame visual transformation. The intended ONNX contract is:

- input: `1 x 3 x height x width`
- output: `1 x 3 x height x width`

Height and width should be dynamic once ONNX export is validated.

## Upstream Baseline Versus Forjyn Target

The inherited upstream ONNX weights are useful as a CPU smoke-test baseline. Initial validation showed that they run at fixed `1080x1080` input/output size, but they do not provide dynamic H/W behavior.

Forjyn's target is a shape-preserving ONNX model whose height and width are dynamic. A model that only declares a dynamic batch dimension is not sufficient for the project target.

## Non-Goals

Forjyn should not treat any of the following as the product solution:

- tiling
- patch stitching
- preview-only fixed `224`, `384`, or `512` input/output sizes
- upscaling low-resolution output into a final image

These techniques may be useful for tests or diagnostics, but they are not the target product behavior for this project.
