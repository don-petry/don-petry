# Carriers, fare brands, miles, and the home-vs-hub arithmetic

The household's standing preferences live in `config/household.yaml` (default carrier, what to
compare when children fly, home airport and alternates). This file is the general knowledge that
tells you what those preferences cost:

- **A default carrier** — usually the one with the loyalty balance, and often the right answer when
  two adults fly alone.
- **Southwest or a budget carrier when the children are along** — worth comparing, and the
  comparison is only meaningful once bags and seats are priced in.
- **The home airport when it's easy, the hub when it's cheaper** — and the second half of that
  sentence is only true after the drive, the parking, and sometimes a hotel night are counted.

---

## 1. Home airport vs. a hub airport

### What the home airport actually flies

Record the home airport's nonstops in `config/household.yaml` under `home_nonstops`, read from the
airport's own "airlines and destinations" page, with the date you read it. A small regional airport
typically has a few dozen nonstops across four or five carriers, and often no ultra-low-cost
carrier at all. **Re-check the page each trip** — a regional airport's route map changes a few times
a year, and a new nonstop is the single biggest thing that can happen to a family's airfare.

Consequences worth internalizing:
- **Anything not on that list is a connection from home.** For a long trip, the home airport often
  means one stop through the very hub you could have driven to (you fly *over* the drive), while the
  hub means nonstop.
- **Southwest's network at a small airport is often genuinely good** for the big leisure
  destinations (Denver, Las Vegas, Orlando, Tampa, Dallas, Houston, Baltimore, Chicago Midway,
  Nashville). That can be most of where a family goes with children.
- **A legacy carrier at a small airport is mostly a feed to its hub.** Home→hub→destination is
  usually cheap but adds 3–4 hours and a connection risk.
- **If no budget carrier serves home**, a budget option means driving to the hub — the ground cost
  and the ultra-cheap fare arrive together.

### The true cost of leaving from the hub

Illustrative numbers for a hub about two hours away, about 300 miles round trip. Priced honestly
(`DRIVE_COST_PER_MILE` in the script, default $0.67/mile all-in) that is roughly **$200 in car cost
alone** before parking. Then:

- **Parking**: an off-airport lot is often about **$10/day**, versus $12–18/day at the airport
  decks. A 10-day trip is ~$100.
- **The night before**: for any departure before about 9 AM, the sane routine is to drive over the
  day before and stay at an airport hotel. Call it **~$190** plus dinner, and it beats a 3 AM start
  with two children. Record the household's own routine (hotel, lot) in the config.
- **Two hours each way of the vacation**, which is not a dollar figure but is real.

Put all of this in `origin_costs` and let the script do it. The recurring finding, and the reason
this model exists: **a fare that is $80/person cheaper out of the hub usually loses to the home
airport once ground costs land** — $320 of "savings" against $200 of driving, $100 of parking, and a
$190 hotel.

The hub wins when: the fare gap is large (>$150/person for four), the home routing adds a connection
on a long day with children, the trip is short enough that parking days are few, or the destination
has no reasonable routing from home at all.

### One more comparison worth running: don't fly at all

For destinations within about a day's drive, **price the drive**. For a party of four going a few
hundred miles to a city or a beach, four fares plus bags plus parking plus a rental car at the far
end rarely beats the car. `drive_options` in the ledger makes `report` do this properly.

The arithmetic that decides it, and where instinct goes wrong:

- **Ask who is driving first — it changes the answer more than any fare does.** On a drop-off
  (sending someone and collecting them later) the car covers the route **four** times while the
  passengers ride it **twice**, and an adult absorbs every one of those hours. If the travelers
  drive themselves, the car makes exactly two runs and the adult-hours term is **zero**. On the
  worked example below, that one fact moves the drive from $1,671 and 36
  adult-hours to $836 and none — from "not close" to "probably the right call." Never infer the
  answer from the travelers' ages; ask.
- **Check ages against a recorded date of birth, not a school grade.** A grade level is a decent
  guess and a bad fact. An 11th grader can turn 18 six weeks before the trip; a grade-based
  inference would put them at 16 and rule out the option that wins.
- **Two costs, both quoted.** The all-in rate (~$0.67/mile) books fuel, depreciation, tires and the
  maintenance the miles bring forward — the honest economic cost. The fuel-only figure is the
  out-of-pocket one, roughly $0.12/mile at 24 mpg and $2.95/gal. They differ by a factor of five,
  and a comparison that quotes only the first gets disbelieved while one that quotes only the
  second is wrong. Quote both.
- **Hours are part of the price.** A 491-mile run each way is ~7 hours; a drop-off round trip is
  28 hours of somebody's life. Flying the same route is a 20-minute airport run at each end. State
  the trade as a rate — "flying buys back an adult's time at $24/hour" — and let the household
  judge it. Below roughly $25–30/hour flying is usually worth it; well above that it isn't.
