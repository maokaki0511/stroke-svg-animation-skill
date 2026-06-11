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
            raise ValueError(f"Path starts without command: {d[:40]}")

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
                c1 = (current[0] + 2.0 / 3.0 * (c[0] - current[0]), current[1] + 2.0 / 3.0 * (c[1] - current[1]))
                c2 = (end[0] + 2.0 / 3.0 * (c[0] - end[0]), end[1] + 2.0 / 3.0 * (c[1] - end[1]))
                if out_tangents:
                    out_tangents[-1] = [c1[0] - current[0], c1[1] - current[1]]
                add_vertex(end, in_t=(c2[0] - end[0], c2[1] - end[1]))
                current = end
        elif lower == "z":
            closed = True
            if start is not None:
                current = start
        else:
            raise ValueError(f"Unsupported SVG path command: {cmd}")

    return {"c": closed, "v": vertices, "i": in_tangents, "o": out_tangents}


def parse_color(value: str):
    if not value or value in ("black", "#000"):
        return [0, 0, 0, 1]
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return [int(value[1:3], 16) / 255, int(value[3:5], 16) / 255, int(value[5:7], 16) / 255, 1]
    return [0, 0, 0, 1]


def path_len(shape):
    total = 0.0
    pts = shape["v"]
    for a, b in zip(pts, pts[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    return max(1.0, total)


def svg_to_lottie(svg_path: Path, name: str, fps: int, seconds: float, stagger: float, color_override: str | None = None):
    root = ET.parse(svg_path).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    width = float(root.attrib.get("width", "800").replace("px", ""))
    height = float(root.attrib.get("height", "600").replace("px", ""))
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = [float(x) for x in view_box.replace(",", " ").split()]
        if len(parts) == 4:
            width, height = parts[2], parts[3]

    paths = root.findall(f".//{ns}path")
    total_frames = int(fps * seconds)
    layers = []
    draw_frames = max(5, int((total_frames * 0.82) / max(1, len(paths))))
    stagger_frames = max(1, int(fps * stagger))

    for idx, element in enumerate(paths, start=1):
        d = element.attrib.get("d", "")
        if not d:
            continue
        shape_data = parse_path(d)
        start_frame = (idx - 1) * stagger_frames
        end_frame = min(total_frames - 1, start_frame + draw_frames)
        stroke_width = float(element.attrib.get("stroke-width", "8"))
        stroke = parse_color(color_override or element.attrib.get("stroke", "black"))
        layer = {
            "ddd": 0,
            "ind": idx,
            "ty": 4,
            "nm": element.attrib.get("id") or f"stroke_{idx:03d}",
            "sr": 1,
            "ks": {
                "o": {"a": 0, "k": 100},
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [0, 0, 0]},
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
                            "c": {"a": 0, "k": stroke},
                            "o": {"a": 0, "k": 100},
                            "w": {"a": 0, "k": stroke_width},
                            "lc": 2,
                            "lj": 2,
                            "nm": "stroke",
                        },
                        {
                            "ty": "tm",
                            "s": {"a": 0, "k": 0},
                            "e": {
                                "a": 1,
                                "k": [
                                    {"t": start_frame, "s": [0]},
                                    {"t": end_frame, "s": [100]},
                                ],
                            },
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
        layers.append(layer)

    return {
        "v": "5.12.2",
        "fr": fps,
        "ip": 0,
        "op": total_frames,
        "w": int(round(width)),
        "h": int(round(height)),
        "nm": name,
        "ddd": 0,
        "assets": [],
        "layers": layers,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("svg")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--basename", default="animated-strokes")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--stagger", type=float, default=0.075)
    parser.add_argument("--color", help="Optional stroke color override, e.g. '#111111'")
    args = parser.parse_args()

    src = Path(args.svg)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    source_copy = outdir / f"{args.basename}.source.svg"
    shutil.copyfile(src, source_copy)
    lottie = svg_to_lottie(source_copy, args.basename, args.fps, args.seconds, args.stagger, args.color)
    lottie_path = outdir / f"{args.basename}.lottie.json"
    lottie_path.write_text(json.dumps(lottie, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "source_svg": str(source_copy),
        "lottie_json": str(lottie_path),
        "path_count": len(lottie["layers"]),
        "fps": args.fps,
        "seconds": args.seconds,
        "stagger": args.stagger,
    }
    manifest_path = outdir / f"{args.basename}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
