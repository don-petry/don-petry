#!/usr/bin/env python3
"""Deterministic equity-offer scenarios for the tax-wealth team.

Compares job offers that trade cash for equity: after-tax cash over a horizon plus after-tax equity
proceeds at a range of exit values, and the exit value at which two offers break even.

It does no tax law of its own. Every rate, cap and exclusion fraction is an INPUT that must carry a
source tag — `run:<id>` (an engine output, e.g. a PolicyEngine run) or `src:<key>` (an entry in
reference/rules-<year>.md). An unsourced rate is refused, which enforces the numeric
rule in reference/verification.md §2.

Usage:
    python3 scripts/equity_scenarios.py <inputs.json> [--out <runs_dir>]

Writes <runs_dir>/<id>.json stamped with engine, version, input hash and time, and prints it. The id
hashes engine, version and inputs, and an existing run file is never overwritten with different
outputs (see runstamp.py).

gain_treatment: "ltcg" (federal_ltcg + state_capital_gain), "qsbs" (§1202 exclusion inputs; gain above
the per-issuer cap is taxed at federal_ltcg), or "ordinary" (ordinary_marginal + state_ordinary — e.g.
an NSO cash-out or a disqualifying ISO disposition; the ordinary rates must be all-in as supplied).

Optional, from 0.4.0:

- `after_tax_cash_by_year` on an offer: a list of `years` sourced figures, for pay that changes over the
  horizon (e.g. a written step-up at month twelve). Each entry is {value, source} with a run:/src: source.
- `liquidity`: a probability-and-time view of the equity for an illiquid private company. Equity value
  today = after-tax equity proceeds x P(payout) / (1 + discount_rate) ^ years_to_liquidity. Cash is not
  discounted (it is paid as earned). `p_payout` and `years_to_liquidity` are lists that form a grid;
  every cell reports each offer's total and the break-even exit value of each pair. These three inputs
  are DECISION ASSUMPTIONS, not tax facts, so besides run:/src: they may carry an `assumption:` source
  naming whose assumption it is. The plain (undiscounted) outputs are unchanged.
"""

import argparse
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runstamp  # noqa: E402

ENGINE = "equity_scenarios"
VERSION = "0.4.0"
SOURCE_PREFIXES = ("run:", "src:")
ASSUMPTION_PREFIXES = SOURCE_PREFIXES + ("assumption:",)
# Inputs under "rates" that are not fractions of a dollar, so the [0, 1] bound does not apply.
NON_FRACTION_RATES = ("qsbs_cap", "qsbs_basis_multiple")


class InputError(ValueError):
    pass


def _rate(inputs, name, offer=None):
    """A rate is {"value": float, "source": "run:<id>" | "src:<key>"}; anything else is refused.

    An offer may carry its own "rates" (e.g. the gain rate at that offer's income); they win over the
    shared ones."""
    r = (offer or {}).get("rates", {}).get(name) or inputs.get("rates", {}).get(name)
    if r is None:
        raise InputError("missing rate: %s" % name)
    if not isinstance(r, dict) or "value" not in r:
        raise InputError("rate %s must be {value, source}" % name)
    src = str(r.get("source", ""))
    if not src.startswith(SOURCE_PREFIXES):
        raise InputError("rate %s has no run:/src: source — unsourced figures are not allowed" % name)
    value = _number(r["value"], "rate %s" % name)
    if name in NON_FRACTION_RATES:
        if value < 0:
            raise InputError("%s must be >= 0, got %r" % (name, value))
    elif not 0.0 <= value <= 1.0:
        raise InputError("rate %s must be a fraction in [0, 1], got %r (a percent entered as a whole number?)"
                         % (name, value))
    return value


