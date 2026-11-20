#!/usr/bin/env python3
"""Lint skills/ and agents/ against the agent-neutral standard. Exit 1 on any error.

Skills follow the Agent Skills format (https://agentskills.io): a folder with SKILL.md whose
frontmatter holds only name, description, license, compatibility and metadata. Nothing in a skill
may depend on one harness: no harness tool names (mcp__...), no harness config paths (.claude/...).
Personas in agents/ carry name and description only, so every harness can load them.

    python3 tools/lint_skills.py
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_KEYS = {"name", "description", "license", "compatibility", "metadata"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HARNESS_RE = re.compile(r"mcp__|(?<![\w/])~?/?\.claude/|allowed-tools:")
TEXT = {".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt", ".html", ".toml"}


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body


def main():
    errors, warnings = [], []
    for d in sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir()):
        md = d / "SKILL.md"
        if not md.exists():
            errors.append(f"{d.name}: missing SKILL.md")
            continue
        try:
            fm, body = frontmatter(md)
        except yaml.YAMLError as e:
            errors.append(f"{d.name}/SKILL.md: frontmatter is not valid YAML: {str(e).splitlines()[0]}")
            continue
        if fm is None:
            errors.append(f"{d.name}/SKILL.md: no YAML frontmatter")
            continue
        if set(fm) - SKILL_KEYS:
            errors.append(f"{d.name}/SKILL.md: non-standard frontmatter keys {sorted(set(fm) - SKILL_KEYS)}")
        name = str(fm.get("name", ""))
        if name != d.name or not NAME_RE.match(name) or len(name) > 64:
            errors.append(f"{d.name}/SKILL.md: name '{name}' must equal the folder name (lowercase, hyphens, <=64)")
        desc = str(fm.get("description", ""))
        if not 1 <= len(desc) <= 1024:
            errors.append(f"{d.name}/SKILL.md: description must be 1-1024 characters (is {len(desc)})")
        if "metadata" in fm and not all(isinstance(v, str) for v in (fm["metadata"] or {}).values()):
            errors.append(f"{d.name}/SKILL.md: metadata values must be strings")
        if len(body.splitlines()) > 500:
            warnings.append(f"{d.name}/SKILL.md: body is {len(body.splitlines())} lines (standard advises < 500)")
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in TEXT:
                for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if HARNESS_RE.search(line):
                        errors.append(f"{f.relative_to(ROOT)}:{n}: harness-specific reference: {line.strip()[:100]}")
    for f in sorted((ROOT / "agents").glob("*")) if (ROOT / "agents").exists() else []:
        if f.suffix != ".md":
            errors.append(f"agents/{f.name}: agents/ holds persona .md files only")
            continue
        try:
            fm, _ = frontmatter(f)
        except yaml.YAMLError:
            fm = None
        if not fm or set(fm) != {"name", "description"} or fm.get("name") != f.stem:
            errors.append(f"agents/{f.name}: frontmatter must be exactly name (= file name) and description")
    for w in warnings:
        print("warn ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
