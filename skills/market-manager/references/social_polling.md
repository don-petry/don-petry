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
  confirmed for Bash), so `avg_engagement` may be uncapturable from public view; when it is, fall back
  to **post cadence** (`posts_last_90d`, readable from post dates in the grid) and visible **comment
  counts** as the activity proxy. With engagement blank, the trend derives from the follower delta
  alone — which is why a market can read `stable` even while clearly active.
- **Facebook:** follower/like counts are frequently **login-gated or simply absent** from the tree —
  expect to leave `fb_followers` blank and lean on IG for reach. Don't burn time forcing it.
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

Capture per market, per poll date:
- **Followers** — IG and FB counts (the reach signal; IG weighted higher downstream).
- **Activity** — `posts_last_90d` (how alive the account is) and `avg_engagement` (avg likes +
  comments on recent posts — the momentum signal).
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
- **Engagement / sentiment trend** → captured via `avg_engagement` + `sentiment` across snapshots.
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

Across a market's snapshots, the script compares the **earliest vs latest** and scores momentum:
- follower change ≥ +10% → +1, ≤ −10% → −1 (else 0);
- engagement change ≥ +10% → +1, ≤ −10% → −1 (else 0);
- `negative` sentiment → −1 (positive never inflates — downside caution, per methodology).

Net points map to `growing` (≥+1) · `stable` (0) · `soft_decline` (−1) · `decline` (≤−2). A market
with a **single snapshot** stays `stable` ("insufficient history") — momentum needs at least two polls
over time, so the value compounds the more you poll. Tune the thresholds at the top of the script.

> Stay honest: per the methodology, only let real evidence move a market off `stable`. If the data is
> thin, leave it `stable` and say so.
