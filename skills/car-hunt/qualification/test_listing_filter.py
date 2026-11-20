"""Unit tests for the pre-contact listing disqualifier (no LLM, no network).

This is the regression gate for the bug where a non-running car received an
opener: the keyword decision now lives in tested Python, so a missing phrasing
fails here instead of in production.

Run:  PYTHONPATH=. pytest test_listing_filter.py
"""
import pytest

from listing_filter import disqualifying_reason, is_contactable


# --- must DISQUALIFY (the car/listing should never be contacted) ---
DISQUALIFY = [
    # the exact class that slipped through: "doesn't run" family
    ("Selling my 04 Civic, doesn't run, needs a motor", "non-running"),
    ("Great body but the car is not running right now", "non-running"),
    ("Non running Camry, good for parts", "non-running"),
    ("Project car, won't start, have title", "non-running"),
    ("Mechanic special — cranks but won't start", "non-running"),
    ("Parts car only, no returns", "non-running"),
    ("Selling for parts", "non-running"),
    ("Engine is blown, otherwise clean", "non-running"),
    ("blown head gasket, needs work", "non-running"),
    ("transmission is shot, drives rough", "non-running"),
    ("motor seized last month", "non-running"),
    ("engine locked up", "non-running"),
    ("Needs engine. Body is mint.", "non-running"),
    ("needs a transmission, everything else works", "non-running"),
    ("doesn't move under its own power", "non-running"),
    ("rod knock, you can hear it", "non-running"),
    ("ran when parked, been sitting 2 years", "non-running"),
    ("non-op, needs to be towed", "non-running"),
    # branded title
    ("Clean running Accord, rebuilt title though", "branded-title"),
    ("salvage title, runs great", "branded-title"),
    ("No title but I have a bill of sale", "branded-title"),
    ("bill of sale only, no title in hand", "branded-title"),
    # scam signals
    ("Beautiful car, can ship anywhere, pay by Zelle", "scam-signal"),
    ("Send a deposit to hold, will ship to you", "scam-signal"),
]

# --- must NOT disqualify (honest, contactable listings) ---
CLEAR = [
    "Runs and drives great, no issues at all",
    "No check engine light, no knocking, never overheats",
    "New transmission installed last year, runs perfect",
    "Head gasket was replaced, all maintenance done",
    "Clean title in hand, not salvage, no accidents",
    "Cold A/C, blows ice cold, well maintained non-smoker car",
    "Engine rebuilt, runs like new",
    "No rust, garage kept, starts right up every time",
    "Project completed — fully restored and running",  # 'project' alone, no 'car'
    "Great mechanic kept it serviced its whole life",   # not 'mechanic special'
    "Needs engine oil change and new tires, otherwise solid",  # 'needs engine oil'
    "Needs transmission fluid service soon",            # not 'needs transmission'
    "Brand new motor, zero problems",
    "No salvage, no flood, clean title in hand",
    "Daily driver, smooth shifts, no slipping",
]


@pytest.mark.parametrize("text,family", DISQUALIFY)
def test_disqualified(text, family):
    reason = disqualifying_reason(text)
    assert reason is not None, f"expected disqualify for: {text!r}"
    assert reason.startswith(family), f"{text!r} -> {reason} (wanted {family})"
    assert is_contactable(text) is False


@pytest.mark.parametrize("text", CLEAR)
def test_clear(text):
    reason = disqualifying_reason(text)
    assert reason is None, f"false positive on {text!r} -> {reason}"
    assert is_contactable(text) is True


def test_empty_and_none_are_clear():
    assert disqualifying_reason("") is None
    assert disqualifying_reason(None) is None


def test_reason_includes_the_matched_phrase():
    r = disqualifying_reason("this one doesn't run sadly")
    assert "doesn't run" in r
