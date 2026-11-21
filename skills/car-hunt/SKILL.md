---
name: car-hunt
description: 'Find, research, and rank used Honda/Toyota/Scion vehicles (Civic, Accord, CR-V, Camry, Corolla,
  RAV4, Tacoma, Scion tC/xD) by CPM (cost per remaining mile). Also supports Insurance Claim Comp mode:
  finds the highest-priced national dealer comps for a totalled vehicle to maximize insurance ACV payout.
  Researches reliability by model year, searches AutoTrader/CarGurus/Facebook Marketplace/Auto.dev, calculates
  value score, ranks candidates, and runs VIN recall/TCO lookups via NHTSA + Auto.dev CLI.'
license: MIT
metadata:
  argument-hint: '[make model year-range max-price zip radius | --mode insurance-comp year make model
    trim drivetrain mileage]'
---

# Car Hunt — Used Vehicle Finder & Ranker

Search, score, and rank used Honda/Toyota vehicles by Cost Per Mile (CPM) — the core value metric. Lower CPM = more remaining useful life per dollar spent.

Also supports **Insurance Claim Comp mode** — finds the highest-priced national dealer comps for a vehicle being totalled by insurance, to maximize your ACV payout.

---

## Mode Detection

Car Hunt has two modes. Detect from keywords in the user's request (or the skill arguments) or ask if ambiguous:

| Trigger keywords | Mode |
|---|---|
| "insurance comp", "insurance claim", "totalled", "total loss", "ACV", "actual cash value", "totaled" | **Insurance Claim Comp** — read [references/insurance-comp.md](references/insurance-comp.md) and follow it |
| All other invocations | **Standard Hunt** — continue through Core Formula and Steps 1–7 |

**If mode is Insurance Claim Comp:** read `references/insurance-comp.md` and follow it. Do NOT run the Standard Hunt steps (reliability research, CPM scoring, test-drive prep, outreach). Those are irrelevant to an insurance claim.

---

## Household Config (read first)

Every run starts by reading `config/household.yaml` (next to this file). It holds the
user's own values: home ZIP, city and state, Facebook Marketplace city ID, Craigslist
regions, default makes/models, scheduled-run defaults, the home metro's
location-quality tiers, the outreach opener, the title-transfer rules for their
state, output folders, and the tracking-sheet ID.

**If `config/household.yaml` is missing:** copy `config/household.example.yaml` to
`config/household.yaml`, ask the user for each value in one message (ZIP, city,
state, preferred makes/models, outreach wording, where to save files), and write
their answers. Leave a key empty rather than guessing. Never put the user's values
back into this file or the example.

Below, `CONFIG.<key>` means a value from that file (e.g. `CONFIG.location.zip`).

---

## Tools this works with

Check these before running. Tell the user upfront what is available and what will be
degraded. Any agent or harness works; use whatever provides the capability.

| Capability | Examples | Required for | Degraded without |
|---|---|---|---|
| **Web search + fetch a URL** | built-in web search/fetch tools, a search API, `curl` | Step 1 research, Step 2 search, deep-dive | Nothing works well — this is the baseline |
| **Shell (bash + Python 3)** | any local shell | Auto.dev CLI, the tested helpers in `qualification/` and `sources/`, PDF generation | Helpers can't run; do the checks by hand and say so |
| **Auto.dev CLI** (`npx @auto.dev/sdk`) | the CLI with a browser login or `AUTODEV_API_KEY` | Step 2 dealer search, IC mode search, VIN recalls/TCO/taxes | Falls back to web scraping; national structured search unavailable |
| **Browser automation with a logged-in session** | a Chrome/Chromium automation extension, a Playwright or Puppeteer server, or the user driving the browser manually | Step 2 Facebook Marketplace (Option C), Step 5.5 NHTSA VIN fallback, Steps 7–8 outreach and thread reading | Facebook Marketplace degrades to ~30% coverage (Google-indexed listings only); recall check needs a manual browser lookup; no outreach |
| **Spreadsheet export** | a Google Drive tool that can create a spreadsheet from CSV, the Sheets API, or writing a local `.csv` | Step 6, IC Step IC-6 | Write a CSV file and give the user its path |

