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
5. **Participate** — show up prepared for each market.
6. **Remember** — log what actually happened, persist data, and distill learnings so next season starts smarter.

Work through them in order for a full season plan, or jump to one (e.g., "is this market worth it?"
is just **Evaluate**; "what's on the calendar?" is **Plan**). Always tell the user which capability
you're operating in so the workflow stays legible.

## Configuration (defaults — confirm/adjust per user)

These parameters drive every capability. For a new user, confirm them up front; for HoneyBeeham
they are already set:

- **Home base:** Birmingham, AL. **Travel range:** Tuscaloosa (~2h round trip), Huntsville (~3h),
  Auburn (~4h), Chattanooga (~4h), Atlanta (~5h), Nashville (~6h), Franklin (~6.5h). **Tuscaloosa
  and Auburn are priority college towns** (Univ. of Alabama / Auburn Univ.) — affluent, expendable
  income that skews eco-friendly, farm-friendly, and buys candles; scout them, but watch home
  football Saturdays (`sport_conflict`).
- **Products:** premium handmade beeswax candles ($15–25) + local raw honey ($20/jar). Honey profit
  is markets-only (storefront honey revenue goes to the family supplier, not the business).
- **Seller constraint:** Charley Ann is 12 and in school → markets must be Fri/Sat/Sun, or a weekday
  after 3 p.m.; multi-day shows are costly. Because she sells, **kid-friendly markets that offer a
  discounted "junior artisan" / "junior vendor" youth booth rank higher** (see Evaluate).
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
popularity trend, the **junior-vendor boost**, and schedule fit (school days + total hours on-site
**including round-trip drive** — the $/hour lever). The full rubric, bands, and rationale are in
`references/methodology.md`; the exact input columns and how to fill them are in
`references/input_schema.md`.

**Kid-friendly markets rank higher.** Because the seller is 12, a market that offers a discounted
**"junior artisan" / "junior vendor"** youth booth earns a ×1.10 boost (`junior_vendor = yes`) — it
lets Charley Ann participate cheaply and makes the day a family activity. These programs are
**frequently unadvertised**: don't assume the absence of a web mention means it's missing. Actively
look — DM the organizer, check vendor Facebook groups and prior-year flyers — and only score `yes`
once confirmed. _Bash on the Bluff offers one even though it isn't on the site._

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

> **Evaluate v2.1 — social polling & catalog (built):** the `popularity_trend` modifier is no longer a
> one-time guess. Run the **on-demand poll** (`references/social_polling.md` + `scripts/social_poller.py`)
> to snapshot each market's IG/FB/website over time and catalog deadlines, location changes, interaction
> trends, and vendor lists. Capture is Claude + browser tools (social platforms block scrapers). The
> script blends **three weighted interest signals — FOLLOWING (followers), ENGAGEMENT (interactions ÷
> followers), REACH (post views)** — into `popularity_trend` plus a multi-year **GAINING/HOLDING/WANING
> trajectory** ("is this market on the way up or waxing down?"), and can `--patch-input` the trend
> straight back into the scorer CSV. Facebook is the richest interaction source (per-post likes /
> comments / shares / views). Re-score after polling. See the **Register** and **Remember** steps for how
> the same poll feeds the deadline tracker and the catalog.

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

- Maintain a **deadline tracker** (`assets/deadline_tracker_template.csv`: market, open/close dates,
  status, action, fee quote, one-day option). Common windows: brewery/pop-up apps are rolling/DM;
  juried shows close 4–8 weeks before; some open a fixed date (e.g., a holiday market each July, a
  flagship farmers market each September). The **social poll** (§2, Evaluate v2) populates this file
  and `scripts/social_poller.py` ranks windows by urgency (URGENT / SOON / OPEN / NOT_OPEN / CLOSED)
  so nothing lapses.
- Because most fees are quote-on-acceptance, **draft a short vendor-inquiry message** when asked, and
  always confirm four things before committing: **fee, date, hours, and whether a one-day option
  exists** for a multi-day show (a single-day booth can rescue an otherwise school-blocked market).
