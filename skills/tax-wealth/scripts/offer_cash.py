#!/usr/bin/env python3
"""Gross cash-and-retirement comparison for a salaried job offer (no equity).

Compares a "stay" baseline with offer cases, before tax: base, bonus, the employer's retirement
contribution (capped at the plan compensation limit), and year one versus a steady year when the new
employer's contribution needs a waiting period. It also solves for the base at which an offer's year one
matches the baseline. Writes one stamped run file that drafts cite as [run:<id>] (see runstamp.py).

After-tax figures are not computed here; they need a PolicyEngine run (compute.py).

Usage:
    python3 scripts/offer_cash.py <inputs.json> [--out <runs_dir>]

Inputs:
    {"label": "...", "assumptions": ["..."], "comp_limit": 360000,
     "baseline": {"name": "Stay", "base": 247000, "bonus": 33700, "employer_retirement": 20000},
     "offers": [{"name": "Offer 310 / 10%", "base": 310000, "bonus_pct": 0.10,
                 "employer_retirement_pct": 0.06, "year1_employer_retirement_pct": 0.0}],
     "breakeven": [{"name": "Year 1, no bonus", "bonus_pct": 0.0, "year1_employer_retirement_pct": 0.0}]}

Baseline employer retirement is either employer_retirement (dollars) or employer_retirement_pct_of_cash
(a percent of base plus bonus, capped at comp_limit); offer contributions are a percent of base, capped
at comp_limit.
"""

import argparse
import json
import sys

import runstamp

ENGINE = "offer_cash"
ENGINE_VERSION = "1.0.0"


def r2(x):
    return round(float(x), 2)


def offer_row(o, comp_limit, base_total):
    base = float(o["base"])
    bonus = base * float(o.get("bonus_pct", 0.0))
    capped = min(base, comp_limit)
    steady_ret = capped * float(o.get("employer_retirement_pct", 0.0))
    y1_ret = capped * float(o.get("year1_employer_retirement_pct", o.get("employer_retirement_pct", 0.0)))
    cash = base + bonus
    return {
        "name": o["name"],
        "base": r2(base),
        "bonus": r2(bonus),
        "total_cash": r2(cash),
        "employer_retirement_steady": r2(steady_ret),
        "employer_retirement_year1": r2(y1_ret),
        "total_steady": r2(cash + steady_ret),
        "total_year1": r2(cash + y1_ret),
        "vs_baseline_steady": r2(cash + steady_ret - base_total),
        "vs_baseline_year1": r2(cash + y1_ret - base_total),
    }


def breakeven_base(b, comp_limit, base_total):
    """Base where base*(1+bonus) + min(base, limit)*ret = base_total."""
    bonus = float(b.get("bonus_pct", 0.0))
    ret = float(b.get("year1_employer_retirement_pct", 0.0))
    base = base_total / (1.0 + bonus + ret)
    if base > comp_limit:
        base = (base_total - comp_limit * ret) / (1.0 + bonus)
    return r2(base)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    with open(a.inputs, encoding="utf-8") as f:
        inputs = json.load(f)
    limit = float(inputs["comp_limit"])
    bl = inputs["baseline"]
    bl_cash = float(bl["base"]) + float(bl.get("bonus", 0.0))
    bl_ret = float(bl.get("employer_retirement", 0.0))
    if "employer_retirement_pct_of_cash" in bl:
        bl_ret = min(bl_cash, limit) * float(bl["employer_retirement_pct_of_cash"])
    bl_total = bl_cash + bl_ret
    outputs = {
        "baseline": {"name": bl["name"], "base": r2(bl["base"]), "bonus": r2(bl.get("bonus", 0.0)),
                     "total_cash": r2(bl_cash), "employer_retirement": r2(bl_ret),
                     "total": r2(bl_total)},
        "offers": [offer_row(o, limit, bl_total) for o in inputs.get("offers", [])],
        "breakeven_base": [{"name": b["name"], "base": breakeven_base(b, limit, bl_total)}
                           for b in inputs.get("breakeven", [])],
    }
    rid, digest = runstamp.run_id("offer_cash", ENGINE, ENGINE_VERSION, inputs)
    result = {"id": rid, "engine": ENGINE, "engine_version": ENGINE_VERSION, "input_sha256": digest,
              "inputs": inputs, "outputs": outputs}
    lines = ["%s  [run:%s]" % (inputs.get("label", ""), rid),
             "Baseline %s: total %.2f" % (bl["name"], bl_total)]
    for row in outputs["offers"]:
        lines.append("%-28s cash %10.2f  steady %10.2f (%+.2f)  year1 %10.2f (%+.2f)" % (
            row["name"], row["total_cash"], row["total_steady"], row["vs_baseline_steady"],
            row["total_year1"], row["vs_baseline_year1"]))
    for b in outputs["breakeven_base"]:
        lines.append("Break-even base, %s: %.2f" % (b["name"], b["base"]))
    text = "\n".join(lines)
    if a.out:
        rc = runstamp.write_run(a.out, result, json.dumps(result, indent=2, ensure_ascii=False))
        if rc:
            return rc
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
