#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


TOKEN_RE = re.compile(r"[MLCQZmlcqz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


TEXTURES = {
    "pencil": [
        {"scale": 0.62, "opacity": 46, "color": [0.19, 0.19, 0.18, 1], "offset": [-0.55, -0.25]},
        {"scale": 0.38, "opacity": 34, "color": [0.08, 0.08, 0.075, 1], "offset": [0.35, 0.40]},
        {"scale": 0.22, "opacity": 20, "color": [0.36, 0.35, 0.32, 1], "offset": [0.75, -0.50]},
    ],
    "chalk": [
        {"scale": 1.16, "opacity": 38, "color": [0.04, 0.04, 0.04, 1], "offset": [-0.85, -0.25]},
        {"scale": 0.92, "opacity": 54, "color": [0.08, 0.08, 0.075, 1], "offset": [0.35, 0.55]},
        {"scale": 0.56, "opacity": 28, "color": [0.30, 0.30, 0.28, 1], "offset": [1.15, -0.75]},
        {"scale": 0.24, "opacity": 18, "color": [0.00, 0.00, 0.00, 1], "offset": [-1.35, 0.90]},
    ],
}


def parse_hex_color(value: str | None):
    if not value:
        return None
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return [int(value[1:3], 16) / 255, int(value[3:5], 16) / 255, int(value[5:7], 16) / 255, 1]
    if value.lower() == "black":
        return [0, 0, 0, 1]
    if value.lower() == "white":
        return [1, 1, 1, 1]
    return None


def tint_styles(styles, color):
    if color is None:
        return styles
    factors = [0.72, 0.48, 1.12, 0.86, 1.0]
    tinted = []
    for index, style in enumerate(styles):
        factor = factors[index % len(factors)]
        next_style = dict(style)
        next_style["color"] = [min(1, max(0, color[0] * factor)), min(1, max(0, color[1] * factor)), min(1, max(0, color[2] * factor)), 1]
        tinted.append(next_style)
    return tinted


def parse_path(d: str):
    tokens = TOKEN_RE.findall(d)
    i = 0
    cmd = None
    current = (0.0, 0.0)
    start = None
    vertices = []
    in_tangents = []
    out_tangents = []
    closed = False

    def is_cmd(value):
        return bool(re.fullmatch(r"[MLCQZmlcqz]", value))

    def number():
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    def add_vertex(point, in_t=(0.0, 0.0), out_t=(0.0, 0.0)):
        vertices.append([point[0], point[1]])
        in_tangents.append([in_t[0], in_t[1]])
        out_tangents.append([out_t[0], out_t[1]])

    while i < len(tokens):
        if is_cmd(tokens[i]):
            cmd = tokens[i]
            i += 1
        if cmd is None:
            raise ValueError("Path starts without a command")
        absolute = cmd.isupper()
        lower = cmd.lower()
        if lower == "m":
            x, y = number(), number()
            if not absolute:
                x += current[0]
                y += current[1]
            current = (x, y)
            start = current
            add_vertex(current)
            cmd = "L" if absolute else "l"
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = number(), number()
                if not absolute:
                    x += current[0]
                    y += current[1]
                current = (x, y)
                add_vertex(current)
        elif lower == "l":
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = number(), number()
                if not absolute:
                    x += current[0]
                    y += current[1]
                current = (x, y)
                add_vertex(current)
        elif lower == "c":
            while i < len(tokens) and not is_cmd(tokens[i]):
                c1 = (number(), number())
                c2 = (number(), number())
                end = (number(), number())
                if not absolute:
                    c1 = (c1[0] + current[0], c1[1] + current[1])
                    c2 = (c2[0] + current[0], c2[1] + current[1])
                    end = (end[0] + current[0], end[1] + current[1])
                if out_tangents:
                    out_tangents[-1] = [c1[0] - current[0], c1[1] - current[1]]
                add_vertex(end, in_t=(c2[0] - end[0], c2[1] - end[1]))
                current = end
        elif lower == "q":
            while i < len(tokens) and not is_cmd(tokens[i]):
                c = (number(), number())
                end = (number(), number())
                if not absolute:
                    c = (c[0] + current[0], c[1] + current[1])
                    end = (end[0] + current[0], end[1] + current[1])
                c1 = (current[0] + 2 / 3 * (c[0] - current[0]), current[1] + 2 / 3 * (c[1] - current[1]))
                c2 = (end[0] + 2 / 3 * (c[0] - end[0]), end[1] + 2 / 3 * (c[1] - end[1]))
                if out_tangents:
                    out_tangents[-1] = [c1[0] - current[0], c1[1] - current[1]]
                add_vertex(end, in_t=(c2[0] - end[0], c2[1] - end[1]))
                current = end
        elif lower == "z":
            closed = True
            if start is not None:
                current = start
        else:
            raise ValueError(f"Unsupported path command {cmd}")
    return {"c": closed, "v": vertices, "i": in_tangents, "o": out_tangents}


def path_length(shape):
    pts = shape["v"]
    return max(1.0, sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])))


