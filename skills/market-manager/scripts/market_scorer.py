#!/usr/bin/env python3
"""
HoneyBeeham Market Scorer  (v6)
===============================
Ranks farmers / artisan / holiday / pop-up markets for a PREMIUM handmade beeswax-candle
+ local-honey seller, using only externally observable signals (no internal sales data).

    FINAL = QUALITY (7 weighted criteria, 0-5)  ×  MODIFIERS (mostly 0-1)

Quality is the market's intrinsic draw/fit; modifiers are penalties that suppress it — except
the junior_vendor BOOST, which can exceed 1.0 to reward kid-friendly markets.

Run:
    python3 market_scorer.py markets_input.csv markets_scored.csv

------------------------------------------------------------------------------
INPUT CSV COLUMNS (one row per market; blanks are handled gracefully)
------------------------------------------------------------------------------
  name                  Market name.
  QUALITY (analyst 1-5 unless noted):
    premium_positioning curated gift/artisan (5) vs family/produce festival (1)
    median_income_10mi  median household income within ~10 mi (USD) -> affluence
    destination_pull    yes/no — pulls affluent attendees from >10 mi (affluence override)
    affinity_or_nonprofit yes/no — high-affinity group / non-profit benefit (affluence override)
    foot_traffic        crowd VOLUME / access (big free crowd = 5)
    scale               vendor count / physical size (NOT age — see maturity)
    vendor_density      5 = FEW competing candle/honey/craft vendors inside (you're rare); 1 = saturated
    reach               FALLBACK 1-5 only; normally COMPUTED from ig/fb followers
    ig_handle           Instagram handle; blank or "(FB only)" => no IG (demographic penalty)
    ig_followers        Instagram follower count (number)
    fb_followers        Facebook follower/like count (number)
    free_admission      yes/no — free to attend
    ticketed            yes/no — paid admission (gates the casual crowd)
    booth_fee           vendor booth fee (USD); blank = apply-only/unpublished
  MODIFIERS (categorical unless noted):
    fine_art_focus      none / partial / fine_art  (juried fine-art crowd won't buy candles/honey)
    same_day_competition none / some / heavy        (competing markets same area + day)
    maturity            established / newish / new   (new/unknown market draws a smaller crowd)
    sport_conflict      none / major / iron_bowl     (significant same-day sport event in area)
    junior_vendor       none / no / yes  (BOOST: market offers a discounted "junior artisan" /
                        "junior vendor" youth spot — often unadvertised, ask the organizer. The one
                        modifier allowed to exceed 1.0, because a kid-friendly market lets the
                        12-year-old seller participate cheaply and is worth ranking higher.)
    day_window          weekend | evening_ok | mixed_partial | weekday_daytime  (school fit)
    min_days            min days vendor MUST attend (use the 1-day option if offered)
    hours_per_day       shopper hours per day (e.g. Sat 11a-5p = 6). total hours = hours_per_day x
                        min_days drives a $/hour-efficiency factor: fewer total hours on-site is
                        better (a 6-hr single day beats a 3-day, 24-hr show). Falls back to a
                        days-only penalty if hours_per_day is blank.
    drive_rt_hrs        round-trip drive hours from home base (Birmingham, AL). Added to on-site
                        hours so out-of-town markets (Tuscaloosa ~2, Huntsville ~3, Auburn ~4,
                        Chattanooga ~4, Atlanta ~5, Nashville ~6) cost more time and dilute $/hour.
                        Birmingham metro = 0.
    notes / fee_note    free text (ignored by scoring)

------------------------------------------------------------------------------
DECISIONS CAPTURED (this is the canonical record of how the rubric was tuned)
------------------------------------------------------------------------------
  * External-only: never use internal sales; this predicts market quality, not booth economics.
  * Affluence override: low local income is NOT penalized if the market is a destination pull
    or a high-affinity / non-profit-benefit event (floor lifted to OVERRIDE_FLOOR).
  * Entry-fee drag: booth fee (the vendor's $ risk) weighted 60% vs admission 40%.
  * Vendor density: few competing similar vendors inside = higher per-booth capture.
  * Reach is computed from IG/FB followers (IG weighted higher); no IG / IG-parent => -0.5 demographic.
  * Fine-art penalty: juried fine-art shows score high on "premium" but the crowd isn't buying
    candles/honey -> strong multiplier penalty.
  * Date drags: same-day competing markets, market newness, major sport day (Iron Bowl).
  * Schedule fit (Charley Ann is 12 / in school): markets must be Fri/Sat/Sun OR weekday after 3pm;
    a school-hours weekday is near-disqualifying; >3 required days is a big drag; a one-day option
    on a multi-day market fixes it (set min_days to the smallest commitment).
  * Validation: on the 4 markets with known take-home, v6 orders Deck > Bash > 20th and lands
    MadeSouth last — matching actuals once reach reflects real followers.
"""
import csv
import sys

