#!/usr/bin/env python3
# pii-scanner-definition
"""Strict no-PII scanner: keeps the skills, docs and tests in this repo generic.

Ported from combsmith/google-app-scripts `scripts/check-no-pii.js`, same model:

* BASE_RULES below are generic and public: household surname outside the author's own
  public name, personal Gmail addresses, US Social Security numbers, private-network IPs.
* Household-specific rules (first names, addresses, schools, local businesses, account
  numbers) are supplied OUT OF BAND and never committed:
    - `PII_CUSTOM_RULES_JSON` environment variable (CI: a repository secret), or
    - `.pii-rules.json` in the repo root (gitignored).
  Format: a JSON array of {"name", "pattern", "flags"?, "description"?, "whitelist"?: [regex]}.
  Patterns are Python `re` syntax; flags may contain "i".
* Scans every text file: any extension, including extensionless files; binary files are
  skipped by extension and refused if they contain NUL bytes.
* Full mode scans git-tracked files (what CI sees); --staged scans the staged blobs
  (what is about to be committed). A file that cannot be read fails the check.
* Inline escape hatch: a line containing `pii-ignore` is skipped. Use sparingly.

Usage:
    python3 tools/check_no_pii.py            # every git-tracked file
    python3 tools/check_no_pii.py --staged   # staged blobs only (pre-commit)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Rule:
    name: str
    pattern: re.Pattern
    description: str
    whitelist: list = field(default_factory=list)   # regexes; a match inside one is allowed
    skip_files: tuple = ()                          # posix paths this rule does not apply to


# The author's public profile files name him and give his public contact address on purpose.
PROFILE_FILES = ("CV.md", "README.md")

BASE_RULES = [
    Rule(
        "Household surname",
        re.compile(r"\bPetry\b", re.I),
        "Household surname outside the author's public name; use a placeholder family.",
        [re.compile(p, re.I) for p in (r"don-petry", r"github\.com/don-petry", r"Don Petry",
                                        r"Copyright \(c\) \d{4} Don Petry", r"petry-projects")],
        PROFILE_FILES,
    ),
    Rule(
        "Personal Gmail address",
        re.compile(r"\b[a-zA-Z0-9._%+-]+@gmail\.com\b", re.I),
        "Personal Gmail addresses must not be committed; use name@example.com.",
        [re.compile(r"^(your-email|household-member|testuser)@gmail\.com$", re.I)],
        PROFILE_FILES,
    ),
    Rule(
        "US Social Security number",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "Social Security numbers must never be committed.",
        [re.compile(r"^(000-00-0000|123-45-6789)$")],
    ),
    Rule(
        "Private network address",
        re.compile(r"(?<![\d.])(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?![\d.])"),
        "Home-network IPs identify a household; use the documentation range 192.0.2.x.",
    ),
]

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".heic", ".tif", ".tiff", ".pdf",
    ".zip", ".gz", ".tgz", ".7z", ".jar", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3",
    ".mp4", ".mov", ".wasm", ".stl", ".3mf", ".step", ".dwg",
}
IGNORED_PATHS = {"tools/check_no_pii.py", "tools/test_check_no_pii.py", ".pii-rules.json"}


def load_custom_rules(env: dict | None = None, root: Path = REPO_ROOT) -> list[Rule]:
    env = os.environ if env is None else env
    raw = env.get("PII_CUSTOM_RULES_JSON", "")
    if not raw and (root / ".pii-rules.json").exists():
        raw = (root / ".pii-rules.json").read_text(encoding="utf-8")
    if not raw.strip():
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"Error parsing custom PII rules: {e}")
    rules = []
    for e in entries if isinstance(entries, list) else []:
        if not (isinstance(e, dict) and e.get("name") and e.get("pattern")):
            continue
        flags = re.I if "i" in e.get("flags", "i") else 0
        rules.append(Rule(
            e["name"],
            re.compile(e["pattern"], flags),
            e.get("description", "Prohibited custom PII pattern."),
            [re.compile(w, re.I) for w in e.get("whitelist", [])],
            tuple(e.get("skip_files", ())),
        ))
    return rules


def scannable(rel: str) -> bool:
    return Path(rel).suffix.lower() not in BINARY_EXTENSIONS and rel not in IGNORED_PATHS


def whitelisted(line: str, m: re.Match, whitelist: list) -> bool:
    for wl in whitelist:
        if wl.search(m.group(0)):          # the matched text itself is allowed
            return True
        for w in wl.finditer(line):
            if w.start() <= m.start() and m.end() <= w.end():
                return True
    return False


def scan_text(rel: str, text: str, rules: list[Rule]) -> list[dict]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if "pii-ignore" in line:
            continue
        for r in rules:
            if rel in r.skip_files:
                continue
            for m in r.pattern.finditer(line):
                if not whitelisted(line, m, r.whitelist):
                    out.append({"file": rel, "line": n, "rule": r.name, "match": m.group(0),
                                "description": r.description})
    return out


def decode(data: bytes, rel: str) -> str:
    if data[:2] == b"\xff\xfe":
        return data.decode("utf-16-le", errors="replace")
    if data[:2] == b"\xfe\xff":
        return data.decode("utf-16-be", errors="replace")
    if b"\0" in data:
        sys.exit(f"Error: {rel} contains binary/NUL bytes; cannot scan for PII")
    return data.decode("utf-8", errors="replace")


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True).stdout


def main(argv: list[str]) -> int:
    staged = "--staged" in argv
    rules = BASE_RULES + load_custom_rules()
    if staged:
        files = [f for f in git("diff", "--cached", "-z", "--name-only", "--diff-filter=ACMR").decode().split("\0") if f]
    else:
        files = [f for f in git("ls-files", "-z").decode().split("\0") if f]
    files = [f for f in files if scannable(f)]
    violations = []
    for rel in files:
        try:
            if staged:
                data = git("show", f":{rel}")
            else:
                p = REPO_ROOT / rel
                if p.is_symlink() or not p.is_file():
                    continue
                data = p.read_bytes()
        except (OSError, subprocess.CalledProcessError) as e:
            sys.exit(f"Error reading {rel}: {e}. Cannot scan for PII; failing the check.")
        violations += scan_text(rel, decode(data, rel), rules)
    if violations:
        print("\n❌ PII CHECK FAILED — prohibited personal information detected:", file=sys.stderr)
        for v in violations:
            print(f"• [{v['rule']}] {v['file']}:{v['line']}\n  Matched: \"{v['match']}\"\n  Remedy: {v['description']}",
                  file=sys.stderr)
        print("\nThis repo holds generic skills. A household's own details belong in each skill's\n"
              "gitignored config/household.yaml, never in a commit.", file=sys.stderr)
        return 1
    custom = len(rules) - len(BASE_RULES)
    print(f"✅ No-PII check passed ({len(files)} file(s), {len(BASE_RULES)} base + {custom} custom rule(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
