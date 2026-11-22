#!/usr/bin/env python3
"""Extract a filed tax return PDF into structured JSON (skill: tax-wealth-returns).

Deterministic: every value is read from the PDF's text layer, never typed by a model. Each value keeps
its page and the exact token it came from, so a draft can cite it as [src:return-<year>-<kind>:<line>].

How it reads a form: on IRS and ADOR forms each amount sits in a right-hand column next to (federal:
slightly above) its line number. For every page, the extractor classifies the form from the page header,
then pairs each line-number token with the nearest amount to its right in the same row band.

Usage (from the skill folder, in a venv with pdfplumber — scripts/requirements.txt):
    python scripts/extract_return.py <return.pdf> --year 2025 --kind federal \\
        --drive-id <file id> --link-template "<URL with {id}>" --title "<title>" --out <returns_dir>/2025/federal.json

`--kind` is `federal` or a mapped state return — `al` (Alabama Form 40) is the one mapped today, as the
worked example. `--drive-id` records where the PDF lives; `--link-template` (e.g. your cloud drive's file
URL with `{id}`) turns it into a link. Output is written UTF-8 and also printed.

Re-run the summary and checks on already-extracted JSON (no PDF needed), e.g. after a line-map change:
    python scripts/extract_return.py --recheck <returns_dir>/*/*.json

Exit status is non-zero when any check FAILs or GAPs, or when no check PASSes (an empty extraction).
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys

VERSION = "0.2.0"

LINE_CODE = re.compile(r"^(\d{1,2}[a-z]?)$")
AMOUNT = re.compile(r"^\(?-?\$?(\d{1,3}(?:,\d{3})*|\d+)(\.\d{0,2})?\)?[•.]?\)?$")
ROW_BAND = 8.0          # points: a value may sit this far above or below its line number
LABEL_BAND = 4.0        # points: a line-number tag and the amount it labels share a row this closely
MAX_GAP = 130.0         # points: the value must start within this distance right of the line number
VALUE_MIN_X_RATIO = 0.65  # values live in the right part of the page
# Multi-column schedules (one column per property or asset) start their value columns further left.
WIDE_FORMS = {"schE": 0.40, "f8949": 0.40, "f4562": 0.40}
# Pages with a middle amount column. Form 1040 page 1 prints lines 2a, 3a, 4a, 5a and 6a (tax-exempt
# interest, qualified dividends, gross IRA/pension/social security) in boxes left of 0.65 of the width.
PAGE_COLUMN_RATIO = {("1040", "p1"): 0.35}
VERSION_NOTE = ("0.2.0: 1040 p1 value column at 0.35 (middle 'a' boxes); line-number tags excluded as amounts; "
                "parenthesized negatives; AL Schedule A classifier; identity checks with GAP status. "
                "0.1.1: value column threshold 0.65 (0.40 on multi-column schedules)")

# Page classifiers: (regex over the first ~300 characters of the page text, form key, page tag).
FEDERAL_PAGES = [
    (r"Form 1040 \(\d{4}\) Page 2", "1040", "p2"),
    (r"U\.S\. Individual Income Tax Return", "1040", "p1"),
    (r"Schedule 1 \(Form 1040\) \d{4} Page 2", "sch1", "p2"),
    (r"SCHEDULE 1\b", "sch1", "p1"),
    (r"Schedule 2 \(Form 1040\) \d{4} Page 2", "sch2", "p2"),
    (r"SCHEDULE 2\b", "sch2", "p1"),
    (r"SCHEDULE 3\b", "sch3", "p1"),
    (r"SCHEDULE A\b", "schA", "p1"),
    (r"SCHEDULE B\b", "schB", "p1"),
    (r"SCHEDULE C\b", "schC", "p1"),
    (r"Schedule D \(Form 1040\) \d{4} Page 2", "schD", "p2"),
    (r"SCHEDULE D\b", "schD", "p1"),
    (r"SCHEDULE E\b", "schE", "p1"),
    (r"SCHEDULE F\b", "schF", "p1"),
    (r"SCHEDULE SE\b", "schSE", "p1"),
    (r"Schedule 8812 \(Form 1040\) \d{4} Page 2", "sch8812", "p2"),
    (r"SCHEDULE 8812\b", "sch8812", "p1"),
    (r"^\s*(\d{4}(?:-[A-Z])?)\s*\|", None, None),  # "8889 | Health Savings Accounts" etc.
]
AL_PAGES = [
    (r"Form 40 \(\d{4}\) Page 2", "40", "p2"),
    (r"FORM \| 40 \| Alabama", "40", "p1"),
    # ADOR prints "SCHEDULE A" or the combined "SCHEDULES A, B ..." header; the Form 40 / Alabama anchor keeps a
    # federal Schedule A (Form 1040) attached to the AL return from matching.
    (r"SCHEDULES?\s*(?:\|\s*)?A\b(?!\s*(?:\|\s*)?\(Form 1040).{0,200}?(?:(?:Form|FORM)\s*(?:\|\s*)?40\b|Alabama)",
     "al_schA", "p1"),
    (r"SCHEDULE \| B\b", "al_schB", "p1"),
    (r"SCHEDULE \| DS", "al_schDS", "p1"),
    (r"SCHEDULE \| OC", "al_schOC", "p1"),
    (r"SCHEDULE\s.*\| ATP", "al_schATP", "p1"),
]

# Cover-page summary lines TurboTax prints on its filing instructions — an independent cross-check.
COVER = {
    "agi": r"Adjusted Gross Income\s+\$\s*([\d,]+\.\d\d)",
    "taxable_income": r"Taxable Income\s+\$\s*([\d,]+\.\d\d)",
    "total_tax": r"Total Tax\s+\$\s*([\d,]+\.\d\d)",
    "total_payments": r"Total Payments/Credits\s+\$\s*([\d,]+\.\d\d)",
    "refund": r"Refund\s+\$\s*([\d,]+\.\d\d)",
    "payment_due": r"Payment Due\s+\$\s*([\d,]+\.\d\d)",
    "penalty_interest": r"Penalty/Interest\s+\$\s*([\d,]+\.\d\d)",
    "balance_due": r"Balance Due With Penalty/Interest\s+\$\s*([\d,]+\.\d\d)",
    "effective_rate_pct": r"Effective Tax Rate\s+([\d.]+)%",
}


def to_number(token):
    m = AMOUNT.match(token)
    if not m:
        return None
    # "(3,000.)" is negative; so is "3,000.)" when the text layer splits the opening paren into its own word
    neg = token.startswith("(") or token.startswith("-") or token.rstrip("•").endswith(")")
    value = float((m.group(1) + (m.group(2) or "")).replace(",", "").rstrip("."))
    return -value if neg else value


def classify(text, kind):
    head = text[:300].replace("\n", " | ")
    for pattern, form, tag in (FEDERAL_PAGES if kind == "federal" else AL_PAGES):
        m = re.search(pattern, head)
        if m:
            if form is None:  # numbered IRS form: key by its number
                return "f" + m.group(1).lower(), "p1"
            return form, tag
    m = re.search(r"Form (\d{4}(?:-[A-Z])?) \(\d{4}\)\s+(?:Attachment Sequence No\. \S+ )?Page (\d)", head)
    if m and kind == "federal":
        return "f" + m.group(1).lower(), "p" + m.group(2)
    return None, None


def value_min_x_ratio(form, tag):
    """Where the value columns start on this form page, as a fraction of the page width."""
    return PAGE_COLUMN_RATIO.get((form, tag), WIDE_FORMS.get(form, VALUE_MIN_X_RATIO))


def _is_number(w):
    return to_number(w["text"]) is not None and any(c.isdigit() for c in w["text"])


def _is_label_tag(w, words):
    """A bare line number ("4", "12") with a number to its right on the same row is the form's column tag
    for that row, not an amount. "0" and anything with "," or "." stay amounts."""
    t = w["text"]
    if not LINE_CODE.match(t) or t == "0":
        return False
    return any(o is not w and _is_number(o) and 0 < o["x0"] - w["x1"] <= MAX_GAP
               and abs(o["top"] - w["top"]) <= LABEL_BAND for o in words)


def pair_lines(words, page_width, min_x_ratio=VALUE_MIN_X_RATIO):
    """Pair each line-number token with the amount to its right in the same row band."""
    amounts = [w for w in words if _is_number(w) and w["x0"] >= page_width * min_x_ratio
               and not _is_label_tag(w, words)]
    # Preparer software that ends every amount with "." (TurboTax on federal forms): on such a page an
    # undotted number is an SSN fragment, a count or a checkbox digit, not an amount.
    dotted = [w for w in amounts if w["text"].rstrip("•)").endswith(".")]
    if len(dotted) >= 3:
        amounts = dotted
    found = {}
    for w in words:
        m = LINE_CODE.match(w["text"])
        if not m:
            continue
        best = None
        for a in amounts:
            gap = a["x0"] - w["x1"]
            dy = abs(a["top"] - w["top"])
            if 0 < gap <= MAX_GAP and dy <= ROW_BAND:
                # on a dy tie, prefer a token that looks like money ("," or ".") over a bare integer
                plain = 0 if ("," in a["text"] or "." in a["text"]) else 1
                if best is None or (dy, plain, gap) < (best[1], best[3], best[2]):
                    best = (a, dy, gap, plain)
        if best:
            a = best[0]
            key = m.group(1)
            candidate = {"value": to_number(a["text"]), "token": a["text"], "y": round(a["top"], 1)}
            # a line number printed twice on a page (label and column tag) keeps the closer pairing
            if key not in found or best[1] < found[key]["_dy"]:
                candidate["_dy"] = best[1]
                found[key] = candidate
    for v in found.values():
        v.pop("_dy", None)
    return found


def section_of(text, current):
    """Which return a page belongs to. A preparer's PDF may hold the federal return, the Alabama
    return and a second federal copy; a filing-instructions page or a form's first page starts a section."""
    head = text[:300]
    if re.search(r"Filing Instructions for your \d{4} Alabama", head) or re.search(r"FORM\s+40\s+Alabama", head):
        return "al"
    if re.search(r"Filing Instructions for your \d{4} Federal", head) or "U.S. Individual Income Tax Return" in head:
        return "federal"
    return current


