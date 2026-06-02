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
REVIEW_DIR = REFERENCE_ROOT / "review"
STARTER_PACK_DIR = REFERENCE_ROOT / "starter_pack"

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
    for path in [REFERENCE_ROOT, TEMP_DIR, SAVED_DIR, METADATA_DIR, CONTACT_SHEET_DIR, REVIEW_DIR, STARTER_PACK_DIR]:
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


def accent_colors(palette):
    return palette[2:-1] if len(palette) > 4 else palette[2:]


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


def add_vignette(arr, strength=0.34):
    height, width = arr.shape[:2]
    x, y = xy_grid(width, height)
    dist = np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2)
    mask = 1.0 - np.clip((dist - 0.24) / 0.55, 0.0, 1.0) * strength
    return clamp01(arr * mask[..., None])


def add_dark_structure(arr, rng, amount=0.28):
    height, width = arr.shape[:2]
    x, y = xy_grid(width, height)
    for _ in range(2 + int(amount * 5)):
        angle = rng.uniform(0, math.tau)
        axis = math.cos(angle) * (x - rng.uniform(0.25, 0.75)) + math.sin(angle) * (y - rng.uniform(0.25, 0.75))
        band = np.exp(-(axis ** 2) / rng.uniform(0.0015, 0.008))
        arr = clamp01(arr * (1.0 - band[..., None] * rng.uniform(0.10, 0.22) * amount))
    return arr