### Auto.dev CLI — login and tiers

```bash
npx @auto.dev/sdk login      # opens browser → sign in → CLI authorized
npx @auto.dev/sdk whoami     # verify auth status
```

The CLI handles auth, pagination, and output formatting. Tiers: **Starter (free)** —
`listings` (all Standard Hunt and IC search steps); **Growth** — `tco` (Step 5E);
**Scale** — `open-recalls`, `taxes` (Steps 5F2, 5.5B, 5.5E). `"You need to log in
first."` → run `npx @auto.dev/sdk login`. Treat any `402: Payment Required` as "tier
not available": skip TCO silently; use the NHTSA browser fallback for recalls; skip taxes.

### Browser automation — Facebook Marketplace

A logged-in browser session is what makes Facebook Marketplace actually work. Without
it, FB is limited to whatever listings Google has indexed (typically 20–40% of active
inventory). It unlocks full Marketplace search, seller-profile extraction (Seller
Trust Score, Step 3), the message composer (Step 7), thread reading (Step 8), and the
NHTSA VIN recall fallback (Step 5.5B).

**If no browser automation is available:**
- Standard Hunt: note "Facebook Marketplace: limited coverage (no logged-in browser)" in the Step 2 summary. Use Option A (Google-indexed listings) and Option B (manual search URL). Do NOT silently skip FB — always report the gap.
- Insurance Claim Comp mode: no impact (dealer-only; FB Marketplace is not searched).

---

## Core Formula

```
CPM      = Price / (Expected_Miles − Current_Miles)
Life_Pct = Current_Miles / Expected_Miles   (lower = more life left)
```

**Remaining miles** is the denominator — you are buying future utility, not past metal.

---

## Static Vehicle Reference Table

Baseline data — augmented each run by Step 1 (live reliability research). Do NOT ask the user to re-explain these.

### Expected Lifetime Miles

| Make   | Model   | Expected Miles | Notes                              |
|--------|---------|---------------|------------------------------------|
| Honda  | Civic   | 250,000       | One of the most reliable small cars |
| Honda  | Accord  | 250,000       | 10th gen (2018+) best              |
| Honda  | CR-V    | 250,000       | Avoid 2017–2018 1.5T if cold climate |
| Toyota | Camry   | 300,000       | Exceptional longevity              |
| Toyota | Corolla | 300,000       | Extremely durable drivetrain       |
| Toyota | RAV4    | 250,000       | 5th gen (2019+) excellent          |
| Toyota | Tacoma  | 250,000       | Legendary longevity (many reach 300k+); inspect frame for rust, esp. pre-2010 |
| Scion  | tC      | 250,000       | Camry-derived engine; 1st-gen (05–10) 2AZ-FE burns oil — verify oil records |
| Scion  | xD      | 250,000       | Corolla 1.8L; durable economy hatch, many reach 200k+ |

### Baseline Reliable/Caution Years

| Make   | Model   | Caution Years        | Preferred Years | Reason                                  |
|--------|---------|---------------------|-----------------|-----------------------------------------|
| Honda  | Civic   | 2012–2015 (9th gen) | 2016+           | 9th gen had engine/AC issues            |
| Honda  | Accord  | 2013–2017 (9th gen) | 2018+           | CVT issues in 4-cyl variants            |
| Honda  | CR-V    | 2017–2018           | 2019+           | Oil dilution with 1.5T in cold climates |
| Toyota | Camry   | 2007–2011           | 2012+           | Oil consumption issues pre-2012         |
| Toyota | Corolla | —                   | 2014+           | Generally very reliable across gens     |
| Toyota | RAV4    | —                   | 2013+           | 2019+ (5th gen) preferred               |
| Toyota | Tacoma  | 2016–2017, 2006–2009 | 2013–2015, 2018+ | 3rd-gen 2016–17 auto-trans shudder/hesitation; early 2nd-gen frame rust |
| Scion  | tC      | 2005–2010 (1st gen) | 2011+           | 2AZ-FE oil consumption (piston rings); TSB on 2007–2009 |
| Scion  | xD      | 2008                | 2011+           | 1st-yr oil consumption + electrical/HVAC; later years cleaner |

