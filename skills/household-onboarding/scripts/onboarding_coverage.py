#!/usr/bin/env python3
"""Validate an onboarding coverage file and print the coverage report (references/plan.md §6).

    python3 scripts/onboarding_coverage.py <coverage.yaml>                # validate, then one line per area
    python3 scripts/onboarding_coverage.py <coverage.yaml> --today 2026-03-01
    python3 scripts/onboarding_coverage.py <coverage.yaml> --check        # validate only; exit 1 on any error

Each area row needs `area` (A<n>), `past`, `current` and `future`, each with a `status` of gap,
partial or known. Areas whose `next_review` is before today are flagged OVERDUE. The script only
reads; it never edits the file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import yaml

SECTIONS = ("past", "current", "future")
STATUSES = ("gap", "partial", "known")
AREA_RE = re.compile(r"^A\d{1,2}$")
LIST_FIELDS = ("open_questions", "documents_missing")
DATE_FIELDS = ("discovered", "next_session", "next_review")


def _date(v) -> dt.date | None:
    if v is None or isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))


def validate(doc) -> list[str]:
    """Return a list of problems; empty means the file is valid."""
    errs: list[str] = []
    if not isinstance(doc, dict) or not isinstance(doc.get("areas"), list):
        return ["top level must be a mapping with an `areas:` list"]
    seen = set()
    for i, a in enumerate(doc["areas"]):
        where = f"areas[{i}]"
        if not isinstance(a, dict):
            errs.append(f"{where}: must be a mapping")
            continue
        aid = str(a.get("area", ""))
        where = aid or where
        if not AREA_RE.match(aid):
            errs.append(f"{where}: `area` must look like A1…A14")
        if aid in seen:
            errs.append(f"{where}: duplicate area")
        seen.add(aid)
        for s in SECTIONS:
            sec = a.get(s)
            if not isinstance(sec, dict):
                errs.append(f"{where}: `{s}` must be a mapping with a status")
                continue
            if sec.get("status") not in STATUSES:
                errs.append(f"{where}: {s}.status must be one of {', '.join(STATUSES)} (is {sec.get('status')!r})")
            try:
                _date(sec.get("verified"))
            except ValueError:
                errs.append(f"{where}: {s}.verified is not a date")
        for f in LIST_FIELDS:
            if a.get(f) is not None and not isinstance(a[f], list):
                errs.append(f"{where}: `{f}` must be a list")
        for f in DATE_FIELDS:
            try:
                _date(a.get(f))
            except ValueError:
                errs.append(f"{where}: `{f}` is not a date (YYYY-MM-DD)")
    return errs


def is_done(a: dict) -> bool:
    return all(a[s]["status"] == "known" for s in SECTIONS)


def report(doc, today: dt.date) -> list[str]:
    lines = []
    for a in doc["areas"]:
        st = "/".join(a[s]["status"] for s in SECTIONS)
        oq = len(a.get("open_questions") or [])
        dm = len(a.get("documents_missing") or [])
        nxt = _date(a.get("next_session"))
        rev = _date(a.get("next_review"))
        flag = " OVERDUE" if rev and rev < today else ""
        done = " done" if is_done(a) else ""
        lines.append(f"{a['area']:<4} {str(a.get('name', '')):<38.38} {st:<22} "
                     f"open {oq:>2}  docs {dm:>2}  next {nxt or '—'}{flag}{done}")
    known = sum(a[s]["status"] == "known" for a in doc["areas"] for s in SECTIONS)
    lines.append(f"{len(doc['areas'])} areas · {known} of {3 * len(doc['areas'])} sections known")
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--check", action="store_true", help="validate only")
    a = ap.parse_args(argv)
    try:
        doc = yaml.safe_load(a.path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        print(f"ERROR {a.path}: {e}", file=sys.stderr)
        return 1
    errs = validate(doc)
    for e in errs:
        print(f"ERROR {e}", file=sys.stderr)
    if errs:
        return 1
    if not a.check:
        print("\n".join(report(doc, a.today)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
