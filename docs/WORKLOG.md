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
- Next step: create or export an ONNX model with input `1 x 3 x height x width` and output `1 x 3 x height x width`.
