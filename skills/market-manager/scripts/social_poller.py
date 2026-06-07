#!/usr/bin/env python3
"""
HoneyBeeham Social Poller / Catalog  (Evaluate v2)
==================================================
Turns periodic, browser-collected snapshots of each market's Instagram / Facebook / website into
two living signals the rest of the skill consumes:

  1. popularity_trend  — year-over-year momentum (growing / stable / soft_decline / decline),
                         derived from follower + engagement + sentiment deltas across snapshots.
                         Feeds the `popularity_trend` modifier in market_scorer.py.
  2. deadline status   — which application windows are open / closing soon / closed, feeding
                         the Register deadline tracker.

THIS IS THE ANALYSIS HALF of the on-demand poll. The CAPTURE half is Claude + browser tools:
because Instagram/Facebook block automated scraping, a human-in-the-loop session uses browser
tools to read each market's public accounts and APPENDS a row to `social_catalog.csv` (and any
newly found application windows to `deadline_tracker.csv`). See references/social_polling.md for
the capture playbook. This script never fetches anything — it only reads the CSVs you filled and
computes signals from them, so it is deterministic, offline, and safe to re-run.

Run:
    python3 social_poller.py social_catalog.csv deadline_tracker.csv \\
            [--today YYYY-MM-DD] [--out social_signals.csv] [--patch-input markets_input.csv]

  --today        reference date for deadline math (default: system today).
  --out          write a per-market signals CSV (default: social_signals.csv next to the catalog).
  --patch-input  ALSO write each derived popularity_trend back into a market_scorer input CSV
                 (matched by `name`); other columns are left untouched.

------------------------------------------------------------------------------
social_catalog.csv  (append-only; one row per market per poll date)
------------------------------------------------------------------------------
  market               Market name (must match the scorer input's `name`).
  date_polled          YYYY-MM-DD the snapshot was taken.
  ig_followers         Instagram follower count at poll time (number; blank ok).
  fb_followers         Facebook follower/like count (number; blank ok).
  posts_last_90d       # posts in the trailing 90 days (activity proxy; blank ok).
  avg_engagement       avg likes+comments per recent post (engagement proxy; blank ok).
  sentiment            positive / neutral / negative — tone of recent posts + comments.
  location_current     current venue/location string (used to detect a move).
  similar_vendor_count # competing candle/honey/soap vendors seen in the lineup (feeds density).
  notable_vendors      ; -separated notable/competing vendors observed.
  source_urls          where the snapshot came from (for audit).
  notes                free text.

------------------------------------------------------------------------------
deadline_tracker.csv  (one row per market application window)
------------------------------------------------------------------------------
  market, app_platform, app_opens (YYYY-MM-DD), app_closes (YYYY-MM-DD),
  status (researching/applied/waitlisted/accepted/booked), action, fee_quote,
  one_day_option (yes/no), source_url, last_checked, notes
"""
import csv
import sys
from datetime import date, datetime

# ============================ TUNABLE CONSTANTS ==============================

GROWTH_THRESHOLD = 0.10   # ±10% follower/engagement change to count as a momentum signal
URGENT_DAYS = 28          # application closes within this many days -> URGENT
SOON_DAYS = 56            # ...within this many days -> SOON

# Net evidence points -> popularity_trend bucket (matches the scorer's allowed values).
# Conservative on the downside per methodology: only flag decline with corroborating evidence.
TREND_BY_POINTS = [(1, "growing"), (0, "stable"), (-1, "soft_decline")]  # else "decline"
SINGLE_SNAPSHOT_TREND = "stable"  # not enough history to claim momentum

# ============================ PARSING HELPERS ===============================

def _num(v):
    try:
        return float(str(v).replace("$", "").replace(",", "").replace("%", "").strip())
    except (ValueError, AttributeError):
        return None


def _pos(v):
    n = _num(v)
    return n if (n and n > 0) else None


def _date(v):
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _pct(cur, prev):
    """Signed fractional change cur vs prev; None if prev is missing/zero."""
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / prev

# ============================ TREND DERIVATION ==============================

def _momentum_point(pct):
    if pct is None:
        return 0
    if pct >= GROWTH_THRESHOLD:
        return 1
    if pct <= -GROWTH_THRESHOLD:
        return -1
    return 0


def derive_trend(snapshots):
    """snapshots: list of catalog rows for ONE market. Returns (trend, evidence, extras)."""
    snaps = sorted([s for s in snapshots if _date(s.get("date_polled"))],
                   key=lambda s: _date(s["date_polled"]))
    latest = snaps[-1] if snaps else {}
    extras = {
        "latest_poll": latest.get("date_polled", ""),
        "ig_followers": _pos(latest.get("ig_followers")),
        "fb_followers": _pos(latest.get("fb_followers")),
        "sentiment": (str(latest.get("sentiment", "")).strip().lower() or "neutral"),
        "location_changed": "no",
        "similar_vendor_count": _num(latest.get("similar_vendor_count")),
        "notable_vendors": latest.get("notable_vendors", ""),
    }

    if len(snaps) < 2:
        extras["span_days"] = 0
        return SINGLE_SNAPSHOT_TREND, "single snapshot — insufficient history", extras

    base, cur = snaps[0], snaps[-1]
    span = (_date(cur["date_polled"]) - _date(base["date_polled"])).days
    extras["span_days"] = span

    foll_cur = _pos(cur.get("ig_followers")) or _pos(cur.get("fb_followers"))
    foll_base = _pos(base.get("ig_followers")) or _pos(base.get("fb_followers"))
    foll_pct = _pct(foll_cur, foll_base)
    eng_pct = _pct(_pos(cur.get("avg_engagement")), _pos(base.get("avg_engagement")))
    sentiment = extras["sentiment"]

    loc_base = str(base.get("location_current", "")).strip().lower()
    loc_cur = str(cur.get("location_current", "")).strip().lower()
    if loc_base and loc_cur and loc_base != loc_cur:
        extras["location_changed"] = "yes"

    points = _momentum_point(foll_pct) + _momentum_point(eng_pct)
    if sentiment == "negative":
        points -= 1  # negative tone only ever subtracts (downside caution)

    trend = "decline"
    for threshold, label in TREND_BY_POINTS:
        if points >= threshold:
            trend = label
            break

    def _fmt(pct):
        return f"{pct*100:+.0f}%" if pct is not None else "n/a"

    bits = [f"followers {_fmt(foll_pct)}", f"engagement {_fmt(eng_pct)}", f"sentiment {sentiment}"]
    if extras["location_changed"] == "yes":
        bits.append("LOCATION MOVED")
    bits.append(f"{span}d span")
    return trend, ", ".join(bits), extras

