import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "ForJyn_Workbench"
CONTENT_DIR = WORKBENCH / "inputs"
STYLE_DIR = WORKBENCH / "references"
OUTPUT_DIR = WORKBENCH / "outputs"
TECHNICAL_DIR = WORKBENCH / "technical"
MODELS_DIR = TECHNICAL_DIR / "models"
REPORTS_DIR = TECHNICAL_DIR / "reports"
CACHE_DIR = TECHNICAL_DIR / "cache"
LOGS_DIR = TECHNICAL_DIR / "logs"
PREVIEWS_DIR = TECHNICAL_DIR / "previews"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VALIDATION_SHAPES = [
    (1, 3, 1090, 1280),
    (1, 3, 1080, 1920),
    (1, 3, 1920, 1080),
    (1, 3, 1091, 1279),
]

GUIDES = {
    CONTENT_DIR / "PUT_OPTIONAL_CONTENT_PHOTOS_HERE.txt": "Optional: put photos you want to transform in this folder.\nThe GUI can also choose photos from any local path.\nSupported formats: jpg, jpeg, png, webp, bmp.\n",
    STYLE_DIR / "PUT_OPTIONAL_STYLE_REFERENCES_HERE.txt": "Optional: put style/reference images in this folder.\nThe GUI can also choose style images from any local path.\n",
    OUTPUT_DIR / "RESULTS_WILL_APPEAR_HERE.txt": "ForJyn writes final user-facing job outputs here.\n",
}


def repo_path(path):
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (ROOT / candidate).resolve()


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(Path(path).resolve()).replace("\\", "/")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def read_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_dirs():
    for path in [CONTENT_DIR, STYLE_DIR, OUTPUT_DIR, TECHNICAL_DIR, MODELS_DIR, REPORTS_DIR, CACHE_DIR, LOGS_DIR, PREVIEWS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def image_paths(path):
    root = repo_path(path)
    if not root.exists():
        return []
    if root.is_file():
        return [root] if root.suffix.lower() in IMAGE_EXTENSIONS else []
    items = []
    for child in sorted(root.iterdir()):
        if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
            items.append(child.resolve())
    return items


def image_info(path):
    with Image.open(path) as image:
        return {"path": rel(path), "width": image.width, "height": image.height, "mode": image.mode}


def slugify(value):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "forjyn-style"


def model_slug(model_id):
    return re.sub(r"^\d{8}-", "", model_id)


def dated_model_id(name):
    return f"{date.today().strftime('%Y%m%d')}-{slugify(name)}"


def timestamped_job_id(name):
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(name)}"


def unique_model_id(base):
    model_id = base
    index = 2
    while (MODELS_DIR / model_id).exists():
        model_id = f"{base}-{index:02d}"
        index += 1
    return model_id


def unique_job_id(base, output_root):
    job_id = base
    index = 2
    while (MODELS_DIR / job_id).exists() or (output_root / job_id).exists():
        job_id = f"{base}-{index:02d}"
        index += 1
    return job_id


def model_dir(path):
    resolved = repo_path(path)
    if not resolved.exists():
        raise SystemExit(f"Model directory missing: {resolved}")
    return resolved


def checkpoint_path(path):
    checkpoint = path / "checkpoint.pth"
    if not checkpoint.exists():
        raise SystemExit(f"Checkpoint missing: {checkpoint}")
    return checkpoint


def primary_onnx_path(path):
    preferred = path / f"{path.name}.onnx"
    if preferred.exists():
        return preferred
    fallback = path / "model.onnx"
    if fallback.exists():
        return fallback
    raise SystemExit(f"ONNX model missing in: {path}")


def safe_clear_dir(path):
    resolved = Path(path).resolve()
    cache_root = CACHE_DIR.resolve()
    if cache_root not in resolved.parents and resolved != cache_root:
        raise RuntimeError(f"Refusing to clear path outside workbench cache: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def local_env():
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["TORCH_HOME"] = str(CACHE_DIR / "torch")
    env["XDG_CACHE_HOME"] = str(CACHE_DIR / "xdg")
    (CACHE_DIR / "torch").mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "xdg").mkdir(parents=True, exist_ok=True)
    return env


