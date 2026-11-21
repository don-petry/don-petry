#!/usr/bin/env python3
"""Decide *when* to buy the tickets, and *which* ticket is actually cheapest.

Airfare is the one trip cost that changes every day after you plan it and stops
changing the moment you pay. Both halves of that go wrong in predictable ways:

- **The timing.** The family watches a fare drift for weeks, waits for a drop that
  the data says was never coming, and buys inside three weeks at the worst price
  of the whole watch. Or the opposite: buys eleven months out on a holiday route
  because "early is cheaper", which for domestic flights it usually isn't.
- **The comparison.** The cheapest fare on the screen is compared against another
  cheapest fare on a screen, when what the household actually pays is airfare plus
  bags plus the seat fees to sit the kids next to a parent plus the drive to the
  hub airport plus eight days of parking plus the hotel night before a 6 AM
  departure. A $59 budget fare out of the hub can lose to a legacy carrier out of
  the home airport once all of that lands.
- **The dates.** A trip is rarely one date pair. It is a holiday anchor that cannot
  move (be there Thanksgiving Day) wrapped in tails that can (fly out Friday or
  Saturday, come home Sunday or Monday). Priced as one pair, the flexibility is
  invisible; priced as a grid, it is frequently worth several hundred dollars.

So this script holds one **fare watch ledger** per trip — the date plan, the party,
what each airport really costs to leave from, and every price quote observed over
time — and does the arithmetic mechanically: the date grid to shop, the all-in
normalised cost of each quote, where today's best price sits in its own history,
which phase of the booking window the trip is in, and therefore whether to buy
today or keep watching.

It never buys anything. The recommendation is for a human to act on.

Usage:
    python3 fare_watch.py grid     watch.json [--as-of DATE] [--limit N] [--json]
    python3 fare_watch.py verify   watch.json [--as-of DATE]
    python3 fare_watch.py report   watch.json [--as-of DATE] [--fresh-days N] [--json]
    python3 fare_watch.py schedule watch.json [--as-of DATE] [--json]

Ledger JSON (see reference/example-watch.json for a filled-in one):

    {
      "trip": "Example family - San Francisco, Thanksgiving 2026",
      "party": [{"name": "Parent A", "type": "adult"},
                {"name": "Child 1", "type": "child", "age": 12}],
      "seats_together": true,
      "checked_bags": 3,
      "profile": "auto",              # or domestic_standard / domestic_thanksgiving /
                                      # domestic_christmas / domestic_peak /
                                      # international / international_peak
      "dates": {
        "mode": "flexible",           # flexible | fixed
        "outbound": {"preferred": "2026-11-21", "flex_days": [0, 2]},
        "return":   {"preferred": "2026-11-28", "flex_days": 1},
        "nights": {"min": 5, "max": 8},
        "must_be_there": ["2026-11-26"],      # the holiday anchor - cannot flex
        "blackout": ["2026-11-30"],           # school day, work, wedding
        "outbound_time": {"depart_after": "07:00", "arrive_by": "22:00"},
        "return_time":   {"depart_after": "09:00", "arrive_by": "23:00"},
        "note": "Thanksgiving Day is fixed; the tails flex"
      },
      "route": {"destination": "SFO", "origins": ["HOME", "HUB"],   # your airports
                "destination_alternates": ["OAK", "SJC"]},
      "origin_costs": {
        "HOME": {"drive_minutes": 20, "drive_miles": 24, "parking_per_day": 12},
        "HUB":  {"drive_minutes": 150, "drive_miles": 300, "parking_per_day": 10,
                "prenight_hotel": 190, "prenight_if_departs_before": "09:00"}
      },
      "miles": {"program": "Delta SkyMiles", "balance": 190000, "min_cpm": 1.3},
      "target_price": 2600,           # all-in, whole party
      "walk_away_price": 3600,
      "quotes": [ ... ],              # see QUOTE_FIELDS below
      "purchased": null               # once bought, see `purchased` below
    }

Every quote is one priced option observed on one day:

    {
      "observed_on": "2026-09-14",
      "carrier": "Delta", "carrier_type": "legacy",   # legacy | southwest | budget
      "origin": "HOME", "destination": "SFO",
      "outbound_date": "2026-11-21", "return_date": "2026-11-28",
      "outbound_depart_local": "06:00",               # optional, drives prenight cost
      "stops": 1,
      "fare_brand": "Main Cabin", "basic_economy": false,
      "changeable": true, "refundable_24h": true,
      "price_per_person": 428.00,                     # airfare incl. taxes
      "bag_fee_each_way": 35.0,                       # per checked bag, per direction
      "seat_fee_total": 0.0,                          # to seat the party together
      "award": {"miles_per_person": 32000, "cash_per_person": 5.60},
      "seats_left": 4,
      "source": {"tier": 1, "name": "delta.com", "url": "https://..."}
    }

Source tiers (reference/price-sources.md):

    1  The airline's own booking page - the only place a fare is actually for sale,
       and the only acceptable source for a fare you are about to buy.
    2  Google Flights and other metasearch reading live inventory. Fine for sweeping
       a date grid and for tracking a trend; confirm on tier 1 before buying.
    3  Everything else - deal blogs, screenshots, "I saw $198 last week", memory.
       Useful as a lead, never as a price.
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Booking-window models
# ---------------------------------------------------------------------------
# Days before departure. `prime` is the band where the published studies put the
# low point for that trip shape; `sweet` is the middle of it; `book_by` is the
# day after which waiting has historically cost money rather than saved it.
# Sources and the reasoning behind each band: reference/booking-windows.md.


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    prime: tuple[int, int]
    sweet: int
    book_by: int
    watch_from: int
    note: str


PROFILES: dict[str, Profile] = {
    "domestic_standard": Profile(
        "domestic_standard", "Domestic, ordinary dates",
        prime=(28, 61), sweet=43, book_by=21, watch_from=120,
        note="Low point clusters ~6 weeks out; inside 3 weeks prices climb steadily.",
    ),
    "domestic_peak": Profile(
        "domestic_peak", "Domestic, peak season (summer / spring break)",
        prime=(45, 90), sweet=60, book_by=30, watch_from=180,
        note="Peak-season demand pulls the low point earlier and the cheap "
             "buckets sell out sooner than on ordinary dates.",
    ),
    "domestic_thanksgiving": Profile(
        "domestic_thanksgiving", "Domestic, Thanksgiving",
        prime=(36, 74), sweet=45, book_by=30, watch_from=180,
        note="Thanksgiving bottoms around 6-7 weeks out; the Sunday return is the "
             "single most expensive day of the year to fly.",
    ),
    "domestic_christmas": Profile(
        "domestic_christmas", "Domestic, Christmas / New Year",
        prime=(51, 90), sweet=58, book_by=35, watch_from=210,
        note="Buy by roughly Halloween for Christmas travel; late December fares "
             "rise hard and rarely retreat.",
    ),
    "international": Profile(
        "international", "International, ordinary dates",
        prime=(60, 180), sweet=90, book_by=45, watch_from=330,
        note="Wider, flatter band than domestic - there is far less to gain by "
             "waiting and far more to lose.",
    ),
    "international_peak": Profile(
        "international_peak", "International, peak season or holiday",
        prime=(120, 240), sweet=150, book_by=75, watch_from=330,
        note="Peak international is the one case where very early really is "
             "cheaper; seat inventory, not price alone, is the binding constraint.",
    ),
}

# A fare this far below the trip's own observed median is not a timing question.
EXCEPTIONAL_RATIO = 0.85
# Within this much of the cheapest price ever observed, "waiting for better" is noise.
AT_THE_LOW_RATIO = 1.02
# Above this, today's price is high enough for its own history to argue for waiting.
RUNNING_HIGH_RATIO = 1.15

# How old a quote may be and still count as "the price today".
DEFAULT_FRESH_DAYS = 3

# How often to re-check, by how far out the trip is. Pairs (days_out_at_least, every_n_days).
CADENCE = ((120, 14), (90, 7), (45, 3), (21, 2), (0, 1))

# IRS-style all-in driving cost per mile - fuel plus depreciation, tyres and the
# maintenance the miles bring forward. The honest economic cost of a drive.
DRIVE_COST_PER_MILE = 0.67
# What the household actually feels at the pump. Quote alongside the all-in figure.
DEFAULT_MPG = 24.0
DEFAULT_GAS_PRICE = 2.95

CARRIER_TYPES = ("legacy", "southwest", "budget")
PARTY_TYPES = ("adult", "child", "infant")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class FareWatchError(ValueError):
    """Raised when a watch ledger is internally inconsistent or under-specified."""


# ---------------------------------------------------------------------------
# Holiday detection - "we sometimes book travel around holidays"
# ---------------------------------------------------------------------------


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th `weekday` (Mon=0) of a month; n=-1 means the last one."""
    days = [
        date(year, month, d)
        for d in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, d).weekday() == weekday
    ]
    return days[n - 1] if n > 0 else days[n]


