# ForJyn Workbench Guide

ForJyn Workbench is the simple Windows-first way to create a local per-style ONNX candidate from a content photo and one or more style/reference images.

## Easy GUI Workflow

1. Double click `run_forjyn_workbench.bat`.
2. Click `Choose content photo`.
3. Select the photo you want to transform, for example `amber.jpg`.
4. Click `Choose style/reference images`.
5. Select one or more style images, for example `rain-princess.jpg`.
6. Choose quality.
7. Click `Start`.
8. Wait.
9. Click `Open output folder`.
10. Click `Create review sheet` to compare completed outputs visually.

Step 2 also includes `Generate reference images`. This opens the local `ForJyn Reference Generator`, which can create procedural reference-image variations without downloading assets or using external AI generation.

The generator currently includes these presets:

- Neon Bloom
- Cyber Edge
- Liquid Neon
- Neon Poster
- Holographic Glass
- Painterly Color Storm

Each generation stores PNG variations and metadata under:

```text
ForJyn_Workbench/generated_references/
```

Generated images can be previewed, selected, and saved into the Workbench reference list. Saved generated references are copied into:

```text
ForJyn_Workbench/generated_references/saved/
```

The generated files and metadata are local workbench artifacts and should not be committed.

The generator includes anti-washout safeguards. Each generated image is scored for brightness, contrast, saturation, white clipping, dark/bright balance, and edge detail. If an output is too white, too flat, or too low-information, ForJyn retries with a derived seed and records the final metrics in metadata.

Reference quality matters. A useful style/reference image should contain dark zones, bright zones, structure, texture, color variation, and readable edges. Pretty but flat references usually train weaker models.

Recommended first presets:

- Cyber Edge
- Neon Bloom
- Liquid Neon

Basic generator workflow:

```text
generate many references -> save a few promising ones -> use in Step 2 -> train selected references -> review outputs -> final-train only winners
```

The GUI also shows a compact status area with:

- Workbench readiness.
- Training device availability.
- PyTorch version.
- ONNX Runtime providers.
- DirectML provider availability for possible future ONNX inference acceleration.
- WebP support.
- Output folder path.

ForJyn uses GPU only if the local PyTorch/CUDA environment supports it. If the GUI shows `CPU only`, that is not necessarily a bug; it can simply mean the installed PyTorch build is CPU-only or CUDA is unavailable on the machine.

DirectML may be useful later for ONNX inference acceleration on compatible Windows GPUs, but ForJyn does not automatically install or enable DirectML.

## Optional DirectML ONNX Inference

DirectML is optional. When `onnxruntime-directml` is available, ForJyn can use it for ONNX Runtime validation and apply/inference only.

DirectML does not accelerate PyTorch training in this setup. Training remains CPU-only unless the local PyTorch environment exposes CUDA.

If DirectML is unavailable, incompatible, or fails during inference, ForJyn keeps a CPU fallback. Do not treat CPU fallback as a workflow failure.

## What You Get

For each style/reference image, ForJyn creates one output folder containing:

- ONNX model ready to copy.
- `.onnx.data` if generated.
- Styled output image.
- Validation metadata.
- Training log.
- Export metadata.
- Model card.
- Output README.

Output folders use this shape:

```text
ForJyn_Workbench/outputs/YYYYMMDD-HHMMSS-style-name/
```

Example:

```text
ForJyn_Workbench/outputs/20260602-181530-rain-princess/
```

## Important Clarification

- ONNX is not trained directly.
- ForJyn trains a PyTorch checkpoint first.
- Then it exports ONNX.
- Then it validates ONNX.
- Then it applies ONNX to the content photo.
- The output image keeps the original width and height.

Internal flow:

```text
content image + style/reference image
-> train PyTorch TransformerNet
-> checkpoint .pth
-> export ONNX dynamic H/W shape-preserving
-> validate ONNX
-> apply ONNX to the content image
-> save output + ONNX + metadata
```

## Quality Modes

- Draft screening - 300 steps
  Fast screening. Use this to test multiple references before spending time.
- Normal candidate - 800 steps
  Good first candidate. Use this for promising references.
- Final quality - 2000 steps
  Slow. Use only for selected winners.

ForJyn output quality depends on the style image, content photo, training steps, and local environment. Review generated results before sharing them.

The bottleneck is training, so do not train too many references blindly. Use Draft or Normal to compare several references, then reserve Final quality for the best few.

## Supported Image Formats

ForJyn accepts:

- JPG
- JPEG
- PNG
- WebP, if supported by the current Pillow installation

If WebP does not work in your Python/Pillow environment, convert the image to JPG or PNG and run the job again.

## Progress And Logs

The GUI shows the current stage:

- Training
- Exporting ONNX
- Validating
- Applying
- Done

Raw progress percentages from lower-level tools are filtered out of the GUI log so the log stays readable.

## Review Sheet

After one or more jobs complete, click `Create review sheet` in the GUI. ForJyn composes a local comparison sheet from already-generated outputs; it does not train, export ONNX, or process new content.

The latest GUI review sheet is saved here:

```text
ForJyn_Workbench/reviews/latest-review-sheet.jpg
```

Use it for human visual review before deciding which references deserve slower final-quality training.

## Where Files Are Stored

User-facing outputs:

```text
ForJyn_Workbench/outputs/
```

Technical files:

```text
ForJyn_Workbench/technical/
```

The GUI can choose input files from any local path. Optional convenience folders are:

```text
ForJyn_Workbench/inputs/
ForJyn_Workbench/references/
```

The backend command `cleanup-temp` removes only temporary generated-reference sessions:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py cleanup-temp
```

It keeps starter packs, saved references, contact sheets, outputs, models, reports, reviews, `.venv`, `.local`, and `weights`.

## Backend Command

The GUI calls the backend command once for each selected style/reference image:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py run-job --content "C:\path\amber.jpg" --style "C:\path\rain-princess.jpg" --name "rain-princess" --steps 800 --output-root "ForJyn_Workbench\outputs"
```

The backend prints a final machine-readable line:

```text
FORJYN_OUTPUT_DIR=C:\...\ForJyn_Workbench\outputs\YYYYMMDD-HHMMSS-style-name
```

## Troubleshooting

### Training Completed But ONNX Export Failed

If training finishes but ONNX export or apply fails, the local `checkpoint.pth` may still be usable. You can recover the job without retraining:

```powershell
.\.venv\Scripts\python tools\forjyn_workbench.py recover-job --model-dir "ForJyn_Workbench\technical\models\YYYYMMDD-HHMMSS-style-name" --content "C:\path\content.webp" --output-dir "ForJyn_Workbench\outputs\YYYYMMDD-HHMMSS-style-name"
```

This recovery command exports ONNX from the existing checkpoint, validates the ONNX model, applies it to the original content image, and writes output files into the existing output folder.

On Windows, some tools can print Unicode status characters during ONNX export. ForJyn forces UTF-8-safe subprocess handling and quiet export capture so those console characters do not break the job.

## Regeneration

Regeneration is intended to be functionally similar, not byte-for-byte identical. Quick tests are not final-quality models.

## Release

Release packaging is not handled yet. It will be done later, after the workbench is stable and generates good ONNX model candidates.