def add_prismatic_polygons(arr, rng, palette, count, alpha_scale=0.42):
    image = to_image(arr).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    width, height = image.size
    for _ in range(count):
        cx = rng.randint(-width // 8, width + width // 8)
        cy = rng.randint(-height // 8, height + height // 8)
        radius = rng.randint(max(24, width // 12), max(32, width // 3))
        sides = rng.randint(3, 6)
        angle = rng.uniform(0, math.tau)
        points = []
        for index in range(sides):
            theta = angle + math.tau * index / sides
            points.append((cx + int(math.cos(theta) * radius * rng.uniform(0.55, 1.0)), cy + int(math.sin(theta) * radius * rng.uniform(0.55, 1.0))))
        color = tuple(int(v * 255) for v in rng.choice(accent_colors(palette))) + (int(rng.randint(35, 120) * alpha_scale),)
        draw.polygon(points, fill=color)
        draw.line(points + [points[0]], fill=color[:3] + (min(210, color[3] + 55),), width=rng.randint(2, 6))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(0.6, 1.2 * alpha_scale)))
    image.alpha_composite(layer)
    return screen(arr, from_image(image), 0.72)


def add_neon_frames(arr, rng, palette, count, glow_amount):
    height, width = arr.shape[:2]
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    for _ in range(count):
        margin_x = rng.randint(-width // 10, width // 3)
        margin_y = rng.randint(-height // 10, height // 3)
        w = rng.randint(width // 5, max(width // 4, width))
        h = rng.randint(height // 5, max(height // 4, height))
        box = [margin_x, margin_y, margin_x + w, margin_y + h]
        color = tuple(int(v * 255) for v in rng.choice(accent_colors(palette))) + (rng.randint(80, 165),)
        line_width = rng.randint(2, max(3, int(5 + glow_amount * 8)))
        glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer, "RGBA")
        glow_draw.rectangle(box, outline=color[:3] + (70,), width=line_width * 4)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=int(8 + glow_amount * 18)))
        layer.alpha_composite(glow_layer)
        draw.rectangle(box, outline=color, width=line_width)
    return screen(arr, from_image(layer), 0.85)


def add_flow_ribbons(arr, rng, palette, count, glow_amount):
    image = to_image(arr).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    width, height = image.size
    for _ in range(count):
        color = tuple(int(v * 255) for v in rng.choice(accent_colors(palette))) + (rng.randint(70, 155),)
        start_x = rng.randint(-width // 5, width // 2)
        start_y = rng.randint(-height // 8, height + height // 8)
        points = []
        for index in range(6):
            t = index / 5
            points.append((
                int(start_x + t * width * rng.uniform(0.55, 1.15)),
                int(start_y + math.sin(t * math.tau + rng.uniform(-1.2, 1.2)) * height * rng.uniform(0.05, 0.22)),
            ))
        draw.line(points, fill=color, width=rng.randint(12, int(28 + glow_amount * 46)), joint="curve")
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(1, int(2 + glow_amount * 8))))
    image.alpha_composite(layer)
    return screen(arr, from_image(image), 0.8)


def apply_contrast(arr, amount):
    factor = 0.75 + amount * 1.25
    return clamp01((arr - 0.5) * factor + 0.5)


def glow_image(image, amount, radius=26):
    if amount <= 0:
        return image
    bright = ImageEnhance.Contrast(image).enhance(1.6)
    blurred = bright.filter(ImageFilter.GaussianBlur(radius=max(2, int(radius * amount))))
    return ImageChops.screen(image, ImageEnhance.Brightness(blurred).enhance(0.55 + amount))


def luma_array(arr):
    return arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722


def control_exposure(image, target_brightness=0.46):
    arr = from_image(image)
    luma = luma_array(arr)
    white_ratio = float(np.mean(luma > 0.90))
    brightness = float(np.mean(luma))
    if white_ratio > 0.045 or brightness > 0.54:
        gamma = 1.12 + white_ratio * 2.7 + max(0.0, brightness - target_brightness) * 1.35
        arr = np.power(clamp01(arr), gamma)
    luma = luma_array(arr)
    highlight_mask = np.clip((luma - 0.66) / 0.30, 0.0, 1.0)
    arr = arr * (1.0 - highlight_mask[..., None] * 0.16)
    luma = luma_array(arr)
    brightness = float(np.mean(luma))
    if brightness > 0.60:
        arr *= 0.60 / max(brightness, 1e-6)
    arr = np.minimum(arr, 0.925)
    image = to_image(arr)
    image = ImageEnhance.Color(image).enhance(1.08)
    return image


def quality_metrics(image):
    arr = from_image(image)
    luma = luma_array(arr)
    max_channel = np.max(arr, axis=2)
    min_channel = np.min(arr, axis=2)
    saturation = np.zeros_like(max_channel)
    np.divide(max_channel - min_channel, max_channel, out=saturation, where=max_channel > 1e-6)
    grad_y, grad_x = np.gradient(luma)
    edge_score = float(np.mean(np.sqrt(grad_x * grad_x + grad_y * grad_y)))
    white_clip_ratio = float(np.mean((luma > 0.90) & (min_channel > 0.82)))
    dark_ratio = float(np.mean(luma < 0.20))
    bright_ratio = float(np.mean(luma > 0.70))
    brightness = float(np.mean(luma))
    contrast = float(np.std(luma))
    saturation_score = float(np.mean(saturation))
    quality_score = (
        contrast * 2.6
        + saturation_score * 1.8
        + edge_score * 5.0
        + min(dark_ratio, 0.30) * 0.8
        + min(bright_ratio, 0.25) * 0.55
        - max(0.0, brightness - 0.62) * 1.2
        - white_clip_ratio * 2.0
    )
    final_quality_pass = (
        brightness <= 0.68
        and white_clip_ratio <= 0.09
        and contrast >= 0.115
        and saturation_score >= 0.16
        and edge_score >= 0.006
        and dark_ratio >= 0.035
    )
    return {
        "brightness_score": round(brightness, 5),
        "contrast_score": round(contrast, 5),
        "saturation_score": round(saturation_score, 5),
        "white_clip_ratio": round(white_clip_ratio, 5),
        "edge_score": round(edge_score, 5),
        "dark_ratio": round(dark_ratio, 5),
        "bright_ratio": round(bright_ratio, 5),
        "quality_score": round(float(quality_score), 5),
        "final_quality_pass": bool(final_quality_pass),
    }


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
        color = tuple(int(v * 255) for v in rng.choice(accent_colors(palette))) + (rng.randint(125, 235),)
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
        color = tuple(int(v * 255) for v in rng.choice(accent_colors(palette))) + (rng.randint(55, 150),)
        x = rng.randint(-width // 5, width)
        y = rng.randint(-height // 5, height)
        points = []
        for i in range(rng.randint(4, 9)):
            points.append((x + i * rng.randint(18, 64), y + rng.randint(-90, 90)))
        draw.line(points, fill=color, width=rng.randint(18, int(42 + amount * 60)), joint="curve")
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(1, int(1 + amount * 3))))
    image.alpha_composite(layer)
    return from_image(image)


def broad_painterly_clusters(arr, rng, palette, clusters, amount):
    image = to_image(arr).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    width, height = image.size
    for _ in range(clusters):
        origin = (rng.randint(-width // 6, width), rng.randint(-height // 6, height))
        direction = rng.uniform(-0.9, 0.9)
        color = tuple(int(v * 255) for v in rng.choice(accent_colors(palette))) + (rng.randint(70, 150),)
        for stroke_index in range(rng.randint(5, 11)):
            x = origin[0] + rng.randint(-width // 8, width // 8)
            y = origin[1] + stroke_index * rng.randint(12, 34) + rng.randint(-height // 12, height // 12)
            length = rng.randint(width // 5, max(width // 4, int(width * 0.7)))
            points = []
            for step in range(5):
                t = step / 4
                points.append((
                    int(x + t * math.cos(direction) * length + rng.randint(-35, 35)),
                    int(y + t * math.sin(direction) * length + rng.randint(-70, 70)),
                ))
            draw.line(points, fill=color, width=rng.randint(20, int(44 + amount * 82)), joint="curve")
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(1, int(1 + amount * 2))))
    image.alpha_composite(layer)
    return from_image(image)


def base_scene(width, height, rng, palette):
    arr = linear_gradient(width, height, palette[0], palette[1], rng.uniform(0, math.tau))
    arr = multiply(arr, np.ones_like(arr) * rng.uniform(0.34, 0.72), 0.38)
    return add_vignette(arr, 0.20)


def generate_neon_bloom(width, height, rng, params):
    palette = palette_array("neon-bloom")
    arr = base_scene(width, height, rng, palette)
    arr = add_dark_structure(arr, rng, 0.35)
    for _ in range(5 + int(params["complexity"] * 8)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[2:5]), params["intensity"] * rng.uniform(0.24, 0.68), rng.uniform(0.12, 0.40))
    arr = add_flow_ribbons(arr, rng, palette, int(1 + params["complexity"] * 3), params["glow"] * 0.55)
    arr = add_line_layer(arr, rng, palette, int(2 + params["complexity"] * 5), params["glow"] * 0.78, geometric=False)
    arr = add_prismatic_polygons(arr, rng, palette, int(1 + params["complexity"] * 3), 0.32)
    return finish(arr, rng, params, "neon-bloom", glow_radius=34, dark_strength=0.30)


def generate_cyber_edge(width, height, rng, params):
    palette = palette_array("cyber-edge")
    arr = base_scene(width, height, rng, palette)
    arr = add_dark_structure(arr, rng, 0.42)
    for _ in range(3 + int(params["complexity"] * 5)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[2:5]), params["intensity"] * 0.34, rng.uniform(0.06, 0.20))
    arr = add_neon_frames(arr, rng, palette, int(2 + params["complexity"] * 5), params["glow"])
    arr = add_line_layer(arr, rng, palette, int(10 + params["complexity"] * 20), params["glow"] * 0.85, geometric=True)
    arr = add_prismatic_polygons(arr, rng, palette, int(2 + params["complexity"] * 5), 0.24)
    image = chromatic_offset(to_image(arr), params["intensity"] * 0.9)
    image = glow_image(ImageEnhance.Contrast(image).enhance(1.12 + params["contrast"] * 0.82), params["glow"] * 0.78, 18)
    return control_exposure(image, 0.42)


def generate_liquid_neon(width, height, rng, params):
    palette = palette_array("liquid-neon")
    arr = base_scene(width, height, rng, palette)
    arr = add_dark_structure(arr, rng, 0.28)
    x, y = xy_grid(width, height)
    field = np.zeros((height, width), dtype=np.float32)
    for _ in range(10 + int(params["complexity"] * 12)):
        cx, cy = rng.uniform(0, 1), rng.uniform(0, 1)
        rx = rng.uniform(0.06, 0.24)
        ry = rng.uniform(0.05, 0.26)
        field += np.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))
    field = field / max(1e-6, field.max())
    for idx, color in enumerate(palette[2:]):
        mask = np.clip(np.sin(field * math.pi * (idx + 1.35) + rng.uniform(0, math.tau)), 0, 1)
        arr = screen(arr, color * mask[..., None] * params["intensity"], 0.34)
    arr = add_flow_ribbons(arr, rng, palette, int(3 + params["complexity"] * 6), params["glow"])
    arr = add_line_layer(arr, rng, palette, int(2 + params["complexity"] * 4), params["glow"] * 0.65, geometric=False)
    return finish(arr, rng, params, "liquid-neon", glow_radius=30, dark_strength=0.25)


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
    for _ in range(4 + int(params["complexity"] * 7)):
        color = tuple(int(v * 255) for v in rng.choice(palette[2:5])) + (rng.randint(120, 210),)
        x = rng.randint(-width // 5, width)
        draw.line([(x, -height // 8), (x + rng.randint(width // 5, width), height + height // 8)], fill=color, width=rng.randint(8, 24))
    arr = overlay(from_image(image), add_texture(np.zeros_like(arr) + 0.5, rng, params["texture"]), 0.45)
    arr = halftone(arr, rng, params["texture"], tuple(int(v * 255) for v in palette[0]) + (95,))
    arr = posterize(arr, levels=5, amount=0.35 + params["contrast"] * 0.25)
    return control_exposure(glow_image(to_image(apply_contrast(add_vignette(arr, 0.24), params["contrast"])), params["glow"] * 0.45, 12), 0.47)


def generate_holographic_glass(width, height, rng, params):
    palette = palette_array("holographic-glass")
    arr = base_scene(width, height, rng, palette)
    arr = screen(arr, linear_gradient(width, height, palette[1], palette[3], rng.uniform(0, math.tau)) * 0.62, 0.52)
    arr = overlay(arr, linear_gradient(width, height, palette[2], palette[4], rng.uniform(0, math.tau)), 0.38)
    arr = add_dark_structure(arr, rng, 0.20)
    for _ in range(3 + int(params["complexity"] * 6)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[1:5]), params["intensity"] * rng.uniform(0.12, 0.34), rng.uniform(0.10, 0.30))
    arr = add_prismatic_polygons(arr, rng, palette, int(5 + params["complexity"] * 10), 0.38)
    arr = add_line_layer(arr, rng, palette, int(3 + params["complexity"] * 6), params["glow"] * 0.55, geometric=False)
    image = to_image(arr)
    image = ImageEnhance.Contrast(image).enhance(0.95 + params["contrast"] * 0.75)
    return control_exposure(glow_image(chromatic_offset(image, params["intensity"] * 0.25), params["glow"] * 0.35, 14), 0.50)


def generate_painterly_color_storm(width, height, rng, params):
    palette = palette_array("painterly-color-storm")
    arr = base_scene(width, height, rng, palette)
    arr = add_dark_structure(arr, rng, 0.30)
    for _ in range(4 + int(params["complexity"] * 7)):
        arr = add_radial_blob(arr, rng, rng.choice(palette[2:]), params["intensity"] * rng.uniform(0.20, 0.56), rng.uniform(0.10, 0.33))
    arr = broad_painterly_clusters(arr, rng, palette, int(4 + params["complexity"] * 7), params["texture"])
    arr = brush_strokes(arr, rng, palette, int(12 + params["complexity"] * 26), params["texture"] * 0.85)
    arr = add_texture(arr, rng, params["texture"] * 1.2)
    return control_exposure(glow_image(to_image(apply_contrast(add_vignette(arr, 0.18), params["contrast"])), params["glow"] * 0.18, 8), 0.47)


GENERATORS = {
    "neon-bloom": generate_neon_bloom,
    "cyber-edge": generate_cyber_edge,
    "liquid-neon": generate_liquid_neon,
    "neon-poster": generate_neon_poster,
    "holographic-glass": generate_holographic_glass,
    "painterly-color-storm": generate_painterly_color_storm,
}


def finish(arr, rng, params, _preset, glow_radius, dark_strength=0.26):
    arr = add_texture(arr, rng, params["texture"])
    arr = add_vignette(arr, dark_strength)
    arr = apply_contrast(arr, params["contrast"])
    image = to_image(arr)
    image = glow_image(image, params["glow"], glow_radius)
    return control_exposure(image)


def generate_image(preset, seed, width, height, intensity, glow, contrast, texture, complexity):
    if preset not in GENERATORS:
        raise SystemExit(f"Unknown preset: {preset}")
    rng = random.Random(seed)
    params = normalized_params(intensity, glow, contrast, texture, complexity)
    return GENERATORS[preset](width, height, rng, params).resize((width, height), Image.Resampling.LANCZOS)


def generate_image_with_quality(preset, seed, width, height, intensity, glow, contrast, texture, complexity, max_retries=5):
    best = None
    for attempt in range(max_retries + 1):
        candidate_seed = seed + attempt * 104729
        image = generate_image(preset, candidate_seed, width, height, intensity, glow, contrast, texture, complexity)
        metrics = quality_metrics(image)
        metrics["retry_count"] = attempt
        metrics["requested_seed"] = seed
        metrics["actual_seed"] = candidate_seed
        candidate = {"image": image, "metrics": metrics}
        if metrics["final_quality_pass"]:
            return candidate
        if best is None or metrics["quality_score"] > best["metrics"]["quality_score"]:
            best = candidate
    assert best is not None
    best["metrics"]["final_quality_pass"] = False
    best["metrics"]["quality_note"] = "Best available attempt after anti-washout retries"
    return best


def session_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def metadata_for(filename, preset, seed, width, height, intensity, glow, contrast, texture, complexity, quality=None):
    quality = quality or {}
    return {
        "filename": filename,
        "preset": preset,
        "preset_name": PRESETS[preset]["name"],
        "seed": seed,
        "requested_seed": quality.get("requested_seed", seed),
        "actual_seed": quality.get("actual_seed", seed),
        "width": width,
        "height": height,
        "palette": PRESETS[preset]["palette"],
        "intensity": intensity,
        "glow": glow,
        "contrast": contrast,
        "texture": texture,
        "complexity": complexity,
        "brightness_score": quality.get("brightness_score"),
        "contrast_score": quality.get("contrast_score"),
        "saturation_score": quality.get("saturation_score"),
        "white_clip_ratio": quality.get("white_clip_ratio"),
        "edge_score": quality.get("edge_score"),
        "dark_ratio": quality.get("dark_ratio"),
        "bright_ratio": quality.get("bright_ratio"),
        "quality_score": quality.get("quality_score"),
        "final_quality_pass": quality.get("final_quality_pass"),
        "retry_count": quality.get("retry_count", 0),
        "quality_note": quality.get("quality_note"),
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
    count = max(1, min(12, int(count)))
    session = session or f"{session_id()}-{preset}"
    out_dir = TEMP_DIR / session
    out_dir.mkdir(parents=True, exist_ok=True)
    base_seed = parse_seed(seed)
    images = []
    metadata_paths = []
    metrics_items = []
    for index in range(count):
        item_seed = base_seed + index * 9973
        generated = generate_image_with_quality(preset, item_seed, width, height, intensity, glow, contrast, texture, complexity)
        quality = generated["metrics"]
        actual_seed = quality["actual_seed"]
        filename = f"{preset}-{actual_seed}-{index + 1:02d}.png"
        image_path = out_dir / filename
        image = generated["image"]
        image.save(image_path)
        metadata = metadata_for(filename, preset, actual_seed, width, height, intensity, glow, contrast, texture, complexity, quality)
        metadata["session_id"] = session
        metadata["path"] = str(image_path)
        metadata_path = out_dir / f"{Path(filename).stem}.json"
        global_metadata_path = METADATA_DIR / f"{Path(filename).stem}.json"
        write_metadata(metadata, metadata_path)
        write_metadata(metadata, global_metadata_path)
        images.append(image_path)
        metadata_paths.append(metadata_path)
        metrics_items.append(quality)
    sheet_path = CONTACT_SHEET_DIR / f"{session}-contact-sheet.png"
    make_contact_sheet(images, sheet_path)
    return {
        "session_id": session,
        "preset": preset,
        "temp_dir": str(out_dir),
        "images": [str(path) for path in images],
        "metadata": [str(path) for path in metadata_paths],
        "contact_sheet": str(sheet_path),
        "quality": metrics_items,
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
    width = args.width or args.size
    height = args.height or args.size
    result = generate_references(
        preset=args.preset,
        count=args.count,
        seed=args.seed,
        width=width,
        height=height,
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


def read_metadata(path):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))


def metadata_for_image_path(image_path):
    image_path = Path(image_path)
    local_metadata = image_path.with_suffix(".json")
    global_metadata = METADATA_DIR / f"{image_path.stem}.json"
    if local_metadata.exists():
        return read_metadata(local_metadata)
    if global_metadata.exists():
        return read_metadata(global_metadata)
    return {}


def strongest_items(image_paths, limit=6):
    items = []
    for image_path in image_paths:
        metadata = metadata_for_image_path(image_path)
        items.append({
            "image": str(image_path),
            "metadata": metadata,
            "quality_score": float(metadata.get("quality_score") or -999.0),
            "final_quality_pass": bool(metadata.get("final_quality_pass")),
        })
    return sorted(items, key=lambda item: (item["final_quality_pass"], item["quality_score"]), reverse=True)[:limit]


def write_review_summary(output_path, preset_results, strongest):
    lines = [
        "# ForJyn Reference Generator Review V2",
        "",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Generated local procedural references only. No training or ONNX export was run.",
        "",
        "## Presets Generated",
        "",
    ]
    for preset, result in preset_results:
        retry_total = sum(int(item.get("retry_count", 0)) for item in result["quality"])
        failed = sum(1 for item in result["quality"] if not item.get("final_quality_pass"))
        lines.append(f"- {PRESETS[preset]['name']} (`{preset}`): {len(result['images'])} images, retries {retry_total}, quality failures kept {failed}")
    lines.extend(["", "## Strongest Heuristic Picks", ""])
    for index, item in enumerate(strongest, start=1):
        metadata = item["metadata"]
        lines.append(
            f"{index}. {Path(item['image']).name} - {metadata.get('preset_name')} seed {metadata.get('actual_seed')} "
            f"score {metadata.get('quality_score')} contrast {metadata.get('contrast_score')} saturation {metadata.get('saturation_score')} "
            f"white clip {metadata.get('white_clip_ratio')}"
        )
    lines.extend([
        "",
        "## Suggested First Presets",
        "",
        "- Cyber Edge: strongest geometric structure and edge energy.",
        "- Neon Bloom: strong premium glow with dark negative space.",
        "- Liquid Neon: strongest fluid/glass-like candidate set.",
        "",
        "These are candidate references for review, not final model-quality claims.",
    ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def cmd_review_contact_sheet(args):
    ensure_dirs()
    priority = ["neon-bloom", "cyber-edge", "liquid-neon", "painterly-color-storm"]
    secondary = ["neon-poster", "holographic-glass"]
    base_seed = parse_seed(args.seed)
    all_images = []
    preset_results = []
    for index, preset in enumerate(priority + secondary):
        count = args.priority_count if preset in priority else args.secondary_count
        result = generate_references(
            preset=preset,
            count=count,
            seed=str(base_seed + index * 50000),
            width=args.size,
            height=args.size,
            intensity=args.intensity,
            glow=args.glow,
            contrast=args.contrast,
            texture=args.texture,
            complexity=args.complexity,
            session=f"review-v2-{preset}-{session_id()}",
        )
        all_images.extend(Path(path) for path in result["images"])
        preset_results.append((preset, result))
    output = CONTACT_SHEET_DIR / "review-v2-contact-sheet.jpg"
    make_contact_sheet(all_images, output, thumb=args.thumb, columns=6)
    strongest = strongest_items(all_images, limit=8)
    summary = REVIEW_DIR / "review-v2-summary.md"
    write_review_summary(summary, preset_results, strongest)
    print(json.dumps({
        "contact_sheet": str(output),
        "summary": str(summary),
        "image_count": len(all_images),
        "strongest": [
            {
                "image": item["image"],
                "preset": item["metadata"].get("preset"),
                "seed": item["metadata"].get("actual_seed"),
                "quality_score": item["metadata"].get("quality_score"),
                "retry_count": item["metadata"].get("retry_count"),
                "final_quality_pass": item["metadata"].get("final_quality_pass"),
            }
            for item in strongest
        ],
    }, indent=2, sort_keys=True))


def starter_reason(preset):
    return {
        "cyber-edge": "Selected for geometric edge energy, layered diagonals, and strong dark/bright contrast.",
        "neon-bloom": "Selected for premium cyan/magenta bloom, dark negative space, and usable luminous depth.",
        "liquid-neon": "Selected for fluid gel structure, glossy color transitions, and enough detail for style learning.",
    }.get(preset, "Selected by procedural quality heuristics.")


def cmd_starter_pack(args):
    ensure_dirs()
    presets = ["cyber-edge", "neon-bloom", "liquid-neon"]
    base_seed = parse_seed(args.seed)
    chosen = []
    for index, preset in enumerate(presets):
        result = generate_references(
            preset=preset,
            count=args.candidates,
            seed=str(base_seed + index * 90000),
            width=args.size,
            height=args.size,
            intensity=args.intensity,
            glow=args.glow,
            contrast=args.contrast,
            texture=args.texture,
            complexity=args.complexity,
            session=f"starter-candidates-{preset}-{session_id()}",
        )
        best = strongest_items([Path(path) for path in result["images"]], limit=1)[0]
        source = Path(best["image"])
        target = STARTER_PACK_DIR / f"starter-{preset}-{best['metadata'].get('actual_seed')}.png"
        shutil.copy2(source, target)
        metadata = best["metadata"]
        metadata["starter_pack_path"] = str(target)
        metadata["starter_reason"] = starter_reason(preset)
        metadata["recommended_intended_use"] = "candidate for first serious ONNX run"
        metadata_path = STARTER_PACK_DIR / f"{target.stem}.json"
        write_metadata(metadata, metadata_path)
        chosen.append({"image": str(target), "metadata": str(metadata_path), "preset": preset, "seed": metadata.get("actual_seed"), "reason": metadata["starter_reason"]})
    readme_lines = [
        "ForJyn starter reference pack",
        "",
        "Recommended intended use: candidate for first serious ONNX run",
        "",
    ]
    for item in chosen:
        readme_lines.extend([
            f"- {Path(item['image']).name}",
            f"  Preset: {PRESETS[item['preset']]['name']}",
            f"  Seed: {item['seed']}",
            f"  Why: {item['reason']}",
            "",
        ])
    readme = STARTER_PACK_DIR / "STARTER_PACK_README.txt"
    readme.write_text("\n".join(readme_lines), encoding="utf-8")
    print(json.dumps({"starter_pack": str(STARTER_PACK_DIR), "readme": str(readme), "chosen": chosen}, indent=2, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description="ForJyn procedural reference image generator")
    parser.add_argument("--check", action="store_true", help="Run a lightweight generator import/check")
    subparsers = parser.add_subparsers(dest="command")

    generate = subparsers.add_parser("generate", help="Generate procedural reference images")
    generate.add_argument("--preset", required=True, choices=sorted(PRESETS))
    generate.add_argument("--count", type=int, default=DEFAULTS["count"])
    generate.add_argument("--seed", default="random")
    generate.add_argument("--size", type=int, default=DEFAULTS["width"])
    generate.add_argument("--width", type=int)
    generate.add_argument("--height", type=int)
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

    review = subparsers.add_parser("review-contact-sheet", help="Generate a stronger local review contact sheet and summary")
    review.add_argument("--seed", default="2026")
    review.add_argument("--size", type=int, default=512)
    review.add_argument("--thumb", type=int, default=180)
    review.add_argument("--priority-count", type=int, default=5)
    review.add_argument("--secondary-count", type=int, default=3)
    review.add_argument("--intensity", type=int, default=DEFAULTS["intensity"])
    review.add_argument("--glow", type=int, default=DEFAULTS["glow"])
    review.add_argument("--contrast", type=int, default=DEFAULTS["contrast"])
    review.add_argument("--texture", type=int, default=DEFAULTS["texture"])
    review.add_argument("--complexity", type=int, default=DEFAULTS["complexity"])
    review.set_defaults(func=cmd_review_contact_sheet)

    starter = subparsers.add_parser("starter-pack", help="Prepare 3 local starter references for first serious ONNX runs")
    starter.add_argument("--seed", default="4242")
    starter.add_argument("--size", type=int, default=1024)
    starter.add_argument("--candidates", type=int, default=6)
    starter.add_argument("--intensity", type=int, default=DEFAULTS["intensity"])
    starter.add_argument("--glow", type=int, default=DEFAULTS["glow"])
    starter.add_argument("--contrast", type=int, default=DEFAULTS["contrast"])
    starter.add_argument("--texture", type=int, default=DEFAULTS["texture"])
    starter.add_argument("--complexity", type=int, default=DEFAULTS["complexity"])
    starter.set_defaults(func=cmd_starter_pack)
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