def command_display(command):
    return [rel(part) if str(part).startswith(str(ROOT)) else str(part) for part in command]


def cmd_init(_args):
    ensure_dirs()
    for path, text in GUIDES.items():
        if not path.exists():
            path.write_text(text, encoding="utf-8")
    payload = {
        "workbench": rel(WORKBENCH),
        "content_images": rel(CONTENT_DIR),
        "style_images": rel(STYLE_DIR),
        "outputs": rel(OUTPUT_DIR),
        "technical": rel(TECHNICAL_DIR),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def scan_payload():
    ensure_dirs()
    content = [image_info(path) for path in image_paths(CONTENT_DIR)]
    styles = [image_info(path) for path in image_paths(STYLE_DIR)]
    today = date.today().strftime("%Y%m%d")
    planned = [
        {
            "style": item["path"],
            "model_id": f"{today}-{slugify(Path(item['path']).stem)}",
            "outputs_dir": rel(OUTPUT_DIR / f"{today}-{slugify(Path(item['path']).stem)}"),
        }
        for item in styles
    ]
    problems = []
    if not content:
        problems.append("No content images found in ForJyn_Workbench/inputs.")
    if not styles:
        problems.append("No style images found in ForJyn_Workbench/references.")
    if content and len(content) < 8:
        problems.append("Very few content images found; training will be a pilot, not a final-quality model.")
    return {
        "content_count": len(content),
        "style_count": len(styles),
        "content_images": content,
        "style_images": styles,
        "planned_models": planned,
        "problems": problems,
    }


def cmd_scan(_args):
    payload = scan_payload()
    print(f"Content images: {payload['content_count']}")
    for item in payload["content_images"]:
        print(f"  - {item['path']} ({item['width']}x{item['height']})")
    print(f"Style images: {payload['style_count']}")
    for item in payload["style_images"]:
        print(f"  - {item['path']} ({item['width']}x{item['height']})")
    print("Planned model names:")
    for item in payload["planned_models"]:
        print(f"  - {item['model_id']} from {item['style']}")
    if payload["problems"]:
        print("Problems:")
        for problem in payload["problems"]:
            print(f"  - {problem}")
    write_json(REPORTS_DIR / "scan.json", payload)


def generate_synthetic_dataset(out_dir, count=24, size=512, seed=20260602):
    rng = np.random.default_rng(seed)
    items = []
    for index in range(count):
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        arr = np.zeros((size, size, 3), dtype=np.uint8)
        arr[..., 0] = ((xx / size) * 160 + rng.integers(0, 80)) % 255
        arr[..., 1] = ((yy / size) * 180 + rng.integers(10, 90)) % 255
        arr[..., 2] = (((xx + yy) / (size * 2)) * 220 + rng.integers(0, 50)) % 255
        image = Image.fromarray(arr, "RGB")
        draw = ImageDraw.Draw(image, "RGBA")
        for _ in range(12):
            color = tuple(int(v) for v in rng.integers(20, 240, size=3)) + (int(rng.integers(70, 180)),)
            x0 = int(rng.integers(0, size))
            y0 = int(rng.integers(0, size))
            x1 = x0 + int(rng.integers(40, 220))
            y1 = y0 + int(rng.integers(40, 220))
            if rng.random() < 0.5:
                draw.ellipse([x0, y0, x1, y1], fill=color)
            else:
                draw.rectangle([x0, y0, x1, y1], fill=color)
        path = out_dir / f"synthetic-{index + 1:04d}.jpg"
        image.save(path, quality=94)
        items.append({"path": rel(path), "width": size, "height": size})
    return items


def prepare_training_dataset(model_id, allow_synthetic_fallback, content_sources=None):
    content = [repo_path(path) for path in content_sources] if content_sources else image_paths(CONTENT_DIR)
    dataset_root = CACHE_DIR / "datasets" / model_id
    class_dir = dataset_root / "content"
    safe_clear_dir(dataset_root)
    class_dir.mkdir(parents=True, exist_ok=True)
    source = "selected-content-images" if content_sources else "content-images"
    if content:
        for index, path in enumerate(content, start=1):
            if not path.exists():
                raise SystemExit(f"Content image missing: {path}")
            target = class_dir / f"content-{index:04d}{path.suffix.lower()}"
            shutil.copy2(path, target)
    elif allow_synthetic_fallback:
        source = "synthetic-fallback"
        generate_synthetic_dataset(class_dir)
    else:
        raise SystemExit(
            "No content images found. Add photos to ForJyn_Workbench/inputs/ "
            "or pass --allow-synthetic-fallback for a pilot-only synthetic test."
        )
    count = len(image_paths(class_dir))
    if count == 0:
        raise SystemExit("Training dataset preparation produced no images.")
    return dataset_root, count, source


def write_style_metadata(model_path, style_path):
    info = image_info(style_path)
    payload = {
        "style_image": info,
        "sha256": sha256(style_path),
        "source": "user-provided-local-workbench-style",
        "license_status": "user-responsibility",
        "note": "Style images are local workbench inputs and are not committed.",
    }
    write_json(model_path / "style-source-metadata.json", payload)
    return payload


def train_one(args):
    ensure_dirs()
    style = repo_path(args.style)
    if not style.exists():
        raise SystemExit(f"Style image missing: {style}")
    name = args.name or style.stem
    if getattr(args, "model_id", None):
        model_id = args.model_id
    else:
        base_id = dated_model_id(name)
        model_id = unique_model_id(base_id)
    path = MODELS_DIR / model_id
    if path.exists() and not getattr(args, "reuse_model_dir", False):
        raise SystemExit(f"Model directory already exists: {path}")
    path.mkdir(parents=True, exist_ok=True)
    dataset, image_count, dataset_source = prepare_training_dataset(
        model_id,
        args.allow_synthetic_fallback,
        getattr(args, "content_sources", None),
    )
    batches_per_epoch = max(1, math.ceil(image_count / max(1, args.batch_size)))
    epochs = max(1, math.ceil(args.steps / batches_per_epoch))
    checkpoint = path / "checkpoint.pth"
    command = [
        sys.executable,
        str(ROOT / "train.py"),
        "--dataset",
        str(dataset),
        "--style-image",
        str(style),
        "--save-model",
        str(path),
        "--save-name",
        checkpoint.name,
        "--epochs",
        str(epochs),
        "--batch-size",
        str(args.batch_size),
        "--image-size",
        str(args.image_size),
        "--style-size",
        str(args.style_size),
        "--max-steps",
        str(args.steps),
        "--num-workers",
        "0",
        "--device",
        args.device,
        "--log-interval",
        "20",
    ]
    log = {
        "model_id": model_id,
        "status": "running",
        "started_at_unix": time.time(),
        "command": command_display(command),
        "style_image": rel(style),
        "dataset": rel(dataset),
        "dataset_source": dataset_source,
        "content_image_count": image_count,
        "pilot_warning": image_count < 8,
        "training": {
            "requested_steps": args.steps,
            "computed_epochs": epochs,
            "image_size": args.image_size,
            "style_size": args.style_size,
            "batch_size": args.batch_size,
            "device": args.device,
        },
        "note": "Training creates a PyTorch checkpoint first; ONNX is exported afterward.",
    }
    if image_count < 8:
        print("WARNING: very few content images found. This training run is a pilot, not a final-quality model.")
    if dataset_source == "synthetic-fallback":
        print("WARNING: using synthetic fallback content. This is only for a technical pilot test.")
    print(f"Training model {model_id} from style {rel(style)}")
    print(f"Checkpoint will be saved to {rel(checkpoint)}")
    write_json(path / "training-log.json", log)
    completed = subprocess.run(command, cwd=ROOT, env=local_env(), check=False)
    log["ended_at_unix"] = time.time()
    log["seconds"] = round(log["ended_at_unix"] - log["started_at_unix"], 3)
    log["returncode"] = completed.returncode
    log["status"] = "passed" if completed.returncode == 0 else "failed"
    if checkpoint.exists():
        log["checkpoint"] = {"path": rel(checkpoint), "bytes": checkpoint.stat().st_size, "sha256": sha256(checkpoint)}
    write_json(path / "training-log.json", log)
    style_metadata = write_style_metadata(path, style)
    model_card = {
        "model_id": model_id,
        "name": name,
        "status": "trained-local-pilot",
        "quality_status": "not-final-needs-human-review",
        "checkpoint": log.get("checkpoint"),
        "style_source_metadata": rel(path / "style-source-metadata.json"),
        "training_log": rel(path / "training-log.json"),
        "style": style_metadata,
        "regeneration": "functionally similar regeneration; not byte-identical reproduction",
    }
    write_json(path / "model-card.json", model_card)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print(json.dumps({"model_dir": rel(path), "checkpoint": rel(checkpoint), "pilot_warning": image_count < 8}, indent=2, sort_keys=True))
    return path


def load_transformer(checkpoint):
    import torch

    sys.path.insert(0, str(ROOT))
    from model import TransformerNet

    transformer = TransformerNet()
    state_dict = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if isinstance(state_dict, dict) and "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]
    result = transformer.load_state_dict(state_dict, strict=False)
    if result.missing_keys or result.unexpected_keys:
        raise RuntimeError(f"Checkpoint mismatch: missing={result.missing_keys}, unexpected={result.unexpected_keys}")
    transformer.eval()
    return transformer, result


def shape_preserving_wrapper(transformer):
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


def export_one(args):
    import torch
    from torch.export import Dim

    path = model_dir(args.model_dir)
    checkpoint = checkpoint_path(path)
    transformer, load_result = load_transformer(checkpoint)
    wrapper = shape_preserving_wrapper(transformer)
    primary = path / f"{path.name}.onnx"
    alias = path / "model.onnx"
    started = time.time()
    torch.onnx.export(
        wrapper,
        (torch.randn(1, 3, 256, 320),),
        str(primary),
        input_names=["input"],
        output_names=["output"],
        dynamic_shapes={
            "input": {
                0: Dim("batch", min=1),
                2: Dim("height", min=16),
                3: Dim("width", min=16),
            }
        },
        opset_version=18,
    )
    if primary.exists():
        shutil.copy2(primary, alias)
    payload = {
        "model_id": path.name,
        "checkpoint": rel(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "onnx": rel(primary),
        "onnx_sha256": sha256(primary),
        "model_alias": rel(alias) if alias.exists() else None,
        "sidecar": rel(Path(str(primary) + ".data")) if Path(str(primary) + ".data").exists() else None,
        "sidecar_sha256": sha256(Path(str(primary) + ".data")) if Path(str(primary) + ".data").exists() else None,
        "opset": 18,
        "load_missing_keys": load_result.missing_keys,
        "load_unexpected_keys": load_result.unexpected_keys,
        "seconds": round(time.time() - started, 3),
        "wrapper": "dynamic final crop to input H/W",
    }
    write_json(path / "export-metadata.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return path


def validate_one(args):
    import onnx
    import onnxruntime as ort

    path = model_dir(args.model_dir)
    onnx_path = primary_onnx_path(path)
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    rng = np.random.default_rng(args.seed)
    results = []
    for shape in VALIDATION_SHAPES:
        tensor = rng.standard_normal(shape, dtype=np.float32)
        started = time.perf_counter()
        output = session.run(None, {input_name: tensor})[0]
        seconds = time.perf_counter() - started
        result = {
            "input_shape": list(tensor.shape),
            "output_shape": list(output.shape),
            "seconds": round(seconds, 3),
            "preserves_hw": output.shape[2:] == tensor.shape[2:],
        }
        results.append(result)
        print(json.dumps(result, sort_keys=True))
    payload = {
        "model_id": path.name,
        "onnx": rel(onnx_path),
        "input_name": input_name,
        "output_name": output_name,
        "opsets": [f"{op.domain or 'ai.onnx'}:{op.version}" for op in onnx_model.opset_import],
        "results": results,
        "all_preserve_hw": all(item["preserves_hw"] for item in results),
    }
    write_json(path / "validation.json", payload)
    if not payload["all_preserve_hw"]:
        raise SystemExit("Validation failed: at least one output did not preserve H/W.")
    return path


def pil_to_tensor(image):
    arr = np.asarray(image.convert("RGB")).astype(np.float32)
    return arr.transpose(2, 0, 1)[None, ...]


def tensor_to_pil(tensor):
    arr = tensor[0].transpose(1, 2, 0)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def apply_image(model_path, content_path, output_dir=None, style_slug=None):
    import onnxruntime as ort

    onnx_path = primary_onnx_path(model_path)
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    original = Image.open(content_path).convert("RGB")
    started = time.perf_counter()
    output_tensor = session.run(None, {input_name: pil_to_tensor(original)})[0]
    output = tensor_to_pil(output_tensor)
    if output.size != original.size:
        raise RuntimeError(f"Output size mismatch: input={original.size}, output={output.size}")
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR / model_path.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{content_path.stem}__{style_slug or model_slug(model_path.name)}.jpg"
    output.save(out_path, quality=95)
    return {
        "model_id": model_path.name,
        "content": rel(content_path),
        "output": rel(out_path),
        "input_size": list(original.size),
        "output_size": list(output.size),
        "preserves_size": output.size == original.size,
        "seconds": round(time.perf_counter() - started, 3),
        "sha256": sha256(out_path),
    }


def apply_one(args):
    path = model_dir(args.model_dir)
    content = repo_path(args.content)
    if not content.exists():
        raise SystemExit(f"Content image missing: {content}")
    result = apply_image(path, content)
    print(json.dumps(result, indent=2, sort_keys=True))
    return [result]


def apply_batch(args):
    path = model_dir(args.model_dir)
    content = image_paths(CONTENT_DIR)
    if not content:
        raise SystemExit(f"No content images found in {CONTENT_DIR}")
    results = []
    for item in content:
        result = apply_image(path, item)
        results.append(result)
        print(json.dumps(result, sort_keys=True))
    write_json(path / "apply-results.json", {"model_id": path.name, "results": results})
    return results


def contact_sheet(model_path, results):
    if not results:
        return None
    tiles = []
    for result in results:
        input_image = Image.open(ROOT / result["content"]).convert("RGB")
        output_image = Image.open(ROOT / result["output"]).convert("RGB")
        tiles.append(("Input", input_image))
        tiles.append((model_slug(model_path.name), output_image))
    tile_w = 260
    tile_h = 210
    header_h = 30
    cols = 2
    rows = len(results)
    sheet = Image.new("RGB", (cols * tile_w, rows * (tile_h + header_h)), (12, 12, 14))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(tiles):
        x = (index % cols) * tile_w
        y = (index // cols) * (tile_h + header_h)
        draw.text((x + 8, y + 8), label[:34], fill=(245, 245, 245))
        thumb = image.copy()
        thumb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        bg = Image.new("RGB", (tile_w, tile_h), (22, 22, 28))
        bg.paste(thumb, ((tile_w - thumb.width) // 2, (tile_h - thumb.height) // 2))
        sheet.paste(bg, (x, y + header_h))
    path = PREVIEWS_DIR / f"{model_path.name}-contact-sheet.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=95)
    return path


def run_one(args):
    trained = train_one(args)
    export_one(argparse.Namespace(model_dir=str(trained)))
    validate_one(argparse.Namespace(model_dir=str(trained), seed=args.seed))
    results = apply_batch(argparse.Namespace(model_dir=str(trained)))
    sheet = contact_sheet(trained, results)
    print(json.dumps({"model_dir": rel(trained), "contact_sheet": rel(sheet) if sheet else None}, indent=2, sort_keys=True))
    return trained


def output_root_path(value):
    output_root = repo_path(value or OUTPUT_DIR)
    resolved_output = output_root.resolve()
    resolved_workbench = WORKBENCH.resolve()
    if resolved_output != resolved_workbench and resolved_workbench not in resolved_output.parents:
        raise SystemExit(f"Output root must stay inside {WORKBENCH}: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


def copy_if_exists(source, target):
    source = Path(source)
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target
    return None


def write_output_readme(job_dir, job_id, style, content):
    text = f"""ForJyn output folder

Job: {job_id}
Content photo: {content.name}
Style/reference image: {style.name}

Files in this folder are local generated artifacts. Review quality before sharing.
ONNX is not trained directly: ForJyn trained a PyTorch checkpoint, exported ONNX, validated it, then applied ONNX to the content photo.
The styled image should preserve the original content width and height.
"""
    (job_dir / "README_OUTPUT.txt").write_text(text, encoding="utf-8")


def run_job(args):
    ensure_dirs()
    content = repo_path(args.content)
    style = repo_path(args.style)
    if not content.exists() or not content.is_file():
        raise SystemExit(f"Content image missing: {content}")
    if content.suffix.lower() not in IMAGE_EXTENSIONS:
        raise SystemExit(f"Unsupported content image format: {content.suffix}")
    if not style.exists() or not style.is_file():
        raise SystemExit(f"Style/reference image missing: {style}")
    if style.suffix.lower() not in IMAGE_EXTENSIONS:
        raise SystemExit(f"Unsupported style/reference image format: {style.suffix}")

    style_slug = slugify(args.name or style.stem)
    output_root = output_root_path(args.output_root)
    job_id = unique_job_id(timestamped_job_id(style_slug), output_root)
    job_dir = output_root / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    print(f"ForJyn job started: {job_id}", flush=True)
    print(f"Content photo: {rel(content)}", flush=True)
    print(f"Style/reference image: {rel(style)}", flush=True)
    print(f"Output folder: {rel(job_dir)}", flush=True)

    train_args = argparse.Namespace(
        style=str(style),
        name=style_slug,
        model_id=job_id,
        reuse_model_dir=False,
        content_sources=[str(content)],
        steps=args.steps,
        image_size=args.image_size,
        batch_size=args.batch_size,
        style_size=args.style_size,
        device=args.device,
        allow_synthetic_fallback=False,
        seed=args.seed,
    )

    print("Phase: training PyTorch TransformerNet checkpoint", flush=True)
    trained = train_one(train_args)

    print("Phase: exporting dynamic H/W shape-preserving ONNX", flush=True)
    export_one(argparse.Namespace(model_dir=str(trained)))

    print("Phase: validating ONNX Runtime CPU output shapes", flush=True)
    validate_one(argparse.Namespace(model_dir=str(trained), seed=args.seed))

    print("Phase: applying ONNX to content photo", flush=True)
    apply_result = apply_image(trained, content, output_dir=job_dir, style_slug=style_slug)
    write_json(job_dir / "apply-result.json", apply_result)

    primary = primary_onnx_path(trained)
    final_onnx = copy_if_exists(primary, job_dir / f"{job_id}.onnx")
    primary_sidecar = Path(str(primary) + ".data")
    final_sidecar = copy_if_exists(primary_sidecar, job_dir / f"{job_id}.onnx.data")
    for filename in [
        "model-card.json",
        "validation.json",
        "training-log.json",
        "export-metadata.json",
        "style-source-metadata.json",
    ]:
        copy_if_exists(trained / filename, job_dir / filename)

    job_summary = {
        "job_id": job_id,
        "content": rel(content),
        "style": rel(style),
        "output_dir": rel(job_dir),
        "technical_model_dir": rel(trained),
        "onnx": rel(final_onnx) if final_onnx else None,
        "sidecar": rel(final_sidecar) if final_sidecar else None,
        "apply_result": apply_result,
        "quality_status": "not-final-needs-human-review",
        "regeneration": "functionally similar regeneration; not byte-identical reproduction",
    }
    write_json(job_dir / "job-summary.json", job_summary)
    write_output_readme(job_dir, job_id, style, content)

    print("Phase: complete", flush=True)
    print(json.dumps(job_summary, indent=2, sort_keys=True), flush=True)
    print(f"FORJYN_OUTPUT_DIR={job_dir.resolve()}", flush=True)
    return job_dir


def run_all(args):
    styles = image_paths(STYLE_DIR)
    if not styles:
        raise SystemExit(f"No style images found in {STYLE_DIR}")
    models = []
    for style in styles:
        run_args = argparse.Namespace(
            style=str(style),
            name=style.stem,
            steps=args.steps,
            image_size=args.image_size,
            batch_size=args.batch_size,
            style_size=args.style_size,
            device=args.device,
            allow_synthetic_fallback=args.allow_synthetic_fallback,
            seed=args.seed,
        )
        models.append(run_one(run_args))
    print(json.dumps({"models": [rel(path) for path in models]}, indent=2, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description="ForJyn Workbench: train, export, validate, and apply local style models")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create the local workbench folders")
    init.set_defaults(func=cmd_init)

    scan = subparsers.add_parser("scan", help="Scan content/style folders")
    scan.set_defaults(func=cmd_scan)

    def add_training_args(command):
        command.add_argument("--steps", type=int, default=800)
        command.add_argument("--image-size", type=int, default=384)
        command.add_argument("--batch-size", type=int, default=1)
        command.add_argument("--style-size", type=int, default=512)
        command.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
        command.add_argument("--allow-synthetic-fallback", action="store_true")
        command.add_argument("--seed", type=int, default=20260602)

    train = subparsers.add_parser("train-one", help="Train one PyTorch checkpoint from one style image")
    train.add_argument("--style", required=True)
    train.add_argument("--name")
    add_training_args(train)
    train.set_defaults(func=lambda args: train_one(args))

    export = subparsers.add_parser("export-one", help="Export one checkpoint to dynamic shape-preserving ONNX")
    export.add_argument("--model-dir", required=True)
    export.set_defaults(func=lambda args: export_one(args))

    validate = subparsers.add_parser("validate-one", help="Validate one ONNX model on realistic tensor shapes")
    validate.add_argument("--model-dir", required=True)
    validate.add_argument("--seed", type=int, default=20260602)
    validate.set_defaults(func=lambda args: validate_one(args))

    apply_single = subparsers.add_parser("apply-one", help="Apply one ONNX model to one content image")
    apply_single.add_argument("--model-dir", required=True)
    apply_single.add_argument("--content", required=True)
    apply_single.set_defaults(func=lambda args: apply_one(args))

    apply_all = subparsers.add_parser("apply-batch", help="Apply one ONNX model to all content images")
    apply_all.add_argument("--model-dir", required=True)
    apply_all.set_defaults(func=lambda args: apply_batch(args))

    run = subparsers.add_parser("run-one", help="Train, export, validate, apply batch, and create contact sheet")
    run.add_argument("--style", required=True)
    run.add_argument("--name")
    add_training_args(run)
    run.set_defaults(func=lambda args: run_one(args))

    job = subparsers.add_parser("run-job", help="GUI-friendly one-content/one-style workflow")
    job.add_argument("--content", required=True)
    job.add_argument("--style", required=True)
    job.add_argument("--name")
    job.add_argument("--output-root", default=str(OUTPUT_DIR))
    add_training_args(job)
    job.set_defaults(func=lambda args: run_job(args))

    run_all_command = subparsers.add_parser("run-all", help="Run the full workflow for all style images")
    add_training_args(run_all_command)
    run_all_command.set_defaults(func=lambda args: run_all(args))

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
