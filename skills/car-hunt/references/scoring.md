# car-hunt — Scoring detail, results layout and spreadsheet columns (Steps 3, 4, 6)

Read this when scoring listings (Step 3), presenting results (Step 4) or exporting (Step 6) in `../SKILL.md`.

## Location Quality Tier — rules and display (Step 3)

**Tier-aware scoring rules:**
- Tier A or B + listing description is sparse → still ⚠️ flag, but assume "maybe just terse seller, not hiding issues."
- Tier D + sparse description → escalate to ⚠️⚠️ — sparse + likely-tighter-finances combination is the highest-risk group.
- Tier A or B + price seems high → that's the negotiation opportunity; sellers in these tiers often accept 8–12% off ask without pushback.
- Tier D + price below market → verify scam signals and title with extra rigor before celebrating CPM.

**Display the Tier in:**
- The ranked listings table (new column: `Tier`)
- The spreadsheet (new column after `Location`: `Tier`)
- The head-to-head comparison table (new row: `Location tier`)
- The test-drive PDF header line (e.g., "Location: Northside Hills ST · Tier A")
- The skill's recommendation: a Tier A car at slightly worse CPM should still be presented as the leading candidate over a Tier D car at slightly better CPM, with the why explicit.

**Extending to other metros:** when `CONFIG.location_tiers` is empty, or the user searches from a ZIP outside the configured metro, ask once: *"I'll build a location-quality tier table for that metro on the first run and reuse it — OK?"* Then research median household income by city in that metro (Census, Wikipedia, BestPlaces.net), build a 4-tier table with the thresholds in `../SKILL.md` (Location Quality Tier), and save it to `config/household.yaml` under `location_tiers` (or a second metro entry) so it persists across runs. Leave `Tier` blank until a table exists.

**Honest framing in the user-facing output:**

When you cite tier in a recommendation or warning, name the actual mechanism, not the demographic. Good: *"Sellers in {town} tend to be less price-sensitive — there's room to negotiate $300–500 off ask."* Bad: *"{town} is a rich neighborhood."* The signal is economic and behavioral, not identity-based; keep the language objective.

## Seller Trust Score (Step 3)

After applying the location-quality tier, compute a **Seller Trust Score** for each listing based on observable seller profile signals. This score stacks on top of the location-tier CPM adjustment.

**Classification table (Facebook Marketplace):**

**Evaluate in order — CAUTION first, then TRUSTED, then NEUTRAL as the fallback.**

| Score | Label | Criteria |
|-------|-------|----------|
| S− | `CAUTION` | `joined_months < 12` OR `active_listings ≥ 10` (flipper/dealer front) OR (`fb_rating < 4.0` AND `fb_rating_count ≥ 5`) |
| S+ | `TRUSTED` | `joined_months ≥ 36` AND (`fb_rating ≥ 4.5` OR `fb_rating_count = 0` with `joined_months ≥ 24`) AND (`active_listings ≤ 3` OR `active_listings = null`) |
| S0 | `NEUTRAL` | All other cases, including profile unreadable (default) |

**Default seller trust by platform (when no profile data is available):**
- Craigslist private: `NEUTRAL` (always anonymous; no signals)
- AutoTrader / CarGurus private seller: `NEUTRAL` (no profile exposed)
- Dealer listings (any platform): `—` (institutional sellers; no trust tier applies)

**CPM adjustment (stacked on location-tier adjustment):**
- `TRUSTED` → subtract $0.003/mi from quality-adjusted CPM
- `NEUTRAL` → no change
- `CAUTION` → add $0.004/mi to quality-adjusted CPM

The final `Adj.CPM` used for sort order = real CPM ± location-tier adjustment ± seller-trust adjustment.

**Seller column display format:**
- `TRUSTED ★4.8(12)` — long-tenure account with rating and count
- `TRUSTED` — long tenure, no ratings yet
- `NEUTRAL` — default / no strong signal
- `NEUTRAL (profile unreadable)` — extraction failed; treated conservatively
- `CAUTION ⚠ new acct` — joined < 12 months
- `CAUTION ⚠ 14 listings` — high active-listing count (flipper/dealer signal)
- `—` — dealer listing (not applicable)

**Additional flags** (add to Flags column):
- `🔴 CAUTION SELLER` — seller is classified CAUTION; complements the CPM penalty so it's visible at a glance
- `🟡 UNVERIFIED SELLER` — seller profile was unreachable or unreadable; score defaulted to NEUTRAL

