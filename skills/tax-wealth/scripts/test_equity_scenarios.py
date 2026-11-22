"""Tests for equity_scenarios.py — run: python3 -m unittest scripts/test_equity_scenarios.py

Rates below are test fixtures, not tax law. Real runs take every rate from an engine run or a
rules-<year>.md entry.
"""

import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import compute  # noqa: E402
import equity_scenarios as es  # noqa: E402
import runstamp  # noqa: E402


def src(v):
    return {"value": v, "source": "src:test-fixture"}


def base_inputs(**over):
    inputs = {
        "years": 4,
        "offers": [
            {"id": "A", "base": 300000, "bonus_target_pct": 0.30, "equity_pct": 0.01, "exercise_cost": 0},
            {"id": "B", "base": 250000, "bonus_target_pct": 0.25, "equity_pct": 0.03, "exercise_cost": 0},
        ],
        "exit_values": [0, 10_000_000, 50_000_000],
        "gain_treatment": "ltcg",
        "rates": {
            "ordinary_marginal": src(0.30),
            "state_ordinary": src(0.05),
            "federal_ltcg": src(0.20),
            "state_capital_gain": src(0.05),
        },
    }
    inputs.update(over)
    return inputs


class CashAndEquity(unittest.TestCase):
    def test_cash_after_tax_uses_marginal_rates(self):
        a = base_inputs()["offers"][0]
        self.assertAlmostEqual(es.cash_after_tax(a, base_inputs()), 390000 * 0.65)

    def test_engine_cash_figure_wins(self):
        inputs = base_inputs()
        inputs["offers"][0].update(after_tax_cash_per_year=250000, after_tax_cash_source="run:pe-1")
        self.assertEqual(es.cash_after_tax(inputs["offers"][0], inputs), 250000)

    def test_preference_and_dilution_reduce_common(self):
        inputs = base_inputs(preference_ahead_of_common=2_000_000, dilution_pct=0.5)
        b = inputs["offers"][1]
        # 3% * 50% of (10M - 2M) = 120,000 gain, taxed at 25%
        self.assertAlmostEqual(es.equity_after_tax(b, 10_000_000, inputs), 90000)

    def test_exercise_cost_is_basis(self):
        inputs = base_inputs()
        b = dict(inputs["offers"][1], exercise_cost=20000)
        # proceeds 300,000; gain 280,000; tax 70,000; net 300,000 - 20,000 - 70,000
        self.assertAlmostEqual(es.equity_after_tax(b, 10_000_000, inputs), 210000)

    def test_zero_exit_loses_the_exercise_cost(self):
        inputs = base_inputs()
        b = dict(inputs["offers"][1], exercise_cost=20000)
        self.assertAlmostEqual(es.equity_after_tax(b, 0, inputs), -20000)


    def test_offer_rates_override_shared_rates(self):
        inputs = base_inputs()
        b = dict(inputs["offers"][1], rates={"federal_ltcg": src(0.30)})
        # proceeds 300,000 taxed at 30% + 5% shared state rate
        self.assertAlmostEqual(es.equity_after_tax(b, 10_000_000, inputs), 300000 * 0.65)

    def test_unsourced_offer_rate_is_refused(self):
        inputs = base_inputs()
        b = dict(inputs["offers"][1], rates={"federal_ltcg": {"value": 0.3}})
        with self.assertRaises(es.InputError):
            es.equity_after_tax(b, 10_000_000, inputs)