### Trim Hierarchy (low → high)

| Make   | Model   | Trim Order (low → high)                                              |
|--------|---------|----------------------------------------------------------------------|
| Honda  | Civic   | LX → Sport → EX → EX-L → Sport Touring → Touring                    |
| Honda  | Accord  | LX → Sport → EX → EX-L → Sport 2.0T → Touring                      |
| Honda  | CR-V    | LX → EX → SE → EX-L → Touring                                       |
| Toyota | Camry   | L → LE → SE → XLE → XSE → TRD → XSE V6 → XLE V6                    |
| Toyota | Corolla | L → LE → SE → XLE → XSE → Apex                                      |
| Toyota | RAV4    | LE → XLE → XLE Premium → TRD → Adventure → Limited → Platinum       |
| Toyota | Tacoma  | SR → SR5 → TRD PreRunner → TRD Sport → TRD Off-Road → Limited → Trailhunter → TRD Pro |
| Scion  | tC      | Base → Release Series (RS) — mono-spec, no trim ladder; RS = special editions |
| Scion  | xD      | Base → Release Series (RS) — mono-spec, no trim ladder; RS = special editions |

---

## Search Parameters

If the request or skill arguments include any of make, model, year range, max price, zip, radius, parse them.

Otherwise ask (combine into one prompt):

> "Let's set up your search. Answer any you know:
> 1. Which makes/models? (default: {CONFIG.interactive_defaults.makes_models})
> 2. Year range? (e.g., 2002–2023)
> 3. Max price? (e.g., ${CONFIG.interactive_defaults.example_max_price})
> 4. Your zip code? (default: {CONFIG.location.zip})
> 5. Search radius — how many miles from your zip to search? (e.g., {CONFIG.interactive_defaults.example_radius_mi})
> 6. Max odometer — the highest mileage you'll consider on the car itself? (e.g., {CONFIG.interactive_defaults.example_max_odometer} — leave blank to include all)
> 7. Min trim? (optional — e.g., 'EX or above')"

Store as `MAKES_MODELS` (list of make/model pairs), `YEAR_MIN`, `YEAR_MAX`, `MAX_PRICE`,
`ZIP`, `RADIUS` (miles from the ZIP — how far away the car can be), `MAX_ODOMETER`
(optional; defaults to expected lifetime per model) and `MIN_TRIM` (optional).

Location inputs for Step 2 come from `CONFIG.location`: `search_terms` (city/state words appended to WebSearch queries), `fb_marketplace_city_id`, `craigslist_regions`, and `state` (Auto.dev `--state`). If the user searches from a ZIP other than `CONFIG.location.zip`, derive these for that ZIP and offer to save them.

**Facebook Marketplace city ID:** always use the numeric ID, never the city slug — slugs are disambiguated by IP/cookies and can resolve to a same-named city in another country. To find it, open the city's Marketplace page once in a logged-in browser and read the number from the URL after Facebook redirects; save it as `CONFIG.location.fb_marketplace_city_id`.

---

## Step 1: Reliability Research

**Run this before searching listings.** The goal is to produce a per-model reliability card — best years to buy, years to avoid, and known problem patterns — sourced from live data rather than static knowledge. This step takes ~2 minutes and pays for itself by preventing bad purchases.

For each make/model in `MAKES_MODELS`, search Consumer Reports, JD Power, Edmunds,
RepairPal, CarComplaints and owner forums in parallel, fetch the top hits, and output
one **Reliability Card** per model (best years, caution years, avoid years, top-3
recurring problems, generation boundaries, reliability scores, one buying tip).
Queries and the card template: [references/reliability.md](references/reliability.md).

### How Research Feeds into Scoring

After producing reliability cards, build an **adjusted caution list** that merges:
- Static baseline caution years (from reference table above)
- Any additional years flagged by live research

Use this merged list — not just the static table — when applying flags in Step 3.

If research contradicts the static table (e.g., a year previously flagged is now cleared by updated data), note the discrepancy and use the live data.

---

## Step 2: Search for Listings

