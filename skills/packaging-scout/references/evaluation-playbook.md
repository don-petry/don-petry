# Packaging evaluation playbook

Depth reference for `packaging-scout`. Read when researching options, judging origin, or building the
comparison. The SKILL.md has the workflow; this has the field knowledge that makes the judgments good.

## Table of contents
- Vendor types and where each wins
- Search terms that surface real options
- Origin detection (domestic vs. overseas)
- Total landed cost — the hidden line items
- Sites that block automated reads (use the browser)
- Format notes by product shape
- Scoring rubric (meets / partial / fails)

## Vendor types and where each wins

| Type | Strengths | Watch out for | Examples |
|---|---|---|---|
| General distributors | In stock, low MOQ, fast domestic ship, blank stock | Generic look; limited sizes; reselling imports | Uline, Papermart, Nashville Wraps, ClearBags |
| Eco / sustainable | Best material story, recycled/compostable | Custom sizes gate behind high MOQ (often thousands) | EcoEnclose, noissue |
| Category specialists | Purpose-built fit + inserts (solves protection) | Narrow catalog; may use film windows | candle-box makers, bottle/jar specialists |
| Custom box shops | Any size, windows, low MOQ, print options | Often overseas; setup/dieline fees; long lead | many "custom ___ boxes" sites |
| Small-batch makers | Lowest MOQ, rustic, blank, cheap | Inconsistent stock; manual ordering | Etsy sellers |

Rule of thumb for a first run of 50–300 units: a general distributor (buy-now) or a small-batch maker
usually beats a custom shop on total cost and speed, unless the product needs a size/window only custom can
provide.

## Search terms that surface real options

Combine the product + format + material + a fit dimension, and try several phrasings:
- `"<product> box"`, `"<product> packaging"`, `"<N> inch <product> box"`
- `"kraft <product> box with window"`, `"<product> gift box window"`
- `"made in usa <product> box"`, `"<product> packaging low minimum"`, `"<product> box no minimum"`
- format variants: `"belly band"`, `"pillow box"`, `"sleeve"`, `"folding carton"`, `"two piece rigid box"`, `"mailer"`, `"kraft tube"`
- channel/material variants: `"recyclable"`, `"plastic free"`, `"compostable"`, `"eco"`

## Origin detection (domestic vs. overseas)

When the user prefers domestic, classify each vendor:
- **Domestic manufacturer** — discloses a real plant/facility location; "made in <country>" stated; reasonable domestic lead times. Highest confidence.
- **Domestic distributor** — ships fast from in-country warehouses but resells imported stock. "Ships from" yes, "made in" not guaranteed. Fine if the user only cares about ship-from / lead time.
- **Overseas with a local office** — the common trap. Signals: the only address is a sales office; "free worldwide shipping" folded into unit price; multi-week real lead times; no disclosed domestic plant; reviews mention overseas shipment; quote-only pricing with dieline talk.

Always report origin with a confidence level and where you saw it (about page, shipping policy, review).

## Total landed cost — the hidden line items

Headline unit price is rarely the real price. Add:
- **Shipping** — or the free-ship threshold (and whether the order clears it). Heavy/bulky boxes ship dimensionally.
- **Setup / dieline / plate / tooling fees** — one-time, common on custom and printed boxes, frequently not shown until the proof. A low unit price + a high dieline fee can lose to a slightly pricier stock box at low volume.
- **Sample costs** and minimum order $ values.
Normalize everything to **cost per package at the user's actual starting volume**.

## Sites that block automated reads (use the browser)

These commonly return 403 / empty HTML to scrapers; get prices via the Chrome extension instead and date
the confirmation:
- Betterbee, Uline, Papermart, ClearBags, Nashville Wraps (product pages), Etsy listings.
Image CDNs for these sites are often still reachable with `curl` + a browser User-Agent + matching `Referer`,
even when the HTML page is blocked.

**When you don't have the Chrome extension** (e.g. you're a research subagent), the live product page may be
blocked but the *price* often still leaks out two ways. First, `curl` the raw HTML with a browser User-Agent
and grep for embedded structured data — `application/ld+json` with an `Offer`/`UnitPriceSpecification`, or
`og:price`/`product:price` meta tags; the number is regularly sitting in static markup even when the rendered
page looks empty (this is the highest-yield no-extension tactic). Prefer raw `curl` over `WebFetch`, whose
summarizer hides JSON and throws false "not found." Second, Google Shopping listings, the price line in a
search result, or a cached copy often expose the unit price — record those as a list price, not a verified
quantity-tier price, since only the extension reliably reads the break table. The hard exception: a fully
JS-rendered storefront (e.g. EcoEnclose) keeps the price only in client-side script with nothing in raw HTML
or snippets — that genuinely needs a live JS browser, so mark it unverified with that reason and don't
over-spend attempts.

## Format notes by product shape

- **Long & brittle (tapers, incense, dowels)** — length is make-or-break; needs a divider/insert to stop snapping and rubbing; film or open window both fine, open is plastic-free. Belly bands look great but give zero shipping protection alone.
- **Jars / tins / candles in vessels** — diameter and height; weight drives shipping cost; consider inserts/cradles for breakage. Beware the round-in-square trap: a cylindrical item in a square-section box touches the walls at its widest points even when the listed dimensions "fit," giving zero cushioning — size up and add an insert, or use a tube/round mailer, rather than scoring it a clean fit.
- **Soft goods** — mailers and sleeves; less fragility, more about presentation and print.
- **Multi-packs** — interior must hold N units with dividers; the "don't let them touch" problem is real for anything that can mar or stick (wax, ceramics).

## Scoring rubric (meets / partial / fails)

For each criterion in the matrix:
- **Meets (✓)** — clearly satisfies the requirement at the user's volume/budget.
- **Partial (~)** — satisfies in spirit but with a real caveat (kraft box but plastic film window = partial on "plastic-free"; 12" length holding a 9" item with curve loss = still meets fit, but note it).
- **Fails (✗)** — does not satisfy; if the failed criterion is fit or a hard requirement, the option is disqualified, not just low-scored.

Be honest about partials — they carry the most decision-relevant information. A wall of green ✓ that hides a
plastic film cover is less useful than an accurate ~.
