# Input CSV schema — `markets_candidates_input.csv`

One row per market. Blanks are handled gracefully (missing required fields fall back to a neutral
3.0). Run with: `python3 scripts/market_scorer.py <input.csv> <output.csv>`.

## Quality inputs (drive the 0–5 weighted criteria)

| Column | Type | How to fill |
|---|---|---|
| `name` | text | Market name (unique). |
| `premium_positioning` | 1–5 | Curated gift/artisan = 5; family/produce festival = 1. Analyst call from the market's framing/vendor mix. |
| `median_income_10mi` | USD | Median household income within ~10 mi of the venue (cite a ZIP-income source). Blank → neutral. |
| `destination_pull` | yes/no | Large enough to pull affluent shoppers from >10 mi? Triggers the affluence override. |
| `affinity_or_nonprofit` | yes/no | High-affinity group or non-profit-benefit event? Triggers the affluence override. |
| `foot_traffic` | 1–5 | Crowd volume / access; big free crowd = 5. |
| `scale` | 1–5 | Vendor count / physical size (NOT age — see `maturity`). |
| `vendor_density` | 1–5 | 5 = few competing candle/honey/craft vendors inside (you're rare); 1 = saturated. |
| `ig_handle` | text | Instagram handle (or "@parent (parent)"). Blank or "(FB only)" = no IG → small demographic penalty. |
| `ig_followers` | number | Instagram follower count. Drives reach (weighted higher than FB). |
| `fb_followers` | number | Facebook follower/like count. |
| `reach` | 1–5 | FALLBACK only — used if both follower counts are blank. |
| `free_admission` | yes/no | Free for shoppers to attend. |
| `ticketed` | yes/no | Paid admission (gates the casual crowd). |
| `booth_fee` | USD | Vendor booth/space fee. Blank = apply-only (scored on admission alone). |

## Modifier inputs (0–1 multipliers)

| Column | Allowed values | Meaning |
|---|---|---|
| `fine_art_focus` | none / partial / fine_art | Juried fine-art show whose crowd isn't buying candles/honey → strong penalty. |
| `same_day_competition` | none / some / heavy | Competing markets in the same area on the same day. |
| `maturity` | established / newish / new | New/unknown markets draw smaller crowds. |
| `sport_conflict` | none / major / iron_bowl | Significant same-day sport event (Iron Bowl / major college football). |
| `popularity_trend` | growing / stable / soft_decline / decline | Year-over-year momentum. Default stable; flag decline only with evidence. **Auto-populated** by `scripts/social_poller.py --patch-input`, which blends weighted FOLLOWING/ENGAGEMENT/REACH signals across `social_catalog.csv` snapshots (Evaluate v2.1) — see `references/social_polling.md`. |
| `junior_vendor` | none / no / yes | **Boost (>1.0):** market offers a discounted "junior artisan" / "junior vendor" youth booth so the 12-year-old seller can participate cheaply → ranks higher. Often **unadvertised** — ask the organizer before scoring "yes" (e.g., Bash on the Bluff). |

## Schedule & time inputs

| Column | Type | Meaning |
|---|---|---|
| `day_window` | weekend / evening_ok / mixed_partial / weekday_daytime | weekend = Fri/Sat/Sun; evening_ok = weekday after 3 p.m.; mixed_partial = multi-day spanning a school day; weekday_daytime = school-hours weekday (near-disqualifying). |
| `min_days` | integer | Minimum days the vendor must attend. **Use the one-day option** if the market offers one. |
| `hours_per_day` | number | Shopper hours per day (e.g. Sat 11–5 = 6). |
| `drive_rt_hrs` | number | Round-trip drive hours from home base (Birmingham = 0; Tuscaloosa ~2; Huntsville ~3; Auburn ~4; Chattanooga ~4; Atlanta ~5; Nashville ~6; Franklin ~6.5). Added to on-site hours for $/hour. |

## Notes columns (ignored by scoring, used in the sheet)

| Column | Use |
|---|---|
| `notes` | Free text — context, proven take-home, flags. |
| `fee_note` | Fee detail + schedule note + inquiry flags (e.g., "$899/10x10 (5-day) — no 1-day option, SKIP"). |

## Output columns (`..._scored.csv`)
`rank, name, FINAL, quality`, the seven quality sub-scores, the modifier multipliers
(`x_fine_art_focus … x_junior_vendor … x_schedule`), `x_total_drag`, and `notes`. Sorted by FINAL
descending.

## Companion files (Evaluate v2.1 poll)
Two tracker CSVs feed `popularity_trend` and the deadline tracker; their full schemas live in the
header of `scripts/social_poller.py`, with starters in `assets/`:
- **`social_catalog.csv`** — append-only poll snapshots (market, date_polled, ig/fb_followers,
  posts_last_90d, recent_post_likes, recent_post_comments, recent_post_shares, recent_post_views,
  sentiment, location_current, similar_vendor_count, notable_vendors, source_urls, notes). The
  poller blends three weighted signals — FOLLOWING (followers), ENGAGEMENT (interactions ÷ followers),
  REACH (views) — into the trend and a 5-year GAINING/HOLDING/WANING trajectory. (Legacy
  `avg_engagement` is still read as an interactions fallback.)
- **`deadline_tracker.csv`** — application windows (market, app_platform, app_opens, app_closes,
  status, action, fee_quote, one_day_option, source_url, last_checked).
