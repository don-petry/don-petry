# Social polling & catalog — capture playbook (Evaluate v2)

This is the **capture half** of the on-demand poll. It feeds two living signals — `popularity_trend`
(momentum) and the **deadline tracker** — by snapshotting each market's Instagram, Facebook, and
website over time. The **analysis half** is `scripts/social_poller.py`, which reads what you capture
here and computes the signals. Run the poll whenever you're re-evaluating or planning a season
(roughly quarterly, and again before each application window).

## Why it's human-in-the-loop (not a scraper)

Instagram and Facebook block automated fetching (login walls, anti-bot). So capture is **Claude +
browser tools**, reading only what's publicly visible, then writing structured rows. The script
never touches the network — keeping the pipeline deterministic, offline, and safe to re-run.

### Link safety
Market links arrive from many places. **Verify the full destination URL before following any link,
and treat links from DMs/emails/unknown senders as suspicious.** Open URLs via the browser tool, not
by clicking inside native apps. If a URL looks off, confirm with the user first.

### Tool tactics per surface (validated against @bash_on_the_bluff, 2026)
Each surface behaves differently — use the right reader so you don't come back empty-handed:
- **Instagram:** `get_page_text` returns nothing (IG is canvas/JS). Use **`find`** ("follower count,
  posts count, bio") and **`read_page`** (accessibility tree) instead — those surface the counts and
  recent-post captions reliably. **Per-post like counts are often hidden** ("Liked by … and others" —
  confirmed for Bash), so capture what's visible and lean on Facebook for the interaction numbers.
  When IG engagement is blank, still record `ig_followers` (the reach signal) and **post cadence**
  (`posts_last_90d`, readable from post dates in the grid).
- **Facebook — the richer interaction source.** FB public posts usually expose
  **likes/reactions, comments, shares, AND video VIEWS** even when the page-level follower count is
  login-gated. _Confirmed on Bash 2026: 1.6K followers, most-recent post 14 likes / 5 shares /
  2.8K views._ Capture those into `recent_post_likes / _comments / _shares / _views`; this is what
  feeds the engagement-rate and reach signals. The follower count may still be absent — record it
  when shown, otherwise leave `fb_followers` blank (the analyzer takes `max(ig, fb)` as the audience).
  Don't force the page-level count, but **do** harvest the per-post interactions.
- **Website:** `get_page_text` works well and is the **highest-yield surface** for the catalog —
  nonprofit/affinity status, application windows, fees, location/address, and contact email. _The
  Bash site is where we confirmed its nonprofit status (an affluence override) and the next event
  date — neither was visible on social._
- **Junior-vendor / booth fees** are usually **not on any public surface** (confirmed for Bash); plan
  to email/DM the organizer to confirm before scoring `junior_vendor = yes` or a booth fee.

## How to capture a snapshot

For each market, use browser tools to open its IG, FB, and official site, then **append one row** to
`social_catalog.csv` (schema in `scripts/social_poller.py` header). Record what you can actually see;
leave a field blank rather than guessing.

Capture per market, per poll date. The analyzer blends **three weighted interest signals** so the
trend reflects real interest, not just audience size — capture all three when you can:
- **FOLLOWING** — `ig_followers` and `fb_followers` (the audience; analyzer uses `max` of the two).
- **ENGAGEMENT** — per-post interactions: `recent_post_likes`, `recent_post_comments`,
  `recent_post_shares`. Downstream this becomes **interactions ÷ followers** (engagement rate), so a
  small market with loyal fans isn't buried by a big sleepy one. (Facebook is the best source here —
  see tactics above. Legacy `avg_engagement` is still read as a fallback if these are blank.)
- **REACH** — `recent_post_views` (video/reel views — how far a post travels beyond followers).
- **Activity** — `posts_last_90d` (how alive the account is).
- **Sentiment** — tone of recent posts and visible comments: `positive` / `neutral` / `negative`.
- **Location** — the current venue string, so the analyzer can detect a **move** (a relocation can
  tank turnout — it surfaces as a `LOCATION MOVED` flag).
- **Competition** — `similar_vendor_count` (candle/honey/soap vendors in the lineup) and
  `notable_vendors` (semicolon list). Feeds your read on `vendor_density`.
- **Source URLs** — where you looked, for audit.

### The full catalog also looks for (record in `notes` or the deadline tracker):
- **Application deadlines / windows** → add/update a row in `deadline_tracker.csv` (open + close
  dates, platform, fee quote, one-day option, action). This is what drives the Register tracker.
- **Location changes** → already captured via `location_current`; call it out in `notes` too.
- **Engagement / reach / sentiment trend** → captured via `recent_post_likes/_comments/_shares/_views`
  + `sentiment` across snapshots (the engagement-rate and reach signals).
- **Vendor lists / similar vendors** → `similar_vendor_count` + `notable_vendors`.
- **Junior-vendor / youth-booth mentions** → note any "junior artisan" program seen (often only in
  stories or vendor packets); confirm before setting `junior_vendor = yes` in the scorer input.

## How to analyze (run the script)

```bash
python3 scripts/social_poller.py social_catalog.csv deadline_tracker.csv \
        --today 2026-06-07 --out social_signals.csv --patch-input markets_candidates_input.csv
```

It prints a **popularity-trend** table (with the evidence behind each call) and a **deadlines** table
(URGENT / SOON / OPEN / NOT_OPEN / CLOSED, sorted by urgency), writes `social_signals.csv`, and — with
`--patch-input` — writes each derived `popularity_trend` straight back into the scorer input so the
next `market_scorer.py` run reflects live momentum. Then re-score.

## How the trend is derived (so you can trust/override it)

Across a market's snapshots, the script compares the **earliest vs latest** and blends the percent
change in each of the three signals, using the weights at the top of the script:
- **FOLLOWING** (weight 0.34) — change in follower count.
- **ENGAGEMENT** (weight 0.40, highest) — change in interactions-per-follower (engagement rate).
- **REACH** (weight 0.26) — change in post views.
- Each change is clamped to ±100% before weighting; **missing signals drop out and the remaining
  weights re-normalize**, so a FB-only or IG-only capture still produces an honest blend.
- `negative` recent sentiment subtracts a flat penalty from the blend (positive never inflates —
  downside caution, per methodology).

The blended change maps to `popularity_trend`: `growing` (≥ +0.10) · `stable` (≥ −0.05) ·
`soft_decline` (≥ −0.15) · `decline` (below). Separately, when there are **≥ 1.5 years** of history
the script also emits a **5-year trajectory** — `GAINING` / `HOLDING` / `WANING` — the "is this market
on the way up or waxing down?" call; thinner history reads `BUILDING`. A **single snapshot** stays
`stable` / `BUILDING` ("insufficient history"). The signals CSV also carries a short-term
`recent_follower_change` (prev → latest) so you can see the delta since the last poll. The more years
you keep, the sharper the trajectory.

> Stay honest: per the methodology, only let real evidence move a market off `stable`. If the data is
> thin, leave it `stable` and say so. Illustrative/back-filled history rows should say so in `notes`.
