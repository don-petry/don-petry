#!/usr/bin/env python3
"""Store HSA / health FSA / dependent-care FSA activity from an Alegeus WealthCare portal and build its ledger.

Alegeus runs the consumer portal (`*.wealthcareportal.com`) behind many benefits administrators. Each account
carries a type code (often HSA, FSA, DCA; the HSA's code may be its custodian bank's). `scripts/alegeus-activity.js`
reads the accounts in a signed-in session; this script does the rest. Paths, account codes, ledger account names
and the time zone come from config/household.yaml (see household.example.yaml); flags override.

  alegeus_sync.py merge <capture>  merge a capture (the reader's JSON, or a file holding it) into
                                   <admin_store>/{activity,accounts}.csv
  alegeus_sync.py ledger           regenerate the Beancount file (config paths.admin_ledger)
  alegeus_sync.py status           balances, open plan years, claim deadlines and balance-due items

Read-only toward the portal. Every figure written is a portal figure or a sum of portal rows.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys
from zoneinfo import ZoneInfo

import yaml

SKILL = pathlib.Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]
CONFIG = SKILL / "config" / "household.yaml"

ACTIVITY_FIELDS = ["id", "date", "settled", "acct", "type", "merchant", "mcc", "amount", "paid", "status",
                   "claimant", "svc_start", "svc_end", "provider", "patient", "balance_due", "ineligible",
                   "reason", "claim_id", "receipts", "key", "item", "seq"]
ACCOUNT_FIELDS = ["as_of", "acct", "plan", "start", "end", "election", "deposits", "spent", "available",
                  "total", "balance_due", "portfolio", "rollover_in", "last_claim"]

NO_MONEY = {"Denied", "Partially Approved"}     # nothing left the account
DEFAULT_ACCOUNTS = {
    "hsa_cash": "Assets:HSA:Cash", "hsa_invested": "Assets:HSA:Invested",
    "fsa": "Assets:FSA:Health", "dcfsa": "Assets:FSA:DependentCare",
    "payroll": "Income:Salary:Employer", "employer_seed": "Income:Benefits:HSA-Employer",
    "interest": "Income:Interest", "fees": "Expenses:Financial:BankFees",
    "transfers": "Equity:Transfers", "opening": "Equity:Opening-Balances", "forfeited": "Expenses:Benefits:Forfeited",
    "dental": "Expenses:Healthcare:Dental", "vision": "Expenses:Healthcare:Vision",
    "pharmacy": "Expenses:Healthcare:Pharmacy", "medical": "Expenses:Healthcare:Medical",
    "childcare": "Expenses:Family:ChildCare",
}
# Category words matched against the card's merchant category and name; config ledger.category_hints adds more.
BASE_HINTS = {"dental": r"dentist|orthodont|dental", "vision": r"optic|optomet|eye ?car|vision",
              "pharmacy": r"drug|pharm|grocery|cvs|walgreen", "childcare": r"dependent care"}


class Settings:
    """Household values from config/household.yaml, with generic defaults when it is absent."""

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {}
        h, adm, led, paths = (cfg.get(k) or {} for k in ("household", "administrator", "ledger", "paths"))
        self.holder = h.get("account_holder") or "the account holder"
        self.tz = h.get("timezone") or "UTC"
        codes = {"hsa": "HSA", "fsa": "FSA", "dcfsa": "DCA", **(adm.get("codes") or {})}
        self.hsa, self.fsa, self.dca = codes["hsa"], codes["fsa"], codes["dcfsa"]
        self.acc = {**DEFAULT_ACCOUNTS, **(led.get("accounts") or {})}
        self.asset = {self.hsa: self.acc["hsa_cash"], self.fsa: self.acc["fsa"], self.dca: self.acc["dcfsa"]}
        self.names = {self.hsa: "HSA", self.fsa: "Health FSA", self.dca: "Dependent-care FSA"}
        self.hints = {k: "|".join([v] + [re.escape(w.lower()) for w in (led.get("category_hints") or {}).get(k, [])])
                      for k, v in BASE_HINTS.items()}
        self.payee = adm.get("short_name") or "Administrator"
        self.title = led.get("title") or "HSA, health FSA and dependent-care FSA activity from the Alegeus portal."
        self.fsa_comment = f"  ; {led['fsa_comment']}" if led.get("fsa_comment") else ""
        self.id_key = led.get("id_key") or "alegeus_id"     # Beancount metadata key holding the row id
        self.store = REPO / paths["admin_store"] if paths.get("admin_store") else None
        self.bean = REPO / paths["admin_ledger"] if paths.get("admin_ledger") else None


def load_settings() -> Settings:
    return Settings((yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}) if CONFIG.exists() else {})


DEFAULT = Settings()


def money(v) -> float:
    v = str(v if v is not None else "").replace("$", "").replace(",", "").strip()
    return round(float(v), 2) if v not in ("", "None") else 0.0


def read_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_capture(path: pathlib.Path) -> dict:
    """The reader's JSON, raw or wrapped in an agent's saved tool output ([{type, text}] holding a JSON string)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        text = data[0]["text"].split("\n\n(captured")[0]
        data = json.loads(text)
    if isinstance(data, str):
        data = json.loads(data)
    return data


