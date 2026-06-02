import argparse
import json
import math
import random
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "ForJyn_Workbench" / "generated_references"
TEMP_DIR = REFERENCE_ROOT / "temp"
SAVED_DIR = REFERENCE_ROOT / "saved"
METADATA_DIR = REFERENCE_ROOT / "metadata"
CONTACT_SHEET_DIR = REFERENCE_ROOT / "contact_sheets"

DEFAULTS = {
    "count": 5,
    "width": 1024,
    "height": 1024,
    "intensity": 70,
    "glow": 75,
    "contrast": 65,
    "texture": 45,
    "complexity": 60,
}

PRESETS = {
    "neon-bloom": {
        "name": "Neon Bloom",
        "palette": ["#050617", "#171033", "#00E5FF", "#FF2ED1", "#7A4CFF", "#F8FBFF"],
        "description": "Night blue, cyan/magenta bloom, soft premium glow.",
    },
    "cyber-edge": {
        "name": "Cyber Edge",
        "palette": ["#020309", "#050914", "#00F0FF", "#FF1E6E", "#E52727", "#FFFFFF"],
        "description": "Dark geometric edges, cyan/magenta/red glow.",
    },
    "liquid-neon": {
        "name": "Liquid Neon",
        "palette": ["#061028", "#034B68", "#00E5FF", "#FF3DC8", "#FF3333", "#F7F4FF"],
        "description": "Fluid organic neon, gel and glass-like forms.",
    },
    "neon-poster": {
        "name": "Neon Poster",
        "palette": ["#070815", "#083B8F", "#00D4FF", "#F51AA7", "#FF3030", "#FFF5E5"],
        "description": "Graphic blocks, halftone, print texture.",
    },
    "holographic-glass": {
        "name": "Holographic Glass",
        "palette": ["#07121E", "#C7F9FF", "#8BF4FF", "#FFB9F2", "#A983FF", "#FFFFFF"],
        "description": "Iridescent cyan, rose, violet, white glossy glass.",
    },
    "painterly-color-storm": {
        "name": "Painterly Color Storm",
        "palette": ["#101021", "#265DFF", "#00D4FF", "#F42A7B", "#FF7A1A", "#F6E7B1"],
        "description": "Dense synthetic brush energy with strong warm/cool color.",
    },
}