def _number(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise InputError("%s must be a finite number, got %r" % (what, v))
    return float(v)


def _years(inputs):
    y = inputs.get("years")
    if isinstance(y, bool) or not (isinstance(y, int) or (isinstance(y, float) and y.is_integer())) or y < 1:
        raise InputError("years must be a whole number >= 1, got %r" % (y,))
    return int(y)


def _equity_terms(offer, inputs):
    """Validated (equity_pct, dilution_pct, preference_ahead_of_common, exercise_cost)."""
    pct = _number(offer.get("equity_pct"), "offer %s equity_pct" % offer.get("id"))
    if not 0.0 < pct <= 1.0:
        raise InputError("offer %s equity_pct must be a fraction in (0, 1], got %r (1%% is 0.01)"
                         % (offer.get("id"), pct))
    dilution = _number(inputs.get("dilution_pct", 0.0), "dilution_pct")
    if not 0.0 <= dilution < 1.0:
        raise InputError("dilution_pct must be in [0, 1), got %r" % dilution)
    pref = _number(inputs.get("preference_ahead_of_common", 0.0), "preference_ahead_of_common")
    if pref < 0:
        raise InputError("preference_ahead_of_common must be >= 0, got %r" % pref)
    basis = _number(offer.get("exercise_cost", 0.0), "offer %s exercise_cost" % offer.get("id"))
    if basis < 0:
        raise InputError("offer %s exercise_cost must be >= 0, got %r" % (offer.get("id"), basis))
    return pct, dilution, pref, basis


def _cash_by_year(offer, inputs):
    """Validated list of per-year after-tax cash figures, or None when the offer has none."""
    rows = offer.get("after_tax_cash_by_year")
    if rows is None:
        return None
    years = _years(inputs)
    if not isinstance(rows, list) or len(rows) != years:
        raise InputError("offer %s after_tax_cash_by_year must list exactly %d years" % (offer.get("id"), years))
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict) or not str(r.get("source", "")).startswith(SOURCE_PREFIXES):
            raise InputError("offer %s after_tax_cash_by_year[%d] needs {value, source} with a run:/src: source"
                             % (offer.get("id"), i))
        v = _number(r.get("value"), "offer %s after_tax_cash_by_year[%d]" % (offer.get("id"), i))
        if v < 0:
            raise InputError("offer %s after_tax_cash_by_year[%d] must be >= 0" % (offer.get("id"), i))
        out.append(v)
    return out


def cash_total(offer, inputs):
    """After-tax cash over the whole horizon."""
    by_year = _cash_by_year(offer, inputs)
    if by_year is not None:
        return sum(by_year)
    return cash_after_tax(offer, inputs) * _years(inputs)


def cash_after_tax(offer, inputs):
    """After-tax cash per year (the horizon average when the offer lists cash by year).

    An engine-computed figure on the offer wins over marginal rates."""
    by_year = _cash_by_year(offer, inputs)
    if by_year is not None:
        return sum(by_year) / len(by_year)
    if "after_tax_cash_per_year" in offer:
        src = str(offer.get("after_tax_cash_source", ""))
        if not src.startswith(SOURCE_PREFIXES):
            raise InputError("offer %s after_tax_cash_per_year has no run:/src: source" % offer["id"])
        return float(offer["after_tax_cash_per_year"])
    gross = offer["base"] * (1 + offer.get("bonus_target_pct", 0.0))
    rate = _rate(inputs, "ordinary_marginal", offer) + _rate(inputs, "state_ordinary", offer)
    return gross * (1 - rate)


