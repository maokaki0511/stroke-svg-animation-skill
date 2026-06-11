#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
]


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("SKILL.md frontmatter must be closed with ---")
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: validate_skill.py <skill-folder>")

    skill_dir = Path(sys.argv[1])
    if not skill_dir.is_dir():
        raise SystemExit(f"Not a directory: {skill_dir}")

    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (skill_dir / relative).is_file():
            errors.append(f"Missing required file: {relative}")

    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        try:
            fields = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            name = fields.get("name")
            description = fields.get("description")
            if not name:
                errors.append("SKILL.md frontmatter missing name")
            elif not re.fullmatch(r"[a-z0-9-]{1,63}", name):
                errors.append("Skill name must use lowercase letters, digits, and hyphens only")
            elif skill_dir.name != name:
                errors.append(f"Skill folder name must match skill name: {name}")
            if not description:
                errors.append("SKILL.md frontmatter missing description")
        except ValueError as exc:
            errors.append(str(exc))

    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for script in scripts_dir.glob("*.py"):
            compile(script.read_text(encoding="utf-8"), str(script), "exec")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)

    print(f"OK: {skill_dir}")


if __name__ == "__main__":
    main()
