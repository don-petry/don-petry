"""Tests for the generic paths of agents_explorer.py (works on any repo of Agent Skills).

Runs from self-private (module in scripts/) and from the public repo (module beside this file).
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
for _p in (HERE.parent / "scripts", HERE):   # self-private: scripts/; public repo: tools/
    if (_p / "agents_explorer.py").is_file():
        sys.path.insert(0, str(_p))
        break

import agents_explorer as ae  # noqa: E402


def write(root: pathlib.Path, rel: str, text: str) -> pathlib.Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def agents_json(html: str) -> list[dict]:
    start = html.index("const AGENTS = ") + len("const AGENTS = ")
    end = html.index(";\n", start)
    return json.loads(html[start:end])


def run(*argv: str) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ae.main(list(argv))
    return code, out.getvalue() + err.getvalue()


class ExplorerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        write(self.root, "skills/demo-skill/SKILL.md",
              "---\nname: demo-skill\ndescription: >\n  Does a demo\n  thing.\n---\nBody\n")
        write(self.root, "skills/demo-skill/references/more.md", "detail\n")
        write(self.root, "agents/red-team.md",
              "---\nname: red-team\ndescription: Reads a draft from the other side.\n---\nBody\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_builds_with_no_notes_file(self):
        html = ae.Explorer(self.root).build()
        rows = {r["id"]: r for r in agents_json(html)}
        self.assertEqual(set(rows), {"demo-skill", "agent-red-team"})
        self.assertEqual(rows["demo-skill"]["desc"], "Does a demo thing.")
        self.assertEqual(rows["demo-skill"]["name"], "Demo Skill")
        self.assertEqual(rows["demo-skill"]["surface"], "Agent Skills")
        self.assertEqual(rows["agent-red-team"]["invoke"], "agents/red-team.md")
        self.assertEqual(rows["agent-red-team"]["icon"], "🥊")
        self.assertIn("<title>Agent Explorer</title>", html)
        for placeholder in ("__TITLE__", "__HEADING__", "__SUBTITLE__", "__SCHED_HINT__",
                            "__AGENTS_JSON__", "__FLOWS_JSON__"):
            self.assertNotIn(placeholder, html)
        self.assertIn("const FLOWS = []", html)

    def test_missing_frontmatter_keys_fall_back(self):
        write(self.root, "skills/no-fm/SKILL.md", "Just a body, no frontmatter.\n")
        write(self.root, "skills/name-only/SKILL.md", "---\nname: name-only\n---\nBody\n")
        write(self.root, "skills/not-a-map/SKILL.md", "---\n- a\n- list\n---\nBody\n")
        write(self.root, "agents/bare.md", "---\ndescription: no name key\n---\n")
        rows = {r["id"]: r for r in agents_json(ae.Explorer(self.root).build())}
        for sid in ("no-fm", "name-only", "not-a-map"):
            self.assertEqual(rows[sid]["desc"], "No description in frontmatter.")
            self.assertIn(f"/{sid}  ·  skills/{sid}/SKILL.md", rows[sid]["invoke"])
        self.assertEqual(rows["agent-bare"]["name"], "Bare")
        self.assertEqual(rows["agent-bare"]["desc"], "no name key")

    def test_missing_folders_are_skipped(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.assertEqual(agents_json(ae.Explorer(empty).build()), [])

    def test_custom_layout(self):
        write(self.root, "catalog/x/SKILL.md", "---\nname: x\ndescription: X.\n---\n")
        rows = agents_json(ae.Explorer(self.root, skills="catalog", agents="nope").build())
        self.assertEqual([r["id"] for r in rows], ["x"])
        self.assertEqual(rows[0]["invoke"], "/x  ·  catalog/x/SKILL.md")

    def test_notes_config_and_annotations(self):
        write(self.root, "skills/demo-skill/SKILL.md",
              "---\nname: demo-skill\ndescription: Demo.\nallowed-tools: Read, srv__list_events, srv__zap\n---\n")
        notes = {
            "config": {"title": "My Agents", "subtitle": "Mine.", "skill_surface": "Codex",
                       "icon_rules": [["demo", "🎯"]], "tool_labels": [["event", "Calendar"]],
                       "acronyms": {"Demo": "DEMO"}},
            "annotations": {"agent:red-team": {"note": "Use before sending."}},
            "flows": [{"title": "F", "rows": []}],
        }
        html = ae.Explorer(self.root, notes).build()
        rows = {r["id"]: r for r in agents_json(html)}
        self.assertIn("<title>My Agents</title>", html)
        self.assertEqual(rows["demo-skill"]["icon"], "🎯")
        self.assertEqual(rows["demo-skill"]["name"], "DEMO Skill")
        self.assertEqual(rows["demo-skill"]["surface"], "Codex")
        self.assertEqual(rows["demo-skill"]["tools"], ["Read", "Calendar", "connector"])
        self.assertEqual(rows["agent-red-team"]["note"], "Use before sending.")
        self.assertIn('"title": "F"', html)

    def test_check_detects_staleness(self):
        out = self.root / "docs/agents-explorer.html"
        code, msg = run("build", "--root", str(self.root), "--no-notes")
        self.assertEqual(code, 0, msg)
        self.assertTrue(out.is_file())
        self.assertEqual(run("check", "--root", str(self.root), "--no-notes")[0], 0)
        # git stats alone never make the page stale
        out.write_text(out.read_text(encoding="utf-8").replace('"commits": null', '"commits": 7'),
                       encoding="utf-8")
        self.assertEqual(run("check", "--root", str(self.root), "--no-notes")[0], 0)
        # a new skill does
        write(self.root, "skills/new-one/SKILL.md", "---\nname: new-one\ndescription: New.\n---\n")
        code, msg = run("check", "--root", str(self.root), "--no-notes")
        self.assertEqual(code, 1)
        self.assertIn("STALE", msg)
        self.assertIn("build", msg)
        # and so does a re-described one
        run("build", "--root", str(self.root), "--no-notes")
        write(self.root, "agents/red-team.md", "---\nname: red-team\ndescription: Changed.\n---\n")
        self.assertEqual(run("check", "--root", str(self.root), "--no-notes")[0], 1)

    def test_check_fails_when_page_missing(self):
        self.assertEqual(run("check", "--root", str(self.root), "--no-notes")[0], 1)

    def test_out_and_notes_arguments(self):
        notes = write(self.root, "n.json", json.dumps({"config": {"output": "site/a.html"}}))
        self.assertEqual(run("build", "--root", str(self.root), "--notes", str(notes))[0], 0)
        self.assertTrue((self.root / "site/a.html").is_file())
        target = self.root / "elsewhere.html"
        self.assertEqual(run("build", "--root", str(self.root), "--no-notes", "--out", str(target))[0], 0)
        self.assertTrue(target.is_file())

    def test_foreign_root_ignores_default_notes(self):
        # The notes beside the script describe the script's own repo, never another one.
        html = ae.Explorer(self.root).build()
        code, _ = run("build", "--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual((self.root / "docs/agents-explorer.html").read_text(encoding="utf-8"), html)

    def test_public_scrub_is_loud(self):
        ex = ae.Explorer(self.root, {"public_scrub": {"rules": [{"find": "Does a demo", "replace": "Demos"}]}})
        page = ex.public(ex.build())
        self.assertNotIn("<html", page)
        self.assertIn("Demos thing.", page)
        stale = ae.Explorer(self.root, {"public_scrub": {"rules": [{"find": "not there", "replace": ""}]}})
        with self.assertRaises(SystemExit):
            stale.public(stale.build())
        forbid = ae.Explorer(self.root, {"public_scrub": {"forbid": ["demo thing"]}})
        with self.assertRaises(SystemExit):
            forbid.public(forbid.build())

    def test_titleize_and_frontmatter(self):
        self.assertEqual(ae.titleize("ha-health-check"), "HA Health Check")
        self.assertEqual(ae.titleize("pdf-tool", {}), "Pdf Tool")
        p = write(self.root, "bad.md", "---\nname: [unclosed\n---\n")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ae.frontmatter(p), {})


if __name__ == "__main__":
    unittest.main()