def equity_after_tax(offer, exit_value, inputs):
    """After-tax proceeds from the offer's equity at one enterprise exit value."""
    pct, dilution, pref, basis = _equity_terms(offer, inputs)
    common_value = max(exit_value - pref, 0.0)
    owned = pct * (1 - dilution)
    proceeds = owned * common_value
    gain = max(proceeds - basis, 0.0)

    mode = inputs.get("gain_treatment")
    if mode == "ltcg":
        tax = gain * (_rate(inputs, "federal_ltcg", offer) + _rate(inputs, "state_capital_gain", offer))
    elif mode == "qsbs":
        fraction = _rate(inputs, "qsbs_excluded_fraction", offer)
        cap = max(_rate(inputs, "qsbs_cap"), _rate(inputs, "qsbs_basis_multiple") * basis)
        # IRC §1(h)(7): only gain within the per-issuer cap that is not excluded (the percentage
        # limitation) is "section 1202 gain" at the 28% rate; gain above the cap is ordinary LTCG.
        within = min(gain, cap)
        excluded = fraction * within
        federal_taxable = gain - excluded
        federal = ((within - excluded) * _rate(inputs, "qsbs_nonexcluded_rate", offer)
                   + (gain - within) * _rate(inputs, "federal_ltcg", offer))
        if "state_conforms_to_qsbs" not in inputs:
            raise InputError("state_conforms_to_qsbs must be stated explicitly (state conformity is a stale-law check)")
        state_base = federal_taxable if inputs["state_conforms_to_qsbs"] else gain
        tax = federal + state_base * _rate(inputs, "state_capital_gain", offer)
    elif mode == "ordinary":
        tax = gain * (_rate(inputs, "ordinary_marginal", offer) + _rate(inputs, "state_ordinary", offer))
    else:
        raise InputError("gain_treatment must be 'ltcg', 'qsbs' or 'ordinary'")
    return proceeds - basis - tax


def total_after_tax(offer, exit_value, inputs, equity_factor=1.0):
    """Cash over the horizon plus equity proceeds, the equity scaled by equity_factor (1 = certain, now)."""
    return cash_total(offer, inputs) + equity_factor * equity_after_tax(offer, exit_value, inputs)


def _assumption(block, name, lo, hi, as_list=False):
    """A liquidity input: {value, source} with a run:/src:/assumption: source; value in [lo, hi]."""
    r = block.get(name)
    if not isinstance(r, dict) or "value" not in r:
        raise InputError("liquidity.%s must be {value, source}" % name)
    if not str(r.get("source", "")).startswith(ASSUMPTION_PREFIXES):
        raise InputError("liquidity.%s needs a run:, src: or assumption: source" % name)
    values = r["value"] if as_list else [r["value"]]
    if as_list and (not isinstance(values, list) or not values):
        raise InputError("liquidity.%s value must be a non-empty list" % name)
    out = []
    for v in values:
        v = _number(v, "liquidity.%s" % name)
        if not lo <= v <= hi:
            raise InputError("liquidity.%s values must be in [%s, %s], got %r" % (name, lo, hi, v))
        out.append(v)
    return out if as_list else out[0]


def liquidity_grid(offers, inputs):
    """Totals and break-evens with equity weighted by P(payout) and discounted for time to liquidity."""
    block = inputs["liquidity"]
    if not isinstance(block, dict):
        raise InputError("liquidity must be an object")
    rate = _assumption(block, "discount_rate", 0.0, 1.0)
    probs = _assumption(block, "p_payout", 0.0, 1.0, as_list=True)
    horizons = _assumption(block, "years_to_liquidity", 0.0, 50.0, as_list=True)
    cells = []
    for t in horizons:
        for p in probs:
            factor = p / (1.0 + rate) ** t
            cell = {"p_payout": p, "years_to_liquidity": t, "equity_factor": round(factor, 6),
                    "equity_value_today": {}, "totals_by_exit_value": []}
            for ev in inputs["exit_values"]:
                row = {"exit_value": ev}
                for o in offers:
                    row[o["id"]] = round(total_after_tax(o, ev, inputs, factor), 0)
                cell["totals_by_exit_value"].append(row)
            for ev in inputs["exit_values"]:
                cell["equity_value_today"][str(ev)] = {
                    o["id"]: round(factor * equity_after_tax(o, ev, inputs), 0) for o in offers}
            if len(offers) >= 2 and factor > 0:
                be = {}
                for i in range(len(offers)):
                    for j in range(i + 1, len(offers)):
                        a, b = offers[i], offers[j]
                        found = break_evens(a, b, inputs, equity_factor=factor)
                        be["%s_vs_%s" % (a["id"], b["id"])] = found[0] if found else None
                cell["break_even_exit_value"] = be
            cells.append(cell)
    return {"discount_rate": rate, "cash_discounted": False, "cells": cells}


