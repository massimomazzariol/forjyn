# Model Policy

New model files are not committed unless explicitly approved for a specific release or distribution reason.

The fork preserves inherited upstream files, including upstream-tracked sample weights. New checkpoints, exports, datasets, and generated outputs should remain local unless their source, license, and release purpose are documented.

## Upstream Baseline Weights

Inherited upstream ONNX weights are preserved as baseline/demo artifacts from the fork source. They are acceptable for smoke tests and compatibility checks, but they are not the final Forjyn model target.

The current upstream ONNX weights declare batch-dynamic, fixed-spatial shapes:

- input: `[batch_size, 3, 1080, 1080]`
- output: `[batch_size, 3, 1080, 1080]`

Batch dynamism alone is not enough for Forjyn. The Forjyn target remains ONNX models with dynamic height and width:

- input: `1 x 3 x height x width`
- output: `1 x 3 x height x width`

Input/output shape preservation must hold across dynamic height and width, not only at a single fixed `1080x1080` size.

## Dynamic Shape-Preserving Export

A temporary export smoke test showed that `TransformerNet` can be wrapped with a final dynamic crop to restore the original input height and width after the model's internal stride/upsample path. The exported wrapper uses dynamic H/W input and returns runtime shape-preserving output for tested non-fixed sizes.

The smoke-test model uses random/default weights and exists only to validate architecture, ONNX export, and ONNX Runtime behavior. It is not a usable style model and must not be presented as a trained or quality-validated Forjyn model.

The dynamic crop is allowed only as a final shape correction back to the original input H/W. It is not tiling, not patch stitching, and not an upscale workaround for low-resolution output.

Before any generated model is treated as real or useful, Forjyn still needs:

- trained and validated weights
- a stable export policy
- numeric validation across multiple H/W inputs
- visual validation on legal test images
- documented training data, style reference, license status, export settings, and known limitations

## License Requirements

Every model must have a clear license status before it is shared, published, or consumed downstream.

Training data, style references, and evaluation assets must be legal to use. Do not train from proprietary app assets, commercial competitor models, extracted presets, copied UI assets, or unclear sources.

## Documentation Requirements

Generated models should document:

- source code revision
- style reference source and license status
- training dataset source and license status
- training settings
- export settings
- validation results
- known limitations

This documentation should exist before a model is treated as a candidate for downstream app validation.
