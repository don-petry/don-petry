# HoneyBeeham Market Scoring — Methodology (v6, canonical)

_Single source of truth. Supersedes `Market_Scoring_Rubric_v2.md` and `Market_Scoring_Rubric_v3.md`. Implemented in `market_scorer.py`; results in `markets_candidates_scored.csv` and the `Candidate_Scores_v4` + `Calendar_2026_2027` tabs of `HoneyBeeham_Market_Evaluation.xlsx`._

## What it does
Ranks markets for a **premium handmade beeswax-candle + local-honey** seller using **only externally observable signals** (no internal sales data), so it can be applied to any new market.

```
FINAL = QUALITY (7 weighted criteria, 0–5)  ×  MODIFIERS (each 0–1)
```
Quality = the market's intrinsic draw/fit. Modifiers = things that suppress turnout/fit for *this* seller on *this* date.

## Quality criteria (weights sum to 100)
| Criterion | Wt | 1 ↔ 5 |
|---|---|---|
| Premium/artisan positioning | 18 | family/produce festival ↔ curated artisan gift market |
| Local affluence & affinity | 18 | low 10-mi median income ↔ high (with override, below) |
| Foot-traffic volume & access | 18 | small/gated ↔ large free crowd |
| Reach (social) | 13 | **computed from IG/FB followers** (see below) |
| Vendor density | 12 | saturated with similar vendors ↔ you're rare |
| Scale | 11 | tiny ↔ many vendors / large footprint |
| Entry-fee drag | 10 | ticketed + pricey booth ↔ free + cheap |

**Affluence (median HH income → band):** ≥$110k→5 · $85–110k→4 · $65–85k→3 · $50–65k→2.5 · $40–50k→2 · <$40k→1. **Override:** if the market is a large *destination pull* OR a *high-affinity / non-profit-benefit* event, the affluence floor is lifted to **4.5** regardless of local income. Unknown income with no override → neutral 3.0.

**Reach (computed from social):** effective following = `max(IG, 0.7×FB)` → ≥50k→5 · 25–50k→4.5 · 12–25k→4 · 6–12k→3.5 · 2.5–6k→3 · 1–2.5k→2.5 · <1k→2. If no follower data, falls back to a manual estimate.

**No-Instagram demographic penalty:** a market with **no IG and no IG-parent account** (Facebook-only) loses **0.5** off its affluence/affinity score — FB-only audiences skew older/different from the premium-gift buyer.

**Entry-fee drag:** admission factor (free & non-ticketed = 5; ticketed = 2.5) blended with a booth-fee band (≤$50→4.5 … >$600→1.0), **weighted 60% booth / 40% admission** — the booth fee is the real out-of-pocket risk. Apply-only/unpublished fee → score on admission alone.

## Modifiers (0–1 multipliers)
| Modifier | Values → multiplier | Captures |
|---|---|---|
| **Fine-art focus** | none 1.0 · partial 0.90 · fine_art 0.78 | juried fine-art crowds aren't there for candles/honey |
| Same-day competition | none 1.0 · some 0.92 · heavy 0.85 | competing markets same area + day |
| Maturity | established 1.0 · newish 0.95 · new 0.88 | new/unknown markets draw smaller crowds |
| Sport conflict | none 1.0 · major 0.90 · **iron_bowl 0.80** | Iron Bowl / major college-football / big sport day |
| **Popularity trend** | growing/stable 1.0 · soft_decline 0.93 · decline 0.85 | year-over-year momentum |
| **Junior vendor (boost)** | none/no 1.0 · **yes 1.10** | kid-friendly market with a discounted youth booth |
| **Schedule fit** | day-window × time-efficiency | school fit + total hours on-site ($/hr) |

**Popularity trend (now data-fed — Evaluate v2.1):** default is `stable` — only flag `decline` with real evidence. This value is no longer a one-time guess: the **on-demand social poll** (`scripts/social_poller.py` over `social_catalog.csv`, playbook in `references/social_polling.md`) snapshots each market's IG/FB/website across time and derives the trend, then `--patch-input`s it back into the scorer CSV. Derivation blends **three weighted interest signals** by earliest→latest percent change: **FOLLOWING** (followers, w 0.34), **ENGAGEMENT** (interactions ÷ followers, w 0.40 — the highest, so loyal small audiences count), and **REACH** (post views, w 0.26); each change is clamped to ±100%, missing signals drop and the rest re-normalize, and `negative` sentiment subtracts a penalty (positive never inflates). Blend ≥ +0.10 → `growing`, ≥ −0.05 → `stable`, ≥ −0.15 → `soft_decline`, below → `decline`. With ≥1.5 years of snapshots it also emits a **5-year trajectory** — `GAINING` / `HOLDING` / `WANING` — the "on the way up or waxing down?" read; a single snapshot stays `stable` (insufficient history), so the signal sharpens the more you poll. Reliable per-year social data is still scarce — corroborate with **year-over-year vendor counts in news** and **coverage tone**; weak supplements are **Google Trends** and **archived follower snapshots**. _Example: a "Market Noel declined in 2025" perception was checked and **not supported** — vendor count held at 100+, footprint unchanged, coverage steady, 2026 moving up to the larger BJCC → scored `stable`._