def _bisect(diff, lo, hi, tol):
    d_lo = diff(lo)
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if (diff(mid) > 0) == (d_lo > 0):
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 0)


def break_evens(a, b, inputs, lo=0.0, hi=1e11, tol=1.0, points=2000, equity_factor=1.0):
    """Every exit value in [lo, hi] where offers a and b are worth the same after tax, ascending.

    Scans lo plus a log-spaced grid up to hi for sign changes of the difference, then bisects each
    bracket. With one crossing the result is the whole-range bisection, identical to earlier versions.
    Crossings closer together than one grid step (~1% of the exit value) can be missed."""
    def diff(x):
        return total_after_tax(a, x, inputs, equity_factor) - total_after_tax(b, x, inputs, equity_factor)

    start = max(lo, 1e3)
    grid = [lo, hi]
    if start < hi:
        grid += [start * (hi / start) ** (k / (points - 1)) for k in range(points)]
    grid = sorted(x for x in set(grid) if lo <= x <= hi)
    values = [diff(x) for x in grid]
    zeros, brackets = [], []
    for i, (x, d) in enumerate(zip(grid, values)):
        if d == 0:
            if i == 0 or values[i - 1] != 0:
                zeros.append(x)
        elif i and values[i - 1] != 0 and (values[i - 1] > 0) != (d > 0):
            brackets.append((grid[i - 1], x))
    if len(brackets) == 1 and not zeros:
        return [_bisect(diff, lo, hi, tol)]
    return sorted(zeros + [_bisect(diff, x0, x1, tol) for x0, x1 in brackets])


def break_even(a, b, inputs, lo=0.0, hi=1e11, tol=1.0):
    """The lowest exit value where offers a and b break even, or None if they never cross.

    When they cross more than once, run() also reports every crossing (break_even_all_crossings)."""
    found = break_evens(a, b, inputs, lo, hi, tol)
    return found[0] if found else None


def run(inputs, now=None):
    offers = inputs["offers"]
    if len(offers) < 1:
        raise InputError("at least one offer is required")
    _years(inputs)
    for o in offers:
        _equity_terms(o, inputs)
        _cash_by_year(o, inputs)
    table = []
    for ev in inputs["exit_values"]:
        row = {"exit_value": ev}
        for o in offers:
            row[o["id"]] = round(total_after_tax(o, ev, inputs), 0)
        table.append(row)
    outputs = {
        "cash_after_tax_per_year": {o["id"]: round(cash_after_tax(o, inputs), 0) for o in offers},
        "totals_by_exit_value": table,
    }
    if len(offers) >= 2:
        crossings = {
            "%s_vs_%s" % (offers[i]["id"], offers[j]["id"]): break_evens(offers[i], offers[j], inputs)
            for i in range(len(offers)) for j in range(i + 1, len(offers))
        }
        outputs["break_even_exit_value"] = {k: (v[0] if v else None) for k, v in crossings.items()}
        multiple = {k: v for k, v in crossings.items() if len(v) > 1}
        if multiple:
            # Present only when some pair crosses more than once: there is no single break-even.
            outputs["break_even_all_crossings"] = multiple
    if "liquidity" in inputs:
        outputs["liquidity"] = liquidity_grid(offers, inputs)
    run_id, digest = runstamp.run_id(ENGINE, ENGINE, VERSION, inputs)
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": run_id,
        "engine": ENGINE,
        "engine_version": VERSION,
        "input_sha256": digest,
        "run_at": stamp,
        "label": inputs.get("label", ""),
        "assumptions": inputs.get("assumptions", []),
        "outputs": outputs,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inputs")
    ap.add_argument("--out", help="runs_dir to write <id>.json into")
    args = ap.parse_args(argv)
    with open(args.inputs, encoding="utf-8") as f:
        inputs = json.load(f)
    try:
        result = run(inputs)
    except InputError as e:
        print("REFUSED: %s" % e, file=sys.stderr)
        return 2
    result["inputs"] = os.path.relpath(args.inputs)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out and runstamp.write_run(args.out, result, text):
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
