# Booking windows — when the price is actually lowest

Everything in this file is a **prior**, not a prediction. It tells you where to point the watch and
when to stop waiting; the trip's own observed price history decides the rest. When the prior and the
watch disagree, the watch wins — it is about this route on these dates, and the prior is an average
over millions of itineraries that mostly aren't yours.

---

## 1. The shape of an airfare curve

Airfares are not a random walk and they are not a countdown. They are a **U with a long left arm and
a cliff on the right**:

- **Far out (roughly 6–11 months).** Only the airline's own opening inventory is loaded. Prices are
  set, not discovered — often mid-range and flat for weeks. Nothing to win here on domestic routes.
- **The descent (about 3 months to 6 weeks out).** Airlines start discounting to fill the plane.
  Fare sales cluster here. This is where the watch earns its keep.
- **The floor (roughly 6 weeks out for domestic).** The cheapest buckets are open and demand hasn't
  eaten them yet.
- **The cliff (inside 3 weeks).** Cheap buckets are gone; the remaining inventory is priced for
  business travelers who have no choice. Prices climb, and they climb faster the closer you get.
  **Waiting inside three weeks is not a strategy, it is a fine.**

The one thing everybody gets wrong: **last-minute is not cheap.** The airline would rather fly an
empty seat than teach the market that patience is rewarded.

## 2. The windows this skill uses

Days before departure. These are the `PROFILES` in `scripts/fare_watch.py`.

| Trip shape | Prime band | Low point | Book by | Why |
|---|---|---|---|---|
| Domestic, ordinary dates | 28–61 d | ~43 d | 21 d | Google Flights' own historical analysis puts the average low at ~43 days out with a cheap zone of 28–61 days. |
| Domestic, peak season (summer, spring break) | 45–90 d | ~60 d | 30 d | Leisure demand is heavy and undifferentiated, so the cheap buckets empty earlier than the average. |
| Domestic, Thanksgiving | 36–74 d | ~45 d | 30 d | Thanksgiving fares bottom around 6–7 weeks out; roughly early-to-mid October for a late-November trip. |
| Domestic, Christmas / New Year | 51–90 d | ~58 d | 35 d | Buy by about Halloween. Late-December fares rise hard and effectively never retreat. |
| International, ordinary dates | 60–180 d | ~90 d | 45 d | Much flatter curve — less to gain by waiting, much more to lose. |
| International, peak or holiday | 120–240 d | ~150 d | 75 d | The one case where genuinely early is genuinely cheaper, and where **seat inventory**, not price, is the binding constraint. |

`fare_watch.py` picks the profile automatically from the trip dates (Thanksgiving is computed as the
fourth Thursday, Memorial and Labor Day from the calendar, so it stays right in future years). Set
`"profile"` explicitly to override it.

**Re-verify these numbers annually.** They come from the published booking-window studies
(Google Flights' historical analysis, Expedia/ARC's annual Air Travel Outlook, Going, KAYAK,
NerdWallet) as read in **August 2026**. The studies get re-run each year and the bands move a few
days. They have never moved enough to change the shape of the advice.

## 3. Holiday dates change the problem, not just the price

This is the case the family hits most, and it breaks the ordinary model in three ways:

1. **The anchor cannot move.** You must be there on Thanksgiving Day, or for the wedding, or on the
   first day of the school break. Flexibility exists only in the *tails* — which day you fly out,
   which day you come home. Put the anchor in `dates.must_be_there` so the grid never proposes a
   trip that misses the thing the trip is for.
2. **Everyone else's tails are the same as yours.** The expensive days are not "around
   Thanksgiving," they are specific: the Wednesday before and the Sunday after are the two worst
   flying days of the American year. Moving the return from that Sunday to the Saturday before or
   the Monday/Tuesday after is frequently worth more than every other optimization combined.
3. **Flying on the holiday itself is cheap.** Thanksgiving morning, Christmas Day, New Year's Day —
   nobody wants them, so they're discounted. If the destination is family, arriving Thanksgiving
   morning may be perfectly fine and several hundred dollars cheaper.

