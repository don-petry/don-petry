#!/usr/bin/env python3
"""PolicyEngine-US wrapper for the tax-wealth team (trigger T-POLICYENGINE).

Takes a small household description with named cases, runs each through PolicyEngine-US, and writes
one stamped run file (engine, version, input hash, time) that drafts cite as [run:<id>]. The id hashes
engine, version and inputs, and an existing run file is never overwritten with different outputs (see
runstamp.py).

Usage (inside the tax-wealth venv — see reference/triggers.yaml T-POLICYENGINE; paths relative to the skill):
    python scripts/compute.py <inputs.json> [--out <runs_dir>]
    python scripts/compute.py --smoke

A fuller example: examples/household-2026.example.json. Alabama ("AL") is the state mapped today, as the
worked example; add a state to STATE_OUTPUTS (and STATE_ITEMIZED_OUTPUTS) from PolicyEngine-US's variables.

Inputs:
    {"tax_year": 2026, "state": "AL", "label": "...", "assumptions": ["..."],
     "adults": [{"id": "parent_a", "age": 45}, {"id": "parent_b", "age": 47}],
     "dependents": [{"id": "child_1", "age": 12}],
     "cases": {"A": {"parent_a.wages": 390000, "parent_b.wages": 100000},
               "A_gain": {"parent_a.wages": 390000, "parent_b.wages": 100000, "parent_a.ltcg": 1000000}},
     "derive": [{"name": "A_after_tax", "type": "after_tax_increment", "case": "A", "base": "base",
                 "gross": 390000},
                {"name": "A_gain_federal_rate", "type": "rate", "case": "A_gain", "base": "A",
                 "amount": 1000000, "vars": ["income_tax"]}]}

Per-person fields a case may set: wages, ltcg (long-term capital gains), stcg, interest, dividends
(qualified), ordinary_dividends (non-qualified), other_income (taxed as ordinary income), schedule_c (Schedule C net
profit, negative for a loss — e.g. a disregarded single-member LLC), and the
itemized-deduction inputs charitable_cash, charitable_noncash, real_estate_taxes, mortgage_interest
(home acquisition interest). Payroll: set wages to Medicare wages (W-2 box 5) and pretax_payroll to the
part excluded from box 1 (401(k) deferrals), so box-1 wages = wages - pretax_payroll and the Additional
Medicare tax uses the right base. contrib_529: contributions to the state's 529 plan (the state deduction, capped by the engine's
parameters; in the Alabama example, CollegeCounts). Dependents may set childcare_expenses (care for a child under 13);
the earner sets dependent_care_benefits (employer dependent-care FSA, W-2 box 10).
Tax-unit fields: tu.foreign_tax_credit and tu.qbi_deduction override the engine's own figure with the
return's when calibrating against a filed return.
Tax-unit field: tu.state_income_tax_paid — state income tax actually paid in the year (withholding plus
estimates), the cash-basis figure federal Schedule A line 5a uses. Without it the engine estimates
withholding from income, which is not the household's figure.

Scholarship-granting-organization (SGO) gifts, per case (see sgo_credits below):
    "sgo.al_gift": 12700            Alabama Accountability Act gift; credit = min(gift, Alabama tax, cap)
    "sgo.federal": "safe_harbor"    federal treatment of that gift:
        "safe_harbor" — no charitable deduction; the credited part counts as state tax paid (needs
                        tu.state_income_tax_paid)                     [rule:fed-164-3j-safe-harbor]
        "charitable"  — deducted as a charitable gift (how a DAF-routed gift was filed)
        "none"        — neither (deduction reduced, no safe harbor)  [rule:fed-170a-state-credit-reduction]
    "sgo.al_deducted": false        also deducted on the Alabama itemized schedule? Default false — the
                                    rule bars it [rule:al-aaa-no-al-deduction]; true reproduces an
                                    error, for checking a filed return
    "sgo.f25f_gift": 1700           federal §25F gift (tax years 2027+), no Alabama credit claimed on it
    "sgo.f25f_cap": 1700            §25F credit cap; joint-return cap unsettled ([rule:fed-25f-credit],
                                    [rule:fed-25f-prop-regs]) — set 3400 to model the per-spouse reading
Household inputs stay on this machine; nothing is sent anywhere.
"""

