# car-hunt — Pre-Test-Drive VIN Finalization and Checklists (Step 5.5)

Read this when the user says they will go look at, test drive, or buy a specific car.

## Step 5.5: Pre-Test-Drive VIN Finalization

**Trigger:** the user says they'll go look at, test drive, or visit a specific car ("I'll test drive it tomorrow", "I'm going to see the Camry", "set me up for the Accord visit", etc.). This step gates the test drive — do NOT let the user walk into a seller's driveway without it.

**Goal:** convert "this listing looks good" into "this specific VIN is verified, recall-clear, and inspection-ready". The 5 minutes this takes prevents the most expensive failure modes (rebuilt title, salvage, mismatched VIN, open Takata airbag).

### Inputs needed from user

If the user has not provided the VIN, ask for it in one message:

> "Before you drive over, ask the seller for the VIN. Most sellers will share it — if they refuse, that's a red flag worth walking away from. Send the VIN here (text or photo of the door sticker) and I'll run the final checks."

Accept any of: typed VIN string, photo of door-jamb sticker (read it from the image), photo of dashboard windshield VIN.

Always echo the VIN back to the user before running checks — VINs are easy to misread (8/B, 1/I/L, 0/O/Q, 5/S, 2/Z).

### A. NHTSA VIN decode (free, always)

```
GET https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{VIN}?format=json
```

**Critical fields to verify against the listing:** ModelYear, Make, Model, Trim, BodyClass, EngineHP/Displacement/Cylinders, TransmissionStyle, DriveType, PlantCity, PlantCountry.

**🚫 If ANY field disagrees with the listing → STOP.** Possible causes: salvage rebuild with mismatched parts/body, fraudulent listing, sticker swap on a stolen car, or a typo. Do not let the user proceed until the discrepancy is resolved.

### B. Per-VIN unrepaired-recall check (Auto.dev CLI — preferred)

**Try Auto.dev first** — it provides the same per-VIN unrepaired recall data via a stable API, without browser automation:

```bash
npx @auto.dev/sdk open-recalls {VIN} --json 2>&1
```

Parse the JSON response:
- If the recalls array is empty → "All recalls remedied — no open recalls on this VIN."
- If recalls present → list each with campaign number, component, and remedy-available status.

**Tell the user to NOT take delivery until the dealer fixes any open recalls — Honda/Toyota fix open recalls for free regardless of buyer.**

**Fallback — browser automation (if Auto.dev CLI not logged in, or if CLI returns 402 Payment Required):**


Drive `https://www.nhtsa.gov/recalls` with a browser-automation tool (or ask the user to run it by hand). Use the 6-step flow documented in `deep-dive.md` Step 5 §F2:
1. Navigate to `https://www.nhtsa.gov/recalls`
2. Find `#ymm-vin-recalls-search-input`, set value via prototype setter, dispatch `InputEvent('input')` with `inputType: 'insertText'` and `data: <VIN>`, then `change`.
3. Walk up ~12 parents to find the enclosing container, click the visible "Search" submit button.
4. Wait ~6s for the result panel to render (URL redirects to `?vymm={VIN}`).
5. Read `document.body.innerText` and parse the result block:
```
{YEAR} {MAKE} {MODEL} VIN: {VIN}
Recall data refreshed on {date}
{N} Unrepaired Recalls associated with this VIN
```
6. Match against the result block (which has `VIN: {VIN}` immediately above) — not just the literal phrase — to avoid the false-positive in the page's help text.

- `N == 0` → safe; report "all recalls remedied"
- `N > 0` → list each unrepaired campaign with NHTSA #, component, and remedy availability.

### C. Title pre-flight (free)

For every private-party purchase, whatever the state, run NICB VINCheck (free, manual — no automation). Provide the link and the VIN. NICB will reveal:
- Theft history
- Total-loss declarations from any participating insurer (most major US insurers participate)

