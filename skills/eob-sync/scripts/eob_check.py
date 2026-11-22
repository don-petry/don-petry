#!/usr/bin/env python3
"""Flag health and dental claims that need proactive management. Insurer-agnostic.

Reads the EOB store (config/household.yaml `paths.store`, relative to the repository root; or --dir):
  plans.yaml        plan facts, expected claims, thresholds
  claims.csv        one row per claim, transcribed from the portal EOB
  notices.csv       carrier emails (EOB ready, premium posted, prior auth)
  accumulators.csv  deductible / out-of-pocket / annual-max snapshots from the portal

Prints one line per issue and exits 1 when anything needs a person (ACT).
Read-only unless --write (re-renders the issues block in index.md) or
--mark-reviewed (stamps notices as read after a portal pass).

  python3 skills/eob-sync/scripts/eob_check.py
  python3 skills/eob-sync/scripts/eob_check.py --write
  python3 skills/eob-sync/scripts/eob_check.py --mark-reviewed dental 2026-11-08
  python3 skills/eob-sync/scripts/eob_check.py --dir skills/eob-sync/examples/store --today 2026-11-08
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys

import yaml

SKILL = pathlib.Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]                      # skills/<name>/ sits two levels below the repository root
CONFIG = SKILL / "config" / "household.yaml"
START, END = "<!-- eob-issues:start -->", "<!-- eob-issues:end -->"
RANK = {"ACT": 0, "WATCH": 1, "INFO": 2}

COB_RE = re.compile(r"coordinat|other (insurance|coverage)|\bCOB\b|medicaid", re.I)
INFO_RE = re.compile(r"additional information|records|questionnaire|accident|subrogat|itemized", re.I)


def load_config() -> dict:
    """The household's config/household.yaml (private; copy household.example.yaml to start)."""
    return (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}) if CONFIG.exists() else {}


def default_store() -> pathlib.Path | None:
    p = (load_config().get("paths") or {}).get("store")
    return REPO / p if p else None


def money(v: str) -> float:
    v = (v or "").replace("$", "").replace(",", "").strip()
    return float(v) if v else 0.0


def day(v: str) -> dt.date | None:
    v = (v or "").strip()
    return dt.date.fromisoformat(v) if v else None


def read_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def issue(sev, code, plan, ref, what, action, clock=""):
    return {"sev": sev, "code": code, "plan": plan, "ref": ref,
            "what": what, "action": action, "clock": clock}


def check_notices(notices, plans, today, th):
    out = []
    for plan in sorted({n["plan"] for n in notices}):
        unread = [n for n in notices if n["plan"] == plan and n["kind"] == "eob" and not n["reviewed"]]
        if unread:
            oldest = min(day(n["date"]) for n in unread)
            age = (today - oldest).days
            sev = "ACT" if age > th["stale_days"] else "WATCH"
            out.append(issue(sev, "EOB_UNREAD", plan, f"{len(unread)} notices",
                             f"{len(unread)} EOB notice(s) not read in the portal; oldest {oldest} ({age} days)",
                             "Sign in to the portal and transcribe each EOB into claims.csv"))
    for n in notices:
        if n["kind"] == "prior_auth" and not n["reviewed"]:
            out.append(issue("ACT", "PRIOR_AUTH", n["plan"], n["date"],
                             "Prior authorization status changed; member and service not yet known",
                             "Read it in the portal (precert page); record approved/denied and dates"))

    # Premium: for each plan that sends payment confirmations, every month since the first should have one.
    for plan in sorted({n["plan"] for n in notices if n["kind"] == "premium_paid"}):
        paid = sorted(day(n["date"]) for n in notices if n["kind"] == "premium_paid" and n["plan"] == plan)
        months = {(d.year, d.month) for d in paid}
        y, m = paid[0].year, paid[0].month
        last = (today.year, today.month) if today.day > 6 else \
            ((today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12))
        while (y, m) <= last:
            if (y, m) not in months:
                out.append(issue("ACT", "PREMIUM_MISSING", plan, f"{y}-{m:02d}",
                                 f"No premium payment confirmation for {y}-{m:02d}",
                                 "Check the bank draft and the plan's billing page — a missed premium can lapse the policy"))
            y, m = (y, m + 1) if m < 12 else (y + 1, 1)

    for name, plan in plans.items():
        if (plan.get("notices") or {}).get("eob") == "unknown":
            out.append(issue("WATCH", "FEED_MISSING", name, "",
                             "This plan's EOB notices do not reach the watched mailbox",
                             "Turn on email EOB notices in the portal to an address this sync reads"))
    return out