import argparse
import datetime
import importlib.metadata
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runstamp  # noqa: E402

FIELDS = {
    "wages": "employment_income",
    "ltcg": "long_term_capital_gains",
    "stcg": "short_term_capital_gains",
    "interest": "taxable_interest_income",
    "dividends": "qualified_dividend_income",
    "ordinary_dividends": "non_qualified_dividend_income",
    "other_income": "miscellaneous_income",
    "charitable_cash": "charitable_cash_donations",
    "charitable_noncash": "charitable_non_cash_donations",
    "real_estate_taxes": "real_estate_taxes",
    "mortgage_interest": "home_mortgage_interest",
    "pretax_payroll": "traditional_401k_contributions",
    "childcare_expenses": "pre_subsidy_childcare_expenses",
    "dependent_care_benefits": "dependent_care_employer_benefits",
    "contrib_529": "investment_in_529_plan_indv",
    "schedule_c": "self_employment_income",
}
TU_FIELDS = {
    "state_income_tax_paid": "state_withheld_income_tax",
    "foreign_tax_credit": "foreign_tax_credit",
    "qbi_deduction": "qualified_business_income_deduction",
    "al_agi": "al_agi",
}
# tu.al_agi_offset: Alabama AGI = federal AGI + offset, for Alabama-only items the engine does not model
# (on these returns: Alabama-specific rental figures and adjustments). Resolved to tu.al_agi before a run.
ITEMIZED_FIELDS = {"charitable_cash", "charitable_noncash", "real_estate_taxes", "mortgage_interest",
                   "pretax_payroll", "childcare_expenses", "dependent_care_benefits", "contrib_529"}
# Reported only for cases that use itemized or SGO inputs, so earlier run files keep their outputs.
ITEMIZED_OUTPUTS = [
    "tax_unit_itemizes", "itemized_taxable_income_deductions", "charitable_deduction",
    "salt_deduction", "salt_cap", "income_tax_before_refundable_credits",
    "adjusted_gross_income", "ctc", "non_refundable_ctc", "refundable_ctc", "cdcc", "foreign_tax_credit",
    "qualified_business_income_deduction",
]
STATE_ITEMIZED_OUTPUTS = {"AL": ["al_agi", "al_dependent_exemption", "al_itemized_deductions", "al_529_plan_deduction",
                                 "al_deductions", "al_taxable_income",
                                 "al_income_tax_before_non_refundable_credits"]}

# SGO rules — each constant is quoted in reference/rules-2026.md.
AL_AAA_CAP = 100000.0     # [rule:al-aaa-credit-individual-limits] per individual or married couple
F25F_CAP = 1700.0         # [rule:fed-25f-credit]
F25F_FIRST_YEAR = 2027    # [rule:fed-25f-credit] taxable years ending after 2026-12-31
SGO_KEYS = {"sgo.al_gift", "sgo.federal", "sgo.al_deducted", "sgo.f25f_gift", "sgo.f25f_cap"}
SGO_FEDERAL = ("safe_harbor", "charitable", "none")
CONVERGE_TOL = 0.005
MAX_PASSES = 12
TAX_UNIT_OUTPUTS = [
    "adjusted_gross_income", "standard_deduction", "taxable_income", "income_tax",
    "alternative_minimum_tax", "net_investment_income_tax", "additional_medicare_tax",
]
PERSON_OUTPUTS = ["employee_social_security_tax", "employee_medicare_tax"]
STATE_OUTPUTS = {"AL": "al_income_tax"}  # Alabama is the worked example; add a state here before running a household in it


def state_var(inputs):
    """The state income-tax output for the household's state. An unmapped state is refused rather than
    reported with zero state tax."""
    var = STATE_OUTPUTS.get(inputs.get("state"))
    if not var:
        raise ValueError("no state income-tax variable mapped for state %r — add it to STATE_OUTPUTS"
                         % (inputs.get("state"),))
    return var