def extract(pdf_path, year, kind):
    import pdfplumber
    forms, cover, unclassified = {}, {}, []
    section, starts = "federal", 0
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            new = section_of(text, section)
            if new != section or "Filing Instructions" in text[:120]:
                starts = starts + 1 if new == kind else starts
            section = new
            if section != kind or starts > 1:
                continue  # another return, or a later duplicate copy of this one
            if "Electronic Filing Instructions" in text[:200]:
                for field, pattern in COVER.items():
                    m = re.search(pattern, text)
                    if m:
                        cover[field] = {"value": float(m.group(1).replace(",", "")), "page": i}
            form, tag = classify(text, kind)
            if not form:
                unclassified.append(i)
                continue
            lines = pair_lines(page.extract_words(), page.width, value_min_x_ratio(form, tag))
            if not lines:
                continue
            for v in lines.values():
                v["page"] = i
            instances = forms.setdefault(form, {}).setdefault(tag, [])
            instances.append(lines)
    return forms, cover, unclassified


def line(forms, form, tag, code, instance=0):
    try:
        return forms[form][tag][instance][code]["value"]
    except (KeyError, IndexError, TypeError):
        return None


def summarize(forms, year, kind, maps):
    spec = maps.get(kind, {}).get(str(year))
    if not spec:
        return {}, ["no summary map for %s %s — add one to reference/line-maps.json" % (kind, year)]
    out, missing = {}, []
    for field, ref in spec.items():
        form, tag, code = ref.split(":")
        v = line(forms, form, tag, code)
        out[field] = v
        if v is None:
            missing.append("%s (%s)" % (field, ref))
    return out, missing