# ============================ TUNABLE CONSTANTS ==============================

# Quality criteria weights (sum need not be 100 — the score is normalised by the sum).
WEIGHTS = {
    "premium_positioning": 18,
    "affluence_affinity": 18,
    "foot_traffic_access": 18,
    "reach": 13,
    "vendor_density": 12,
    "scale": 11,
    "entry_fee_drag": 10,
}
WEIGHT_SUM = sum(WEIGHTS.values())

# Affluence: median household income (USD) -> 1-5 band.
INCOME_BANDS = [(110000, 5.0), (85000, 4.0), (65000, 3.0), (50000, 2.5), (40000, 2.0), (0, 1.0)]
OVERRIDE_FLOOR = 4.5            # affluence floor for destination / affinity / non-profit markets
NEUTRAL_AFFLUENCE = 3.0         # used when income is unknown and no override applies

# Social: combined effective following -> 1-5 reach band (IG weighted higher than FB).
SOCIAL_BANDS = [(50000, 5.0), (25000, 4.5), (12000, 4.0), (6000, 3.5), (2500, 3.0), (1000, 2.5), (0, 2.0)]
FB_WEIGHT = 0.7                 # FB followers discounted vs IG
NO_IG_DEMOGRAPHIC_PENALTY = 0.5 # FB-only / no-IG markets skew to a different/older demographic

# Entry-fee drag: admission factor + booth-fee band (booth weighted 60%).
# BOOTH_FEE_BANDS: first (cap, score) where booth_fee <= cap; else 1.0 (higher fee = lower score).
ADMISSION_FREE, ADMISSION_GATED = 5.0, 2.5
BOOTH_FEE_BANDS = [(0, 5.0), (50, 4.5), (100, 4.0), (200, 3.0), (350, 2.0), (600, 1.5)]
BOOTH_WEIGHT = 0.6

# Modifiers (0-1 multipliers applied to the quality score).
MODIFIERS = {
    "fine_art_focus":       {"none": 1.00, "partial": 0.90, "fine_art": 0.78},
    "same_day_competition": {"none": 1.00, "some": 0.92, "heavy": 0.85},
    "maturity":             {"established": 1.00, "newish": 0.95, "new": 0.88},
    "sport_conflict":       {"none": 1.00, "major": 0.90, "iron_bowl": 0.80},
    # Year-over-year momentum. Default "stable" — only flag "decline" with real evidence
    # (year-over-year attendance/vendor drop, scaled-back footprint, negative coverage). Reliable
    # per-year social data is scarce; see methodology doc for what's actually obtainable.
    "popularity_trend":     {"growing": 1.00, "stable": 1.00, "soft_decline": 0.93, "decline": 0.85},
    # BOOST (the one modifier allowed to exceed 1.0): a market that offers a discounted "junior
    # artisan" / "junior vendor" youth spot lets the 12-year-old seller participate cheaply, so it
    # is worth ranking higher. Often unadvertised — confirm with the organizer before scoring "yes".
    "junior_vendor":        {"none": 1.00, "no": 1.00, "yes": 1.10},
}
MODIFIER_DEFAULT = {"fine_art_focus": "none", "same_day_competition": "none",
                    "maturity": "established", "sport_conflict": "none", "popularity_trend": "stable",
                    "junior_vendor": "none"}

