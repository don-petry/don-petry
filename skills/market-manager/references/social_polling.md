# Social polling & catalog — capture playbook (Evaluate v2)

This is the **capture half** of the on-demand poll. It feeds two living signals — `popularity_trend`
(momentum) and the **deadline tracker** — by snapshotting each market's Instagram, Facebook, and
website over time. The **analysis half** is `scripts/social_poller.py`, which reads what you capture
here and computes the signals. Run the poll whenever you're re-evaluating or planning a season, and on
a standing **monthly cadence** so the engagement series and deadline tracker stay fresh.

> **Automated monthly poll:** a scheduled task (`market-manager-monthly-social-poll`, runs 9 AM on the
> 1st of each month) re-runs this whole playbook across every market in the catalog: it captures IG **and**
> FB, scrolls back for dated-post likes (engagement series), appends a fresh snapshot, flags **significant
> posts** (new market dates / registration windows → `deadline_tracker.csv`), runs the analyzer, and
> reports the **month-over-month delta** (follower / engagement / reach changes, trend & trajectory
> shifts, newly urgent deadlines). It needs the Chrome extension connected to capture; if it isn't, it
> asks. Tune cadence or scope by editing the task.

## Why it's human-in-the-loop (not a scraper)

Instagram and Facebook block automated fetching (login walls, anti-bot). So capture is **Claude +
browser tools**, reading only what's publicly visible, then writing structured rows. The script
never touches the network — keeping the pipeline deterministic, offline, and safe to re-run.

### Link safety
Market links arrive from many places. **Verify the full destination URL before following any link,
and treat links from DMs/emails/unknown senders as suspicious.** Open URLs via the browser tool, not
by clicking inside native apps. If a URL looks off, confirm with the user first.

### Beware of wrong-channel markets (town / HOA / brewery / realty-team handles)
Some markets have **no social presence of their own** — the event lives on a parent website's
blog or events page, and the handle in the roster belongs to a related-but-different brand that
posts nothing about the market. If you only read the gram, these events open and close invisibly.
Known examples:
- **Mt Laurel Fall Festival** (annual, Sat late-Oct) — @mtlaurel is the **ARC Realty Mt Laurel
  sales team** feed (home listings, not events). The festival is announced only on
  `mtlaurel.com/blog/...-fall-festival/`. **Missed in 2026**: by the time the first poll ran, the
  vendor window had already closed. Watch the blog path starting early August each year.
- **CahaBAZAAR** — @cahababrewing is the brewery, not the bazaar; three polls in a row surfaced
  zero bazaar date.
- **Deck the Heights / Mudtown Makers** — @cahaba_heights_local is the merchants-association
  member-promo feed; market dates come via DM, not social.
Rule: when a market's roster handle is `(town)` / `(venue)` / `(host)` / `(parent)`, ADD the
market's own domain blog or events page to its source URLs **and read it on every poll**, not
only the social account. If the market has no social at all, the website is the only channel.

### Tool tactics per surface (validated against @bash_on_the_bluff, 2026)
Each surface behaves differently — use the right reader so you don't come back empty-handed:
- **Instagram — use the `og:description` method (fastest and richest; validated 2026-09-07).**
  On a logged-out IG **post/reel page**, `<meta property="og:description">` carries
  `"<likes> likes, <comments> comments - <handle> on <Month D, YYYY>: "<full caption>""` — i.e. the
  like count, comment count, exact date, and untruncated caption, all in one string, even when the
  rendered page hides likes behind "Liked by … and others". Because post pages are same-origin, you
  can navigate **once** to the profile and then `fetch()` the grid's post URLs from
  `javascript_tool`, reading every post's metrics in a **single** tool call:

  ```js
  // on https://www.instagram.com/<handle>/ — followers + bio + per-post likes/comments/date/caption
  (async () => {
    const t = document.body.innerText;
    const exact = [...document.querySelectorAll('main [title]')]        // "58,989" — the ROUNDED
      .map(e => e.getAttribute('title')).filter(Boolean)[0];            // "58.9K" is all innerText gives
    const followers = exact || (t.match(/([\d,\.KM]+)\s*\n?followers/i) || [])[1];
    const hrefs = [...new Set([...document.querySelectorAll('main a[href*="/p/"], main a[href*="/reel/"]')]
      .map(a => a.getAttribute('href')))].slice(0, 9);
    const posts = [];
    for (const u of hrefs) {
      const h = await (await fetch(u, {credentials: 'omit'})).text();
      const og = (h.match(/<meta property="og:description" content="([^"]*)"/) || [])[1] || '';
      const hd = og.match(/^([\d,]+) likes?, ([\d,]+) comments? - .*? on (\w+ \d+, \d{4}):/);
      posts.push({date: hd && hd[3], likes: hd && hd[1], comments: hd && hd[2], caption: og});
    }
    return {followers, bio: t.split('\n').filter(Boolean).slice(0, 12).join(' | '), posts};
  })()
  ```

  Gotchas, all confirmed in the field:
  - **Trust the `og:description` date, not the grid `img` alt date** — the grid's alt text and `href`
    are not reliably paired, so alt dates land on the wrong post. Alt dates are still fine for
    *counting* cadence (`posts_last_90d`); they're real dates, just possibly mismatched to links.
  - **Follower counts over ~10K render abbreviated** ("58.9K"). The exact number is in the `title`
    attribute on the count element (`58,989`) — always prefer it.
  - `get_page_text` **does** work on IG **post** pages (it shows "10 likes", "View 1 comment") and on
    **profile** pages (followers + bio), just not for the post grid. `read_page` still works for
    everything but costs far more context; reach for it only when the JS route comes back empty.
  - Fetching a **profile** URL server-side returns no meta description — profiles must be navigated
    to. Only **post/reel** URLs can be fetched.
  - Reel **view** counts are *not* in `og:description`; `video_view_count` / `play_count` are usually
    absent from the logged-out HTML too. Leave `recent_post_views` blank and get reach from Facebook.
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