- **A free overnight is worth showing even at $0.** Breaking a 7-hour haul into two half-days with
  grandparents changes whether the drive is *tolerable*, which is a different question from whether
  it's *cheap*. Price it at zero, show it anyway.
- **Half a journey is not a journey.** "Drive down, fly home" is a legitimate plan but not a
  substitute for a round trip — its cash figure is missing two one-way fares. The script marks
  those `[PARTIAL]` and refuses to let them set the bar.

Worked example — sending two 18-year-olds 491 miles to family for Thanksgiving 2026, with
grandparents near the halfway point offering a free overnight:

| Option | All-in | At the pump | Adult-hours |
|---|---|---|---|
| **They drive themselves**, straight through (491 mi each way) | **$738** | **$201** | **0** |
| **They drive themselves** via the grandparents, free overnight (534 mi) | **$836** | **$251** | **0** |
| They drive themselves, two cars | $1,551 | $383 | 0 |
| An adult drops them off, straight through | $1,476 | $401 | 28 |
| An adult drops them off via the grandparents | $1,671 | $503 | 36 |
| Fly (connecting; no nonstop exists) | *fare* | *fare* | ~1.3 |

Read the two halves of that table against each other: **the same route, the same miles, and a 2×
swing in cash plus the entire adult-hours column, decided by nothing but who holds the wheel.**
As a drop-off, driving loses on cash and time and isn't close. Driven by the travelers, it beats
almost any Thanksgiving fare for two — and the free overnight with family costs $98 to turn a
7-hour push into two 4.5-hour halves, which is the version worth doing.

Note what the model deliberately does *not* do: it won't price the risk of a long drive for a
new driver, and it shouldn't. It puts the money, the hours and the vehicle question in front of
the household and stops. That call belongs to them.

## 2. Fare brands — what the cheap number leaves out

The headline fare is not the product. What differs is exactly the stuff a family needs.

### Delta

- **Main Cabin and above**: no change fees on domestic itineraries, advance seat selection included,
  first checked bag paid separately.
- **Main Basic (basic economy)**: cheapest, and for a family usually a false economy — no advance
  seat selection (a 12-year-old may end up rows from a parent), no changes, last boarding group, so
  the roller bag gets gate-checked anyway.
- **24-hour risk-free cancellation on every fare, including Basic** — and Delta applies it even to
  tickets bought the day of departure, which is more generous than the DOT floor requires. This is
  the single most useful policy in this whole file: see §5.
- Delta's own booking page is the only place to get its award pricing.

### Southwest — changed substantially in 2025–26, so old instincts are wrong

The two things "everyone knows" about Southwest are both now false:

- **Bags no longer fly free** on most fares. For tickets booked on or after **28 May 2025**, checked
  bags cost roughly **$45 first / $55 second** on Basic, Choice and Choice Preferred. Only **Choice
  Extra** still includes two free checked bags. A-List members and the Southwest credit cards retain
  their own allowances — check the household's status before assuming.
- **Seating is assigned.** From flights on **27 January 2026** onward, seats are selected at booking
  on most fares; **Basic** gets a seat assigned at check-in, which for a family means whatever is
  left.

Fare tiers and what they mean for a family:

| Fare | Changes | If canceled | Use it when |
|---|---|---|---|
| **Basic** | Not changeable | No credit after the 24-hour window — the money is gone | Never, with children. It gives up every advantage Southwest has. |
| **Choice** | Free changes, no fee | 12-month transferable flight credit | The default. This is the fare that makes Southwest worth watching. |
| **Choice Preferred / Extra** | Free changes | Cash refund | When the dates are genuinely uncertain, or (Extra) when 2 free bags beat the fare gap |

**The Southwest superpower is re-faring.** On Choice and above, and on points bookings, there is no
change fee — so when the price drops you re-book the same flight and pocket the difference as credit
(or points back), as many times as it drops. That inverts the usual advice: on Southwest, buying
early is *safe*, because you keep the upside of every later drop. On Basic you get none of it.

Southwest fares now appear in Google Flights, so the grid sweep can include them — but **book on
southwest.com**, which is where points pricing and the re-fare flow live.

### Budget carriers (Frontier, Spirit, Allegiant, and Breeze's cheapest bundles)

Many small airports have none of them, and then a budget option means driving to the hub — the
ground cost and the ultra-cheap fare arrive together. Check `home_nonstops.not_served` in the config.

