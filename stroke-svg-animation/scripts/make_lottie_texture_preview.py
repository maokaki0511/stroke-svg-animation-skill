#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stroke Lottie Texture Preview</title>
  <style>
    :root { background: #f6f3ed; color: #1a1916; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 28px; }
    main { width: min(1040px, 100%); }
    .bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    h1 { margin: 0; font-size: 18px; letter-spacing: 0; }
    .controls { display: flex; gap: 8px; flex-wrap: wrap; }
    button { height: 38px; padding: 0 14px; border: 1px solid #222; border-radius: 6px; background: #fff; color: #1d1d1b; font-size: 14px; cursor: pointer; }
    button.active, #replay { background: #1d1d1b; color: #fff; }
    .stage { background: #fff; border: 1px solid #ddd8cc; border-radius: 8px; overflow: hidden; padding: 24px; }
    #preview { width: 100%; min-height: 280px; display: grid; place-items: center; overflow: auto; }
    #preview svg { width: 100%; height: auto; display: block; }
    p { margin: 14px 0 0; color: #6b6258; font-size: 14px; line-height: 1.6; }
  </style>
</head>
<body>
  <main>
    <div class="bar">
      <h1>Stroke texture preview</h1>
      <div class="controls">
        <button class="active" data-mode="clean" type="button">clean</button>
        <button data-mode="pencil" type="button">pencil</button>
        <button data-mode="chalk" type="button">chalk</button>
        <button id="replay" type="button">重新播放</button>
      </div>
    </div>
    <section class="stage"><div id="preview"></div></section>
    <p>预览使用 SVG dash 动画模拟；同目录中的 Lottie JSON 使用 shape layer + trim path。</p>
  </main>
  <script>
    const duration = __DURATION_MS__;
    const stagger = __STAGGER_MS__;
    const preview = document.querySelector("#preview");
    const modes = {
      clean: [{ scale: 1, opacity: 1, color: "__COLOR__", offset: [0, 0] }],
      pencil: [
        { scale: 0.62, opacity: 0.46, color: "__COLOR__", offset: [-0.55, -0.25] },
        { scale: 0.38, opacity: 0.34, color: "__COLOR__", offset: [0.35, 0.40] },
        { scale: 0.22, opacity: 0.20, color: "__COLOR__", offset: [0.75, -0.50] }
      ],
      chalk: [
        { scale: 1.16, opacity: 0.38, color: "__COLOR__", offset: [-0.85, -0.25] },
        { scale: 0.92, opacity: 0.54, color: "__COLOR__", offset: [0.35, 0.55] },
        { scale: 0.56, opacity: 0.28, color: "__COLOR__", offset: [1.15, -0.75] },
        { scale: 0.24, opacity: 0.18, color: "__COLOR__", offset: [-1.35, 0.90] }
      ]
    };
    let baseSvg = "";
    let activeMode = "clean";
    let paths = [];
    let token = 0;
    function renderMode(mode) {
      activeMode = mode;
      token += 1;
      const localToken = token;
      preview.innerHTML = baseSvg;
      const svg = preview.querySelector("svg");
      const originals = Array.from(svg.querySelectorAll("path"));
      const styles = modes[mode];
      originals.forEach((path) => path.remove());
      originals.forEach((path) => {
        styles.forEach((style) => {
          const clone = path.cloneNode(true);
          const width = Number(path.getAttribute("stroke-width") || 8);
          clone.setAttribute("stroke-width", String(Math.max(0.5, width * style.scale)));
          clone.setAttribute("stroke", style.color);
          clone.setAttribute("opacity", String(style.opacity));
          clone.setAttribute("transform", `translate(${style.offset[0]} ${style.offset[1]})`);
          svg.appendChild(clone);
        });
      });
      prepare();
      animate(performance.now(), localToken);
    }
    function prepare() {
      paths = Array.from(preview.querySelectorAll("path"));
      paths.forEach((path) => {
        const length = path.getTotalLength();
        path.dataset.length = String(length);
        path.style.strokeDasharray = String(length);
        path.style.strokeDashoffset = String(length);
      });
    }
    function animate(startTime, localToken) {
      function frame(now) {
        const elapsed = (now - startTime) % duration;
        const perPath = Math.max(260, (duration * 0.82) / __SOURCE_PATH_COUNT__);
        paths.forEach((path, index) => {
          const sourceIndex = Math.floor(index / modes[activeMode].length);
          const begin = sourceIndex * stagger;
          const progress = Math.max(0, Math.min(1, (elapsed - begin) / perPath));
          const eased = 1 - Math.pow(1 - progress, 3);
          const length = Number(path.dataset.length);
          path.style.strokeDashoffset = String(length * (1 - eased));
        });
        if (token === localToken) requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    }
    document.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-mode]").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        renderMode(button.dataset.mode);
      });
    });
    document.querySelector("#replay").addEventListener("click", () => renderMode(activeMode));
    fetch("./__SOURCE_SVG__").then((response) => response.text()).then((svg) => { baseSvg = svg; renderMode("clean"); });
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--source-svg", required=True)
    parser.add_argument("--path-count", type=int, required=True)
    parser.add_argument("--seconds", type=float, default=4.2)
    parser.add_argument("--stagger", type=float, default=0.075)
    parser.add_argument("--color", default="#111111")
    args = parser.parse_args()
    html = (
        HTML.replace("__SOURCE_SVG__", args.source_svg)
        .replace("__SOURCE_PATH_COUNT__", str(args.path_count))
        .replace("__DURATION_MS__", str(round(args.seconds * 1000)))
        .replace("__STAGGER_MS__", str(round(args.stagger * 1000)))
        .replace("__COLOR__", args.color)
    )
    Path(args.out).write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
