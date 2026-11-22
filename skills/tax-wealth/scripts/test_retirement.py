"""Tests for retirement.py — run from the skill folder: ~/.venvs/owl/bin/python -m unittest scripts/test_retirement.py

Needs the Owl venv (T-OWL) and skips without it. Uses the household's retirement case when
config/household.yaml sets engines.retirement_case, else the fictional examples/retirement-case.example.json.
"""

import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import retirement as rt  # noqa: E402

HAVE_OWL = importlib.util.find_spec("owlplanner") is not None
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_path(key, example):
    """A household input named in config engines.<key> (repo-relative), else the fictional example."""
    cfg = os.path.join(SKILL, "config", "household.yaml")
    if os.path.exists(cfg):
        try:
            import yaml
            with open(cfg, encoding="utf-8") as f:
                rel = ((yaml.safe_load(f) or {}).get("engines") or {}).get(key)
            path = os.path.join(SKILL, "..", "..", rel) if rel else None
            if path and os.path.exists(path):
                return path
        except ImportError:
            pass
    return os.path.join(SKILL, "examples", example)


CASE = data_path("retirement_case", "retirement-case.example.json")


def load_case():
    with open(CASE, encoding="utf-8") as f:
        return json.load(f)


@unittest.skipUnless(HAVE_OWL, "owlplanner not installed (T-OWL)")
class Tables(unittest.TestCase):
    def setUp(self):
        self.case = load_case()
        self.a, self.b = self.case["people"][0], self.case["people"][1]
        self.start = int(self.case["start_date"][:4])

    def test_wages_stop_after_last_work_year(self):
        s = self.start
        t = rt.hfp_tables(self.case, {self.a["id"]: s + 3, self.b["id"]: s + 1})
        a = t[self.a["name"]].set_index("year")
        b = t[self.b["name"]].set_index("year")
        self.assertGreater(a.loc[s + 3, "anticipated wages"], 0)
        self.assertEqual(a.loc[s + 4, "anticipated wages"], 0)
        self.assertEqual(b.loc[s + 2, "anticipated wages"], 0)
        self.assertEqual(b.loc[s + 2, "401k ctrb"], 0)

    def test_first_year_uses_remaining_contributions(self):
        s = self.start
        a = rt.hfp_tables(self.case, {self.a["id"]: s + 4, self.b["id"]: s + 4})[self.a["name"]].set_index("year")
        remaining = self.case["wages"][self.a["id"]]["contrib_%d_remaining" % s]
        self.assertEqual(a.loc[s, "Roth 401k ctrb"], remaining["roth_401k_ctrb"])

    def test_health_care_runs_from_retirement_to_medicare_age(self):
        s = self.start
        medicare = self.case["events"]["health_care_pre_medicare"]["medicare_age"]
        b = rt.hfp_tables(self.case, {self.a["id"]: s, self.b["id"]: s})[self.b["name"]].set_index("year")
        turns_medicare = int(self.b["born"][:4]) + medicare
        self.assertLess(b.loc[turns_medicare - 1, "big-ticket items"], 0)   # the year before Medicare age
        self.assertEqual(b.loc[turns_medicare, "big-ticket items"], 0)     # Medicare age

    def test_pia_round_trips_through_owl_factor(self):
        from owlplanner import socialsecurity as ss
        pia = rt.pia_from_benefit("1980-01-15", 50000.0, 70.0)
        fra = ss.getFRAs([1980], [1], [15])[0]
        self.assertAlmostEqual(pia * ss.getSelfFactor(fra, 70.0, False) * 12, 50000.0, places=6)


if __name__ == "__main__":
    unittest.main()
