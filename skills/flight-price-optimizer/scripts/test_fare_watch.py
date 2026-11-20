#!/usr/bin/env python3
"""Tests for fare_watch.py.

Run: python3 -m unittest discover -s skills/flight-price-optimizer/scripts
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fare_watch as fw  # noqa: E402

EXAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reference",
    "example-watch.json",
)

BASE = {
    "trip": "test trip",
    "party": [
        {"name": "A", "type": "adult"},
        {"name": "B", "type": "adult"},
        {"name": "C", "type": "child", "age": 10},
        {"name": "D", "type": "child", "age": 12},
    ],
    "checked_bags": 2,
    "dates": {
        "outbound": {"preferred": "2026-11-21", "flex_days": [0, 2]},
        "return": {"preferred": "2026-11-30", "flex_days": [2, 1]},
        "nights": {"min": 5, "max": 9},
        "must_be_there": ["2026-11-26"],
        "blackout": ["2026-11-29"],
    },
    "route": {"destination": "DEN", "origins": ["HOME", "HUB"]},
    "origin_costs": {
        "HOME": {"drive_miles": 24, "parking_per_day": 12, "drive_minutes": 20},
        "HUB": {
            "drive_minutes": 150,
            "drive_miles": 300,
            "parking_per_day": 10,
            "prenight_hotel": 190,
            "prenight_if_departs_before": "09:00",
        },
    },
    "quotes": [],
}


def quote(**overrides):
    record = {
        "observed_on": "2026-10-01",
        "carrier": "Delta",
        "carrier_type": "legacy",
        "origin": "HOME",
        "destination": "DEN",
        "outbound_date": "2026-11-21",
        "return_date": "2026-11-30",
        "price_per_person": 400.0,
        "bag_fee_each_way": 35.0,
        "changeable": True,
        "source": {"tier": 1, "name": "delta.com"},
    }
    record.update(overrides)
    return record


def ledger(**overrides):
    raw = copy.deepcopy(BASE)
    for key, value in overrides.items():
        if key == "dates":
            raw["dates"].update(value)
        else:
            raw[key] = value
    return fw.Ledger(raw)


class HolidayDetection(unittest.TestCase):
    def test_thanksgiving_is_the_fourth_thursday(self):
        self.assertEqual(fw._nth_weekday(2026, 11, 3, 4), date(2026, 11, 26))
        self.assertEqual(fw._nth_weekday(2027, 11, 3, 4), date(2027, 11, 25))

    def test_late_november_trip_picks_the_thanksgiving_profile(self):
        profile, why = fw.resolve_profile(ledger())
        self.assertEqual(profile.key, "domestic_thanksgiving")
        self.assertTrue(any("Thanksgiving" in reason for reason in why))

    def test_ordinary_dates_get_the_standard_profile(self):
        book = ledger(dates={
            "outbound": {"preferred": "2026-09-12"},
            "return": {"preferred": "2026-09-19"},
            "must_be_there": [],
            "blackout": [],
            "nights": {"min": 5, "max": 9},
        })
        self.assertEqual(fw.resolve_profile(book)[0].key, "domestic_standard")

    def test_christmas_outranks_a_bare_holiday_overlap(self):
        book = ledger(dates={
            "outbound": {"preferred": "2026-12-20"},
            "return": {"preferred": "2026-12-27"},
            "must_be_there": [],
            "blackout": [],
            "nights": {"min": 5, "max": 9},
        })
        self.assertEqual(fw.resolve_profile(book)[0].key, "domestic_christmas")

    def test_international_holiday_trip_uses_the_peak_international_window(self):
        book = ledger(route={"destination": "CDG", "origins": ["HUB"], "international": True})
        self.assertEqual(fw.resolve_profile(book)[0].key, "international_peak")

    def test_explicit_profile_wins_over_detection(self):
        self.assertEqual(fw.resolve_profile(ledger(profile="domestic_standard"))[0].key,
                         "domestic_standard")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(fw.FareWatchError):
            fw.resolve_profile(ledger(profile="cheap_please"))


class DateGrid(unittest.TestCase):
    def test_fuzzy_window_expands_both_tails(self):
        pairs = ledger().dates.grid()
        outs = sorted({p.outbound for p in pairs})
        self.assertEqual(outs, [date(2026, 11, 21), date(2026, 11, 22), date(2026, 11, 23)])

    def test_blackout_date_never_appears(self):
        pairs = ledger().dates.grid()
        self.assertTrue(all(p.inbound != date(2026, 11, 29) for p in pairs))

    def test_anchor_must_fall_inside_the_trip(self):
        # Nights that end before Thanksgiving are dropped even though they are legal
        # lengths - the holiday is the reason for the trip.
        book = ledger(dates={"nights": {"min": 1, "max": 9}})
        self.assertTrue(all(p.outbound <= date(2026, 11, 26) <= p.inbound
                            for p in book.dates.grid()))

    def test_nights_bounds_are_enforced(self):
        pairs = ledger().dates.grid()
        self.assertTrue(all(5 <= p.nights <= 9 for p in pairs))
        self.assertNotIn((date(2026, 11, 21), date(2026, 12, 1)),
                         [(p.outbound, p.inbound) for p in pairs])

    def test_precise_mode_yields_exactly_one_pair(self):
        book = ledger(dates={
            "mode": "fixed",
            "outbound": {"preferred": "2026-11-21", "flex_days": 3},
            "return": {"preferred": "2026-11-30", "flex_days": 3},
        })
        self.assertTrue(book.dates.precise)
        pairs = book.dates.grid()
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0].preferred)

    def test_zero_flex_is_precise_without_declaring_fixed_mode(self):
        book = ledger(dates={
            "outbound": {"preferred": "2026-11-21"},
            "return": {"preferred": "2026-11-30"},
        })
        self.assertTrue(book.dates.precise)

    def test_symmetric_flex_days_number(self):
        book = ledger(dates={
            "outbound": {"preferred": "2026-11-21", "flex_days": 1},
            "return": {"preferred": "2026-11-30", "flex_days": 0},
            "nights": {"min": 5, "max": 10},
            "blackout": [],
        })
        self.assertEqual(sorted({p.outbound for p in book.dates.grid()}),
                         [date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 22)])

    def test_nights_only_plan_derives_the_return_window(self):
        book = ledger(dates={
            "outbound": {"preferred": "2026-11-21", "flex_days": [0, 1]},
            "return": None,
            "nights": {"min": 6, "max": 7},
            "must_be_there": [],
            "blackout": [],
        })
        book.raw["dates"].pop("return")
        plan = fw.DatePlan(book.raw["dates"])
        self.assertTrue(all(6 <= p.nights <= 7 for p in plan.grid()))

    def test_grid_skips_dates_already_past(self):
        pairs = ledger().dates.grid(as_of=date(2026, 11, 22))
        self.assertTrue(all(p.outbound >= date(2026, 11, 22) for p in pairs))

    def test_contradictory_plan_yields_nothing_rather_than_guessing(self):
        book = ledger(dates={
            "outbound": {"preferred": "2026-11-21", "flex_days": 0},
            "return": {"preferred": "2026-11-24", "flex_days": 0},
            "nights": {"min": 1, "max": 9},
        })
        self.assertEqual(book.dates.grid(), [])  # trip ends before Thanksgiving

    def test_backwards_window_is_rejected(self):
        with self.assertRaises(fw.FareWatchError):
            fw.DatePlan({
                "outbound": {"earliest": "2026-11-25", "latest": "2026-11-21"},
                "return": {"preferred": "2026-11-30"},
            })

    def test_bad_time_rule_is_rejected(self):
        with self.assertRaises(fw.FareWatchError):
            fw.DatePlan({
                "outbound": {"preferred": "2026-11-21"},
                "return": {"preferred": "2026-11-30"},
                "outbound_time": {"depart_after": "6am"},
            })


class CostModel(unittest.TestCase):
    def test_bags_are_counted_both_directions_for_the_party(self):
        book = ledger()
        costed = book.cost(fw.load_quote(quote()))
        self.assertEqual(costed.airfare, 1600.0)          # 400 x 4 seats
        self.assertEqual(costed.bags, 140.0)              # 35 x 2 bags x 2 directions

    def test_hub_carries_its_drive_parking_and_hotel(self):
        book = ledger()
        home = book.cost(fw.load_quote(quote(outbound_depart_local="06:05")))
        hub = book.cost(fw.load_quote(
            quote(origin="HUB", price_per_person=312.0, outbound_depart_local="06:05")
        ))
        self.assertGreater(hub.ground, home.ground)
        self.assertIn("night before", hub.ground_detail)
        # $88/person cheaper on the fare, still more expensive door to door.
        self.assertGreater(hub.total, home.total)

    def test_no_prenight_hotel_for_a_civilised_departure(self):
        book = ledger()
        late = book.cost(fw.load_quote(quote(origin="HUB", outbound_depart_local="11:30")))
        self.assertNotIn("night before", late.ground_detail)

    def test_parking_counts_every_day_the_car_sits(self):
        book = ledger()
        costed = book.cost(fw.load_quote(quote()))
        self.assertIn("10d parking", costed.ground_detail)  # Nov 21 -> Nov 30 inclusive

    def test_award_quote_prices_the_cash_component_only(self):
        book = ledger()
        costed = book.cost(fw.load_quote(quote(
            price_per_person=0,
            award={"miles_per_person": 30000, "cash_per_person": 5.60},
        )))
        self.assertEqual(costed.airfare, 22.4)
        self.assertEqual(costed.miles, 120000)
        self.assertIn("miles", costed.headline())


class Eligibility(unittest.TestCase):
    def test_fare_with_too_few_seats_is_not_comparable(self):
        book = ledger()
        costed = book.cost(fw.load_quote(quote(price_per_person=99.0, seats_left=3)))
        self.assertFalse(costed.eligible)
        self.assertIn("3 seat", costed.ineligible_reason)

    def test_basic_economy_without_priced_seats_is_not_comparable(self):
        book = ledger()
        costed = book.cost(fw.load_quote(quote(basic_economy=True, seat_fee_total=0)))
        self.assertFalse(costed.eligible)

    def test_basic_economy_with_seats_priced_in_is_comparable(self):
        book = ledger()
        costed = book.cost(fw.load_quote(quote(basic_economy=True, seat_fee_total=96.0)))
        self.assertTrue(costed.eligible)

    def test_tier_three_source_is_not_a_fare(self):
        book = ledger()
        costed = book.cost(fw.load_quote(
            quote(source={"tier": 3, "name": "a deal blog"})
        ))
        self.assertFalse(costed.eligible)

    def test_award_beyond_the_balance_is_not_comparable(self):
        book = ledger(miles={"program": "Delta SkyMiles", "balance": 50000})
        costed = book.cost(fw.load_quote(quote(
            price_per_person=0,
            award={"miles_per_person": 30000, "cash_per_person": 5.60},
        )))
        self.assertFalse(costed.eligible)
        self.assertIn("balance", costed.ineligible_reason)


class Decisions(unittest.TestCase):
    def _decide(self, quotes, as_of, **kwargs):
        book = ledger(quotes=quotes, **kwargs)
        return fw.analyse(book, date.fromisoformat(as_of))

    def test_far_out_is_a_watch_not_a_buy(self):
        decision = self._decide([quote(observed_on="2026-08-08")], "2026-08-08")
        self.assertEqual(decision.action, "WATCH")
        self.assertEqual(decision.phase, "too_early")

    def test_inside_book_by_is_buy_now(self):
        decision = self._decide([quote(observed_on="2026-11-05")], "2026-11-05")
        self.assertEqual(decision.action, "BUY NOW")
        self.assertEqual(decision.phase, "late")

    def test_target_price_triggers_a_buy_even_early(self):
        decision = self._decide(
            [quote(observed_on="2026-08-08", price_per_person=200.0)],
            "2026-08-08",
            target_price=1200,
        )
        self.assertEqual(decision.action, "BUY")
        self.assertIn("target", decision.headline)

    def test_a_two_day_low_is_not_treated_as_exceptional(self):
        # Same trap the first draft fell into: "cheapest ever seen" over two days of
        # watching is not evidence, and must not produce a BUY.
        quotes = [
            quote(observed_on="2026-08-07", price_per_person=600.0),
            quote(observed_on="2026-08-08", price_per_person=300.0, fare_brand="Sale"),
        ]
        decision = self._decide(quotes, "2026-08-08")
        self.assertEqual(decision.action, "WATCH")

    def test_a_genuine_outlier_with_history_behind_it_is_a_buy(self):
        quotes = [
            quote(observed_on=f"2026-08-0{day}", price_per_person=600.0,
                  fare_brand=f"obs{day}")
            for day in range(1, 8)
        ]
        quotes.append(quote(observed_on="2026-08-08", price_per_person=300.0,
                            fare_brand="drop"))
        decision = self._decide(quotes, "2026-08-08")
        self.assertEqual(decision.action, "BUY")
        self.assertIn("median", decision.headline)

    def test_prime_window_at_the_low_buys(self):
        quotes = [
            quote(observed_on="2026-09-25", price_per_person=500.0, fare_brand="a"),
            quote(observed_on="2026-10-02", price_per_person=520.0, fare_brand="b"),
            quote(observed_on="2026-10-07", price_per_person=500.0, fare_brand="a"),
        ]
        decision = self._decide(quotes, "2026-10-07")
        self.assertEqual(decision.phase, "prime")
        self.assertEqual(decision.action, "BUY")

    def test_prime_window_above_its_own_low_waits(self):
        quotes = [
            quote(observed_on="2026-09-25", price_per_person=400.0, fare_brand="a"),
            quote(observed_on="2026-10-02", price_per_person=430.0, fare_brand="b"),
            quote(observed_on="2026-10-07", price_per_person=520.0, fare_brand="c"),
        ]
        decision = self._decide(quotes, "2026-10-07")
        self.assertEqual(decision.action, "WATCH CLOSELY")

    def test_ineligible_bargain_never_becomes_the_recommendation(self):
        quotes = [
            quote(observed_on="2026-08-08", price_per_person=99.0, seats_left=2,
                  carrier="Frontier", carrier_type="budget", fare_brand="Basic"),
            quote(observed_on="2026-08-08", price_per_person=400.0),
        ]
        decision = self._decide(quotes, "2026-08-08", target_price=1200)
        self.assertEqual(decision.action, "WATCH")
        self.assertTrue(any("Excluded" in w for w in decision.warnings))

    def test_stale_watch_is_flagged_and_exits_nonzero(self):
        decision = self._decide([quote(observed_on="2026-09-01")], "2026-10-07")
        self.assertTrue(decision.stale)
        self.assertTrue(any("stale prices" in w for w in decision.warnings))

    def test_no_quotes_means_shop_first(self):
        decision = self._decide([], "2026-08-08")
        self.assertEqual(decision.action, "SHOP")

    def test_walk_away_price_is_surfaced(self):
        decision = self._decide(
            [quote(observed_on="2026-08-08", price_per_person=900.0)],
            "2026-08-08",
            walk_away_price=1000,
        )
        self.assertTrue(any("walk-away" in w for w in decision.warnings))

    def test_cadence_tightens_as_the_trip_approaches(self):
        self.assertEqual(fw.cadence_days(200), 14)
        self.assertEqual(fw.cadence_days(100), 7)
        self.assertEqual(fw.cadence_days(50), 3)
        self.assertEqual(fw.cadence_days(30), 2)
        self.assertEqual(fw.cadence_days(10), 1)


class MilesVersusCash(unittest.TestCase):
    def test_poor_redemption_says_pay_cash(self):
        quotes = [
            quote(observed_on="2026-10-07", price_per_person=400.0),
            quote(observed_on="2026-10-07", price_per_person=0, fare_brand="award",
                  award={"miles_per_person": 40000, "cash_per_person": 5.60}),
        ]
        decision = fw.analyse(ledger(quotes=quotes), date(2026, 10, 7))
        self.assertIsNotNone(decision.cpm)
        self.assertLess(decision.cpm, 1.3)
        self.assertTrue(any("pay cash" in r for r in decision.reasons))

    def test_strong_redemption_says_spend_the_miles(self):
        quotes = [
            quote(observed_on="2026-10-07", price_per_person=900.0),
            quote(observed_on="2026-10-07", price_per_person=0, fare_brand="award",
                  award={"miles_per_person": 25000, "cash_per_person": 5.60}),
        ]
        decision = fw.analyse(ledger(quotes=quotes), date(2026, 10, 7))
        self.assertGreater(decision.cpm, 1.3)
        self.assertTrue(any("worth spending" in r for r in decision.reasons))


class AfterPurchase(unittest.TestCase):
    def test_price_drop_on_a_changeable_ticket_is_a_refare(self):
        book = ledger(
            quotes=[quote(observed_on="2026-10-20", price_per_person=300.0)],
            purchased={"date": "2026-10-07", "carrier": "Southwest", "price": 2000,
                       "changeable": True},
        )
        decision = fw.analyse(book, date(2026, 10, 20))
        self.assertEqual(decision.action, "RE-FARE")

    def test_drop_on_a_locked_fare_warns_instead(self):
        book = ledger(
            quotes=[quote(observed_on="2026-10-20", price_per_person=300.0)],
            purchased={"date": "2026-10-07", "carrier": "Frontier", "price": 2000,
                       "changeable": False},
        )
        decision = fw.analyse(book, date(2026, 10, 20))
        self.assertEqual(decision.action, "HOLDING")
        self.assertTrue(any("not\nchangeable" in w or "not changeable" in w
                            for w in decision.warnings))

    def test_no_drop_just_holds(self):
        book = ledger(
            quotes=[quote(observed_on="2026-10-20", price_per_person=700.0)],
            purchased={"date": "2026-10-07", "carrier": "Delta", "price": 2000,
                       "changeable": True},
        )
        self.assertEqual(fw.analyse(book, date(2026, 10, 20)).action, "HOLDING")


DRIVE = {
    "id": "via-halfway-town",
    "label": "Drive via Halfway Town",
    "legs": [
        {"from": "Hometown", "to": "Halfway Town", "miles": 269, "hours": 4.75,
         "overnight": {"where": "Grandparents", "cost": 0}},
        {"from": "Halfway Town", "to": "Coast City", "miles": 265, "hours": 4.15},
    ],
    "traversals": 4,
    "traveler_traversals": 2,
    "cost_per_mile": 0.67,
    "extra_per_traversal": 60,
}


class Driving(unittest.TestCase):
    def test_cash_counts_every_traversal_not_just_the_travellers(self):
        option = fw.load_drive_option(DRIVE)
        self.assertAlmostEqual(option.miles_one_way, 534)
        # 534 mi x $0.67 + $0 overnight + $60 food = $417.78 per run, four runs.
        self.assertAlmostEqual(option.cash_per_traversal, 534 * 0.67 + 60, places=2)
        self.assertAlmostEqual(option.cash_total, (534 * 0.67 + 60) * 4, places=2)

    def test_adult_hours_exceed_traveller_hours_on_a_dropoff(self):
        option = fw.load_drive_option(DRIVE)
        self.assertAlmostEqual(option.hours_one_way, 8.9)
        self.assertAlmostEqual(option.adult_hours, 35.6)
        self.assertAlmostEqual(option.traveler_hours, 17.8)
        self.assertGreater(option.adult_hours, option.traveler_hours)

    def test_free_overnight_is_priced_at_zero_but_still_shown(self):
        option = fw.load_drive_option(DRIVE)
        self.assertEqual(option.overnight_cost_one_way, 0.0)
        self.assertTrue(any("Grandparents" in entry for entry in option.overnights))

    def test_paid_overnight_lands_in_every_traversal(self):
        record = copy.deepcopy(DRIVE)
        record["legs"][0]["overnight"] = {"where": "hotel", "cost": 120}
        option = fw.load_drive_option(record)
        self.assertAlmostEqual(option.cash_total - fw.load_drive_option(DRIVE).cash_total,
                               120 * 4, places=2)

    def test_fuel_only_cost_is_far_below_the_all_in_cost(self):
        option = fw.load_drive_option(DRIVE)
        self.assertLess(option.fuel_total, option.cash_total)
        # Fuel at 24 mpg / $2.95 is ~$0.123/mi against the $0.67 all-in rate, so the
        # pump figure must be well under half - this is the number that decides
        # whether a household believes the comparison.
        self.assertLess(option.fuel_total, option.cash_total * 0.6)

    def test_fuel_assumptions_are_configurable(self):
        record = copy.deepcopy(DRIVE)
        record["fuel"] = {"mpg": 12, "gas_price": 4.50}
        thirsty = fw.load_drive_option(record)
        self.assertGreater(thirsty.fuel_total, fw.load_drive_option(DRIVE).fuel_total)

    def test_travellers_driving_themselves_costs_no_adult_hours(self):
        record = copy.deepcopy(DRIVE)
        record["driven_by"] = "travelers"
        record["traversals"] = 2
        record["traveler_traversals"] = 2
        option = fw.load_drive_option(record)
        self.assertTrue(option.self_driven)
        self.assertEqual(option.adult_hours, 0.0)
        self.assertAlmostEqual(option.traveler_hours, 17.8)
        self.assertTrue(option.complete)

    def test_self_driven_halves_the_cash_versus_a_dropoff(self):
        record = copy.deepcopy(DRIVE)
        record.update({"driven_by": "travelers", "traversals": 2, "traveler_traversals": 2})
        self.assertAlmostEqual(
            fw.load_drive_option(record).cash_total,
            fw.load_drive_option(DRIVE).cash_total / 2,
            places=2,
        )

    def test_self_driven_car_cannot_make_trips_the_travellers_dont(self):
        record = copy.deepcopy(DRIVE)
        record["driven_by"] = "travelers"   # traversals 4 vs traveler_traversals 2
        with self.assertRaises(fw.FareWatchError):
            fw.load_drive_option(record)

    def test_unknown_driver_is_rejected(self):
        record = copy.deepcopy(DRIVE)
        record["driven_by"] = "the dog"
        with self.assertRaises(fw.FareWatchError):
            fw.load_drive_option(record)

    def test_two_vehicles_double_the_mileage_cost(self):
        record = copy.deepcopy(DRIVE)
        record.update({"driven_by": "travelers", "traversals": 2,
                       "traveler_traversals": 2, "vehicles": 2})
        one = copy.deepcopy(record)
        one["vehicles"] = 1
        two_cars = fw.load_drive_option(record)
        one_car = fw.load_drive_option(one)
        mileage = 534 * 0.67
        self.assertAlmostEqual(two_cars.cash_total - one_car.cash_total,
                               mileage * 2, places=2)

    def test_self_driven_comparison_talks_about_their_time_not_an_adults(self):
        record = copy.deepcopy(DRIVE)
        record.update({"driven_by": "travelers", "traversals": 2, "traveler_traversals": 2})
        book = ledger(quotes=[quote(observed_on="2026-10-07", price_per_person=900.0)],
                      drive_options=[record])
        decision = fw.analyse(book, date(2026, 10, 7))
        text = "\n".join(fw.drive_comparison(book, decision.best))
        self.assertIn("costs an adult nothing", text)
        self.assertIn("their own driving", text)

    def test_leg_with_no_hours_is_rejected(self):
        record = copy.deepcopy(DRIVE)
        record["legs"][0]["hours"] = 0
        with self.assertRaises(fw.FareWatchError):
            fw.load_drive_option(record)

    def test_travellers_cannot_ride_more_than_the_car_drives(self):
        record = copy.deepcopy(DRIVE)
        record["traveler_traversals"] = 6
        with self.assertRaises(fw.FareWatchError):
            fw.load_drive_option(record)

    def test_one_way_drive_is_partial_and_never_sets_the_bar(self):
        hybrid = copy.deepcopy(DRIVE)
        hybrid["id"] = "drive-down-fly-home"
        hybrid["traversals"] = 2
        hybrid["traveler_traversals"] = 1
        book = ledger(drive_options=[hybrid, DRIVE])
        options = {o.id: o for o in book.drive_options}
        self.assertFalse(options["drive-down-fly-home"].complete)
        self.assertTrue(options["via-halfway-town"].complete)
        lines = fw.drive_comparison(book, None)
        text = "\n".join(lines)
        self.assertIn("PARTIAL", text)
        # The bar must come from the complete option, not the cheaper half-journey.
        self.assertIn(fw.money(options["via-halfway-town"].cash_total), text)

    def test_only_partial_options_refuses_to_compare(self):
        hybrid = copy.deepcopy(DRIVE)
        hybrid["traveler_traversals"] = 1
        book = ledger(drive_options=[hybrid])
        text = "\n".join(fw.drive_comparison(book, None))
        self.assertIn("cannot be compared", text)

    def test_self_driven_bar_talks_about_their_hours_not_an_adults(self):
        record = copy.deepcopy(DRIVE)
        record.update({"driven_by": "travelers", "traversals": 2, "traveler_traversals": 2})
        text = "\n".join(fw.drive_comparison(ledger(drive_options=[record]), None))
        self.assertIn("buys back none of an", text)
        self.assertNotIn("0 adult-hours ahead", text)

    def test_with_no_fares_the_drive_sets_the_bar(self):
        book = ledger(drive_options=[DRIVE])
        lines = fw.drive_comparison(book, None)
        self.assertTrue(any("has to land under" in line for line in lines))

    def test_expensive_drive_against_a_cheap_fare_says_fly(self):
        book = ledger(quotes=[quote(observed_on="2026-10-07", price_per_person=150.0)],
                      drive_options=[DRIVE])
        decision = fw.analyse(book, date(2026, 10, 7))
        lines = fw.drive_comparison(book, decision.best)
        self.assertTrue(any("loses on both counts" in line for line in lines))

    def test_cheap_drive_against_an_expensive_fare_prices_the_trade_per_hour(self):
        book = ledger(quotes=[quote(observed_on="2026-10-07", price_per_person=900.0)],
                      drive_options=[DRIVE])
        decision = fw.analyse(book, date(2026, 10, 7))
        lines = fw.drive_comparison(book, decision.best)
        self.assertTrue(any("/hour" in line for line in lines))

    def test_flying_adult_hours_counts_both_round_trips(self):
        book = ledger(drive_options=[DRIVE])
        # HOME is 20 minutes away: drop-off round trip + collection round trip.
        self.assertAlmostEqual(book.flying_adult_hours("HOME"), 20 * 4 / 60)

    def test_drive_section_appears_in_the_report(self):
        book = ledger(quotes=[quote(observed_on="2026-10-07")], drive_options=[DRIVE])
        decision = fw.analyse(book, date(2026, 10, 7))
        text = "\n".join(fw.render_report(book, decision, date(2026, 10, 7), 3))
        self.assertIn("Driving alternative:", text)


class Verify(unittest.TestCase):
    def test_quote_outside_the_grid_is_caught(self):
        book = ledger(quotes=[quote(outbound_date="2026-11-29", return_date="2026-12-05")])
        problems = fw.verify(book, date(2026, 10, 7))
        self.assertTrue(any("outside the date grid" in p for p in problems))

    def test_future_observation_is_caught(self):
        book = ledger(quotes=[quote(observed_on="2026-12-01")])
        self.assertTrue(any("in the future" in p for p in fw.verify(book, date(2026, 10, 7))))

    def test_award_from_metasearch_is_rejected(self):
        book = ledger(quotes=[quote(
            price_per_person=0,
            award={"miles_per_person": 30000, "cash_per_person": 5.60},
            source={"tier": 2, "name": "Google Flights"},
        )])
        self.assertTrue(any("award calendar" in p or "tier 1" in p
                            for p in fw.verify(book, date(2026, 10, 7))))

    def test_unknown_origin_is_caught(self):
        book = ledger(quotes=[quote(origin="MSY")])
        self.assertTrue(any("not one of the trip's origins" in p
                            for p in fw.verify(book, date(2026, 10, 7))))

    def test_budget_carrier_without_bag_fees_is_caught(self):
        book = ledger(quotes=[quote(carrier="Spirit", carrier_type="budget",
                                    bag_fee_each_way=0)])
        self.assertTrue(any("no bag fee" in p for p in fw.verify(book, date(2026, 10, 7))))

    def test_missing_origin_costs_are_caught(self):
        raw = copy.deepcopy(BASE)
        raw["origin_costs"].pop("HUB")
        problems = fw.verify(fw.Ledger(raw), date(2026, 10, 7))
        self.assertTrue(any("no origin_costs entry" in p for p in problems))

    def test_priceless_quote_is_rejected_at_load(self):
        with self.assertRaises(fw.FareWatchError):
            fw.load_quote(quote(price_per_person=0))

    def test_sourceless_quote_is_rejected_at_load(self):
        with self.assertRaises(fw.FareWatchError):
            fw.load_quote(quote(source={}))

    def test_party_is_required(self):
        raw = copy.deepcopy(BASE)
        raw["party"] = []
        with self.assertRaises(fw.FareWatchError):
            fw.Ledger(raw)


class Schedule(unittest.TestCase):
    def test_checks_stop_at_the_book_by_date(self):
        payload = fw.schedule(ledger(), date(2026, 8, 8))
        last = date.fromisoformat(payload["checks"][-1]["date"])
        self.assertLessEqual((date(2026, 11, 21) - last).days,
                             fw.PROFILES["domestic_thanksgiving"].book_by + 2)

    def test_reminders_cover_window_low_point_and_deadline(self):
        payload = fw.schedule(ledger(), date(2026, 8, 8))
        summaries = " ".join(r["summary"] for r in payload["reminders"])
        self.assertIn("buying window opens", summaries)
        self.assertIn("low point", summaries)
        self.assertIn("BOOK BY TODAY", summaries)

    def test_past_reminders_are_not_emitted(self):
        payload = fw.schedule(ledger(), date(2026, 11, 1))
        self.assertTrue(all(date.fromisoformat(r["date"]) >= date(2026, 11, 1)
                            for r in payload["reminders"]))


class ExampleLedger(unittest.TestCase):
    def _run(self, argv) -> tuple[int, str]:
        with tempfile.TemporaryFile("w+") as handle:
            stdout, sys.stdout = sys.stdout, handle
            try:
                code = fw.main(argv)
            finally:
                sys.stdout = stdout
            handle.seek(0)
            return code, handle.read()

    def test_shipped_example_verifies_and_reports(self):
        for command in ("verify", "report", "grid", "schedule"):
            code, out = self._run([command, EXAMPLE, "--as-of", "2026-08-08"])
            self.assertEqual(code, 0, f"{command} exited {code}")
            self.assertTrue(out.strip(), f"{command} printed nothing")

    def test_json_report_is_machine_readable(self):
        _, out = self._run(["report", EXAMPLE, "--as-of", "2026-08-08", "--json"])
        payload = json.loads(out)
        self.assertEqual(payload["profile"], "domestic_thanksgiving")
        self.assertIn(payload["action"], ("WATCH", "WATCH CLOSELY", "BUY", "BUY NOW"))

    def test_hub_bargain_loses_to_home_once_ground_costs_land(self):
        book = fw.load(EXAMPLE)
        costed = [book.cost(q) for q in book.quotes if not q.is_award]
        hub = next(c for c in costed
                   if c.quote.origin == "HUB" and c.quote.carrier == "Delta")
        home = next(c for c in costed
                   if c.quote.origin == "HOME" and c.quote.carrier == "Delta")
        self.assertLess(hub.quote.price_per_person, home.quote.price_per_person)
        self.assertGreater(hub.total, home.total)


if __name__ == "__main__":
    unittest.main()