Search Facebook Marketplace, Craigslist, and Auto.dev in parallel for each make/model combination. **AutoTrader and CarGurus are DEPRECATED for routine hunting** (see `references/sources.md`) — Auto.dev covers the same dealer inventory. (CarGurus is still used in Insurance Claim Comp mode, which is unaffected by this deprecation.)

> **Inspect before batch:** Before running bulk Auto.dev CLI listing queries, run one single-model call (e.g., `--make Honda --model Civic --limit 1 --json`) and inspect the actual JSON field names. Do not assume field names from documentation — verify `make`, `model`, `price`, `mileage`, `year` paths in the real response before extracting across all models.

### Per-source mechanics — read `references/sources.md`

**Read [references/sources.md](references/sources.md) before searching.** It holds the
hard-won details for each source:

| Source | Status | Key facts (full detail in the reference) |
|---|---|---|
| **Facebook Marketplace** | Primary private-party source | Options A (Google-indexed), B (manual search URL), C (logged-in browser — preferred). Numeric city ID, `/search?query=` URL form, `radiusKM` is km, **Discontinued makes** (Scion free-text + `sources/scion.py` post-filter), message-composer mechanics, seller-profile regexes, already-messaged detection. |
| **Craigslist** | Primary | Modern search is a JS app — a thin shell is **gating, not zero inventory**; run every page through `sources/craigslist.py` `diagnose()`. Regions from `CONFIG.location.craigslist_regions`. |
| **Auto.dev** | Dealer inventory (structured) | Inspect fields first; `--state {CONFIG.location.state}`; **0-miles guard**. |
| **AutoTrader**, **CarGurus** | Deprecated for routine hunting | WebSearch-to-listing only; CarGurus still used in IC mode. |
| **WebSearch fallback** | Any source | `site:` queries with `CONFIG.location.search_terms`. |

### Data to Extract Per Listing

For each listing found, extract:
- `date_found` — today's date
- `date_posted` — the date the listing was originally posted (shown on the listing page as "posted" or "listed on")
- `make`, `model`, `year`, `trim`
- `miles` — current odometer
- `price` — asking price in USD
- `doors` — `2` or `4` (coupe vs. sedan/hatchback); extract from listing text or body style
- `transmission` — `Auto` or `Manual`; extract from listing text or specs
- `location` — city, state
- `distance_mi` — estimated driving distance from user's ZIP to listing city (see Distance Estimation below)
- `dealer` — dealership name, "Private", or "Facebook Marketplace"
- `link` — direct listing URL
- `notes` — any flags (rental history, accidents, new tires, warranty, etc.)

If a field is not found, note it as "—" — it can be filled during deep-dive.

### Distance Estimation

After collecting all unique listing cities, geocode the user ZIP and each unique listing city with the free Nominatim API (no key;
cache repeated cities), take the Haversine straight-line distance, and multiply by
**1.3** for road routing (`driving_est`). Requests and code: the "Distance estimation"
section of [references/sources.md](references/sources.md).

Display as `~{driving_est} mi`. If geocoding fails for a city, use `—`.

**Add `Distance` column to the output table and sheet** — sort remains CPM ascending, but distance helps the user weigh travel cost against CPM savings.

**Hard distance cap:** **Drop any listing whose `driving_est` exceeds `RADIUS` miles** — it is too far to be worth a test drive, regardless of CPM. Record dropped-for-distance listings in the `disqualified` array with `reason: "too far (~{driving_est} mi > {RADIUS} mi cap)"` so they are auditable but never ranked or contacted. The FB Marketplace `radiusKM` URL parameter is a coarse pre-filter only (FB often returns listings well outside it); this geocoded cap is the authoritative distance gate. If a city can't be geocoded (`driving_est` = "—"), keep the listing but flag "distance unknown" — do NOT auto-drop it.

**Staleness filter:** If `date_posted` is more than 21 days before today, **skip the listing entirely** — it has almost certainly sold or the seller is unresponsive. If `date_posted` cannot be determined, include the listing but note "Post date unknown" in Notes.