def check_claims(claims, plans, today, th):
    out = []
    for c in claims:
        if c.get("resolution", "").strip():
            continue
        plan, ref = c["plan"], c["claim_id"]
        who = f'{c["patient"]} · {c["provider"]} · {c["service_date"]}'
        status = c["status"].strip().lower()
        paid, resp = money(c["plan_paid"]), money(c["patient_resp"])
        remarks = c.get("remarks", "")
        appeal_by = day(c.get("appeal_by"))
        clock = f"appeal by {appeal_by}" if appeal_by else ""

        members = (plans.get(plan) or {}).get("members") or []
        if members and c["patient"] not in members:
            out.append(issue("ACT", "NOT_MEMBER", plan, ref, f"{who}: patient is not a listed member",
                             "Confirm who is on this plan before paying anything"))
        if status == "denied" or (status in ("paid", "processed", "partial") and paid == 0 and resp > 0):
            out.append(issue("ACT", "DENIED", plan, ref, f"{who}: plan paid $0, you owe ${resp:,.2f} ({remarks or 'no remark'})",
                             "Read the denial reason; fix and resubmit through the provider, or appeal", clock))
        if COB_RE.search(remarks):
            out.append(issue("ACT", "COB", plan, ref, f"{who}: coordination of benefits — {remarks}",
                             "Answer the other-coverage questionnaire; tell the provider which plan is primary", clock))
        elif INFO_RE.search(remarks):
            out.append(issue("ACT", "INFO_REQUESTED", plan, ref, f"{who}: carrier wants more — {remarks}",
                             "Send what is asked (or get the provider to) before it denies", clock))
        svc = day(c["service_date"])
        if status == "pending" and svc and (today - svc).days > th["pending_days"]:
            out.append(issue("ACT", "PENDING_AGED", plan, ref, f"{who}: pending {(today - svc).days} days",
                             "Call member services and ask what is holding it"))
        billed_to_us = money(c.get("provider_billed"))
        if billed_to_us and billed_to_us > resp + 0.01:
            out.append(issue("ACT", "OVERBILLED", plan, ref,
                             f"{who}: provider billed ${billed_to_us:,.2f}, EOB says you owe ${resp:,.2f}",
                             "Pay only the EOB amount; send the provider the EOB and ask for a corrected bill"))
        if resp >= th["high_patient_resp"] and status != "deductible":
            out.append(issue("WATCH", "HIGH_PATIENT_RESP", plan, ref, f"{who}: you owe ${resp:,.2f}",
                             "Check the EOB line by line before paying"))
        if appeal_by and status in ("denied", "partial") and 0 <= (appeal_by - today).days <= th["appeal_warn_days"]:
            out.append(issue("ACT", "APPEAL_CLOCK", plan, ref, f"{who}: appeal window closes in {(appeal_by - today).days} days",
                             "Decide now whether to appeal", clock))

    seen: dict[tuple, str] = {}
    for c in claims:
        key = (c["plan"], c["patient"], c["provider"], c["service_date"], c["billed"])
        if key in seen and seen[key] != c["claim_id"]:
            out.append(issue("WATCH", "DUPLICATE", c["plan"], f'{seen[key]} / {c["claim_id"]}',
                             f'Two claims for {c["patient"]} · {c["provider"]} · {c["service_date"]} · ${money(c["billed"]):,.2f}',
                             "Make sure only one was paid and you were billed once"))
        seen.setdefault(key, c["claim_id"])

    # Roll-ups: one line per provider / plan, not one per claim.
    this_year = [c for c in claims if (day(c["service_date"]) or today).year == today.year]
    oon: dict[tuple, list] = {}
    for c in this_year:
        if c.get("network", "").strip().lower() in ("out", "oon", "out-of-network"):
            oon.setdefault((c["plan"], c["provider"]), []).append(c)
    for (plan, prov), cs in sorted(oon.items()):
        owed = sum(money(c["patient_resp"]) for c in cs)
        out.append(issue("INFO", "OUT_OF_NETWORK", plan, prov,
                         f"{prov}: {len(cs)} out-of-network claim(s) in {today.year}, ${owed:,.2f} ours, no PPO discount",
                         "An in-network provider would cut the eligible charge; pay no more than the EOB says"))
    unreimbursed: dict[str, list] = {}
    for c in this_year:
        if money(c["patient_resp"]) > 0 and not c.get("reimbursed", "").strip():
            unreimbursed.setdefault(c["plan"], []).append(c)
    for plan, cs in sorted(unreimbursed.items()):
        total = sum(money(c["patient_resp"]) for c in cs)
        out.append(issue("INFO", "REIMBURSE", plan, f"{len(cs)} claims",
                         f"${total:,.2f} out of pocket on {len(cs)} {today.year} claim(s) not marked reimbursed",
                         "Claim them from the HSA / limited-purpose FSA; the EOB is the receipt"))
    no_pdf: dict[str, list] = {}
    for c in this_year:
        owed = money(c["patient_resp"]) > 0 or c["status"].strip().lower() == "denied"
        if owed and not c.get("eob_drive_id", "").strip():
            no_pdf.setdefault(c["plan"], []).append(c)
    for plan, cs in sorted(no_pdf.items()):
        out.append(issue("INFO", "EOB_PDF_MISSING", plan, f"{len(cs)} claims",
                         f"{len(cs)} {today.year} EOB(s) we owe on (or denied) have no saved PDF",
                         "Save them (SKILL.md step 6) and record eob_drive_id"))
    return out


