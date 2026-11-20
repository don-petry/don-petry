# Domain Pack — Beekeeping Supplies (illustrative sketch)

> Sketch accompanying `../DESIGN.md`. Beekeeping is the domain that proves the
> engine can encode **"sometimes don't buy used."** Used comb and woodenware
> carry an *invisible, catastrophic* disqualifier — **American Foulbrood (AFB)**
> spores survive 40+ years and many states legally **require burning** infected
> equipment. So this pack biases hard toward NEW for comb/woodenware and only
> green-lights used for **inert, sterilizable metal tools**.

## Pack manifest

```yaml
domain: beekeeping
life_unit: seasons
consumed_life: estimate            # age + wear; comb age is the key risk axis
item_types:                        # buy-policy routing (§3·B) — the canonical example
  # used_market (green): inert / sterilizable
  - { name: steel_extractor, policy: used_market, metric: cpru }
  - { name: smoker,          policy: used_market, metric: cpru }
  - { name: hive_tool,       policy: used_market, metric: cpru }
  - { name: uncapping_tank,  policy: used_market, metric: cpru }
  - { name: refractometer,   policy: used_market, metric: cpru }
  - { name: suit_veil,       policy: used_market, metric: cpru }
  # used_if (yellow): only when the condition holds
  - { name: woodenware_boxes, policy: used_if, condition: scorchable_and_disease_free }
  # new_only (red): AFB risk → recommend NEW, price the best new comp, don't hunt used
  - { name: drawn_comb,       policy: new_only, reason: "AFB spores persist 40+ yrs; some states require burning" }
  - { name: frames_with_comb, policy: new_only, reason: "same — comb is the disease vector" }
location_signal: active_beekeeping_region_and_club_proximity   # local pickup avoids shipping live-disease risk
default_radius: 100
freight_option: true               # extractors ship; comb/woodenware shouldn't travel far
cadence: interactive
outreach_mode: draft
stale_days: 30
```

## Expected life (seasons) — illustrative, **inert tools only**

| Item | Expected seasons | Notes |
|---|---|---|
| Stainless extractor | 20–30 | the classic smart used buy; sterilizable |
| Smoker (stainless) | 10–20 | inert; clean and go |
| Hive tool / frame grip | 15+ | effectively indestructible |
| Bee suit / veil | 5–10 | wash; check zippers/netting |

CPRU applies to these. For comb/woodenware the pack does **not** compute a
"buy" CPRU — it returns a **recommend-NEW** verdict with the disease rationale.

## Quality Card sources

Mann Lake / Dadant / Betterbee guides, **state apiary/extension** disease pages,
Beesource forums, local club guidance. Card axes: which items are safe used
(inert metal) vs. NEW-only (comb/woodenware); failure modes (AFB/EFB,
wax moth, rot, sun-rotted suits).

## Source registry

`Facebook Marketplace` + `Craigslist` (universal) **+** new-gear retailers
(Mann Lake/Dadant/Betterbee — price floor & comp) **+** **local club swap /
bee-club channels** (the best *used inert-tool* channel; a human pointer, not
scrapeable) **+** estate/farm auctions for extractors.

## Deal-breakers (auto-skip)

**Any comb/woodenware with unknown or positive AFB/foulbrood history** (hard
stop — recommend NEW) · pesticide-contaminated comb · rotted/moldy boxes ·
"whole apiary, bees included, seller vague on disease/inspection" · shipped live
comb across a state plant line.

## Verification recipes (deep-dive)

`state_apiary_inspection_records` (was the yard inspected/clean?) ·
`equipment_standard_match` (8-frame vs **10-frame** Langstroth; deep vs medium —
mismatched gear is unusable) · frame/foundation type · for tools: stainless-vs-
plated, structural integrity.

## Minimal-N qualification slots (→ FSM)

```yaml
qualification_slots:
  disease_history: "Has this comb/equipment ever had foulbrood (AFB/EFB), and was the yard state-inspected?"   # the gating one
  item_type:       "Is this drawn comb/woodenware, or inert tools (extractor, smoker, hive tool)?"
  standard:        "What frame size/standard — 8 or 10-frame Langstroth, deep or medium?"
```

`fail` / unclear on `disease_history` for any comb/woodenware → disqualified with
"recommend NEW — AFB spores persist for decades." Inert tools clear on
`disease_history = n/a (sterilizable)`.

## What this domain teaches the engine

That a good acquisition engine encodes **when not to play.** The right output is
often "buy this NEW," and the skill should say so with the reason — not
manufacture a CPRU for a hive box that could carry a 40-year disease.

## Outreach template

> "Hi {name} — interested in your {item}. Quick question first: has the
> equipment ever had foulbrood, and was the yard inspected? For metal tools I'm
> easy; for comb/boxes I have to be careful on disease. Thanks!"