If the user is comfortable spending $3, also offer the NMVTIS lookup ([vehiclehistory.com](https://www.vehiclehistory.com/license-plate-search/{VIN})) for nationwide title brand history — junk, salvage, flood, etc. Critical when a listing description omits title status.

### D. Cross-check against listing claims

Compare:
- VIN-decoded year/trim ↔ listing year/trim
- VIN-decoded plant ↔ "1 owner" / "always local" claims (an import or a car built far from where the seller says it has always lived may have a different history than the seller suggests)
- Miles claimed ↔ NHTSA's odometer history (if available via the VIN report)

Flag any inconsistency for the user to ask about face-to-face.

### E. Estimated Out-of-Pocket (Auto.dev taxes — when logged in)

After VIN decode confirms the car, run:

```bash
npx @auto.dev/sdk taxes {VIN} --price {LISTING_PRICE} --zip {ZIP} --json 2>&1
# {LISTING_PRICE} = the seller's asking price from the listing, not the user's target budget
```

If the command fails (not logged in or Scale tier not enabled), **omit the entire block** — do not show empty fields. Just show: `Asking price: ${listing_price}`.

Parse and add an out-of-pocket block to the test-drive summary before handing the user the checklist:

```
💳 ESTIMATED OUT-OF-POCKET (ZIP {ZIP}):
  Asking price:       ${listing_price}
  Sales tax (est.):   ${tax_amount}
  Registration fee:   ${reg_fee}
  Doc fee:            ${doc_fee}
  ─────────────────────────────
  Total (est.):       ${total}
```

This helps set the negotiation ceiling: if total is tight, the user knows to negotiate more aggressively on price to stay within budget after taxes and fees.

### F. Generate the printable test-drive checklist

After all VIN checks complete, **always** generate a checklist for this specific car. The checklist is the deliverable of Step 5.5 — it's what the user takes with them to the seller. Format it as a single block of clean Markdown that prints/copies cleanly to a phone or paper. Use this template:

```
═══════════════════════════════════════════════════════════════
  TEST-DRIVE CHECKLIST — {YEAR} {MAKE} {MODEL} {TRIM}
  VIN: {VIN}  ·  ${price}  ·  {miles} mi  ·  CPM ${cpm}/mi
  Seller: {first_name}  ·  {city, state}  ·  Listing: {short_url}
  Generated: {YYYY-MM-DD}
═══════════════════════════════════════════════════════════════

┌─ BEFORE YOU LEAVE THE HOUSE ─────────────────────────────────┐
[ ] Cash or cashier's check ready (target: $______, walk-away: $______)
[ ] Bill of sale form printed ({CONFIG.jurisdiction.bill_of_sale_copies} copies, both signatures)
[ ] Flashlight + magnet (paint/body filler check) + tire-tread gauge
[ ] OBD-II scanner if you own one (clears recent codes = red flag)
[ ] Phone fully charged for photos of damage, VIN, odometer
[ ] Tell the seller: "Don't run it before I get there — I want to do a cold start."
└──────────────────────────────────────────────────────────────┘

┌─ PAPER CHECKS (before keys turn) ────────────────────────────┐
[ ] Title in seller's name, clean, NOT marked "Salvage" / "Rebuilt" / "Junk"
[ ] Title VIN matches dashboard VIN matches door-jamb sticker VIN
    Expected VIN: {VIN}
[ ] Seller's photo ID matches name on title
[ ] Odometer on title matches dashboard reading (within 1000 mi)
[ ] No active liens noted on title
└──────────────────────────────────────────────────────────────┘

┌─ COLD START (most important — only happens once) ────────────┐
[ ] Hood up, key OFF: oil dipstick at FULL line, oil clean honey/light brown
[ ] Coolant reservoir between MIN/MAX, no rust/oil floating in it
[ ] Brake fluid at MAX, light amber not dark
[ ] Power steering fluid at MAX, not foamy or dark
[ ] Transmission dipstick (if equipped): FULL, RED — not brown, not burnt smell
[ ] Now start it. WATCH the tailpipe in the rearview mirror at first key-on:
    [ ] No blue/white smoke (= oil burning)
    [ ] No black smoke (= rich/fuel issue)
    [ ] Smoke clears within 10 seconds in cold weather, immediately in warm
[ ] LISTEN for first 5 seconds:
{IF make=Honda AND model=Civic AND year IN [2012-2015]}
    [ ] No 1-2 second metallic rattle (= VTC actuator, $400-700 fix)
{IF make=Honda AND model=Accord AND year IN [2008-2012]}
    [ ] No metallic rattle on first cold start (= VTC actuator, $400-700)
{IF make=Toyota AND model=Camry AND year IN [2007-2011]}
    [ ] No clattering / valve-train tap (= 2AR-FE oil consumption beginning)
{IF year < 2010}
    [ ] No ticking/knocking from top end (= worn rocker arm or low oil)
[ ] All warning lights illuminate THEN extinguish within 5 seconds
[ ] No CEL (Check Engine), ABS, SRS, or TCS lights stay on
[ ] All gauges sweep and settle in normal range
└──────────────────────────────────────────────────────────────┘

┌─ STATIC INSPECTION (engine off, 5 minutes) ──────────────────┐
[ ] Walk around: panel gaps even, paint matches across panels (rebuild signal)
[ ] Magnet sticks to every steel body panel (no Bondo)
[ ] Tire tread depth ≥ 4/32" all four (penny test: Lincoln's head shows = bad)
[ ] All four tires same brand & size, even wear (uneven = alignment/suspension)
[ ] No rust on rocker panels, frame rails (look UNDER the car with flashlight)
[ ] Check for fluid puddles where it was parked (oil, coolant, transmission)
[ ] Open all 4 doors, hood, trunk — alignment, latches, weatherstripping intact
[ ] All glass: no chips, cracks, repair stars (windshield replacement = $200-400)
[ ] All lights work: headlights low/high, brake, turn (both sides), reverse
[ ] AC: blows COLD at center vent within 60 seconds at idle
[ ] Heat: blows HOT at center vent within 90 seconds (rules out heater core)
[ ] All windows up/down without grinding (regulators are common failure)
[ ] Power locks work all 4 doors
[ ] Driver's seat slides/reclines smoothly; no broken plastics on switches
[ ] All seatbelts retract fully and lock when yanked
[ ] No mildew/cigarette/pet smell (flood/heavy use signal)
[ ] Trunk floor / spare tire well DRY (water damage check)
└──────────────────────────────────────────────────────────────┘

┌─ MODEL-SPECIFIC RED FLAGS (this car's known issues) ─────────┐
{INSERT model-specific items based on year/make/model from reliability card}
{Examples — only emit the rows that match this car's profile:}
[ ] {Honda Accord 2008-2012} Pull dipstick after test drive — oil should still be at FULL
    Ask: "How often do you add oil between changes?" — anything > 0 qt/1000mi = walk
[ ] {Honda Accord 2008-2012 V6} Reject this model — 5AT in V6 had failure rate >25% by 150K. K24 4-cyl only.
[ ] {Honda Civic 2012-2015} Ask if airbag inflator recalls (Takata) have been done — verify on receipts
[ ] {Toyota Camry 2007-2011} 2AR-FE oil consumption: ask about piston-ring TSB (T-SB-0094-11). Untreated cars use 1qt/1000mi.
[ ] {Toyota Camry 2007-2011} Check for rear strut rubbing/clunk over bumps
[ ] {Honda CR-V 2017-2018 1.5T} Walk away — oil dilution issue, especially in cold climates
[ ] {Toyota Camry 2012+} Look for rear stabilizer bar end-link rattle on test drive
[ ] {ANY 8th gen Accord 2008-2012} Verify A/C compressor — failure ~$800
└──────────────────────────────────────────────────────────────┘

┌─ TEST DRIVE — minimum 15 minutes, mixed roads ───────────────┐
[ ] Driveway: smooth take-off from cold, no clunks from suspension
[ ] Parking lot: tight figure-8 left and right, listen for CV joint clicks
[ ] Reverse: 30+ feet straight back, no whine/grinding
[ ] City stop-and-go: smooth 1→2 and 2→3 shifts, no flare or slip (auto)
[ ] Hard braking from 30 mph (in safe spot): straight stop, no pulsation, no pull
[ ] 45-55 mph cruise: no vibration in steering wheel (alignment/balance)
[ ] Highway 65+ mph: no wandering, no death-wobble
[ ] Highway: WOT (wide-open throttle) acceleration to 70 — listen for transmission slip
[ ] Wind down all windows, stereo OFF: listen for whines, ticks, knocks at every speed
[ ] Hot stop: park, leave running 2 min, look under for new leaks
[ ] After drive: pop hood — coolant NOT boiling out of overflow (head gasket check)
[ ] After drive: oil dipstick still at FULL (oil consumption check)
└──────────────────────────────────────────────────────────────┘

┌─ NEGOTIATION LEVERS YOU FOUND (fill in during inspection) ───┐
[ ] Tire tread <4/32 → -$400 (set of 4 budget tires installed)
[ ] AC weak → -$600 to -$1200 (compressor/condenser)
[ ] Brake pulsation → -$200 (rotors + pads)
[ ] Battery >4 yrs old → -$150
[ ] Cracked windshield → -$300
[ ] Each warning light ON → -$200 minimum (codes need scan)
[ ] Cosmetic damage seller already disclosed: $______
[ ] Total deductions: $______
[ ] My ceiling: ${ask_price} − total deductions = $______
└──────────────────────────────────────────────────────────────┘

┌─ RED FLAGS — IF YOU SEE ANY OF THESE, WALK AWAY ─────────────┐
[ ] Title not present at meeting (any reason)
[ ] VIN on title doesn't match dashboard or door
[ ] Seller name on title doesn't match seller's ID
[ ] Engine smokes blue at any point (oil burning)
[ ] Transmission flares or slips on test drive
[ ] Any frame rail rust deeper than surface
[ ] CEL on, seller "doesn't know what it means"
[ ] Coolant in oil cap (mayonnaise) or oil in coolant (sheen)
[ ] Recent paint on a single panel that doesn't match
[ ] Seller pressures you to "decide now" or "two other people coming"
└──────────────────────────────────────────────────────────────┘

┌─ AFTER YOU AGREE TO BUY ─────────────────────────────────────┐
[ ] Sign bill of sale (both copies, both sign, keep one)
[ ] Title: seller signs and dates SELLER section ONLY (buyer signs
    {CONFIG.jurisdiction.buyer_signs_title})
[ ] Take photo of seller's driver's license next to the title for records
[ ] Pay only after both signatures and physical title in YOUR hand
[ ] Get keys (all keys — most cars have 2; ask for both)
[ ] Register at the {CONFIG.jurisdiction.register_where} within
    {CONFIG.jurisdiction.register_within_days} days (late fees accrue)
└──────────────────────────────────────────────────────────────┘
```

**Implementation rules for the checklist generator:**

- Always emit the WHOLE template — every section, every checkbox. Brevity is not a virtue here; the user is going to use this in a stressful negotiation and wants to see the line *before* needing to remember it.
- Substitute `{...}` placeholders with concrete values from the listing + VIN check + reliability card.
- For the `MODEL-SPECIFIC RED FLAGS` section: only emit the rows that match the year+make+model. If none match, emit a single line: `[ ] No known year-specific issues — standard inspection only`. Pull from the static caution table AND any live Step 1 reliability card findings.
- Substitute the price and the `walk-away` line — walk-away should default to ask price minus typical inspection-revealed deductions (~$500 for most listings).

### G. Save the checklist as a PDF (always)

**Every checklist generated in Step 5.5 must also be saved as a printable PDF.** The Markdown is for the chat; the PDF is for the user's pocket — they'll print it or open it on their phone at the seller's driveway.

**Filename:** `{CONFIG.paths.checklist_output_dir}/car-hunt-checklist-{YYYY-MM-DD}-{make-lower}-{model-lower}-{last4ofVIN}.pdf`

Example: `car-hunt-checklist-2026-04-28-honda-accord-9855.pdf`

**Implementation:**
- Use Python `reportlab` (Platypus). Install with `pip3 install --quiet reportlab` if it's not already present.
- Page size: US Letter, 0.5" side margins, 0.4" top/bottom.
- Use a header with the model + VIN, a sub-line with price/miles/CPM/seller/listing URL, and a "Verified: 0 unrepaired NHTSA recalls" line if Step B came back clean (or list the open ones if not).
- Every checklist section becomes a `<b>` heading followed by checkbox rows: render checkboxes as the literal Unicode `☐` followed by the item text (a Paragraph). Use `<sub>` / `<super>` tags for any subscripts/superscripts — never Unicode subscript glyphs (built-in fonts don't render them).
- The "Negotiation levers" section should be rendered as a `Table` with three columns (Issue / Deduction / Confirmed?) so the user can fill it in by hand. Bold-row + light-yellow background for the "Total deductions" and "My counter" rows.
- Insert a `PageBreak()` after the static-inspection section so the model-specific + test-drive + negotiation sections start fresh on page 2.
- Set the PDF's `title` and `author` metadata so it's identifiable in Finder/Files.
- Footer: a small italic note acknowledging the cold-start tailpipe + VTC listen as the single most important moment.

After writing the file, tell the user the absolute path and say: "Open it on your phone or AirPrint it. Take it to the seller."

**Per-car checklists are NOT committed to any repo.** They're disposable (tied to one listing) — keep `car-hunt-checklist-*.pdf` and `car-hunt-ranking-*.pdf` out of version control. For durable access, upload each to the cloud folder named in `CONFIG.paths.drive_folder` (create it once if missing) with whatever Drive tool is available — alongside delivering it in chat. Only the reusable forms (§H) live in the skill.

### H. Fraud / paperwork checklist (always emit alongside the test-drive checklist)

Used-car fraud is a multi-billion-dollar industry: forged titles, VIN cloning, curbstoning, title-jumping, odometer rollback, fake cashier's checks. **Every test-drive checklist generated in §F must be paired with a fraud / paperwork checklist** so the user can verify the documents against the car. This is a vehicle-agnostic checklist — it doesn't change based on year/make/model — so generate it once and reuse it across cars in the same hunt session.

**Prebuilt standing documents.** The fraud/paperwork checklist and a fillable bill of sale are vehicle-agnostic — do NOT regenerate them per car:
- `forms/fraud-paperwork-checklist.pdf`
- the bill of sale named in `CONFIG.jurisdiction.bill_of_sale_form` (the bundled generator builds an Alabama motor-vehicle bill of sale as one state's example — `forms/bill-of-sale-alabama.pdf`, seller's copy + buyer's copy; use your own state's form where it differs)
- Generator: `forms/build_forms.py`. If the PDFs are missing (a fresh copy of this skill ships without them), run it once to create them.

Just point the user at these two files (or attach them) alongside each per-car test-drive checklist. The per-car checklists are the only documents generated on the fly; the fraud + bill-of-sale forms never change.

**Mandatory sections, in this order:**

1. **⚠️ Walk-away triggers** — single-fail-and-leave items (refused VIN, missing title, mismatched VIN, scratched/laminated title, salvage/rebuilt brand, lien with no release, crypto/wire payment demand, blank-form signing pressure, ID mismatch, location-changing meets, time pressure tactics)
2. **Title document — visual inspection** (original not photocopy, watermarks/security features, no erasures/white-out, single ink color, brand-history field clean, owner name printed not handwritten, odometer field filled in, issue date plausible)
3. **VIN verification — three locations match** (dashboard / door jamb / title — write all three down digit-by-digit; beware 0/O, 1/I/L, 5/S, 2/Z, 8/B; 17 chars post-1981; sticker intact, no fresh adhesive; no paint overspray on plates; NHTSA decode + nhtsa.gov/recalls + nicb.org/vincheck + optional NMVTIS)
4. **Curbstoning detection** (title in seller's name 30+ days; ID matches title and address; ownership story plausible; insurance card present; personal photos in listing not lot/curbside; no multiple cars on same profile; reverse-image search; phone area code local; meeting at home)
5. **Odometer fraud detection** (title odometer matches dash within 1000 mi; no "Not Actual Mileage"; wear consistent — bolster, wheel, pedals, carpet, door handles; service stickers; cluster screws factory; OBD-II ECU mileage)
6. **Bill of sale** (two identical handwritten copies; today's date; both names + addresses; full VIN; odometer; actual sale price; AS-IS WHERE-IS language; both sign and date both copies; photo of seller's ID with bill of sale + VIN visible)
7. **Title transfer mechanics** (state-specific — fill from `CONFIG.jurisdiction`: who signs where and when (`buyer_signs_title`), registration deadline (`register_within_days`) and office (`register_where`), what to bring — signed title + bill of sale + ID + insurance + payment of `sales_tax_note`. Worked example, Alabama: seller signs SELLER section only in your presence and fills odometer + price; **buyer does NOT sign yet — a courthouse witness is required**; register within 20 days; ~2% state sales tax)
8. **Payment protection** (pay only after title + keys in hand; counterfeit-detector pen for cash; never accept seller's cashier's check; bank-to-bank meet at teller; never crypto/gift cards/wire to remote bank; no deposits; written receipt)
9. **Stolen-vehicle detection** (NICB clean; ignition/locks intact; service records consistent owner; insurance matches title; license plate registered to seller; ask to meet at police station — real sellers say yes)
10. **Title-jumping detection** (seller's name MUST be on title as registered owner, not as prior buyer; walk away from any "I haven't transferred it yet" situation except documented estate sales)
11. **After-purchase (within 7 days)** (register at the county office named in `CONFIG.jurisdiction.register_where`; new plate; insurance updated; independent mechanic post-purchase inspection $75–100; save all documents 3+ years)

**Implementation notes:**
- Use the same reportlab structure as §F (US Letter, ☐ checkboxes, sections in `<b>` headings, page break after section 4 or 5).
- Header should be in red (`#a83232`) instead of blue to visually distinguish it from the test-drive checklist.
- Add a prominent footer: *"This checklist exists because used-car fraud is a multi-billion-dollar industry. Most sellers are honest; the protective habit is: walk away if anything feels off. There will be another car."*
- The generator is `forms/build_forms.py` (builds both the fraud checklist and the example bill of sale) — adapt that rather than rebuilding from scratch. Its outputs are written next to it.

After producing the car-specific test-drive checklist, tell the user: *"Three docs are ready — the test-drive checklist (car-specific) plus the fraud-paperwork checklist and a fillable bill of sale (both reusable across all cars). Take all three. The fraud one is most useful in the seller's driveway when you're looking at the title; the bill of sale is for when you agree to buy."*

**Sample script structure** (the implementation that worked for the first checklist):

```python
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.flowables import HRFlowable

OUT = os.path.expanduser(f'{output_dir}/car-hunt-checklist-{date}-{make}-{model}-{vin_last4}.pdf')  # output_dir = CONFIG.paths.checklist_output_dir
doc = SimpleDocTemplate(OUT, pagesize=letter,
    leftMargin=0.5*inch, rightMargin=0.5*inch,
    topMargin=0.4*inch, bottomMargin=0.4*inch,
    title=f'Car Hunt Test-Drive Checklist — {year} {make} {model} (VIN ...{vin_last4})',
    author='car-hunt skill')

# Styles, sections, items, neg-table, etc. (see prior implementation)

doc.build(story)
```

Save the first working script to a scratch location (e.g. a temp directory) and adapt it for each new car rather than rebuilding from scratch; `forms/build_forms.py` shows the same reportlab patterns.