class Qsbs(unittest.TestCase):
    def qsbs_inputs(self, conforms):
        inputs = base_inputs(gain_treatment="qsbs", state_conforms_to_qsbs=conforms)
        inputs["rates"].update(
            qsbs_excluded_fraction=src(1.0), qsbs_cap=src(15_000_000),
            qsbs_basis_multiple=src(10), qsbs_nonexcluded_rate=src(0.28),
        )
        return inputs

    def test_full_exclusion_with_conforming_state(self):
        inputs = self.qsbs_inputs(True)
        b = inputs["offers"][1]
        self.assertAlmostEqual(es.equity_after_tax(b, 10_000_000, inputs), 300000)

    def test_nonconforming_state_taxes_the_whole_gain(self):
        inputs = self.qsbs_inputs(False)
        b = inputs["offers"][1]
        self.assertAlmostEqual(es.equity_after_tax(b, 10_000_000, inputs), 300000 * 0.95)

    def test_cap_limits_exclusion(self):
        inputs = self.qsbs_inputs(True)
        big = {"id": "X", "base": 0, "equity_pct": 1.0, "exercise_cost": 0}
        # gain 20M; 15M excluded; the 5M above the cap is not §1202 gain, so it is taxed at the
        # LTCG rate (20%) plus 5% state (conforming state) — not at 28%
        self.assertAlmostEqual(es.equity_after_tax(big, 20_000_000, inputs),
                               20_000_000 - 5_000_000 * (0.20 + 0.05))

    def test_half_exclusion_above_cap(self):
        inputs = self.qsbs_inputs(True)
        inputs["rates"]["qsbs_excluded_fraction"] = src(0.5)
        big = {"id": "X", "base": 0, "equity_pct": 1.0, "exercise_cost": 0}
        # gain 20M; within cap 15M, 7.5M excluded; 7.5M at 28% + 5M above cap at 20% federal;
        # conforming state taxes the 12.5M not excluded at 5%
        federal = 7_500_000 * 0.28 + 5_000_000 * 0.20
        state = 12_500_000 * 0.05
        self.assertAlmostEqual(es.equity_after_tax(big, 20_000_000, inputs), 20_000_000 - federal - state)

    def test_state_conformity_must_be_stated(self):
        inputs = self.qsbs_inputs(True)
        del inputs["state_conforms_to_qsbs"]
        with self.assertRaises(es.InputError):
            es.equity_after_tax(inputs["offers"][1], 10_000_000, inputs)


class OrdinaryTreatment(unittest.TestCase):
    def test_gain_taxed_at_ordinary_rates(self):
        inputs = base_inputs(gain_treatment="ordinary")
        b = inputs["offers"][1]
        # proceeds 300,000 taxed at 30% ordinary + 5% state ordinary
        self.assertAlmostEqual(es.equity_after_tax(b, 10_000_000, inputs), 300000 * 0.65)

    def test_ordinary_needs_ordinary_rates(self):
        inputs = base_inputs(gain_treatment="ordinary")
        del inputs["rates"]["ordinary_marginal"]
        with self.assertRaises(es.InputError):
            es.equity_after_tax(inputs["offers"][1], 10_000_000, inputs)

    def test_unknown_treatment_is_refused(self):
        inputs = base_inputs(gain_treatment="capital")
        with self.assertRaises(es.InputError):
            es.equity_after_tax(inputs["offers"][1], 10_000_000, inputs)


class InputValidation(unittest.TestCase):
    def refused(self, inputs):
        with self.assertRaises(es.InputError):
            es.run(inputs)

    def test_equity_pct_entered_as_percent_is_refused(self):
        inputs = base_inputs()
        inputs["offers"][1]["equity_pct"] = 1.25
        self.refused(inputs)

    def test_zero_or_negative_equity_pct_is_refused(self):
        for bad in (0, -0.01):
            inputs = base_inputs()
            inputs["offers"][0]["equity_pct"] = bad
            self.refused(inputs)

    def test_negative_dilution_is_refused(self):
        self.refused(base_inputs(dilution_pct=-0.5))

    def test_full_dilution_is_refused(self):
        self.refused(base_inputs(dilution_pct=1.0))

    def test_rate_outside_unit_interval_is_refused(self):
        for bad in (1.2, -0.05, 20):
            inputs = base_inputs()
            inputs["rates"]["federal_ltcg"] = src(bad)
            self.refused(inputs)

    def test_qsbs_cap_is_not_bounded_by_one(self):
        inputs = base_inputs(gain_treatment="qsbs", state_conforms_to_qsbs=True)
        inputs["rates"].update(qsbs_excluded_fraction=src(1.0), qsbs_cap=src(15_000_000),
                               qsbs_basis_multiple=src(10), qsbs_nonexcluded_rate=src(0.28))
        es.run(inputs)

    def test_non_integer_years_is_refused(self):
        for bad in (2.9, "4", 0, True):
            self.refused(base_inputs(years=bad))

    def test_integral_float_years_is_accepted(self):
        now = datetime.datetime(2026, 9, 26, tzinfo=datetime.timezone.utc)
        self.assertEqual(es.run(base_inputs(years=4.0), now)["outputs"],
                         es.run(base_inputs(years=4), now)["outputs"])

    def test_negative_preference_is_refused(self):
        self.refused(base_inputs(preference_ahead_of_common=-1))