# ============================ DEADLINE STATUS ==============================

def deadline_status(row, today):
    closes = _date(row.get("app_closes"))
    opens = _date(row.get("app_opens"))
    if closes is None:
        return "UNKNOWN", None
    days = (closes - today).days
    if days < 0:
        return "CLOSED", days
    if opens and today < opens:
        return "NOT_OPEN", days
    if days <= URGENT_DAYS:
        return "URGENT", days
    if days <= SOON_DAYS:
        return "SOON", days
    return "OPEN", days

# ================================= MAIN =====================================

def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main():
    positional = [a for a in sys.argv[1:] if not a.startswith("--")
                  and sys.argv[sys.argv.index(a) - 1] not in ("--today", "--out", "--patch-input")]
    catalog_path = positional[0] if positional else "social_catalog.csv"
    deadlines_path = positional[1] if len(positional) > 1 else "deadline_tracker.csv"
    out_path = _arg("--out", "social_signals.csv")
    patch_input = _arg("--patch-input")
    today = _date(_arg("--today")) or date.today()

    # --- popularity_trend per market ---
    by_market = {}
    try:
        with open(catalog_path, newline="") as fh:
            for r in csv.DictReader(fh):
                by_market.setdefault(r["market"].strip(), []).append(r)
    except FileNotFoundError:
        print(f"!! catalog not found: {catalog_path}")
        by_market = {}

    signals = {}
    for market, snaps in sorted(by_market.items()):
        trend, evidence, extras = derive_trend(snaps)
        signals[market] = {"market": market, "popularity_trend": trend, "evidence": evidence, **extras}

    # --- deadlines ---
    deadlines = []
    try:
        with open(deadlines_path, newline="") as fh:
            for r in csv.DictReader(fh):
                status, days = deadline_status(r, today)
                deadlines.append({**r, "_status": status, "_days": days})
    except FileNotFoundError:
        print(f"!! deadline tracker not found: {deadlines_path}")

    # --- report ---
    print(f"Poll signals as of {today}\n")
    if signals:
        print("POPULARITY TREND")
        print(f"  {'Market':<28}{'Trend':<14}Evidence")
        for s in sorted(signals.values(), key=lambda s: s["market"]):
            flag = "  <-- venue moved" if s.get("location_changed") == "yes" else ""
            print(f"  {s['market'][:27]:<28}{s['popularity_trend']:<14}{s['evidence']}{flag}")
    if deadlines:
        order = {"URGENT": 0, "SOON": 1, "OPEN": 2, "NOT_OPEN": 3, "CLOSED": 4, "UNKNOWN": 5}
        deadlines.sort(key=lambda d: (order.get(d["_status"], 9), d["_days"] if d["_days"] is not None else 9999))
        print("\nAPPLICATION DEADLINES")
        print(f"  {'Status':<10}{'Closes':<12}{'Days':>5}  {'Market':<28}Action")
        for d in deadlines:
            dd = "" if d["_days"] is None else str(d["_days"])
            print(f"  {d['_status']:<10}{str(d.get('app_closes','')):<12}{dd:>5}  "
                  f"{d['market'][:27]:<28}{d.get('action','')}")

    # --- write signals csv ---
    fields = ["market", "popularity_trend", "evidence", "latest_poll", "ig_followers",
              "fb_followers", "sentiment", "location_changed", "span_days",
              "similar_vendor_count", "notable_vendors"]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in sorted(signals.values(), key=lambda s: s["market"]):
            w.writerow(s)
    print(f"\nWrote {out_path}")

    # --- optional: patch popularity_trend back into a scorer input CSV ---
    if patch_input:
        with open(patch_input, newline="") as fh:
            reader = csv.DictReader(fh)
            in_fields = reader.fieldnames or []
            rows = list(reader)
        if "popularity_trend" not in in_fields:
            in_fields = in_fields + ["popularity_trend"]
        patched = 0
        for r in rows:
            sig = signals.get(r.get("name", "").strip())
            if sig:
                r["popularity_trend"] = sig["popularity_trend"]
                patched += 1
        with open(patch_input, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=in_fields)
            w.writeheader()
            w.writerows(rows)
        print(f"Patched popularity_trend on {patched}/{len(rows)} rows in {patch_input}")


if __name__ == "__main__":
    main()
