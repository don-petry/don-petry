#!/usr/bin/env python3
"""Tests for the Scion free-text-search post-filter (issue #31).

Run: python3 -m pytest skills/car-hunt/sources/test_scion.py -q
"""
from __future__ import annotations

import scion


# ---- genuine matches ------------------------------------------------------

def test_explicit_scion_tc():
    assert scion.is_genuine_scion("2008 Scion tC Coupe - $4,500", "tc")


def test_explicit_scion_xd():
    assert scion.is_genuine_scion("2009 SCION xD hatchback, clean title", "xd")


def test_case_insensitive_make_word():
    assert scion.is_genuine_scion("scion TC release series", "tc")


def test_bare_model_token_no_make_word():
    # FB sometimes lists just "tC" without the word Scion.
    assert scion.is_genuine_scion("2010 tC sunroof, 120k mi", "tc")


# ---- noise the fuzzy search drags in --------------------------------------

def test_rejects_plain_toyota_camry_noise():
    assert not scion.is_genuine_scion("2012 Toyota Camry LE", "tc")


def test_rejects_wrong_scion_model_for_query():
    # An xB is a real Scion, but the query was for tC.
    assert not scion.is_genuine_scion("2011 Scion xB wagon", "tc")


def test_rejects_competing_make_even_with_loose_token():
    # "tacoma" must not trip the \btc\b matcher, and a Toyota truck is not a tC.
    assert not scion.is_genuine_scion("2015 Toyota Tacoma SR5", "tc")


def test_wrong_model_token_absent():
    assert not scion.is_genuine_scion("2008 Scion xA", "tc")


# ---- model-agnostic mode --------------------------------------------------

def test_model_agnostic_accepts_any_scion():
    assert scion.is_genuine_scion("Scion FR-S 2013", None)
    assert scion.is_genuine_scion("clean xD, runs great", None)


def test_model_agnostic_rejects_non_scion():
    assert not scion.is_genuine_scion("2009 Honda Civic EX", None)


# ---- frs spelling variants ------------------------------------------------

def test_frs_spelling_variants():
    for t in ["Scion FR-S", "scion frs", "Scion FR S coupe"]:
        assert scion.is_genuine_scion(t, "frs"), t


# ---- batch filter ---------------------------------------------------------

def test_filter_scion_keeps_only_genuine():
    cards = [
        {"text": "2008 Scion tC", "url": "u1"},
        {"text": "2012 Toyota Camry", "url": "u2"},
        {"text": "2010 tC coupe", "url": "u3"},
        {"text": "2011 Scion xB", "url": "u4"},  # wrong model
    ]
    kept = scion.filter_scion(cards, "tc")
    assert [c["url"] for c in kept] == ["u1", "u3"]


if __name__ == "__main__":
    import sys
    sys.exit(__import__("pytest").main([__file__, "-q"]))