class Guardrails(unittest.TestCase):
    def test_unsourced_rate_is_refused(self):
        inputs = base_inputs()
        inputs["rates"]["ordinary_marginal"] = {"value": 0.37}
        with self.assertRaises(es.InputError):
            es.cash_after_tax(inputs["offers"][0], inputs)

    def test_bare_number_rate_is_refused(self):
        inputs = base_inputs()
        inputs["rates"]["federal_ltcg"] = 0.2
        with self.assertRaises(es.InputError):
            es.equity_after_tax(inputs["offers"][1], 1_000_000, inputs)


class BreakEvenAndStamp(unittest.TestCase):
    def test_break_even_matches_closed_form(self):
        inputs = base_inputs()
        a, b = inputs["offers"]
        cash_gap = (es.cash_after_tax(a, inputs) - es.cash_after_tax(b, inputs)) * 4
        closed_form = cash_gap / ((0.03 - 0.01) * 0.75)
        self.assertAlmostEqual(es.break_even(a, b, inputs), closed_form, delta=2)

    def test_no_crossing_returns_none(self):
        inputs = base_inputs()
        a = inputs["offers"][0]
        worse = dict(a, id="W", base=100000, equity_pct=0.005)
        self.assertIsNone(es.break_even(a, worse, inputs))

    def test_multiple_crossings_are_all_reported(self):
        # QSBS cap kinks: A 3% no cash vs B 2.5% with 2.4M cash. A's gain passes the 15M cap at 500M,
        # B's at 600M, so the difference crosses zero three times: 480M, 540M, 640M.
        inputs = base_inputs(gain_treatment="qsbs", state_conforms_to_qsbs=True, years=1,
                             exit_values=[0])
        inputs["rates"].update(qsbs_excluded_fraction=src(1.0), qsbs_cap=src(15_000_000),
                               qsbs_basis_multiple=src(10), qsbs_nonexcluded_rate=src(0.28))
        inputs["offers"] = [
            {"id": "A", "equity_pct": 0.03, "after_tax_cash_per_year": 0, "after_tax_cash_source": "src:t"},
            {"id": "B", "equity_pct": 0.025, "after_tax_cash_per_year": 2_400_000,
             "after_tax_cash_source": "src:t"},
        ]
        a, b = inputs["offers"]
        found = es.break_evens(a, b, inputs)
        self.assertEqual(len(found), 3)
        for got, want in zip(found, (480e6, 540e6, 640e6)):
            self.assertAlmostEqual(got, want, delta=2)
        for x in found:
            gap = es.total_after_tax(a, x, inputs) - es.total_after_tax(b, x, inputs)
            self.assertLess(abs(gap), 1.0)
        out = es.run(inputs)["outputs"]
        self.assertEqual(out["break_even_all_crossings"], {"A_vs_B": found})
        self.assertEqual(out["break_even_exit_value"]["A_vs_B"], found[0])

    def test_single_crossing_has_no_extra_output(self):
        out = es.run(base_inputs())["outputs"]
        self.assertNotIn("break_even_all_crossings", out)

    def test_run_is_stamped_and_deterministic(self):
        now = datetime.datetime(2026, 9, 26, tzinfo=datetime.timezone.utc)
        r1, r2 = es.run(base_inputs(), now), es.run(base_inputs(), now)
        self.assertEqual(r1, r2)
        self.assertEqual(r1["engine"], "equity_scenarios")
        self.assertEqual(r1["run_at"], "2026-09-26T00:00:00Z")
        self.assertIn("A_vs_B", r1["outputs"]["break_even_exit_value"])