# Known answer, verified 2026-09-26 against IRS newsroom "IRS releases tax inflation adjustments for
# tax year 2026" — "For tax year 2026, the standard deduction increases to $32,200 for married couples
# filing jointly." Cited in reference/rules-2026.md as [src:std-deduction-2026-mfj].
SMOKE = {
    "tax_year": 2026, "state": "AL", "label": "smoke",
    "adults": [{"id": "a", "age": 45}, {"id": "b", "age": 45}],
    "dependents": [],
    "cases": {"smoke": {"a.wages": 390000}},
}
SMOKE_EXPECT = {"standard_deduction": 32200.0, "taxable_income": 357800.0}


def split_case(case):
    """Separate a case's engine inputs from its sgo.* keys."""
    base = {k: v for k, v in case.items() if not k.startswith("sgo.")}
    sgo = {k: v for k, v in case.items() if k.startswith("sgo.")}
    unknown = set(sgo) - SGO_KEYS
    if unknown:
        raise ValueError("unknown case field: %s" % ", ".join(sorted(unknown)))
    return base, sgo


def situation(inputs, case, adj=None):
    """PolicyEngine situation for one case. `adj` carries the SGO adjustments sgo_credits() applies:
    charitable_add (to the first adult), salt_paid_add (to state tax paid) and al_itemized (override)."""
    adj = adj or {}
    year = str(inputs["tax_year"])
    people = {}
    tax_unit = {}
    for p in inputs["adults"] + inputs.get("dependents", []):
        people[p["id"]] = {"age": {year: p["age"]}}
        if p in inputs.get("dependents", []):
            people[p["id"]]["is_tax_unit_dependent"] = {year: True}
    for key, value in case.items():
        pid, field = key.split(".", 1)
        if pid == "tu":
            if field not in TU_FIELDS:
                raise ValueError("unknown case field: %s" % key)
            tax_unit[TU_FIELDS[field]] = {year: value}
            continue
        if pid not in people or field not in FIELDS:
            raise ValueError("unknown case field: %s" % key)
        people[pid][FIELDS[field]] = {year: value}
    first = inputs["adults"][0]["id"]
    if adj.get("charitable_add"):
        cur = people[first].get("charitable_cash_donations", {}).get(year, 0)
        people[first]["charitable_cash_donations"] = {year: cur + adj["charitable_add"]}
    if adj.get("salt_paid_add"):
        cur = tax_unit["state_withheld_income_tax"][year]
        tax_unit["state_withheld_income_tax"] = {year: cur + adj["salt_paid_add"]}
    if "al_itemized" in adj:
        tax_unit["al_itemized_deductions"] = {year: adj["al_itemized"]}
    members = list(people)
    adults = [p["id"] for p in inputs["adults"]]
    return {
        "people": people,
        "tax_units": {"tu": dict(members=members, **tax_unit)},
        "marital_units": {"mu": {"members": adults}},
        "families": {"f": {"members": members}},
        "spm_units": {"s": {"members": members}},
        "households": {"h": {"members": members, "state_name": {year: inputs["state"]}}},
    }


def outputs(sim, inputs, extended):
    year = int(inputs["tax_year"])
    names = TAX_UNIT_OUTPUTS + PERSON_OUTPUTS + [state_var(inputs)]
    if extended:
        names += ITEMIZED_OUTPUTS + STATE_ITEMIZED_OUTPUTS.get(inputs["state"], [])
    return {v: round(float(sim.calculate(v, year).sum()), 2) for v in names}


def total_tax(out, svar):
    return round(out["income_tax"] + out[svar] + out["employee_social_security_tax"]
                 + out["employee_medicare_tax"] + out["additional_medicare_tax"], 2)


def al_sgo_credit(gift, al_tax_before_credits):
    """Accountability Act credit: 100% of the gift, up to 100% of the Alabama tax, capped
    [rule:al-aaa-credit-individual-limits]. The unused part carries forward [rule:al-aaa-carryforward]."""
    return round(min(gift, max(al_tax_before_credits, 0.0), AL_AAA_CAP), 2)


