---
name: stroke-svg-animation
description: Convert user-provided stroke-only SVGs into line-growth animations. Use when the user provides an SVG made of independent line paths and wants Lottie or video output, with clean, pencil, or chalk styles, color control, preview HTML, and optional high-quality frame-rendered MP4.
---

# Stroke SVG Animation

Use this skill when the user gives an SVG whose artwork is already made from independent line paths and wants the lines to grow on over time.

## Input Contract

The source SVG should contain independent line paths:

```svg
<path d="..." fill="none" stroke="#111111" stroke-width="9" stroke-linecap="round"/>
```

Requirements:

- Prefer one visual stroke per `<path>`.
- `fill` should be `none`; filled outline shapes are not valid input for this skill.
- SVG path order controls animation order unless the user asks for a different order.
- Preserve `stroke-width`, `stroke-linecap`, and `stroke-linejoin` from the source.
- Ask for color only if the user has not specified one; default to `#111111`.

## Output Tracks

Keep Lottie and video separate.

### Lottie Track

Use Lottie for lightweight vector playback.

Styles:

- `clean`: one Lottie shape layer per source path.
- `pencil`: each source path becomes 3 semi-transparent vector layers.
- `chalk`: each source path becomes 4 semi-transparent vector layers.

Commands:

```bash
python3 scripts/svg_strokes_to_lottie.py input.svg --outdir out --basename title --color '#111111'
python3 scripts/svg_strokes_to_textured_lottie.py out/title.source.svg --outdir out --basename title --texture pencil --color '#111111'
python3 scripts/svg_strokes_to_textured_lottie.py out/title.source.svg --outdir out --basename title --texture chalk --color '#111111'
python3 scripts/make_lottie_texture_preview.py --out out/texture-preview.html --source-svg title.source.svg --path-count 29 --color '#111111'
```

Preview the Lottie-style result by serving `out/texture-preview.html`. The preview should match the interaction pattern of the proven local page `texture-preview.html`: buttons for `clean`, `pencil`, `chalk`, plus replay.

### Video Track

Use video for richer raster rendering. Video is rendered frame-by-frame and encoded with `ffmpeg`.

Styles:

- `clean`: clean line-growth video on a fixed pure background.
- `pencil`: frame-rendered pencil texture on a fixed pure background.
- `chalk`: frame-rendered chalk texture on a fixed pure background.

Commands:

```bash
python3 scripts/svg_strokes_to_video.py input.svg --outdir out --basename title --mode clean --color '#111111' --pure-background --ffmpeg /path/to/ffmpeg
python3 scripts/svg_strokes_to_video.py input.svg --outdir out --basename title --mode pencil --color '#111111' --pure-background --ffmpeg /path/to/ffmpeg
python3 scripts/svg_strokes_to_video.py input.svg --outdir out --basename title --mode chalk --color '#f8f4e1' --pure-background --ffmpeg /path/to/ffmpeg
```

If the user asks for “Lottie pencil/chalk as video,” render or capture the Lottie preview separately; do not confuse it with the frame-rendered `pencil`/`chalk` video track. Prefer frame-rendered video when the user wants richer texture.

## Validation

Before generating:

1. Parse the SVG and count `<path>` elements.
2. Confirm the paths are stroke-only (`fill` absent or `none`).
3. Report if filled shapes, images, masks, or unsupported elements are present.

After generating:

1. Run `python3 -m json.tool` on Lottie JSON outputs.
2. Use `ffmpeg -i` to check MP4 duration, size, and fps.
3. Give the user links to the generated files and the preview page.

## Notes

- This skill does not convert filled typography into centerline strokes. The user should provide the stroke-only SVG.
- Keep backgrounds stable in video unless the user explicitly requests animated background texture.
- For high-quality video, prefer `--scale 2`, `24fps`, `4-6s`, and `--pure-background`.
