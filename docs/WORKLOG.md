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
- 2026-06-03: GitHub presentation, Windows CI, local tests, and README polish prepared for publishing the ForJyn branch.
- 2026-06-09: Workbench monitoring UI simplified after local DirectML/CPU training validation; main counters now emphasize state, stage, elapsed time, total CPU load, process RAM, style progress, and output location, with technical details kept behind a details control.
- 2026-06-09: AMD GPU training spike completed. The stable `.venv` was preserved as PyTorch `2.12.0+cpu` with ONNX Runtime `1.24.4` using `DmlExecutionProvider` for ONNX apply. A separate `.venv-gpu` was created; Python 3.13 had no matching `torch-directml` wheel, so the spike used Python 3.12 with `torch-directml 0.2.5.dev240914` and `torch 2.4.1+cpu`. DirectML tensor matmul passed on `privateuseone:0`.
- 2026-06-09: Experimental DirectML training was added as explicit opt-in only: CLI accepts `--device directml`, GUI shows/selects DirectML training only when `torch_directml` is importable, and CPU remains the default. ForJyn micro training passed on DirectML, but Adam emitted a DML CPU fallback warning for `aten::lerp.Scalar_out`.
- 2026-06-09: Micro benchmark, cache warm, synthetic 2-image dataset, 64px, batch 1, 2 optimizer steps: CPU `.venv` took `2.958s`; DirectML `.venv-gpu` took `2.807s`. This is roughly `1.05x` faster but too small and noisy to justify enabling DirectML by default. Treat DirectML training as usable for later investigation, not stable production guidance.
- 2026-06-09: ROCm/PyTorch on Windows was evaluated from AMD docs and not installed. AMD documents PyTorch ROCm Windows wheels for Python 3.12 and driver `26.2.2`, but the current Windows PyTorch 7.2.1 support matrix lists `gfx1201`, `gfx1200`, `gfx1100`, and `gfx1101` Radeon hardware, not RX 6900 XT / `gfx1030`. Sources: https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/windows/install-pytorch.html and https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html.

## Current Next Step

Use legal local content and reference images to train and visually screen a small set of Workbench candidates. Keep CPU as the default training path; use DirectML training only as an experimental opt-in until longer, isolated benchmarks show a meaningful win.