**Hard disqualification filters — skip any listing that matches ANY of:** dealer/finance
language ("buy here pay here", "we finance"); title problems (no/lost title, salvage,
rebuilt, lien); non-running or major mechanical ("doesn't run", "project car", "needs
transmission", "blown head gasket", "ran when parked"…); scam redirects ("messenger
broken", email-only, urgent off-platform texting, absurdly low price); implausibly low
mileage for the age without explanation (log for human review, no auto-contact). Full
keyword lists: "Disqualification keyword lists" in [references/sources.md](references/sources.md).

**Description scraping is mandatory before disqualification.** The structured "About this vehicle" block (mileage, trim, transmission) is not enough — scam, title, and non-running disclosures live almost exclusively in the seller's free-form description. On FB Marketplace, the description appears under "Seller's description" and may be truncated behind a "See more" link; expand and capture the full text before running disqualification regexes.

The non-running scan must run on the **full concatenated text** of: listing title + structured fields + seller's description + any visible "Condition" or "Notes" fields. Do not rely on a single regex against partial text.

**Authoritative gate — use the tested filter, not eyeballing.** The keyword lists are documentation; the decision is owned by `skills/car-hunt/qualification/listing_filter.py` (`disqualifying_reason(text)`), which is unit-tested (`test_listing_filter.py`) and handles negation ("clean title, not salvage") and resolution ("head gasket replaced," "new transmission") so it doesn't false-positive on honest listings. **Before contacting OR drafting to any listing, pass its full concatenated text through the filter** — in the scheduled workflow:
```
printf '%s' "<FULL listing text>" | python3 skills/car-hunt/qualification/listing_filter.py
```
A non-zero exit (`DISQUALIFIED: <reason>`) means do NOT contact; record the reason in `disqualified[]`. This mirrors how seller-reply qualification moved the consequential decision into tested code — a non-running car must never receive an opener.

Log all disqualified listings in a separate "Disqualified" section at the end of output with the reason — do not silently drop them.

### Parallel Search Strategy

Launch all make/model × source searches simultaneously. Target **50+ raw candidates** before filtering — after disqualification and staleness filtering, 15 is not enough survivors for a useful comparison.

**Exhaustive coverage is mandatory.** Do NOT stop at the first page of results, declare success after a few listings, or give up on a source after one failure. For each source:
- Paginate all result pages until no more listings exist (Craigslist: `&s=120`, `&s=240`, etc.)
- If a fetch fails, retry once then fall back to WebSearch — but always report the fallback
- Every in-scope vehicle must be evaluated; none may be silently skipped
- Note at the end of Step 2 exactly how many pages/results were checked per source

**Batch listing-page fetches efficiently.** After extracting all URLs from a search results page, do NOT fetch each listing page one at a time sequentially. Instead:
1. Extract ALL listing URLs from a search page in a single read
2. Score candidates based on the brief preview data (price, mileage, year) shown in the search results — this is enough to disqualify ~60% of listings without fetching their pages
3. Only WebFetch individual listing pages for candidates that pass the price/mileage preview filter
4. This keeps total fetches manageable while still covering all in-scope listings

**Why results are often ~15:** A single Craigslist search page has 120 results but only a fraction pass price/mileage/year filters. Working through every configured region × every model, each search potentially paginating, is the only way to find 50+ qualifying candidates. Do not stop early.

---

## Step 3: Calculate CPM and Score Each Listing

For each listing, compute:

```python
expected_miles = EXPECTED_MILES[make][model]  # from reference table
remaining      = expected_miles - current_miles
cpm            = price / remaining             # dollars per remaining mile
life_pct       = current_miles / expected_miles  # 0.0 to 1.0
```

**Flag rules** (use merged caution list from Step 1 research):
- `life_pct > 0.75` → mark as ⚠️ HIGH CONSUMPTION
- Year in merged caution list → mark as ⚠️ CAUTION YEAR + include the specific issue from the reliability card
- Year in "avoid" list from research → mark as 🚫 AVOID YEAR
- `remaining < 50,000` → mark as ⚠️ LOW REMAINING LIFE
- Source is Facebook Marketplace → mark as 🏠 PRIVATE SELLER (neutral, just informational)

**Trim score** (for tiebreaking, not ranking):
- Assign a numeric rank from the trim hierarchy table (higher = better)
- Display trim rank alongside trim name

### Location Quality Tier

The seller's location is a real value signal. Used cars from higher-income areas correlate (statistically, not deterministically) with: more frequent dealer service, more single-owner histories, gentler use patterns (shorter commutes, more multi-car households spreading miles, fewer hard-loaded trips), and sellers who are less price-sensitive (i.e., more flexibility in negotiation since the asking price isn't load-bearing for their finances). Cars from lower-income areas are not categorically worse — there are well-maintained gems in every zip — but the base-rate odds are different, and that's worth a small modifier in ranking.

