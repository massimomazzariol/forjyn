# ForJyn v0.1.0

ForJyn v0.1.0 is the first clean GitHub release of the project as a local ONNX style-transfer workbench.

## What Is Included

- Local Windows/Python workbench with a minimal Tkinter GUI.
- Procedural reference generator for project-owned reference experiments.
- Draft, Normal, and Final workflow for local candidate screening.
- PyTorch training path for local per-style models.
- Dynamic height/width ONNX export, validation, and apply workflow.
- Review sheet workflow for human screening.
- Optional DirectML ONNX inference path with CPU fallback.
- Windows setup and launcher scripts:
  - `setup_windows.bat`
  - `run_forjyn_workbench.bat`
- GitHub Actions CI and local unittest coverage for path, CLI, generator, and repository hygiene checks.

## Artifact Policy

Generated checkpoints, ONNX files, `.onnx.data` sidecars, output images, copied references, caches, reports, and the `workbench/` runtime are not included in Git history.

Final ONNX/filter packs may be distributed later as separate release assets after model cards, attribution, validation, and limitations are documented.

## Limitations

- The current GUI is intentionally minimal and technical, not a polished consumer interface.
- Training can be slow, especially on CPU.
- Visual quality depends on content images, reference images, training settings, and human review.
- Generated models are local candidates until validated and documented.
- ForJyn does not guarantee byte-identical reproduction across machines or dependency versions.
- License and third-party attribution should be reviewed before wider redistribution.

## Notes

This release does not include generated models, checkpoints, ONNX exports, output images, caches, or runtime workbench artifacts.
