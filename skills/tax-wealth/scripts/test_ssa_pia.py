"""Tests for ssa_pia.py — run from the skill folder: ~/.venvs/tax-wealth/bin/python -m unittest scripts/test_ssa_pia.py

Needs PolicyEngine-US (T-POLICYENGINE) for the wage index and skips without it. Uses the household's
statement and retirement case when config/household.yaml sets engines.ssa_statement and
engines.retirement_case, else the fictional examples/ (whose figures are regression fixtures).
"""

import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_retirement import data_path  # noqa: E402

HAVE_PE = importlib.util.find_spec("policyengine_us") is not None
STATEMENT = data_path("ssa_statement", "ssa-statement.example.json")
CASE = data_path("retirement_case", "retirement-case.example.json")


@unittest.skipUnless(HAVE_PE, "policyengine-us not installed (T-POLICYENGINE)")
class StatementReproduction(unittest.TestCase):
    def test_statement_pia_reproduces_and_case_matches(self):
        import contextlib
        import io
        import ssa_pia
        with open(CASE, encoding="utf-8") as f:
            case = json.load(f)
        person = next(pid for pid, v in case["social_security"].items()
                      if isinstance(v, dict) and v.get("pia_by_last_work_year"))
        case_pias = case["social_security"][person]["pia_by_last_work_year"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ssa_pia.main([STATEMENT, "--last-work-years", *sorted(case_pias)])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["reproduced_pia"], out["statement_pia"])
        self.assertEqual({k: v["pia_monthly"] for k, v in out["by_last_work_year"].items()}, case_pias)


if __name__ == "__main__":
    unittest.main()