**Tier the listing by city/neighborhood**, not by ZIP — Census-tract income data per ZIP is noisy and ZIPs cross municipal boundaries. The home metro's table lives in `CONFIG.location_tiers` (tier → places, median household income, CPM modifier, notes). Use it as written; if it is missing or the listing's city isn't in it, see "Extending to other metros" below the table.

| Tier | Median HHI ~ (default thresholds) | Default CPM modifier | Meaning |
|---|---|---|---|
| **A** (preferred) | $100K+ | −$0.005/mi | Highest base-rate odds of a single-owner, dealer-serviced car; sellers often replace cars on a cosmetic schedule; good negotiation flexibility. |
| **B** (good) | $75K–$100K | −$0.002/mi | Solid maintenance habits common; mixed dealer/independent service; negotiation typical. |
| **C** (neutral) | $55K–$75K | none | No directional signal. Treat at face value. |
| **D** (caution) | <$55K | +$0.003/mi | Higher base-rate of deferred maintenance and harder use; tighter negotiation. Not a disqualifier — verify maintenance with extra rigor. |

**How tier affects scoring (apply during Step 3):** add the tier's `cpm_adjust` from `CONFIG.location_tiers` (defaults above) to the real CPM to get a "quality-adjusted CPM" for ranking — e.g., a real $0.044/mi from a Tier A town ranks against other cars at $0.039/mi.

This is a **ranking modifier only** — the displayed CPM remains the real number. The adjusted CPM is used for sort order and for the comparison tables in Step 5.25 (head-to-head). Always show both: real CPM and tier-adjusted CPM.

Tier-aware flags, where to display `Tier`, building a table for a new metro, and how to word
tier in user-facing copy: [references/scoring.md](references/scoring.md). **Extending to other metros:** when `CONFIG.location_tiers` is empty or the user searches outside the configured metro, build a 4-tier table with the thresholds above and save it to `config/household.yaml`. **Name the economic mechanism, never the demographic.**

### Seller Trust Score

From the Facebook seller profile (tenure, rating and count, active listings — read only
with a logged-in browser), classify each private listing — evaluate **CAUTION** first,
then **TRUSTED**, else **NEUTRAL** (also the default when the profile is unreadable;
Craigslist and other anonymous private sellers are NEUTRAL; dealers are `—`). TRUSTED
subtracts $0.003/mi and CAUTION adds $0.004/mi to the quality-adjusted CPM, stacked on
the tier adjustment:

`Adj.CPM = real CPM ± location-tier adjustment ± seller-trust adjustment` (the sort key).

Thresholds, display format (`TRUSTED ★4.8(12)`, `CAUTION ⚠ new acct`, …) and the
`🔴 CAUTION SELLER` / `🟡 UNVERIFIED SELLER` flags: [references/scoring.md](references/scoring.md).

---

## Step 4: Rank and Present Results

Sort all candidates by **CPM ascending** (best value first).

Present the reliability cards first, then the ranked table, then flags and a summary.
Table columns: `# | Make/Model | Year | Trim | Dr | Trans | Miles | Price | CPM | Adj.CPM | Life% | Dist | Posted | Location | Tier | Seller | Dealer | Flags | Link`.
Summary lines: best CPM overall, best local deal, best private seller, best trusted
seller, best per make, best reliability year, and the count skipped for missing data.
Full layout with a worked example: [references/scoring.md](references/scoring.md).

