#!/usr/bin/env python3
"""Owl retirement-planner wrapper for the tax-wealth team (trigger T-OWL).

Takes a household retirement case (examples/retirement-case.example.json shows the shape), builds one Owl plan per scenario and
objective, solves each, and writes one stamped run file (engine, version, input hash, time) that drafts
cite as [run:<id>]. Ids and write-once files come from runstamp.py, as for compute.py.

Owl is a multi-decade planner: it optimizes Roth conversions and the order of withdrawals (taxable,
tax-deferred, Roth) for maximum lifetime spending or estate. Single-year tax questions stay with
compute.py (PolicyEngine); Owl's own tax model takes the standard deduction only.

Usage (inside the Owl venv — see reference/triggers.yaml T-OWL; paths relative to the skill folder):
    ~/.venvs/owl/bin/python scripts/retirement.py run <case.json> [--out <runs_dir>]
    ~/.venvs/owl/bin/python scripts/retirement.py verify [--examples <dir>]

`verify` solves three of Owl's published example cases and compares them with the values its own test
suite pins (tests/plan/test_toml_cases.py). `--examples` points at a checkout's examples/ folder; without
it the folder is cloned at the installed version's tag into a temporary directory.
"""

import argparse
import contextlib
import datetime
import importlib.metadata
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runstamp  # noqa: E402

# Pinned by Owl's own test suite (tests/plan/test_toml_cases.py, EXPECTED_OBJECTIVE_VALUES), today's $.
VERIFY_CASES = {
    "Case_jack+jill": (102_535, 400_000),
    "Case_joe": (92_575, 300_000),
    "Case_john+sally": (145_000, 16_803),
}
OWL_REPO = "https://github.com/mdlacasse/Owl.git"


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(float(v)) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return json.dumps(v)
    return "[ " + ", ".join(_toml_value(x) for x in v) + " ]"


def _toml(sections):
    out = []
    for name, body in sections.items():
        if name == "":
            out += ["%s = %s" % (k, _toml_value(v)) for k, v in body.items()]
            continue
        out.append("\n[%s]" % name)
        out += ["%s = %s" % (k, _toml_value(v)) for k, v in body.items()]
    return "\n".join(out) + "\n"


def inflator(case):
    rate = case["rates"]["values"][3] / 100.0
    start = int(case["start_date"][:4])
    return lambda year: (1 + rate) ** (year - start)


def pia_from_benefit(born, annual_benefit, at_age):
    """Monthly PIA implied by an annual benefit claimed at at_age, using Owl's own SSA factor."""
    from owlplanner import socialsecurity as ss
    y, m, d = (int(x) for x in born.split("-"))
    fra = ss.getFRAs([y], [m], [d])[0]
    return annual_benefit / 12.0 / ss.getSelfFactor(fra, at_age, d == 1)


def hfp_tables(case, scenario):
    """Per-person year tables (nominal dollars) for Owl's Household Financial Profile."""
    import pandas as pd
    grow = inflator(case)
    start = int(case["start_date"][:4])
    ev = case["events"]
    tables = {}
    for p in case["people"]:
        pid, born_year = p["id"], int(p["born"][:4])
        last_year = born_year + p["life_expectancy"]
        last_work = scenario[pid]
        w = case["wages"][pid]
        rows = []
        for year in range(start - 5, last_year + 1):
            r = {"year": year, "anticipated wages": 0.0, "other inc": 0.0, "401k ctrb": 0.0,
                 "Roth 401k ctrb": 0.0, "big-ticket items": 0.0}
            if start <= year <= last_work:
                c = w["contrib_%d_remaining" % start] if year == start else w["contrib_today"]
                f = 1.0 if year == start else grow(year)
                r["401k ctrb"] = round(c["401k_ctrb"] * f, 2)
                r["Roth 401k ctrb"] = round(c["roth_401k_ctrb"] * f, 2)
                full = w["contrib_today"]
                box1 = w["box1_wages"] if "box1_wages" in w else w["box1_2025"]  # W-2 box 1, latest filed year
                r["anticipated wages"] = round((box1 - full["roth_401k_ctrb"]) * grow(year), 2)
            if year >= start:
                if ev.get("rental_income", {}).get("who") == pid:
                    r["other inc"] = round(ev["rental_income"]["annual_today"] * grow(year), 2)
                for item in ev.get("items", []):
                    if item["who"] == pid and year in item["years"]:
                        r["big-ticket items"] += round(item["amount_today"] * grow(year), 2)
                hc = ev.get("health_care_pre_medicare")
                if hc and last_work < year < born_year + hc["medicare_age"]:
                    r["big-ticket items"] -= round(hc["annual_today_per_person"] * grow(year), 2)
            rows.append(r)
        tables[p["name"]] = pd.DataFrame(rows)
    return tables