# Arithmetic identities: (name, result field, required operand fields, blank-as-zero operand fields, formula).
# A required field that is null makes the check SKIPPED. A blank-as-zero field that is null counts as 0 —
# a blank line on the form is zero — but if the identity then fails the check is a GAP, not a PASS, because
# the null may be a line the extractor could not read rather than a blank one.
FEDERAL_IDENTITIES = [
    ("total_income == wages + taxable_interest + ordinary_dividends + ira_taxable + pensions_taxable"
     " + social_security_taxable + capital_gain + other_income_sch1", "total_income", ["wages"],
     ["taxable_interest", "ordinary_dividends", "ira_taxable", "pensions_taxable", "social_security_taxable",
      "capital_gain", "other_income_sch1"],
     lambda v: v["wages"] + v["taxable_interest"] + v["ordinary_dividends"] + v["ira_taxable"]
     + v["pensions_taxable"] + v["social_security_taxable"] + v["capital_gain"] + v["other_income_sch1"]),
    ("agi == total_income - adjustments", "agi", ["total_income"], ["adjustments"],
     lambda v: v["total_income"] - v["adjustments"]),
    ("deductions_total == deductions + qbi_deduction + schedule_1a_deductions", "deductions_total",
     ["deductions"], ["qbi_deduction", "schedule_1a_deductions"],
     lambda v: v["deductions"] + v["qbi_deduction"] + v["schedule_1a_deductions"]),
    ("taxable_income == max(agi - deductions_total, 0)", "taxable_income", ["agi", "deductions_total"], [],
     lambda v: max(v["agi"] - v["deductions_total"], 0)),
    ("tax_after_credits == max(tax + sch2_line3 - nonrefundable_credits, 0)", "tax_after_credits", ["tax"],
     ["sch2_line3", "nonrefundable_credits"],
     lambda v: max(v["tax"] + v["sch2_line3"] - v["nonrefundable_credits"], 0)),
    ("total_tax == tax_after_credits + other_taxes", "total_tax", ["tax_after_credits"], ["other_taxes"],
     lambda v: v["tax_after_credits"] + v["other_taxes"]),
    ("total_payments == withholding + estimated_payments + refundable_credits", "total_payments",
     ["withholding"], ["estimated_payments", "refundable_credits"],
     lambda v: v["withholding"] + v["estimated_payments"] + v["refundable_credits"]),
    ("amount_owed - estimated_tax_penalty == max(total_tax - total_payments, 0)", "amount_owed",
     ["total_tax", "total_payments"], ["estimated_tax_penalty"],
     lambda v: max(v["total_tax"] - v["total_payments"], 0) + v["estimated_tax_penalty"]),
    ("overpaid == max(total_payments - total_tax, 0)", "overpaid", ["total_tax", "total_payments"], [],
     lambda v: max(v["total_payments"] - v["total_tax"], 0)),
    ("refund disposition: overpaid == refund + applied_to_next_year", "overpaid",
     ["total_tax", "total_payments"], ["refund", "applied_to_next_year"],
     lambda v: v["refund"] + v["applied_to_next_year"]),
]
AL_IDENTITIES = [
    ("total_income == wages + interest_dividends + other_income", "total_income", ["wages"],
     ["interest_dividends", "other_income"],
     lambda v: v["wages"] + v["interest_dividends"] + v["other_income"]),
    ("agi == total_income - adjustments", "agi", ["total_income"], ["adjustments"],
     lambda v: v["total_income"] - v["adjustments"]),
    ("deductions_total == deductions + federal_tax_deduction + personal_exemption + dependent_exemption",
     "deductions_total", ["deductions"], ["federal_tax_deduction", "personal_exemption", "dependent_exemption"],
     lambda v: v["deductions"] + v["federal_tax_deduction"] + v["personal_exemption"] + v["dependent_exemption"]),
    ("taxable_income == max(agi - deductions_total, 0)", "taxable_income", ["agi", "deductions_total"], [],
     lambda v: max(v["agi"] - v["deductions_total"], 0)),
    # line 20 is not in the line map; a return that uses it will fail here until it is mapped
    ("total_tax == net_tax + additional_taxes", "total_tax", ["net_tax"], ["additional_taxes"],
     lambda v: v["net_tax"] + v["additional_taxes"]),
    ("amount_owed == max(total_tax - adjusted_total_payments, 0)", "amount_owed",
     ["total_tax", "adjusted_total_payments"], [],
     lambda v: max(v["total_tax"] - v["adjusted_total_payments"], 0)),
    ("overpaid == max(adjusted_total_payments - total_tax, 0)", "overpaid",
     ["total_tax", "adjusted_total_payments"], [],
     lambda v: max(v["adjusted_total_payments"] - v["total_tax"], 0)),
    ("refund disposition: overpaid == applied_to_next_year + donations + refund", "overpaid",
     ["total_tax", "adjusted_total_payments"], ["applied_to_next_year", "donations", "refund"],
     lambda v: v["applied_to_next_year"] + v["donations"] + v["refund"]),
]
COVER_FIELDS = ("agi", "taxable_income", "total_tax", "total_payments", "refund")