def f25f_credit(gift, cap, federal_tax_before_refundable):
    """§25F credit: the gift up to the cap, limited to federal tax (non-refundable) [rule:fed-25f-credit].
    No Alabama credit is claimed on this gift, so there is no state-credit reduction."""
    return round(min(gift, cap, max(federal_tax_before_refundable, 0.0)), 2)


def sgo_credits(Simulation, inputs, base, sgo):
    """Run one case with SGO gifts. The Alabama credit depends on Alabama tax, which depends on
    federal tax (Alabama deducts it), which under the safe harbor depends on the credit — so the case
    is re-run until the credit stops changing."""
    year = int(inputs["tax_year"])
    gift = float(sgo.get("sgo.al_gift", 0) or 0)
    fed = sgo.get("sgo.federal")
    al_deducted = bool(sgo.get("sgo.al_deducted", False))
    gift25 = float(sgo.get("sgo.f25f_gift", 0) or 0)
    cap25 = float(sgo.get("sgo.f25f_cap", F25F_CAP))
    if gift < 0 or gift25 < 0 or cap25 <= 0:
        raise ValueError("SGO gifts must be >= 0 and the §25F cap > 0")
    if gift and inputs["state"] != "AL":
        raise ValueError("sgo.al_gift is the Alabama Accountability Act credit; state must be AL")
    if gift and fed not in SGO_FEDERAL:
        raise ValueError("sgo.federal must be one of %s when sgo.al_gift is set" % ", ".join(SGO_FEDERAL))
    if fed == "safe_harbor" and "tu.state_income_tax_paid" not in base:
        raise ValueError("sgo.federal=safe_harbor needs tu.state_income_tax_paid (cash-basis state tax "
                         "paid); the engine's withholding estimate is not the household's figure")
    if gift25 and year < F25F_FIRST_YEAR:
        raise ValueError("§25F applies to tax years %d and later" % F25F_FIRST_YEAR)

    adj = {}
    if gift and fed == "charitable":
        adj["charitable_add"] = gift
        if not al_deducted:
            # Alabama itemized deductions computed without the credited gift [rule:al-aaa-no-al-deduction]
            no_gift = Simulation(situation=situation(inputs, base))
            adj["al_itemized"] = float(no_gift.calculate("al_itemized_deductions", year).sum())
    credit, passes = 0.0, 0
    while True:
        passes += 1
        a = dict(adj)
        if fed == "safe_harbor" and credit:
            a["salt_paid_add"] = credit  # only the credit actually applied [rule:fed-164-3j-safe-harbor]
        sim = Simulation(situation=situation(inputs, base, a))
        out = outputs(sim, inputs, True)
        new = al_sgo_credit(gift, out["al_income_tax_before_non_refundable_credits"]) if gift else 0.0
        if abs(new - credit) < CONVERGE_TOL:
            break
        if passes >= MAX_PASSES:
            raise ValueError("SGO credit did not converge after %d passes" % MAX_PASSES)
        credit = new
    svar = state_var(inputs)
    c25 = f25f_credit(gift25, cap25, out["income_tax_before_refundable_credits"]) if gift25 else 0.0
    out.update({
        "al_sgo_gift": gift,
        "al_sgo_credit": credit,
        "al_sgo_credit_unused": round(gift - credit, 2),
        "sgo_federal_treatment": fed or "",
        "sgo_safe_harbor_salt_added": credit if fed == "safe_harbor" else 0.0,
        "al_income_tax_after_sgo_credit": round(out[svar] - credit, 2),
        "f25f_gift": gift25,
        "f25f_credit": c25,
        "f25f_credit_unused": round(min(gift25, cap25) - c25, 2),
        "income_tax_after_f25f": round(out["income_tax"] - c25, 2),
        "sgo_passes": passes,
    })
    out["total_tax"] = round(total_tax(out, svar) - credit - c25, 2)
    return out


def resolve_al_agi(Simulation, inputs, base):
    """Turn tu.al_agi_offset into a tu.al_agi override. Federal AGI does not depend on the SGO
    adjustments (they are deductions), so one extra pass is enough."""
    if "tu.al_agi_offset" not in base:
        return base
    if inputs["state"] != "AL":
        raise ValueError("tu.al_agi_offset applies to Alabama only")
    base = dict(base)
    offset = float(base.pop("tu.al_agi_offset"))
    sim = Simulation(situation=situation(inputs, base))
    agi = float(sim.calculate("adjusted_gross_income", int(inputs["tax_year"])).sum())
    base["tu.al_agi"] = round(agi + offset, 2)
    return base