class RunFiles(unittest.TestCase):
    def test_id_includes_engine_and_version(self):
        inputs = base_inputs()
        id1, digest = runstamp.run_id("equity_scenarios", "equity_scenarios", "0.3.0", inputs)
        id2, _ = runstamp.run_id("equity_scenarios", "equity_scenarios", "0.4.0", inputs)
        self.assertNotEqual(id1, id2)
        self.assertEqual(digest, runstamp.canonical_sha256(inputs))
        self.assertNotEqual(id1.split("-", 1)[1], digest[:10])

    def main_quiet(self, argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = es.main(argv)
        return code, err.getvalue()

    def test_rerun_is_noop_and_differing_outputs_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "inputs.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(base_inputs(), f)
            out = os.path.join(d, "runs")
            self.assertEqual(self.main_quiet([path, "--out", out])[0], 0)
            [name] = os.listdir(out)
            run_path = os.path.join(out, name)
            with open(run_path, encoding="utf-8") as f:
                first = f.read()
            # identical rerun: no-op, file (including run_at) left alone
            code, err = self.main_quiet([path, "--out", out])
            self.assertEqual(code, 0)
            self.assertIn("UNCHANGED", err)
            with open(run_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), first)
            # the cited file's outputs differ from what this engine produces now: refuse
            tampered = json.loads(first)
            tampered["outputs"]["cash_after_tax_per_year"]["A"] += 1
            with open(run_path, "w", encoding="utf-8") as f:
                json.dump(tampered, f)
            code, err = self.main_quiet([path, "--out", out])
            self.assertEqual(code, 2)
            self.assertIn("REFUSED", err)
            with open(run_path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), tampered)


class ComputeGuards(unittest.TestCase):
    """compute.py pieces that run without policyengine-us installed."""

    class FakeSim:
        def __init__(self, situation):
            pass

        def calculate(self, var, year):
            class V:
                def sum(self_inner):
                    return 100.0
            return V()

    def test_unmapped_state_is_refused(self):
        inputs = dict(compute.SMOKE, state="GA")
        with self.assertRaises(ValueError):
            compute.run_case(self.FakeSim, inputs, inputs["cases"]["smoke"])
        with self.assertRaises(ValueError):
            compute.run(inputs)

    def test_mapped_state_is_counted_in_total_tax(self):
        out = compute.run_case(self.FakeSim, compute.SMOKE, compute.SMOKE["cases"]["smoke"])
        self.assertEqual(out["al_income_tax"], 100.0)
        self.assertEqual(out["total_tax"], 500.0)

    def test_write_run_refuses_differing_outputs(self):
        result = {"id": "policyengine-abc", "engine_version": "2.15.6", "outputs": {"x": 1.0}}
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runstamp.write_run(d, result, json.dumps(result)), 0)
            self.assertEqual(runstamp.write_run(d, result, json.dumps(result)), 0)
            newer = dict(result, engine_version="2.16.0")
            self.assertEqual(runstamp.write_run(d, newer, json.dumps(newer)), 2)
            changed = dict(result, outputs={"x": 2.0})
            self.assertEqual(runstamp.write_run(d, changed, json.dumps(changed)), 2)


if __name__ == "__main__":
    unittest.main()


