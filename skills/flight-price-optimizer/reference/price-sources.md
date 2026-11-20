# Where prices come from, and what counts as one

A fare watch is only as good as the prices in it. This file is the sourcing discipline: which tools
to sweep with, which to buy from, what to write down, and the one thing this skill never does.

---

## 0. The guardrail: never buy

**This skill researches, compares, recommends and schedules. A human presses "purchase."**

No exceptions, and not even when asked — booking spends real money on a non-refundable-after-24-hours
product, in someone else's name, with someone else's payment card, and it is the one action in the
whole workflow that cannot be undone by trying again. The deliverable is a recommendation the family
can act on in about ninety seconds: carrier, fare brand, exact dates and flights, the all-in number,
where to click, and the deadline.

The same applies to standing price alerts on the family's accounts: propose them, hand over the
exact steps, let the user create them.

## 1. Source tiers

| Tier | Source | What it's good for |
|---|---|---|
| **1** | **The airline's own booking page** — delta.com, southwest.com, united.com, aa.com. Also Delta's award calendar for SkyMiles pricing. | The only place a fare is actually for sale. **Required before buying** and for anything logged as a final number. |
| **2** | **Google Flights** and comparable metasearch reading live inventory. | Sweeping a date grid, comparing carriers and airports, price history and alerts. Fine for tracking a trend; confirm on tier 1 before acting. |
| **3** | Deal blogs, newsletters, screenshots, "I saw $198 last week," a fare quoted in an earlier session, memory. | A **lead**, never a price. `fare_watch.py` refuses to build a recommendation on one. |

Every quote in the ledger carries `source: {tier, name, url}`. A price with no source doesn't go in.

**Prices go stale in days, not weeks.** A quote older than `--fresh-days` (default 3) stops counting
as today's price and becomes history. A whole watch that hasn't been checked within its cadence
makes `report` exit non-zero — a stale watch is a broken watch, not a quiet one.

## 2. The sweep: Google Flights

This is the workhorse for tier-2 breadth. In one pass it answers the date question, the airport
question and the carrier question.

1. **Enter the route with both origins.** Google Flights accepts multiple origin airports in one
   search (the home airport and the hub) and multiple destinations. One search covers the whole airport comparison.
2. **Open the date grid** (the calendar view) to see a matrix of outbound × return prices, and the
   **price graph** for the trend across dates. This is the fastest way to price the whole fuzzy
   window — but read it against the grid `fare_watch.py grid` printed, because Google's grid does
   not know about the holiday anchor, the blackout days or the nights limits.
3. **Read the price-history / "cheapest time to book" panel.** Google shows whether the current
   price is low, typical or high for that route and dates, and where the historical low point sits.
   That is route-specific evidence and it beats the generic booking-window prior — log it in the
   ledger as a note.
4. **Filter to the family's real constraints** before comparing: max stops, departure and arrival
   time windows, carriers, and bags (Google can add bag fees to the displayed price — turn it on).
5. **Turn on price tracking** for the specific dates, and separately for "any dates" if the trip is
   flexible. Alerts go to the user's Google account; ask before creating them on anyone's behalf.
6. **Southwest appears in Google Flights** now, so it belongs in the sweep — but book on
   southwest.com, where points pricing and the re-fare flow live.

Two Google features worth knowing and not over-trusting:
- **Price guarantee** — on some Book-on-Google itineraries a badge promises the difference back if
  the price drops before departure. It's capped (about $500/year), US departures only, and shows up
  on a minority of itineraries. Nice when present; never a reason to choose an itinerary.
- **"Prices are currently low"** is a claim about history, not a forecast. It's an input to the
  decision, not the decision.

## 3. Confirming on tier 1

Before any BUY recommendation goes to the family, re-price the exact itinerary on the airline's own
site and log that quote. Metasearch drifts from live inventory in exactly the ways that matter:
the last four seats at the low bucket, a fare that no longer exists, a bag fee that changed, an
award price that metasearch never had.

While there, capture what only the airline shows: `seats_left` if displayed, the fare brand's real
rules, whether seat selection costs extra for the party, and the award price in miles.

## 4. Other places worth a look, and what they're for

- **The airline's own low-fare calendar** (Delta's, Southwest's) — the cleanest month-at-a-glance
  view for that carrier, and for Southwest the only place points prices appear.
- **Fare-sale mail.** Sales are the biggest single cause of a real drop. If a mail tool is
  available, search the household's mail for `from:delta.com`, `from:southwest.com`,
  `subject:(fare sale OR "price drop")` when a watch is running, and check the airline's deals page
  during the prime window.
- **Deal newsletters** (Going, Thrifty Traveler, Dollar Flight Club) — genuinely useful as a
  *trigger* to go look, since they surface mistake fares and flash sales the watch would miss
  between checks. Tier 3 as a price: verify on tier 1 before believing.
- **Award search tools** — helpful for finding award space across programs, but Delta's own site is
  the price of record.

## 5. Automated price APIs — don't build on one

There is no dependable free flight-price API to script against, and the skill deliberately doesn't
need one.

- **Amadeus Self-Service**, long the default free tier for flight-offer search and cheapest-date
  search, **shut down on 17 July 2026**; what remains is enterprise-only. Anything written against
  it is dead code.
- Skyscanner, Kiwi and Duffel are partner/commercial arrangements with approval and volume terms.
- Scraping Google Flights or an airline site violates their terms, breaks constantly, and gets the
  household's IP blocked.

So the architecture is deliberate: **a human-or-agent-driven sweep writes observations into the
ledger, and the script does the arithmetic and the deciding.** The judgment lives in code and the
data collection stays flexible. If a licensed API ever becomes available, it feeds the same ledger
and nothing else changes.

## 6. What to write down for each quote

Enough that the number can be reproduced and compared. The fields `fare_watch.py` reads:

| Field | Why it matters |
|---|---|
| `observed_on` | Freshness. A price is a fact about a day. |
| `carrier`, `carrier_type` | `carrier_type` decides which ancillary fees the model expects (`legacy` / `southwest` / `budget`). |
| `origin`, `destination` | Drives the ground-cost model for home airport vs hub. |
| `outbound_date`, `return_date` | Must be a pair from the grid, or `verify` flags it. |
| `outbound_depart_local` | Triggers the night-before hotel cost on early departures from a distant airport. |
| `stops` | A connection is a cost even when it isn't a dollar. |
| `fare_brand`, `basic_economy` | What the fare actually includes. |
| `changeable`, `refundable_24h` | Whether buying is reversible — this changes the recommendation. |
| `price_per_person` | Airfare including taxes. |
| `bag_fee_each_way`, `seat_fee_total` | The difference between a fare and a price. |
| `award.miles_per_person`, `award.cash_per_person` | Cents-per-mile math. Tier 1 only. |
| `seats_left` | A fare that can't seat the whole party is not an option. |
| `source` | Tier, name, URL. |
| `notes` | Anything the next reader would need — "sale ends Friday," "last row only." |

## 7. Sources

Read August 2026.

- [Google Flights](https://www.google.com/travel/flights)
- [Thrifty Traveler — How to use Google Flights](https://thriftytraveler.com/guides/google-flights/)
- [Going — Google Flights timing tricks](https://www.going.com/guides/best-time-to-book-with-google-flights)
- [Going — Google Flights price guarantee](https://www.going.com/guides/google-flights-price-guarantee)
- [Thrifty Traveler — Southwest fares now appear on Google Flights](https://thriftytraveler.com/guides/google-flights/southwest-fares-now-appear/)
- [Amadeus for Developers — Self-Service](https://developers.amadeus.com/pricing) (confirm current status before assuming any tier exists)