def holiday_periods(year: int) -> list[tuple[str, date, date, str]]:
    """(key, start, end, label) for the US travel peaks that reshape airfare."""
    thanksgiving = _nth_weekday(year, 11, 3, 4)  # 4th Thursday
    memorial = _nth_weekday(year, 5, 0, -1)      # last Monday
    labor = _nth_weekday(year, 9, 0, 1)          # 1st Monday
    return [
        ("domestic_christmas", date(year, 12, 17), date(year + 1, 1, 4),
         "Christmas / New Year"),
        ("domestic_christmas", date(year, 1, 1), date(year, 1, 4),
         "New Year return period"),
        ("domestic_thanksgiving", thanksgiving - timedelta(days=7),
         thanksgiving + timedelta(days=5), "Thanksgiving"),
        ("domestic_peak", date(year, 3, 8), date(year, 4, 12), "Spring break"),
        ("domestic_peak", date(year, 6, 1), date(year, 8, 15), "Summer peak"),
        ("domestic_peak", memorial - timedelta(days=4), memorial + timedelta(days=1),
         "Memorial Day weekend"),
        ("domestic_peak", date(year, 7, 1), date(year, 7, 7), "July 4th"),
        ("domestic_peak", labor - timedelta(days=4), labor + timedelta(days=1),
         "Labor Day weekend"),
    ]


def detect_holidays(start: date, end: date) -> list[tuple[str, str]]:
    """Every holiday/peak period the trip touches, most disruptive first."""
    hits: list[tuple[str, str]] = []
    for year in range(start.year - 1, end.year + 1):
        for key, h_start, h_end, label in holiday_periods(year):
            if start <= h_end and end >= h_start:
                if (key, label) not in hits:
                    hits.append((key, label))
    rank = {"domestic_christmas": 0, "domestic_thanksgiving": 1, "domestic_peak": 2}
    return sorted(hits, key=lambda pair: rank.get(pair[0], 9))


def resolve_profile(ledger: "Ledger") -> tuple[Profile, list[str]]:
    """The booking-window model for this trip, plus why it was chosen."""
    holidays = detect_holidays(ledger.span_start, ledger.span_end)
    labels = [label for _, label in holidays]

    declared = (ledger.raw.get("profile") or "auto").strip()
    if declared and declared != "auto":
        if declared not in PROFILES:
            raise FareWatchError(
                f"unknown profile {declared!r} - choose from {', '.join(PROFILES)} or 'auto'"
            )
        why = [f"profile set explicitly to {declared}"]
        if labels:
            why.append("trip overlaps " + ", ".join(labels))
        return PROFILES[declared], why

    if ledger.international:
        key = "international_peak" if holidays else "international"
    elif holidays:
        key = holidays[0][0]
    else:
        key = "domestic_standard"
    why = [f"auto-detected: {PROFILES[key].label}"]
    if labels:
        why.append("trip overlaps " + ", ".join(labels))
    return PROFILES[key], why


# ---------------------------------------------------------------------------
# The date plan - precise when the dates are locked, fuzzy when they aren't
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    outbound: date
    inbound: date
    preferred: bool

    @property
    def nights(self) -> int:
        return (self.inbound - self.outbound).days

    def label(self) -> str:
        star = " *preferred" if self.preferred else ""
        return (
            f"{self.outbound:%a %b %-d} -> {self.inbound:%a %b %-d} "
            f"({self.nights} nights){star}"
        )


def _as_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise FareWatchError(f"{label} {value!r} is not a date (YYYY-MM-DD)") from exc


def _flex(spec: dict, label: str) -> tuple[date, date, date]:
    """(earliest, preferred, latest) for one end of the trip.

    Accepts an explicit earliest/latest window, or a preferred date with
    `flex_days` - either a single number (symmetric) or [before, after].
    A missing/zero flex means the date is precise.
    """
    preferred = spec.get("preferred") or spec.get("date")
    earliest = spec.get("earliest")
    latest = spec.get("latest")

    if preferred:
        pref = _as_date(preferred, f"{label}.preferred")
    elif earliest:
        pref = _as_date(earliest, f"{label}.earliest")
    else:
        raise FareWatchError(f"{label} needs a 'preferred' or 'earliest' date")

    flex = spec.get("flex_days", 0)
    if isinstance(flex, (list, tuple)):
        if len(flex) != 2:
            raise FareWatchError(f"{label}.flex_days list must be [before, after]")
        before, after = int(flex[0]), int(flex[1])
    else:
        before = after = int(flex)
    if before < 0 or after < 0:
        raise FareWatchError(f"{label}.flex_days cannot be negative")

    low = _as_date(earliest, f"{label}.earliest") if earliest else pref - timedelta(days=before)
    high = _as_date(latest, f"{label}.latest") if latest else pref + timedelta(days=after)
    if high < low:
        raise FareWatchError(f"{label} window ends ({high}) before it starts ({low})")
    if not low <= pref <= high:
        pref = low
    return low, pref, high