Price the fare as: base + **carry-on** (they charge for it) + checked bags (often $60–80 each way,
each) + seat fees to sit the party together + any card-payment or "convenience" fee. A $119 fare for
four with three bags and assigned seats routinely lands north of $1,400 all-in. Sometimes it still
wins. Log those fees in the quote (`bag_fee_each_way`, `seat_fee_total`) and let the script decide —
`verify` refuses a budget quote with no bag fee recorded, because that comparison is fiction.

The other cost is thin schedules: two flights a week means a cancellation can be a two-day delay,
with no interline agreement to re-accommodate you on anyone else. For a trip with a hard anchor
(the holiday, the cruise, the wedding), price that risk in.

## 3. Miles — Delta SkyMiles

Delta has had **no award chart since 2015**. Award prices are dynamic and track cash fares, so the
question is never "do we have enough miles," it's **"what is each mile buying?"**

    cents per mile = (comparable cash cost − award cash cost) ÷ miles × 100

`fare_watch.py` computes this against the comparable cash quote on the same dates and origin.

- **Baseline value: about 1.2¢ per mile.** The ledger's `miles.min_cpm` sets the floor — default 1.3¢.
- **Below the floor, pay cash.** Domestic short-haul awards often price at 0.9–1.3¢, which means the
  miles are worth more saved for a trip where they aren't.
- **Above it, spend.** Peak-date domestic and international premium cabins are where SkyMiles earn
  their keep.
- **Award tickets cancel free back to the account**, which is a real flexibility premium on top of
  the cents-per-mile — worth a few tenths of a cent when the dates are shaky.
- **TakeOff 15** knocks 15% off award prices for Delta card holders; check whether the household's
  card qualifies before comparing.
- Paying cash **earns** miles and MQDs; paying miles doesn't. On a marginal call, that tilts to cash.

Award space is not a price you can watch on Google Flights. It has to come from Delta's own award
calendar, which is why `verify` rejects an award quote from a tier-2 source.

## 4. Two adults vs. the whole family

The party changes the answer, not just the total. The household's own version of these rules lives
in `config/household.yaml` under `rules.party_modes`:

- **Both adults alone** — the default carrier, no checked bags or one, seat fees irrelevant, basic
  economy actually viable if the fare gap is real. Flexibility matters less. Miles go further per
  person.
- **With the children** — three or four checked bags, seats together are non-negotiable, basic
  economy is usually disqualified on that ground alone, and a missed connection is a much bigger
  event. Southwest's re-fare flexibility and Delta's Main Cabin change-free policy are worth real
  money.
- **A bigger party (six or more)** — cheap fare buckets frequently don't have six seats left, so the
  *availability* constraint starts binding before the price does. `seats_left` in a quote is what
  catches this; the script disqualifies any fare that can't seat the whole party.

## 5. The policies that make buying reversible

This is why "buy now" is usually less risky than it feels.

- **The DOT 24-hour rule (14 CFR 259.5).** For a ticket bought at least **7 days** before departure,
  US carriers must offer either a free 24-hour hold at the quoted fare *or* a full refund if you
  cancel within 24 hours. The airline chooses which; most, including Delta, offer the refund.
- **Delta goes further** — 24-hour risk-free cancellation on every fare, even inside the 7-day
  window.
- So the recommended move on any BUY is: **book it, then re-shop the same grid the next day.** If
  something better turned up, cancel for a full refund. The downside is one day of attention; the
  upside is the whole price gap.
- **After 24 hours**: Delta Main and above can be changed for free (fare difference applies, and a
  drop becomes an eCredit); Delta Basic cannot be changed at all. Southwest Choice and above can be
  re-fared freely; Southwest Basic cannot, and canceling it after 24 hours forfeits the money.
- Set `refundable_24h` and `changeable` on each quote — they are what turn a BUY into a
  BUY-AND-WATCH, and what decide whether a post-purchase drop is recoverable.

## 6. Sources

Read August 2026. Airline policies change often — **re-verify anything in §2 and §5 on the
carrier's own site before acting on it.**

- Your home airport's own "airlines and destinations" page (record it in `home_nonstops.source`)
- [Southwest — lower fare refund options](https://support.southwest.com/helpcenter/s/article/lower-fare-refund)
- [Southwest 2026 changes: assigned seating, fare bundles, bag fees](https://www.pointscrowd.com/blog/southwest-changes-2026-assigned-seating-new-fare-bundles-bag-fees-more/)
- [Southwest price-drop policy by fare tier](https://www.plot.travel/blog/southwest-price-drop-policy)
- [The 24-hour flight cancellation rule](https://thriftytraveler.com/guides/24-hour-rule-free-cancellation/)
- [Delta SkyMiles award pricing — dynamic model](https://10xtravel.com/delta-skymiles-award-dynamic-pricing-model/)
- [Delta SkyMiles redemption guide with real pricing data](https://awardfares.com/blog/skymiles-guide/)