def with_ids(activity: list[dict]) -> list[dict]:
    """A stable id per row: account, type, the portal's transaction key (or item id), sequence."""
    seen: dict[str, int] = {}
    out = []
    for a in activity:
        base = "|".join([a.get("acct") or "", a.get("type") or "", a.get("key") or a.get("item") or
                         f"{a.get('date')}:{a.get('amount')}", str(a.get("seq") or "")])
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append(dict(a, id=base if n == 0 else f"{base}#{n}"))
    return out


def local_day(stamp: str, tz: str = "UTC") -> str:
    """The reader stamps UTC; the store dates everything in the household's zone (config household.timezone)."""
    t = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return t.astimezone(ZoneInfo(tz)).date().isoformat()


def merge(capture: dict, store: pathlib.Path, st: Settings = DEFAULT) -> tuple[int, int]:
    as_of = local_day(capture["captured"], st.tz)
    fresh = {r["id"]: r for r in with_ids(capture["activity"])}
    rows = {r["id"]: r for r in read_csv(store / "activity.csv")}
    added = sum(1 for k in fresh if k not in rows)
    years = {int(y) for y in capture.get("years") or []}
    # A captured year is authoritative: drop stored rows of that year the portal no longer shows.
    rows = {k: r for k, r in rows.items() if int(r["date"][:4]) not in years}
    rows.update(fresh)
    ordered = sorted(rows.values(), key=lambda r: (r["date"], r["id"]))
    write_csv(store / "activity.csv", ACTIVITY_FIELDS, ordered)
    accts = [r for r in read_csv(store / "accounts.csv") if r["as_of"] != as_of]
    accts += [dict(a, as_of=as_of) for a in capture["accounts"]]
    accts.sort(key=lambda r: (r["as_of"], r["acct"], r["start"]))
    write_csv(store / "accounts.csv", ACCOUNT_FIELDS, accts)
    return len(ordered), added


def category(r: dict, st: Settings = DEFAULT) -> str:
    text = f"{r['mcc']} {r['merchant']}".lower()
    for kind in ("dental", "vision", "pharmacy"):
        if re.search(st.hints[kind], text):
            return st.acc[kind]
    if r["acct"] == st.dca or re.search(st.hints["childcare"], text):
        return st.acc["childcare"]
    return st.acc["medical"]


