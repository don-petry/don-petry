# Domain Pack — Cars (used Honda/Toyota)

The car knowledge for the generic `goods-hunt` engine. Combined with
`../SKILL.md` this reproduces the behavior of the live `skills/car-hunt` skill —
see `../PARITY.md` for the section map. The live `/car-hunt` remains the
production entry point until a deliberate, eval-gated cutover; the two giant
checklist templates (test-drive + PDF, fraud/paperwork) stay **canonical in
`skills/car-hunt/references/test-drive.md` (Step 5.5 §F–H)** and are referenced (not duplicated) here
to avoid drift.

```yaml
domain: cars
life_unit: miles
consumed_life: odometer
item_types:
  - { name: vehicle, policy: used_market, metric: cpru }
location_signal: affluent_favorable
default_radius: 25                 # scheduled default; interactive runs ask
freight_option: false
cadence: scheduled                 # cars are the live scheduled hunt (car-hunt workflows)
outreach_mode: autosend            # car-only; gated by QUAL_SEND_ENABLED + eval
stale_days: 21
```

**Description / arg form (for the alias):** "Find, research, and rank used
Honda/Toyota vehicles (Civic, Accord, CR-V, Camry, Corolla, RAV4) by CPM."
Arg: `[make model year-range max-price zip radius | --mode comp year make model trim drivetrain mileage]`.

**Comp-mode triggers:** "insurance comp", "insurance claim", "totalled",
"total loss", "ACV", "actual cash value", "totaled".

**Automation-opener fingerprint (Step 8 turn attribution):** an outbound turn
containing a fragment from `outreach.opener_fingerprint` in the cars shared config
(the standard opener below) = `automation`; any other outbound = `human`.

---

## Core metric

```
CPM      = Price / (Expected_Miles − Current_Miles)
Life_Pct = Current_Miles / Expected_Miles
```
Flag rules: `life_pct > 0.75` → ⚠️ HIGH CONSUMPTION; year in merged caution list →
⚠️ CAUTION YEAR (+ the specific issue); year in avoid list → 🚫 AVOID YEAR;
`remaining < 50,000` → ⚠️ LOW REMAINING LIFE; FB private seller → 🏠 (neutral).
Output conventions: CPM to 3 decimals, Life% integer, sort by CPM ascending.

## Expected Lifetime Miles

| Make   | Model   | Expected Miles | Notes                              |
|--------|---------|---------------|------------------------------------|
| Honda  | Civic   | 250,000       | One of the most reliable small cars |
| Honda  | Accord  | 250,000       | 10th gen (2018+) best              |
| Honda  | CR-V    | 250,000       | Avoid 2017–2018 1.5T if cold climate |
| Toyota | Camry   | 300,000       | Exceptional longevity              |
| Toyota | Corolla | 300,000       | Extremely durable drivetrain       |
| Toyota | RAV4    | 250,000       | 5th gen (2019+) excellent          |

## Baseline Reliable/Caution Years

| Make   | Model   | Caution Years        | Preferred Years | Reason                                  |
|--------|---------|---------------------|-----------------|-----------------------------------------|
| Honda  | Civic   | 2012–2015 (9th gen) | 2016+           | 9th gen had engine/AC issues            |
| Honda  | Accord  | 2013–2017 (9th gen) | 2018+           | CVT issues in 4-cyl variants            |
| Honda  | CR-V    | 2017–2018           | 2019+           | Oil dilution with 1.5T in cold climates |
| Toyota | Camry   | 2007–2011           | 2012+           | Oil consumption issues pre-2012         |
| Toyota | Corolla | —                   | 2014+           | Generally very reliable across gens     |
| Toyota | RAV4    | —                   | 2013+           | 2019+ (5th gen) preferred               |

## Trim Hierarchy (low → high, for tiebreak scoring)