def svg_size(root):
    width = float(root.attrib.get("width", "800").replace("px", ""))
    height = float(root.attrib.get("height", "600").replace("px", ""))
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = [float(x) for x in view_box.replace(",", " ").split()]
        if len(parts) == 4:
            width, height = parts[2], parts[3]
    return int(round(width)), int(round(height))


def make_layer(index, name, shape_data, stroke_width, style, start_frame, end_frame, total_frames):
    return {
        "ddd": 0,
        "ind": index,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": {
            "o": {"a": 0, "k": style["opacity"]},
            "r": {"a": 0, "k": 0},
            "p": {"a": 0, "k": [style["offset"][0], style["offset"][1], 0]},
            "a": {"a": 0, "k": [0, 0, 0]},
            "s": {"a": 0, "k": [100, 100, 100]},
        },
        "ao": 0,
        "shapes": [
            {
                "ty": "gr",
                "it": [
                    {"ty": "shape", "ks": {"a": 0, "k": shape_data}, "nm": "path"},
                    {
                        "ty": "st",
                        "c": {"a": 0, "k": style["color"]},
                        "o": {"a": 0, "k": 100},
                        "w": {"a": 0, "k": max(0.5, stroke_width * style["scale"])},
                        "lc": 2,
                        "lj": 2,
                        "nm": "textured_stroke",
                    },
                    {
                        "ty": "tm",
                        "s": {"a": 0, "k": 0},
                        "e": {"a": 1, "k": [{"t": start_frame, "s": [0]}, {"t": end_frame, "s": [100]}]},
                        "o": {"a": 0, "k": 0},
                        "nm": "draw",
                    },
                ],
                "nm": "stroke_group",
            }
        ],
        "ip": 0,
        "op": total_frames,
        "st": 0,
        "bm": 0,
    }


def convert(svg_path: Path, texture: str, fps: int, seconds: float, stagger: float, color: str | None = None):
    root = ET.parse(svg_path).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    width, height = svg_size(root)
    paths = root.findall(f".//{ns}path")
    styles = tint_styles(TEXTURES[texture], parse_hex_color(color))
    total_frames = int(fps * seconds)
    draw_frames = max(6, int((total_frames * 0.82) / max(1, len(paths))))
    stagger_frames = max(1, int(fps * stagger))
    layers = []
    layer_index = 1
    for path_index, element in enumerate(paths, start=1):
        shape_data = parse_path(element.attrib.get("d", ""))
        base_width = float(element.attrib.get("stroke-width", "8"))
        start = (path_index - 1) * stagger_frames
        end = min(total_frames - 1, start + draw_frames)
        for style_index, style in enumerate(styles, start=1):
            layers.append(
                make_layer(
                    layer_index,
                    f"stroke_{path_index:03d}_texture_{style_index}",
                    shape_data,
                    base_width,
                    style,
                    start,
                    end,
                    total_frames,
                )
            )
            layer_index += 1
    return {
        "v": "5.12.2",
        "fr": fps,
        "ip": 0,
        "op": total_frames,
        "w": width,
        "h": height,
        "nm": f"{svg_path.stem}_{texture}",
        "ddd": 0,
        "assets": [],
        "layers": layers,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("svg")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--basename", required=True)
    parser.add_argument("--texture", choices=sorted(TEXTURES), required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--seconds", type=float, default=4.2)
    parser.add_argument("--stagger", type=float, default=0.075)
    parser.add_argument("--color", help="Optional texture color tint, e.g. '#111111'")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    source = outdir / f"{args.basename}.source.svg"
    if not source.exists():
        shutil.copyfile(args.svg, source)
    lottie = convert(Path(args.svg), args.texture, args.fps, args.seconds, args.stagger, args.color)
    lottie_path = outdir / f"{args.basename}.{args.texture}.lottie.json"
    lottie_path.write_text(json.dumps(lottie, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"texture": args.texture, "layers": len(lottie["layers"]), "lottie": str(lottie_path)}, indent=2))


if __name__ == "__main__":
    main()
