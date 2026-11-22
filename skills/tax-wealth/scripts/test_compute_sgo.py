"""Tests for the SGO-credit extension of compute.py.

Run: python3 -m unittest scripts/test_compute_sgo.py
The engine tests need the tax-wealth venv (T-POLICYENGINE) and skip without it.
Dollar amounts are test fixtures, not household figures.
"""

import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import compute  # noqa: E402

HAVE_ENGINE = importlib.util.find_spec("policyengine_us") is not None


def household(cases, year=2026):
    return {"tax_year": year, "state": "AL", "label": "test",
            "adults": [{"id": "a", "age": 45}, {"id": "b", "age": 45}],
            "dependents": [], "cases": cases}


BASE = {"a.wages": 300000, "b.wages": 100000, "a.real_estate_taxes": 5000,
        "a.mortgage_interest": 20000, "a.charitable_cash": 20000, "tu.state_income_tax_paid": 18000}


class PureRules(unittest.TestCase):
    def test_al_credit_limited_by_tax_and_cap(self):
        self.assertEqual(compute.al_sgo_credit(5000, 12000), 5000)
        self.assertEqual(compute.al_sgo_credit(15000, 12000), 12000)
        self.assertEqual(compute.al_sgo_credit(500000, 300000), compute.AL_AAA_CAP)
        self.assertEqual(compute.al_sgo_credit(5000, -10), 0)

    def test_f25f_credit_limited_by_cap_and_tax(self):
        self.assertEqual(compute.f25f_credit(3000, 1700, 50000), 1700)
        self.assertEqual(compute.f25f_credit(3000, 3400, 50000), 3000)
        self.assertEqual(compute.f25f_credit(3000, 1700, 900), 900)

    def test_delta_derive(self):
        res = {"a": {"x": 10.0, "y": 5.0}, "b": {"x": 4.0, "y": 1.0}}
        got = compute.derive(res, [{"name": "d", "type": "delta", "case": "a", "base": "b", "vars": ["x", "y"]}])
        self.assertEqual(got, {"d": 10.0})

    def test_unknown_sgo_key_refused(self):
        with self.assertRaises(ValueError):
            compute.split_case({"a.wages": 1, "sgo.typo": 1})

    def test_unknown_tax_unit_field_refused(self):
        with self.assertRaises(ValueError):
            compute.situation(household({}), {"tu.nope": 1})


@unittest.skipUnless(HAVE_ENGINE, "policyengine-us not installed (T-POLICYENGINE)")
class EngineSGO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gift = 5000
        cls.gift = gift
        cases = {
            "base": dict(BASE),
            "direct": dict(BASE, **{"sgo.al_gift": gift, "sgo.federal": "safe_harbor"}),
            "daf": dict(BASE, **{"sgo.al_gift": gift, "sgo.federal": "charitable"}),
            "daf_al_deducted": dict(BASE, **{"sgo.al_gift": gift, "sgo.federal": "charitable",
                                             "sgo.al_deducted": True}),
            "none": dict(BASE, **{"sgo.al_gift": gift, "sgo.federal": "none"}),
            "huge": dict(BASE, **{"sgo.al_gift": 1000000, "sgo.federal": "none"}),
        }
        cls.out = compute.run(household(cases))["outputs"]

    def test_base_case_reports_itemized_outputs(self):
        self.assertIn("charitable_deduction", self.out["base"])
        self.assertNotIn("al_sgo_credit", self.out["base"])

    def test_direct_gift_credit_and_safe_harbor(self):
        d, b = self.out["direct"], self.out["base"]
        self.assertEqual(d["al_sgo_credit"], self.gift)
        self.assertEqual(d["sgo_safe_harbor_salt_added"], self.gift)
        self.assertEqual(d["charitable_deduction"], b["charitable_deduction"])
        self.assertEqual(d["al_income_tax_after_sgo_credit"], round(d["al_income_tax"] - self.gift, 2))

    def test_daf_route_deducts_federally_but_not_in_alabama(self):
        d, b = self.out["daf"], self.out["base"]
        self.assertEqual(d["charitable_deduction"], b["charitable_deduction"] + self.gift)
        self.assertEqual(d["al_itemized_deductions"], b["al_itemized_deductions"])
        self.assertEqual(d["al_sgo_credit"], self.gift)

    def test_al_deducted_reproduces_the_double_deduction(self):
        self.assertEqual(self.out["daf_al_deducted"]["al_itemized_deductions"],
                         self.out["base"]["al_itemized_deductions"] + self.gift)

    def test_none_neither_deducts_nor_adds_salt(self):
        n, b = self.out["none"], self.out["base"]
        self.assertEqual(n["charitable_deduction"], b["charitable_deduction"])
        self.assertEqual(n["sgo_safe_harbor_salt_added"], 0.0)
        self.assertEqual(n["income_tax"], b["income_tax"])

    def test_credit_never_exceeds_alabama_tax(self):
        h = self.out["huge"]
        self.assertEqual(h["al_sgo_credit"], h["al_income_tax_before_non_refundable_credits"])
        self.assertGreater(h["al_sgo_credit_unused"], 0)
        self.assertEqual(h["al_income_tax_after_sgo_credit"], round(h["al_income_tax"] - h["al_sgo_credit"], 2))

    def test_safe_harbor_needs_state_tax_paid(self):
        case = {k: v for k, v in BASE.items() if not k.startswith("tu.")}
        case.update({"sgo.al_gift": 1000, "sgo.federal": "safe_harbor"})
        with self.assertRaises(ValueError):
            compute.run(household({"x": case}))

    def test_f25f_before_2027_refused(self):
        with self.assertRaises(ValueError):
            compute.run(household({"x": dict(BASE, **{"sgo.f25f_gift": 1700})}))

    def test_f25f_capped(self):
        out = compute.run(household({"x": dict(BASE, **{"sgo.f25f_gift": 3000})}, year=2027))["outputs"]["x"]
        self.assertEqual(out["f25f_credit"], compute.F25F_CAP)
        self.assertEqual(out["income_tax_after_f25f"], round(out["income_tax"] - compute.F25F_CAP, 2))
        self.assertEqual(out["charitable_deduction"],
                         compute.run(household({"y": dict(BASE)}, year=2027))["outputs"]["y"]["charitable_deduction"])


if __name__ == "__main__":
    unittest.main()
