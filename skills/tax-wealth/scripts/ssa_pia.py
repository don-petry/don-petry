#!/usr/bin/env python3
"""Social Security PIA from a my Social Security earnings record, for the Owl retirement case (T-OWL).

Owl takes each person's Primary Insurance Amount (PIA, the monthly benefit at full retirement age).
SSA's statement prints one PIA, which assumes you keep earning your latest year's earnings through the
year before you claim. Early retirement means zero years after the last working year, so this script recomputes the
PIA for each last working year, in today's (wage-indexed) dollars, and checks itself against SSA's
own figure first.

Method (42 USC 415(a)-(b)): index each year's FICA earnings by the national average wage index
(AWI) to the index year, take the highest 35 years, AIME = floor(total / 420), PIA = 90% / 32% / 15% of
AIME across the bend points. The AWI series and bend points are read from the PolicyEngine-US
parameter files in the tax-wealth venv (gov/ssa/nawi.yaml, gov/ssa/social_security/pia/formula_factors.yaml;
each cites ssa.gov/oact). "Today's dollars" follows the statement's convention: wages held at the
index year's level, so the figure is not inflated to the claim year.

Usage:
    ~/.venvs/tax-wealth/bin/python scripts/ssa_pia.py <statement.json> \
        [--last-work-years 2026 2029 2032 2035] [--future-earnings <dollars>]
"""

import argparse
import importlib.util
import json
import math
import os
import sys

import yaml

STATEMENT_TOLERANCE = 1  # dollars per month: SSA rounds each step down to the dime, then the dollar


def pe_parameters():
    spec = importlib.util.find_spec("policyengine_us")
    if spec is None:
        raise SystemExit("REFUSED: policyengine-us not installed (T-POLICYENGINE) — needed for the AWI series")
    root = os.path.join(os.path.dirname(spec.origin), "parameters", "gov", "ssa")
    with open(os.path.join(root, "nawi.yaml"), encoding="utf-8") as f:
        awi = {int(str(k)[:4]): float(v) for k, v in yaml.safe_load(f)["values"].items()}
    with open(os.path.join(root, "social_security", "pia", "formula_factors.yaml"), encoding="utf-8") as f:
        brackets = yaml.safe_load(f)["brackets"]
    bends = {}
    for b in brackets[1:]:
        for k, v in b["threshold"]["values"].items():
            bends.setdefault(int(str(k)[:4]), []).append(float(v))
    rates = [float(list(b["rate"].values())[-1]) for b in brackets]
    return awi, bends, rates


def pia(earnings, index_year, bend_year, awi, bends, rates):
    """earnings: {year: FICA earnings}. Returns (pia_monthly, aime)."""
    indexed = sorted((e * max(1.0, awi[index_year] / awi[y]) if y <= index_year else e
                      for y, e in earnings.items()), reverse=True)
    aime = math.floor(sum(indexed[:35]) / 420)
    b1, b2 = bends[bend_year]
    amount = rates[0] * min(aime, b1) + rates[1] * max(0, min(aime, b2) - b1) + rates[2] * max(0, aime - b2)
    return math.floor(amount * 10) / 10, aime


def projected(record, last_work_year, future, first_future, stop_year):
    earnings = {int(y): float(v) for y, v in record["fica_earnings"].items()}
    for y in range(first_future, min(last_work_year, stop_year) + 1):
        earnings[y] = future
    return earnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("statement")
    ap.add_argument("--last-work-years", type=int, nargs="*", default=[])
    ap.add_argument("--future-earnings", type=float,
                    help="FICA earnings per working year from now on, today's dollars (default: last year on record)")
    ap.add_argument("--index-year", type=int, default=2024, help="latest published AWI year (default 2024)")
    ap.add_argument("--bend-year", type=int, default=2026, help="bend-point year (default 2026)")
    args = ap.parse_args(argv)
    with open(args.statement, encoding="utf-8") as f:
        record = json.load(f)
    awi, bends, rates = pe_parameters()
    born = int(record["born"][:4])
    last_year = max(int(y) for y in record["fica_earnings"])
    future = args.future_earnings or float(record["fica_earnings"][str(last_year)])
    fra = record["full_retirement_age"]

    # Check against SSA's own PIA. The statement assumes the latest year's earnings continue through the
    # year before the claim age; on 2026-10-16 that reproduced a real statement exactly at 63-67 and 70.
    stmt_pia = record["estimates_monthly"][str(fra)]
    full = projected(record, born + fra - 1, future, last_year + 1, born + fra - 1)
    got, aime = pia(full, args.index_year, args.bend_year, awi, bends, rates)
    ok = abs(math.floor(got) - stmt_pia) <= STATEMENT_TOLERANCE
    out = {"statement_pia": stmt_pia, "reproduced_pia": math.floor(got), "aime": aime, "check": "PASS" if ok else "FAIL",
           "index_year": args.index_year, "bend_year": args.bend_year, "future_earnings": future,
           "by_last_work_year": {}}
    for lw in args.last_work_years:
        e = projected(record, lw, future, last_year + 1, born + fra - 1)
        p, a = pia(e, args.index_year, args.bend_year, awi, bends, rates)
        out["by_last_work_year"][str(lw)] = {"pia_monthly": math.floor(p), "aime": a}
    print(json.dumps(out, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
