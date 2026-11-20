# Domain Pack — Generic High-Value Goods (fallback sketch)

> Sketch accompanying `../DESIGN.md`. The fallback pack for high-value used goods
> not covered by a dedicated pack — appliances, power tools, electronics,
> instruments, exercise equipment, etc. Tuned from whatever the first three
> dedicated packs teach us. When the user hunts something with no specific pack,
> the engine loads this and asks 2–3 calibration questions up front.

## Pack manifest

```yaml
domain: generic
life_unit: years | cycles | hours  # ask the user / infer from item class
consumed_life: estimate            # age × usage intensity; photo-grade where possible
item_types:                        # set by the calibration questions below (§3·B)
  # each requested item is classified used_market | used_if | new_only at hunt start;
  # metric chosen per type: cpru (lifetime known) | comp_value (collectible) | under_market
  - { name: "<asked at runtime>", policy: "<used_market|used_if|new_only>", metric: "<cpru|comp_value|under_market>" }
location_signal: affluent_favorable   # default; flip if the item class suggests otherwise
default_radius: 100
freight_option: true
cadence: interactive
outreach_mode: draft
stale_days: 30
```

## Calibration (ask once on first run of an unlisted item)

> "A couple of quick calibration questions so I can rank these well:
> 1. Roughly how long does a well-kept one last (years / hours / cycles)?
> 2. Is this a *consumable* good (wears out) or a *collectible* (can appreciate)?
> 3. Any must-avoid red flags you already know about?"

Answers set `life_unit`, choose `metric` (cpru vs comp_value), and seed the
deal-breaker list. The engine saves the answers inline so later runs reuse them
(same pattern car-hunt uses to persist a new metro's location tiers).

## Expected life — by item class (built on first run)

Researched live via the Quality Card step (manufacturer + RepairClinic/iFixit +
the item's subreddit) the first time a new class is hunted, then cached:

| Class (examples) | Typical life unit | Source of consumed_life |
|---|---|---|
| Major appliance | 10–15 years | age (+ photo wear) |
| Power tool | rated hours / DIY-years | age × usage |
| Treadmill/rower | years (motor hours) | age + console hours if shown |
| Instrument | decades (often appreciates) | condition, not consumption → `comp_value` |

## Quality Card sources

Manufacturer reliability + **iFixit repairability score** + **RepairClinic**
common-failure parts + the item's subreddit ("best/worst <brand>"). Axes:
durable brands/eras to favor; **discontinued-parts** models to avoid (the
generic "future paperweight" risk); class-typical failure modes.

## Source registry

`Facebook Marketplace` + `Craigslist` (universal) **+** `eBay` (sold comps for
value/authenticity) **+** `OfferUp` **+** estate/liquidation auctions for the
relevant class.

## Deal-breakers (auto-skip)

non-functional / "for parts" (unless user is parts-hunting) · **missing critical
or discontinued parts** · recalled-unrepaired (CPSC lookup) · counterfeit /
misrepresented brand · scam signals (universal) · stale / out-of-radius
(universal).

## Verification recipes (deep-dive)

`recall_lookup` (CPSC / manufacturer) · `ifixit_repairability` · `sold_comps`
(eBay/auction) · `serial_authenticity` where the brand exposes it.

## Minimal-N qualification slots (→ FSM)

```yaml
qualification_slots:
  functional: "Does it power on and work fully, with no error codes or known faults?"
  complete:   "Is it complete — all parts/accessories present and nothing discontinued/missing?"
  ownership:  "Is it yours to sell, with a receipt or proof if available?"
```

`fail` on `functional` or `complete` → disqualified.

## Outreach template

> "Hi {name} — interested in your {item}. Does it fully work with no faults, and
> is everything included? Happy to arrange a time. Thanks!"
