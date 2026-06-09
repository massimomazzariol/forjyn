# Next Steps

The ForJyn pipeline works: local reference generation, training, ONNX export, validation, apply, review sheets, CPU fallback, and optional DirectML acceleration are in place. The current models are still experimental. Visual quality needs a dedicated phase before any produced ONNX filter should be treated as release-ready.

## Future Work: Model Quality And ONNX Filter Production

### 1. Model Quality Lab

- Move from pilot training on one content image to an organized experiment workflow.
- Create repeatable experiments with fixed content sets, reference images, parameters, and seeds.
- Generate comparison review sheets for each experiment.
- Save experiment reports with inputs, parameters, runtime, output paths, and review notes.

### 2. Content Dataset

- Use a local mini dataset with many different images.
- Warn below 20 images: pilot only.
- Treat 50 images as a minimum for a serious test.
- Prefer 100 to 200+ images for stronger candidate training.
- Include architecture, faces, objects, interiors, landscapes, urban scenes, highlights, and shadows.

### 3. Reference Selection

- Avoid references that are too monochromatic.
- Avoid crushed blacks.
- Avoid posterized or heatmap-like references.
- Prefer more midtones.
- Prefer palettes with 2 or 3 clear colors.
- Prefer visible texture.
- Preserve content readability over maximum style intensity.

### 4. Parameter Grid

Explore configurable training parameters:

- style weight
- content weight
- total variation or smoothing if added later
- image size or crop size
- steps
- batch size where applicable

Compare low, medium, and high style intensity before spending time on long runs.

### 5. Quality Review

- Apply candidate models to 3 to 5 test images.
- Compare CPU and DirectML only when it helps understand runtime behavior.
- Build review sheets.
- Manually reject weak outputs.
- Promote only the best references to 800 or 2000 step runs.

### 6. ONNX Optimization

- Evaluate ONNX file size.
- Track `.onnx.data` sidecars when present.
- Keep export compatibility across PyTorch versions.
- Consider quantization only after visual quality is acceptable.
- Keep Mixelith compatibility as a downstream requirement.

### 7. Mixelith Handoff

When one ONNX model is genuinely good:

- Import it into Mixelith.
- Apply it offline to photos.
- Preview outputs.
- Export/share outputs.
- Evaluate Android performance.

### 8. Refactor Checkpoint

- `tools/forjyn_workbench_gui.py` is large and could be split.
- `tools/forjyn_workbench.py` is large and could be split.
- Future split candidates: GUI layout, run monitor, environment checks, backend export/apply/recovery, report writing.
- Do this only if ForJyn work resumes; do not refactor just for v0.1.1.
