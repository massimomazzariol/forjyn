# Third-Party Notes

ForJyn is based on `yakhyo/fast-neural-style-transfer`. The upstream README identifies the original project as MIT licensed. Preserve upstream attribution when changing public documentation or source files.

## Upstream Origin

- Project: `yakhyo/fast-neural-style-transfer`
- Purpose: fast neural style transfer training, inference, ONNX export, and deployment examples
- License: MIT, as stated by the inherited upstream README
- Status in ForJyn: source baseline and tracked demo weights

## Tracked Upstream Weights

The repository tracks inherited ONNX weights:

- `weights/candy.onnx`
- `weights/mosaic.onnx`
- `weights/rain-princess.onnx`
- `weights/udnie.onnx`

These are upstream baseline/demo artifacts. They are not ForJyn-owned generated models and should not be replaced by local Workbench output.

## Local Upstream Checkpoints

The upstream `v1.0` release provides PyTorch checkpoints. ForJyn previously validated `candy.pth` locally as a technical baseline. Any future local checkpoint copy belongs under `workbench/_runtime/models/` and must not be committed.

- Release: `https://github.com/yakhyo/fast-neural-style-transfer/releases/tag/v1.0`
- Validated local path convention: `workbench/_runtime/models/upstream-yakhyo-v1.0/candy.pth`
- SHA256 recorded during local validation: `D458C378A796C7F2B332050995AD1B2D27DD5D73AC3C015C79E4C45D773AF282`
- Status: upstream baseline, not ForJyn-owned

Do not download or use additional upstream checkpoints without an explicit validation task.

## Runtime And Training Dependencies

Core dependencies from `requirements.txt`:

- PyTorch and torchvision for training, model code, and VGG16 feature loss.
- ONNX, ONNX Script, and ONNX Runtime for export, validation, and inference.
- Pillow for image IO and WebP capability checks.
- NumPy for tensor/image handling.
- OpenCV Python and tqdm from the inherited workflow.
- Flask for the inherited deployment example.

VGG16 pretrained weights are used by the training loss path through torchvision. The local cache for those weights should remain local and untracked.

## DirectML

`onnxruntime-directml` is included in the Windows setup so ONNX inference can use DirectML when the local machine supports it. ForJyn keeps CPU fallback enabled. DirectML does not accelerate PyTorch training in this project.

Environment packages are not project artifacts.

## License Boundaries

Package licenses and model/dataset licenses should be checked before public release. If a license or asset provenance is not verified, document it as `not verified` and do not publish the resulting model as release-ready.

Do not use proprietary competitor models, app assets, extracted presets, copied UI assets, unclear datasets, or unclear manual references for training or public model distribution.