def posting(r: dict, st: Settings = DEFAULT) -> tuple[float, str] | None:
    """(amount into the account, other leg) for a row that moved money, else None."""
    if r["status"] in NO_MONEY or r["acct"] not in st.asset:
        return None
    t, paid, amount = r["type"].upper(), money(r["paid"]), money(r["amount"])
    if t in ("CARD TRANSACTION", "HSA BILLPAY"):
        if not paid and money(r["balance_due"]):       # "Ineligible Purchase": the card paid; proof is owed
            paid = money(r["balance_due"])
        return (-paid, category(r, st)) if paid else None
    if t in ("MANUAL CLAIM", "MEMBER CLAIM"):
        return (-paid, st.acc["transfers"]) if paid else None       # reimbursed to the holder's bank
    if t == "REFUND":
        return (abs(amount), category(r, st))
    if t == "INVESTMENT ACCOUNT FEE":
        return (-abs(amount), st.acc["fees"])
    if t == "INTEREST PAYMENT":
        return (amount, st.acc["interest"])
    if t == "EMPLOYER SEEDING CONTRIBUTION":
        return (amount, st.acc["employer_seed"])
    if t == "DEPOSIT":
        return (amount, st.acc["payroll"])
    raise ValueError(f"unknown Alegeus activity type {r['type']!r} ({r.get('id', '')})")


def q(s: str) -> str:
    return s.replace("\\", "/").replace('"', "'")


def ledger_text(activity: list[dict], accounts: list[dict], st: Settings = DEFAULT,
                source: str = "the activity store") -> str:
    as_of = max(a["as_of"] for a in accounts)
    snap = [a for a in accounts if a["as_of"] == as_of]
    hsa = next(a for a in snap if a["acct"] == st.hsa)
    moved = [(r, p) for r in activity if (p := posting(r, st))]
    A = st.acc
    first = min(r["date"] for r, _ in moved)
    opened = (dt.date.fromisoformat(first) - dt.timedelta(days=1)).isoformat()
    check = (dt.date.fromisoformat(as_of) + dt.timedelta(days=1)).isoformat()
    out = [
        f";; {st.title}",
        f";; Generated by skills/hsa-fsa-reimburse/scripts/alegeus_sync.py from {source}.",
        ";; Do not edit; re-run `alegeus_sync.py ledger`. Only rows that moved money are here (denials are not).",
        ";;",
        f";; Activity on the portal starts {first}. The HSA cash and invested balances are asserted at the",
        f";; {as_of} capture; the pads before the first row absorb the pre-{first[:4]} balance and the cash swept to",
        ";; investments (Alegeus lists no sweep rows), so the opening equity is a plug, not a contribution history.",
        f";; FSA payouts go to {A['transfers']} (they land in {st.holder}'s bank). FSA balances are not asserted: the",
        ";; health FSA is front-loaded, so deposits minus spending runs negative until the year's payroll catches up.",
        "",
        f"{opened} open {A['hsa_cash']} USD",
        f"{opened} open {A['hsa_invested']} USD",
        f"{opened} open {A['fsa']} USD{st.fsa_comment}",
        f"{opened} open {A['dcfsa']} USD",
        f"{opened} pad {A['hsa_cash']} {A['opening']}",
        f"{opened} pad {A['hsa_invested']} {A['opening']}",
        "",
    ]
    for r, (amt, other) in sorted(moved, key=lambda x: (x[0]["date"], x[0]["id"])):
        tags = " #balance-due" if money(r["balance_due"]) else ""
        payee = q(r["merchant"] or r["type"].title())
        out.append(f'{r["date"]} * "{payee}" "{st.names[r["acct"]]}: {q(r["type"].title())}"{tags}')
        out.append(f'  {st.id_key}: "{q(r["id"])}"')
        if r["svc_start"] and r["svc_start"] != r["date"]:
            out.append(f'  service_date: "{r["svc_start"]}"')
        if r["status"] not in ("Paid", "Approved"):
            out.append(f'  {st.id_key.removesuffix("_id")}_status: "{q(r["status"])}"')
        out.append(f"  {st.asset[r['acct']]:<44}{amt:>12.2f} USD")
        out.append(f"  {other}")
        out.append("")
    # A rollover from a plan year the portal has no activity for arrives without a row of its own.
    for a in snap:
        prior = str(int(a["start"][:4]) - 1)
        if money(a["rollover_in"]) > 0 and not any(r["acct"] == a["acct"] and r["date"][:4] == prior for r, _ in moved):
            out.append(f'{a["start"]} * "{st.payee}" "{st.names[a["acct"]]} {a["start"][:4]}: rollover in from {prior}"')
            out.append(f"  {st.asset[a['acct']]:<44}{money(a['rollover_in']):>12.2f} USD")
            out.append(f"  {A['opening']}")
            out.append("")
    # Plan years whose claim deadline passed with money left: the remainder was forfeited.
    today = dt.date.fromisoformat(as_of)
    for a in snap:
        if a["acct"] in (st.fsa, st.dca) and a["last_claim"] and money(a["available"]) > 0:
            deadline = dt.date.fromisoformat(a["last_claim"])
            if deadline < today:
                d = (deadline + dt.timedelta(days=1)).isoformat()
                out.append(f'{d} * "{st.payee}" "{st.names[a["acct"]]} {a["start"][:4]}: left after the {a["last_claim"]} claim deadline (forfeited)"')
                out.append(f"  {st.asset[a['acct']]:<44}{-money(a['available']):>12.2f} USD")
                out.append(f"  {A['forfeited']}")
                out.append("")
    out.append(f"{check} balance {A['hsa_cash']} {money(hsa['available']):.2f} USD  ; {st.payee} available, {as_of}")
    out.append(f"{check} balance {A['hsa_invested']} {money(hsa['portfolio']):.2f} USD  ; Alegeus portfolio value, {as_of}")
    return "\n".join(out) + "\n"