**Junior-vendor boost (the one modifier > 1.0):** a market that offers a discounted **"junior artisan" / "junior vendor"** youth booth lets the 12-year-old seller participate cheaply and makes the day a family activity, so it earns a **×1.10** boost (`none`/`no` = 1.0). These programs are **frequently unadvertised** — _Bash on the Bluff offers one even though it isn't on the site_ — so actively look for it (organizer DM, vendor groups, prior-year flyers) and only score `yes` once confirmed. This is the sole modifier permitted to exceed 1.0; everything else is a 0–1 penalty.

**Schedule fit** = day-window × **time-efficiency**. Day-window: `weekend` or `evening_ok` (weekday after 3pm) = 1.0; `mixed_partial` 0.85; `weekday_daytime` 0.45. **Time-efficiency** = **effective hours** → ≤6h 1.0 · ≤10h 0.97 · ≤16h 0.90 · ≤24h 0.82 · >24h 0.72. Effective hours = on-site (`hours_per_day × min_days`) **+ round-trip drive from Birmingham** (`drive_rt_hrs`: Birmingham 0 · Tuscaloosa ~2 · Huntsville ~3 · Auburn ~4 · Chattanooga ~4 · Atlanta ~5 · Nashville ~6 · Franklin ~6.5). This is the **$/hour** lever: a 6-hr local single day beats both a 3-day show and a far-drive market — e.g., The Chattanooga Market's 5 on-site hrs + 4 drive = 9 effective (×0.97), and a Nashville show at 14 on-site + 6 drive = 20 (×0.82). **Use the one-day option** for multi-day markets — set `min_days` to the smallest commitment (e.g., Market Noel's 1-day Fri/Sat booth → min_days = 1, 8 hrs). If `hours_per_day` is blank, falls back to a days-only penalty (≤2 days 1.0; 3 → 0.93; 4 → 0.85; 5+ → 0.78).

## Decisions captured this session
1. External-only signals; pairs with real results over time — it predicts *quality*, not booth economics.
2. Affluence override for destination / affinity / non-profit markets.
3. Vendor-density criterion (intra-market competition for the same wallet).
4. Reach computed from real IG/FB followers; FB-only demographic penalty.
5. Fine-art penalty decouples "premium" from "fit."
6. Booth fee weighted 60% of fee-drag (the vendor's financial risk).
7. Date drags: same-day competing markets, newness, Iron Bowl / major sport days.
8. School-schedule fit (Fri/Sat/Sun or after-3pm) AND **time/$-per-hour efficiency** — fewer total hours on-site (hours/day × days) is better; a short single day beats a multi-day show.

## From scores to a calendar (recommendation process)
The score ranks markets; turning that into a bookable plan adds three steps, captured in the `Calendar_2026_2027` tab:
1. **Filter to school-compatible** markets (the schedule modifier already does this — a >0 score that isn't crushed by `weekday_daytime` / long hours).
2. **Apply capacity:** ~2 markets/month, up to 4 in November–December.
3. **Resolve same-date overlaps** (you can only be one place): when two recommended markets fall on the same weekend, pick the **local / shorter-drive** option — which also wins on $/hour. Each weekend gets one `GO`; the conflicting market is `DEFER` (save for a year its weekend is open). Multi-weekend markets (e.g., Chattanooga Holiday's two December weekends) are the relief valve for crowded dates.

Dates are labeled **(announced)** = organizer-confirmed vs **(est)** = projected from the 2025 pattern (verify before applying). 2026's four real clashes — Nov 14, Nov 21, Dec 5, Dec 12 — all resolve toward the local pick.

## Validation
On the 4 markets with known take-home, v6 orders **Deck > Bash > 20th** and lands **MadeSouth last** — matching actuals once reach reflects real followers. The refactored code was verified to reproduce identical scores, and two markets were hand-recomputed independently (Chattanooga Market 4.21; Christmas Village BJCC 4.14 × 0.351 = 1.45).

## How to run
```
python3 market_scorer.py <input.csv> <output.csv>
```
Edit the `WEIGHTS`, `*_BANDS`, and `MODIFIERS` constants at the top of `market_scorer.py` to re-tune; the score auto-normalizes by the weight sum. Add a market by appending a row to the input CSV.

## Honest limitations
- Qualitative 1–5 inputs (premium, foot-traffic, vendor-density, scale) and the modifier flags are analyst judgments from public signals; income, reach, and fee-drag are computed from data.
- Follower counts are snippet-derived approximations; many Facebook counts are hidden behind login walls.
- Most booth fees are application-only; most 2027 dates are unannounced. Verify fees and dates before applying.
