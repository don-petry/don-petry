# Domain Pack — Furniture & Antiques (illustrative sketch)

> Sketch accompanying `../DESIGN.md`. Furniture is the domain that **validates
> the no-meter path**: there is no odometer, so remaining life is *estimated*
> from construction grade + age + photo-graded wear. High-end/antique pieces
> often *appreciate*, so this pack supports both metrics.

## Pack manifest

```yaml
domain: furniture
life_unit: service_years
consumed_life: estimate            # no meter → age + construction grade + PHOTO wear (critical dep)
item_types:                        # buy-policy routing (§3·B) runs first
  - { name: case_goods,        policy: used_market, metric: cpru }        # dressers, tables, shelving
  - { name: antique_heirloom,  policy: used_market, metric: comp_value }  # appreciating → buy below resale
  - { name: upholstered,       policy: used_if, condition: no_bedbugs_smoke_pets, metric: cpru }
  - { name: mattresses,        policy: new_only, reason: "hygiene / bed-bug risk / no resale" }
location_signal: estate_sales_and_older_affluent_favorable
default_radius: 150
freight_option: true               # armoires/sofas; fold freight into landed cost
cadence: interactive
outreach_mode: draft
stale_days: 30
```

## Expected life (service-years) by construction grade — illustrative

| Grade | Tells (from photos/description) | Expected service-years |
|---|---|---|
| Heirloom | solid hardwood, **dovetail** joinery, dust panels, named maker | 50–100+ (often appreciates) |
| Good | solid wood or quality veneer over ply, mortise/dowel joints | 25–40 |
| Budget | particleboard/MDF, **stapled** joints, plastic glides, flat-pack | 5–12 |

CPRU = `price / (expected_years − age_years)`, shown as a **band** (estimate).
For Heirloom/appreciating pieces, switch to **`comp_value`** (§7 of DESIGN) —
buy below realizable resale, using eBay/auction **sold** comps.

## Quality Card sources

Maker/brand guides, antiques references, r/Furniture "is X good quality",
"<brand> solid wood or veneer", auction-house maker pages. Card axes: solid-wood
makers & eras to favor; particleboard/flat-pack lines to avoid; failure modes
(veneer lift, frame sag, MDF water-swell, loose joints).

## Source registry

`Facebook Marketplace` + `Craigslist` (universal private-party) **+** `eBay`
(with **sold** filter = instant comps + authenticity) **+** `Chairish`/`1stDibs`
(curated, real comps) **+** `EstateSales.net`/`AuctionZip`/`LiveAuctioneers`
(lots, photo-heavy, motivated sellers).

## Deal-breakers (auto-skip)

**Bed bugs** (the "salvage title" of furniture — once mentioned/suspected,
skip) · heavy smoke or pet odor · structural break/broken frame · water damage /
**mold** · MDF water-swelling · **reproduction sold as antique** (misrepresented
provenance) · "free, you haul" with infestation risk language.

## Verification recipes (deep-dive)

`makers_mark_lookup` (hallmark/label → maker & era) · **`ebay_auction_sold_comps`**
(value + authenticity in one) · reproduction-vs-original tells · materials check
from photos (end-grain, joinery, drawer construction).

## Minimal-N qualification slots (→ FSM)

```yaml
qualification_slots:
  pests_odor:   "Is the piece from a smoke-free, pet-free home with no history of bed bugs?"   # the gating one
  construction: "Is it solid wood, or veneer/particleboard — and any maker's mark?"
  condition:    "Any structural damage, water/mold, or loose joints?"
  dimensions:   "Could you confirm the W×D×H?"                                                  # optional
```

`fail` on `pests_odor` (bed bugs / heavy odor) or `condition` (broken/mold) →
disqualified — the bed-bug gate is to furniture what salvage-title is to cars.

## Net-new feature this domain forces

**Photo-based condition grading (model vision)** — grade veneer lift, frame
sag, finish wear, joinery from listing photos to set `consumed_life`. Plus
**lot/bundle valuation** for estate sales (value a mixed lot, per-item CPRU) and
**arbitrage flagging** (local FB price ≪ eBay sold-comps → flip signal).

## Outreach template

> "Hi {name} — love the {item}. Is it from a smoke-free/pet-free home with no bed
> bug history, and is it solid wood? Happy to arrange pickup. Thanks!"
