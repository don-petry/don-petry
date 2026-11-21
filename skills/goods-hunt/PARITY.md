# Parity map — `car-hunt/SKILL.md` → `goods-hunt` engine + `cars` pack

Phase 1 (issue #27) extracted the live `skills/car-hunt/SKILL.md` (~1,935 lines)
into the generic engine (`SKILL.md`) + the cars pack (`domains/cars.md`). This
table proves every live section has a home — nothing silently dropped. **E** =
generic engine, **C** = cars pack, **C(ref)** = stays canonical in the live
`car-hunt` skill and is referenced (not duplicated) to avoid drift until cutover.

> **2026-11-20:** car-hunt was split for open-source publishing — its long sections
> now live in `skills/car-hunt/references/*.md` (sources, deep-dive, test-drive,
> outreach, insurance-comp, scoring, reliability) and household values in its
> `config/household.yaml`. "Live `car-hunt/SKILL.md`" below means that skill as a
> whole; the section names are unchanged.

| Live `car-hunt/SKILL.md` section | New home | Notes |
|---|---|---|
| Frontmatter / description / arg-hint | E + C | engine tool-list + arg convention; car description/arg in cars pack |
| Mode Detection (standard vs insurance-comp) | E | generic two-mode routing; car comp-triggers in cars pack |
| Tool Prerequisites table | E + C | generic probe/degrade pattern (Step 0.5); Auto.dev/NHTSA rows in cars pack |
| Auto.dev CLI login / setup | C | automotive API |
| Browser automation / FB Marketplace prereq | E | platform mechanics |
| Spreadsheet export prereq | E | platform mechanics |
| Core Formula (CPM, Life_Pct) | E + C | engine = CPRU; cars pack = the CPM instance + flag thresholds |
| Static Vehicle Reference (expected miles / caution years / trim) | C | verbatim tables in cars pack |
| Search Parameters (parse the request → ask → store) | E + C | flow generic; car defaults in pack |
| Step 1 Reliability Research + Reliability Card | E + C | engine = Quality Card (Step 2); car sources/fields in pack |
| How research feeds scoring (merged caution list) | E | generic; "caution years" is the car instance |
| Step 2 Search (intro / inspect-before-batch) | E | generic orchestration |
| AutoTrader | E + C | WebSearch-to-listing + 503 handling generic; site/queries in pack |
| CarGurus (deprecated routine; live in comp) | E + C | deprecation-handling generic; site + note in pack |
| Facebook Marketplace (A/B/C, all operational facts, composer, profile extraction) | E + C | mechanics generic (Step 3); numeric city ID in household config |
| Craigslist (pagination, link rule) | E + C | mechanics generic; `cta` category + regions in pack |
| Auto.dev listings + 0-miles guard | C | automotive API + field paths |
| WebSearch fallback | E + C | pattern generic; queries in pack |
| Data to Extract Per Listing | E + C | generic skeleton (Step 3); car fields (doors/trans/miles) in pack |
| Distance Estimation (Nominatim/Haversine/cap/staleness) | E | fully generic (Step 3.5) |
| Hard disqualification filters | E + C | scam/staleness/distance generic (Step 3.6); car vocabulary in pack |
| Description scraping mandatory | E | generic platform lesson |
| Parallel Search Strategy (50+, exhaustive, batch, preview-filter) | E | generic |
| Step 3 CPM + flag rules + trim score | E + C | engine = CPRU scoring; car thresholds/flags in pack |
| Location Quality Tier (concept + mechanism) | E | generic; favorable direction is pack-defined |
| Home-metro tier table + CPM modifiers | C + config | thresholds/modifiers in cars pack; the household's table in car-hunt `config/household.yaml` |
| Tier-aware scoring rules / extending to metros / honest framing | E + C | mechanism generic; car examples in pack |
| Seller Trust Score (table/defaults/adj/display/flags/regexes) | E + C | mechanism + FB regexes generic; thresholds/±/display in pack |
| Step 4 Rank & Present | E + C | sort/header/summary generic; car columns + "best Honda/Toyota" in pack |
| Step 5 Deep-Dive A–F (NHTSA/KBB/TCO/VIN/history) | E + C | "run verification recipes" generic; all car endpoints in pack |
| Step 5.25 Head-to-Head | E + C | info-asymmetry + opinionated-pick generic; car rows in pack |
| Step 5.5 Pre-Test-Drive A–E (VIN/recall/title/cross-check/OOP) | E + C | gate concept generic; car endpoints in pack |
| Step 5.5 F/G Test-drive checklist + PDF | E + **C(ref)** | generator pattern generic; full template canonical in live `car-hunt/SKILL.md` |
| Step 5.5 H Fraud/paperwork checklist | E + **C(ref)** | concept generic; 11-section content canonical in live `car-hunt/SKILL.md` |
| Step 6 Export to Google Sheet (all subsections) | E + C | mechanics fully generic; car columns in pack |
| Scheduling | E + C | discipline generic; default params in pack |
| Step 7 Outreach (offer/execute/rules) | E + C | FB mechanics generic; message template in pack |
| Step 8 Messenger interpretation (all) | E + C | engine fully generic; opener-fingerprint in pack |
| Step 8 Seller Qualification (Minimal-3 + FSM) | E + C(code) | architecture generic + already-generalized code (`qualification/specs.py` CARS); rubric in pack |
| Insurance Comp Mode IC-1..IC-6 | E + C | comp-mode process generic; car fields/sources/±bands/columns in pack |
| IC Test Cases IC-TC-1..4 | **C(ref)** | canonical regression set in live `car-hunt/SKILL.md` |
| Output Format Rules | E + C | generic rules in engine; CPM-precision conventions in pack |
| Important Rules | E + C | generic rules in engine; car-specific rules in pack |

## Parity gates

- **Qualification (the consequential, testable part):** unchanged code, already
  domain-agnostic since Phase 0. `PYTHONPATH=. pytest` in
  `skills/car-hunt/qualification/` (31 tests) + `skills/car-hunt/eval/` remain the
  gates. Cars still resolve `vin/title/runs` via the `CARS` QualSpec.
- **The rest is doc-driven**, so parity = structural fidelity (this map) +
  spot-running `goods-hunt --domain cars` against a known search and diffing the
  ranked output vs a `car-hunt` run before any cutover.

## What this pass deliberately did NOT do

- It did **not** rewire `/car-hunt` or its workflows. They remain the live entry
  point. Cutover (making `car-hunt` delegate to the engine + cars pack) is a
  separate, eval-gated step.
- It did **not** duplicate the two giant checklist templates or the IC test cases —
  those stay canonical in the live skill (marked `C(ref)`) and move at cutover.
