# Third-Party Notes

Forjyn is a fork of `yakhyo/fast-neural-style-transfer`.

The upstream README identifies the original project as MIT licensed. Preserve upstream attribution, license notes, and references when changing public documentation or source files.

## Upstream Origin

- Project: `yakhyo/fast-neural-style-transfer`
- Purpose: fast neural style transfer training, inference, ONNX export, and Flask deployment examples
- License: MIT, as stated in the upstream README inherited by this fork

## Upstream Release Artifacts

The upstream `v1.0` release provides PyTorch checkpoints for the inherited styles. Forjyn locally validated only `candy.pth` in `.local/`; this file is not tracked and must not be committed.

- Release: `https://github.com/yakhyo/fast-neural-style-transfer/releases/tag/v1.0`
- Local artifact: `.local/upstream-yakhyo-v1.0/candy.pth`
- Size: `6,738,604` bytes
- SHA256: `D458C378A796C7F2B332050995AD1B2D27DD5D73AC3C015C79E4C45D773AF282`
- Status: upstream baseline, not Forjyn-owned

Do not download or use additional upstream checkpoints without an explicit local validation task.

## References To Evaluate Later

These projects may be useful technical references, but they must be reviewed for license compatibility and implementation relevance before use:

- `kleinicke/onnx_small_style`
- `gnsmrky/pytorch-fast-neural-style-for-web`
- `pytorch/examples/fast_neural_style`

## Asset And Code Boundaries

Do not use proprietary competitor models, app assets, extracted code, copied presets, SVGs, or UI assets. Any third-party style reference, dataset, or model must have a clear legal basis before it is used for training, export, or documentation.
