---
name: market-manager
description: >-
  End-to-end workflow for a maker/vendor to routinely FIND, EVALUATE, PLAN, REGISTER for,
  PARTICIPATE in, and REMEMBER local craft, farmers, artisan, holiday, and pop-up markets in a
  home region and nearby drivable cities. Use this whenever the user wants to discover new markets
  to sell at, score or compare markets, decide whether a market is worth its booth fee / drive /
  time commitment, build a market calendar or season schedule, resolve date conflicts, track
  vendor application deadlines, prepare for a market, or log results afterward. Trigger for
  requests like "find me markets," "is this market worth it," "should I do this market," "plan my
  market season," "which markets should I apply to," "build a vendor calendar," "compare these
  craft fairs," or any booth / vendor-fair / maker-market planning — even if the user never says
  the word "skill." Built for HoneyBeeham (premium beeswax candles + local honey, Birmingham AL),
  but the home base, products, and constraints are configurable at the top.
---

# Market Manager

A repeatable system for a small vendor to run their market program end to end. It turns the messy,
recurring job of "which markets should we do, and when?" into six clear capabilities. The intent is
not a one-time analysis but a living loop: the data and calendar improve every season as real
results come in.

## The six capabilities

1. **Find** — discover candidate markets in the home region and nearby cities.
2. **Evaluate** — score each market for fit, cost, time, and audience.
3. **Plan** — turn scores into a bookable, conflict-free calendar.
4. **Register** — apply to the chosen markets and track deadlines/status.
5. **Participate** — show up prepared and capture what actually happened.
6. **Remember** — persist data, results, and learnings so next season starts smarter.

Work through them in order for a full season plan, or jump to one (e.g., "is this market worth it?"
is just **Evaluate**; "what's on the calendar?" is **Plan**). Always tell the user which capability
you're operating in so the workflow stays legible.

## Configuration (defaults — confirm/adjust per user)

These parameters drive every capability. For a new user, confirm them up front; for HoneyBeeham
they are already set:

- **Home base:** Birmingham, AL. **Travel range:** Huntsville (~3h round trip), Chattanooga (~4h),
  Atlanta (~5h), Nashville (~6h), Franklin (~6.5h).
- **Products:** premium handmade beeswax candles ($15–25) + local raw honey ($20/jar). Honey profit
  is markets-only (storefront honey revenue goes to the family supplier, not the business).
- **Seller constraint:** Charley Ann is 12 and in school → markets must be Fri/Sat/Sun, or a weekday
  after 3 p.m.; multi-day shows are costly.
- **Capacity:** ~2 markets/month, up to 4 in Nov–Dec.
- **Best-fit audience:** curated artisan / holiday markets; NOT fine-art-only or produce-only shows.

## Grounding rules (apply throughout)

This skill informs real money and time decisions, so accuracy matters more than completeness.

- **Never fabricate** a fee, date, attendance, or follower count. Cite a source for each external
  figure; if it isn't published, write "apply-only" / "not found" / "(est.)" and say so.
- **External signals predict quality, not booth economics.** The score is a prior; the user's own
  take-home results are the truth. Always weigh them together — the model is known to under-rate
  proven free family markets where real $/hour is high.
- **Most booth fees are application-only** (a quote after acceptance) and **most future dates are
  unannounced** — flag both rather than guessing.

---

## 1. FIND

**Goal:** a candidate list of markets worth evaluating, across the home metro + drivable cities.

Most strong fits are *not* on the open web — pop-up and brewery markets are Instagram-native. Cover
all of these channels (see `references/finding_markets.md` for the full playbook):

