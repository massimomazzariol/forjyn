import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "configs" / "model_manifest.json"
DEFAULT_LOCAL_ROOT = "workbench/_runtime/models/model-factory"


def load_manifest(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def repo_path(path):
    return (ROOT / path).resolve()


def local_model_dir(manifest, model_id):
    return repo_path(manifest.get("local_root", DEFAULT_LOCAL_ROOT)) / model_id


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def find_model(manifest, model_id):
    for model in manifest.get("models", []):
        if model.get("id") == model_id:
            return model
    raise SystemExit(f"Unknown model id: {model_id}")


def manifest_shapes(manifest):
    return [tuple(shape) for shape in manifest.get("validation_shapes_nchw", [])]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def cmd_check(args):
    manifest = load_manifest(args.manifest)
    errors = []
    required = [
        "id",
        "name",
        "type",
        "status",
        "style_image",
        "style_provenance",
        "style_license",
        "checkpoint",
        "export",
        "validation",
    ]
    ids = set()
    for model in manifest.get("models", []):
        for key in required:
            if key not in model:
                errors.append(f"{model.get('id', '<missing id>')}: missing {key}")
        model_id = model.get("id")
        if model_id in ids:
            errors.append(f"duplicate model id: {model_id}")
        ids.add(model_id)
        if model.get("type") not in {"upstream-baseline", "forjyn-owned"}:
            errors.append(f"{model_id}: invalid type {model.get('type')}")
        style_image = repo_path(model.get("style_image", ""))
        if not style_image.exists():
            errors.append(f"{model_id}: style image missing: {style_image}")

    for shape in manifest_shapes(manifest):
        if len(shape) != 4:
            errors.append(f"invalid validation shape: {shape}")

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        raise SystemExit(1)

    print(f"OK manifest {args.manifest}")
    print(f"models {len(manifest.get('models', []))}")
    print(f"validation_shapes {len(manifest_shapes(manifest))}")


def cmd_status(args):
    manifest = load_manifest(args.manifest)
    print("id\ttype\tstatus\tcheckpoint\texport\tvalidation")
    for model in manifest.get("models", []):
        checkpoint = repo_path(model["checkpoint"]["local_path"])
        export = repo_path(model["export"]["local_path"])
        print(
            "\t".join(
                [
                    model["id"],
                    model["type"],
                    model["status"],
                    "present" if checkpoint.exists() else "missing",
                    "present" if export.exists() else "missing",
                    model["validation"]["status"],
                ]
            )
        )


def load_transformer(checkpoint_path):
    import torch

    sys.path.insert(0, str(ROOT))
    from model import TransformerNet

    transformer = TransformerNet()
    state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if isinstance(state_dict, dict) and "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]
    result = transformer.load_state_dict(state_dict, strict=False)
    if result.missing_keys or result.unexpected_keys:
        raise RuntimeError(
            "Checkpoint is not an exact TransformerNet match: "
            f"missing={result.missing_keys}, unexpected={result.unexpected_keys}"
        )
    transformer.eval()
    return transformer, result


def build_wrapper(transformer):
    import torch

    class ShapePreservingTransformerNet(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.transformer = model

        def forward(self, input):
            height = input.shape[-2]
            width = input.shape[-1]
            output = self.transformer(input)
            return output[..., :height, :width]

    return ShapePreservingTransformerNet(transformer).eval()


def cmd_export(args):
    import torch
    from torch.export import Dim

    manifest = load_manifest(args.manifest)
    model = find_model(manifest, args.model_id)
    checkpoint_path = repo_path(model["checkpoint"]["local_path"])
    export_path = repo_path(model["export"]["local_path"])

    if not checkpoint_path.exists():
        raise SystemExit(f"Checkpoint missing: {checkpoint_path}")

    transformer, load_result = load_transformer(checkpoint_path)
    wrapper = build_wrapper(transformer)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.randn(1, 3, 256, 320)

    torch.onnx.export(
        wrapper,
        (dummy,),
        str(export_path),
        input_names=["input"],
        output_names=["output"],
        dynamic_shapes={
            "input": {
                0: Dim("batch", min=1),
                2: Dim("height", min=16),
                3: Dim("width", min=16),
            }
        },
        opset_version=int(model["export"].get("opset", 18)),
    )

    metadata = {
        "model_id": model["id"],
        "checkpoint_path": model["checkpoint"]["local_path"],
        "checkpoint_sha256": sha256(checkpoint_path),
        "export_path": model["export"]["local_path"],
        "sidecar_path": f"{model['export']['local_path']}.data",
        "load_missing_keys": load_result.missing_keys,
        "load_unexpected_keys": load_result.unexpected_keys,
        "opset": int(model["export"].get("opset", 18)),
        "wrapper": "dynamic final crop to input H/W",
    }
    write_json(local_model_dir(manifest, model["id"]) / "metadata" / "export.json", metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))


def cmd_validate(args):
    import numpy as np
    import onnx
    import onnxruntime as ort

    manifest = load_manifest(args.manifest)
    model = find_model(manifest, args.model_id)
    export_path = repo_path(model["export"]["local_path"])
    if not export_path.exists():
        raise SystemExit(f"Export missing: {export_path}")

    onnx_model = onnx.load(export_path)
    onnx.checker.check_model(onnx_model)
    session = ort.InferenceSession(str(export_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    rng = np.random.default_rng(args.seed)

    results = []
    for shape in manifest_shapes(manifest):
        x = rng.standard_normal(shape, dtype=np.float32)
        started = time.perf_counter()
        y = session.run(None, {input_name: x})[0]
        seconds = time.perf_counter() - started
        result = {
            "input_shape": list(x.shape),
            "output_shape": list(y.shape),
            "seconds": round(seconds, 3),
            "preserves_hw": y.shape[2:] == x.shape[2:],
        }
        results.append(result)
        print(json.dumps(result, sort_keys=True))

    payload = {
        "model_id": model["id"],
        "export_path": model["export"]["local_path"],
        "input_name": input_name,
        "output_name": output_name,
        "opsets": [f"{op.domain or 'ai.onnx'}:{op.version}" for op in onnx_model.opset_import],
        "results": results,
        "all_preserve_hw": all(item["preserves_hw"] for item in results),
    }
    write_json(local_model_dir(manifest, model["id"]) / "metadata" / "validation.json", payload)
    if not payload["all_preserve_hw"]:
        raise SystemExit("Validation failed: at least one shape did not preserve H/W")


def cmd_train(args):
    manifest = load_manifest(args.manifest)
    model = find_model(manifest, args.model_id)
    style_image = repo_path(model["style_image"])
    save_dir = local_model_dir(manifest, model["id"]) / "checkpoints"
    save_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "train.py"),
        "--dataset",
        str(Path(args.dataset).resolve()),
        "--style-image",
        str(style_image),
        "--save-model",
        str(save_dir),
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--image-size",
        str(args.image_size),
    ]
    if args.dry_run:
        print(" ".join(command))
        return
    subprocess.run(command, cwd=ROOT, check=True)


def cmd_batch(args):
    manifest = load_manifest(args.manifest)
    model_ids = args.models.split(",") if args.models else [model["id"] for model in manifest.get("models", [])]
    steps = args.steps.split(",")
    for model_id in model_ids:
        print(f"== {model_id} ==")
        if "export" in steps:
            cmd_export(argparse.Namespace(manifest=args.manifest, model_id=model_id))
        if "validate" in steps:
            cmd_validate(argparse.Namespace(manifest=args.manifest, model_id=model_id, seed=args.seed))


def build_parser():
    parser = argparse.ArgumentParser(description="Forjyn local model factory")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to model manifest JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Validate manifest structure")
    check.set_defaults(func=cmd_check)

    status = subparsers.add_parser("status", help="Print model status table")
    status.set_defaults(func=cmd_status)

    train = subparsers.add_parser("train", help="Train one model into workbench/_runtime/models")
    train.add_argument("model_id")
    train.add_argument("--dataset", required=True)
    train.add_argument("--epochs", type=int, default=1)
    train.add_argument("--batch-size", type=int, default=4)
    train.add_argument("--image-size", type=int, default=256)
    train.add_argument("--dry-run", action="store_true")
    train.set_defaults(func=cmd_train)

    export = subparsers.add_parser("export", help="Export one checkpoint to dynamic shape-preserving ONNX")
    export.add_argument("model_id")
    export.set_defaults(func=cmd_export)

    validate = subparsers.add_parser("validate", help="Validate one ONNX export on manifest shapes")
    validate.add_argument("model_id")
    validate.add_argument("--seed", type=int, default=123)
    validate.set_defaults(func=cmd_validate)

    batch = subparsers.add_parser("batch", help="Run export/validate steps for models in the manifest")
    batch.add_argument("--models", help="Comma-separated model ids. Defaults to all.")
    batch.add_argument("--steps", default="export,validate", help="Comma-separated steps: export,validate")
    batch.add_argument("--seed", type=int, default=123)
    batch.set_defaults(func=cmd_batch)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