def ss_pia(person, ss, scenario):
    """Monthly PIA: from an SSA statement per last working year when the case has it, else converted."""
    by_year = ss.get("pia_by_last_work_year")
    if by_year:
        key = str(scenario[person["id"]])
        if key not in by_year:
            raise ValueError("no SSA PIA for %s with last working year %s — run ssa_pia.py" % (person["id"], key))
        return by_year[key]
    return round(pia_from_benefit(person["born"], ss["annual_benefit"], ss["at_age"]))


def case_toml(case, objective, scenario):
    people = case["people"]
    names = [p["name"] for p in people]
    k = lambda x: round(x / 1000.0, 5)  # noqa: E731 — Owl's case-file units are $k
    bal = case["balances"]
    pen = case["pensions"]
    ss = case["social_security"]
    sb = case["allocation"]["stocks_bonds"]
    mix = [sb[0], sb[1], 0, 0]
    solver = {"withMedicare": "loop", "withSSTaxability": "loop", "solver": "HiGHS", "spendingSlack": 0}
    if objective["objective"] == "maxSpending":
        solver["bequest"] = k(objective.get("bequest_today", 0.0))
    else:
        solver["netSpending"] = k(objective["net_spending_today"])
    return _toml({
        "": {"case_name": case.get("case_name", "household"), "description": case.get("label", "")},
        "basic_info": {
            "status": "married", "names": names, "sexes": [p["sex"] for p in people],
            "date_of_birth": [p["born"] for p in people],
            "life_expectancy": [p["life_expectancy"] for p in people],
            "start_date": case["start_date"], "state": case["state"],
        },
        "savings_assets": {
            "taxable_savings_balances": [k(bal[p["id"]]["taxable"]) for p in people],
            "tax_deferred_savings_balances": [k(bal[p["id"]]["tax_deferred"]) for p in people],
            "tax_free_savings_balances": [k(bal[p["id"]]["tax_free"]) for p in people],
            "beneficiary_fractions": [1.0, 1.0, 1.0, 1.0],
            "spousal_surplus_deposit_fraction": 0.5,
        },
        "fixed_income": {
            "pension_monthly_amounts": [float(pen[p["id"]]["monthly"]) for p in people],
            "pension_ages": [float(pen[p["id"]]["age"]) for p in people],
            "pension_indexed": [bool(pen[p["id"]]["indexed"]) for p in people],
            "pension_survivor_fraction": [float(pen[p["id"]]["survivor_fraction"]) for p in people],
            "social_security_pia_amounts": [ss_pia(p, ss[p["id"]], scenario) for p in people],
            "social_security_ages": [float(ss[p["id"]]["claim_age"]) for p in people],
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": 30.0, "dividend_rate": 1.7,
            "method": case["rates"]["method"], "values": case["rates"]["values"],
        },
        "asset_allocation": {
            "interpolation_method": "linear", "interpolation_center": 15.0, "interpolation_width": 5.0,
            "type": "individual", "generic": [[mix, mix], [mix, mix]],
        },
        "optimization_parameters": {
            "spending_profile": case["spending"]["profile"],
            "surviving_spouse_spending_percent": case["spending"]["survivor_percent"],
            "objective": objective["objective"],
        },
        "solver_options": solver,
    })