def check_cleanings(claims, plans, today):
    """Dental cleanings are limited per calendar year; the third one is denied."""
    out = []
    for name, plan in plans.items():
        limit = plan.get("cleanings_per_year")
        if not limit:
            continue
        mine = [c for c in claims if c["plan"] == name and c.get("cleaning")]
        for member in plan.get("members") or []:
            used = sum(1 for c in mine if c["patient"] == member and c["cleaning"] == "covered"
                       and day(c["service_date"]).year == today.year)
            past = sorted(day(c["service_date"]).year for c in mine if c["patient"] == member
                          and c["cleaning"] == "denied" and "CARC 119" in c.get("remarks", ""))
            if used >= limit:
                sev = "ACT" if past else ("WATCH" if today.month >= 9 else "INFO")
                hist = f"; a third cleaning was denied in {', '.join(map(str, past))}" if past else ""
                out.append(issue(sev, "CLEANINGS_USED", name, member,
                                 f"{member}: both {today.year} cleanings used{hist}",
                                 f"Any cleaning before Dec 31 will be denied; book the next one on or after Jan 1, {today.year + 1}"))
            elif today.month >= 10:
                out.append(issue("INFO", "CLEANING_LEFT", name, member,
                                 f"{member}: {limit - used} covered cleaning(s) left in {today.year}",
                                 "Book before Dec 31 to use it"))
    return out


def check_expected(expected, claims, today):
    out = []
    for e in expected or []:
        names = [n.lower() for n in e.get("provider_match") or [e["provider"].split(" (")[0]]]
        hit = [c for c in claims if c["plan"] == e["plan"] and
               any(n in c["provider"].lower() for n in names)]
        if hit:
            continue
        due = e["expect_by"] if isinstance(e["expect_by"], dt.date) else day(str(e["expect_by"]))
        late = due and today > due
        out.append(issue("ACT" if late else "INFO", "EXPECTED_MISSING", e["plan"], e["id"],
                         f'No claim yet from {e["provider"]}: {e["what"]}',
                         "Ask the provider whether and when it was filed" if late else "Watch for it",
                         f"expected by {due}"))
    return out


def check_accumulators(rows, today, th):
    out, latest = [], {}
    for r in rows:
        k = (r["plan"], r["member"])
        if k not in latest or r["as_of"] > latest[k]["as_of"]:
            latest[k] = r
    for (plan, member), r in latest.items():
        for met, lim, label in (("deductible_met", "deductible_limit", "deductible"),
                                ("oop_met", "oop_limit", "out-of-pocket max"),
                                ("annual_max_used", "annual_max", "annual maximum")):
            m, l = money(r.get(met)), money(r.get(lim))
            if label == "deductible" and l < 500:
                continue  # a $50 dental deductible met in January changes no decision
            if l and m / l >= th["accumulator_warn"]:
                yearend = today.month >= 10
                out.append(issue("WATCH" if yearend else "INFO", "ACCUMULATOR", plan, member,
                                 f"{member}: {label} ${m:,.0f} of ${l:,.0f} as of {r['as_of']}",
                                 "Book planned care before Dec 31, while it costs less" if label != "annual maximum"
                                 else "Dental max nearly used — push non-urgent work to January"))
    return out


