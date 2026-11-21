# car-hunt — Deep-Dive and Head-to-Head (Steps 5 and 5.25)

Read this when the user picks candidates to investigate, gives a VIN, or is weighing two cars.

## Step 5: Deep-Dive (Optional — user-initiated)

When the user selects specific candidates, run in parallel for each:

### A. NHTSA Recalls (free API)

```
GET https://api.nhtsa.gov/recalls/recallsByVehicle?make={make}&model={model}&modelYear={year}
```

Report: number of open recalls, brief descriptions, whether they are safety-critical.

### B. NHTSA Complaints (free API)

```
GET https://api.nhtsa.gov/complaints/complaintsByVehicle?make={make}&model={model}&modelYear={year}
```

Report: total complaints, top 3 complaint categories, any patterns matching the reliability card from Step 1.

### C. NHTSA Safety Ratings (free API)

```
GET https://api.nhtsa.gov/SafetyRatings/modelyear/{year}/make/{make}/model/{model}
```

Report: overall safety rating (stars out of 5).

### D. Market Comparison (WebSearch)

Search: `"KBB {year} {make} {model} {trim} {miles} miles value"` to find if ask price is above/below market.

```
Market Context — {year} {make} {model} {trim} @ {miles}mi:
  Ask price:    ${price}
  KBB estimate: ~${kbb_range} (fair purchase price)
  Verdict:      [Below market / At market / Above market by ~${delta}]
```

### E. Total Cost of Ownership (Auto.dev CLI — when logged in)

```bash
npx @auto.dev/sdk tco {VIN} --zip {ZIP} --json 2>&1
```

If the command fails (not logged in or Growth tier not enabled), skip this section silently — it's informational, not blocking.

Parse the JSON and surface a TCO block in the deep-dive summary:

```
💵 5-YEAR TOTAL COST OF OWNERSHIP (Auto.dev estimate):
  Fuel:           ~$X,XXX
  Insurance:      ~$X,XXX
  Maintenance:    ~$X,XXX
  Depreciation:   ~$X,XXX
  ─────────────────────
  5-yr TCO:       ~$XX,XXX   (~$X,XXX/yr)
```

**Usage rules:**
- TCO is a **secondary signal only** — never use it to override CPM for ranking decisions.
- TCO assumes average driving (~15K mi/yr, national avg fuel/insurance rates). Flag to the user if their usage patterns differ significantly.
- Comparing two candidates' TCO alongside their CPM helps surface cases where a nominally cheaper car (lower price, better CPM) has higher ongoing ownership costs.

### F. VIN Lookup (user provides VIN — image, sticker photo, or string)

When the user gives you a VIN (or a photo of one — read it from the image), run these in parallel:

#### F1. NHTSA VIN decode — free, always works
```
GET https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{VIN}?format=json
```
Verify: model year, make, model, trim, body class, engine displacement, cylinders, transmission, drive type, plant city all match the listing. **Flag any mismatch as 🚫 — possible fraud, salvage rebuild, or wrong sticker.**

#### F2. Per-VIN remedy status — Auto.dev CLI (preferred) or browser fallback

**Preferred — Auto.dev CLI (no browser needed):**
```bash
npx @auto.dev/sdk open-recalls {VIN} --json 2>&1
```
Returns only unrepaired recalls for this specific VIN. Empty array = all recalls remedied.

**Fallback — NHTSA browser automation (if not logged in to Auto.dev, or if CLI returns 402 Payment Required):**

The public NHTSA recall API (`api.nhtsa.gov/recalls/recallsByVin`) returns "Missing Authentication Token" — it's not a real public endpoint. Drive the NHTSA site with a browser-automation tool (or have the user do it by hand):

1. Navigate the tab to `https://www.nhtsa.gov/recalls`
2. Find input `#ymm-vin-recalls-search-input`, focus it, set value via the prototype setter, dispatch `InputEvent('input')` with `inputType: 'insertText'` and `data: <VIN>`, then `change`.
3. Walk up ~12 parents from the input to find the enclosing container, then click the visible submit button whose text is "Search".
4. Wait ~6s for the result panel to render. The URL will redirect to `?vymm={VIN}`.
5. Read `document.body.innerText` and parse the result block. Look for the literal pattern:
   ```
   {YEAR} {MAKE} {MODEL} VIN: {VIN}
   Recall data refreshed on {date}
   {N} Unrepaired Recalls associated with this VIN
   ```
   - If `{N} == 0` → **All recalls remedied — strong positive signal.**
   - If `{N} > 0` → Each unrepaired recall is listed below with NHTSA campaign #, component, and "Remedy Available" / "Remedy Not Yet Available". Capture all of these and report them as blocking issues (free dealer fix required before purchase).

**Caution:** the help text on the same page also contains the literal string "0 unrepaired recalls associated with this VIN" as an example — match against the result block (which has `VIN: {VIN}` immediately above), not just the literal phrase, to avoid false positives.

