#!/usr/bin/env python3
"""Plan and record HSA / limited-purpose FSA reimbursements from the household's EOBs.

Reads the store (config/household.yaml `paths.store`, relative to the repository root; or --store):
  claims.csv          one row per claim (skills/eob-sync); `reimbursed` is set here
  accounts.yaml       HSA and FSA facts, FSA elections and deadlines, name → project slug
  reimbursements.csv  the register: one row per claim and account (created on first `record`). A claim can be
                      split — e.g. $55 of it from the FSA, the rest from the HSA — and the plan keeps what is left.
each person's <projects>/<slug>/project.yaml (`health.hsa_eligible`), the Beancount files in <ledger> (optional)
and the administrator's card activity in <admin_store>/activity.csv (optional; skills/hsa-fsa-reimburse/scripts/alegeus_sync.py).

  reimburse.py plan [--year 2026]          what can be reimbursed, from which account, and what is held
  reimburse.py status                      register totals plus the plan's buckets
  reimburse.py packet --year 2026 --account HSA [--out FILE]
                                           a submission packet (EOB Drive links) for claims ready to file
  reimburse.py record <claim_id> --as HSA|FSA|card|n/a [--status submitted|paid|denied]
                                           [--date YYYY-MM-DD] [--amount N] [--note TEXT]
                                           --amount below the claim's patient share records part of it; the
                                           remainder stays in the plan (claims.csv `reimbursed` = partial)
  reimburse.py match-card [--year 2026] [--record]
                                           claims the HSA or FSA card already paid, from the administrator's
                                           activity (<admin_store>/activity.csv);
                                           --record records each unambiguous match `--as card`

Try it on the fictional sample:
  reimburse.py --store skills/hsa-fsa-reimburse/examples/store --projects skills/hsa-fsa-reimburse/examples/projects \
               --today 2026-11-08 plan --year 2026

Read-only except `record` (writes reimbursements.csv and claims.csv `reimbursed`) and `packet --out`.
It never submits anything; the account holder files. Figures it prints are sums of EOB rows.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import re
import sys

import yaml

SKILL = pathlib.Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]
CONFIG = SKILL / "config" / "household.yaml"
REGISTER_FIELDS = ["claim_id", "plan", "patient", "service_date", "amount", "account", "status",
                   "date", "note"]
LIVE = {"planned", "submitted", "paid", "paid-by-card"}
LEDGER_WINDOW_DAYS = 240
CARD_EARLY_DAYS = 7                  # a copay is often charged at the desk, a few days before the claim's date
ADMIN_BEAN = "alegeus_hsa_fsa.bean"  # account-paid spending (alegeus_sync.py ledger): not out-of-pocket evidence
CODES = {"hsa": "HSA", "fsa": "FSA"}  # the administrator's account type codes (config administrator.codes)
CARD_TYPES = {"CARD TRANSACTION", "HSA BILLPAY"}
NAME_NOISE = {"dmd", "dds", "md", "pc", "llc", "inc", "the", "of", "and", "dr", "assoc", "center", "health"}

TXN_RE = re.compile(r'^(\d{4}-\d{2}-\d{2}) [*!] "([^"]*)"(?: "([^"]*)")?')
POSTING_RE = re.compile(r"^\s+(Expenses:Healthcare[\w:-]*)\s+(-?[\d,]+\.\d+) USD")


def load_config() -> dict:
    """The household's config/household.yaml (private; copy household.example.yaml to start)."""
    return (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}) if CONFIG.exists() else {}


def money(v) -> float:
    v = str(v or "").replace("$", "").replace(",", "").strip()
    return round(float(v), 2) if v else 0.0


def day(v) -> dt.date | None:
    if isinstance(v, dt.date):
        return v
    v = str(v or "").strip()
    return dt.date.fromisoformat(v) if v else None