class DatePlan:
    """Both ends of the trip, their flexibility, and the anchors that cannot move."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.fixed = (raw.get("mode") or "flexible").lower() == "fixed"
        if "outbound" not in raw:
            raise FareWatchError("dates.outbound is required")
        self.ob_low, self.ob_pref, self.ob_high = _flex(raw["outbound"], "dates.outbound")

        nights = raw.get("nights") or {}
        self.nights_min = int(nights["min"]) if "min" in nights else None
        self.nights_max = int(nights["max"]) if "max" in nights else None

        if raw.get("return"):
            self.rt_low, self.rt_pref, self.rt_high = _flex(raw["return"], "dates.return")
        elif self.nights_min is not None and self.nights_max is not None:
            self.rt_low = self.ob_low + timedelta(days=self.nights_min)
            self.rt_high = self.ob_high + timedelta(days=self.nights_max)
            self.rt_pref = self.ob_pref + timedelta(days=self.nights_min)
        else:
            raise FareWatchError(
                "dates needs either a 'return' window or 'nights' {min, max}"
            )

        if self.fixed:
            self.ob_low = self.ob_high = self.ob_pref
            self.rt_low = self.rt_high = self.rt_pref

        self.must_be_there = [
            _as_date(d, "dates.must_be_there") for d in raw.get("must_be_there", [])
        ]
        self.blackout = [_as_date(d, "dates.blackout") for d in raw.get("blackout", [])]
        for key in ("outbound_time", "return_time"):
            for bound in ("depart_after", "arrive_by", "depart_before"):
                value = (raw.get(key) or {}).get(bound)
                if value and not TIME_RE.match(value):
                    raise FareWatchError(f"dates.{key}.{bound} {value!r} must be HH:MM")

        if self.nights_min is not None and self.nights_max is not None:
            if self.nights_max < self.nights_min:
                raise FareWatchError("dates.nights.max is less than dates.nights.min")

    @property
    def precise(self) -> bool:
        return self.ob_low == self.ob_high and self.rt_low == self.rt_high

    def grid(self, as_of: date | None = None) -> list[Pair]:
        """Every date pair worth pricing, honouring the anchors and blackouts."""
        pairs: list[Pair] = []
        ob = self.ob_low
        while ob <= self.ob_high:
            if ob in self.blackout or (as_of and ob < as_of):
                ob += timedelta(days=1)
                continue
            rt = self.rt_low
            while rt <= self.rt_high:
                if rt in self.blackout or rt <= ob:
                    rt += timedelta(days=1)
                    continue
                nights = (rt - ob).days
                if self.nights_min is not None and nights < self.nights_min:
                    rt += timedelta(days=1)
                    continue
                if self.nights_max is not None and nights > self.nights_max:
                    rt += timedelta(days=1)
                    continue
                if all(ob <= anchor <= rt for anchor in self.must_be_there):
                    pairs.append(Pair(ob, rt, ob == self.ob_pref and rt == self.rt_pref))
                rt += timedelta(days=1)
            ob += timedelta(days=1)
        return pairs

    def time_rules(self) -> list[str]:
        out = []
        for key, leg in (("outbound_time", "Outbound"), ("return_time", "Return")):
            spec = self.raw.get(key) or {}
            bits = []
            if spec.get("depart_after"):
                bits.append(f"departs no earlier than {spec['depart_after']}")
            if spec.get("depart_before"):
                bits.append(f"departs no later than {spec['depart_before']}")
            if spec.get("arrive_by"):
                bits.append(f"lands by {spec['arrive_by']}")
            if spec.get("red_eye_ok") is False:
                bits.append("no red-eyes")
            if spec.get("max_stops") is not None:
                bits.append(f"max {spec['max_stops']} stop(s)")
            if bits:
                out.append(f"{leg}: " + ", ".join(bits))
        return out


# ---------------------------------------------------------------------------
# Quotes and the all-in cost model
# ---------------------------------------------------------------------------


@dataclass
class Quote:
    observed_on: date
    carrier: str
    carrier_type: str
    origin: str
    destination: str
    outbound_date: date
    return_date: date
    price_per_person: float
    raw: dict = field(default_factory=dict)
    stops: int | None = None
    fare_brand: str = ""
    basic_economy: bool = False
    changeable: bool = False
    refundable_24h: bool = True
    bag_fee_each_way: float = 0.0
    seat_fee_total: float = 0.0
    outbound_depart_local: str = ""
    seats_left: int | None = None
    award_miles_per_person: int = 0
    award_cash_per_person: float = 0.0
    source_tier: int = 3
    source_name: str = ""
    source_url: str = ""
    notes: str = ""

    @property
    def is_award(self) -> bool:
        return self.award_miles_per_person > 0

    @property
    def option_key(self) -> str:
        kind = "award" if self.is_award else "cash"
        return (
            f"{self.carrier}|{self.origin}->{self.destination}|"
            f"{self.outbound_date}|{self.return_date}|{self.fare_brand or '-'}|{kind}"
        )

    def label(self) -> str:
        award = f" ({self.award_miles_per_person:,} mi pp)" if self.is_award else ""
        brand = f" {self.fare_brand}" if self.fare_brand else ""
        stops = "nonstop" if self.stops == 0 else (
            f"{self.stops} stop" if self.stops == 1 else
            f"{self.stops} stops" if self.stops else "stops n/k"
        )
        return (
            f"{self.carrier}{brand}{award} {self.origin}->{self.destination} "
            f"{self.outbound_date:%b %-d}/{self.return_date:%b %-d}, {stops}"
        )


def load_quote(record: dict) -> Quote:
    for field_name in ("observed_on", "carrier", "origin", "destination",
                       "outbound_date", "return_date"):
        if not record.get(field_name):
            raise FareWatchError(f"quote is missing {field_name!r}")
    source = record.get("source") or {}
    if not source.get("name"):
        raise FareWatchError(
            f"{record['carrier']} quote observed {record['observed_on']}: no source. "
            "Every price must say where it was read - a price with no source is a "
            "memory, and memories of airfare are wrong."
        )
    award = record.get("award") or {}
    quote = Quote(
        observed_on=_as_date(record["observed_on"], "quote.observed_on"),
        carrier=record["carrier"],
        carrier_type=(record.get("carrier_type") or "legacy").lower(),
        origin=record["origin"].upper(),
        destination=record["destination"].upper(),
        outbound_date=_as_date(record["outbound_date"], "quote.outbound_date"),
        return_date=_as_date(record["return_date"], "quote.return_date"),
        price_per_person=float(record.get("price_per_person") or 0.0),
        raw=record,
        stops=record.get("stops"),
        fare_brand=record.get("fare_brand", ""),
        basic_economy=bool(record.get("basic_economy", False)),
        changeable=bool(record.get("changeable", False)),
        refundable_24h=bool(record.get("refundable_24h", True)),
        bag_fee_each_way=float(record.get("bag_fee_each_way") or 0.0),
        seat_fee_total=float(record.get("seat_fee_total") or 0.0),
        outbound_depart_local=record.get("outbound_depart_local", ""),
        seats_left=record.get("seats_left"),
        award_miles_per_person=int(award.get("miles_per_person") or 0),
        award_cash_per_person=float(award.get("cash_per_person") or 0.0),
        source_tier=int(source.get("tier") or 3),
        source_name=source["name"],
        source_url=source.get("url", ""),
        notes=record.get("notes", ""),
    )
    if quote.carrier_type not in CARRIER_TYPES:
        raise FareWatchError(
            f"{quote.carrier}: carrier_type {quote.carrier_type!r} must be one of "
            f"{', '.join(CARRIER_TYPES)} - it decides which fees the model adds"
        )
    if quote.return_date <= quote.outbound_date:
        raise FareWatchError(f"{quote.label()}: return is not after the outbound")
    if quote.outbound_depart_local and not TIME_RE.match(quote.outbound_depart_local):
        raise FareWatchError(
            f"{quote.label()}: outbound_depart_local must be HH:MM local"
        )
    if not quote.is_award and quote.price_per_person <= 0:
        raise FareWatchError(f"{quote.label()}: cash quote needs a price_per_person")
    return quote


@dataclass
class DriveLeg:
    origin: str
    destination: str
    miles: float
    hours: float
    overnight_where: str = ""
    overnight_cost: float = 0.0


@dataclass
class DriveOption:
    """Driving, priced the same way flying is: cash AND hours, both stated.

    The mistake this exists to prevent is comparing a fare against a tank of gas.
    A drive has three costs and only one of them is fuel: the car (fuel, wear, the
    IRS-style all-in rate), the overnights and meals, and the driver's hours - and
    for a drop-off trip the car covers the route far more times than the travelers
    do. Two teenagers riding down and back is two traversals; the adult who takes
    them and comes home, then goes again to collect them, drives four.
    """

    id: str
    label: str
    legs: list[DriveLeg]
    traversals: int = 4
    traveler_traversals: int = 2
    cost_per_mile: float = DRIVE_COST_PER_MILE
    extra_per_traversal: float = 0.0
    notes: str = ""
    mpg: float = DEFAULT_MPG
    gas_price: float = DEFAULT_GAS_PRICE
    driven_by: str = "adult"
    vehicles: int = 1
    vehicle: str = ""

    @property
    def fuel_per_mile(self) -> float:
        return self.gas_price / self.mpg if self.mpg else 0.0

    @property
    def fuel_total(self) -> float:
        """What actually leaves the bank account: petrol, plus overnights and food.

        The all-in rate is the honest economic cost - it books depreciation, tyres and
        the maintenance the miles bring forward. But a household compares a fare
        against what it *feels*, which is the pump. Quote both, or the comparison gets
        argued with rather than used.
        """
        return (
            self.miles_one_way * self.fuel_per_mile * self.vehicles
            + self.overnight_cost_one_way
            + self.extra_per_traversal
        ) * self.traversals

    @property
    def miles_one_way(self) -> float:
        return sum(leg.miles for leg in self.legs)

    @property
    def hours_one_way(self) -> float:
        return sum(leg.hours for leg in self.legs)

    @property
    def overnight_cost_one_way(self) -> float:
        return sum(leg.overnight_cost for leg in self.legs)

    @property
    def cash_per_traversal(self) -> float:
        return (
            self.miles_one_way * self.cost_per_mile * self.vehicles
            + self.overnight_cost_one_way
            + self.extra_per_traversal
        )

    @property
    def cash_total(self) -> float:
        return self.cash_per_traversal * self.traversals

    @property
    def self_driven(self) -> bool:
        return self.driven_by == "travelers"

    @property
    def adult_hours(self) -> float:
        """Hours of a driving adult's life. Zero when the travelers drive themselves.

        This is usually the deciding term, so who holds the wheel changes the answer
        more than any fare does: a drop-off costs an adult four traversals, and the
        same trip driven by the travelers costs an adult none.
        """
        return 0.0 if self.self_driven else self.hours_one_way * self.traversals

    @property
    def traveler_hours(self) -> float:
        return self.hours_one_way * self.traveler_traversals

    @property
    def complete(self) -> bool:
        """Does this option get the travelers there AND back by road?

        An option where they ride the route once is a hybrid - drive down, fly home -
        and its cash figure is only half the journey. It must never set the bar a
        fare has to beat, or the comparison silently comes up short by the price of
        two one-way tickets.
        """
        return self.traveler_traversals >= 2

    @property
    def overnights(self) -> list[str]:
        return [
            f"{leg.overnight_where} ({money(leg.overnight_cost)})"
            for leg in self.legs
            if leg.overnight_where
        ]


def load_drive_option(record: dict) -> DriveOption:
    if not record.get("id") or not record.get("label"):
        raise FareWatchError("drive option needs an 'id' and a 'label'")
    legs = []
    for raw in record.get("legs", []):
        miles = float(raw.get("miles") or 0)
        hours = float(raw.get("hours") or 0)
        if miles <= 0 or hours <= 0:
            raise FareWatchError(
                f"{record['id']}: every drive leg needs positive miles and hours - "
                "a leg with no time in it is how driving wins comparisons it shouldn't"
            )
        overnight = raw.get("overnight") or {}
        legs.append(DriveLeg(
            origin=raw.get("from", ""),
            destination=raw.get("to", ""),
            miles=miles,
            hours=hours,
            overnight_where=overnight.get("where", ""),
            overnight_cost=float(overnight.get("cost") or 0.0),
        ))
    if not legs:
        raise FareWatchError(f"{record['id']}: drive option has no legs")

    option = DriveOption(
        id=record["id"],
        label=record["label"],
        legs=legs,
        traversals=int(record.get("traversals", 4)),
        traveler_traversals=int(record.get("traveler_traversals", 2)),
        cost_per_mile=float(record.get("cost_per_mile", DRIVE_COST_PER_MILE)),
        extra_per_traversal=float(record.get("extra_per_traversal") or 0.0),
        notes=record.get("notes", ""),
        mpg=float((record.get("fuel") or {}).get("mpg", DEFAULT_MPG)),
        gas_price=float((record.get("fuel") or {}).get("gas_price", DEFAULT_GAS_PRICE)),
        driven_by=(record.get("driven_by") or "adult").lower(),
        vehicles=int(record.get("vehicles", 1)),
        vehicle=record.get("vehicle", ""),
    )
    if option.driven_by not in ("adult", "travelers"):
        raise FareWatchError(
            f"{option.id}: driven_by must be 'adult' or 'travelers' - it decides "
            "whether the hours land on an adult or on the travelers, which is "
            "usually what settles drive-vs-fly"
        )
    if option.self_driven and option.traversals != option.traveler_traversals:
        raise FareWatchError(
            f"{option.id}: the travelers drive themselves, so the car makes exactly "
            f"the trips they do - traversals ({option.traversals}) must equal "
            f"traveler_traversals ({option.traveler_traversals})"
        )
    if option.vehicles < 1:
        raise FareWatchError(f"{option.id}: vehicles must be at least 1")
    if option.traveler_traversals > option.traversals:
        raise FareWatchError(
            f"{option.id}: travelers ride the route {option.traveler_traversals} "
            f"times but the car only covers it {option.traversals} times"
        )
    return option


@dataclass
class Costed:
    quote: Quote
    airfare: float
    bags: float
    seats: float
    ground: float
    ground_detail: str
    total: float
    miles: int
    quote_party: int = 1
    eligible: bool = True
    ineligible_reason: str = ""

    @property
    def per_person(self) -> float:
        return self.total / max(self.quote_party, 1)

    def headline(self) -> str:
        if self.miles:
            return f"{self.miles:,} miles + {money(self.total)}"
        return money(self.total)


class Ledger:
    def __init__(self, raw: dict, path: str = ""):
        self.raw = raw
        self.path = path
        self.trip = raw.get("trip") or "(unnamed trip)"
        self.party = raw.get("party") or []
        if not self.party:
            raise FareWatchError(
                "party is required - bag fees, seat fees and award miles are all "
                "per-traveler, so a watch with no party prices nothing correctly"
            )
        for member in self.party:
            kind = (member.get("type") or "adult").lower()
            if kind not in PARTY_TYPES:
                raise FareWatchError(
                    f"party member {member.get('name', '?')}: type {kind!r} must be "
                    f"one of {', '.join(PARTY_TYPES)}"
                )
        self.seats = sum(
            1 for m in self.party if (m.get("type") or "adult").lower() != "infant"
        )
        self.children = [
            m for m in self.party if (m.get("type") or "adult").lower() == "child"
        ]
        self.seats_together = bool(raw.get("seats_together", bool(self.children)))
        self.checked_bags = int(raw.get("checked_bags") or 0)
        self.dates = DatePlan(raw.get("dates") or {})
        route = raw.get("route") or {}
        self.destination = (route.get("destination") or "").upper()
        self.origins = [o.upper() for o in route.get("origins", [])]
        self.international = bool(route.get("international", False))
        self.origin_costs = {k.upper(): v for k, v in (raw.get("origin_costs") or {}).items()}
        self.miles_cfg = raw.get("miles") or {}
        self.target_price = raw.get("target_price")
        self.walk_away_price = raw.get("walk_away_price")
        self.quotes = [load_quote(q) for q in raw.get("quotes", [])]
        self.drive_options = [load_drive_option(d) for d in raw.get("drive_options", [])]
        self.purchased = raw.get("purchased") or None

    def flying_adult_hours(self, origin: str) -> float:
        """Hours an adult spends driving to and from the airport for a drop-off trip.

        Two round trips: one to hand them over, one to collect them.
        """
        spec = self.origin_costs.get(origin.upper()) or {}
        minutes = float(spec.get("drive_minutes") or 0.0)
        return minutes * 4 / 60.0

    @property
    def span_start(self) -> date:
        return self.dates.ob_low

    @property
    def span_end(self) -> date:
        return self.dates.rt_high

    def trip_days(self, quote: Quote) -> int:
        """Days a car would sit in the lot - the outbound and return days included."""
        return (quote.return_date - quote.outbound_date).days + 1

    def cost(self, quote: Quote) -> Costed:
        """All-in cost for the whole party: the number the family actually pays."""
        if quote.is_award:
            airfare = quote.award_cash_per_person * self.seats
        else:
            airfare = quote.price_per_person * self.seats
        bags = quote.bag_fee_each_way * self.checked_bags * 2
        seats = quote.seat_fee_total

        ground = 0.0
        details: list[str] = []
        spec = self.origin_costs.get(quote.origin) or {}
        days = self.trip_days(quote)
        parking = float(spec.get("parking_per_day") or 0.0) * days
        if parking:
            ground += parking
            details.append(f"{days}d parking ${parking:,.0f}")
        drive_miles = float(spec.get("drive_miles") or 0.0)
        if drive_miles:
            drive = drive_miles * float(spec.get("cost_per_mile", DRIVE_COST_PER_MILE))
            ground += drive
            details.append(f"{drive_miles:.0f} mi drive ${drive:,.0f}")
        hotel = float(spec.get("prenight_hotel") or 0.0)
        threshold = spec.get("prenight_if_departs_before")
        if hotel and threshold and quote.outbound_depart_local:
            if quote.outbound_depart_local < threshold:
                ground += hotel
                details.append(
                    f"night before (departs {quote.outbound_depart_local}) ${hotel:,.0f}"
                )
        for extra in spec.get("extras", []):
            ground += float(extra.get("amount") or 0.0)
            details.append(f"{extra.get('label', 'extra')} ${float(extra['amount']):,.0f}")

        eligible, reason = self.eligibility(quote)
        return Costed(
            quote=quote,
            airfare=airfare,
            bags=bags,
            seats=seats,
            ground=ground,
            ground_detail=", ".join(details) or "-",
            total=airfare + bags + seats + ground,
            miles=quote.award_miles_per_person * self.seats,
            quote_party=self.seats,
            eligible=eligible,
            ineligible_reason=reason,
        )

    def eligibility(self, quote: Quote) -> tuple[bool, str]:
        """Can this option actually be bought, by this party, as priced?

        An option that fails here still gets displayed - seeing the $119 fare and
        why it isn't real is the whole point - but it is kept out of the "best
        price", the price history, and the buy recommendation. Recommending a fare
        with three seats left to a family of four is worse than recommending
        nothing.
        """
        if quote.seats_left is not None and quote.seats_left < self.seats:
            return False, (
                f"only {quote.seats_left} seat(s) left at this fare; the party needs "
                f"{self.seats}"
            )
        if quote.is_award:
            balance = int(self.miles_cfg.get("balance") or 0)
            need = quote.award_miles_per_person * self.seats
            if balance and need > balance:
                return False, (
                    f"needs {need:,} miles, balance on file is {balance:,}"
                )
        if quote.basic_economy and self.seats_together and not quote.seat_fee_total:
            return False, (
                "basic economy with no seat fee priced in - the party cannot be seated "
                "together at this number, so it isn't comparable to the other fares"
            )
        if quote.source_tier >= 3:
            return False, (
                f"tier-{quote.source_tier} source ({quote.source_name}) - a price that "
                "wasn't read off a booking page is a lead, not a fare"
            )
        return True, ""


def load(path: str) -> Ledger:
    with open(path, encoding="utf-8") as handle:
        return Ledger(json.load(handle), path)


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------


@dataclass
class Decision:
    action: str
    headline: str
    phase: str
    days_out: int
    profile: Profile
    reasons: list[str]
    warnings: list[str]
    next_check: date
    best: Costed | None
    best_cash: Costed | None
    best_award: Costed | None
    cpm: float | None
    stats: dict
    stale: bool


def latest_per_option(items) -> list[Costed]:
    """One row per bookable option - its most recent observation.

    A price checked five days running is one option, not five. Left un-deduped it
    would crowd the comparison and quietly weight the median toward whatever got
    re-checked most often.
    """
    newest: dict[str, Costed] = {}
    for costed in items:
        key = costed.quote.option_key
        if key not in newest or costed.quote.observed_on >= newest[key].quote.observed_on:
            newest[key] = costed
    return list(newest.values())


def cadence_days(days_out: int) -> int:
    for threshold, every in CADENCE:
        if days_out >= threshold:
            return every
    return 1


def phase_of(days_out: int, profile: Profile) -> str:
    if days_out > profile.watch_from:
        return "dormant"
    if days_out > profile.prime[1]:
        return "too_early"
    if days_out >= profile.prime[0]:
        return "prime"
    if days_out >= profile.book_by:
        return "closing"
    if days_out >= 0:
        return "late"
    return "departed"


PHASE_LABEL = {
    "dormant": "Too far out to shop meaningfully",
    "too_early": "Before the buying window",
    "prime": "In the buying window",
    "closing": "Buying window closing",
    "late": "Past the point where waiting pays",
    "departed": "Departure date has passed",
}


def analyse(ledger: Ledger, as_of: date, fresh_days: int = DEFAULT_FRESH_DAYS) -> Decision:
    profile, profile_why = resolve_profile(ledger)
    depart = ledger.dates.ob_pref
    days_out = (depart - as_of).days
    phase = phase_of(days_out, profile)
    reasons = list(profile_why)
    warnings: list[str] = []

    costed = [ledger.cost(q) for q in ledger.quotes]
    fresh = latest_per_option(
        c for c in costed if 0 <= (as_of - c.quote.observed_on).days <= fresh_days
    )
    cash_all = [c for c in costed if not c.quote.is_award and c.eligible]
    cash_fresh = [c for c in fresh if not c.quote.is_award and c.eligible]
    award_fresh = [c for c in fresh if c.quote.is_award and c.eligible]
    excluded = [c for c in fresh if not c.eligible]

    best_cash = min(cash_fresh, key=lambda c: c.total) if cash_fresh else None
    best_award = min(award_fresh, key=lambda c: c.total) if award_fresh else None
    best = best_cash

    stats: dict = {}
    if cash_all:
        totals = [c.total for c in cash_all]
        stats["observations"] = len(totals)
        stats["min"] = min(totals)
        stats["median"] = statistics.median(totals)
        stats["max"] = max(totals)
        low_quote = min(cash_all, key=lambda c: c.total)
        stats["low_seen_on"] = low_quote.quote.observed_on.isoformat()
        stats["days_watched"] = (
            max(c.quote.observed_on for c in cash_all)
            - min(c.quote.observed_on for c in cash_all)
        ).days
        if best_cash:
            stats["index_vs_median"] = best_cash.total / stats["median"]
            stats["index_vs_low"] = best_cash.total / stats["min"]

    last_check = max((c.quote.observed_on for c in costed), default=None)
    every = cadence_days(max(days_out, 0))
    stale = last_check is None or (as_of - last_check).days > every
    next_check = as_of + timedelta(days=every) if not stale else as_of

    # ---- trend on the option we would actually buy -------------------------
    trend = None
    if best_cash:
        series = sorted(
            (c for c in cash_all if c.quote.option_key == best_cash.quote.option_key),
            key=lambda c: c.quote.observed_on,
        )
        if len(series) >= 3:
            recent = [c.total for c in series[-3:]]
            if recent[0] < recent[1] < recent[2]:
                trend = "rising"
            elif recent[0] > recent[1] > recent[2]:
                trend = "falling"
            else:
                trend = "flat"

    # ---- warnings ----------------------------------------------------------
    if not ledger.quotes:
        warnings.append("No prices logged yet - nothing to recommend until the grid is shopped.")
    if stale and ledger.quotes:
        warnings.append(
            f"Last price check was {last_check} ({(as_of - last_check).days}d ago); at "
            f"{days_out} days out this watch should be checked every {every} day(s). "
            "The recommendation below is built on stale prices."
        )
    for dropped in excluded:
        warnings.append(
            f"Excluded from the comparison - {dropped.quote.label()} at "
            f"{dropped.headline()}: {dropped.ineligible_reason}."
        )
    if best_cash and best_cash.quote.basic_economy:
        warnings.append(
            "Cheapest eligible fare is basic economy: no changes, last boarding group, "
            "and seat assignments only because they were paid for. Price the next fare "
            "up before treating this as the winner - the gap is often small."
        )
    if best_cash and best_cash.quote.seats_left is not None:
        if best_cash.quote.seats_left <= ledger.seats + 2:
            warnings.append(
                f"Only {best_cash.quote.seats_left} seat(s) left at this fare for a party "
                f"of {ledger.seats} - this price can move while the booking is in progress."
            )
    for costed_quote in fresh:
        if costed_quote.quote.carrier_type == "budget" and not costed_quote.quote.bag_fee_each_way:
            warnings.append(
                f"{costed_quote.quote.carrier}: no bag fee recorded for a budget carrier. "
                "Their carry-on and checked-bag fees are the fare - price them in or the "
                "comparison is fiction."
            )
    if ledger.dates.must_be_there:
        anchors = ", ".join(a.isoformat() for a in ledger.dates.must_be_there)
        reasons.append(f"Holiday/anchor dates that cannot move: {anchors}")

    # ---- miles vs cash -----------------------------------------------------
    cpm = None
    if best_award and best_award.miles:
        comparable = None
        same = [
            c for c in cash_fresh
            if c.quote.origin == best_award.quote.origin
            and c.quote.outbound_date == best_award.quote.outbound_date
            and c.quote.return_date == best_award.quote.return_date
        ]
        comparable = min(same, key=lambda c: c.total) if same else best_cash
        if comparable:
            cpm = (comparable.total - best_award.total) / best_award.miles * 100

    # ---- the call ----------------------------------------------------------
    action = "WATCH"
    headline = "Keep watching."

    if phase == "departed":
        action, headline = "EXPIRED", "The preferred departure date has passed."
    elif ledger.purchased:
        action, headline = _post_purchase(ledger, as_of, best_cash, reasons, warnings)
    elif not best_cash and not best_award:
        action = "SHOP"
        headline = (
            "No fresh prices. Shop the date grid before any timing question can be answered."
        )
    else:
        current = best_cash or best_award
        target = ledger.target_price
        index_median = stats.get("index_vs_median")
        index_low = stats.get("index_vs_low")
        enough_history = stats.get("observations", 0) >= 3 and stats.get("days_watched", 0) >= 7

        hit_target = target is not None and current.total <= float(target)
        # "Cheapest so far" over two days of watching is not evidence of anything.
        exceptional = (
            enough_history and index_median is not None and index_median <= EXCEPTIONAL_RATIO
        )
        at_the_low = index_low is not None and index_low <= AT_THE_LOW_RATIO
        running_high = index_median is not None and index_median >= RUNNING_HIGH_RATIO

        if phase == "late":
            action = "BUY NOW"
            headline = (
                f"{days_out} days out - past {profile.label.lower()}'s book-by point "
                f"({profile.book_by}d). Waiting has cost money from here, not saved it."
            )
        elif hit_target:
            action = "BUY"
            headline = f"Hit the target price (${float(target):,.0f} all-in) - take it."
        elif exceptional:
            action = "BUY"
            headline = (
                f"${current.total:,.0f} is {(1 - index_median) * 100:.0f}% under this "
                "trip's own median. An outlier this good is not a timing question."
            )
        elif phase == "closing":
            if running_high and not at_the_low:
                action = "WATCH CLOSELY"
                headline = (
                    "In the closing window but today's price is running high against its "
                    "own history - check daily and buy on any drop, or by the book-by date "
                    f"({(depart - timedelta(days=profile.book_by)):%b %-d}) regardless."
                )
            else:
                action = "BUY"
                headline = (
                    f"{days_out} days out, inside the closing window - the remaining "
                    "downside is smaller than the risk of the fare moving up."
                )
        elif phase == "prime":
            if at_the_low or trend == "rising":
                action = "BUY"
                headline = (
                    "In the buying window and "
                    + ("at the lowest price seen on this watch."
                       if at_the_low else "the price has risen three checks running.")
                )
            elif not enough_history:
                action = "WATCH CLOSELY"
                headline = (
                    "In the buying window but with too little price history to know a "
                    "good fare from a bad one - check daily for a week, then decide."
                )
            else:
                action = "WATCH CLOSELY"
                headline = (
                    "In the buying window with today's price above its own low - check "
                    "daily and buy on the next drop."
                )
        elif phase in ("too_early", "dormant"):
            action = "WATCH"
            headline = (
                f"{days_out} days out; the low point for {profile.label.lower()} sits "
                f"around {profile.sweet} days ({profile.prime[0]}-{profile.prime[1]}d). "
                "Track it, don't buy it - unless a fare drops below the target."
            )

        if ledger.walk_away_price and current.total > float(ledger.walk_away_price):
            warnings.append(
                f"Every fresh option is above the walk-away price "
                f"(${float(ledger.walk_away_price):,.0f}). Worth asking whether the dates "
                "or the destination should move instead of the budget."
            )

        # Buying is reversible on most fares - say so, because it changes the call.
        if action in ("BUY", "BUY NOW") and current.quote.refundable_24h:
            reasons.append(
                "This fare has a 24-hour free-cancel window (DOT rule; Delta applies it "
                "to every fare) - buy it, then re-shop the same grid tomorrow and cancel "
                "for a full refund if something cheaper turns up."
            )
        if action in ("BUY", "BUY NOW") and current.quote.changeable:
            reasons.append(
                "The fare is changeable without a fee, so a later drop can be recaptured "
                "by re-faring. Keep the watch running after purchase."
            )
        if best_cash and best_cash.quote.carrier_type == "southwest":
            reasons.append(
                "Southwest Choice fares and points bookings can be re-fared for the "
                "difference every time the price drops, with no change fee - which makes "
                "buying early materially safer on Southwest than on anyone else. Basic "
                "fares get none of that."
            )

    if cpm is not None:
        floor = float(ledger.miles_cfg.get("min_cpm") or 1.3)
        program = ledger.miles_cfg.get("program", "miles")
        if cpm >= floor:
            reasons.append(
                f"Award option returns {cpm:.2f}c per mile against the comparable cash "
                f"fare - at or above the {floor:.2f}c floor, so {program} are worth "
                "spending here."
            )
        else:
            reasons.append(
                f"Award option returns only {cpm:.2f}c per mile (floor {floor:.2f}c) - "
                f"pay cash and keep the {program}."
            )

    return Decision(
        action=action,
        headline=headline,
        phase=phase,
        days_out=days_out,
        profile=profile,
        reasons=reasons,
        warnings=warnings,
        next_check=next_check,
        best=best,
        best_cash=best_cash,
        best_award=best_award,
        cpm=cpm,
        stats=stats,
        stale=stale,
    )


def _post_purchase(
    ledger: Ledger,
    as_of: date,
    best_cash: Costed | None,
    reasons: list[str],
    warnings: list[str],
) -> tuple[str, str]:
    """After the tickets are bought the watch does not stop - it changes job."""
    bought = ledger.purchased
    paid = float(bought.get("price") or 0.0)
    reasons.append(
        f"Purchased {bought.get('date', '?')} on {bought.get('carrier', '?')} "
        f"for ${paid:,.0f} all-in."
    )
    deadline = bought.get("free_cancel_until")
    if deadline:
        try:
            until = date.fromisoformat(deadline)
        except ValueError:
            until = None
        if until and as_of <= until:
            reasons.append(
                f"Free-cancel window is open until {until} - one more sweep of the grid "
                "today is free money if anything undercuts what was paid."
            )
    if best_cash and paid and best_cash.total < paid - 1:
        drop = paid - best_cash.total
        if bought.get("changeable"):
            return (
                "RE-FARE",
                f"The same trip is now ${drop:,.0f} cheaper and the ticket is "
                "changeable - call it in / re-fare online for the difference.",
            )
        warnings.append(
            f"Price has dropped ${drop:,.0f} since purchase but the fare is not "
            "changeable. Check whether the carrier offers a fare-difference credit."
        )
    return "HOLDING", "Tickets bought. Watching for a drop worth re-faring."


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def money(value: float) -> str:
    return f"${value:,.0f}"


def render_grid(ledger: Ledger, as_of: date, limit: int | None) -> list[str]:
    pairs = ledger.dates.grid(as_of)
    plan = ledger.dates
    lines = [f"{ledger.trip}", ""]
    if plan.precise:
        lines.append("Dates: PRECISE - one pair only, no flexibility declared.")
    else:
        lines.append(
            f"Dates: FLEXIBLE - outbound {plan.ob_low} to {plan.ob_high}, "
            f"return {plan.rt_low} to {plan.rt_high}"
        )
    if plan.must_be_there:
        lines.append(
            "Anchors that cannot move: "
            + ", ".join(f"{d:%a %b %-d}" for d in plan.must_be_there)
        )
    if plan.blackout:
        lines.append(
            "Blackout dates: " + ", ".join(f"{d:%a %b %-d}" for d in plan.blackout)
        )
    if plan.nights_min is not None:
        lines.append(f"Trip length: {plan.nights_min}-{plan.nights_max} nights")
    for rule in plan.time_rules():
        lines.append(f"Time rule - {rule}")
    lines.append("")

    origins = ledger.origins or ["(origin not set)"]
    dests = [ledger.destination] + [
        d.upper() for d in (ledger.raw.get("route") or {}).get("destination_alternates", [])
    ]
    lines.append(
        f"{len(pairs)} date pair(s) x {len(origins)} origin(s) x {len(dests)} "
        f"destination(s) = {len(pairs) * len(origins) * len(dests)} searches"
    )
    lines.append(f"Airports: {', '.join(origins)} -> {', '.join(d for d in dests if d)}")
    lines.append("")
    shown = pairs[:limit] if limit else pairs
    for pair in shown:
        lines.append(f"  [ ] {pair.label()}")
    if limit and len(pairs) > limit:
        lines.append(f"  ... and {len(pairs) - limit} more")
    if not pairs:
        lines.append(
            "  (none) - the anchors, blackouts and nights limits leave no legal pair. "
            "Widen the flex or drop a constraint."
        )
    return lines


def render_report(ledger: Ledger, decision: Decision, as_of: date, fresh_days: int) -> list[str]:
    lines = [
        f"{ledger.trip}",
        f"As of {as_of} - {decision.days_out} days to the preferred departure "
        f"({ledger.dates.ob_pref:%a %b %-d, %Y})",
        "",
        f"  ACTION: {decision.action}",
        f"  {decision.headline}",
        "",
        f"Booking window: {decision.profile.label} - "
        f"prime {decision.profile.prime[0]}-{decision.profile.prime[1]} days out "
        f"(low point ~{decision.profile.sweet}d), book by {decision.profile.book_by}d.",
        f"Phase: {PHASE_LABEL[decision.phase]}",
        f"  {decision.profile.note}",
        "",
    ]

    fresh = latest_per_option(
        ledger.cost(q) for q in ledger.quotes
        if 0 <= (as_of - q.observed_on).days <= fresh_days
    )
    if fresh:
        lines.append(
            f"All-in cost for the party of {ledger.seats}, priced within "
            f"{fresh_days} day(s):"
        )
        best_key = decision.best.quote.option_key if decision.best else None
        for costed in sorted(fresh, key=lambda c: (not c.eligible, c.total)):
            mark = "*" if costed.quote.option_key == best_key else (
                "x" if not costed.eligible else " "
            )
            lines.append(f" {mark} {costed.headline():>22}  {costed.quote.label()}")
            bits = [f"airfare {money(costed.airfare)}"]
            if costed.bags:
                bits.append(f"bags {money(costed.bags)}")
            if costed.seats:
                bits.append(f"seats {money(costed.seats)}")
            if costed.ground:
                bits.append(f"ground {money(costed.ground)} ({costed.ground_detail})")
            lines.append(f"      {' + '.join(bits)}")
            if not costed.eligible:
                lines.append(f"      NOT COMPARABLE: {costed.ineligible_reason}")
            lines.append(
                f"      source: tier {costed.quote.source_tier} "
                f"{costed.quote.source_name}"
                + (f" - {costed.quote.source_url}" if costed.quote.source_url else "")
            )
        lines.append("")

    if decision.stats:
        stats = decision.stats
        lines.append(
            f"Price history: {stats['observations']} cash quote(s) over "
            f"{stats['days_watched']} day(s) - low {money(stats['min'])} "
            f"(seen {stats['low_seen_on']}), median {money(stats['median'])}, "
            f"high {money(stats['max'])}"
        )
        if "index_vs_median" in stats:
            lines.append(
                f"Today's best sits at {stats['index_vs_median'] * 100:.0f}% of the "
                f"median and {stats['index_vs_low'] * 100:.0f}% of the lowest ever seen."
            )
        lines.append("")

    flex = _flex_savings(ledger, as_of)
    if flex:
        lines.extend(flex + [""])

    drive = drive_comparison(ledger, decision.best)
    if drive:
        lines.extend(drive + [""])

    if decision.reasons:
        lines.append("Why:")
        lines.extend(f"  - {reason}" for reason in decision.reasons)
        lines.append("")
    if decision.warnings:
        lines.append("Watch out:")
        lines.extend(f"  ! {warning}" for warning in decision.warnings)
        lines.append("")

    lines.append(f"Next price check: {decision.next_check} "
                 f"(every {cadence_days(max(decision.days_out, 0))} day(s) at this range)")
    return lines


def drive_comparison(ledger: Ledger, best: Costed | None) -> list[str]:
    """Is driving anywhere close? Answer in cash AND in hours, never just cash.

    Flying almost always wins on the travelers' time and often loses on cash.
    Rather than pick for the household, this states the trade as a price per hour
    of adult time saved - which is a number they can actually judge.
    """
    if not ledger.drive_options:
        return []
    lines = ["Driving alternative:"]
    for option in sorted(ledger.drive_options, key=lambda o: o.cash_total):
        flag = "" if option.complete else "  [PARTIAL - one-way by road]"
        lines.append(f"  {money(option.cash_total):>9}  {option.label}{flag}")
        route = " -> ".join(
            [option.legs[0].origin] + [leg.destination for leg in option.legs]
        )
        lines.append(
            f"      {route} - {option.miles_one_way:.0f} mi / "
            f"{option.hours_one_way:.1f} h each way"
        )
        who = ("they drive themselves" if option.self_driven
               else "an adult drives")
        fleet = f", {option.vehicles} vehicles" if option.vehicles > 1 else ""
        car = f" - {option.vehicle}" if option.vehicle else ""
        lines.append(f"      {who}{fleet}{car}")
        lines.append(
            f"      car covers it {option.traversals}x "
            f"({money(option.cash_per_traversal)} per run at "
            f"{option.cost_per_mile:.2f}/mi"
            + (f" + {money(option.extra_per_traversal)} food/tolls"
               if option.extra_per_traversal else "")
            + f"); travelers ride {option.traveler_traversals}x"
        )
        if option.overnights:
            lines.append(f"      overnights: {', '.join(option.overnights)}")
        lines.append(
            f"      {money(option.fuel_total)} out of pocket at the pump "
            f"({option.mpg:.0f} mpg, {option.gas_price:.2f}/gal) - the rest is "
            "depreciation and wear"
        )
        if option.self_driven:
            lines.append(
                f"      NO adult time at all · {option.traveler_hours:.0f} h "
                "of driving for the travelers themselves"
            )
        else:
            lines.append(
                f"      {option.adult_hours:.0f} adult-hours behind the wheel · "
                f"{option.traveler_hours:.0f} h of travel for the travelers"
            )
        if option.notes:
            lines.append(f"      {option.notes}")

    complete = [o for o in ledger.drive_options if o.complete]
    partial = [o for o in ledger.drive_options if not o.complete]
    if partial:
        lines.append("")
        lines.append(
            "  [PARTIAL] options only cover one direction by road - add the one-way "
            "fares for the other leg before comparing them to anything."
        )
    if not complete:
        lines.append(
            "  No complete drive option logged, so driving cannot be compared to flying "
            "head to head yet."
        )
        return lines
    cheapest = min(complete, key=lambda o: o.cash_total)
    if not best:
        lines.append("")
        lines.append(
            f"  No fares logged yet, so the bar is set by the drive: a flight has to "
            f"land under {money(cheapest.cash_total)} all-in for the pair "
            f"({money(cheapest.fuel_total)} if you only count the pump)"
            + (
                f" - and because they drive themselves, a fare buys back none of an "
                f"adult's time, only {cheapest.traveler_hours:.0f} h of theirs."
                if cheapest.self_driven
                else f" - and it starts {cheapest.adult_hours:.0f} adult-hours ahead "
                     "before it has to."
            )
        )
        return lines

    fly_hours = ledger.flying_adult_hours(best.quote.origin)
    cash_gap = cheapest.cash_total - best.total
    hour_gap = cheapest.adult_hours - fly_hours
    lines.append("")
    lines.append(
        f"  Flying {best.quote.origin}: {money(best.total)} and about "
        f"{fly_hours:.1f} adult-hours of airport runs."
    )
    if cheapest.self_driven:
        # The adult-hours term is zero, so the comparison collapses to cash and to
        # the travelers' own time - a different trade entirely.
        extra_traveler = cheapest.traveler_hours
        if cash_gap >= 0:
            lines.append(
                f"  Driving costs {money(cash_gap)} MORE, and they drive it "
                f"themselves. It saves no money and no adult time - fly."
            )
        else:
            lines.append(
                f"  Driving saves {money(-cash_gap)} and costs an adult nothing - "
                f"the whole price is {extra_traveler:.0f} h of their own driving and "
                "the risk that carries. That is a judgement call about the drivers, "
                "not an arithmetic one."
            )
    elif cash_gap >= 0:
        lines.append(
            f"  Driving costs {money(cash_gap)} MORE and {hour_gap:.0f} more "
            "adult-hours. It loses on both counts - fly."
        )
    elif hour_gap <= 0:
        lines.append(
            f"  Driving is {money(-cash_gap)} cheaper AND quicker. Drive."
        )
    else:
        rate = -cash_gap / hour_gap if hour_gap else 0.0
        lines.append(
            f"  Driving saves {money(-cash_gap)} and costs {hour_gap:.0f} extra "
            f"adult-hours - so flying is buying back an adult's time at "
            f"{money(rate)}/hour. Worth it below roughly $25-30/hour; not worth it "
            "much above that."
        )
    return lines


def _flex_savings(ledger: Ledger, as_of: date) -> list[str]:
    """What the flexibility is worth - the number that decides whether to use it."""
    cash = [
        c for c in (ledger.cost(q) for q in ledger.quotes)
        if not c.quote.is_award and c.eligible
    ]
    if not cash:
        return []
    preferred = [
        c for c in cash
        if c.quote.outbound_date == ledger.dates.ob_pref
        and c.quote.return_date == ledger.dates.rt_pref
    ]
    if not preferred:
        return []
    best_pref = min(preferred, key=lambda c: c.total)
    best_any = min(cash, key=lambda c: c.total)
    if best_any.total >= best_pref.total - 1:
        return ["Date flexibility: the preferred dates are also the cheapest priced so far."]
    saving = best_pref.total - best_any.total
    return [
        f"Date flexibility is worth {money(saving)}: preferred "
        f"{ledger.dates.ob_pref:%b %-d}/{ledger.dates.rt_pref:%b %-d} prices at "
        f"{money(best_pref.total)}, while {best_any.quote.outbound_date:%b %-d}/"
        f"{best_any.quote.return_date:%b %-d} on {best_any.quote.carrier} prices at "
        f"{money(best_any.total)}.",
    ]


def schedule(ledger: Ledger, as_of: date) -> dict:
    """The check cadence and the dated reminders that make the timing actionable."""
    profile, _ = resolve_profile(ledger)
    depart = ledger.dates.ob_pref
    # Checks run until the book-by date, not until departure: after that the decision
    # has been made and a price check is just a way to feel bad. Once the tickets are
    # bought the watch continues, but only to catch a drop worth re-faring.
    horizon = (
        depart if ledger.purchased else depart - timedelta(days=profile.book_by)
    )
    checks = []
    cursor = as_of
    while cursor <= horizon:
        days_out = (depart - cursor).days
        checks.append({
            "date": cursor.isoformat(),
            "days_out": days_out,
            "purpose": "re-fare watch" if ledger.purchased else "price check",
        })
        cursor += timedelta(days=7 if ledger.purchased else cadence_days(days_out))
    reminders = []

    def add(when: date, title: str, detail: str) -> None:
        if when >= as_of:
            reminders.append(
                {"date": when.isoformat(), "all_day": True, "summary": title,
                 "description": detail}
            )

    window_opens = depart - timedelta(days=profile.prime[1])
    sweet = depart - timedelta(days=profile.sweet)
    book_by = depart - timedelta(days=profile.book_by)
    add(window_opens, f"Airfare buying window opens - {ledger.trip}",
        f"{profile.label}: prime band is {profile.prime[0]}-{profile.prime[1]} days out. "
        "Shop the full date grid and start daily checks.")
    add(sweet, f"Airfare low point (typical) - {ledger.trip}",
        f"Historical low point for {profile.label.lower()} is about {profile.sweet} days "
        "out. Buy today unless the watch says the price is running high.")
    add(book_by, f"BOOK BY TODAY - airfare for {ledger.trip}",
        f"Past {profile.book_by} days out, waiting has historically cost money. Buy the "
        "best option on the watch.")
    if ledger.purchased and ledger.purchased.get("free_cancel_until"):
        try:
            until = date.fromisoformat(ledger.purchased["free_cancel_until"])
            add(until, f"Free-cancel deadline - {ledger.trip} airfare",
                "Last chance to re-shop and cancel for a full refund at no cost.")
        except ValueError:
            pass  # best-effort: unreadable/absent state falls back to defaults
    return {
        "trip": ledger.trip,
        "profile": profile.key,
        "departure": depart.isoformat(),
        "checks": checks,
        "reminders": reminders,
    }


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def verify(ledger: Ledger, as_of: date) -> list[str]:
    """Structural problems that would make the recommendation meaningless."""
    problems: list[str] = []
    grid = {(p.outbound, p.inbound) for p in ledger.dates.grid()}
    if not grid:
        problems.append(
            "the date plan yields no legal date pair - anchors, blackouts or the nights "
            "range contradict each other"
        )
    for quote in ledger.quotes:
        if (quote.outbound_date, quote.return_date) not in grid:
            problems.append(
                f"{quote.label()}: these dates are outside the date grid. Either the "
                "quote is for the wrong trip or the flexibility needs widening."
            )
        if quote.observed_on > as_of:
            problems.append(f"{quote.label()}: observed_on {quote.observed_on} is in the future")
        if ledger.origins and quote.origin not in ledger.origins:
            problems.append(
                f"{quote.label()}: origin {quote.origin} is not one of the trip's "
                f"origins ({', '.join(ledger.origins)})"
            )
        if quote.is_award and quote.source_tier > 1:
            problems.append(
                f"{quote.label()}: award pricing is dynamic and program-specific - it has "
                "to come from the airline's own award calendar (tier 1), not metasearch."
            )
        if ledger.checked_bags and quote.carrier_type != "legacy" and not quote.bag_fee_each_way:
            problems.append(
                f"{quote.label()}: {ledger.checked_bags} checked bag(s) planned but no "
                f"bag fee recorded for a {quote.carrier_type} carrier"
            )
    if ledger.origins and ledger.origin_costs:
        for origin in ledger.origins:
            if origin not in ledger.origin_costs:
                problems.append(
                    f"origin {origin} has no origin_costs entry - comparing airports "
                    "without their drive, parking and hotel costs is the classic way to "
                    "'save' $200 on a fare and spend $300 getting to it"
                )
    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("grid", "verify", "report", "schedule"))
    parser.add_argument("path", help="path to the fare-watch JSON")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--fresh-days", type=int, default=DEFAULT_FRESH_DAYS,
                        help="how old a quote may be and still count as today's price")
    parser.add_argument("--limit", type=int, default=None, help="grid: cap rows printed")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        as_of = date.fromisoformat(args.as_of)
        ledger = load(args.path)
    except (FareWatchError, ValueError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    try:
        if args.command == "grid":
            pairs = ledger.dates.grid(as_of)
            if args.json:
                print(json.dumps(
                    {
                        "trip": ledger.trip,
                        "precise": ledger.dates.precise,
                        "origins": ledger.origins,
                        "destination": ledger.destination,
                        "time_rules": ledger.dates.time_rules(),
                        "pairs": [
                            {"outbound": p.outbound.isoformat(),
                             "return": p.inbound.isoformat(),
                             "nights": p.nights,
                             "preferred": p.preferred}
                            for p in pairs
                        ],
                    },
                    indent=2,
                ))
            else:
                print("\n".join(render_grid(ledger, as_of, args.limit)))
            return 0 if pairs else 1

        if args.command == "verify":
            problems = verify(ledger, as_of)
            if problems:
                for problem in problems:
                    print(f"FAIL: {problem}", file=sys.stderr)
                return 1
            profile, why = resolve_profile(ledger)
            print(
                f"OK: {ledger.trip} - {len(ledger.quotes)} quote(s), "
                f"{len(ledger.dates.grid())} date pair(s), profile {profile.key} "
                f"({'; '.join(why)})"
            )
            return 0

        decision = analyse(ledger, as_of, args.fresh_days)
        if args.command == "schedule":
            payload = schedule(ledger, as_of)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"{payload['trip']} - departure {payload['departure']}")
                print(
                    f"{len(payload['checks'])} price check(s), "
                    f"{payload['checks'][0]['date']} through "
                    f"{payload['checks'][-1]['date']}:"
                )
                for threshold, every in CADENCE:
                    matching = [
                        c for c in payload["checks"]
                        if cadence_days(c["days_out"]) == every
                    ]
                    if matching:
                        print(
                            f"  every {every:>2}d  from {matching[0]['date']} "
                            f"({matching[0]['days_out']}d out) - "
                            f"{len(matching)} check(s)"
                        )
                print("Calendar reminders:")
                for reminder in payload["reminders"]:
                    print(f"  {reminder['date']}  {reminder['summary']}")
            return 0

        if args.json:
            print(json.dumps(
                {
                    "trip": ledger.trip,
                    "as_of": as_of.isoformat(),
                    "action": decision.action,
                    "headline": decision.headline,
                    "phase": decision.phase,
                    "days_out": decision.days_out,
                    "profile": decision.profile.key,
                    "best_total": decision.best.total if decision.best else None,
                    "cents_per_mile": decision.cpm,
                    "drive_options": [
                        {
                            "id": option.id,
                            "label": option.label,
                            "cash_total": option.cash_total,
                            "fuel_total": option.fuel_total,
                            "adult_hours": option.adult_hours,
                            "traveler_hours": option.traveler_hours,
                            "miles_one_way": option.miles_one_way,
                        }
                        for option in ledger.drive_options
                    ],
                    "stats": decision.stats,
                    "reasons": decision.reasons,
                    "warnings": decision.warnings,
                    "next_check": decision.next_check.isoformat(),
                    "stale": decision.stale,
                },
                indent=2,
            ))
        else:
            print("\n".join(render_report(ledger, decision, as_of, args.fresh_days)))
        return 1 if decision.stale else 0
    except FareWatchError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
