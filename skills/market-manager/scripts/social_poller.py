#!/usr/bin/env python3
"""
HoneyBeeham Social Poller / Catalog  (Evaluate v2.1)
====================================================
Turns periodic, browser-collected snapshots of each market's Instagram / Facebook / website into
the signals the rest of the skill consumes:

  1. popularity_trend  — momentum, blended from THREE signals so it reflects real interest, not just
                         raw audience size:
                           • FOLLOWING   — follower count (the audience).
                           • ENGAGEMENT  — interactions per follower = (likes+comments+shares)/followers
                                           (normalizes small vs large markets).
                           • REACH       — video/post VIEWS (how far a post travels beyond followers).
                         Feeds the `popularity_trend` modifier in market_scorer.py.
  2. trajectory        — a multi-year (up to 5y) read of whether a market is GAINING / HOLDING /
                         WANING, from the earliest vs latest snapshot. This is the "is this market
                         on the way up or down?" call the calendar leans on.
  3. deadline status   — which application windows are open / closing soon / closed (Register).

THIS IS THE ANALYSIS HALF of the on-demand poll. The CAPTURE half is Claude + browser tools:
social platforms block scrapers, so a human-in-the-loop session reads each market's public accounts
and APPENDS a row to `social_catalog.csv` (and any application windows to `deadline_tracker.csv`).
See references/social_polling.md. Facebook exposes per-post likes/comments/shares/VIEWS (Instagram
usually hides like counts), so FB is the richer interaction source — capture it when you can. This
script never fetches; it only reads the CSVs you filled, so it is deterministic and safe to re-run.
The more years of snapshots you keep, the sharper the trajectory.

Run:
    python3 social_poller.py social_catalog.csv deadline_tracker.csv \\
            [--today YYYY-MM-DD] [--out social_signals.csv] [--patch-input markets_input.csv]

------------------------------------------------------------------------------
social_catalog.csv  (append-only; one row per market per poll date)
------------------------------------------------------------------------------
  market               Market name (must match the scorer input's `name`).
  date_polled          YYYY-MM-DD the snapshot was taken.
  ig_followers         Instagram follower count (number; blank ok).
  fb_followers         Facebook follower count (number; blank ok).
  posts_last_90d       # posts in the trailing 90 days (activity proxy; blank ok).
  recent_post_likes    likes/reactions on the sampled recent post(s).
  recent_post_comments comments on the sampled recent post(s).
  recent_post_shares   shares of the sampled recent post(s).
  recent_post_views    VIEWS of the sampled recent post(s) (video/reel reach; blank ok).
  sentiment            positive / neutral / negative — tone of recent posts + comments.
  location_current     current venue string (used to detect a move).
  similar_vendor_count # competing candle/honey/soap vendors in the lineup (feeds density).
  notable_vendors      ; -separated notable/competing vendors observed.
  source_urls          where the snapshot came from (audit).
  notes                free text.
  (legacy: avg_engagement is still read as an interactions fallback if the recent_post_* fields
   are blank, so older catalogs keep working.)

------------------------------------------------------------------------------
deadline_tracker.csv  (one row per market application window)
------------------------------------------------------------------------------
  market, app_platform, app_opens (YYYY-MM-DD), app_closes (YYYY-MM-DD),
  status, action, fee_quote, one_day_option, source_url, last_checked, notes
"""
import csv
import sys
from datetime import date, datetime

# ============================ TUNABLE CONSTANTS ==============================

# Blend weights for the three interest signals (following / engagement / reach).
# Engagement (interest per follower) is weighted highest; reach (views) is a strong second; raw
# following is context. Missing signals are dropped and the remaining weights re-normalize.
INTEREST_WEIGHTS = {"following": 0.34, "engagement": 0.40, "reach": 0.26}

# Blended change -> popularity_trend modifier value (matches the scorer's allowed values).
# Conservative on the downside per methodology: real evidence required to flag a decline.
TREND_BANDS = [(0.10, "growing"), (-0.05, "stable"), (-0.15, "soft_decline")]  # else "decline"
SINGLE_SNAPSHOT_TREND = "stable"

