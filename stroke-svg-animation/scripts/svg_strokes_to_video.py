#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import random
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


TOKEN_RE = re.compile(r"[MLCQZmlcqz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def parse_path_points(d: str, samples_per_curve: int = 28) -> list[tuple[float, float]]:
    tokens = TOKEN_RE.findall(d)
    i = 0
    cmd = None
    current = (0.0, 0.0)
    start = None
    points: list[tuple[float, float]] = []

    def is_cmd(value: str) -> bool:
        return bool(re.fullmatch(r"[MLCQZmlcqz]", value))

    def number() -> float:
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    def add_point(point: tuple[float, float]) -> None:
        if not points or math.hypot(points[-1][0] - point[0], points[-1][1] - point[1]) > 0.25:
            points.append(point)

    def cubic(p0, c1, c2, p1):
        for step in range(1, samples_per_curve + 1):
            t = step / samples_per_curve
            mt = 1 - t
            x = mt**3 * p0[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * p1[0]
            y = mt**3 * p0[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * p1[1]
            add_point((x, y))

    while i < len(tokens):
        if is_cmd(tokens[i]):
            cmd = tokens[i]
            i += 1
        if cmd is None:
            raise ValueError("Path starts without command")
        absolute = cmd.isupper()
        lower = cmd.lower()
        if lower == "m":
            x, y = number(), number()
            if not absolute:
                x += current[0]
                y += current[1]
            current = (x, y)
            start = current
            add_point(current)
            cmd = "L" if absolute else "l"
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = number(), number()
                if not absolute:
                    x += current[0]
                    y += current[1]
                current = (x, y)
                add_point(current)
        elif lower == "l":
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = number(), number()
                if not absolute:
                    x += current[0]
                    y += current[1]
                current = (x, y)
                add_point(current)
        elif lower == "c":
            while i < len(tokens) and not is_cmd(tokens[i]):
                c1 = (number(), number())
                c2 = (number(), number())
                p1 = (number(), number())
                if not absolute:
                    c1 = (c1[0] + current[0], c1[1] + current[1])
                    c2 = (c2[0] + current[0], c2[1] + current[1])
                    p1 = (p1[0] + current[0], p1[1] + current[1])
                cubic(current, c1, c2, p1)
                current = p1
        elif lower == "q":
            while i < len(tokens) and not is_cmd(tokens[i]):
                c = (number(), number())
                p1 = (number(), number())
                if not absolute:
                    c = (c[0] + current[0], c[1] + current[1])
                    p1 = (p1[0] + current[0], p1[1] + current[1])
                c1 = (current[0] + 2 / 3 * (c[0] - current[0]), current[1] + 2 / 3 * (c[1] - current[1]))
                c2 = (p1[0] + 2 / 3 * (c[0] - p1[0]), p1[1] + 2 / 3 * (c[1] - p1[1]))
                cubic(current, c1, c2, p1)
                current = p1
        elif lower == "z":
            if start is not None:
                add_point(start)
                current = start
        else:
            raise ValueError(f"Unsupported command {cmd}")
    return points


def partial_points(points: list[tuple[float, float]], progress: float) -> list[tuple[float, float]]:
    if progress <= 0 or len(points) < 2:
        return []
    if progress >= 1:
        return points
    segs = []
    total = 0.0
    for a, b in zip(points, points[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append((a, b, length))
        total += length
    target = total * progress
    out = [points[0]]
    traveled = 0.0
    for a, b, length in segs:
        if traveled + length <= target:
            out.append(b)
            traveled += length
        else:
            if length > 0:
                t = (target - traveled) / length
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            break
    return out


def read_svg(svg_path: Path):
    root = ET.parse(svg_path).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    width = float(root.attrib.get("width", "800").replace("px", ""))
    height = float(root.attrib.get("height", "600").replace("px", ""))
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = [float(x) for x in view_box.replace(",", " ").split()]
        if len(parts) == 4:
            width, height = parts[2], parts[3]
    paths = []
    for el in root.findall(f".//{ns}path"):
        d = el.attrib.get("d")
        if not d:
            continue
        paths.append(
            {
                "points": parse_path_points(d),
                "width": float(el.attrib.get("stroke-width", "8")),
            }
        )
    return int(round(width)), int(round(height)), paths


def make_background(w: int, h: int, mode: str, rng: random.Random, pure: bool = False) -> Image.Image:
    if pure:
        color = (255, 255, 255) if mode == "clean" else ((246, 242, 234) if mode == "pencil" else (25, 34, 31))
        return Image.new("RGB", (w, h), color)
    if mode == "clean":
        return Image.new("RGB", (w, h), (255, 255, 255))
    if mode == "clean":
        base = color or (17, 17, 17)
        styles = [(1.0, 255, base, 0.0)]
    elif mode == "pencil":
        base = np.zeros((h, w, 3), dtype=np.uint8)
        base[:] = np.array([238, 230, 213], dtype=np.uint8)
        noise = rng_np(rng).normal(0, 7, (h, w, 1))
        fiber_x = np.sin(np.linspace(0, math.pi * 18, w))[None, :, None] * 3
        arr = np.clip(base + noise + fiber_x, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, "RGB").filter(ImageFilter.GaussianBlur(0.25))
    base = np.zeros((h, w, 3), dtype=np.uint8)
    base[:] = np.array([22, 34, 30], dtype=np.uint8)
    noise = rng_np(rng).normal(0, 8, (h, w, 1))
    smudge = np.sin(np.linspace(0, math.pi * 8, h))[:, None, None] * 8
    arr = np.clip(base + noise + smudge, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").filter(ImageFilter.GaussianBlur(0.35))


def rng_np(rng: random.Random):
    return np.random.default_rng(rng.randrange(0, 2**32 - 1))


def parse_hex_color(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not value:
        return fallback
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    if value.lower() == "black":
        return (0, 0, 0)
    if value.lower() == "white":
        return (255, 255, 255)
    return fallback


def scaled_color(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(channel * factor))) for channel in color)


def draw_polyline(layer: Image.Image, pts: list[tuple[float, float]], width: int, fill: tuple[int, int, int, int]) -> None:
    if len(pts) < 2:
        return
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.line([(round(x), round(y)) for x, y in pts], fill=fill, width=max(1, width), joint="curve")
    radius = max(1, width // 2)
    for x, y in (pts[0], pts[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def textured_stroke(
    canvas: Image.Image,
    pts: list[tuple[float, float]],
    base_width: float,
    mode: str,
    rng: random.Random,
    scale: int,
    color: tuple[int, int, int] | None = None,
) -> None:
    if len(pts) < 2:
        return
    if mode == "pencil":
        base = color or (44, 43, 39)
        styles = [
            (0.90, 74, scaled_color(base, 1.00), 1.0),
            (0.48, 54, scaled_color(base, 0.45), 1.8),
            (0.24, 34, scaled_color(base, 1.72), 2.6),
            (0.12, 24, scaled_color(base, 0.76), 3.4),
        ]
    else:
        base = color or (248, 244, 225)
        styles = [
            (1.35, 70, scaled_color(base, 0.98), 1.4),
            (0.95, 92, scaled_color(base, 1.08), 2.1),
            (0.58, 46, scaled_color(base, 0.78), 3.2),
            (0.25, 34, scaled_color(base, 1.12), 4.4),
            (0.12, 28, scaled_color(base, 1.20), 5.6),
        ]
    for width_scale, alpha, rgb, jitter in styles:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        jittered = [
            (
                x + rng.uniform(-jitter, jitter) * scale,
                y + rng.uniform(-jitter, jitter) * scale,
            )
            for x, y in pts
        ]
        draw_polyline(layer, jittered, round(base_width * width_scale), (*rgb, alpha))
        alpha_arr = np.array(layer.getchannel("A")).astype(np.float32)
        noise = rng_np(rng).normal(0.88 if mode == "pencil" else 0.78, 0.18 if mode == "pencil" else 0.28, alpha_arr.shape)
        alpha_arr = np.clip(alpha_arr * noise, 0, 255).astype(np.uint8)
        layer.putalpha(Image.fromarray(alpha_arr, "L").filter(ImageFilter.GaussianBlur(0.15 if mode == "pencil" else 0.35)))
        canvas.alpha_composite(layer)


def add_atmosphere(img: Image.Image, mode: str, frame: int, rng: random.Random, pure_background: bool = False) -> Image.Image:
    if pure_background:
        return img.convert("RGB")
    arr = np.array(img.convert("RGBA")).astype(np.int16)
    h, w = arr.shape[:2]
    if mode == "chalk":
        dust = rng_np(rng).random((h, w))
        mask = dust > 0.996
        arr[mask, :3] = np.clip(arr[mask, :3] + 70, 0, 255)
        arr[mask, 3] = 255
    else:
        grain = rng_np(rng).normal(0, 3, (h, w, 1))
        arr[:, :, :3] = np.clip(arr[:, :, :3] + grain, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA").convert("RGB")


def render(svg: Path, outdir: Path, mode: str, fps: int, seconds: float, scale: int, ffmpeg: Path, pure_background: bool, basename: str, color_value: str | None) -> Path:
    w, h, paths = read_svg(svg)
    w *= scale
    h *= scale
    total_frames = int(round(fps * seconds))
    frame_dir = outdir / f"{mode}_frames"
    shutil.rmtree(frame_dir, ignore_errors=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    draw_duration = max(0.26, seconds * 0.82 / max(1, len(paths)))
    stagger = 0.075
    for frame in range(total_frames):
        t = frame / fps
        rng = random.Random(1000 + frame)
        bg = make_background(w, h, mode, rng, pure=pure_background).convert("RGBA")
        for idx, path in enumerate(paths):
            start = idx * stagger
            progress = (t - start) / draw_duration
            progress = max(0.0, min(1.0, progress))
            eased = 1 - (1 - progress) ** 3
            pts = partial_points(path["points"], eased)
            pts = [(x * scale, y * scale) for x, y in pts]
            fallback = (17, 17, 17) if mode == "clean" else ((44, 43, 39) if mode == "pencil" else (248, 244, 225))
            stroke_color = parse_hex_color(color_value, fallback)
            textured_stroke(bg, pts, path["width"] * scale, mode, rng, scale, color=stroke_color)
        frame_img = add_atmosphere(bg, mode, frame, rng, pure_background=pure_background)
        frame_img.save(frame_dir / f"frame_{frame:04d}.png")

    suffix = "purebg.video" if pure_background else "video"
    out = outdir / f"{basename}.{mode}.{suffix}.mp4"
    cmd = [
        str(ffmpeg),
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frame_dir / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("svg")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--mode", choices=["clean", "pencil", "chalk"], required=True)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--seconds", type=float, default=4.6)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--ffmpeg", default="work/ffmpeg-bin/ffmpeg")
    parser.add_argument("--pure-background", action="store_true")
    parser.add_argument("--basename", default="stroke-animation")
    parser.add_argument("--color", help="Optional stroke color tint, e.g. '#111111'")
    args = parser.parse_args()

    out = render(
        Path(args.svg),
        Path(args.outdir),
        args.mode,
        args.fps,
        args.seconds,
        args.scale,
        Path(args.ffmpeg),
        args.pure_background,
        args.basename,
        args.color,
    )
    print(out)


if __name__ == "__main__":
    main()