| Make   | Model   | Trim Order (low → high)                                        |
|--------|---------|----------------------------------------------------------------|
| Honda  | Civic   | LX → Sport → EX → EX-L → Sport Touring → Touring               |
| Honda  | Accord  | LX → Sport → EX → EX-L → Sport 2.0T → Touring                  |
| Honda  | CR-V    | LX → EX → SE → EX-L → Touring                                  |
| Toyota | Camry   | L → LE → SE → XLE → XSE → TRD → XSE V6 → XLE V6                |
| Toyota | Corolla | L → LE → SE → XLE → XSE → Apex                                 |
| Toyota | RAV4    | LE → XLE → XLE Premium → TRD → Adventure → Limited → Platinum  |

## Quality Card sources (Step 2)

Consumer Reports (`"{make} {model} reliability by year" site:consumerreports.org`),
JD Power (`site:jdpower.com`), Edmunds long-term (`site:edmunds.com`), RepairPal
(`site:repairpal.com`), CarComplaints worst-years (`site:carcomplaints.com`), owner
forums (`years to avoid reddit OR forum`). Card fields: best/worst years, top-3
issues, generation boundaries, RepairPal/JD/CR scores, buying tip.

## Sources (Step 3)

**Universal:** Facebook Marketplace (numeric city ID =
`CONFIG.location.fb_marketplace_city_id`) + Craigslist (category **`cta`** = cars+trucks;
regions: `CONFIG.location.craigslist_regions` — `https://{region}.craigslist.org/search/cta?query={make}+{model}&max_price={MAX}&auto_miles_max={MAX_ODO}&sort=priceasc`, paginate `&s=120`).

**AutoTrader** (WebSearch to individual listings; pages are JS-rendered — don't
WebFetch search pages): `site:autotrader.com used {ymin}-{ymax} {make} {model} under ${max} {CONFIG.location.search_terms}`; listing format `autotrader.com/cars-for-sale/vehicledetails.xhtml?listingId=…`. Handle 503 by noting outage + continuing.

**CarGurus** — ⚠️ DEPRECATED for routine hunting (use Auto.dev); **still used in
Comp mode**. `site:cargurus.com used {make} {model} {ymin}-{ymax} {CONFIG.location.search_terms} under ${max}`.

**Auto.dev** (structured dealer inventory — automotive API CLI):
```bash
npx @auto.dev/sdk whoami 2>&1                      # if not logged in, skip + note
npx @auto.dev/sdk listings --make Honda --model Civic --limit 1 --json 2>&1   # inspect fields first
npx @auto.dev/sdk listings --make {make} --model {model} --year {ymin}-{ymax} \
  --price 0-{MAX} --miles 0-{MAX_ODO} --state {CONFIG.location.state} --sort "price:asc" --limit 50 --json 2>&1
```
Field paths: `retailListing.miles`; `vehicle.year/make/model/trim`;
`retailListing.price/city/state/dealer`. **0-miles guard:** `miles==0` = unknown
odometer (not new) → skip CPM, list under "Mileage not reported". Tiers: Starter
(free) = `listings`; Growth = `tco`; Scale = `open-recalls`, `taxes`. Treat any
402 as "tier unavailable" → skip/fallback.

Per-listing car fields: `make, model, year, trim, miles, price, doors` (2=coupe /
4=sedan), `transmission` (Auto/Manual), location, dealer, link, notes.

## Deal-breakers (Step 3.6, car vocabulary)

Skip on: dealer/finance language ("down payment", "monthly payment", "buy here pay
here", "BHPH", "in-house financing", "we finance"); title problems ("no/lost
title", "salvage", "rebuilt title", "lien"); non-running ("won't crank", "won't
start", "needs motor/engine/transmission", "blown head gasket", "seized",
"knocking", "rod knock", "for parts", "as is" + non-running); scam redirects;
mileage implausibly low for age without explanation. Premise: the buyer needs a
running, clean-title car.

## Location-Quality Tiers — home metro (from config)