# Multi-year trajectory label (needs at least MIN_TRAJECTORY_YEARS of history).
TRAJECTORY_BANDS = [(0.10, "GAINING"), (-0.05, "HOLDING")]  # else "WANING"
MIN_TRAJECTORY_YEARS = 1.5
SENTIMENT_PENALTY = 0.15   # negative recent sentiment nudges the blend down

URGENT_DAYS = 28           # application closes within this many days -> URGENT
SOON_DAYS = 56             # ...within this many days -> SOON

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
    """Signed fractional change cur vs prev; None if either is missing or prev is zero."""
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / prev


def _clamp(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))

# ============================ SNAPSHOT METRICS ==============================

def snapshot_metrics(row):
    """Per-snapshot following / engagement / reach metrics from one catalog row."""
    ig, fb = _pos(row.get("ig_followers")), _pos(row.get("fb_followers"))
    followers = max(ig or 0, fb or 0) or None   # the audience the post was shown to

    likes = _num(row.get("recent_post_likes"))
    comments = _num(row.get("recent_post_comments"))
    shares = _num(row.get("recent_post_shares"))
    views = _pos(row.get("recent_post_views"))

    parts = [p for p in (likes, comments, shares) if p is not None]
    interactions = sum(parts) if parts else _num(row.get("avg_engagement"))  # legacy fallback

    engagement_rate = (interactions / followers) if (interactions is not None and followers) else None
    return {
        "followers": followers,
        "interactions": interactions,
        "engagement_rate": engagement_rate,  # interactions per follower
        "reach": views,                       # views = how far the post traveled
    }

# ============================ TREND / TRAJECTORY ============================

def derive_trend(snapshots):
    """snapshots: catalog rows for ONE market. Returns (trend, trajectory, evidence, extras)."""
    snaps = sorted([s for s in snapshots if _date(s.get("date_polled"))],
                   key=lambda s: _date(s["date_polled"]))
    latest = snaps[-1] if snaps else {}
    lm = snapshot_metrics(latest) if snaps else {}
    extras = {
        "latest_poll": latest.get("date_polled", ""),
        "followers": lm.get("followers"),
        "engagement_rate": lm.get("engagement_rate"),
        "reach_views": lm.get("reach"),
        "sentiment": (str(latest.get("sentiment", "")).strip().lower() or "neutral"),
        "location_changed": "no",
        "span_years": 0.0,
        "follower_change": None, "engagement_change": None, "reach_change": None,
        "recent_follower_change": None,
    }

    if len(snaps) < 2:
        return SINGLE_SNAPSHOT_TREND, "BUILDING", "single snapshot — insufficient history", extras

    base, prev, cur = snaps[0], snaps[-2], snaps[-1]
    bm, pm, cm = snapshot_metrics(base), snapshot_metrics(prev), snapshot_metrics(cur)
    span_days = (_date(cur["date_polled"]) - _date(base["date_polled"])).days
    span_years = round(span_days / 365.25, 1)
    extras["span_years"] = span_years

    # Long-term change (earliest -> latest): the trajectory signal.
    foll_chg = _pct(cm["followers"], bm["followers"])
    eng_chg = _pct(cm["engagement_rate"], bm["engagement_rate"])
    reach_chg = _pct(cm["reach"], bm["reach"])
    extras.update(follower_change=foll_chg, engagement_change=eng_chg, reach_change=reach_chg)
    # Short-term delta (prev -> latest): "what changed since last snapshot".
    extras["recent_follower_change"] = _pct(cm["followers"], pm["followers"])

    if str(base.get("location_current", "")).strip().lower() and \
       str(base.get("location_current", "")).strip().lower() != str(cur.get("location_current", "")).strip().lower():
        extras["location_changed"] = "yes"

    # Weighted blend over whichever signals are present (re-normalize missing ones away).
    pairs = [("following", foll_chg), ("engagement", eng_chg), ("reach", reach_chg)]
    num = den = 0.0
    for key, chg in pairs:
        if chg is not None:
            w = INTEREST_WEIGHTS[key]
            num += w * _clamp(chg)
            den += w
    blended = (num / den) if den else 0.0
    if extras["sentiment"] == "negative":
        blended -= SENTIMENT_PENALTY

    trend = "decline"
    for thr, label in TREND_BANDS:
        if blended >= thr:
            trend = label
            break

    if span_years >= MIN_TRAJECTORY_YEARS:
        trajectory = "WANING"
        for thr, label in TRAJECTORY_BANDS:
            if blended >= thr:
                trajectory = label
                break
    else:
        trajectory = "BUILDING"

    def _p(x):
        return f"{x*100:+.0f}%" if x is not None else "n/a"

    bits = [f"following {_p(foll_chg)}", f"engagement-rate {_p(eng_chg)}", f"reach {_p(reach_chg)}",
            f"sentiment {extras['sentiment']}"]
    if extras["location_changed"] == "yes":
        bits.append("LOCATION MOVED")
    bits.append(f"{span_years}y, blend {blended:+.2f}")
    return trend, trajectory, ", ".join(bits), extras