def checks(summary, cover, kind=None):
    """Internal-consistency checks. Each is a named arithmetic identity on extracted values.

    Status: PASS; FAIL (the identity does not hold on values that were all read); GAP (it does not hold, or a
    cover value has no return value, and a null line is involved — incomplete extraction); SKIPPED (a
    required line is null, or the cover does not print that figure)."""
    if kind is None:
        kind = "al" if "income_tax" in summary else "federal"
    s = summary
    results = []

    def compare(name, left, right, unread=()):
        ok = abs(left - right) < 0.5
        r = {"check": name, "status": "PASS" if ok else ("GAP" if unread else "FAIL"), "left": left, "right": right}
        if unread and not ok:
            r["unread"] = sorted(unread)
        results.append(r)

    for field in COVER_FIELDS:
        c = (cover.get(field) or {}).get("value")
        name = "cover.%s == return.%s" % (field, field)
        if c is None:
            results.append({"check": name, "status": "SKIPPED"})
        elif s.get(field) is None:
            results.append({"check": name, "status": "GAP", "left": c, "right": None, "unread": [field]})
        else:
            compare(name, c, s[field])
    due = (cover.get("payment_due") or {}).get("value")
    name = "cover.payment_due + cover.penalty_interest == return.amount_owed"
    if due is None:
        results.append({"check": name, "status": "SKIPPED"})
    else:
        left = due + ((cover.get("penalty_interest") or {}).get("value") or 0)
        if s.get("amount_owed") is None:
            results.append({"check": name, "status": "GAP", "left": left, "right": None, "unread": ["amount_owed"]})
        else:
            compare(name, left, s["amount_owed"])

    for name, result, required, optional, formula in (AL_IDENTITIES if kind == "al" else FEDERAL_IDENTITIES):
        if any(s.get(f) is None for f in required):
            results.append({"check": name, "status": "SKIPPED"})
            continue
        values = {f: s[f] for f in required}
        values.update({f: s.get(f) or 0 for f in optional})
        unread = [f for f in optional + [result] if f not in required and s.get(f) is None]
        compare(name, s.get(result) or 0, formula(values), unread)
    return results


