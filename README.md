# Stroke SVG Animation Skill

Codex skill for converting stroke-only SVG artwork into line-growth animations.

It supports:

- Clean Lottie vector animation
- Pencil-textured Lottie animation
- Chalk-textured Lottie animation
- Optional frame-rendered MP4 output
- Preview HTML for checking the animation locally

## Install

Install this skill from GitHub with Codex's skill installer:

```bash
install-skill-from-github.py --repo OWNER/REPO --path stroke-svg-animation
```

If installing from a specific branch or tag:

```bash
install-skill-from-github.py --repo OWNER/REPO --ref main --path stroke-svg-animation
```

Restart Codex after installing so the skill is discovered.

## Use

Ask Codex something like:

```text
Use stroke-svg-animation to convert this stroke-only SVG into a pencil Lottie, preserving the SVG colors.
```

Good SVG inputs use independent paths, for example:

```svg
<path d="M10 10 C20 20 40 20 50 10" fill="none" stroke="#111111" stroke-width="8" stroke-linecap="round"/>
```

## Repository Layout

```text
.
├── stroke-svg-animation/   # The installable Codex skill
├── scripts/                # Maintainer scripts
├── CHANGELOG.md
├── LICENSE
└── README.md
```

Keep user-facing documentation in the repository root. Keep the skill folder focused on `SKILL.md`, `agents/`, and bundled resources used by Codex.

## Maintain

Validate before publishing:

```bash
python3 scripts/validate_skill.py stroke-svg-animation
```

Typical update flow:

```bash
git status
python3 scripts/validate_skill.py stroke-svg-animation
git add .
git commit -m "Update stroke SVG animation skill"
git push
```

## License

MIT
