"""Tests for the run-results normalizer (stdlib only).

Run: PYTHONPATH=. pytest test_normalize.py
"""
from normalize_results import normalize, CONTRACT_SOURCES, VALID_STATUS


def _valid(out):
    return (
        isinstance(out["totals"]["scored"], (int, float))
        and isinstance(out["totals"]["new"], (int, float))
        and isinstance(out["top_new"], list)
        and isinstance(out["inbox"], list)
        and isinstance(out["ip_blocking_observed"], bool)
        and isinstance(out["sources"], list)
        and len(out["sources"]) == 3
        and sorted(s["name"] for s in out["sources"]) == sorted(CONTRACT_SOURCES)
        and all(s["status"] in VALID_STATUS for s in out["sources"])
        and all(isinstance(s["listings_found"], (int, float)) for s in out["sources"])
    )


def test_drifted_output_becomes_valid():
    # the exact shape that broke run 27384566908
    drifted = {
        "listings_scored": 2,
        "new_listings_added": 2,
        "sources_searched": ["facebook", "craigslist", "autodev"],
        "outreach": {"sent": 0, "reason": "no new listings"},
        "messenger_threads_reviewed": 5,
    }
    out = normalize(drifted)
    assert _valid(out)
    assert out["totals"]["scored"] == 2 and out["totals"]["new"] == 2
    assert out["outreach"] == []          # object → empty array (no per-listing data)


def test_valid_contract_passthrough():
    good = {
        "totals": {"scored": 10, "new": 4},
        "top_new": [{"x": 1}],
        "sources": [
            {"name": "autodev", "status": "ok", "listings_found": 5},
            {"name": "craigslist", "status": "partial", "listings_found": 2},
            {"name": "facebook", "status": "ok", "listings_found": 3},
        ],
        "inbox": [{"url": "u", "slots": {}}],
        "ip_blocking_observed": False,
    }
    out = normalize(good)
    assert _valid(out)
    assert out["totals"] == {"scored": 10, "new": 4}
    assert len(out["inbox"]) == 1          # inbox + slots preserved for qualification


def test_garbage_becomes_minimal_skeleton():
    for junk in ({}, {"weird": True}, None):
        out = normalize(junk if isinstance(junk, dict) else {})
        assert _valid(out)
        assert out["totals"] == {"scored": 0, "new": 0}
        assert all(s["status"] == "skipped" for s in out["sources"])


def test_missing_source_filled_as_skipped():
    out = normalize({"sources_searched": ["facebook"]})
    assert _valid(out)
    by = {s["name"]: s for s in out["sources"]}
    assert by["facebook"]["status"] == "ok"
    assert by["autodev"]["status"] == "skipped"
    assert by["craigslist"]["status"] == "skipped"


def test_inbox_with_slots_preserved():
    out = normalize({"inbox": [{"url": "u", "human_led": False,
                                "slots": {"vin": {"verdict": "pass"}}}]})
    assert out["inbox"][0]["slots"]["vin"]["verdict"] == "pass"


def test_inbox_seller_vehicle_aliases_mapped():
    # the exact drift that orphaned conversations in run 27465869807:
    # the agent wrote seller/vehicle instead of the contract recipient/listing.
    out = normalize({"inbox": [
        {"url": "u", "seller": "Doodlebob",
         "vehicle": "2006 Honda Accord EX-L", "human_led": False},
    ]})
    e = out["inbox"][0]
    assert e["recipient"] == "Doodlebob"      # mapped from seller
    assert e["listing"] == "2006 Honda Accord EX-L"  # mapped from vehicle


def test_inbox_recipient_listing_take_precedence_over_aliases():
    out = normalize({"inbox": [
        {"url": "u", "recipient": "Real", "seller": "Alias",
         "listing": "Real Car", "vehicle": "Alias Car"},
    ]})
    e = out["inbox"][0]
    assert e["recipient"] == "Real" and e["listing"] == "Real Car"


def test_inbox_human_led_coerced_to_bool():
    out = normalize({"inbox": [{"url": "u"}]})  # human_led missing
    assert out["inbox"][0]["human_led"] is False
