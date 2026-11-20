# Domain Pack — Tractors & Attachments (illustrative sketch)

> 🛑 **DISABLED (owner request — 2026-06-19).** The tractor hunt is turned off.
> The engine must **not** run this pack: refuse tractor invocations (see
> `../SKILL.md` Step 0 routing guard) and do not schedule it. No tractor outreach,
> drafting, or thread-reading while disabled. The config below is retained for
> reference — re-enable by flipping `enabled: true` in the manifest and deleting
> this banner.

> Sketch accompanying `../DESIGN.md`. Numbers are realistic but illustrative,
> not researched-to-publish. Tractors are the **closest analog to cars** and the
> recommended first new domain: hour-meter ≈ odometer, TractorHouse ≈ Auto.dev,
> serial decode ≈ VIN, hydraulics/PTO ≈ runs-and-drives.

## Hunt config (per household)

The user's hunt parameters live in `config/household.yaml` under `packs.tractors.hunt`
(makes, class, max hours, year, max price, attachments, ZIP, radius, cadence,
outreach) — see `config/household.example.yaml` for the shape. Ask for any value that
is missing before the first run, including any **must-have attachments** to fold into
bundle CPRU.

## Pack manifest

```yaml
domain: tractors
enabled: false                     # 🛑 DISABLED 2026-06-19 (owner) — engine must refuse this pack
life_unit: engine_hours
consumed_life: hour_meter          # the odometer's exact analog
item_types:                        # buy-policy routing (§3·B) runs first
  - { name: tractor_base, policy: used_market, metric: cpru }
  - { name: attachments,  policy: used_market, metric: cpru }   # box blade, cutter, loader, etc.
  # note: emissions/DPF filters & some wear parts are effectively new_only
location_signal: rural_ag_favorable
default_radius: 250                # iron travels; pair with freight_option
freight_option: true               # surface landed CPRU for far units
cadence: interactive               # one-shot now; graduate to scheduled if wanted
outreach_mode: draft               # until the tractor eval clears the bar
stale_days: 30
```

## Expected life (engine hours) — illustrative

| Class | Example models | Expected hours | Notes |
|---|---|---|---|
| Compact utility (diesel) | Kubota L/B, John Deere 1–4-series, Mahindra | 5,000–8,000 | Kubota diesels run forever if serviced |
| Utility (40–100 hp) | JD 5-series, Kubota M, NH Workmaster | 8,000–12,000 | Workhorses; clutch is the wear item |
| Older simple diesel (pre-emissions) | Ford 8N/3000, MF 135, JD 4020 | 10,000+ (rebuildable) | Simplicity = longevity; parts cheap |
| Modern Tier-4 (DEF/DPF) | post-2013 mid-size | 8,000–10,000 | Emissions complexity ↓ effective life; regen faults |

CPRU = `price / (expected_hours − meter_hours)`. A $14k 2,500-hr Kubota L3901
(exp 6,000) → `14000 / 3500 = $4.00/hr` remaining. Show a CPRU **band** when the
meter's originality is unconfirmed.

## Quality Card sources

TractorData (specs/years), TractorByNet + r/Tractors (real-owner issues),
Fastline buyer guides, dealer service bulletins, "best/worst <model> years".
Card axes: reliable series & **pre-emissions-complexity** eras to favor; Tier-4
regen-prone years to approach with caution; common failure modes (hydraulic
leaks, regen/DEF faults, clutch wear, front-axle slop on loader-worked units).

## Source registry

`TractorHouse`, `Fastline`, `Machinery Pete`, `EquipmentTrader` (structured,
the Auto.dev tier) **+** `Facebook Marketplace` + `Craigslist` (universal
private-party, inherits all FB know-how) **+** farm-equipment auctions
(`AuctionTime`/local) for comps.

## Deal-breakers (auto-skip)

seized/blown engine · dead/weak hydraulics · no PTO engagement · **rolled-back
or replaced hour-meter** (claimed hours ≪ visible wear) · **emissions-delete on a
Tier-4** (regulatory + resale poison) · no clear ownership · loader frame cracks.

## Verification recipes (deep-dive)

`serial_decode` (year/plant — the VIN analog) · `tractordata_spec_match` (engine,
hyd flow, PTO hp, 3-pt category) · **`parts_availability`** (discontinued parts =
future paperweight — a tractor-specific killer) · hour-meter-vs-wear plausibility.

## Minimal-N qualification slots (→ FSM)

**Canonical in code:** `skills/car-hunt/qualification/specs.py` → `TRACTORS`
(slots `hours`/`title`/`runs`). The FSM reads slots from there — keep this block in
sync with it (the optional `serial` 4th slot is not yet in the code spec):

```yaml
qualification_slots:
  hours:  "What does the hour-meter read, and is it the original meter?"
  title:  "Do you have clear ownership/a bill of sale in hand?"
  runs:   "Does it start cold, and do the hydraulics and PTO work without leaks or faults?"
  serial: "Could you share the serial-plate number or a photo?"   # optional 4th (not in specs.py yet)
```

`fail` on any (won't run, dead hydraulics, rolled meter, no ownership) →
disqualified, exactly like cars' `vin/title/runs`.

## Net-new feature this domain forces

**Attachment/compatibility graph.** Score the *bundle*: match implements to the
base unit by 3-point-hitch **category** (Cat 0/1/2), **PTO hp** (don't run a
6-ft bush hog on 18 PTO hp), loader mount, and hydraulic remotes. The hunt can
target "L-series Kubota **+** compatible box blade + 5-ft rotary cutter" and rank
on combined landed CPRU.

## Outreach template

> "Hi {name} — interested in your {year} {model}. Could we set a time to see it
> start cold and run the loader/PTO? And do you have ownership paperwork in hand?
> Thanks!"