def run_case(Simulation, inputs, case):
    base, sgo = split_case(case)
    base = resolve_al_agi(Simulation, inputs, base)
    if sgo:
        return sgo_credits(Simulation, inputs, base, sgo)
    extended = any(k.startswith("tu.") or k.split(".", 1)[1] in ITEMIZED_FIELDS for k in base)
    sim = Simulation(situation=situation(inputs, base))
    out = outputs(sim, inputs, extended)
    out["total_tax"] = total_tax(out, state_var(inputs))
    return out


def derive(results, specs):
    """Deterministic figures computed from case outputs, so drafts cite them as [run:<id>] too.

    after_tax_increment: gross - (case.total_tax - base.total_tax) — the after-tax value of income that
        separates `case` from `base` (e.g. one adult's pay under an offer).
    rate: (sum of vars in case - sum in base) / amount — the tax rate on the amount that separates them
        (e.g. a capital gain), for the listed output variables.
    delta: sum of vars in case - sum in base — the dollar difference between two cases.
    """
    out = {}
    for d in specs:
        c, b = results[d["case"]], results[d["base"]]
        if d["type"] == "after_tax_increment":
            out[d["name"]] = round(d["gross"] - (c["total_tax"] - b["total_tax"]), 2)
        elif d["type"] == "rate":
            out[d["name"]] = round(sum(c[v] - b[v] for v in d["vars"]) / d["amount"], 6)
        elif d["type"] == "delta":
            out[d["name"]] = round(sum(c[v] - b[v] for v in d["vars"]), 2)
        else:
            raise ValueError("unknown derive type: %s" % d["type"])
    return out


# Bump when a change to this wrapper can change outputs for inputs it already accepted. Version 1 runs
# (no compute_version recorded) keep their ids; later versions fold the version into the id.
COMPUTE_VERSION = 2


def run(inputs, now=None):
    state_var(inputs)
    from policyengine_us import Simulation
    version = importlib.metadata.version("policyengine-us")
    results = {name: run_case(Simulation, inputs, case) for name, case in inputs["cases"].items()}
    if inputs.get("derive"):
        results["derived"] = derive(results, inputs["derive"])
    v2 = any(k.startswith(("tu.", "sgo.")) or k.split(".", 1)[1] in ITEMIZED_FIELDS
             for case in inputs["cases"].values() for k in case)
    engine_version = version if not v2 else "%s+compute.%d" % (version, COMPUTE_VERSION)
    run_id, digest = runstamp.run_id("policyengine", "policyengine-us", engine_version, inputs)
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": run_id,
        "engine": "policyengine-us",
        "engine_version": version,
        **({"compute_version": COMPUTE_VERSION} if v2 else {}),
        "input_sha256": digest,
        "run_at": stamp,
        "label": inputs.get("label", ""),
        "assumptions": inputs.get("assumptions", []),
        "outputs": results,
    }


def smoke():
    got = run(SMOKE)["outputs"]["smoke"]
    bad = {k: (got[k], v) for k, v in SMOKE_EXPECT.items() if got[k] != v}
    if bad:
        print("SMOKE FAIL (got, expected): %s" % bad, file=sys.stderr)
        return 1
    print("SMOKE OK — policyengine-us %s — %s" % (importlib.metadata.version("policyengine-us"), SMOKE_EXPECT))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inputs", nargs="?")
    ap.add_argument("--out", help="runs_dir to write <id>.json into")
    ap.add_argument("--smoke", action="store_true", help="run the known-answer case")
    args = ap.parse_args(argv)
    if args.smoke:
        return smoke()
    if not args.inputs:
        ap.error("inputs file required (or --smoke)")
    with open(args.inputs, encoding="utf-8") as f:
        inputs = json.load(f)
    try:
        result = run(inputs)
    except ValueError as e:
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
