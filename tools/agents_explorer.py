#!/usr/bin/env python3
"""Agents & skills explorer — a one-page HTML catalog of a repo's Agent Skills and personas.

WHY THIS EXISTS
  A hand-written catalog goes stale the moment a skill is added. So the FACTS are derived
  from the repo on every build — names, descriptions, triggers, tools, file lists, sizes,
  revision counts and dates — and only the EDITORIAL layer (the "how it works" bullets, the
  "worth knowing" notes, the pipelines) is hand-written, in an optional notes file.

  A skill or persona with no annotation still appears, correct and complete, using its own
  frontmatter description. Prose is a bonus, never a prerequisite. With no notes file at
  all the page is built from frontmatter alone.

WHAT IT READS (all paths relative to --root)
  skills/<name>/SKILL.md      Agent Skills (agentskills.io layout)        --skills
  agents/<name>.md            personas: frontmatter name + description    --agents
  .github/workflows/*.yml     GitHub Actions workflows                    --workflows
  notes file (optional)       editorial layer and page settings           --notes

  Defaults are "the repo this script lives in": --root is the parent of the script's folder
  (so tools/agents_explorer.py or scripts/agents_explorer.py both find their repo), and the
  notes file is agents-explorer-notes.json beside the script, if present. Pointing --root at
  another repo uses no notes file unless --notes is given. A missing folder is skipped.

NOTES FILE (JSON, every key optional)
  config        page settings: title, heading, subtitle (HTML), schedule_hint, output
                (default docs/agents-explorer.html), skill_surface, persona_surface,
                persona_invoke ("{path}" is replaced), persona_file_note, connector_label,
                tool_labels [[pattern, label], ...] for connector-style tool names,
                icon_rules [[pattern, icon], ...] tried before the built-in ones,
                acronyms {"Qvr": "QVR", ...} added to the built-in ones
  annotations   per entry: "<skill-folder>", "agent:<persona>", "wf:<file.yml>" ->
                name, icon, status, trigger, does[], tools[], files[], tags[], note, related[]
  entries       extra hand-written entries that cannot be derived (host jobs, rules)
  flows         pipelines shown in the Pipelines view
  public_scrub  {title, rules: [{find, replace}], forbid: [regex]} for the `public` mode

USAGE
  python3 tools/agents_explorer.py build                  # write the page
  python3 tools/agents_explorer.py check                  # exit 1 if the page is stale
  python3 tools/agents_explorer.py public /tmp/page.html  # scrubbed, skeleton-free variant
  python3 tools/agents_explorer.py build --root ../other-repo --out site/agents.html

  `check` belongs in CI and a pre-commit hook: adding, removing or re-describing a skill
  without rebuilding fails it. Git-derived stats (commits, last change) are ignored by the
  comparison, since the commit that rebuilds the page changes them.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent
DEFAULT_NOTES = HERE / "agents-explorer-notes.json"
DEFAULT_TEMPLATE = HERE / "agents_explorer.template.html"

# Fallback icons when an entry has no annotation. The NAME is matched first and the
# description only as a tie-breaker — otherwise every entry that merely mentions "legal"
# in its description ends up wearing the scales. A notes file's icon_rules come first.
ICON_RULES = [
    ("red.?team|adversar", "🥊"), ("verifier|verify", "🔍"),
    ("onboard|interview|discovery", "🧭"), ("equity|job.?offer", "📈"),
    ("intake", "📥"), ("return", "🧾"), ("tax|wealth", "💰"),
    ("legal|court|attorney|statute", "⚖️"),
    ("student|college|career|school|assignment|grade", "🎓"),
    ("clip|camera|snapshot|surveillance", "📷"), ("print", "🖨️"),
    ("flight|airfare", "💺"), ("travel|trip|vacation", "✈️"), ("car|vehicle", "🚗"),
    ("calendar", "🗓️"), ("form|paperwork|pdf", "📝"),
    ("cad|design|drawing", "📐"), ("drive|file|ocr", "🗂️"),
    ("automation|deploy", "🏡"), ("project|manager", "📋"),
    ("health", "🩺"), ("status|report", "📊"), ("post|deck", "📣"),
    ("goods|hunt|packaging", "📦"),
]
DEFAULT_ICON = {"Skill": "🧠", "Agent persona": "🎭", "Scheduled workflow": "⚙️"}
# Words that title-casing gets wrong.
ACRONYMS = {"Ai": "AI", "Api": "API", "Cli": "CLI", "Pdf": "PDF", "Ha": "HA", "Ics": "ICS",
            "Ocr": "OCR", "Cad": "CAD", "Url": "URL", "Ui": "UI"}

DEFAULT_CONFIG = {
    "title": "Agent Explorer",
    "heading": "Agent Explorer",
    "subtitle": "Every skill, agent persona and workflow in this repo — what it is, when it "
                "runs, and what it touches.",
    "schedule_hint": "One 24-hour day. Continuous and interval jobs span the full bar. "
                     "Click a name for detail.",
    "output": "docs/agents-explorer.html",
    "skill_surface": "Agent Skills",
    "persona_surface": "Subagent",
    "persona_invoke": "{path}",
    "persona_file_note": "the persona — frontmatter is name + description only",
    "connector_label": "connector",
    "tool_labels": [],
    "icon_rules": [],
    "acronyms": {},
}


class Explorer:
    """One build: a repo layout plus an (optional) notes file."""

    def __init__(self, root: pathlib.Path, notes: dict | None = None, *,
                 skills: str = "skills", agents: str = "agents",
                 workflows: str = ".github/workflows",
                 template: pathlib.Path = DEFAULT_TEMPLATE):
        self.root = root.resolve()
        self.notes = notes or {}
        self.cfg = {**DEFAULT_CONFIG, **self.notes.get("config", {})}
        self.skills_dir = self.root / skills
        self.agents_dir = self.root / agents
        self.workflows_dir = self.root / workflows
        self.template = template
        self.icon_rules = [tuple(r) for r in self.cfg["icon_rules"]] + ICON_RULES
        self.acronyms = {**ACRONYMS, **self.cfg["acronyms"]}

    # ---- helpers ---------------------------------------------------------------------
    def rel(self, path: pathlib.Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    def git(self, *args: str) -> str:
        try:
            return subprocess.run(("git", *args), cwd=self.root, capture_output=True, text=True,
                                  check=False, timeout=60).stdout.strip()
        except (OSError, subprocess.SubprocessError):   # no git, or not a repo: no stats
            return ""

    def frontmatter(self, path: pathlib.Path) -> dict:
        """Parse the YAML frontmatter block. Tolerates folded (>) descriptions."""
        return frontmatter(path, self.root)

    def pick_icon(self, kind: str, name: str, desc: str = "") -> str:
        for hay in (name.lower(), desc.lower()):   # name wins over description
            if not hay:
                continue
            for pattern, icon in self.icon_rules:
                if re.search(pattern, hay):
                    return icon
        return DEFAULT_ICON.get(kind, "🤖")

    def titleize(self, slug: str) -> str:
        return titleize(slug, self.acronyms)

    def history(self, rel: str) -> tuple[int, str | None]:
        """(revisions, last date with real content change).

        Pure renames show 0 added / 0 deleted in --numstat, so a file that was only MOVED
        does not get stamped with the move's date.
        """
        out = self.git("log", "--follow", "--numstat", "--format=@%h %ad", "--date=short", "--", rel)
        revisions, last, cur_date, touched = 0, None, None, False
        for line in out.splitlines() + ["@"]:
            if line.startswith("@"):
                if cur_date is not None:
                    revisions += 1
                    if touched and last is None:
                        last = cur_date
                parts = line[1:].split()
                cur_date = parts[1] if len(parts) > 1 else None
                touched = False
            elif line.strip():
                add, dele = (line.split("\t") + ["", ""])[:2]
                if add not in ("0", "-") or dele not in ("0", "-"):
                    touched = True
        return revisions, last

    def measure(self, path: pathlib.Path, folder: pathlib.Path | None = None) -> dict:
        text = path.read_text(encoding="utf-8", errors="replace")
        files = 1
        if folder is not None:
            tracked = self.git("ls-files", self.rel(folder))
            if tracked:
                files = len(tracked.splitlines())
            else:
                files = sum(1 for p in folder.rglob("*")
                            if p.is_file() and "__pycache__" not in p.parts)
        revisions, modified = self.history(self.rel(path))
        return {
            "lines": text.count("\n") + 1,
            "words": len(text.split()),
            "files": files,
            "commits": revisions or None,
            "modified": modified,
        }

    def listing(self, folder: pathlib.Path, limit: int = 6) -> list[dict]:
        rel = self.rel(folder)
        out = [{"p": f"{rel}/SKILL.md", "d": "the skill"}]
        for sub in sorted(p for p in folder.iterdir() if p.is_dir() and p.name != "__pycache__"):
            n = sum(1 for p in sub.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
            out.append({"p": f"{rel}/{sub.name}/", "d": f"{n} file{'s' if n != 1 else ''}"})
        return out[:limit]

    def short_tool(self, t: str) -> str:
        """A connector-style tool name (server__tool) → a readable connector label."""
        if "__" not in t:
            return t
        tail = t.split("__")[-1].lower()
        for hay in (tail, t.lower()):
            for pattern, label in self.cfg["tool_labels"]:
                if re.search(pattern, hay):
                    return label
        return self.cfg["connector_label"]

    # ---- collectors ------------------------------------------------------------------
    def collect_skills(self, ann: dict) -> list[dict]:
        if not self.skills_dir.is_dir():
            return []
        rows = []
        for folder in sorted(self.skills_dir.iterdir()):
            skill = folder / "SKILL.md"
            if not skill.is_file():
                continue
            fm = self.frontmatter(skill)
            name = str(fm.get("name") or folder.name)
            desc = " ".join(str(fm.get("description") or "").split())
            a = ann.get(folder.name, {})
            tools = [t.strip() for t in str(fm.get("allowed-tools") or "").split(",") if t.strip()]
            rows.append({
                "id": folder.name,
                "name": a.get("name") or self.titleize(name),
                "icon": a.get("icon") or self.pick_icon("Skill", name, desc),
                "kind": "Skill",
                "status": a.get("status", "Active"),
                "surface": self.cfg["skill_surface"],
                "invoke": f"/{name}  ·  {self.rel(skill)}",
                "trigger": a.get("trigger") or (
                    "On demand" + ("" if fm.get("user-invocable") else " (model-invoked)")),
                "desc": desc or "No description in frontmatter.",
                "does": a.get("does", []),
                "tools": a.get("tools") or [self.short_tool(t) for t in tools] or ["Read", "Bash"],
                "files": a.get("files") or self.listing(folder),
                "metrics": self.measure(skill, folder),
                "tags": a.get("tags", []) + ([] if fm.get("user-invocable") else ["model-invoked"]),
                "note": a.get("note", ""),
                "related": a.get("related", []),
            })
        return rows

    def collect_personas(self, ann: dict) -> list[dict]:
        if not self.agents_dir.is_dir():
            return []
        rows = []
        for path in sorted(self.agents_dir.glob("*.md")):
            fm = self.frontmatter(path)
            name = str(fm.get("name") or path.stem)
            desc = " ".join(str(fm.get("description") or "").split())
            a = ann.get(f"agent:{path.stem}", {})
            rel = self.rel(path)
            rows.append({
                "id": f"agent-{path.stem}",
                "name": a.get("name") or self.titleize(name),
                "icon": a.get("icon") or self.pick_icon("Agent persona", name, desc),
                "kind": "Agent persona",
                "status": "Active",
                "surface": self.cfg["persona_surface"],
                "invoke": self.cfg["persona_invoke"].replace("{path}", rel),
                "trigger": a.get("trigger", "Delegated by a skill, or invoked inline"),
                "desc": desc or "No description in frontmatter.",
                "does": a.get("does", []),
                "tools": a.get("tools", ["All tools"]),
                "files": [{"p": rel, "d": self.cfg["persona_file_note"]}],
                "metrics": self.measure(path),
                "tags": a.get("tags", []) + ["persona"],
                "note": a.get("note", ""),
                "related": a.get("related", []),
            })
        return rows

    def collect_workflows(self, ann: dict) -> list[dict]:
        if not self.workflows_dir.is_dir():
            return []
        rows = []
        for path in sorted(self.workflows_dir.glob("*.y*ml")):
            text = path.read_text(encoding="utf-8")
            m = re.search(r"^name:\s*(.+)$", text, re.M)
            name = m.group(1).strip() if m else path.stem
            a = ann.get(f"wf:{path.name}", {})
            # an active schedule is an uncommented `- cron:` line
            active_cron = [c.group(1) for c in re.finditer(r"^\s*-\s*cron:\s*['\"]([^'\"]+)", text, re.M)]
            disabled = bool(re.search(r"#\s*-\s*cron:", text)) and not active_cron
            triggers = []
            if active_cron:
                triggers.append("cron")
            if "workflow_dispatch" in text:
                triggers.append("workflow_dispatch")
            for ev in ("push", "pull_request"):
                if re.search(rf"^\s*{ev}:", text, re.M):
                    triggers.append(ev)
            rel = self.rel(path)
            rows.append({
                "id": f"wf-{path.stem}",
                "name": a.get("name") or name,
                "icon": a.get("icon") or self.pick_icon("Scheduled workflow", path.stem, name),
                "kind": "Scheduled workflow",
                "status": a.get("status") or ("Paused" if disabled else "Active"),
                "surface": "GitHub Actions",
                "invoke": rel,
                "trigger": a.get("trigger") or (
                    "cron DISABLED (commented out); " if disabled else "") + ", ".join(triggers or ["manual"]),
                "desc": a.get("desc") or _wf_desc(text, name),
                "does": a.get("does", []),
                "tools": a.get("tools", []),
                "files": [{"p": rel, "d": f"{text.count(chr(10)) + 1} lines"}],
                "metrics": self.measure(path),
                "tags": a.get("tags", []) + (["paused"] if disabled else []),
                "note": a.get("note", ""),
                "related": a.get("related", []),
                **({"sched": a["sched"]} if "sched" in a else {}),
            })
        return rows

    # ---- output ----------------------------------------------------------------------
    def build(self) -> str:
        ann = self.notes.get("annotations", {})
        agents = self.collect_skills(ann) + self.collect_personas(ann) + self.collect_workflows(ann)
        agents += self.notes.get("entries", [])  # host jobs, runtime, governance — not derivable
        cfg = self.cfg
        return (self.template.read_text(encoding="utf-8")
                .replace("__TITLE__", cfg["title"])
                .replace("__HEADING__", cfg["heading"])
                .replace("__SUBTITLE__", cfg["subtitle"])
                .replace("__SCHED_HINT__", cfg["schedule_hint"])
                .replace("__AGENTS_JSON__", json.dumps(agents, ensure_ascii=False, indent=1))
                .replace("__FLOWS_JSON__", json.dumps(self.notes.get("flows", []), ensure_ascii=False, indent=1)))

    def public(self, rendered: str) -> str:
        """The publish-safe variant: page skeleton stripped, identifiers rewritten.

        Every scrub rule must actually match, so rewording an annotation can never silently
        re-expose a value — the failure is loud and the publish stops.
        """
        scrub = self.notes.get("public_scrub", {})
        out = rendered.replace(f"<title>{self.cfg['title']}</title>",
                               f"<title>{scrub.get('title', 'Agent Explorer')}</title>")
        for rule in scrub.get("rules", []):
            if rule["find"] not in out:
                raise SystemExit(
                    f"scrub rule no longer matches — the annotation was reworded:\n  {rule['find'][:90]}…\n"
                    "Update public_scrub in the notes file before publishing.")
            out = out.replace(rule["find"], rule["replace"])
        # an artifact host supplies <!doctype>/<html>/<head>/<body>
        title = re.search(r"<title>.*?</title>", out, re.S).group(0)
        style = re.search(r"<style>.*?</style>", out, re.S).group(0)
        body = re.search(r"<body>(.*)</body>", out, re.S).group(1).strip()
        out = f"{title}\n{style}\n{body}\n"
        for pattern in scrub.get("forbid", []):
            hit = re.search(pattern, out)
            if hit:
                raise SystemExit(f"publish blocked — {pattern!r} matched {hit.group(0)!r}")
        return out


def frontmatter(path: pathlib.Path, root: pathlib.Path | None = None) -> dict:
    """Parse a file's YAML frontmatter block; {} when absent, malformed or not a mapping."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    import yaml  # hard dependency: silently blanking every description is worse

    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:  # one malformed block must not break the build
        shown = path.relative_to(root) if root and path.is_relative_to(root) else path
        print(f"warning    {shown}: unparsable frontmatter ({exc.__class__.__name__})", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def titleize(slug: str, acronyms: dict | None = None) -> str:
    acronyms = ACRONYMS if acronyms is None else acronyms
    words = [w.capitalize() for w in slug.replace("-", " ").split()]
    return " ".join(acronyms.get(w, w) for w in words)


def _wf_desc(text: str, name: str) -> str:
    """First paragraph of the leading comment block, if the workflow has one."""
    lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            if not body:
                break
            lines.append(body)
        elif lines or line.strip():
            break
    return " ".join(lines[1:]) or f"The {name} workflow."


# `commits` and `modified` come from git log, so they change the moment a commit lands —
# including the very commit that rebuilds the page. A rename is worse: the new path has no
# history until it is committed, so build writes null and the next read sees a real count.
# Comparing them would make `check` fail on exactly the commits that did the right thing, so
# the check compares everything else: a skill added, removed, renamed or re-described still
# fails it.
VOLATILE = re.compile(r'"(commits|modified)": (?:"[^"]*"|null|\d+)')


def signature(html: str) -> str:
    return VOLATILE.sub(r'"\1": *', html)


def load_notes(path: pathlib.Path | None) -> dict:
    if path is None:
        return {}
    if not path.is_file():
        raise SystemExit(f"notes file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "check", "public"))
    ap.add_argument("dest", nargs="?", help="public: where to write the scrubbed page")
    ap.add_argument("--root", type=pathlib.Path, help="repo to catalog (default: this script's repo)")
    ap.add_argument("--skills", default="skills", help="skills folder, relative to --root")
    ap.add_argument("--agents", default="agents", help="personas folder, relative to --root")
    ap.add_argument("--workflows", default=".github/workflows", help="workflows folder, relative to --root")
    ap.add_argument("--notes", type=pathlib.Path, help="notes JSON (default: beside this script, if present)")
    ap.add_argument("--no-notes", action="store_true", help="ignore any notes file")
    ap.add_argument("--template", type=pathlib.Path, default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", type=pathlib.Path, help="page to write/check (default: config.output)")
    a = ap.parse_args(argv)

    root = (a.root or DEFAULT_ROOT).resolve()
    notes_path = a.notes
    if notes_path is None and not a.no_notes and root == DEFAULT_ROOT.resolve() and DEFAULT_NOTES.is_file():
        notes_path = DEFAULT_NOTES
    ex = Explorer(root, None if a.no_notes else load_notes(notes_path),
                  skills=a.skills, agents=a.agents, workflows=a.workflows, template=a.template)
    out = a.out if a.out is not None else root / ex.cfg["output"]
    out = out if out.is_absolute() else (pathlib.Path.cwd() / out)
    shown = ex.rel(out)
    rendered = ex.build()

    if a.cmd == "build":
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        print(f"built      {shown} — {rendered.count(chr(34) + 'kind' + chr(34) + ':')} agents")
        return 0
    if a.cmd == "public":
        dest = pathlib.Path(a.dest or "/tmp/agents-explorer.public.html")
        dest.write_text(ex.public(rendered), encoding="utf-8")
        print(f"public     {dest} — scrubbed and skeleton-free")
        return 0
    current = out.read_text(encoding="utf-8") if out.is_file() else ""
    if signature(current) == signature(rendered):
        note = " (git stats will refresh on the next build)" if current != rendered else ""
        print(f"ok         {shown} lists every agent{note}")
        return 0
    args = sys.argv[1:] if argv is None else list(argv)
    rebuild = " ".join(["python3", sys.argv[0] if argv is None else "agents_explorer.py",
                        *["build" if x == "check" else x for x in args]])
    print(f"STALE      {shown} is out of date (run: {rebuild})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