# Schedule fit (computed, not a simple lookup).
DAY_WINDOW = {"weekend": 1.00, "evening_ok": 1.00, "mixed_partial": 0.85, "weekday_daytime": 0.45}
DAYS_COMMITMENT = [(2, 1.00), (3, 0.93), (4, 0.85)]  # min_days <= key -> mult; else 0.78 (fallback)
# Time efficiency ($/hour): total hours on-site (hours_per_day x min_days) <= cap -> mult; else 0.72.
# A short single day beats a multi-day show; this is the preferred time penalty when hours are known.
TIME_EFFICIENCY = [(6, 1.00), (10, 0.97), (16, 0.90), (24, 0.82)]

MODIFIER_KEYS = list(MODIFIERS.keys()) + ["schedule"]  # column order for output

# ============================ PARSING HELPERS ===============================

def _num(v):
    """Parse a number, tolerating $ and commas; None if blank/invalid."""
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _pos(v):
    """Positive number or None (treats 0 / blank as 'no data')."""
    n = _num(v)
    return n if (n and n > 0) else None


def _bool(v):
    return str(v).strip().lower() in ("yes", "y", "true", "1")


def _req(v, default=3.0):
    """Parse a required 1-5 criterion; fall back to a neutral default if blank/missing
    so one bad cell degrades gracefully instead of aborting the whole run."""
    n = _num(v)
    return n if n is not None else default


def _band(value, bands, below=1.0):
    """Return the score for the first (threshold, score) where value >= threshold (bands hi->lo)."""
    for threshold, score in bands:
        if value >= threshold:
            return score
    return below

# ========================= QUALITY COMPONENT SCORES =========================

def affluence_affinity_score(income, destination_pull, affinity_nonprofit, has_ig=True):
    """Local 10-mi income -> 1-5, with destination/affinity/non-profit override; small
    demographic penalty if the market has no Instagram (or IG-parent) presence."""
    override = destination_pull or affinity_nonprofit
    if income is None:
        base = OVERRIDE_FLOOR if override else NEUTRAL_AFFLUENCE
    else:
        base = _band(income, INCOME_BANDS)
        if override:
            base = max(base, OVERRIDE_FLOOR)
    if not has_ig:
        base = max(1.0, base - NO_IG_DEMOGRAPHIC_PENALTY)
    return base


def social_reach_score(ig_followers, fb_followers, fallback=None):
    """Popularity/attendance proxy from social following (IG weighted higher). Falls back to a
    manual reach estimate (or 2.0) when no follower data exists."""
    if ig_followers is None and fb_followers is None:
        return fallback if fallback is not None else 2.0
    eff = max(ig_followers or 0, FB_WEIGHT * (fb_followers or 0))
    return _band(eff, SOCIAL_BANDS, below=2.0)


def entry_fee_drag_score(free_admission, ticketed, booth_fee):
    """Higher = lower barrier. Booth fee (the vendor's out-of-pocket risk) weighted 60% vs
    admission 40%. If booth fee is unpublished (apply-only), score on admission alone."""
    admission = ADMISSION_FREE if (free_admission and not ticketed) else ADMISSION_GATED
    if booth_fee is None:
        return round(admission, 2)
    booth = 1.0
    for cap, score in BOOTH_FEE_BANDS:  # ascending caps: higher fee -> lower score
        if booth_fee <= cap:
            booth = score
            break
    return round((1 - BOOTH_WEIGHT) * admission + BOOTH_WEIGHT * booth, 2)


def has_instagram(ig_handle):
    h = str(ig_handle or "").strip().lower()
    return bool(h) and "fb only" not in h and h not in ("none", "n/a", "not found", "-")

# ============================= MODIFIERS ====================================

def days_commitment_mult(min_days):
    if min_days is None:
        return 1.0
    return _band(-min_days, [(-k, v) for k, v in DAYS_COMMITMENT], below=0.78)


def time_efficiency_mult(total_hours):
    """Fewer total hours on-site = better $/hour. None if hours unknown."""
    if total_hours is None:
        return None
    for cap, mult in TIME_EFFICIENCY:
        if total_hours <= cap:
            return mult
    return 0.72


