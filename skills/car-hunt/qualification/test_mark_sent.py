#!/usr/bin/env python3
"""Tests for URL-drift-tolerant send recording (the Eli double-send bug).

mark_sent() must record `followup_sent`/`closing_sent` even when the send
executor echoes a drifted Facebook URL in sent.json — otherwise a confirmed
send isn't recorded and the seller is re-messaged next run.

Run: python3 -m pytest skills/car-hunt/qualification/test_mark_sent.py -q
"""
from __future__ import annotations

import json
import pathlib
import tempfile

from ledger import Conversation, Ledger, canonical_listing_key
import qualify


# ---- canonical_listing_key ------------------------------------------------

def test_fb_item_variants_collapse_to_same_key():
    base = "https://www.facebook.com/marketplace/item/1646550739766408/"
    variants = [
        "https://www.facebook.com/marketplace/item/1646550739766408",          # no slash
        "https://www.facebook.com/marketplace/item/1646550739766408/?ref=search",  # query
        "https://m.facebook.com/marketplace/item/1646550739766408/",            # mobile host
        "https://web.facebook.com/marketplace/item/1646550739766408/?mibextid=x",  # share param
        "https://www.facebook.com/marketplace/item/1646550739766408/#scroll",   # fragment
    ]
    key = canonical_listing_key(base)
    assert key == "fb:item:1646550739766408"
    for v in variants:
        assert canonical_listing_key(v) == key, v


def test_different_items_do_not_collide():
    a = canonical_listing_key("https://www.facebook.com/marketplace/item/111/")
    b = canonical_listing_key("https://www.facebook.com/marketplace/item/222/")
    assert a != b


def test_non_fb_url_strips_query_slash_and_lowercases_host():
    a = canonical_listing_key("https://BHAM.craigslist.org/cto/d/x/7712345678.html?lang=en")
    b = canonical_listing_key("https://bham.craigslist.org/cto/d/x/7712345678.html/")
    assert a == b == "https://bham.craigslist.org/cto/d/x/7712345678.html"


def test_empty_url_is_empty_key():
    assert canonical_listing_key(None) == "" and canonical_listing_key("") == ""


# ---- Ledger.match ---------------------------------------------------------

def _ledger_with(url: str) -> Ledger:
    led = Ledger()
    led.conversations[url] = Conversation(url=url, domain="cars", seller="Eli")
    return led


def test_match_exact_then_canonical():
    url = "https://www.facebook.com/marketplace/item/777/"
    led = _ledger_with(url)
    assert led.match(url) is led.conversations[url]                       # exact
    assert led.match("https://m.facebook.com/marketplace/item/777?ref=x") \
        is led.conversations[url]                                          # drifted
    assert led.match("https://www.facebook.com/marketplace/item/999/") is None


# ---- mark_sent end-to-end (the regression) --------------------------------

def _run_mark_sent(ledger: Ledger, sent: list) -> Ledger:
    with tempfile.TemporaryDirectory() as d:
        lp = pathlib.Path(d) / "conversations.json"
        sp = pathlib.Path(d) / "sent.json"
        lp.write_text(ledger.dump())
        sp.write_text(json.dumps(sent))
        qualify.mark_sent(str(lp), str(sp))
        return Ledger.load(lp.read_text())


def test_followup_recorded_despite_drifted_url():
    ledger_url = "https://www.facebook.com/marketplace/item/1646550739766408/"
    led = _ledger_with(ledger_url)
    assert led.conversations[ledger_url].followup_sent is False
    # Executor echoed a drifted URL (query + no trailing slash + mobile host).
    sent = [{"url": "https://m.facebook.com/marketplace/item/1646550739766408?ref=search",
             "sent": True, "kind": "followup", "archived": False}]
    out = _run_mark_sent(led, sent)
    assert out.conversations[ledger_url].followup_sent is True   # was the bug: stayed False


def test_closing_recorded_and_followup_untouched():
    url = "https://www.facebook.com/marketplace/item/555/"
    led = _ledger_with(url)
    led.conversations[url].determination = "disqualified"
    sent = [{"url": "https://www.facebook.com/marketplace/item/555/?ref=x",
             "sent": True, "kind": "closing", "archived": True}]
    out = _run_mark_sent(led, sent)
    assert out.conversations[url].closing_sent is True
    assert out.conversations[url].followup_sent is False


def test_unconfirmed_send_is_not_recorded():
    url = "https://www.facebook.com/marketplace/item/555/"
    led = _ledger_with(url)
    sent = [{"url": url, "sent": False, "kind": "followup"}]
    out = _run_mark_sent(led, sent)
    assert out.conversations[url].followup_sent is False


if __name__ == "__main__":
    import sys
    sys.exit(__import__("pytest").main([__file__, "-q"]))