def status(activity: list[dict], accounts: list[dict], today: dt.date, st: Settings = DEFAULT) -> str:
    as_of = max(a["as_of"] for a in accounts)
    lines = [f"{st.payee} capture {as_of}"]
    for a in [a for a in accounts if a["as_of"] == as_of]:
        if a["acct"] == st.hsa:
            lines.append(f"  HSA: ${money(a['available']):,.2f} cash + ${money(a['portfolio']):,.2f} invested")
            continue
        if a["last_claim"] and dt.date.fromisoformat(a["last_claim"]) < today:
            continue
        lines.append(f"  {st.names.get(a['acct'], a['acct'])} {a['start'][:4]}: election ${money(a['election']):,.2f}, "
                     f"deposited ${money(a['deposits']):,.2f}, spent ${money(a['spent']):,.2f}, "
                     f"available ${money(a['available']):,.2f}, balance due ${money(a['balance_due']):,.2f}, "
                     f"claim by {a['last_claim']}")
    due = [r for r in activity if money(r["balance_due"]) > 0]
    for r in due:
        lines.append(f"  balance due: {r['date']} {r['merchant']} ${money(r['balance_due']):,.2f} ({r['acct']})")
    return "\n".join(lines)


def main(argv=None) -> int:
    st = load_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", type=pathlib.Path, default=st.store, help="default: config paths.admin_store")
    ap.add_argument("--bean", type=pathlib.Path, default=st.bean, help="default: config paths.admin_ledger")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge")
    m.add_argument("capture", type=pathlib.Path)
    sub.add_parser("ledger")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if not a.store:
        ap.error("no activity store: pass --store, or set paths.admin_store in config/household.yaml")
    if a.cmd == "merge":
        total, added = merge(load_capture(a.capture), a.store, st)
        print(f"{total} rows in {a.store / 'activity.csv'} ({added} new)")
        return 0
    activity, accounts = read_csv(a.store / "activity.csv"), read_csv(a.store / "accounts.csv")
    if not accounts:
        print("no capture yet — run merge first", file=sys.stderr)
        return 1
    if a.cmd == "ledger":
        if not a.bean:
            ap.error("no ledger file: pass --bean, or set paths.admin_ledger in config/household.yaml")
        try:
            source = a.store.resolve().relative_to(REPO).as_posix() + "/"
        except ValueError:
            source = str(a.store)
        a.bean.write_text(ledger_text(activity, accounts, st, source), encoding="utf-8")
        print(f"wrote {a.bean}")
    else:
        print(status(activity, accounts, a.today, st))
    return 0


if __name__ == "__main__":
    sys.exit(main())