def exit_status(results):
    """0 only when nothing FAILs or GAPs and at least one check PASSes."""
    statuses = [c["status"] for c in results]
    return 1 if ("FAIL" in statuses or "GAP" in statuses or "PASS" not in statuses) else 0


def load_maps():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "..", "reference", "line-maps.json"), encoding="utf-8") as f:
        return json.load(f)


def recheck(path, maps):
    """Recompute summary, summary_missing and checks of an extracted JSON from its `forms` block and the
    current line maps. `summary_notes` (why a null is not a blank) is kept as it is."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    summary, missing = summarize(d["forms"], d["tax_year"], d["kind"], maps)
    d["summary"], d["summary_missing"] = summary, missing
    d["checks"] = checks(summary, d["cover_summary"], d["kind"])
    d["extractor"]["checks_version"] = VERSION
    ordered = {}
    for k in ("tax_year", "kind", "source", "extractor", "summary", "summary_notes", "summary_missing",
              "cover_summary", "checks", "forms", "unclassified_pages"):
        if k in d:
            ordered[k] = d[k]
    ordered.update({k: v for k, v in d.items() if k not in ordered})
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(ordered, indent=1, ensure_ascii=False) + "\n")
    return ordered


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--year", type=int)
    ap.add_argument("--kind", choices=["federal", "al"])
    ap.add_argument("--drive-id", default=None, help="id of the PDF in your document store")
    ap.add_argument("--link-template", default=None,
                    help="URL with {id}, filled with --drive-id to give source.drive_link")
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--recheck", nargs="+", metavar="JSON",
                    help="recompute summary and checks of extracted JSON files in place (no PDF)")
    args = ap.parse_args(argv)
    maps = load_maps()

    if args.recheck:
        status = 0
        for path in args.recheck:
            d = recheck(path, maps)
            print("%s %s %s" % (d["tax_year"], d["kind"], path))
            for c in d["checks"]:
                print("  %-7s %s%s" % (c["status"], c["check"],
                                       ("  unread: " + ", ".join(c["unread"])) if c.get("unread") else ""))
            status = max(status, exit_status(d["checks"]))
        return status
    if not (args.pdf and args.year and args.kind):
        ap.error("a PDF, --year and --kind are required unless --recheck is given")

    with open(args.pdf, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()

    forms, cover, unclassified = extract(args.pdf, args.year, args.kind)
    summary, missing = summarize(forms, args.year, args.kind, maps)
    result = {
        "tax_year": args.year,
        "kind": args.kind,
        "source": {
            "drive_id": args.drive_id,
            "drive_link": (args.link_template.format(id=args.drive_id)
                           if args.drive_id and args.link_template else None),
            "title": args.title,
            "pdf_sha256": digest,
        },
        "extractor": {"name": "extract_return", "version": VERSION,
                      "run_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "summary": summary,
        "summary_missing": missing,
        "cover_summary": cover,
        "checks": checks(summary, cover, args.kind),
        "forms": forms,
        "unclassified_pages": unclassified,
    }
    text = json.dumps(result, indent=1, ensure_ascii=False)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(json.dumps({k: result[k] for k in ("tax_year", "kind", "summary", "summary_missing", "checks",
                                             "unclassified_pages")}, indent=1))
    return exit_status(result["checks"])


if __name__ == "__main__":
    sys.exit(main())
