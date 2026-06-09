# ForJyn v0.1.1

## Highlights

- Finalizes the current Windows Workbench setup flow.
- Adds dual local runtime setup: stable `.venv` plus optional experimental `.venv-gpu`.
- Adds an automatic launcher that uses the DirectML runtime when available and falls back to CPU.
- Keeps CPU as the stable training fallback.
- Keeps DirectML training experimental.

## Runtime Setup

- `setup_windows.bat` creates or updates the stable `.venv` runtime.
- When Python 3.12 is available, setup also attempts to create `.venv-gpu`.
- `.venv-gpu` installs `torch-directml` plus the non-torch ForJyn runtime dependencies.
- Setup does not fail the whole install if the GPU runtime cannot be created.
- `run_forjyn_workbench.bat` checks `torch_directml.device()` and starts the GUI with `.venv-gpu` when that check passes.
- If the DirectML runtime is missing or broken, the launcher prints a clear fallback message and starts the stable CPU runtime.

## DirectML / AMD Notes

- ONNX apply and validation can use ONNX Runtime DirectML when available.
- DirectML training is experimental and opt-in inside the GUI.
- Tested locally on AMD Radeon RX 6900 XT, Windows 11, Python 3.12.10, PyTorch `2.4.1+cpu`, `torch-directml 0.2.5.dev240914`, and ONNX Runtime DirectML `1.24.4`.
- The DirectML training device appears as `privateuseone:0`.
- Adam may fall back to CPU for `aten::lerp.Scalar_out`.
- This release does not guarantee DirectML training support or speedups on all AMD GPUs.

## UI Improvements

- Main Workbench status remains compact and focused on state, stage, elapsed time, CPU load, RAM, style progress, and output location.
- System status shows the selected training device; CPU remains the default even when the DirectML runtime is available.
- Environment details include runtime mode, Python version, PyTorch version, torch-directml availability, DirectML device, and ONNX providers.
- Stop/Cancel remains available for the active backend job and its child processes.
- Results stay hidden until a job produces output, then show output image, output folder, ONNX provider, apply time, and size preservation.

## Documentation

- README explains the dual runtime setup and automatic launcher.
- `docs/GPU_TRAINING_EXPERIMENTAL.md` documents the experimental DirectML path.
- `docs/NEXT_STEPS.md` records future model-quality work and ONNX filter production steps.
- Workbench docs and worklog were updated for the v0.1.1 runtime behavior.

## Known Limitations

- Model visual quality is still experimental and requires human review.
- DirectML training is experimental and not a universal AMD GPU promise.
- Speedups may vary and some operations may fall back to CPU.
- Generated checkpoints, ONNX files, outputs, caches, `.venv`, `.venv-gpu`, and `workbench/` are not release assets and are not committed.
- No production-quality ONNX filter is included in this release.

## Next Steps

- Build a Model Quality Lab workflow.
- Use better local content datasets.
- Explore parameter grids for style intensity, content preservation, image size, steps, and batch size.
- Produce comparative review sheets.
- Promote only the strongest models to longer runs.
- Optimize ONNX only after visual quality is acceptable.
- Test a genuinely good ONNX model in Mixelith as a future handoff.
