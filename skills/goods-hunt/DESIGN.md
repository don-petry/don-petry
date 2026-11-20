# Goods Hunt — Generalizing Car Hunt into a High-Value Used-Goods Engine

**Status:** Approved & in build — requirements + rationale. The owner has
**real, intended hunts in all four domains** (cars + tractors, furniture,
beekeeping, and other high-value goods). This doc is the **rationale of record**;
the *operational* spec lives in `SKILL.md` (the engine) and the domain packs.

> **Delivered so far (see `README.md` for the live phase tracker):**
> **Phase 0** — the qualification engine is domain-agnostic (pack-injected
> `QualSpec`, `skills/car-hunt/qualification/specs.py`); **Phase 1 (issue #27)** —
> the generic engine `SKILL.md` + the `cars` pack + `PARITY.md` map. **Phase 2
> (issue #28)** — the tractor hunt — is next, blocked on #27 merging.
> `/car-hunt` and its workflows remain untouched (cutover is a later eval-gated
> step). §15/§17 below describe the planned sequence; phases 0–1 are done.

**Review learnings folded into this revision (2026-06-13):**
1. **Buy-Used vs Buy-New is now a first-class routing decision** (new section
   below). Within a single domain, some item *types* are a used market (hunt
   them) and some are new-only (recommend new, price the best new comp, don't
   pretend to "hunt" them). A single hunt can span both.
2. **Don't force CPRU everywhere.** Metered goods use CPRU; unmetered/appreciating
   goods use `comp_value` or simple under-market. The metric is chosen *per item
   type*, not per domain (§3).
3. **Photo-based condition grading is a critical dependency, not a bonus** — and
   an unreliable one. It's promoted out of the "nice extras" list and given an
   accuracy caveat + conservative fallback (§13).
4. **Extract the generic qualification FSM first** as the low-risk kernel, before
   any framework (§15) — it's the one piece that's genuinely generic today.
5. **Automation is opt-in per hunt.** car-hunt's scheduled-cron + watchdog
   apparatus suits a recurring unattended need; some new hunts are interactive
   one-shots. Cadence is a pack input, not a mandate (§15).

**Confirmed build decisions (2026-06-13):**
- **Start with Phase 0** — extract the qualification FSM to config, then the car
  pack behind the parity eval (no behavior change) — *before* any new domain.
- **Cadence: interactive now, graduate later.** Every new hunt runs on demand
  first; a domain is promoted to a scheduled/watchdog'd watch only once it's
  proven and the owner wants it watched continuously. No cron is wired up until then.
- **Outreach: draft-only for all new domains.** The skill drafts seller messages;
  the owner sends them. Auto-send stays car-only unless/until a new domain earns
  it through its own eval.
- **Unmetered/appreciating metric: show both.** For no-meter or appreciating
  items, present the CPRU-with-band *and* the price-vs-comps value side by side;
  don't collapse to one number.

---

## 1. The thesis in one paragraph

`car-hunt` looks like a car skill, but ~80% of it is actually a **general
pipeline for finding, scoring, qualifying, and acquiring high-value used
goods**. The car-specific parts are knowledge and a handful of source/verify
recipes; the *engine* — value-per-remaining-life ranking, multi-source search,
distance gating, scam/condition disqualification, seller qualification via a
deterministic FSM, draft/auto-send outreach, scheduled automation with a
self-healing watchdog, and an eval gate — is domain-agnostic. If we factor the
car knowledge out into a **domain pack** and leave the engine standing, the same
machinery hunts tractors, furniture, beekeeping gear, instruments, appliances,
or any "expensive enough to research, fragmented enough to be inefficiently
priced" market. Cars become the *first* domain pack, not the skill.

---

## 2. What's generic vs. what's car-specific (component audit)

I walked the full `car-hunt/SKILL.md` (~1,900 lines), the qualification engine
(`ledger.py` / `determination.py` / `qualify.py`), the eval harness, and the
three workflows. Here is every major component sorted by how much of it is
reusable as-is.

| Component (current car-hunt) | Generic? | What stays, what becomes a pack input |
|---|---|---|
| **Mode detection** (standard vs. insurance-comp) | ✅ Engine | Routing logic is generic; "insurance comp" becomes generic **Valuation/Comp mode** (§7). |
| **Tool-prerequisite degradation table** (Auto.dev / Chrome MCP / Drive MCP) | ✅ Engine | The *pattern* (probe a tool, announce degraded coverage, fall back) is generic. *Which* tools matter per domain is a pack input. |
| **Core formula** `CPM = price / (expected − current)` | ✅ Engine | Generalizes to **CPRU** (§3). The arithmetic is identical; the *unit* is a pack input. |
| **Static vehicle reference table** (expected miles, caution years, trim ladder) | ⛏️ Pack | This is pure car knowledge → `domains/cars.md`. Every domain ships its own. |
| **Step 1 reliability research** → "reliability card" | ✅ Engine + ⛏️ sources | The *step* (live web research → a per-item quality card that feeds scoring) is generic. The source list (Consumer Reports, JD Power…) is a pack input → **Quality Card** (§4). |
| **Step 2 listing search** across FB / Craigslist / Auto.dev / AutoTrader / CarGurus | ✅ Engine + ⛏️ registry | The *orchestration* (parallel fan-out, paginate-to-exhaustion, dedupe, preview-filter-before-fetch) is generic. The **source registry** is a pack input (§5). FB Marketplace + Craigslist are *universal* sources reused by every domain. |
| **The hard-won FB Marketplace know-how** (numeric city IDs, `search?query=` vs dropped `query=`, `radiusKM`, React textarea setter, "Message again" dedup) | ✅ Engine | This is platform knowledge, not car knowledge. Every domain that searches FB inherits it for free — a major reason generalization is cheap. |
| **Distance estimation** (Nominatim geocode → Haversine → ×1.3 → radius cap) | ✅ Engine | Fully generic. Larger/heavier goods just want a bigger default radius and a freight option (§8). |
| **Disqualification filters** (title, salvage, non-running, scam, stale, mileage-implausible) | ✅ Engine + ⛏️ rules | Scam/staleness/distance are **universal**. Title/salvage/non-running are the *car instance* of a generic **deal-breaker list** that each pack supplies (§6). |
| **Step 3 CPM scoring + flags** | ✅ Engine | Generic once CPRU + pack flags are injected. |
| **Location-quality tier** (home-metro income tiers → CPM modifier) | ✅ Engine + ⛏️ semantics | The *mechanism* (location correlates with item quality & negotiation room → small ranking modifier) is generic. The **direction flips per domain** (§9) — for cars, affluent = gentler use; for tractors, rural/ag = real working iron. |
| **Seller Trust Score** (FB tenure / ratings / active-listings) | ✅ Engine | Pure platform signal. Generic across domains. |
| **Step 5 deep-dive** (NHTSA recalls/complaints/safety, KBB, Auto.dev TCO, VIN decode) | ✅ Engine + ⛏️ recipes | The *slot* ("run domain verification APIs on a shortlisted item") is generic; the APIs are a pack input → **Verification recipes** (§10). |
| **Seller qualification: Minimal-3 slots → FSM** (`vin`/`title`/`runs`) | 🎯 **Almost generic already** | `determination.py`'s FSM (`any_fail→disqualified`, `all_pass→qualified`, else `pending`) is *fully* domain-agnostic. Only `REQUIRED_SLOTS`/`SLOT_QUESTIONS` in `ledger.py` are car-specific. Making those a pack input is the single highest-leverage refactor (§11). |
| **Outreach** (templated FB message, dry-run, modal send, ask-once) | ✅ Engine + ⛏️ template | Mechanism generic; the message copy is a pack input. |
| **Messenger thread interpretation** (attributed turns, human-led hands-off, quote-or-it-didn't-happen) | ✅ Engine | The reasoning discipline is domain-independent. Only the slot-extraction rubric references the Minimal-N (a pack input). |
| **Export to Google Sheet** | ✅ Engine | Column set is mostly generic + a few pack-defined columns. |
| **Scheduling / workflows / watchdog / state branch / run-log issue / dedup** | ✅ Engine | 100% infrastructure. One parameterized workflow per active hunt. |
| **Eval harness** (labeled fixtures + deterministic scorer + accuracy bar) | ✅ Engine | The *harness* is generic; each domain grows its own fixtures (§12). |

**Takeaway:** the only genuinely car-shaped things are (a) a knowledge table,
(b) a list of sources, (c) a list of deal-breakers, (d) a few verification API
recipes, (e) the qualification questions, and (f) an outreach template. That is
*exactly* the shape of a domain pack.

---

## 3. The core abstraction: CPM → CPRU

`car-hunt`'s whole worldview is one formula:

```
CPM = price / (expected_lifetime_miles − current_miles)
```

"You are buying future utility, not past metal." That insight is not about cars.
Generalize the denominator to **remaining useful life in the domain's natural
unit**:

```
CPRU = price / (expected_life − consumed_life)        # Cost Per Remaining Unit
life_pct = consumed_life / expected_life              # 0..1, lower = more life left
```

Each domain pack declares its **life unit** and how to read `consumed_life`:

| Domain | Life unit | `expected_life` source | `consumed_life` source |
|---|---|---|---|
| Cars | miles | model lifetime table | odometer |
| Tractors / equipment | **engine hours** | model/series hour table | **hour-meter** (odometer's exact analog) |
| Furniture | **service-years remaining** | construction-grade table (solid hardwood + joinery vs. veneer vs. particleboard) | age + **photo-graded wear** |
| Beekeeping (durable tools) | **seasons / use-cycles** | tool-class table (extractor, smoker) | age + wear |
| Appliances / power tools | **rated cycles or hours** | class MTBF table | age × usage intensity |
| Instruments | **decades** (often *appreciating*) | tier table | condition, not consumption |

Two honest consequences the engine must handle:

1. **Metered vs. unmetered domains.** Cars and tractors have a meter, so CPRU is
   crisp. Furniture, beekeeping woodenware, and most goods have **no meter** —
   `consumed_life` must be *estimated* from age + construction grade + visible
   wear. This is fuzzier and the engine must show the uncertainty (a CPRU *band*,
   not a false-precision number). It also motivates a genuinely new capability:
   **photo-based condition grading** (§13), which improves cars too.

2. **Appreciating goods break the "consumption" model.** A solid-walnut
   mid-century credenza or a vintage instrument doesn't *consume* life — a good
   one can be worth more in 20 years. For these, the pack switches the metric
   from CPRU to **price-vs-comps** (buy below realizable resale), reusing the
   existing insurance-comp machinery (§7). The engine picks the metric the pack
   declares — **per item type, not per domain** (see routing below):
   `metric: cpru | comp_value | under_market`. **Default for no-meter /
   appreciating items: show both** the CPRU-with-band and the comp value side by
   side (per the 2026-06-13 decision), rather than forcing a single number.

---

## 3·B. Buy-Used vs Buy-New routing (added after review)

> Rationale below; the **operational rule lives in `SKILL.md` Step 1** (the
> engine executes it) — this section explains *why* it's first-class.

The sharpest lesson from the beekeeping case generalizes into a first-class
routing step that runs **before** scoring: not every item type in a domain is a
used market. Each pack classifies its item types into a **buy policy**, and the
engine routes accordingly instead of forcing every item through the hunt:

| Policy | Meaning | What the engine does |
|---|---|---|
| `used_market` | the normal case — a healthy secondhand market exists | full hunt: search sources → score (CPRU/comp) → qualify → outreach |
| `new_only` | used is a bad idea (disease, hygiene, safety, no resale, or used ≈ new price) | **do not hunt used.** Surface the **best new-retail price** as the comp, explain why used is off the table, and *optionally* watch for the rare acceptable exception (sealed/NIB, factory-refurb) |
| `used_if` | used is fine **only when a condition holds** | hunt, but auto-disqualify any listing that fails the condition (e.g. "sterilizable," "scorchable," "no comb") |

Why this matters structurally:

- **It is per item type, not per domain.** A single real hunt routinely spans
  policies. "Set up a beehive" = `new_only` comb/woodenware **+** `used_market`
  steel extractor **+** `used_if` (scorchable) boxes — one hunt, three routes.
- **It picks the metric.** `new_only` items don't get a CPRU at all; they get a
  new-price comp. `used_market` metered items get CPRU; `used_market` appreciating
  items get `comp_value`. So buy-policy and metric selection are the same decision.
- **It encodes "when not to play"** as a normal output, not an apology. The right
  answer for a hive box can be "buy new — here's the best price and why," and the
  engine should say exactly that with the reason, then move on.

Pack shape:

```yaml
item_types:
  - { name: drawn_comb,       policy: new_only,    reason: "AFB spores persist 40+ yrs" }
  - { name: woodenware_boxes, policy: used_if,     condition: scorchable_and_disease_free }
  - { name: steel_extractor,  policy: used_market, metric: cpru }
  - { name: smoker_hive_tool, policy: used_market, metric: cpru }
```

The first step of any hunt is therefore: **classify the requested item(s) →
route each to used_market / used_if / new_only → only the huntable ones enter the
search pipeline.** Everything downstream (sources, scoring, qualification) is
unchanged; we've just stopped pointing the hunt at things that shouldn't be bought
used.

---

## 4. Quality Card (generalized Reliability Card)

Step 1 today produces a per-model **reliability card** from live research
(Consumer Reports, JD Power, RepairPal, CarComplaints, forums). Rename to
**Quality Card** and let the pack supply the sources and the fields:

| Domain | Quality-card sources | "Best to buy" axis | "Avoid" axis | Common failure modes |
|---|---|---|---|---|
| Cars | Consumer Reports, JD Power, RepairPal, CarComplaints, r/whatcarshouldIbuy | best model years/gens | TSB-heavy years | CVT shudder, oil dilution… |
| Tractors | TractorData, TractorByNet / r/Tractors, Fastline guides, dealer bulletins | reliable series / pre-emissions-complexity eras | Tier-4 DEF/regen-prone years, known-weak transmissions | hydraulic leaks, regen faults, clutch wear |
| Furniture | maker guides, antiques references, r/Furniture, "is X good quality" | solid-wood makers / eras, dovetail joinery | particleboard/flat-pack eras, known-flimsy lines | veneer lift, sagging frames, MDF swelling |
| Beekeeping | Mann Lake/Dadant/Betterbee guides, state apiary extension, Beesource forums | inert metal tools used; **woodenware/comb: buy NEW** | **any comb/woodenware with unknown disease history** | **AFB spores (decades-viable)**, wax moth, rot |
| Generic | manufacturer + RepairClinic/iFixit + subreddit | durable brands/eras | discontinued-parts models | class-typical failures |

The card's job is unchanged: produce *best-to-buy*, *avoid*, *common problems*,
and a *buying tip*, then merge into the scoring flags. Only the inputs change.

---

## 5. Source registry (generalized Step 2)

Today's sources are hardcoded. Replace with a **registry** where each source
declares the domains it serves and its access method:

```
SOURCE                 DOMAINS              METHOD                       NOTES
Facebook Marketplace   ALL                  Chrome MCP (logged-in)       universal; inherits all FB know-how
Craigslist             ALL                  regional WebFetch            universal; paginate &s=120
eBay (+ sold comps)    furniture, tools,    WebFetch / API               'sold' filter = instant comp data
                       instruments, parts
Auto.dev / AutoTrader  cars                 CLI / WebSearch              (existing)
TractorHouse           tractors+attach.     WebSearch→listing WebFetch   the Auto.dev of ag equipment
Fastline / Machinery   tractors+attach.     WebSearch→WebFetch           dealer + auction inventory
  Pete
EquipmentTrader        tractors, mowers     WebSearch→WebFetch           —
Chairish / 1stDibs     furniture/antiques   WebFetch                     curated; higher floor, real comps
EstateSales.net /      furniture, tools,    WebFetch (listing + photos)  bundles/lots; photo-grade heavy
  AuctionZip /            beekeeping, all
  LiveAuctioneers
Local club / swap      beekeeping           (human pointer)              best used-gear channel; not scrapeable
```

The orchestration is unchanged from car-hunt: **universal sources (FB +
Craigslist + eBay) always run; the pack's domain-specific structured sources run
alongside; dedupe by URL; preview-filter before fetching pages; paginate to
exhaustion; report coverage gaps honestly.** Note the symmetry with cars: the
private-party axis (FB/Craigslist) + structured-inventory axis (Auto.dev) maps
cleanly onto every domain (FB/CL + TractorHouse, FB/CL + eBay-sold, …).

Each new structured source is its own anti-bot/scraping battle — exactly the
fight already won for FB and Craigslist. Budget for it; don't assume it's free.

---

## 6. Deal-breakers (generalized disqualification)

Split today's filters into **universal** (engine) and **pack** layers.

**Universal (every domain inherits):**
- Scam signals — off-platform payment, shipping-only, Zelle/CashApp-before-seeing, urgency/"moving must sell", broker language.
- Staleness — `date_posted` older than the pack's `stale_days` (cars: 21).
- Distance — `driving_est > RADIUS` (with the pack's freight escape hatch, §8).
- Price-implausibly-low without reason — flag for human review.

**Pack deal-breakers (the domain's "no title / salvage / won't run"):**

| Domain | Hard deal-breakers (auto-skip) |
|---|---|
| Cars | no/salvage/rebuilt title, won't run, frame damage, scam |
| Tractors | seized/blown engine, dead hydraulics, no PTO, **tampered/rolled-back hour-meter**, **emissions-delete on a Tier-4** (regulatory + resale poison), no clear ownership |
| Furniture | **bed bugs** (the cars' "salvage title" of furniture), smoke/heavy pet odor, structural break, water/mold damage, MDF water-swell, mislabeled reproduction sold as antique |
| Beekeeping | **comb/woodenware with unknown or positive AFB/disease history** (American Foulbrood spores survive 40+ yrs and many states *require burning*), pesticide-contaminated comb, rotted boxes |
| Generic | non-functional, missing critical/discontinued parts, recalled-unrepaired, counterfeit |

The beekeeping row is the important lesson: in some domains the *correct default
answer is "don't buy used."* For comb and woodenware the pack should bias hard
toward NEW and only green-light used for **inert, sterilizable items** (steel
extractors, smokers, hive tools). A good engine encodes "when not to play," not
just "how to rank."

---

## 7. Valuation / Comp mode (generalized Insurance-Comp mode)

The existing **Insurance Claim Comp mode** (find highest dealer comps to maximize
ACV payout) is already a second mode bolted onto the same search core. Generalize
it to **Comp mode**, useful far beyond car insurance:

- Maximize an insurance payout on a totaled tractor or a damaged/stolen antique.
- Justify a *listing* price when the user is the **seller** (flip the polarity:
  find the highest realistic comps to anchor your ask).
- Decide a **fair buy ceiling** for appreciating goods (furniture/instruments)
  where CPRU doesn't apply — buy below realizable resale.

Same engine: search comps → rank by price (desc for payout/sell, with
recently-sold comps weighted) → build an evidence package. The eBay/auction
"sold" data that furniture and instruments expose makes comps *easier* here than
for cars. This is why §3's `metric: comp_value` packs route through this mode.

---

## 8. Distance & logistics (small but real)

Generic geocode→Haversine→×1.3→radius-cap is reused unchanged, with two pack
inputs:

- `default_radius` — furniture/tractors tolerate farther travel than a $6k car.
- `freight_option` — large goods (tractors, armoires, extractors) can be
  *shipped*. When a high-CPRU item sits beyond the radius, instead of hard-drop,
  the engine should surface an estimated freight/uShip cost and fold it into an
  **landed CPRU** (`(price + freight) / remaining_life`) so a great deal 600 mi
  away isn't silently discarded. Cars rarely need this; tractors and big
  furniture do.

---

## 9. Location signal — generic mechanism, domain-flipped direction

The location-quality tier is one of car-hunt's subtler ideas: location
correlates (base-rate, not deterministically) with item quality and with
negotiation room, worth a small ranking modifier. The *mechanism* is generic;
the **mapping flips per domain**, so it's a pack input:

| Domain | Favorable location signal | Why |
|---|---|---|
| Cars | affluent suburbs | gentler use, dealer service, less price-sensitive sellers |
| Tractors | **rural / agricultural counties** | real working iron, deeper selection, fair pricing; suburban "hobby-farm" sellers often overprice tired units |
| Furniture/antiques | **older affluent neighborhoods + estate sales** | higher base-rate of solid-wood/quality pieces and motivated estate sellers |
| Beekeeping | **active beekeeping regions / club proximity** | gear from real beekeepers, and local pickup avoids shipping live-disease risk |

Same honest-framing rule carries over: name the economic/behavioral mechanism,
never the demographic.

---

## 10. Verification recipes (generalized deep-dive)

Deep-dive becomes "run the pack's verification recipes on a shortlisted item."
Generic interface: `verify(item) → { specs_match, known_issues, market_value,
authenticity, ownership/title }`.

| Domain | Verification recipes |
|---|---|
| Cars | NHTSA recalls/complaints/safety, VIN decode, Auto.dev TCO/recalls, Carfax pointers (existing) |
| Tractors | **serial-number decode** (year/plant — the VIN analog), TractorData spec match, **parts-availability check** (discontinued parts = future paperweight), hour-meter plausibility vs. wear, manufacturer service bulletins |
| Furniture | **maker's-mark / hallmark lookup**, **eBay/auction sold-comps** (authenticity + value), reproduction-vs-original tells, materials check from photos |
| Beekeeping | **state apiary inspection records**, equipment-standard compatibility (8 vs 10-frame Langstroth), frame/foundation type |
| Generic | model/recall lookup, iFixit repairability, sold-comps, serial/authenticity |

The "VIN decode catches a wrong sticker / salvage rebuild" pattern generalizes
directly to "serial decode catches a misrepresented tractor year" and "hallmark
lookup catches a reproduction."

---

## 11. The qualification engine is *already* domain-agnostic

This is the cleanest win and the proof the abstraction is real. Look at what's
generic vs. hardcoded today:

- `determination.py` — the FSM (`any_fail → disqualified`, `all_pass →
  qualified`, else `pending`), `followup_eligible` send-gate, `draft_followup`,
  the monotonic/idempotent/self-correcting design — has **zero** car knowledge.
- `qualify.py` — slot-merge, ledger persistence, draft surfacing, send-cap — has
  **zero** car knowledge.
- `ledger.py` — **only** these are car-shaped:
  ```python
  REQUIRED_SLOTS = ("vin", "title", "runs")
  SLOT_QUESTIONS = { "vin": "...VIN...", "title": "...title from {state}...", "runs": "...run and drive..." }
  ```

**Refactor:** lift `REQUIRED_SLOTS` / `SLOT_QUESTIONS` out of module constants
and inject them from the active domain pack (e.g. `Ledger.for_domain(pack)` or a
small `QualSpec` passed into `assess`). Everything downstream — FSM, send-gate,
eval scorer's slot checks — keeps working untouched. Then each pack declares its
**Minimal-N**:

| Domain | Minimal-N qualification slots (fail = disqualify) |
|---|---|
| Cars | `vin`, `title`, `runs` (existing) |
| Tractors | `hours` (meter reading + believable), `title/ownership`, `runs_hydraulics_pto`, *(opt)* `serial` |
| Furniture | `bedbugs_smoke_pets` (the gating one), `material_construction`, `structural_condition`, *(opt)* `dimensions` |
| Beekeeping | `disease_history` (AFB/foulbrood — the gating one), `comb_or_woodenware_age`, `equipment_standard` |
| Generic | `functional`, `complete/parts`, `ownership` |

The FSM doesn't care that N changed from 3 — `all_pass`/`any_fail` already
iterate `REQUIRED_SLOTS`. This is a ~30-line change that unlocks every domain's
qualification for free, with the same auto-send safety controls (ask-once,
cap-3, kill-switch, eligible-only) intact.

---

## 12. Eval, per domain

The eval harness (labeled thread fixtures + deterministic scorer + 90% accuracy
bar + hard safety invariants) is generic. Each pack ships its own
`eval/threads.json` fixtures in *its* domain's language, but the scorer, the
safety invariants (`must_not_draft` into human-led, `must_not_disqualify`,
never-miss-an-objective-disqualifier, never-hallucinate-a-slot-verdict), and the
"clear the bar before auto-send" gate are inherited. New domains start
**draft-only** and earn auto-send by passing their own eval — the same
discipline that got the car Messenger flow to 14/15 before it was trusted to
send.

---

## 13. New capabilities that generalization *unlocks*

Generalizing isn't only consolidation; it forces/affords genuinely new features:

1. **Photo-based condition grading (model vision) — critical dependency, not a
   bonus.** Unmetered `used_market` domains have no odometer, so `consumed_life`
   *must* come from age + construction grade + wear graded off listing photos
   (veneer lift, frame sag, rust, regen soot, comb darkness, cosmetic vs.
   structural). The whole no-meter CPRU path leans on this — so treat its
   limits honestly: sellers post flattering angles, crop damage, and reuse stock
   photos, and a grade from 4 photos is not an inspection. **Mitigations the
   engine must apply:** grade *conservatively* (assume worse when unsure), widen
   the CPRU band rather than emit false precision, **never auto-disqualify on
   photos alone** (flag for the human / ask the seller for specific shots — joints,
   underside, hour-meter, door-jamb), and fall back to `under_market`/`comp_value`
   when a grade can't be made. Done this way it also sharpens *cars*
   (tire/rust/interior). Done naively it silently corrupts every unmetered rank.
2. **Attachment/compatibility graph (tractors).** A dimension cars don't have:
   match attachments to a base unit by 3-point-hitch category, PTO hp, loader
   mount, hydraulic remotes. The hunt can target "a tractor *and* a compatible
   box blade + bush hog" and score the **bundle**.
3. **Bundle / lot valuation.** Estate sales and equipment packages sell as lots.
   The engine can value a mixed lot and compute per-item CPRU within it.
4. **One automation, many hunts.** The workflow/watchdog/state-branch machinery
   already supports a parameterized hunt; generalizing lets a single user run a
   *car* hunt, a *tractor* hunt, and a *furniture* watch concurrently, each with
   its own state branch and run-log issue.
5. **Cross-listing arbitrage surfacing.** With eBay-sold comps wired in for
   furniture/tools, the engine can flag "local FB item priced well under
   national sold-comps" — an explicit flip opportunity, not just a buy.

---

## 14. Proposed architecture

```
skills/goods-hunt/
  SKILL.md                 # the GENERIC engine: detect domain → load pack →
                           #   quality card → search registry → CPRU/comp score →
                           #   location tier → deal-breakers → rank → verify →
                           #   outreach → qualify(FSM) → export. Mode: hunt | comp.
  domains/
    cars.md                # the existing car knowledge, extracted verbatim (parity target)
    tractors.md            # sketch in this folder
    furniture.md           # sketch in this folder
    beekeeping.md          # sketch in this folder
    generic.md             # fallback pack for unlisted high-value goods
  qualification/           # existing engine, slots injected from the active pack
    ledger.py              #   REQUIRED_SLOTS/SLOT_QUESTIONS ← pack (the one refactor)
    determination.py       #   unchanged (already generic)
    qualify.py             #   unchanged
  eval/
    <domain>/threads.json  # per-domain fixtures; shared scorer + bar + invariants
```

**A domain pack declares** (this is the whole interface):

```yaml
domain: tractors
item_types:                       # buy-policy routing runs FIRST (§3·B)
  - { name: tractor_base,  policy: used_market, metric: cpru }
  - { name: attachments,   policy: used_market, metric: cpru }
  # a new_only example lives in the beekeeping pack
life_unit: engine_hours
expected_life: { <model/series>: <hours>, ... }
consumed_life: hour_meter         # how to read it; null → estimate from age+photos
quality_card_sources: [ ... ]
sources: [ TractorHouse, Fastline, EquipmentTrader, FacebookMarketplace, Craigslist ]
deal_breakers: [ seized, dead_hydraulics, no_pto, rolled_hour_meter, emissions_delete, no_ownership ]
location_signal: rural_ag_favorable
verification: [ serial_decode, tractordata_spec_match, parts_availability ]
qualification_slots:              # → injected into the FSM
  hours:    "What does the hour-meter read, and is it the original meter?"
  title:    "Do you have clear ownership/title in hand?"
  runs:     "Does it start, and do the hydraulics and PTO work without issues?"
default_radius: 250
freight_option: true
cadence: scheduled | interactive  # automation is opt-in per hunt (§15)
outreach_mode: draft | autosend   # new domains start `draft` until their eval passes
outreach_template: "Hi {name} — interested in your {item}. Could we arrange a time to see it run? ..."
stale_days: 30
```

Everything else — orchestration, FB/Craigslist know-how, distance, scoring,
FSM, send-gate, workflows, watchdog, eval scorer — is the shared engine.

---

## 15. Migration path (low-risk, parity-gated)

**Phase 0a — Extract the qualification FSM as config (the kernel, lowest risk).**
Before any framework: lift `REQUIRED_SLOTS`/`SLOT_QUESTIONS` out of `ledger.py`
constants and inject them from the active pack. This is the one piece that is
*genuinely* generic today (the FSM, send-gate, and eval scorer don't change), and
it's independently useful even if we never build the rest. Gate: the existing car
qualification unit tests + eval still pass with `cars` reproducing `vin/title/runs`.

**Phase 0b — Extract the car pack, prove parity (no behavior change).** Move car
knowledge into `domains/cars.md`; stand up `goods-hunt/SKILL.md` as the generic
engine running the car pack. Keep `/car-hunt` as an alias that loads `cars`.
Success = the existing car eval still passes and a scheduled run produces
identical output. *Live behavior is unchanged — a pure refactor, eval as the
regression gate.* Buy-policy routing (§3·B) lands here as a no-op for cars (one
`used_market` item type) so the seam exists before tractors need it.

**Phase 1 — Tractors (closest analog, validates the abstraction).** Hour-meter ≈
odometer, TractorHouse/Fastline ≈ Auto.dev, serial decode ≈ VIN, hydraulics/PTO
≈ runs-and-drives. Minimal new invention; if the abstraction is right, tractors
mostly *fall out*. Ship draft-only; earn auto-send via a tractor eval. Adds the
attachment/bundle dimension and the first multi-item-type hunt. **Cadence is set
per the real hunt** (scheduled if it's an ongoing watch; interactive one-shot if
it's a single purchase) — the workflow apparatus is opt-in, not assumed.

**Phase 2 — Furniture (validates the no-meter / photo-grading path).** Forces
CPRU-from-estimate, photo condition grading, eBay-sold comps, and the
`comp_value` metric for appreciating pieces. The bed-bug deal-breaker is the
test of pack-specific gating.

**Phase 3 — Beekeeping (validates "sometimes don't buy used").** The pack that
proves the engine can *recommend new* and gate hard on an invisible disqualifier
(AFB). Smallest market, biggest lesson about encoding domain wisdom.

**Phase 4 — Generic fallback pack** for everything else (appliances, tools,
instruments), tuned by the patterns the first three taught us.

Each phase is independently shippable and individually gated by its own eval
before it's trusted to message anyone.

---

## 16. Honest risks & open questions

- **Unmetered CPRU is soft.** For furniture/beekeeping the denominator is an
  estimate; show a band and the assumptions, never false precision. If users
  don't trust soft CPRU, lean on `comp_value` instead.
- **Each structured source is a scraping project.** TractorHouse, eBay, auction
  sites each replay the FB/Craigslist anti-bot fight. Don't under-budget.
- **Authenticity has no NHTSA.** Antique/instrument provenance is genuinely hard;
  the engine can surface comps and hallmark lookups but shouldn't pretend to
  authenticate. Keep a human in the loop.
- **Disease/regulatory gating (beekeeping, emissions) needs care** — these are
  safety/legal lines, not preferences; the pack must treat them as hard
  deal-breakers, not modifiers.
- **Sequencing discipline (not scope creep).** All four hunts are real and wanted,
  but build them *one at a time, end-to-end, each behind its own eval* — resist
  building four half-packs at once. Order by analog-distance from cars
  (tractors → furniture → beekeeping → generic) so each domain only introduces
  one new hard problem.
- **Photo-grading accuracy is unproven** — the no-meter ranks ride on it; keep it
  conservative, banded, and never auto-disqualifying until measured (§13).
- **Naming/back-compat.** `/car-hunt` must keep working verbatim (live workflows,
  state branch, run-log issue). The alias + parity eval protect this.

---

## 17. Recommendation

The abstraction is real and unusually clean — most of `car-hunt` is already a
general goods engine wearing a car costume — and with real hunts confirmed in all
four domains, it's worth building. Sequence: **Phase 0a** (extract the
qualification FSM to config — useful on its own, lowest risk) → **Phase 0b**
(extract the car pack behind the parity eval, add the buy-policy seam as a
cars no-op) → **Phase 1 tractors** end-to-end as the first real new hunt. Each
subsequent domain (furniture, beekeeping, generic) lands one new hard problem at
a time, draft-only until its own eval clears the bar.

The per-hunt specifics needed to finalize each pack are gathered in §18.

See the illustrative packs alongside this doc: `domains/tractors.md`,
`domains/furniture.md`, `domains/beekeeping.md`, `domains/generic.md`.

---

## 18. Inputs needed per hunt (to finalize each pack)

Each real hunt needs these from the owner before its pack can be built and
tested. (Captured as clarifying questions in the PR thread.)

- **The actual target(s)** per domain — specific item(s), spec floor/ceiling,
  and budget. This sets `expected_life`, the value metric, and the deal-breakers.
- **Buy-policy split** — which item types in that hunt are `used_market` vs
  `new_only` vs `used_if`, and the condition for `used_if`.
- **Geography & logistics** — home ZIP, search radius, and whether freight/shipping
  is acceptable (sets `default_radius`, `freight_option`, landed-CPRU).
- **Cadence** — ongoing scheduled watch vs. one-shot interactive hunt (decides
  whether the workflow/watchdog apparatus is wired up for that pack).
- **Outreach** — draft-only vs. auto-send, and the message copy/contact channel
  (all new domains start draft-only until their eval passes).
- **Metric preference** — for unmetered/appreciating items, CPRU-with-band vs.
  comp_value vs. simple under-market.
