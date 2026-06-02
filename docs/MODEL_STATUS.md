# Model Status

This table tracks factory readiness. Model binaries, checkpoints, ONNX exports, validation JSON, and images remain local and untracked.

The active user-facing path is now ForJyn Workbench. Factory entries below are retained as baseline/model-history context, not as a release plan.

| Model | Type | Style Image | Checkpoint | Export | Validation | Notes |
|---|---|---|---|---|---|---|
| `candy` | upstream-baseline | `images/style-images/candy.jpg` | `.local/upstream-yakhyo-v1.0/candy.pth` validated locally | dynamic shape-preserving export validated locally | realistic H/W CPU validation passed | Upstream baseline, not Forjyn-owned |
| `mosaic` | upstream-baseline | `images/style-images/mosaic.jpg` | not downloaded | not run | not run | Ready in manifest; requires explicit checkpoint download approval |
| `rain-princess` | upstream-baseline | `images/style-images/rain-princess.jpg` | not downloaded | not run | not run | Ready in manifest; requires explicit checkpoint download approval |
| `udnie` | upstream-baseline | `images/style-images/udnie.jpg` | not downloaded | not run | not run | Ready in manifest; requires explicit checkpoint download approval |

## Forjyn-Owned Batch Requirements

Before adding a Forjyn-owned model entry, prepare:

- a legal style image stored locally
- provenance and license notes for the style image
- a legal training dataset path
- intended model id and display name
- validation expectations and known limitations

Do not train or export Forjyn-owned models until these inputs are available.