# ============================ DEADLINE STATUS ==============================

def deadline_status(row, today):
    closes, opens = _date(row.get("app_closes")), _date(row.get("app_opens"))
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
    flagged = {"--today", "--out", "--patch-input"}
    positional = [a for i, a in enumerate(sys.argv[1:], 1)
                  if not a.startswith("--") and sys.argv[i - 1] not in flagged]
    catalog_path = positional[0] if positional else "social_catalog.csv"
    deadlines_path = positional[1] if len(positional) > 1 else "deadline_tracker.csv"
    out_path = _arg("--out", "social_signals.csv")
    patch_input = _arg("--patch-input")
    today = _date(_arg("--today")) or date.today()

    by_market = {}
    try:
        with open(catalog_path, newline="") as fh:
            for r in csv.DictReader(fh):
                by_market.setdefault(r["market"].strip(), []).append(r)
    except FileNotFoundError:
        print(f"!! catalog not found: {catalog_path}")

    signals = {}
    for market, snaps in sorted(by_market.items()):
        trend, trajectory, evidence, extras = derive_trend(snaps)
        signals[market] = {"market": market, "popularity_trend": trend,
                           "trajectory": trajectory, "evidence": evidence, **extras}

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
        print("POPULARITY & INTEREST OVER TIME")
        print(f"  {'Market':<26}{'Trend':<12}{'5y traj':<10}Evidence")
        for s in sorted(signals.values(), key=lambda s: s["market"]):
            print(f"  {s['market'][:25]:<26}{s['popularity_trend']:<12}{s['trajectory']:<10}{s['evidence']}")
    if deadlines:
        order = {"URGENT": 0, "SOON": 1, "OPEN": 2, "NOT_OPEN": 3, "CLOSED": 4, "UNKNOWN": 5}
        deadlines.sort(key=lambda d: (order.get(d["_status"], 9),
                                      d["_days"] if d["_days"] is not None else 9999))
        print("\nAPPLICATION DEADLINES")
        print(f"  {'Status':<10}{'Closes':<12}{'Days':>5}  {'Market':<26}Action")
        for d in deadlines:
            dd = "" if d["_days"] is None else str(d["_days"])
            print(f"  {d['_status']:<10}{str(d.get('app_closes','')):<12}{dd:>5}  "
                  f"{d['market'][:25]:<26}{d.get('action','')}")

    # --- write signals csv ---
    def _pctf(x):
        return "" if x is None else f"{x*100:.1f}%"

    fields = ["market", "popularity_trend", "trajectory", "span_years", "latest_poll", "followers",
              "engagement_rate", "reach_views", "follower_change", "engagement_change",
              "reach_change", "recent_follower_change", "sentiment", "location_changed", "evidence"]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in sorted(signals.values(), key=lambda s: s["market"]):
            row = dict(s)
            for k in ("engagement_rate",):
                row[k] = _pctf(s.get(k))
            for k in ("follower_change", "engagement_change", "reach_change", "recent_follower_change"):
                row[k] = _pctf(s.get(k))
            w.writerow(row)
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