School-break dates are the other hard anchor. Pull the real first/last day and break dates from
the schools' published calendars (or the school-calendar skill named in the config, if one is
installed) rather than assuming, and put the school days into `dates.blackout`.

## 4. Day-of-week: the real effect and the myth

- **Myth:** the day you *buy* matters ("book on Tuesday at 1 PM"). It doesn't, meaningfully. Airline
  pricing is continuous and automated. Don't build a plan around it.
- **Real:** the day you *fly* matters a lot. Tuesday, Wednesday and Saturday departures run
  materially cheaper — Monday-to-Wednesday travel prices roughly 13% under weekend travel. Friday
  and Sunday are the expensive ends of any trip.

So the flexibility that pays is on the **travel** dates, which is exactly what the date grid
enumerates.

## 5. Time-of-day flexibility, and what it really costs

The 6 AM departure is usually the cheapest of the day, and out of a hub two hours away it is the
most expensive thing on the page: a 5:50 AM departure there means either a 2:30 AM start from home
or a hotel night. `origin_costs.<airport>.prenight_if_departs_before` makes the model add that hotel
automatically so the comparison is honest.

Record time preferences in `dates.outbound_time` / `dates.return_time` — `depart_after`,
`arrive_by`, `max_stops`, `red_eye_ok`. They are constraints on the search, and `grid` prints them
alongside the date pairs so a sweep doesn't quietly return fares the family would never take.

Rules of thumb worth pricing rather than assuming:
- A connection saves money and costs 3–5 hours plus a missed-connection risk. With two kids and
  three checked bags on a holiday weekend, the nonstop is often worth its premium.
- The last flight of the day is cheap because if it cancels there is nothing behind it. On the
  outbound of a short trip, that's a day of the vacation.
- A red-eye home saves a hotel night and costs the next day.

## 6. Check cadence

Watching daily from eight months out is wasted effort and trains you to ignore the watch. The
cadence in `fare_watch.py`:

| Days out | Check every |
|---|---|
| 120 + | 14 days |
| 90–119 | 7 days |
| 45–89 | 3 days |
| 21–44 | 2 days |
| under 21 | daily |

`schedule` stops the checks at the book-by date, because after that the decision has been made.

## 7. What actually moves a specific fare

When today's price is odd, these are the usual causes — worth knowing before concluding the market
has moved:

- **A fare sale.** Airlines run them in waves, most often for travel 4–10 weeks out. This is the
  single biggest source of a real drop, and the reason the watch exists.
- **A competitor's new route.** When Breeze or Southwest adds a route, everyone's fares on it fall.
  New-service announcements at your home airport are a real signal.
- **Bucket exhaustion.** The price didn't rise; the cheap seats sold. This is a one-way door and the
  reason `seats_left` matters more than the trend line.
- **Schedule change.** Re-timed or re-equipped flights can reprice the whole day.
- **Your own searches.** Cookie-based price manipulation is largely a myth on airline sites, but
  incognito costs nothing if it makes the household feel better.

## 8. Sources

Read August 2026. Re-check annually — the studies are re-run each year.

- [Google Flights — cheapest-time-to-book insights](https://www.google.com/travel/flights) (the price-history and "cheapest time to book" panels are the primary source for the domestic bands)
- [Going — When is the best time to book a flight? (2026 data)](https://www.going.com/guides/the-best-time-to-book-a-cheap-flight)
- [Going — How far in advance should you book a flight? (2026)](https://www.going.com/guides/how-far-in-advance-can-you-book-a-flight)
- [NerdWallet — The best days to book a flight and when to fly](https://www.nerdwallet.com/travel/learn/best-days-book-flight-fly)
- [KAYAK — Best time to book a flight & cheapest days to fly](https://www.kayak.com/news/when-are-flights-cheapest/)
- [Thrifty Traveler — The best time to book flights](https://thriftytraveler.com/guides/best-time-to-book-flights/)
- [The Points Guy — Best time to book flights for cheap airfare in 2026](https://thepointsguy.com/airline/best-time-to-book-a-flight/)
- [Dollar Flight Club — When to book for summer breaks & holidays](https://dollarflightclub.com/articles/when-to-book-flights-summer-breaks-holidays/)