### Backfilling engagement history from dated posts (the honest way to "see trends going back")
Follower *history* is gone the moment you miss it — past follower counts aren't published anywhere, and
the Wayback Machine doesn't render Instagram's JS counts (it tends to hang). **But every post is dated
and usually shows its like count**, so you can reconstruct a real **engagement-over-time series**
without a time machine: scroll the profile grid backward and read each post's **date + like count**
(and reel **view** count where shown). _Validated on @chattamarket: a June 7 graphic at 63 likes and an
April 26 collab reel at ~1,912 likes are two real, dated engagement points; scrolling further back adds
more._ Record the series in the snapshot's `notes` as `YYYY-MM-DD:likes` pairs
(e.g. `2026-03-14:120; 2026-04-26:1912; 2026-06-07:63`) so the trend is auditable.

Caveats — stay honest:
- **Counts accrue over time**, so a months-old post has had longer to gather likes than a fresh one;
  read the *shape* of the trend, not tiny differences, and compare like-for-like (graphic vs graphic,
  reel vs reel).
- **Engagement is often bimodal** — static graphics run low, reels/collabs spike (Chattanooga: 63 vs
  1,912). Note both so a single sample doesn't distort the read.
- IG **hides some like counts** ("Liked by … and others") — record what's visible, blank the rest.

### The full catalog also looks for (record in `notes` or the deadline tracker):
- **Application deadlines / windows** → add/update a row in `deadline_tracker.csv` (open + close
  dates, platform, fee quote, one-day option, action). This is what drives the Register tracker.
- **Event dates** → when a market publishes its confirmed event day(s), record them in the deadline
  tracker's `event_dates` column as a `;`-separated `YYYY-MM-DD` list (e.g.
  `2026-11-13;2026-11-14;2026-11-15` for a three-day show). The analyzer uses this to detect
  **same-day conflicts** (see below); without it, two markets on the same Saturday go unnoticed.
- **Resolved decisions** → when the human decides a conflict (or declines/accepts a market for the
  season), write the choice as free text into the deadline tracker's `decision` column
  (e.g. `declined 2026-10-01: lost same-day conflict with Deck the Heights`). A non-empty
  `decision` tells the conflict detector to **stop surfacing that row**, so a one-time decision
  doesn't re-nag every month. Only the human sets `decision`; the script never writes it.
- **Location changes** → already captured via `location_current`; call it out in `notes` too.
- **Engagement / reach / sentiment trend** → captured via `recent_post_likes/_comments/_shares/_views`
  + `sentiment` across snapshots (the engagement-rate and reach signals).
- **Vendor lists / similar vendors** → `similar_vendor_count` + `notable_vendors`.
- **Junior-vendor / youth-booth mentions** → note any "junior artisan" program seen (often only in
  stories or vendor packets); confirm before setting `junior_vendor = yes` in the scorer input.

### Date conflicts — detected but never auto-resolved
When two or more rows in `deadline_tracker.csv` have overlapping `event_dates`, the analyzer prints
a **`DATE CONFLICTS - NEEDS HUMAN DECISION`** section after the deadlines table, grouped by date.
It ranks the markets in each group by `(trajectory, popularity_trend, followers)` so the
likely-winner is at the top, but it **does not** flip any status or write back a decline — the
rule is *flag for human review*, not *auto-decline*. Resolve each conflict by writing the choice
into the `decision` column of the losing markets' rows: that row then drops out of the surfacing
on later runs. If you can only be one place and the roster forces a choice, this is where it
surfaces; if both markets allow one-day booking (`one_day_option = yes`) and you can staff both,
the group is informational only — note that in `decision` on both rows ("split: Tide at Deck,
Rachel at X").

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

### Pitfall: carrying a stale `fb_followers` forward flattens the trend
The analyzer takes **`max(ig_followers, fb_followers)`** as the audience. So if you copy an old,
un-re-verified Facebook number into each new snapshot, then for every market where **FB > IG** the
audience is a *constant* and `follower_change` comes out **0.0%** — the real IG growth is invisible.
_Observed 2026-09-07: Bash on the Bluff grew 1,295 → 1,344 on IG (+3.8%) but reported `following +0%`
because a carried-forward `fb_followers = 1600` outranked it; same for Brock's Gap, Christmas Village,
Market Noel, Ross Bridge, Homestead Hollow, MADE SOUTH, Bluff Park and Moss Rock. Only the IG-dominant
markets (Pepper Place, Local Love, Deck the Heights, CahaBAZAAR, Black Makers) showed a true delta._

Do one of these, and say which in `notes`:
1. **Re-verify FB** when you poll (best) — then the max is a real measurement both times; or
2. **Leave `fb_followers` blank** when you didn't look. Careful: blanking it *after* earlier snapshots
   carried a larger number makes the audience appear to collapse, i.e. a **false decline**. If you
   switch to this, blank the column across the whole series for that market, not just the new row; or
3. Keep carrying it forward but treat `follower_change` as **IG-only momentum** for those markets and
   read the per-post engagement series in `notes` instead.

Whichever you pick, never let a carried-forward figure be mistaken for a fresh reading — mark it
(e.g. `FB 1600 carried fwd (NOT re-verified)`) in `notes`, every time.