- Official market sites and vendor portals (ZAPPlication, Eventeny, Submittable, EventHub, ManageMyMarket).
- **Instagram-native discovery:** organizer accounts, neighborhood/community accounts (a market is
  often run under the town/merchant-association handle), brewery event calendars, geotags, and local
  hashtags (e.g., #bhammarket, #shoplocalbham).
- Local roundups (city "Now" blogs, Mom Collective holiday-market lists).
- Vendor word-of-mouth / Facebook vendor groups (often the only place fees appear).

**Output:** append rows to the working dataset (`markets_candidates_input.csv`) with at least
`name`, city, venue, type, and a source link. Don't score yet — just capture the universe.

When a task implies discovery in an app the user has connected (Google Drive for prior research,
etc.), use it. If no market data exists yet, start from the channels above.

---

## 2. EVALUATE

**Goal:** a fit score for each market that respects audience, cost, time, and travel.

The scoring engine is `scripts/market_scorer.py`. It computes, per market:

```
FINAL = QUALITY (7 weighted criteria, 0–5)  ×  MODIFIERS (each 0–1)
```

Quality = premium positioning, local affluence, foot traffic, social reach, vendor density, scale,
entry-fee drag. Modifiers = fine-art-focus, same-day competition, maturity, sport conflict,
popularity trend, and schedule fit (school days + total hours on-site **including round-trip drive**
— the $/hour lever). The full rubric, bands, and rationale are in `references/methodology.md`; the
exact input columns and how to fill them are in `references/input_schema.md`.

**Process:**
1. For each candidate, research the inputs and record them in the CSV (`assets/markets_template.csv`
   is a starter with the column header). Compute-able fields (income, social reach, fees, hours,
   drive) come from research; judgment fields (premium positioning, foot traffic, vendor density,
   scale) are 1–5 analyst calls from public signals — note when they're estimates.
2. Run it:
   ```bash
   python3 scripts/market_scorer.py markets_candidates_input.csv markets_candidates_scored.csv
   ```
   Edit the `WEIGHTS`, `*_BANDS`, and `MODIFIERS` constants at the top of the script to re-tune; the
   score auto-normalizes. Adding a market = appending a CSV row.
3. Present the ranked list, and **flag the limitations honestly** (estimates, apply-only fees, the
   under-rating of proven free markets).

> **Planned enhancement (Evaluate v2 — not yet built):** regularly poll each market's social
> accounts and website and catalog recent posts to detect, per year: application deadlines, location
> changes, engagement/sentiment trends, vendor lists, and similar/competing vendors. This will feed
> the `popularity_trend` modifier and the deadline tracker with live data instead of one-time
> research. Leave a clear seam for it: the `popularity_trend` input and per-market source links
> already exist.

---

## 3. PLAN

**Goal:** a dated, conflict-free calendar — one market per slot, sized to capacity.

Three steps turn scores into a schedule:
1. **Filter** to availability-compatible markets (the schedule modifier already penalizes school-day
   conflicts; drop anything it crushes).
2. **Apply capacity** (~2/month, up to 4 in peak holiday months).
3. **Resolve same-date overlaps** — you can only be one place. When two recommended markets share a
   weekend, pick the **local / shorter-drive** option (which also wins on $/hour). Mark the winner
   **GO**, the loser **DEFER** (save for a year its weekend is open), and school conflicts **SKIP**.
   Multi-weekend markets are the relief valve for crowded dates.

Label dates **(announced)** vs **(est.)** and verify before relying on them. Output a calendar with a
clear pick column plus an application-deadline tracker.

---

## 4. REGISTER

**Goal:** actually get the booths, on time.

- Maintain a **deadline tracker** (market, open/close dates, action). Common windows: brewery/pop-up
  apps are rolling/DM; juried shows close 4–8 weeks before; some open a fixed date (e.g., a holiday
  market each July, a flagship farmers market each September).
- Because most fees are quote-on-acceptance, **draft a short vendor-inquiry message** when asked, and
  always confirm four things before committing: **fee, date, hours, and whether a one-day option
  exists** for a multi-day show (a single-day booth can rescue an otherwise school-blocked market).
- Record application **status** per market (researching → applied → waitlisted → accepted → booked).

---

## 5. PARTICIPATE

**Goal:** show up prepared, and capture what actually happened (this is what makes the model smarter).

- **Pre-market:** confirm inventory (candles by SKU; honey jars sourced from the supplier), booth
  kit, payment method, load-in time, and the day's hours.
- **Post-market — log the result:** date, market, entry fee paid, total sales, honey vs candle split,
  hours worked, and qualitative notes (crowd size, weather, competing vendors, what sold). Compute
  **take-home** = sales − entry fee − honey cost, and **$/hour** = take-home ÷ (hours + drive).

This results log is the ground truth that the external score is validated against.

---

## 6. REMEMBER

**Goal:** persist everything so each season compounds.

Keep these artifacts current and reuse them every cycle:
- **`markets_candidates_input.csv`** — the scored dataset (grows as new markets are found).
- **Results log** — actual take-home and $/hour per market done (the validation set).
- **Calendar** — current plan + deadline tracker.
- **Learnings** — durable notes: which markets over/under-perform their score, organizer quirks,
  confirmed fees/one-day options, and any market that closed or moved.

Re-run the scorer whenever inputs change. When recommending, **reconcile score vs. actual take-home**
— if a proven market keeps beating its score, trust the results and note why (e.g., affluent local
crowd + short hours the rubric can't fully see).

---

## Bundled resources

- `scripts/market_scorer.py` — the scoring engine (stdlib Python; run on a market CSV).
- `references/methodology.md` — full rubric: criteria, weights, modifiers, schedule/$-per-hour/drive,
  validation, and the score-to-calendar process.
- `references/input_schema.md` — every CSV column, what it means, and how to fill it.
- `references/finding_markets.md` — the discovery playbook (where/how to find markets, esp. IG-native).
- `assets/markets_template.csv` — starter CSV with the column header and two example rows.

## Iteration roadmap

This skill is meant to grow. Near-term enhancements the user has flagged:
- **2a — Social polling:** routinely fetch each market's IG/FB and website and catalog recent posts.
- **2b — Content retention:** extract and store current-year deadlines, location changes, engagement,
  sentiment, vendor lists, and similar vendors — feeding `popularity_trend` and the deadline tracker.
