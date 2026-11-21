#!/usr/bin/env python3
"""Tests for the Craigslist source guard (issue #30).

Run: python3 -m pytest skills/car-hunt/sources/test_craigslist.py -q
"""
from __future__ import annotations

import pathlib

import craigslist as cl

HERE = pathlib.Path(__file__).parent
GALLERY = (HERE / "testdata" / "search-results-gallery.html").read_text()
SHELL = (HERE / "testdata" / "blocked-shell.html").read_text()


# ---- extraction -----------------------------------------------------------

def test_extracts_absolute_and_relative_listing_urls():
    urls = cl.extract_listing_urls(GALLERY, region="atlanta")
    assert urls == [
        "https://atlanta.craigslist.org/cto/d/decatur-2009-honda-civic-lx/7712345678.html",
        "https://atlanta.craigslist.org/cto/d/marietta-2011-toyota-camry-le/7798765432.html",
        "https://atlanta.craigslist.org/ctd/d/roswell-2008-honda-accord-exl/7701112223.html",
    ]


def test_extraction_is_section_code_agnostic():
    # A future section rename (cta/cto/ctd/xyz) must still match on /d/<id>.html.
    html = '<a href="/xyz/d/some-slug/7700000001.html">x</a>'
    assert cl.extract_listing_urls(html, region="atlanta") == [
        "https://atlanta.craigslist.org/xyz/d/some-slug/7700000001.html"
    ]


def test_no_false_positive_on_non_listing_links():
    html = '<a href="https://atlanta.craigslist.org/search/cta?query=honda">search</a>'
    assert cl.extract_listing_urls(html) == []


def test_dedupes_repeated_urls():
    one = '<a href="/cto/d/s/7700000002.html">a</a>'
    assert len(cl.extract_listing_urls(one + one, region="atlanta")) == 1


# ---- diagnosis / the guard ------------------------------------------------

def test_gallery_with_listings_is_ok():
    d = cl.diagnose(GALLERY, other_sources_total=0)
    assert d.status == "ok" and d.listings == 3 and not d.blocked


def test_thin_shell_is_blocked_even_with_no_other_sources():
    d = cl.diagnose(SHELL, other_sources_total=0)
    assert d.blocked and "thin HTML" in d.detail


def test_zero_from_cl_while_others_have_inventory_is_blocked():
    # A full-size page that yielded nothing, but Auto.dev/FB returned 24.
    big_but_empty = "<html>" + ("<div>filler</div>" * 4000) + "</html>"
    assert len(big_but_empty) >= cl.THIN_HTML_BYTES
    d = cl.diagnose(big_but_empty, other_sources_total=24)
    assert d.blocked and "other sources returned 24" in d.detail


def test_genuine_empty_is_not_flagged_blocked():
    page = "<html>" + ("<div>chrome</div>" * 4000) + "<p>no results</p></html>"
    assert len(page) >= cl.THIN_HTML_BYTES
    d = cl.diagnose(page, other_sources_total=0)
    assert d.status == "empty" and not d.blocked


def test_result_count_parsed():
    assert cl.result_count("showing 1 - 120 of 340 results") == 340
    assert cl.result_count("no count here") is None


if __name__ == "__main__":
    import sys
    sys.exit(__import__("pytest").main([__file__, "-q"]))