Then ask:
> "Want to dig deeper on any of these? I can pull NHTSA recall/complaint data and check the VIN for any you're seriously considering. Just give me the numbers (e.g., '#1, #3') or say 'all top 5'."

---

## Step 5: Deep-Dive (Optional — user-initiated)

When the user selects candidates or gives a VIN, **read [references/deep-dive.md](references/deep-dive.md)**
and run its checks in parallel for each: NHTSA recalls, complaints and safety rating
(free APIs, no key), market comparison, Auto.dev TCO, and the VIN lookup (vPIC decode —
any mismatch is a 🚫 stop — per-VIN open recalls, and free/paid history-report links;
never buy a paid report automatically).

## Step 5.25: Head-to-Head Comparison (when the user is weighing two cars)

Generate an explicit side-by-side table and apply the **information-asymmetry rule**:
the car with verified data (title, owners, per-VIN recalls) is the higher-confidence
buy even at a slightly worse CPM. Be opinionated — pick one, with a fallback
condition. Full table and rules: [references/deep-dive.md](references/deep-dive.md).

## Step 5.5: Pre-Test-Drive VIN Finalization

**Trigger:** the user says they will go look at, test drive, or buy a specific car.
This step gates the test drive. **Read [references/test-drive.md](references/test-drive.md)**
and follow it: get and echo the VIN, decode and cross-check it, per-VIN recall check,
title pre-flight, estimated out-of-pocket, then generate the car-specific
**test-drive checklist** (Markdown + PDF saved to `CONFIG.paths.checklist_output_dir`)
and hand over the reusable **fraud/paperwork checklist** and **bill of sale** from
`forms/`. Title-transfer lines come from `CONFIG.jurisdiction`.

---

## Step 6: Export to a Spreadsheet

After presenting results, always offer to export:

> "Want me to save these results to a spreadsheet?"

Use whatever spreadsheet capability is available (see **Tools this works with**): a
Google Drive tool that can create a spreadsheet from CSV, the Google Sheets API, or —
if neither is available — a local `.csv` file whose path you give the user.

### One persistent tracking sheet

1. Read the current sheet ID from `CONFIG.tracking_sheet.id`.
2. If one exists, download its rows, merge the new results (deduplicate by Link URL), and write the merged sheet.
3. If none exists, create a sheet titled `CONFIG.tracking_sheet.title`.
4. Write the resulting sheet ID back to `config/household.yaml` (`tracking_sheet.id`) and show the sheet's link prominently.

**Many Drive tools can only *create* files, not overwrite them.** If yours creates a
new file on every write, each run gets a new sheet ID: save the new ID to the config,
and say loudly in the run summary — "⚠️ Sheet ID changed — your bookmark to the prior
sheet now shows old data; here's the new one." A stable URL needs real Sheets API
write access (e.g. `gspread` with a service account, or the Sheets `values:update`
endpoint with an OAuth token).

**Upload tip:** when a Drive tool converts uploads, send **`text/csv`** (base64 CSV if
it wants encoded content) and let it convert to a Google Sheet. Uploading an xlsx MIME
type commonly fails base64 validation.

**Deduplication logic:** match rows by `Link` URL (same URL = same listing); on a price
change, update the row and note "Price changed: was $X"; mark prior-run listings not
found this run `STALE — may be sold` (never delete); add new listings as new rows.

### Column Order

```
Date | Make | Model | Year | Package | Doors | Trans | Miles | Cost | CPM | Adj.CPM | Life | Dist | Posted | Location | Tier | Seller | Dealer | Link | Notes | Contacted
```

Formats per column (dates, `$0.019` CPM, `Contacted` = `YYYY-MM-DD sent`, …):
[references/scoring.md](references/scoring.md). Build the CSV with Python's `csv`
module (UTF-8), one row per listing.

### Row Order and Completeness

Sort rows by CPM ascending (same order as the ranked output). Include ALL scored
listings, even those over the mileage filter (flag them in Notes), and unscored
listings at the bottom with `—` for CPM and Life and the reason in Notes. Never drop
a listing silently.

---

## Scheduling

This skill is designed to run periodically (e.g., daily or weekly) from whatever scheduler your agent or CI offers.

