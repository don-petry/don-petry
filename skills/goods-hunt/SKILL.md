---
name: goods-hunt
description: 'Find, research, score, and rank high-value used goods by Cost Per Remaining Useful-life
  Unit (CPRU) — a generalization of car-hunt''s CPM. Loads a domain pack (cars, tractors, furniture, beekeeping,
  generic, …) that supplies the domain knowledge; the engine supplies the pipeline. Also supports Valuation/Comp
  mode (the generalized Insurance-Comp): find the highest verifiable comps to maximize an insured payout
  or justify a price.'
license: MIT
metadata:
  argument-hint: '[--domain <name>] [make/type model year-range max-price zip radius] | [--mode comp <item
    details>]'
---

# Goods Hunt — High-Value Used-Goods Finder & Ranker (generic engine)

Search, score, and rank high-value used goods by **CPRU — Cost Per Remaining
Useful-life Unit**. Lower CPRU = more remaining useful life per dollar. This is
the domain-agnostic generalization of `car-hunt`: the **engine** (this file) owns
the pipeline; a **domain pack** owns the knowledge.

> **Relationship to `/car-hunt`:** `car-hunt` is the live, battle-tested skill and
> its scheduled workflows remain the production entry point. `goods-hunt` is its
> generalized successor. The `cars` pack (`domains/cars.md`) reproduces car-hunt's
> behavior; see `PARITY.md` for the section-by-section map. **Do not rewire
> `/car-hunt` or its workflows from here** — the cutover is a separate, eval-gated
> step. Today, `goods-hunt` runs new domains (tractors first) without touching the
> live car system.

---

## Step 0: Load the Household Config and the Domain Pack

Every run begins by reading the household config, then resolving the active domain
and loading its pack.

0. **Read `config/household.yaml`** (next to this file): home ZIP, city/state,
   Facebook Marketplace numeric city ID, Craigslist regions, per-domain tracking
   sheets, and per-pack household values (`packs.<domain>` — e.g. the cars pack's
   `shared_config` points at car-hunt's household file for location tiers, outreach
   copy and scheduled defaults). **If it is missing:** copy
   `config/household.example.yaml` to `config/household.yaml`, ask the user for each
   value in one message, and write their answers; leave a key empty rather than
   guessing. Below, `CONFIG.<key>` means a value from that file.
1. **Resolve the domain** from `--domain <name>`, else infer from keywords in the user's request
   (e.g. "tractor/Kubota/loader" → tractors; "dresser/credenza/antique" →
   furniture; "hive/extractor/beekeeping" → beekeeping; Honda/Toyota/Civic/Camry →
   cars), else ask. Default to `generic` only when nothing matches.
   - **Disabled-pack guard:** if the resolved pack's manifest has `enabled: false`,
     **stop** — do not run, draft, contact, or read threads for that domain. Tell
     the user the pack is disabled (and the date/reason from its banner) and that
     re-enabling means flipping `enabled: true` in the pack. **`tractors` is
     disabled (2026-06-19).**
2. **Read** `skills/goods-hunt/domains/<domain>.md`. The pack supplies every
   domain-specific input the steps below reference as `PACK.<field>` — **each is
   either a YAML front-matter field or a like-named markdown section**, not
   necessarily a literal YAML key (e.g. the value metric lives in
   `item_types[].metric`; the expected-life data, sources, deal-breakers,
   verification recipes, quality-card sources, location tiers, and outreach copy
   live as their named sections). Inputs referenced: `life_unit`,
   `consumed_life`, `item_types` (metric + buy-policy routing), the expected-life
   table, quality-card sources, the `sources` registry, deal-breakers,
   `location_signal` (+ a location-tier table where the pack defines one),
   verification recipes, qualification slots (+ the automation-opener fingerprint
   for turn attribution), the outreach template, `default_radius`,
   `freight_option`, `cadence`, `outreach_mode`, and `stale_days`.
3. **Announce** the loaded pack and its tool prerequisites (Step 0.5) before
   working, so the user knows what's available and what will be degraded.

If a referenced pack field is missing, say so and fall back to the engine default
noted at that step — never silently invent domain data.

### Step 0.5: Tools this works with (generic pattern)

Probe each capability the active pack needs; tell the user upfront what's available
and what degrades. The *pattern* is generic; the *rows* come from the pack. Any agent
or harness works — use whatever provides the capability.