- Record application **status** per market (researching → applied → waitlisted → accepted → booked).

---

## 5. PARTICIPATE

**Goal:** show up prepared for each market.

- **Pre-market:** confirm inventory (candles by SKU; honey jars sourced from the supplier), booth
  kit, payment method, load-in time, and the day's hours.
- If Charley Ann is working a **junior-vendor booth**, prep her setup and confirm the youth-booth
  terms with the organizer.

Logging what happened afterward belongs with persistence — see **Remember** (§6).

---

## 6. REMEMBER

**Goal:** capture what actually happened and persist everything so each season compounds. Logging a
result and reconciling it against the score are the same job — the results log **is** the ground
truth the external score is validated against — so they live together here.

**Log the result (right after each market):**
- Record: date, market, entry fee paid, total sales, honey vs candle split, hours worked, and
  qualitative notes (crowd size, weather, competing vendors, what sold, and whether the
  junior-vendor booth helped).
- Compute **take-home** = sales − entry fee − honey cost, and **$/hour** = take-home ÷ (hours +
  drive). Append the row to the results log.

**Keep these artifacts current** and reuse them every cycle:
- **`markets_candidates_input.csv`** — the scored dataset (grows as new markets are found).
- **Results log** — actual take-home and $/hour per market done (the validation set).
- **`social_catalog.csv`** — append-only poll snapshots (followers, per-post likes/comments/shares/
  views, sentiment, location, vendors). This is the history `social_poller.py` derives momentum and the
  5-year trajectory from — the more polls, the sharper the `popularity_trend`.
- **Calendar + `deadline_tracker.csv`** — current plan and application windows.
- **Learnings** — durable notes: which markets over/under-perform their score, organizer quirks,
  confirmed fees/one-day options, **confirmed junior-vendor programs**, and any market that closed
  or moved.

**Reconcile score vs. actual.** Re-run the scorer whenever inputs change. When recommending, weigh
the score against real take-home — if a proven market keeps beating its score, trust the results and
note why (e.g., affluent local crowd + short hours the rubric can't fully see).

---

## Bundled resources

- `scripts/market_scorer.py` — the scoring engine (stdlib Python; run on a market CSV).
- `scripts/social_poller.py` — Evaluate v2.1 analyzer: blends weighted following/engagement/reach
  snapshots into `popularity_trend` + a 5-year GAINING/HOLDING/WANING trajectory + a ranked deadline
  tracker; can `--patch-input` the trend back into the scorer CSV.
- `references/methodology.md` — full rubric: criteria, weights, modifiers, schedule/$-per-hour/drive,
  validation, and the score-to-calendar process.
- `references/input_schema.md` — every CSV column, what it means, and how to fill it.
- `references/finding_markets.md` — the discovery playbook (where/how to find markets, esp. IG-native).
- `references/social_polling.md` — the capture playbook for the on-demand social/website poll.
- `assets/markets_template.csv` — starter scorer CSV with the column header and two example rows.
- `assets/social_catalog_template.csv` — starter poll-snapshot log (one row per market per poll).
- `assets/deadline_tracker_template.csv` — starter application-deadline tracker.

## Iteration roadmap

This skill is meant to grow. Status of flagged enhancements:
- **2a — Social polling (shipped):** on-demand snapshot of each market's IG/FB/website via browser
  tools into `social_catalog.csv`. See `references/social_polling.md`.
- **2b — Content retention (shipped):** snapshots persist current-year deadlines, location changes,
  per-post engagement/reach, sentiment, and vendor lists; `social_poller.py` derives `popularity_trend`
  and a ranked deadline tracker from them, closing the loop into the scorer.
- **2c — Multi-year interest trajectory (shipped):** weighted FOLLOWING/ENGAGEMENT/REACH signals across
  up to 5 years of snapshots yield a GAINING/HOLDING/WANING trajectory plus a short-term delta since the
  last poll — so a market's rise or wane is evidence-backed, not vibes.
- **Next ideas:** auto-suggest `vendor_density` from `similar_vendor_count` history; alerting when a
  tracked deadline crosses into URGENT.