def read_csv(path: pathlib.Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def write_csv(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def load_eligibility(people: dict, projects: pathlib.Path) -> dict[str, dict]:
    """Patient name → {status, basis}. A missing project or field is `unknown`."""
    out = {}
    for name, slug in people.items():
        path = projects / slug / "project.yaml"
        elig = {}
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            elig = ((data.get("health") or {}).get("hsa_eligible")) or {}
        status = elig.get("status")
        if isinstance(status, bool):          # YAML reads a bare yes / no as a boolean
            status = "yes" if status else "no"
        out[name] = {"status": str(status or "unknown").lower(),
                     "basis": str(elig.get("basis") or "no health project")}
    return out


def load_ledger(ledger: pathlib.Path | None, exclude: str = ADMIN_BEAN) -> list[tuple[dt.date, str, float]]:
    """(date, payee, amount) for every Expenses:Healthcare posting in the Beancount files."""
    out = []
    if not ledger or not ledger.exists():
        return out
    for path in sorted(ledger.glob("*.bean")):
        if path.name == exclude:
            continue
        head = None
        for line in path.read_text(encoding="utf-8").splitlines():
            m = TXN_RE.match(line)
            if m:
                head = (dt.date.fromisoformat(m.group(1)), m.group(2))
                continue
            p = POSTING_RE.match(line)
            if p and head:
                out.append((head[0], head[1], abs(money(p.group(2)))))
    return out


def ledger_candidates(claim: dict, ledger: list) -> list[tuple[dt.date, str, float]]:
    amt, start = money(claim["patient_resp"]), day(claim["service_date"])
    if not start or not amt:
        return []
    end = start + dt.timedelta(days=LEDGER_WINDOW_DAYS)
    return [t for t in ledger if start <= t[0] <= end and t[2] == amt]


def load_card(admin_store: pathlib.Path, codes: dict = CODES) -> list[dict]:
    """HSA / FSA card and bill-pay payments that moved money, from the administrator's activity store."""
    _, rows = read_csv(admin_store / "activity.csv")
    out = []
    for r in rows:
        if r["type"].upper() not in CARD_TYPES or r["acct"] not in (codes["hsa"], codes["fsa"]):
            continue
        if r["status"] in ("Denied", "Partially Approved"):
            continue
        amount = money(r["paid"]) or money(r["balance_due"])
        if amount:
            out.append({"date": day(r["date"]), "merchant": r["merchant"], "amount": amount,
                        "acct": "HSA" if r["acct"] == codes["hsa"] else "FSA", "id": r["id"],
                        "balance_due": money(r["balance_due"])})
    return out


def name_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in NAME_NOISE}


def card_candidates(claim: dict, cards: list[dict]) -> list[dict]:
    """Card payments of exactly the claim's patient responsibility near its service date, name matches first."""
    amt, start = money(claim["patient_resp"]), day(claim["service_date"])
    if not start or not amt:
        return []
    lo, hi = start - dt.timedelta(days=CARD_EARLY_DAYS), start + dt.timedelta(days=LEDGER_WINDOW_DAYS)
    words = name_words(claim.get("provider", ""))
    hits = [dict(c, named=bool(words & name_words(c["merchant"]))) for c in cards
            if c["amount"] == amt and lo <= c["date"] <= hi]
    return sorted(hits, key=lambda c: (not c["named"], abs((c["date"] - start).days)))


def card_matches(claims, register, cards, year):
    """Pair open claims with card payments. Sure: the payment is no other claim's candidate, and it is the claim's
    only candidate or its only name match. Returns (sure, unsure)."""
    handled = {r["claim_id"] for r in register if r["status"] in LIVE}
    open_claims = [c for c in claims if (c["service_date"] or "")[:4] == str(year) and money(c["patient_resp"]) > 0
                   and not (c.get("reimbursed") or "").strip() and c["claim_id"] not in handled]
    open_claims.sort(key=lambda c: (c["service_date"], c["claim_id"]))
    hits = {c["claim_id"]: card_candidates(c, cards) for c in open_claims}
    claimants: dict[str, int] = {}
    for hs in hits.values():
        for h in hs:
            claimants[h["id"]] = claimants.get(h["id"], 0) + 1
    used, sure, unsure = set(), [], []
    for c in open_claims:
        hs = [h for h in hits[c["claim_id"]] if h["id"] not in used]
        named = [h for h in hs if h["named"]]
        pick = None
        if len(named) == 1:
            pick = named[0]
        elif len(hs) == 1:
            pick = hs[0]
        if pick and claimants[pick["id"]] == 1:
            used.add(pick["id"])
            sure.append((c, pick))
        elif hs:
            unsure.append((c, hs))
    return sure, unsure


def is_ortho(claim: dict, words: list[str], plans=("dental",)) -> bool:
    text = " ".join([claim.get("provider", ""), claim.get("notes", "")]).lower()
    return claim.get("plan") in plans and any(w.lower() in text for w in words)


def fsa_room(accounts: dict, register: list[dict]) -> dict[int, float]:
    years = ((accounts.get("fsa") or {}).get("years")) or {}
    room = {}
    for y, cfg in years.items():
        used = sum(money(r["amount"]) for r in register
                   if r["account"] == "FSA" and r["status"] in LIVE and (r["service_date"] or "")[:4] == str(y))
        room[int(y)] = round(money(cfg.get("election")) - money(cfg.get("used_outside_register")) - used, 2)
    return room


def covered(register) -> dict[str, float]:
    """Amount already reimbursed (or in flight) per claim, from live register rows."""
    out: dict[str, float] = {}
    for r in register:
        if r["status"] in LIVE:
            out[r["claim_id"]] = round(out.get(r["claim_id"], 0.0) + money(r["amount"]), 2)
    return out


def plan(claims, accounts, register, eligibility, ledger, year, today, cards=(), ortho_label="orthodontist's invoices"):
    """Bucket every unreimbursed out-of-pocket claim of `year` — or the unreimbursed rest of a split one.
    Pure; returns a dict of lists."""
    done = covered(register)
    room = fsa_room(accounts, register)
    years = ((accounts.get("fsa") or {}).get("years")) or {}
    fsa_plans = set(accounts.get("fsa_eligible_plans") or [])
    ortho_words = accounts.get("ortho_match") or []
    ortho_plans = accounts.get("ortho_plans") or ["dental"]
    buckets = {k: [] for k in ("FSA", "HSA", "ortho", "held_eligibility", "held_no_pdf")}
    for c in sorted(claims, key=lambda c: (c["service_date"], c["claim_id"])):
        if (c["service_date"] or "")[:4] != str(year) or money(c["patient_resp"]) <= 0:
            continue
        part = done.get(c["claim_id"], 0.0)
        left = round(money(c["patient_resp"]) - part, 2)
        if left <= 0 or ((c.get("reimbursed") or "").strip() and c["claim_id"] not in done):
            continue                  # fully covered, or marked by hand with no register row
        row = dict(c, amount=left, why="", ledger=ledger_candidates(c, ledger),
                   card=card_candidates(c, list(cards)) if not part else [],
                   already=part)
        elig = eligibility.get(c["patient"], {"status": "unknown", "basis": "patient not in accounts.yaml people"})
        if is_ortho(c, ortho_words, ortho_plans):
            row["why"] = f"orthodontic — claim the {ortho_label} actually paid, not the EOB"
            buckets["ortho"].append(row)
        elif elig["status"] != "yes":
            row["why"] = f"HSA eligibility {elig['status']}: {elig['basis']}"
            buckets["held_eligibility"].append(row)
        elif not (c.get("eob_drive_id") or "").strip():
            row["why"] = "no saved EOB PDF yet (eob-sync step 6)"
            buckets["held_no_pdf"].append(row)
        else:
            cfg = years.get(int(year)) or years.get(str(year)) or {}
            deadline = day(cfg.get("claim_deadline"))
            if (c["plan"] in fsa_plans and room.get(int(year), 0) >= row["amount"]
                    and deadline and today <= deadline):
                room[int(year)] = round(room[int(year)] - row["amount"], 2)
                row["why"] = f"limited-purpose FSA {year} (file by {deadline})"
                buckets["FSA"].append(row)
            else:
                row["why"] = "HSA" + ("" if c["plan"] not in fsa_plans else f" (FSA {year} has no room)")
                buckets["HSA"].append(row)
        if part:
            row["why"] += f" — rest of the claim; ${part:,.2f} of ${money(c['patient_resp']):,.2f} already reimbursed"
    return {"buckets": buckets, "fsa_room_left": room}


def total(rows) -> float:
    return round(sum(r["amount"] for r in rows), 2)


def print_plan(result, year, policy, detail=False, ortho_label="orthodontist's invoices", ask="ask the household") -> None:
    b = result["buckets"]
    print(f"Reimbursement plan — {year} claims · HSA policy: {policy or f'NOT SET ({ask})'}")
    for key, label in (("HSA", "Ready — HSA"), ("FSA", "Ready — limited-purpose FSA"),
                       ("ortho", f"Orthodontic — use the {ortho_label}"),
                       ("held_eligibility", "Held — HSA eligibility not settled"),
                       ("held_no_pdf", "Held — no EOB PDF")):
        rows = b[key]
        print(f"\n{label}: {len(rows)} claim(s), ${total(rows):,.2f}")
        if key in ("HSA", "FSA") or detail:
            for r in rows:
                if r["card"]:
                    k = r["card"][0]
                    hint = f"{k['acct']} card {k['date']} {k['merchant'][:22]}" + ("" if k["named"] else " (name differs)")
                elif r.get("already"):
                    hint = f"rest after ${r['already']:,.2f} already reimbursed"
                else:
                    hint = f"ledger: {len(r['ledger'])} candidate(s)" if r["ledger"] else "ledger: none"
                print(f"  {r['service_date']}  {r['patient']:<11} {r['provider'][:30]:<30} ${r['amount']:>9,.2f}"
                      f"  {r['plan']:<7} {r['claim_id']} · {hint}")
            continue
        groups = {}
        for r in rows:
            g = groups.setdefault(r["patient"], {"n": 0, "rows": [], "why": r["why"]})
            g["n"] += 1
            g["rows"].append(r)
        for patient, g in sorted(groups.items()):
            print(f"  {patient:<11} {g['n']:>3} claim(s)  ${total(g['rows']):>9,.2f}  — {g['why']}")
    left = ", ".join(f"{y}: ${v:,.2f}" for y, v in sorted(result["fsa_room_left"].items()))
    print(f"\nFSA room left after this plan: {left}")
    print("A card hint means the HSA or FSA card already paid it — nothing to reimburse: `match-card --record`. "
          "'ledger: none' with no card hint means no payment was found anywhere. `plan --detail` lists every claim.")


def hsa_cash(admin_store: pathlib.Path, codes: dict = CODES) -> float | None:
    """The HSA's available cash at the latest administrator capture (<admin_store>/accounts.csv), if there is one."""
    _, rows = read_csv(admin_store / "accounts.csv")
    rows = [r for r in rows if r["acct"] == codes["hsa"]]
    return money(max(rows, key=lambda r: r["as_of"])["available"]) if rows else None


def cmd_packet(result, year, account, out, cash=None, holder="The account holder",
               portal="the administrator's portal", admin="administrator", link_template=None) -> str:
    """link_template (config pdfs.link_template) turns eob_drive_id into a link, e.g. a document store's
    "https://<host>/file/{id}/view"; without one the id is printed as is."""
    rows = [r for r in result["buckets"][account] if not r.get("card")]
    held = [r for r in result["buckets"][account] if r.get("card")]
    lines = [f"# {account} reimbursement packet — {year} claims", "",
             f"Prepared by skills/hsa-fsa-reimburse on {dt.date.today().isoformat()}. "
             f"Each EOB is the receipt; {holder} files these in {portal}. Nothing here has been submitted.", ""]
    if cash is not None and account == "HSA":
        lines += [f"HSA cash available at the last {admin} read: **${cash:,.2f}** (the rest is invested). File oldest "
                  "first; the line marks where the cash runs out. Claims past it wait for payroll deposits or a "
                  "sale of investments — there is no deadline [rule:hsa-no-annual-withdrawal].", ""]
    lines += ["| # | Service date | Patient | Provider | Plan | Claim | Amount | Running | EOB |",
              "| ---: | :--- | :--- | :--- | :--- | :--- | ---: | ---: | :--- |"]
    run, marked = 0.0, False
    for i, r in enumerate(rows, 1):
        run = round(run + r["amount"], 2)
        if cash is not None and account == "HSA" and run > cash and not marked:
            lines.append(f"| | | **— cash available (${cash:,.2f}) runs out here —** | | | | | | |")
            marked = True
        link = f"[PDF]({link_template.format(id=r['eob_drive_id'])})" if link_template else r["eob_drive_id"]
        lines.append(f"| {i} | {r['service_date']} | {r['patient']} | {r['provider']} | {r['plan']} | "
                     f"{r['claim_id']} | ${r['amount']:,.2f} | ${run:,.2f} | {link} |")
    split = [r for r in rows if r.get("already")]
    lines += ["", f"**{len(rows)} claim(s), ${total(rows):,.2f}** — sum of EOB patient responsibility, less any part "
              "already reimbursed [script:reimburse]. Only amounts actually paid out of pocket may be reimbursed."]
    if split:
        lines += [""] + [f"- {r['claim_id']}: only ${r['amount']:,.2f} — ${r['already']:,.2f} of it was already "
                         "reimbursed; file only this amount." for r in split]
    if held:
        lines += ["", f"**Held — {len(held)} claim(s), ${total(held):,.2f}.** A card charge of the same amount near "
                  "the visit may have paid one of these; settle by hand (`match-card`) before filing them.", "",
                  "| Service date | Patient | Provider | Claim | Amount | Possible card charge |",
                  "| :--- | :--- | :--- | :--- | ---: | :--- |"]
        for r in held:
            k = r["card"][0]
            lines.append(f"| {r['service_date']} | {r['patient']} | {r['provider']} | {r['claim_id']} | "
                         f"${r['amount']:,.2f} | {k['acct']} {k['date']} {k['merchant']} |")
    lines += ["", "After filing: `reimburse.py record <claim_id> --as " + account + " --status submitted` "
              "(a split claim records its unreimbursed rest by default)."]
    text = "\n".join(lines) + "\n"
    if out:
        pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(out).write_text(text, encoding="utf-8")
    return text


def cmd_record(store, claim_id, account, status, date, amount, note) -> str:
    cfields, claims = read_csv(store / "claims.csv")
    match = [c for c in claims if c["claim_id"] == claim_id]
    if not match:
        raise SystemExit(f"claim {claim_id} not in claims.csv")
    c = match[-1]
    rpath = store / "reimbursements.csv"
    rfields, register = read_csv(rpath)
    rfields = rfields or REGISTER_FIELDS
    status = "paid-by-card" if account == "card" else ("n/a" if account == "n/a" else status)
    acct = "HSA" if account == "card" else account
    share = money(c["patient_resp"])
    # One row per claim and account, so a claim split between the FSA and the HSA keeps both parts.
    others = [r for r in register if r["claim_id"] == claim_id and r["account"] != acct]
    others_live = round(sum(money(r["amount"]) for r in others if r["status"] in LIVE), 2)
    keep_others = account != "n/a"
    if amount is None:
        if others_live < share:
            amount = round(share - others_live, 2)       # the rest of a split claim
        else:
            amount, keep_others = share, False         # the whole claim moves to this account
    elif status in LIVE and money(amount) + others_live > share + 0.005:
        raise SystemExit(f"claim {claim_id}: ${money(amount):,.2f} plus ${others_live:,.2f} already recorded "
                         f"exceeds its patient share ${share:,.2f}")
    row = {"claim_id": claim_id, "plan": c["plan"], "patient": c["patient"],
           "service_date": c["service_date"], "amount": f"{money(amount):.2f}",
           "account": acct, "status": status, "date": date, "note": note or ""}
    register = [r for r in register
                if r["claim_id"] != claim_id or (keep_others and r["account"] != acct)] + [row]
    write_csv(rpath, rfields, register)
    rows = [r for r in register if r["claim_id"] == claim_id and r["status"] in LIVE | {"n/a"}]
    paid = round(sum(money(r["amount"]) for r in rows if r["status"] in LIVE), 2)
    if any(r["status"] == "n/a" for r in rows):
        mark = "n/a"
    elif not rows:
        mark = ""
    elif paid < money(c["patient_resp"]):
        mark = "partial"
    else:
        mark = "+".join(sorted({r["account"] for r in rows}))
    for cl in claims:
        if cl["claim_id"] == claim_id:
            cl["reimbursed"] = mark
    write_csv(store / "claims.csv", cfields, claims)
    return f"recorded {claim_id}: {row['account']} {status} ${row['amount']} on {date}"


def load_all(store, projects, ledger_dir, admin_store=None, codes=CODES, exclude=ADMIN_BEAN):
    accounts = yaml.safe_load((store / "accounts.yaml").read_text(encoding="utf-8")) or {}
    _, claims = read_csv(store / "claims.csv")
    _, register = read_csv(store / "reimbursements.csv")
    eligibility = load_eligibility(accounts.get("people") or {}, projects)
    return (accounts, claims, register, eligibility, load_ledger(ledger_dir, exclude),
            load_card(admin_store or store / "administrator", codes))


def main(argv=None) -> int:
    cfg = load_config()
    paths, adm, hh = (cfg.get(k) or {} for k in ("paths", "administrator", "household"))
    at = lambda k: REPO / paths[k] if paths.get(k) else None  # noqa: E731
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # With --store given, the other paths default to the store's own layout, never the household config.
    ap.add_argument("--store", type=pathlib.Path, help="default: config paths.store")
    ap.add_argument("--projects", type=pathlib.Path, help="default: config paths.projects, else <store>/projects")
    ap.add_argument("--ledger", type=pathlib.Path, help="default: config paths.ledger, else none")
    ap.add_argument("--admin-store", type=pathlib.Path,
                    help="default: config paths.admin_store, else <store>/administrator")
    ap.add_argument("--today", type=day, default=dt.date.today())
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--year", type=int); p.add_argument("--detail", action="store_true")
    sub.add_parser("status")
    k = sub.add_parser("packet"); k.add_argument("--year", type=int); k.add_argument("--account", choices=["HSA", "FSA"], required=True)
    k.add_argument("--out")
    r = sub.add_parser("record"); r.add_argument("claim_id"); r.add_argument("--as", dest="account", required=True,
                                                                              choices=["HSA", "FSA", "card", "n/a"])
    r.add_argument("--status", default="submitted", choices=["planned", "submitted", "paid", "denied"])
    r.add_argument("--date", default=dt.date.today().isoformat()); r.add_argument("--amount")
    r.add_argument("--note")
    mc = sub.add_parser("match-card"); mc.add_argument("--year", type=int); mc.add_argument("--record", action="store_true")
    a = ap.parse_args(argv)
    if not a.store:
        a.store, a.projects, a.ledger = at("store"), a.projects or at("projects"), a.ledger or at("ledger")
        a.admin_store = a.admin_store or at("admin_store")
    if not a.store:
        ap.error("no store: pass --store, or copy config/household.example.yaml to config/household.yaml and set paths")
    a.projects = a.projects or a.store / "projects"
    a.admin_store = a.admin_store or a.store / "administrator"
    codes = {**CODES, **{k: v for k, v in (adm.get("codes") or {}).items() if k in CODES}}
    exclude = pathlib.Path(paths["admin_ledger"]).name if paths.get("admin_ledger") else ADMIN_BEAN
    ortho = ((cfg.get("orthodontics") or {}).get("invoices")) or "orthodontist's invoices"
    ask = ((cfg.get("decisions") or {}).get("hsa_policy_question")) or "ask the household"

    if a.cmd == "record":
        print(cmd_record(a.store, a.claim_id, a.account, a.status, a.date, a.amount, a.note))
        return 0
    accounts, claims, register, eligibility, ledger, cards = load_all(a.store, a.projects, a.ledger, a.admin_store,
                                                                      codes, exclude)
    year = getattr(a, "year", None) or a.today.year
    if a.cmd == "match-card":
        sure, unsure = card_matches(claims, register, cards, year)
        print(f"Card-paid {year} claims ({adm.get('short_name') or 'administrator'} activity): {len(sure)} matched, ${sum(money(c['patient_resp']) for c, _ in sure):,.2f}")
        for c, k in sure:
            note = f"{adm.get('short_name') or 'Administrator'} {k['acct']} card {k['date']} {k['merchant']}" + (" — FSA balance due: upload this EOB" if k["balance_due"] else "")
            print(f"  {c['service_date']} {c['patient']:<11} {c['provider'][:28]:<28} ${money(c['patient_resp']):>8,.2f}  {note}")
            if a.record:
                cmd_record(a.store, c["claim_id"], "card", "paid", k["date"].isoformat(), None, note)
        print(f"Ambiguous: {len(unsure)} claim(s) — same amount, no single name match; check by hand")
        for c, hits in unsure:
            opts = "; ".join(f"{h['acct']} {h['date']} {h['merchant'][:20]}" for h in hits[:3])
            print(f"  {c['service_date']} {c['patient']:<11} {c['provider'][:28]:<28} ${money(c['patient_resp']):>8,.2f}  {opts}")
        if a.record:
            print(f"recorded {len(sure)} as card")
        return 0
    result = plan(claims, accounts, register, eligibility, ledger, year, a.today, cards, ortho)
    policy = (accounts.get("hsa") or {}).get("policy")
    if a.cmd == "plan":
        print_plan(result, year, policy, a.detail, ortho, ask)
    elif a.cmd == "packet":
        print(cmd_packet(result, year, a.account, a.out, hsa_cash(a.admin_store, codes),
                         hh.get("account_holder") or "The account holder",
                         adm.get("file_in") or "the administrator's portal", adm.get("short_name") or "administrator",
                         (cfg.get("pdfs") or {}).get("link_template")),
              end="")
    elif a.cmd == "status":
        by = {}
        for row in register:
            key = (row["account"], row["status"], (row["service_date"] or "")[:4])
            n, s = by.get(key, (0, 0.0))
            by[key] = (n + 1, round(s + money(row["amount"]), 2))
        print("Register (reimbursements.csv):" if by else "Register: empty")
        for (acct, st, y), (n, s) in sorted(by.items()):
            print(f"  {y} {acct:<4} {st:<13} {n:>3} claim(s)  ${s:,.2f}")
        b = result["buckets"]
        print(f"Plan {year}: HSA {len(b['HSA'])} ${total(b['HSA']):,.2f} · FSA {len(b['FSA'])} ${total(b['FSA']):,.2f}"
              f" · ortho {len(b['ortho'])} · held (eligibility) {len(b['held_eligibility'])} ${total(b['held_eligibility']):,.2f}"
              f" · held (no PDF) {len(b['held_no_pdf'])} · HSA policy: {policy or 'NOT SET'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