| Capability | Examples | Generic role | Degraded without |
|---|---|---|---|
| **Web search + fetch a URL** | built-in web search/fetch tools, a search API, `curl` | Quality Card research, listing search, verification | Baseline — little works without it |
| **Shell (bash + Python 3)** | any local shell | the shared qualification engine (`skills/car-hunt/qualification/`), pack CLIs | Run checks by hand and say so |
| **Browser automation with a logged-in session** | a Chrome/Chromium automation extension, a Playwright or Puppeteer server, or the user driving the browser | Facebook Marketplace logged-in search, seller-profile extraction, inline outreach, any browser-driven verification fallback | FB Marketplace drops to Google-indexed listings only (~20–40%); browser-driven verifications unavailable. Report the gap, never silently skip. |
| **Image understanding** | a vision-capable model, or the user grading photos | photo-graded condition (Step 4) | Fall back to `under_market` / `comp_value`; ask the seller for specific shots |
| **Spreadsheet export** | a Google Drive tool that can create a spreadsheet from CSV, the Sheets API, or a local `.csv` file | Sheet export (Step 6) | Write a CSV and give the user its path |
| **Pack-specific structured source(s)** | per `PACK.sources` (e.g. an API CLI) | the domain's structured-inventory tier | falls back to web scraping / WebSearch; note the gap |

---

## Core Formula — CPRU

```
CPRU      = Price / (Expected_Life − Consumed_Life)     # cost per remaining unit
Life_Pct  = Consumed_Life / Expected_Life               # 0..1, lower = more life left
```

- `Expected_Life` comes from `PACK.expected_life` (keyed by item type/model);
  unit = `PACK.life_unit` (miles, engine-hours, service-years, seasons, cycles…).
- `Consumed_Life` is read per `PACK.consumed_life`: a **meter** (odometer,
  hour-meter) when one exists, else **estimated** from age + construction grade +
  photo-graded wear (see Step 3 — Condition Grading).
- **Metric selection is per item type** (`PACK.item_types[].metric`):
  `cpru` (metered or estimable lifetime), `comp_value` (appreciating/collectible →
  price-vs-comps via Comp mode), or `under_market`. For unmetered/appreciating
  items the engine default is **show both** a CPRU-with-band and the comp value.

You are buying **future utility**, not past metal/use. The denominator is what
matters.

---

## Mode Detection