**Do NOT use Honda's owner recall portal (`mygarage.honda.com/s/recall-search`).** Its Salesforce LWC form rejects programmatically-typed VINs as "Incorrect VIN entered" regardless of how the input value is set (prototype setter, InputEvent with data, execCommand insertText, blur-to-commit). NHTSA's site works; Honda's does not.

#### F3. Vehicle history report (Carfax-style accident/ownership data)

Carfax and AutoCheck are **paid** ($45–$100 per report) and require a logged-in user account. Do NOT automate these — point the user to them. There are also **free** alternatives that should be checked first:

| Source | What you get | Cost | Automation |
|---|---|---|---|
| **NICB VINCheck** ([nicb.org/vincheck](https://www.nicb.org/vincheck)) | Theft history; salvage/total-loss declarations from member insurers | Free, 5/day limit | Manual — bot-protected form |
| **NMVTIS** (vehiclehistory.com / clearvin.com / etc.) | Title history across all 50 states (junk, salvage, flood, brand changes) | $2–$5/report | Manual — paid |
| **Manufacturer VIN history** (dealer service records) | Service/maintenance history from any franchise dealer using their factory system | Free if you ask the local dealer service desk politely; they often print it | Manual — phone call |
| **Carfax via dealer trade-in tool** | Full Carfax | Free if any car dealer pulls it for you (they pay flat fee) | Manual |
| **Carfax / AutoCheck direct** | Full report | $45–$100 | Manual — never auto-purchase |

For each candidate the user wants to deep-dive, generate **all** of these as clickable links with the VIN pre-filled where supported:
- `https://www.nicb.org/vincheck` (manual entry — VINCheck doesn't accept query params)
- `https://www.vehiclehistory.com/license-plate-search/{VIN}` 
- `https://www.carfax.com/vehicle/{VIN}`
- `https://www.autocheck.com/vehiclehistory/autocheck/en/vinbasics?vin={VIN}`

Tell the user explicitly: "I won't purchase paid reports automatically — open these links yourself if you want to spend the money. Run NICB and ask a local franchise dealer to pull a Carfax for free first."

Present deep-dive report:

```
══════════════════════════════════════
  DEEP DIVE: #{N} — {year} {make} {model} {trim}
  ${price} | {miles} mi | CPM: ${cpm}/mi | Life: {life_pct}%
══════════════════════════════════════

📋 RELIABILITY (from Step 1 research):
  {year} is a: ✅ Best year / ⚠️ Caution year / 🚫 Avoid year
  Known issues for this year: {from reliability card}

🔧 NHTSA RECALLS ({count} open):
  {recall description} — {date} — [Safety critical? Yes/No]
  (none) if clean

📣 NHTSA COMPLAINTS ({total} total):
  Top categories: {category1} ({n}), {category2} ({n}), {category3} ({n})
  {any pattern matching reliability card issues}

⭐ SAFETY RATING: {N}/5 stars overall

💰 MARKET VALUE:
  Ask: ${price} | KBB fair: ~${kbb} | [{verdict}]

💵 5-YEAR TCO (Auto.dev — if available):
  Fuel: ~$X,XXX | Insurance: ~$X,XXX | Maintenance: ~$X,XXX | Depreciation: ~$X,XXX
  Total: ~$XX,XXX (~$X,XXX/yr)   [omit section if Auto.dev not logged in]

🔑 VIN CHECK:
  Decoded: {year} {make} {model} {trim} — ✅ matches listing / ⚠️ mismatch: {detail}
  Full history: vehiclehistory.com/vin/{VIN}  (run manually)

📋 RECOMMENDATION:
  {1-2 sentence summary: worth pursuing / walk away / negotiate price / inspect specific items}
```

---

## Step 5.25: Head-to-Head Comparison (when user is weighing two cars)

When the user pivots to "what about this one?" with a second listing while a first is already in play (or asks "should I do A or B"), do not just analyze the new listing in isolation. Generate an explicit head-to-head table comparing the two on every dimension that matters, with information asymmetry called out:

| | Car A | Car B |
|---|---|---|
| Price | | |
| Miles | | |
| **CPM** | | |
| **Adj.CPM (tier)** | | |
| Remaining miles | | |
| **Location tier** | A / B / C / D | |
| Title | (verified vs. unknown) | |
| Owners | (stated vs. unknown) | |
| Recall status | (per-VIN result if known) | |
| Description detail | (full vs. one sentence) | |
| Caution year? | | |
| Engine reliability | (specific known issues for this powertrain) | |
| Expected lifetime | | |

**Information asymmetry rule:** when one car has verified data (clean title confirmed in description, VIN-checked recall status, full description with disclosures) and the other has unknowns ("Runs and drives smooth" with no title/owner/issue mention), call this out explicitly. The one with more verified data is the higher-confidence buy even if the unverified one wins on raw CPM. Tell the user: "X is theoretically the better-value car, but you're paying with information asymmetry. Y is the higher-confidence buy at a slightly worse CPM."

**Recommendation should be opinionated:** don't list both cars and let the user choose. Pick one and explain why, with a fallback condition ("test drive A first; if it disqualifies, fall back to B"). Hedging-by-default produces analysis paralysis at the seller's driveway.
