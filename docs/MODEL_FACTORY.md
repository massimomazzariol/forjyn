# Model Factory

Forjyn's model factory is a local batch workflow for the project rule: one filter = one model.

The factory keeps source control clean. The tracked repository stores the manifest, scripts, and documentation. Runtime artifacts stay under `.local/` and are not committed.

## Files

- `configs/model_manifest.json`: tracked registry of filters/models.
- `tools/forjyn_factory.py`: local CLI for checking the manifest, training one model, exporting one model, validating one model, and batch-running export/validation.
- `.local/model-factory/<model-id>/`: local output root for checkpoints, ONNX exports, and metadata.

## Manifest Fields

Each model entry must define:

- `id` and `name`
- `type`: `upstream-baseline` or `forjyn-owned`
- `status`
- `style_image`
- `style_provenance`
- `style_license`
- `checkpoint.local_path`
- `export.local_path`
- `validation.status`

The manifest validation shapes include realistic photo-like dimensions:

- `1 x 3 x 1090 x 1280`
- `1 x 3 x 1080 x 1920`
- `1 x 3 x 1920 x 1080`
- `1 x 3 x 1091 x 1279`

## Usage

Check the manifest:

```powershell
.\.venv\Scripts\python tools\forjyn_factory.py check
```

Print model status:

```powershell
.\.venv\Scripts\python tools\forjyn_factory.py status
```

Export one local checkpoint to dynamic shape-preserving ONNX:

```powershell
.\.venv\Scripts\python tools\forjyn_factory.py export candy
```

Validate one exported ONNX model on the manifest shapes:

```powershell
.\.venv\Scripts\python tools\forjyn_factory.py validate candy
```

Run export and validation for selected models:

```powershell
.\.venv\Scripts\python tools\forjyn_factory.py batch --models candy --steps export,validate
```

Training is available as an entrypoint, but should only be run with legal local datasets and style images:

```powershell
.\.venv\Scripts\python tools\forjyn_factory.py train <model-id> --dataset <local-dataset> --dry-run
```

Remove `--dry-run` only after the dataset and style reference are legally cleared.

## Export Contract

The factory exports `TransformerNet` through a shape-preserving wrapper:

- input: `1 x 3 x height x width`
- output: `1 x 3 x height x width`
- batch, height, and width are dynamic
- final dynamic crop restores the original H/W

The crop is shape correction only. It is not tiling, patch stitching, or upscaling.

## Forjyn-Owned Models

No Forjyn-owned model should be trained from unknown images or web-scraped style references. To launch the first real batch, add legal local style images and update the manifest with provenance and license notes.
