# Worklog

## 2026-06-01

- Fork created from `yakhyo/fast-neural-style-transfer`.
- Project repositioning started for Forjyn as a public, CV-friendly model experimentation lab.
- Added project policy and scope documentation before training or export changes.
- Requirements inspected and left unchanged; dependency modernization is deferred.
- Ran the first CPU ONNX smoke tests using inherited upstream weights.
- Confirmed `weights/candy.onnx` runs on CPU with a synthetic `1080x1080` input and produces a `1080x1080` output.
- Confirmed `weights/candy.onnx` rejects a non-`1080x1080` input (`images/style-images/mosaic.jpg`, `470x391`) with an expected shape error: model expected `1080x1080`, got tensor H/W `391x470`.
- Inspected all inherited upstream ONNX weights:
  - `weights/candy.onnx`: input `[batch_size, 3, 1080, 1080]`, output `[batch_size, 3, 1080, 1080]`.
  - `weights/mosaic.onnx`: input `[batch_size, 3, 1080, 1080]`, output `[batch_size, 3, 1080, 1080]`.
  - `weights/rain-princess.onnx`: input `[batch_size, 3, 1080, 1080]`, output `[batch_size, 3, 1080, 1080]`.
  - `weights/udnie.onnx`: input `[batch_size, 3, 1080, 1080]`, output `[batch_size, 3, 1080, 1080]`.
- Conclusion: inherited upstream ONNX weights are a working CPU fixed-size `1080x1080` baseline, but they do not satisfy the Forjyn target of dynamic H/W ONNX with shape-preserving output.
- Ran a temporary dynamic shape-preserving export smoke test using `.local/export_dynamic_shape_preserving_smoke.py`.
- Exported a random/default-weight `TransformerNet` wrapper to `.local/export/forjyn-dynamic-shape-preserving-smoke.onnx` with sidecar `.local/export/forjyn-dynamic-shape-preserving-smoke.onnx.data`.
- Export used the PyTorch ONNX exporter with effective opset `ai.onnx:18`; `onnx.checker` passed.
- Exported ONNX declared input `input` as `[batch, 3, height, width]` and output `output` as `[batch, 3, Min(height, 4*(((height - 1)//4)) + 4), Min(width, 4*(((width - 1)//4)) + 4)]`.
- Runtime validation confirmed shape preservation on CPU:
  - `1 x 3 x 128 x 160` -> `1 x 3 x 128 x 160`.
  - `1 x 3 x 256 x 320` -> `1 x 3 x 256 x 320`.
  - `1 x 3 x 391 x 470` -> `1 x 3 x 391 x 470`.
  - `1 x 3 x 513 x 777` -> `1 x 3 x 513 x 777`.
- Interpretation: ONNX Runtime exposes the output shape as a `Min(...)` expression rather than simplifying it to `height, width`, but runtime validation confirms shape-preserving output for the tested dynamic H/W inputs.
- Conclusion: a temporary wrapper with final dynamic crop can make `TransformerNet` export and run as dynamic H/W shape-preserving ONNX. This validates architecture/export/runtime only; random/default weights do not validate visual quality.
- Next step: define a stable export policy and produce a real trained/validated model with documented training, licensing, numeric checks, and visual checks.
