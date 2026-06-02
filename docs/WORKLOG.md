# Worklog

## 2026-06-02

- Archived the experimental modern-core / modern-artistic V2 workflow in local branch `archive/modern-artistic-v2-experimental-workflow`.
- Reset the active branch back to `2ab5e5b chore: add model factory scaffold` to simplify the project direction.
- Started the ForJyn GUI Workbench direction:
  - `ForJyn_Workbench/inputs/`
  - `ForJyn_Workbench/references/`
  - `ForJyn_Workbench/outputs/`
  - `ForJyn_Workbench/technical/`
- Added `tools/forjyn_workbench.py` with commands for init, scan, train, export, validate, apply, end-to-end local runs, and GUI-friendly `run-job`.
- Added `tools/forjyn_workbench_gui.py` as a minimal Tkinter GUI for choosing a content photo, choosing one or more style/reference images, selecting quality, starting jobs, viewing logs, and opening output folders.
- Added `run_forjyn_workbench.bat` as the Windows launcher for the GUI.
- Added `docs/WORKBENCH.md` as the simple GUI user guide.
- Updated training support for bounded local Workbench runs: max steps, checkpoint naming, worker count, and device selection.
- Release packaging is intentionally deferred until the Workbench is stable.

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
- Downloaded only `candy.pth` from upstream `yakhyo/fast-neural-style-transfer` release `v1.0` into `.local/upstream-yakhyo-v1.0/candy.pth` for local technical validation.
- Recorded `candy.pth` SHA256: `D458C378A796C7F2B332050995AD1B2D27DD5D73AC3C015C79E4C45D773AF282`.
- Confirmed the upstream `candy.pth` checkpoint loads into the local `TransformerNet` with no missing or unexpected keys.
- Exported the real upstream `candy.pth` through the temporary dynamic shape-preserving wrapper to `.local/export/forjyn-candy-real-dynamic-shape-preserving-smoke.onnx` with sidecar `.onnx.data`.
- Validated ONNX Runtime CPU shape preservation on realistic tensor sizes:
  - `1 x 3 x 1090 x 1280` -> `1 x 3 x 1090 x 1280` in about `1.493s`.
  - `1 x 3 x 1080 x 1920` -> `1 x 3 x 1080 x 1920` in about `1.959s`.
  - `1 x 3 x 1920 x 1080` -> `1 x 3 x 1920 x 1080` in about `2.079s`.
  - `1 x 3 x 1091 x 1279` -> `1 x 3 x 1091 x 1279` in about `1.313s`.
- Ran a synthetic image smoke test at `1280 x 1090`; output preserved `1280 x 1090`.
- Conclusion: upstream `candy.pth` is a real compatible baseline that can be exported as dynamic H/W shape-preserving ONNX, but it is not Forjyn-owned and should not be treated as the final project model.
- Added initial model factory scaffolding: tracked manifest, local CLI, factory documentation, and model status table.
- Factory outputs are configured for `.local/model-factory/<model-id>/` and must not be committed.
- Verified the factory path locally with `candy`: manifest check, status, export, and validation passed; generated metadata and ONNX artifacts stayed under `.local/model-factory/candy/`.
- Next step: provide legal Forjyn-owned style images and a legal training dataset path for the first owned-model batch.
