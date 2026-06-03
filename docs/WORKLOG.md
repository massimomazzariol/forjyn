# Worklog

## Milestones

- 2026-06-01: Fork repositioned as ForJyn, a local style-transfer model workbench.
- 2026-06-01: Upstream ONNX weights verified as CPU-compatible fixed `1080x1080` baselines.
- 2026-06-01: Dynamic H/W ONNX export validated with a temporary `TransformerNet` wrapper and random weights.
- 2026-06-01: Upstream `candy.pth` locally validated as compatible with `TransformerNet` and dynamic shape-preserving export.
- 2026-06-02: Model factory scaffold added for manifest-driven baseline checks.
- 2026-06-02: Minimal Windows GUI Workbench added.
- 2026-06-02: Workbench backend added for train, export, validate, apply, recovery, and job orchestration.
- 2026-06-02: Export recovery improved so a completed checkpoint can be reused after export/apply failures.
- 2026-06-02: Optional DirectML ONNX inference path checked with CPU fallback preserved.
- 2026-06-02: Procedural reference generator added for local project-owned reference experiments.
- 2026-06-02: WebP support and GUI environment checks added.
- 2026-06-02: Review sheet workflow added for screening completed outputs.
- 2026-06-02: GUI screening workflow refined around Draft, Normal, and Final candidate passes.
- 2026-06-03: Local artifact cleanup and documentation simplification performed for the active Workbench branch.
- 2026-06-03: Runtime path standardized to ignored `workbench/` with technical files under `_runtime/`.

## Current Next Step

Use legal local content and reference images to train and visually screen a small set of Workbench candidates. Keep artifacts local until a model is documented, validated, and selected for release packaging.