class LiquidityAndCashByYearTests(unittest.TestCase):
    """0.4.0: per-year cash and the probability-and-time view of the equity."""

    def liq(self, **over):
        block = {
            "discount_rate": {"value": 0.15, "source": "assumption:test"},
            "p_payout": {"value": [0.5, 1.0], "source": "assumption:test"},
            "years_to_liquidity": {"value": [0, 2], "source": "assumption:test"},
        }
        block.update(over)
        return block

    def test_plain_outputs_unchanged_by_liquidity_block(self):
        plain = es.run(base_inputs())["outputs"]
        withliq = es.run(base_inputs(liquidity=self.liq()))["outputs"]
        self.assertEqual(plain["totals_by_exit_value"], withliq["totals_by_exit_value"])
        self.assertEqual(plain["break_even_exit_value"], withliq["break_even_exit_value"])

    def test_certain_immediate_cell_matches_plain(self):
        out = es.run(base_inputs(liquidity=self.liq()))["outputs"]
        cell = [c for c in out["liquidity"]["cells"] if c["p_payout"] == 1.0 and c["years_to_liquidity"] == 0][0]
        self.assertEqual(cell["totals_by_exit_value"], out["totals_by_exit_value"])
        self.assertEqual(cell["break_even_exit_value"], out["break_even_exit_value"])

    def test_equity_factor_formula(self):
        inputs = base_inputs(liquidity=self.liq())
        out = es.run(inputs)["outputs"]
        cell = [c for c in out["liquidity"]["cells"] if c["p_payout"] == 0.5 and c["years_to_liquidity"] == 2][0]
        self.assertAlmostEqual(cell["equity_factor"], 0.5 / 1.15 ** 2, places=6)
        b = inputs["offers"][1]
        self.assertEqual(cell["equity_value_today"]["10000000"]["B"],
                         round(0.5 / 1.15 ** 2 * es.equity_after_tax(b, 10_000_000, inputs), 0))

    def test_discounting_raises_break_even(self):
        out = es.run(base_inputs(liquidity=self.liq()))["outputs"]
        plain = out["break_even_exit_value"]["A_vs_B"]
        cell = [c for c in out["liquidity"]["cells"] if c["p_payout"] == 0.5 and c["years_to_liquidity"] == 2][0]
        self.assertGreater(cell["break_even_exit_value"]["A_vs_B"], plain)

    def test_zero_probability_has_no_break_even(self):
        out = es.run(base_inputs(liquidity=self.liq(p_payout={"value": [0.0], "source": "assumption:t"})))["outputs"]
        self.assertNotIn("break_even_exit_value", out["liquidity"]["cells"][0])

    def test_unsourced_assumption_refused(self):
        with self.assertRaises(es.InputError):
            es.run(base_inputs(liquidity=self.liq(discount_rate={"value": 0.15, "source": "guess"})))
        with self.assertRaises(es.InputError):
            es.run(base_inputs(liquidity=self.liq(p_payout={"value": [1.5], "source": "assumption:t"})))

    def test_assumption_prefix_not_allowed_for_tax_rates(self):
        inputs = base_inputs()
        inputs["rates"]["federal_ltcg"] = {"value": 0.2, "source": "assumption:x"}
        with self.assertRaises(es.InputError):
            es.run(inputs)

    def test_cash_by_year_sums(self):
        inputs = base_inputs()
        rows = [{"value": v, "source": "run:test"} for v in (100.0, 200.0, 200.0, 200.0)]
        inputs["offers"][1] = dict(inputs["offers"][1], after_tax_cash_by_year=rows)
        b = inputs["offers"][1]
        self.assertEqual(es.cash_total(b, inputs), 700.0)
        self.assertEqual(es.total_after_tax(b, 0, inputs), 700.0)

    def test_cash_by_year_validation(self):
        inputs = base_inputs()
        inputs["offers"][1] = dict(inputs["offers"][1], after_tax_cash_by_year=[{"value": 1.0, "source": "run:t"}])
        with self.assertRaises(es.InputError):
            es.run(inputs)
        inputs["offers"][1]["after_tax_cash_by_year"] = [{"value": 1.0, "source": "guess"}] * 4
        with self.assertRaises(es.InputError):
            es.run(inputs)
