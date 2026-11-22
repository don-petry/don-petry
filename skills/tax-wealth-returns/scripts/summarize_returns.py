#!/usr/bin/env python3
"""Build the multi-year view of extracted returns (skill: tax-wealth-returns).

Reads <root>/<year>/{federal,<state>}.json and writes:
  - returns/summary.json — {year: {federal: {...}, al: {...}}}, every value copied from the extractions
  - returns/index.md     — the quick-reference table, between <!-- returns:begin --> and <!-- returns:end -->

Derived columns are labeled as such and computed here, deterministically, from extracted values.
A cell reads "—" when the line is blank on the form or was not read, and "n/e" (not extracted) when the
extraction's `summary_notes` records that a null is a known extraction gap, not a blank line.

Usage (from the skill folder): python3 scripts/summarize_returns.py --root <returns_dir>   (config paths.returns_dir)
"""
import argparse
import glob
import json
import os
import re

FED_ROWS = [
    ("Wages", "wages"), ("Taxable interest", "taxable_interest"), ("Ordinary dividends", "ordinary_dividends"),
    ("Qualified dividends", "qualified_dividends"),
    ("Capital gain (loss)", "capital_gain"), ("Schedule 1 income", "other_income_sch1"),
    ("Total income", "total_income"), ("AGI", "agi"), ("Deductions (std or itemized)", "deductions"),
    ("QBI deduction", "qbi_deduction"), ("Taxable income", "taxable_income"), ("Tax", "tax"),
    ("Credits", "nonrefundable_credits"), ("Other taxes (Sch 2)", "other_taxes"), ("Total tax", "total_tax"),
    ("Withholding", "withholding"), ("Total payments", "total_payments"), ("Refund", "refund"),
    ("Amount owed", "amount_owed"), ("Underpayment penalty", "estimated_tax_penalty"),
]
AL_ROWS = [
    ("AL AGI", "agi"), ("AL deductions", "deductions"), ("Federal tax deduction", "federal_tax_deduction"),
    ("AL taxable income", "taxable_income"), ("AL income tax", "income_tax"), ("AL net tax", "net_tax"),
    ("AL total tax", "total_tax"), ("AL payments", "total_payments"), ("AL overpaid", "overpaid"),
    ("AL refund", "refund"), ("AL amount owed", "amount_owed"),
]


def money(v):
    if v is None:
        return "—"
    return ("-$%s" % format(-v, ",.0f")) if v < 0 else ("$%s" % format(v, ",.0f"))


def pct(n, d):
    return "—" if not n or not d else "%.2f%%" % (100.0 * n / d)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="the returns folder (team config paths.returns_dir)")
    args = ap.parse_args(argv)

    data = {}
    for path in sorted(glob.glob(os.path.join(args.root, "*", "*.json"))):
        year, kind = os.path.basename(os.path.dirname(path)), os.path.splitext(os.path.basename(path))[0]
        if not year.isdigit() or kind not in ("federal", "al"):
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        data.setdefault(year, {})[kind] = {
            "summary": d["summary"],
            **({"summary_notes": d["summary_notes"]} if d.get("summary_notes") else {}),
            "checks": [c["status"] for c in d["checks"]],
            "drive_link": d["source"]["drive_link"],
            "extractor_version": d["extractor"]["version"],
        }
    with open(os.path.join(args.root, "summary.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")

    years = sorted(data, reverse=True)
    out = ["| Line | " + " | ".join(years) + " |", "| :--- |" + " ---: |" * len(years)]

    def cell(entry, field):
        v = entry.get("summary", {}).get(field)
        return "n/e" if v is None and field in entry.get("summary_notes", {}) else money(v)

    def row(label, kind, field):
        vals = [cell(data[y].get(kind) or {}, field) for y in years]
        out.append("| %s | %s |" % (label, " | ".join(vals)))

    for label, field in FED_ROWS:
        row(label, "federal", field)
    out.append("| *Derived:* federal total tax ÷ AGI | %s |" % " | ".join(
        pct(data[y].get("federal", {}).get("summary", {}).get("total_tax"),
            data[y].get("federal", {}).get("summary", {}).get("agi")) for y in years))
    for label, field in AL_ROWS:
        row(label, "al", field)
    out.append("| Checks (federal / AL) | %s |" % " | ".join(
        "%s / %s" % (_checks(data[y].get("federal")), _checks(data[y].get("al"))) for y in years))
    out.append("| Source | %s |" % " | ".join(
        "[fed](%s) · [AL](%s)" % ((data[y].get("federal") or {}).get("drive_link"),
                                   (data[y].get("al") or {}).get("drive_link")) for y in years))
    table = "\n".join(out)

    index = os.path.join(args.root, "index.md")
    with open(index, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"<!-- returns:begin -->.*?<!-- returns:end -->",
                  "<!-- returns:begin -->\n" + table + "\n<!-- returns:end -->", text, flags=re.S)
    with open(index, "w", encoding="utf-8") as f:
        f.write(text)
    print(table)


def _checks(entry):
    if not entry:
        return "—"
    c = entry["checks"]
    if "FAIL" in c:
        return "FAIL"
    skipped, gaps = c.count("SKIPPED"), c.count("GAP")
    return ("PASS %d" % c.count("PASS") + (", GAP %d" % gaps if gaps else "")
            + (" (%d skipped)" % skipped if skipped else ""))


if __name__ == "__main__":
    main()