def ensure_dirs():
    for path in [REFERENCE_ROOT, TEMP_DIR, SAVED_DIR, METADATA_DIR, CONTACT_SHEET_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def slugify(value):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "reference"


def parse_seed(value):
    if value is None or str(value).strip().lower() == "random":
        return random.SystemRandom().randint(1, 2**31 - 1)
    return int(value)


def clamp01(arr):
    return np.clip(arr, 0.0, 1.0)


def hex_to_rgb(value):
    value = value.lstrip("#")
    return np.array([int(value[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def palette_array(preset):
    return [hex_to_rgb(color) for color in PRESETS[preset]["palette"]]


def to_image(arr):
    return Image.fromarray((clamp01(arr) * 255).astype(np.uint8), "RGB")


def from_image(image):
    return np.asarray(image.convert("RGB")).astype(np.float32) / 255.0


def normalized_params(intensity, glow, contrast, texture, complexity):
    return {
        "intensity": np.clip(intensity / 100.0, 0.0, 1.0),
        "glow": np.clip(glow / 100.0, 0.0, 1.0),
        "contrast": np.clip(contrast / 100.0, 0.0, 1.0),
        "texture": np.clip(texture / 100.0, 0.0, 1.0),
        "complexity": np.clip(complexity / 100.0, 0.0, 1.0),
    }


def xy_grid(width, height):
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    return x / max(1, width - 1), y / max(1, height - 1)


def screen(base, layer, amount=1.0):
    blended = 1.0 - (1.0 - base) * (1.0 - layer)
    return clamp01(base * (1.0 - amount) + blended * amount)


def add(base, layer, amount=1.0):
    return clamp01(base + layer * amount)


def multiply(base, layer, amount=1.0):
    blended = base * layer
    return clamp01(base * (1.0 - amount) + blended * amount)


def overlay(base, layer, amount=1.0):
    blended = np.where(base < 0.5, 2.0 * base * layer, 1.0 - 2.0 * (1.0 - base) * (1.0 - layer))
    return clamp01(base * (1.0 - amount) + blended * amount)


def linear_gradient(width, height, color_a, color_b, angle):
    x, y = xy_grid(width, height)
    axis = math.cos(angle) * (x - 0.5) + math.sin(angle) * (y - 0.5)
    t = (axis - axis.min()) / max(1e-6, axis.max() - axis.min())
    return color_a * (1.0 - t[..., None]) + color_b * t[..., None]


def add_radial_blob(arr, rng, color, strength=0.8, radius=0.35, center=None, elliptical=True):
    height, width = arr.shape[:2]
    x, y = xy_grid(width, height)
    cx, cy = center or (rng.uniform(0.0, 1.0), rng.uniform(0.0, 1.0))
    rx = radius * rng.uniform(0.65, 1.45) if elliptical else radius
    ry = radius * rng.uniform(0.65, 1.45) if elliptical else radius
    dist = ((x - cx) / max(0.001, rx)) ** 2 + ((y - cy) / max(0.001, ry)) ** 2
    mask = np.exp(-dist * rng.uniform(1.4, 3.8)) * strength
    return screen(arr, color * mask[..., None], 0.95)


def value_noise(width, height, rng, scale=32):
    small_w = max(2, width // scale)
    small_h = max(2, height // scale)
    np_rng = np.random.default_rng(rng.randint(1, 2**31 - 1))
    small = np_rng.random((small_h, small_w)).astype(np.float32)
    image = Image.fromarray((small * 255).astype(np.uint8), "L").resize((width, height), Image.Resampling.BICUBIC)
    return np.asarray(image).astype(np.float32) / 255.0


def add_texture(arr, rng, amount):
    if amount <= 0:
        return arr
    height, width = arr.shape[:2]
    np_rng = np.random.default_rng(rng.randint(1, 2**31 - 1))
    fine = np_rng.normal(0.0, 0.045 * amount, arr.shape).astype(np.float32)
    cloud = value_noise(width, height, rng, scale=int(20 + 80 * (1.0 - amount)))
    cloud = (cloud - 0.5)[..., None] * 0.26 * amount
    return clamp01(arr + fine + cloud)


def apply_contrast(arr, amount):
    factor = 0.75 + amount * 1.25
    return clamp01((arr - 0.5) * factor + 0.5)


def glow_image(image, amount, radius=26):
    if amount <= 0:
        return image
    bright = ImageEnhance.Contrast(image).enhance(1.6)
    blurred = bright.filter(ImageFilter.GaussianBlur(radius=max(2, int(radius * amount))))
    return ImageChops.screen(image, ImageEnhance.Brightness(blurred).enhance(0.55 + amount))


def draw_glow_line(layer, p0, p1, color, width, blur):
    draw = ImageDraw.Draw(layer, "RGBA")
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow, "RGBA")
    gdraw.line([p0, p1], fill=color[:3] + (80,), width=max(width * 4, 4))
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    layer.alpha_composite(glow)
    draw.line([p0, p1], fill=color, width=width)


def add_line_layer(arr, rng, palette, count, glow_amount, geometric=True):
    height, width = arr.shape[:2]
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for _ in range(count):
        color = tuple(int(v * 255) for v in rng.choice(palette[2:])) + (rng.randint(125, 235),)
        lw = rng.randint(2, max(3, int(8 + glow_amount * 10)))
        if geometric:
            if rng.random() < 0.65:
                y = rng.randint(-height // 4, height + height // 4)
                p0 = (rng.randint(-width // 5, width // 3), y)
                p1 = (rng.randint(width // 2, width + width // 4), y + rng.randint(-height // 2, height // 2))
            else:
                x0 = rng.randint(0, width)
                y0 = rng.randint(0, height)
                p0 = (x0, y0)
                p1 = (x0 + rng.randint(-width // 2, width // 2), y0 + rng.randint(-height // 2, height // 2))
            draw_glow_line(layer, p0, p1, color, lw, int(8 + 24 * glow_amount))
        else:
            draw = ImageDraw.Draw(layer, "RGBA")
            x0 = rng.randint(-width // 4, width)
            y0 = rng.randint(-height // 4, height)
            x1 = rng.randint(width // 4, width + width // 3)
            y1 = rng.randint(height // 4, height + height // 3)
            bbox = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            draw.arc(bbox, rng.randint(0, 180), rng.randint(190, 360), fill=color, width=lw)
    return screen(arr, from_image(layer), 0.9)


def chromatic_offset(image, amount):
    if amount <= 0:
        return image
    offset = max(1, int(amount * 8))
    r, g, b = image.split()
    r = ImageChops.offset(r, offset, 0)
    b = ImageChops.offset(b, -offset, 0)
    return Image.merge("RGB", (r, g, b))


def halftone(arr, rng, amount, color):
    if amount <= 0:
        return arr
    image = to_image(arr)
    width, height = image.size
    dots = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dots, "RGBA")
    step = max(10, int(36 - amount * 20))
    gray = ImageOps.grayscale(image)
    for y in range(0, height, step):
        for x in range(0, width, step):
            value = gray.getpixel((min(x, width - 1), min(y, height - 1))) / 255.0
            radius = int(step * (0.12 + (1.0 - value) * 0.42) * amount)
            if radius > 1:
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)
    return overlay(arr, from_image(dots), 0.75)


def posterize(arr, levels=5, amount=0.4):
    quant = np.floor(arr * levels) / max(1, levels - 1)
    return clamp01(arr * (1.0 - amount) + quant * amount)


def brush_strokes(arr, rng, palette, count, amount):
    image = to_image(arr).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    width, height = image.size
    for _ in range(count):
        color = tuple(int(v * 255) for v in rng.choice(palette[2:])) + (rng.randint(55, 150),)
        x = rng.randint(-width // 5, width)
        y = rng.randint(-height // 5, height)
        points = []
        for i in range(rng.randint(4, 9)):
            points.append((x + i * rng.randint(18, 64), y + rng.randint(-90, 90)))
        draw.line(points, fill=color, width=rng.randint(18, int(42 + amount * 60)), joint="curve")
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(1, int(1 + amount * 3))))
    image.alpha_composite(layer)
    return from_image(image)


def base_scene(width, height, rng, palette):
    arr = linear_gradient(width, height, palette[0], palette[1], rng.uniform(0, math.tau))
    arr = multiply(arr, np.ones_like(arr) * rng.uniform(0.55, 0.9), 0.25)
    return arr


def generate_neon_bloom(width, height, rng, params):
    palette = palette_array("neon-bloom")
    arr = base_scene(width, height, rng, palette)
    for _ in range(5 + int(params["complexity"] * 7)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[2:]), params["intensity"] * rng.uniform(0.35, 0.95), rng.uniform(0.16, 0.52))
    arr = add_line_layer(arr, rng, palette, int(1 + params["complexity"] * 4), params["glow"], geometric=False)
    return finish(arr, rng, params, "neon-bloom", glow_radius=44)


def generate_cyber_edge(width, height, rng, params):
    palette = palette_array("cyber-edge")
    arr = base_scene(width, height, rng, palette)
    for _ in range(2 + int(params["complexity"] * 4)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[2:5]), params["intensity"] * 0.5, rng.uniform(0.08, 0.22))
    arr = add_line_layer(arr, rng, palette, int(12 + params["complexity"] * 28), params["glow"], geometric=True)
    image = chromatic_offset(to_image(arr), params["intensity"] * 0.9)
    return glow_image(ImageEnhance.Contrast(image).enhance(1.15 + params["contrast"]), params["glow"], 20)


def generate_liquid_neon(width, height, rng, params):
    palette = palette_array("liquid-neon")
    arr = base_scene(width, height, rng, palette)
    x, y = xy_grid(width, height)
    field = np.zeros((height, width), dtype=np.float32)
    for _ in range(8 + int(params["complexity"] * 9)):
        cx, cy = rng.uniform(0, 1), rng.uniform(0, 1)
        r = rng.uniform(0.08, 0.28)
        field += np.exp(-(((x - cx) ** 2 + (y - cy) ** 2) / (r * r)))
    field = field / max(1e-6, field.max())
    for idx, color in enumerate(palette[2:]):
        mask = np.clip(np.sin(field * math.pi * (idx + 1) + rng.uniform(0, math.tau)), 0, 1)
        arr = screen(arr, color * mask[..., None] * params["intensity"], 0.42)
    arr = add_line_layer(arr, rng, palette, int(3 + params["complexity"] * 5), params["glow"], geometric=False)
    return finish(arr, rng, params, "liquid-neon", glow_radius=36)


def generate_neon_poster(width, height, rng, params):
    palette = palette_array("neon-poster")
    arr = base_scene(width, height, rng, palette)
    image = to_image(arr).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    for _ in range(7 + int(params["complexity"] * 12)):
        color = tuple(int(v * 255) for v in rng.choice(palette[2:])) + (rng.randint(120, 220),)
        x0 = rng.randint(-width // 8, width)
        y0 = rng.randint(-height // 8, height)
        x1 = x0 + rng.randint(width // 8, width // 2)
        y1 = y0 + rng.randint(height // 8, height // 2)
        draw.rectangle([x0, y0, x1, y1], fill=color)
    arr = overlay(from_image(image), add_texture(np.zeros_like(arr) + 0.5, rng, params["texture"]), 0.45)
    arr = halftone(arr, rng, params["texture"], tuple(int(v * 255) for v in palette[0]) + (95,))
    arr = posterize(arr, levels=5, amount=0.35 + params["contrast"] * 0.25)
    return glow_image(to_image(apply_contrast(arr, params["contrast"])), params["glow"] * 0.55, 12)


def generate_holographic_glass(width, height, rng, params):
    palette = palette_array("holographic-glass")
    arr = linear_gradient(width, height, palette[1], palette[3], rng.uniform(0, math.tau))
    arr = overlay(arr, linear_gradient(width, height, palette[2], palette[4], rng.uniform(0, math.tau)), 0.62)
    for _ in range(4 + int(params["complexity"] * 8)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[1:]), params["intensity"] * rng.uniform(0.18, 0.55), rng.uniform(0.12, 0.35))
    arr = add_line_layer(arr, rng, palette, int(4 + params["complexity"] * 8), params["glow"] * 0.7, geometric=False)
    image = to_image(arr)
    image = ImageEnhance.Brightness(image).enhance(1.05)
    image = ImageEnhance.Contrast(image).enhance(0.85 + params["contrast"])
    return glow_image(chromatic_offset(image, params["intensity"] * 0.35), params["glow"] * 0.55, 18)


def generate_painterly_color_storm(width, height, rng, params):
    palette = palette_array("painterly-color-storm")
    arr = base_scene(width, height, rng, palette)
    for _ in range(4 + int(params["complexity"] * 7)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[2:]), params["intensity"] * rng.uniform(0.25, 0.7), rng.uniform(0.12, 0.38))
    arr = brush_strokes(arr, rng, palette, int(22 + params["complexity"] * 46), params["texture"])
    arr = add_texture(arr, rng, params["texture"] * 1.2)
    return glow_image(to_image(apply_contrast(arr, params["contrast"])), params["glow"] * 0.25, 10)


GENERATORS = {
    "neon-bloom": generate_neon_bloom,
    "cyber-edge": generate_cyber_edge,
    "liquid-neon": generate_liquid_neon,
    "neon-poster": generate_neon_poster,
    "holographic-glass": generate_holographic_glass,
    "painterly-color-storm": generate_painterly_color_storm,
}


def finish(arr, rng, params, _preset, glow_radius):
    arr = add_texture(arr, rng, params["texture"])
    arr = apply_contrast(arr, params["contrast"])
    image = to_image(arr)
    image = glow_image(image, params["glow"], glow_radius)
    return image


def generate_image(preset, seed, width, height, intensity, glow, contrast, texture, complexity):
    if preset not in GENERATORS:
        raise SystemExit(f"Unknown preset: {preset}")
    rng = random.Random(seed)
    params = normalized_params(intensity, glow, contrast, texture, complexity)
    return GENERATORS[preset](width, height, rng, params).resize((width, height), Image.Resampling.LANCZOS)


def session_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def metadata_for(filename, preset, seed, width, height, intensity, glow, contrast, texture, complexity):
    return {
        "filename": filename,
        "preset": preset,
        "preset_name": PRESETS[preset]["name"],
        "seed": seed,
        "width": width,
        "height": height,
        "palette": PRESETS[preset]["palette"],
        "intensity": intensity,
        "glow": glow,
        "contrast": contrast,
        "texture": texture,
        "complexity": complexity,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "generation_method": "procedural-project-owned",
        "license_note": "project-owned procedural output",
    }


def write_metadata(metadata, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_contact_sheet(image_paths, output_path, thumb=220, columns=5):
    images = []
    for path in image_paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb, thumb), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (thumb, thumb + 26), (12, 14, 22))
        tile.paste(image, ((thumb - image.width) // 2, 0))
        draw = ImageDraw.Draw(tile)
        draw.text((8, thumb + 7), Path(path).stem[:30], fill=(230, 238, 255))
        images.append(tile)
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb + 26)), (8, 10, 18))
    for index, image in enumerate(images):
        x = (index % columns) * thumb
        y = (index // columns) * (thumb + 26)
        sheet.paste(image, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=95)
    return output_path


def generate_references(
    preset,
    count=DEFAULTS["count"],
    seed="random",
    width=DEFAULTS["width"],
    height=DEFAULTS["height"],
    intensity=DEFAULTS["intensity"],
    glow=DEFAULTS["glow"],
    contrast=DEFAULTS["contrast"],
    texture=DEFAULTS["texture"],
    complexity=DEFAULTS["complexity"],
    session=None,
):
    ensure_dirs()
    if preset not in PRESETS:
        raise SystemExit(f"Unknown preset: {preset}")
    session = session or f"{session_id()}-{preset}"
    out_dir = TEMP_DIR / session
    out_dir.mkdir(parents=True, exist_ok=True)
    base_seed = parse_seed(seed)
    images = []
    metadata_paths = []
    for index in range(count):
        item_seed = base_seed + index * 9973
        filename = f"{preset}-{item_seed}-{index + 1:02d}.png"
        image_path = out_dir / filename
        image = generate_image(preset, item_seed, width, height, intensity, glow, contrast, texture, complexity)
        image.save(image_path)
        metadata = metadata_for(filename, preset, item_seed, width, height, intensity, glow, contrast, texture, complexity)
        metadata["session_id"] = session
        metadata["path"] = str(image_path)
        metadata_path = out_dir / f"{Path(filename).stem}.json"
        global_metadata_path = METADATA_DIR / f"{Path(filename).stem}.json"
        write_metadata(metadata, metadata_path)
        write_metadata(metadata, global_metadata_path)
        images.append(image_path)
        metadata_paths.append(metadata_path)
    sheet_path = CONTACT_SHEET_DIR / f"{session}-contact-sheet.png"
    make_contact_sheet(images, sheet_path)
    return {
        "session_id": session,
        "preset": preset,
        "temp_dir": str(out_dir),
        "images": [str(path) for path in images],
        "metadata": [str(path) for path in metadata_paths],
        "contact_sheet": str(sheet_path),
    }


def save_reference(image_path):
    ensure_dirs()
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Reference image missing: {image_path}")
    target = SAVED_DIR / image_path.name
    suffix = 2
    while target.exists():
        target = SAVED_DIR / f"{image_path.stem}-{suffix:02d}{image_path.suffix}"
        suffix += 1
    shutil.copy2(image_path, target)
    source_meta = image_path.with_suffix(".json")
    if source_meta.exists():
        metadata = json.loads(source_meta.read_text(encoding="utf-8"))
    else:
        metadata = {
            "filename": target.name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "generation_method": "procedural-project-owned",
            "license_note": "project-owned procedural output",
        }
    metadata["filename"] = target.name
    metadata["saved_path"] = str(target)
    metadata["saved_at"] = datetime.now().isoformat(timespec="seconds")
    metadata_path = METADATA_DIR / f"{target.stem}.json"
    saved_metadata_path = target.with_suffix(".json")
    write_metadata(metadata, metadata_path)
    write_metadata(metadata, saved_metadata_path)
    return {"image": str(target), "metadata": str(metadata_path), "saved_metadata": str(saved_metadata_path)}


def list_presets():
    for slug, info in PRESETS.items():
        print(f"{slug}: {info['name']} - {info['description']}")


def cmd_generate(args):
    size = args.size
    result = generate_references(
        preset=args.preset,
        count=args.count,
        seed=args.seed,
        width=size,
        height=size,
        intensity=args.intensity,
        glow=args.glow,
        contrast=args.contrast,
        texture=args.texture,
        complexity=args.complexity,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_check(_args):
    ensure_dirs()
    test = generate_image("neon-bloom", 123, 64, 64, 70, 75, 65, 45, 60)
    if test.size != (64, 64):
        raise SystemExit("Generator check failed")
    print("ForJyn reference generator check passed")
    print("Pillow: available")
    print("NumPy: available")
    print("Presets:")
    for slug, info in PRESETS.items():
        print(f"  - {slug}: {info['name']}")


def cmd_initial_contact_sheet(args):
    ensure_dirs()
    all_images = []
    for preset in PRESETS:
        result = generate_references(
            preset=preset,
            count=args.count,
            seed=args.seed,
            width=args.size,
            height=args.size,
            intensity=args.intensity,
            glow=args.glow,
            contrast=args.contrast,
            texture=args.texture,
            complexity=args.complexity,
            session=f"initial-{preset}-{int(time.time())}",
        )
        all_images.extend(Path(path) for path in result["images"])
    output = CONTACT_SHEET_DIR / "initial-reference-generator-contact-sheet.jpg"
    make_contact_sheet(all_images, output, thumb=args.thumb, columns=6)
    print(json.dumps({"contact_sheet": str(output), "image_count": len(all_images)}, indent=2, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description="ForJyn procedural reference image generator")
    parser.add_argument("--check", action="store_true", help="Run a lightweight generator import/check")
    subparsers = parser.add_subparsers(dest="command")

    generate = subparsers.add_parser("generate", help="Generate procedural reference images")
    generate.add_argument("--preset", required=True, choices=sorted(PRESETS))
    generate.add_argument("--count", type=int, default=DEFAULTS["count"])
    generate.add_argument("--seed", default="random")
    generate.add_argument("--size", type=int, default=DEFAULTS["width"])
    generate.add_argument("--intensity", type=int, default=DEFAULTS["intensity"])
    generate.add_argument("--glow", type=int, default=DEFAULTS["glow"])
    generate.add_argument("--contrast", type=int, default=DEFAULTS["contrast"])
    generate.add_argument("--texture", type=int, default=DEFAULTS["texture"])
    generate.add_argument("--complexity", type=int, default=DEFAULTS["complexity"])
    generate.set_defaults(func=cmd_generate)

    presets = subparsers.add_parser("list-presets", help="List available presets")
    presets.set_defaults(func=lambda _args: list_presets())

    contact = subparsers.add_parser("initial-contact-sheet", help="Generate a local all-preset review contact sheet")
    contact.add_argument("--count", type=int, default=5)
    contact.add_argument("--seed", default="123")
    contact.add_argument("--size", type=int, default=512)
    contact.add_argument("--thumb", type=int, default=180)
    contact.add_argument("--intensity", type=int, default=DEFAULTS["intensity"])
    contact.add_argument("--glow", type=int, default=DEFAULTS["glow"])
    contact.add_argument("--contrast", type=int, default=DEFAULTS["contrast"])
    contact.add_argument("--texture", type=int, default=DEFAULTS["texture"])
    contact.add_argument("--complexity", type=int, default=DEFAULTS["complexity"])
    contact.set_defaults(func=cmd_initial_contact_sheet)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.check:
        cmd_check(args)
        return
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