## Results layout (Step 4)

Present reliability cards first, then the ranked table:

```
═══════════════════════════════════════════════════════════════════
  CAR HUNT RESULTS — {N} candidates — {date}
  Search: {makes/models} | {year_min}–{year_max} | ≤${max_price} | {zip} +{radius}mi
  Sources: AutoTrader · CarGurus · Craigslist · Facebook Marketplace · Auto.dev
═══════════════════════════════════════════════════════════════════

[Reliability cards from Step 1 — one per model — displayed here]

─── RANKED LISTINGS (by CPM) ───────────────────────────────────

| # | Make/Model | Year | Trim | Dr | Trans | Miles | Price | CPM | Adj.CPM | Life% | Dist | Posted | Location | Tier | Seller | Dealer | Flags | Link |
|---|-----------|------|------|----|-------|-------|-------|-----|---------|-------|------|--------|----------|------|--------|--------|-------|------|
| 1 | Honda Civic | 2021 | EX-L | 4 | Auto | 42,000 | $21,500 | $0.103 | $0.098 | 17% | ~12 mi | Apr 20 | Northside Hills, ST | **A** | — | Dealer | — | [link] |
| 2 | Toyota Camry | 2019 | XLE | 4 | Auto | 68,000 | $21,000 | $0.091 | $0.089 | 23% | ~172 mi | Apr 18 | Lakeview, ST | **B** | — | CarMax | — | [link] |
| 3 | Honda Accord | 2018 | Sport | 4 | Auto | 89,000 | $19,500 | $0.121 | $0.128 | 36% | ~8 mi | Apr 10 | Old Mill, ST | **D** | CAUTION ⚠ new acct | Private 🏠 | ⚠️ CAUTION YEAR 🔴 CAUTION SELLER | [link] |
...

⚠️  FLAGS:
  #3: Accord 2018 — CVT shudder reported at 70k+ miles (per CarComplaints); confirm transmission service history
  #3: 🔴 CAUTION SELLER — FB account joined < 12 months ago; verify identity and title carefully
  #N: [any other flags]

📊 SUMMARY:
  Best CPM overall:  #N — {make/model/year} @ ${cpm}/mi
  Best local deal:   #N — within 50 miles of {zip}
  Best private seller: #N — {make/model} via FB Marketplace
  Best trusted seller: #N — {make/model}, TRUSTED ★{rating}({count}) (if any TRUSTED-classified FB listing exists)
  Best Toyota:       #N — {model/year} @ ${cpm}/mi
  Best Honda:        #N — {model/year} @ ${cpm}/mi
  ✅ Best reliability year in results: {year} {make} {model} (per Step 1 research)
  Skipped (no data): {count} listings where miles/price were missing
```

## Spreadsheet columns (Step 6)

```
Date | Make | Model | Year | Package | Doors | Trans | Miles | Cost | CPM | Adj.CPM | Life | Dist | Posted | Location | Tier | Seller | Dealer | Link | Notes | Contacted
```

- **Date** — `DD Mon YYYY` (e.g., `25 Apr 2026`) — date this row was last updated
- **Package** — trim level (e.g., `LX`, `EX`, `LE`); **Doors** — `2` or `4`; **Trans** — `Auto` or `Manual`
- **Posted** — date the listing was first posted (e.g., `Apr 20`) — omit year if current year; `Unknown` if not found
- **Miles** — numeric, no commas (e.g., `53000`); **Cost** — `$4750`
- **CPM** — `$0.019` (3 decimals) — the *real* cost-per-mile
- **Adj.CPM** — `$0.014` — the *quality-adjusted* CPM with location-tier AND seller-trust modifiers stacked (sort by this)
- **Life** — `18%`
- **Tier** — `A` / `B` / `C` / `D` per the metro table; blank if the metro has no table yet
- **Seller** — Seller Trust Score with detail (e.g., `TRUSTED ★4.8(12)`, `NEUTRAL`, `CAUTION ⚠ new acct`); `—` for dealers
- **Notes** — emoji flags (✅ BEST YEAR / ⚠️ CAUTION / 🚫 AVOID / ★ BEST PICK) and the specific reason
- **Contacted** — `YYYY-MM-DD sent` when a message was sent to this seller; blank if not yet contacted. Updated by Step 7.

Build the CSV with Python's `csv` module (UTF-8), one row per listing.