def solve_one(case, scenario, objective):
    import owlplanner as owl
    p = owl.readConfig(io.StringIO(case_toml(case, objective, scenario)), verbose=False, loadHFP=False)
    p.readHFP(hfp_tables(case, scenario), filename_for_logging="retirement-case.json")
    p.solverOptions["absTol"] = 50
    p.solverOptions["relTol"] = 2e-5
    p.resolve()
    if p.caseStatus != "solved":
        return {"status": p.caseStatus}
    years = [int(y) for y in p.year_n]
    defl = [1.0 / g for g in p.gamma_n[: len(years)]]
    acct = ["taxable", "tax_deferred", "tax_free"]
    per_year = []
    for n, year in enumerate(years):
        row = {"year": year, "net_spending_today": round(float(p.g_n[n]) * defl[n])}
        for j, a in enumerate(acct):
            row["start_balance_%s_today" % a] = round(float(sum(p.b_ijn[:, j, n])) * defl[n])
            row["withdrawal_%s_today" % a] = round(float(sum(p.w_ijn[:, j, n])) * defl[n])
        row["roth_conversion_today"] = round(float(sum(p.x_in[:, n])) * defl[n])
        per_year.append(row)
    # Today's-dollar lines only; the timing lines change on every solve and would break write-once runs.
    volatile = ("executed on", "Solve time", "(nominal)")
    summary = {k: v for k, v in p.summaryDic().items()
               if v != "" and not any(s in k for s in volatile)}
    return {
        "status": "solved",
        "net_spending_basis_today": round(float(p.basis)),
        "bequest_today": round(float(p.bequest)),
        "summary": summary,
        "per_year": per_year,
    }


def run(case, now=None):
    version = importlib.metadata.version("owlplanner")
    scenarios = {k: v for k, v in case["scenarios"].items() if not k.startswith("_")}
    outputs = {}
    for sname, scen in scenarios.items():
        for obj in case["objectives"]:
            outputs["%s.%s" % (sname, obj["name"])] = solve_one(case, scen, obj)
    run_id, digest = runstamp.run_id("owl", "owlplanner", version, case)
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": run_id,
        "engine": "owlplanner",
        "engine_version": version,
        "input_sha256": digest,
        "run_at": stamp,
        "label": case.get("label", ""),
        "pending": case.get("pending", []),
        "outputs": outputs,
    }


def verify(examples=None):
    import owlplanner as owl
    version = importlib.metadata.version("owlplanner")
    tmp = None
    if not examples:
        tmp = tempfile.mkdtemp(prefix="owl-examples-")
        tag = "v" + version
        cmd = ["git", "clone", "-q", "--depth", "1", "--branch", tag, OWL_REPO, tmp]
        if subprocess.run(cmd, stderr=subprocess.DEVNULL, timeout=120).returncode != 0:
            # Not every PyPI release is tagged; the examples on the default branch are the fallback.
            print("note: no tag %s; using the default branch's examples" % tag)
            if subprocess.run(["git", "clone", "-q", "--depth", "1", OWL_REPO, tmp], timeout=120).returncode != 0:
                print("VERIFY BLOCKED: could not clone %s; pass --examples" % OWL_REPO, file=sys.stderr)
                return 2
        examples = os.path.join(tmp, "examples")
    bad = 0
    for case, (spend, beq) in VERIFY_CASES.items():
        p = owl.readConfig(os.path.join(examples, case), verbose=False)
        p.readHFP(os.path.join(examples, case.replace("Case_", "HFP_") + ".xlsx"))
        p.solverOptions["absTol"] = 50
        p.solverOptions["relTol"] = 2e-5
        p.resolve()
        ok = abs(p.basis - spend) <= max(50, 5e-4 * spend) and abs(p.bequest - beq) <= max(1, 5e-4 * beq)
        bad += not ok
        print("%s %s: spending %.0f (pinned %d), bequest %.0f (pinned %d)"
              % ("PASS" if ok else "FAIL", case, p.basis, spend, p.bequest, beq))
    print("VERIFY %s — owlplanner %s" % ("OK" if not bad else "FAIL", version))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--out", help="runs_dir to write <id>.json into")
    v = sub.add_parser("verify")
    v.add_argument("--examples")
    args = ap.parse_args(argv)
    if args.cmd == "verify":
        return verify(args.examples)
    with open(args.case, encoding="utf-8") as f:
        case = json.load(f)
    with contextlib.redirect_stdout(sys.stderr):  # Owl logs to stdout; keep stdout for the run JSON
        result = run(case)
    result["inputs"] = os.path.relpath(args.case)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out and runstamp.write_run(args.out, result, text):
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