The household's 4-tier A/B/C/D table (places, median household income, CPM modifier)
lives in `location_tiers` of the file named by `CONFIG.packs.cars.shared_config`
(car-hunt's `config/household.yaml`). Default thresholds and modifiers:

| Tier | Median HHI ~ | CPM modifier (ranking only) |
|---|---|---|
| **A** | $100K+ | **− $0.005/mi** |
| **B** | $75K–$100K | **− $0.002/mi** |
| **C** | $55K–$75K | none |
| **D** | <$55K | **+ $0.003/mi** |

Tier-aware rules: A/B + sparse desc → still ⚠️ but "maybe terse seller"; D + sparse
→ ⚠️⚠️; A/B + high price → negotiation room (often 8–12% off ask); D + below-market
→ verify scam/title with extra rigor. (No table, or a new metro → build a comparable
4-tier table on first run, same thresholds, and save it to the config.)

## Seller Trust Score (FB)

| Score | Label | Criteria | CPM adj |
|---|---|---|---|
| S− | CAUTION | `joined_months < 12` OR `active_listings ≥ 10` OR (`fb_rating < 4.0` AND `fb_rating_count ≥ 5`) | **+ $0.004/mi** |
| S+ | TRUSTED | `joined_months ≥ 36` AND (`fb_rating ≥ 4.5` OR `fb_rating_count = 0` with `joined_months ≥ 24`) AND (`active_listings ≤ 3` OR null) | **− $0.003/mi** |
| S0 | NEUTRAL | all other cases incl. profile unreadable (default) | none |

Evaluate CAUTION → TRUSTED → NEUTRAL. Defaults: Craigslist/AutoTrader/CarGurus
private = NEUTRAL; dealer = `—`. Display: `TRUSTED ★4.8(12)`, `TRUSTED`, `NEUTRAL`,
`NEUTRAL (profile unreadable)`, `CAUTION ⚠ new acct`, `CAUTION ⚠ 14 listings`, `—`.
Profile regexes: `/Joined Facebook (\d+) (year|month)s? ago/i`, `…weeks? ago/i`,
`…days? ago/i` (weeks/days → joined_months=0 → CAUTION), `/(\d+\.\d+) \((\d+)
ratings?\)/i`, `/(\d+) active listings?/i`.
`Adj.CPM = real CPM ± location-tier ± seller-trust`.

## Qualification slots (Step 8)

Defined in code: `skills/car-hunt/qualification/specs.py` → `CARS` (slots
`vin`/`title`/`runs`). Rubric:

| Slot | pass | fail (disqualifies) | unknown |
|---|---|---|---|
| `vin` | VIN or door-jamb photo provided | refuses/evades | not asked |
| `title` | clean, in seller's name, in hand | rebuilt/salvage/branded/flood/junk/lost/no-title/lien-unreleased/bill-of-sale-only/not-in-their-name | not stated |
| `runs` | runs & drives, no warning lights/major issues | won't run/start, or major mechanical (transmission, engine knock, overheating, head gasket) | not stated |

## Verification recipes (Step 5 / pre-commit)

NHTSA (free): `GET https://api.nhtsa.gov/recalls/recallsByVehicle?make={make}&model={model}&modelYear={year}` ·
`…/complaints/complaintsByVehicle?…` · `…/SafetyRatings/modelyear/{year}/make/{make}/model/{model}`.
vPIC decode: `GET https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{VIN}?format=json`
(verify ModelYear/Make/Model/Trim/BodyClass/Engine/Transmission/DriveType/Plant
against listing — mismatch = 🚫 STOP; misread pairs to echo-check: 8/B, 1/I/L,
0/O/Q, 5/S, 2/Z). Per-VIN recalls: `npx @auto.dev/sdk open-recalls {VIN} --json`,
else NHTSA browser fallback at `https://www.nhtsa.gov/recalls` (input
`#ymm-vin-recalls-search-input`; parse the block anchored on `VIN: {VIN}`, not the
help-text literal; **do NOT** use Honda's `mygarage.honda.com` portal). Market:
WebSearch `"KBB {year} {make} {model} {trim} {miles} miles value"` (KBB/Edmunds 403
on WebFetch → snippets only). TCO: `npx @auto.dev/sdk tco {VIN} --zip {ZIP} --json`.
Out-of-pocket: `npx @auto.dev/sdk taxes {VIN} --price {LISTING_PRICE} --zip {ZIP} --json`.
History links (manual, never auto-purchase): `nicb.org/vincheck` (free 5/day),
`vehiclehistory.com/license-plate-search/{VIN}` (NMVTIS $2–5), `carfax.com/vehicle/{VIN}`,
`autocheck.com/vehiclehistory/autocheck/en/vinbasics?vin={VIN}`.

**Checklists (canonical in `skills/car-hunt/references/test-drive.md`):** the full
**test-drive checklist** + PDF generation (Step 5.5 F/G) and the reusable
**fraud/paperwork checklist** (Step 5.5 H) live there verbatim — including the
model-specific cold-start red flags (Civic/Accord VTC rattle, Camry 2AR-FE oil
consumption TSB T-SB-0094-11, CR-V 1.5T oil dilution, 8th-gen Accord V6 5AT) and the
title-transfer mechanics, filled from `jurisdiction` in the cars shared config (who
signs where, registration deadline and office, sales tax). Use those as the source
of truth until cutover.

## Outreach template (Step 7)

Use `outreach.opener_template` from the cars shared config. Shape of a good opener:

```
Hey [FIRST_NAME] - Very interested in your car! Could we meet up for a test drive? And do you have a clean title in hand? Thanks!
```
`[FIRST_NAME]` from the **message-modal recipient name** (not the sidebar); if not
a plausible human first name, open with "Hey -".

## Scheduled defaults

`scheduled_defaults` in the cars shared config (`makes_models`, `zip`, `radius_mi`,
`max_price`, `year_min`, `year_max`, `max_odometer`).

## Comp / Valuation mode (car specifics)

**IC-1 derive (don't ask):** `SEARCH_YEAR_MIN=COMP_YEAR−1`, `+1`;
`SEARCH_MILE_MIN=max(0, MILEAGE−20000)`, `MILE_MAX=MILEAGE+20000`; dealer-only,
national, include-sold (≤12mo), sort price-desc. Fields: year, make, model, trim,
**drivetrain** (FWD/RWD/AWD/4WD — worth $2K–$8K), mileage, packages.
**IC-2 sources:** Auto.dev (`--sort "price:desc" --limit 100`), AutoTrader,
CarGurus (cycle national + FL/CA/NY/TX + home state — prices inflate by regional
delivery fee), **Cars.com = price authority** (`cars.com/shopping/results/?makes[]={make}&models[]={model}&year_min=…&mileage_max=…&sort=list_price_desc&stock_type=used`;
listing `cars.com/vehicledetail/{UUID}/`), CarMax, AutoList
(`autolist.com/{make}-{model}-{year}`), sold (`site:cargurus.com sold …`). Drivetrain
post-filter (exclude confirmed mismatches; mark `⚠️ DRIVETRAIN UNVERIFIED` if
inferred). 0-miles guard.
**IC-3 expansion:** if <5 priced comps within ±20K → ±40K ("thin market") → ±60K;
always cite Δ Miles; for vehicles >15yr or >150K mi, run broad in parallel.
**IC-4 columns:** `# | Yr | Trim | DT | Miles | Δ Miles | Price | Status | Source |
Dealer | State | Notes | Link`; recommend **top-quartile** price as min ACV.
**IC test cases:** see `skills/car-hunt/references/insurance-comp.md` IC-TC-1..4 (modern/liquid;
old/thin with the 2003 Accord verified-comp table; expansion-trigger; mode
detection) — canonical regression set for comp mode.
