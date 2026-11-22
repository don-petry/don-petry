#!/usr/bin/env python3
"""Tests for onboarding_coverage.py.

Run: python3 -m unittest discover -s skills/household-onboarding/scripts
"""
from __future__ import annotations

import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import onboarding_coverage as cov  # noqa: E402

EXAMPLE = HERE.parent / "examples" / "coverage.example.yaml"


def area(**kw):
    a = {"area": "A1", "name": "People",
         "past": {"status": "known", "verified": None},
         "current": {"status": "partial", "verified": None},
         "future": {"status": "gap", "verified": None}}
    a.update(kw)
    return a


class TestValidate(unittest.TestCase):
    def test_example_file_is_valid(self):
        doc = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(cov.validate(doc), [])

    def test_bad_status(self):
        errs = cov.validate({"areas": [area(future={"status": "done"})]})
        self.assertTrue(any("future.status" in e for e in errs))

    def test_missing_section(self):
        a = area()
        del a["current"]
        self.assertTrue(any("`current`" in e for e in cov.validate({"areas": [a]})))

    def test_bad_area_id_and_duplicate(self):
        errs = cov.validate({"areas": [area(area="X1"), area(), area()]})
        self.assertTrue(any("A1…A14" in e for e in errs))
        self.assertTrue(any("duplicate" in e for e in errs))

    def test_bad_date_and_list(self):
        errs = cov.validate({"areas": [area(next_review="soon", open_questions="Q-HF1")]})
        self.assertTrue(any("next_review" in e for e in errs))
        self.assertTrue(any("open_questions" in e for e in errs))

    def test_top_level(self):
        self.assertTrue(cov.validate([]))
        self.assertTrue(cov.validate({"areas": "A1"}))


class TestReport(unittest.TestCase):
    def test_overdue_and_done(self):
        doc = {"areas": [
            area(next_review=dt.date(2026, 1, 1)),
            area(area="A2", past={"status": "known"}, current={"status": "known"}, future={"status": "known"},
                 next_review="2027-01-01"),
        ]}
        lines = cov.report(doc, dt.date(2026, 6, 1))
        self.assertIn("OVERDUE", lines[0])
        self.assertNotIn("OVERDUE", lines[1])
        self.assertIn("done", lines[1])
        self.assertEqual(lines[-1], "2 areas · 4 of 6 sections known")

    def test_counts(self):
        line = cov.report({"areas": [area(open_questions=["a", "b"], documents_missing=["d"])]},
                          dt.date(2026, 1, 1))[0]
        self.assertIn("open  2", line)
        self.assertIn("docs  1", line)


class TestMain(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cov.main([str(a) for a in args])
        return rc, out.getvalue(), err.getvalue()

    def test_example_report(self):
        rc, out, _ = self.run_main(EXAMPLE, "--today", "2026-05-01")
        self.assertEqual(rc, 0)
        self.assertIn("A11", out)
        self.assertIn("OVERDUE", out)

    def test_invalid_file_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "c.yaml")
            Path(p).write_text("areas:\n  - area: A1\n", encoding="utf-8")
            rc, out, err = self.run_main(p, "--check")
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