| Trigger | Mode |
|---|---|
| comp / valuation / "totalled" / "total loss" / insured-payout / "justify my price" keywords (see `PACK` comp triggers) | **Comp / Valuation** → jump to [Comp Mode](#comp--valuation-mode); skip the hunt steps |
| all other invocations | **Standard Hunt** → continue Step 1 → 8 |

---

## Step 1: Buy-Policy Routing (run before searching)

Not every item type in a domain is a used market. Using `PACK.item_types`,
classify each requested item and route it:

- **`used_market`** → full hunt (search → score → qualify → outreach).
- **`used_if <condition>`** → hunt, but auto-disqualify any listing failing the
  condition (e.g. "sterilizable", "scorchable", "no comb", "no bed bugs").
- **`new_only`** → **do not hunt used.** Surface the **best new-retail price** as
  the comp, state plainly why used is off the table (`PACK` reason), and optionally
  watch for a rare acceptable exception (sealed/NIB, factory-refurb).

A single hunt can span all three (e.g. set up a beehive = new comb + used
extractor + scorchable boxes). Only `used_market` / `used_if` items enter the
search pipeline; `new_only` items get a new-price comp and a one-line rationale.
The metric per item follows its `item_types[].metric`.

---

## Step 2: Quality Card (research before searching)

Produce a per-item **Quality Card** from live research — best variants/eras to
buy, ones to avoid, known failure modes — sourced from `PACK.quality_card_sources`
(run all in parallel via WebSearch; WebFetch top hits). Extract: **best
variants/eras**, **avoid variants/eras**, **top-3 recurring issues**, **generation
/ series boundaries**, a **reliability score** if the domain has one, and a
**buying tip**. Emit one card per item type before searching.

Merge live findings into the pack's static `expected_life` / caution data to build
an **adjusted caution list** used in Step 4 scoring; when live data contradicts
the static table, note the discrepancy and prefer live.

In **scheduled/cached** runs, skip this step unless the item list changed.

---

## Step 3: Search for Listings

Search all `PACK.sources` **in parallel**, per item type. Sources split into:

- **Universal sources (every domain): Facebook Marketplace + Craigslist** (+ eBay
  where the pack lists it). The engine owns their mechanics (below).
- **Pack structured sources** (e.g. Auto.dev for cars, TractorHouse/Fastline for
  tractors, eBay-sold/Chairish for furniture): the pack supplies URLs, field
  paths, and any CLI. Inspect one real record's JSON field names before batch
  extraction — never trust documented field names.

Target **50+ raw candidates** before filtering. Paginate **to exhaustion**; report
per-source how many pages/results were checked. Batch efficiently:
preview-filter on the search-card data (price/age/etc.) before fetching individual
pages — that disqualifies most candidates cheaply — then WebFetch only survivors.

### Facebook Marketplace (universal — engine-owned mechanics)

FB is login-gated; individual item URLs hit a login wall via WebFetch. Never emit
a generic `facebook.com/marketplace` placeholder as a listing link — a link column
must hold a real item URL or "Search manually."

- **Option A — Google-indexed public listings:** `site:facebook.com/marketplace/item {query terms} {city}`. Record real `…/item/{id}` URLs; WebFetch (extract if data returns, else still record the URL).
- **Option B — manual search URL** row when A returns nothing.
- **Option C — logged-in browser automation (preferred when available):**
  `https://www.facebook.com/marketplace/{CITY_ID}/search?query={terms}&daysSinceListed={N}&maxPrice={MAX}&minPrice={MIN}&maxMileage={MAX_METER}&minYear={MIN}&radiusKM={RADIUS_KM}&sortBy=creation_time_descend`, then JS-scroll to load lazy cards and extract `/marketplace/item/{id}/` hrefs + preview text.

**Hard-won FB facts (generic — preserve for every domain):**
- **Use the numeric city ID, not the slug** — a city slug is disambiguated by IP/cookies and can resolve to a same-named city in another country. Use `CONFIG.location.fb_marketplace_city_id` (find it once by opening the city's Marketplace page in a logged-in browser and reading the number from the redirected URL).
- `query=` is silently dropped on `/marketplace/{cityId}/vehicles?…`; use `/search?query=…`.
- `radiusKM` is **kilometers**, not miles (100mi ≈ 160km); it's a coarse pre-filter that leaks — the geocoded cap (Step 3.5) is authoritative.
- `daysSinceListed=1` = last 24h, honored.
- Some browser-automation tools refuse to return a JS value that contains a URL with query params (one reports `[BLOCKED: Cookie/query string data]`) — strip URLs or stash in `window.__foo`.
- Seller-profile signals (tenure, rating+count, active-listings) extract only from a live logged-in session; default NEUTRAL otherwise; one attempt then move on.

### Craigslist (universal — engine-owned mechanics)

WebFetch regional search pages (the pack supplies the category code — cars use
`cta`; general goods use the relevant category — and the regional subdomains).
Search each region in `CONFIG.location.craigslist_regions`. Paginate by `&s=120`, `&s=240`… until the total result count is exhausted. Extract
individual listing URLs from the HTML and WebFetch each (plain HTML, full details).
**Never construct or guess a Craigslist URL** — IDs aren't predictable; a wrong ID
404s. Use only the exact scraped URL.

### Pack structured sources

Run per `PACK.sources` definitions (URLs/CLI/field paths). For any API that may
report a **0/empty meter** (e.g. odometer/hour-meter unknown), apply the **0-meter
guard**: do not compute CPRU (a 0 denominator-input yields a meaningless near-zero
CPRU); list those under "Meter not reported" at the end. Dedupe by URL across
sources (keep the richest description for disqualifier scanning).

### Data to Extract Per Listing (generic skeleton)

`date_found`, `date_posted`, item identity (type/model/variant/year-or-age),
`meter_or_age`, `price`, `condition_signals`, `location`, `distance_mi`, `seller`
(dealer/private/platform), `link`, `notes`. Pack adds its own fields (cars: doors,
transmission; tractors: hours, PTO/hyd; furniture: material/joinery). Missing →
`—`, fill during deep-dive.

### Step 3.5: Distance Estimation (engine-owned)

Geocode the user ZIP and each unique listing city via **Nominatim** (free, no
key): `https://nominatim.openstreetmap.org/search?postalcode={ZIP}&countrycodes=us&format=json`
and `…?q={city},{state}&countrycodes=us&format=json&limit=1`. Compute Haversine
straight-line × **1.3** road correction. Display `~{mi} mi`.

- **Hard cap:** drop any listing with `driving_est > RADIUS` → record in
  `disqualified` with `reason: "too far (~{mi} > {RADIUS} cap)"`. If a city can't
  be geocoded, keep it and flag "distance unknown" — don't auto-drop.
- **Freight escape hatch** (`PACK.freight_option`): for large goods, instead of
  hard-dropping a high-value far item, surface an estimated freight cost and a
  **landed CPRU** = `(price + freight) / remaining_life`.
- **Staleness:** drop listings older than `PACK.stale_days` (cars: 21). Unknown
  post date → keep, note "Post date unknown".

### Step 3.6: Disqualification (universal + pack)

Scrape the **full free-form description** (expand "See more") before running any
disqualifier — disclosures live in free text, not structured fields. Run scans on
the full concatenated text (title + fields + description + condition/notes).

- **Universal deal-breakers:** scam signals (off-platform payment, shipping-only,
  Zelle/CashApp-before-seeing, broker language, urgency/"must sell moving"),
  price-implausibly-low-without-reason (flag for human review), plus distance and
  staleness (Step 3.5).
- **Pack deal-breakers (`PACK.deal_breakers`):** the domain's hard "no" list
  (cars: salvage/no-title, won't-run; tractors: seized, dead hydraulics, rolled
  hour-meter, Tier-4 emissions-delete; furniture: bed bugs, mold, structural;
  beekeeping: unknown/positive AFB history on comb/woodenware).

Log every disqualified listing in a "Disqualified" section with its reason — never
silently drop.

---

## Step 4: Score and Rank

For each surviving listing compute CPRU and `life_pct` (Core Formula), then layer
the two **generic ranking modifiers** onto a **quality-adjusted metric**
(`Adj.CPRU`). The modifiers apply to *whatever per-unit-cost metric the pack
defines* — the mechanism is generic, the $/unit values come from the pack.

### Condition Grading (for unmetered or photo-gradeable items)

When `PACK.consumed_life = estimate`, derive `Consumed_Life` from age +
construction grade + **photo-graded wear** (image understanding over listing photos — a vision-capable model or the user).
**Treat this as a critical-but-unreliable input:** grade *conservatively* (assume
worse when unsure), present CPRU as a **band** not a false-precise number, **never
auto-disqualify on photos alone** (flag / ask the seller for specific shots), and
fall back to `under_market`/`comp_value` when no grade can be made. (This also
sharpens metered domains — tire/rust/interior, regen soot, etc.)

### Location-Quality Tier (generic mechanism, pack semantics)

Location correlates (base-rate, not deterministic) with item quality and
negotiation room — worth a small ranking modifier. Tier each listing by
city/neighborhood using the pack's **location-tier table** (a 4-tier A/B/C/D table
the pack supplies per metro — the household's table lives in its config (cars: `location_tiers` in the file named by `CONFIG.packs.cars.shared_config`); build one on first run in a
new metro and save it to `config/household.yaml`). The pack's `location_signal` field names the
**favorable direction** (cars: affluent suburbs; tractors:
rural/ag; furniture: older-affluent + estate sales; beekeeping: active-beekeeping
regions). Apply the pack's per-tier ± modifier to `Adj.CPRU`; the **displayed CPRU
stays the real number**. Name the economic/behavioral mechanism in user-facing
copy, never the demographic.

### Seller Trust Score (generic platform-reputation, stacks on tier)

From observable seller-profile signals (FB tenure, rating+count, active-listings),
classify **CAUTION → TRUSTED → NEUTRAL** (evaluate in that order; defaults:
Craigslist/anonymous private = NEUTRAL; dealer = `—`). Apply the per-class ±
modifier to `Adj.CPRU` (stacks on the location-tier adjustment). The classification
thresholds and ± values live in the pack (cars: `domains/cars.md`); profile
extraction uses the FB profile regexes the cars pack lists (generic FB mechanics —
any FB-sourced domain reuses them). Show the trust label in the Seller
column and add `🔴 CAUTION SELLER` / `🟡 UNVERIFIED SELLER` flags as warranted.

`Adj.CPRU = real CPRU ± location-tier adj ± seller-trust adj` (sort key).

### Present Results

Sort by `Adj.CPRU` ascending (best value first). Show Quality Cards first, then a
ranked table (real CPRU **and** Adj.CPRU both shown, plus Life%, Distance, Tier,
Seller, Flags, Link), then a summary (best overall, best local, best private,
best trusted, best per sub-type, skipped-no-data count). Flag caution/avoid
variants from Step 2 with the specific issue. Then offer the deep-dive.

---

## Step 5: Deep-Dive (user-initiated)

When the user selects candidates, run `PACK.verification` recipes in parallel —
the generic interface is `verify(item) → {specs_match, known_issues,
market_value, authenticity, ownership/title}`. Examples by domain:

- **Cars:** NHTSA recalls/complaints/safety, vPIC VIN decode, Auto.dev
  TCO/open-recalls, KBB market, NICB/NMVTIS/Carfax history (see `domains/cars.md`).
- **Tractors:** serial decode (year/plant), TractorData spec match, parts-
  availability check, hour-meter-vs-wear plausibility.
- **Furniture:** maker's-mark lookup, eBay/auction sold-comps, reproduction tells.
- **Beekeeping:** state apiary inspection records, equipment-standard match.

**Generic verification lessons (reuse for any bot-protected data site):** decode
must match the listing → mismatch is a 🚫 STOP; drive a stubborn gov/data form via
the prototype `.value` setter + dispatch `InputEvent({inputType:'insertText',
data})` + walk up parents to the submit container + wait for redirect + parse
`body.innerText` against an **anchored block** (not a loose literal). Vehicle-
history-style reports that are paid → point the user to them, never auto-purchase.

**Head-to-head (when weighing two candidates):** compare on every dimension the
pack defines; apply the **information-asymmetry rule** — a higher-confidence buy
(verified title/history) can win at a slightly worse CPRU than a cheaper one full
of unknowns. The recommendation must be **opinionated** — pick one, with a
fallback condition.

**Pre-commit finalization (when the user is about to transact):** gate on final
verification (identity decode, recalls/defects, title/ownership, out-of-pocket
estimate) and emit the pack's **inspection checklist** + a **reusable
fraud/paperwork checklist** as the deliverable (PDF when possible). The checklist
*generator* is generic (always emit the whole template; substitute placeholders;
emit only the item-matching model-specific rows; reusable fraud doc skipped if
regenerated <1 week ago); the checklist *content* is pack-supplied.

---

## Step 6: Export to a Spreadsheet (engine-owned)

Offer export with whatever spreadsheet capability is available (Step 0.5), or a local
CSV. Mechanics are generic:
- **Many Drive tools can only create, not overwrite** — then every run = a new
  file/ID. Keep the canonical sheet ID in `CONFIG.tracking_sheets.<domain>` (write it
  back to `config/household.yaml`); surface the new URL **loudly** each run.
- Dedupe by Link URL; mark stale rows (don't delete); merge updates.
- Use **`text/csv`** MIME with base64 CSV (xlsx MIME fails base64 validation).
- Sort by `Adj.CPRU` ascending; include every listing; never silently drop a row.
- Column set = the generic core + `PACK` columns.

---

## Step 7: Outreach (optional, gated)

Only with explicit user confirmation, and respecting `PACK.outreach_mode`
(**new domains default `draft` — draft-only**; auto-send is car-only until a domain
earns it via its own eval). Mechanics (FB Marketplace) are engine-owned:
1. Open the listing tab; **check history** (`Message again` in page text → already
   contacted, skip; also cross-check the sheet's Contacted column).
2. **Dry-run first** — show proposed messages; wait for explicit "proceed".
3. Send via the **modal** dialog; **the modal recipient name is authoritative, NOT
   the listing sidebar** (they can differ — wrong name is worse than no name; if
   not a plausible first name, open with "Hey -"). Personalize from
   `PACK.outreach_template`.
4. Update the sheet's Contacted column (log every attempt, success or FAIL).

Skip non-FB listings (manual contact). Never send without dry-run approval; never
fabricate a name.

---

## Step 8: Read & Interpret Messenger Threads + Qualify (engine-owned)

Runs at the **start** of a run (so disqualifiers take effect before re-ranking).
**Only with a logged-in browser session.** Read-only on Messenger — it never types
or sends; drafts are text for the user.

**Interpretation (the agent is the NLU):** open every recent thread (~20; don't gate
on unread — re-read every run, idempotent). Read the **whole** thread as attributed
turns: `seller` (inbound), `automation` (outbound matching `PACK`'s opener
fingerprint), `human` (any other outbound). Compute `listing`, `last_speaker`,
`human_led` (**true if ANY turn is human**), `disposition`, `open_item`,
`evidence` (**direct quotes — quote or it didn't happen**), `confidence`.

**Action ladder (strict order):** (a) objective disqualifier (seller's words =
title/condition deal-breaker per pack, or sold/scam) → disqualify the matched
listing (idempotent; needs a quote + a matched listing); (b) `human_led` →
**hands off, no draft**; (c) automation-led + `last_speaker=seller` + an
`open_item` + high confidence → **draft only** (never send); (d) else none. A bare
acknowledgment ("Will do", "ok", "👍") carries no standalone meaning.

**Qualification (the agent extracts slots; deterministic Python decides):** for each
contacted, non-human-led thread, fill the `PACK.qualification_slots` for that
domain — `{answered, value, verdict: pass|fail|unknown, evidence}` with the
seller's words. **Never guess pass/fail — use `unknown` when unsure.** The
determination is **not** the agent's: the engine at `skills/car-hunt/qualification/`
(Pydantic ledger + FSM; requires the car-hunt skill installed beside this one) turns slots into qualified/disqualified/pending. That
engine is **already domain-agnostic** — it loads the slot set from a per-domain
`QualSpec` in `qualification/specs.py` (Phase 0). Any `fail` → disqualified
(removed, with the quoted reason); all `pass` → qualified (drafted scheduling
message); else pending (follow-up asks only the still-unanswered questions).
Guardrails are **enforced in tested code, which is the source of truth for the
exact predicate and cap** (`qualification/determination.py` `followup_eligible` +
`FOLLOWUP_CAP`, `qualify.py`): ask-once, a per-run cap, eligible-only (automation-
led + positive disposition + pending + unanswered), a kill-switch repo var, and
the draft-vs-send split. Misreads become eval fixtures in a per-domain eval dir
(mirror `skills/car-hunt/eval/`; create `skills/goods-hunt/eval/<domain>/` when a
domain works toward auto-send), which gate any future auto-send for a new domain.

---

## Scheduling (when a pack opts into unattended runs)

`PACK.cadence` governs this. **New domains default to interactive one-shot — do
NOT wire cron/watchdog until a domain is promoted.** When a pack *is* scheduled
(cars today): skip Step 2 unless the item list changed; surface only **new**
listings (diff links vs prior runs); skip Step 6 unless a high-value find warrants
it; push-notify when a new candidate beats the tracked best CPRU. Default scheduled
parameters live in the pack.

---

## Comp / Valuation Mode

The generalized Insurance-Comp mode — maximize an insured payout (totalled good),
justify a sale price, or set a fair buy ceiling for appreciating items. Process is
generic; the fields, sources, and thresholds come from the pack.

1. **Collect the item + auto-derive the search window** (the pack defines the ±
   bands and which attributes matter — cars: year ±1, meter ±20K, drivetrain).
   Dealer-only, **national scope (no radius)**, **include sold** (≤12 mo), sort
   **price descending**. No CPRU in this mode.
2. **Search** `PACK` comp sources nationally; post-filter on the pack's
   value-driving attributes (cars: drivetrain — worth thousands). 0-meter guard.
   Cross-reference a price-authority source when one source inflates with fees.
3. **Rank** price-descending; flag `★ CLOSEST COMP` / credibility flags (CPO /
   franchise). **Thin-market auto-expansion** (generic trigger; pack ± bands): if
   <5 priced comps, widen the window in logged steps and always cite the actual Δ.
4. **Build the comp package**: count + range, lead with **sold** comps, cite the
   **top-quartile** as the recommended floor (bottom half is dragged down by
   lower-grade/higher-use comps), include a how-to-use-with-the-adjuster brief and
   a negotiation playbook (request their comp report; dispute lower-grade/higher-
   use/wrong-attribute comps; escalate → DOI complaint → public adjuster).
5. **Export** (optional, Step 6 mechanics; pack columns).

---

## Output Format Rules

- Links: a real URL or an explicit "Search manually" / "Call to confirm" — never a
  fabricated or placeholder link.
- Never silently drop a candidate — disqualified items go in a labeled section with
  the reason.
- Show the source for each listing.
- Don't pre-filter by an arbitrary value threshold — rank everything and let the
  user choose the cutoff.
- When FB/scraping coverage is partial, **report the gap honestly**.
- CPRU display precision and sort conventions are pack-defined (cars: CPM to 3
  decimals, Life% integer, sort by CPM).

## Important Rules

- The engine owns the pipeline + platform mechanics; the pack owns all domain
  data. If a pack field is missing, say so — never invent domain knowledge.
- Parameterize the value metric: tier/trust/ranking modifiers stack onto whatever
  per-unit-cost metric the pack defines.
- `/car-hunt` and its workflows are untouched by this engine until a deliberate,
  eval-gated cutover. See `PARITY.md`.
- New domains start **draft-only** and **interactive**; they earn auto-send and
  scheduling only by clearing their own eval.