def run(store: pathlib.Path, today: dt.date) -> list[dict]:
    cfg = yaml.safe_load((store / "plans.yaml").read_text(encoding="utf-8"))
    plans, th = cfg.get("plans", {}), cfg.get("thresholds", {})
    claims = read_csv(store / "claims.csv")
    issues = (check_notices(read_csv(store / "notices.csv"), plans, today, th)
              + check_claims(claims, plans, today, th)
              + check_cleanings(claims, plans, today)
              + check_expected(cfg.get("expected_claims"), claims, today)
              + check_accumulators(read_csv(store / "accumulators.csv"), today, th))
    return sorted(issues, key=lambda i: (RANK[i["sev"]], i["plan"], i["code"]))


def render(issues: list[dict], today: dt.date) -> str:
    acts = sum(i["sev"] == "ACT" for i in issues)
    lines = [START, f"_Checked {today} by `skills/eob-sync/scripts/eob_check.py` — "
                    f"{acts} need action, {len(issues) - acts} to watch._", ""]
    if not issues:
        lines.append("Nothing open.")
    else:
        lines += ["| | Plan | Issue | What | Next action | Clock |", "| :-- | :-- | :-- | :-- | :-- | :-- |"]
        mark = {"ACT": "❗", "WATCH": "⚠️", "INFO": "ℹ️"}
        for i in issues:
            lines.append(f'| {mark[i["sev"]]} | {i["plan"]} | {i["code"]} | {i["what"]} | {i["action"]} | {i["clock"]} |')
    lines.append(END)
    return "\n".join(lines)


def write_index(store: pathlib.Path, block: str) -> None:
    sys.path[:0] = [str(REPO / "scripts"), str(REPO / "tools")]
    try:                                     # mojibake_guard (tools/ in the public repo) refuses damaged UTF-8
        from mojibake_guard import assert_clean, write_text_utf8
    except ImportError:
        def assert_clean(text, what=""):
            if "\ufffd" in text:
                raise SystemExit(f"{what}: contains U+FFFD")

        def write_text_utf8(path, text):
            path.write_text(text, encoding="utf-8")
    path = store / "index.md"
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"{path}: issue markers missing")
    head, rest = text.split(START, 1)
    new = head + block + rest.split(END, 1)[1]
    assert_clean(block, what="issues block")
    write_text_utf8(path, new)


def mark_reviewed(store: pathlib.Path, plan: str, through: dt.date) -> int:
    path = store / "notices.csv"
    rows = read_csv(path)
    n = 0
    for r in rows:
        if r["plan"] == plan and not r["reviewed"] and day(r["date"]) <= through:
            r["reviewed"] = through.isoformat()
            n += 1
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=pathlib.Path, default=None,
                    help="the EOB store (default: config/household.yaml paths.store)")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--write", action="store_true", help="re-render the issues block in index.md")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mark-reviewed", nargs=2, metavar=("PLAN", "DATE"),
                    help="stamp PLAN's notices dated on or before DATE as read")
    a = ap.parse_args()
    a.dir = a.dir or default_store()
    if not a.dir:
        ap.error("no EOB store: pass --dir, or copy config/household.example.yaml to config/household.yaml "
                 "and set paths.store")

    if a.mark_reviewed:
        n = mark_reviewed(a.dir, a.mark_reviewed[0], dt.date.fromisoformat(a.mark_reviewed[1]))
        print(f"marked {n} notice(s) reviewed")
        return 0

    issues = run(a.dir, a.today)
    if a.json:
        print(json.dumps(issues, indent=2))
    else:
        for i in issues:
            print(f'{i["sev"]:5} {i["code"]:17} {i["plan"]:8} {i["ref"]:16} {i["what"]}'
                  + (f' [{i["clock"]}]' if i["clock"] else ""))
        print(f"VERDICT {'ACTION NEEDED' if any(i['sev'] == 'ACT' for i in issues) else 'OK'} "
              f"({len(issues)} issue(s))")
    if a.write:
        write_index(a.dir, render(issues, a.today))
    return 1 if any(i["sev"] == "ACT" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