def on_site_hours(m):
    hpd = _num(m.get("hours_per_day"))
    md = _num(m.get("min_days"))
    return hpd * (int(md) if md else 1) if hpd else None


def effective_hours(m):
    """On-site hours + round-trip drive from Birmingham (travel is time that dilutes $/hour)."""
    base = on_site_hours(m)
    return None if base is None else base + (_num(m.get("drive_rt_hrs")) or 0)


def schedule_mult(m):
    """Day/time fit (school) × time efficiency (on-site + drive hours; days fallback)."""
    day = DAY_WINDOW.get(str(m.get("day_window", "")).strip().lower() or "weekend", 1.0)
    eff = time_efficiency_mult(effective_hours(m))
    if eff is None:  # no hours data -> fall back to a days-only penalty
        md = _num(m.get("min_days"))
        eff = days_commitment_mult(int(md) if md else None)
    return round(day * eff, 3)


def modifier_multipliers(m):
    """All modifiers (fine-art, competition, maturity, sport, popularity, junior-vendor boost,
    schedule) and their product. Most are 0-1 penalties; junior_vendor can exceed 1.0 as a boost."""
    mults = {}
    for factor, table in MODIFIERS.items():
        key = str(m.get(factor, "")).strip().lower() or MODIFIER_DEFAULT[factor]
        mults[factor] = table.get(key, table[MODIFIER_DEFAULT[factor]])
    mults["schedule"] = schedule_mult(m)
    total = 1.0
    for v in mults.values():
        total *= v
    return mults, round(total, 3)

# ============================== SCORING =====================================

def score_market(m):
    has_ig = has_instagram(m.get("ig_handle"))
    crit = {
        "premium_positioning": _req(m.get("premium_positioning")),
        "affluence_affinity": affluence_affinity_score(
            _num(m.get("median_income_10mi")), _bool(m.get("destination_pull")),
            _bool(m.get("affinity_or_nonprofit")), has_ig),
        "foot_traffic_access": _req(m.get("foot_traffic")),
        "reach": social_reach_score(_pos(m.get("ig_followers")), _pos(m.get("fb_followers")),
                                    fallback=_num(m.get("reach"))),
        "vendor_density": _req(m.get("vendor_density")),
        "scale": _req(m.get("scale")),
        "entry_fee_drag": entry_fee_drag_score(
            _bool(m.get("free_admission")), _bool(m.get("ticketed")), _num(m.get("booth_fee"))),
    }
    quality = sum(crit[k] * WEIGHTS[k] for k in WEIGHTS) / WEIGHT_SUM
    mults, drag_total = modifier_multipliers(m)
    return crit, round(quality, 2), mults, drag_total, round(quality * drag_total, 2)


def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else "markets_input.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else "markets_scored.csv"
    with open(inp, newline="") as fh:
        markets = list(csv.DictReader(fh))

    rows = []
    for m in markets:
        crit, quality, mults, drag_total, final = score_market(m)
        row = {"name": m["name"], "FINAL": final, "quality": quality}
        row.update({k: round(v, 2) for k, v in crit.items()})
        row.update({f"x_{k}": v for k, v in mults.items()})
        row["x_total_drag"] = drag_total
        row["notes"] = m.get("notes", "")
        rows.append(row)
    rows.sort(key=lambda r: r["FINAL"], reverse=True)

    fields = (["rank", "name", "FINAL", "quality"] + list(WEIGHTS.keys())
              + [f"x_{k}" for k in MODIFIER_KEYS] + ["x_total_drag", "notes"])
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            r["rank"] = i
            w.writerow(r)

    print(f"Scored {len(rows)} markets | quality weights sum={WEIGHT_SUM}\n")
    print(f"{'#':<3}{'Market':<26}{'FINAL':>6}{'Qual':>6}   "
          + "".join(f"{k.split('_')[0][:6]:>7}" for k in MODIFIER_KEYS) + f"{'drag':>7}")
    for i, r in enumerate(rows, 1):
        print(f"{i:<3}{r['name'][:25]:<26}{r['FINAL']:>6}{r['quality']:>6}   "
              + "".join(f"{r['x_' + k]:>7}" for k in MODIFIER_KEYS) + f"{r['x_total_drag']:>7}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