When running in scheduled/automated mode:
- **Skip Step 1 (reliability research)** unless the model list has changed — reliability cards don't change week to week; use the static reference table or cache the last research output
- Only surface **new** listings not seen before (compare links against prior run output)
- Skip Step 6 (sheet write-back) unless new high-value finds warrant it
- Send a push notification summary if new candidates have CPM below the current best in the tracked sheet

Default search parameters when running unattended come from `CONFIG.scheduled_defaults` (`makes_models`, `zip`, `radius_mi`, `max_price`, `year_min`, `year_max`, `max_odometer`). Update them there after an interactive session changes the user's targets. A scheduler that passes its own parameters overrides them.

---

## Step 7: Automatic Outreach (Optional)

Only with explicit user confirmation, and only on Facebook Marketplace listings with a
logged-in browser. **Read [references/outreach.md](references/outreach.md) first.** The
opener is `CONFIG.outreach.opener_template`; personalize `[FIRST_NAME]` only from the
message-modal recipient name (never the listing sidebar), check "Message again" and the
sheet's `Contacted` column before sending, show a dry run and wait for "proceed", and
**fail closed**: send only after re-reading the composer and finding a
`CONFIG.outreach.opener_fingerprint` fragment — never send Facebook's generic
"is this still available?" prefill.

## Step 8: Read & Interpret Messenger Threads (logged-in browser only)

Runs at the **start** of a run, before ranking. **Read [references/outreach.md](references/outreach.md)**
— its Step 8 section is authoritative. In short: read every recent thread in full as
attributed turns (`seller` / `automation` / `human`); quote or it didn't happen; a
human-led thread is hands-off except for objective disqualifiers; drafts only, never
typed into Messenger. Seller qualification (VIN / title / runs) is extracted by the
agent and **decided by the tested Python engine** in `qualification/`.

## Insurance Claim Comp Mode

Find the highest-priced comparable dealer listings (and recently-sold dealer comps)
for a vehicle being totalled by insurance, to support the **maximum actual cash value
(ACV)**. National scope, dealer-only, sold ≤12 months included, sorted price
descending, no CPM. **Read [references/insurance-comp.md](references/insurance-comp.md)**
for Steps IC-1 to IC-6 (collect details, national search, score, comp package,
negotiation playbook, export) and the IC-TC-1..4 regression test cases.

---

## Output Format Rules

1. **Always show CPM to 3 decimal places** — `$0.103/mi` not `$0.10/mi`
2. **Always show Life% as integer** — `17%` not `0.17`
3. **Links must be real or explicitly marked manual** — every Link column value must be one of: (a) an exact URL returned by WebFetch/WebSearch that points to a specific listing, or (b) a search URL the user can open manually, labeled "Manual search — [source]". Never use a homepage (`facebook.com/marketplace`, `craigslist.org`) as a listing link. Never construct or guess a listing URL.
4. **Flag before ranking** — flags are informational, not disqualifying; reliability card context appears in flag detail
5. **Never silently drop a listing** — if miles or price are missing, show the row with `—` and note it couldn't be scored
6. **Sort by CPM always** — don't re-sort by price or miles unless user asks
7. **Show source column** — AutoTrader / CarGurus / Craigslist / FB Marketplace — so the user knows where to find the listing

---

## Important Rules

1. **Lower CPM = better value** — always. Never present higher CPM as "better."
2. **Expected miles are model-specific** — never use a flat number across all vehicles.
3. **Flag caution years, hard-flag avoid years** — ⚠️ for caution, 🚫 for avoid; never silently drop either.
4. **Live research overrides static table** — if Step 1 clears or adds a year, use that; note any contradiction.
5. **VIN lookups are user-initiated** — never auto-run paid services.
6. **NHTSA APIs are free and require no key** — always run them for deep-dive candidates.
7. **Life% is consumed life, not remaining** — `17%` means 17% used, 83% left. Make this explicit in output.
8. **Do not filter by CPM threshold** — show all scored candidates ranked; let the user choose the cutoff.
9. **Facebook Marketplace scraping often fails** — always note when it was attempted and whether it succeeded, so the user knows to check manually if needed.
