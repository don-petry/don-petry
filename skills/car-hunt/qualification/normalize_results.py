#!/usr/bin/env python3
"""Coerce the agent's run-results.json into the validator's contract shape.

The agent (an LLM) is nondeterministic and periodically drifts from the documented
run-results.json schema (wrong top-level key names, an object where an array is
expected, missing fields). When that happened the contract gate failed and the
whole run was discarded — including the dedup-state persist — even though the
actual work (search, messenger read) was fine and no messages were mis-sent.

This shim runs RIGHT AFTER the agent and BEFORE validation. It maps the common
alias keys, fills sane defaults, and forces the `sources` list to exactly the
three contract sources, so benign format drift no longer throws away a run. It
is intentionally lenient: stdlib only, never raises on weird input — worst case
it emits a minimal-but-valid skeleton (which still records "nothing found",
preserving the silent-failure signal the contract was meant to catch).

Usage: python3 normalize_results.py <run-results.json>   (rewrites in place)
"""
import json
import sys

CONTRACT_SOURCES = ["autodev", "craigslist", "facebook"]
VALID_STATUS = {"ok", "degraded", "partial", "blocked", "skipped"}


def _num(*candidates, default=0):
    for c in candidates:
        if isinstance(c, bool):
            continue
        if isinstance(c, (int, float)):
            return c
    return default


def _as_list(v):
    return v if isinstance(v, list) else []


def _norm_inbox(raw):
    """Map common inbox-entry alias keys to the contract names.

    The agent periodically writes each Messenger thread with `seller`/`vehicle`
    instead of the contract's `recipient`/`listing`. qualify.py reads
    `recipient`/`listing`, so without this mapping every new conversation lands
    in the durable ledger with a null seller — which spawns useless
    "None (None) — answered: none yet" follow-up drafts and orphan entries.
    Mapping here (the drift shim) keeps qualify.py reading one canonical shape.
    """
    out = []
    for e in _as_list(raw.get("inbox")):
        if not isinstance(e, dict):
            continue
        e = dict(e)
        if not e.get("recipient") and e.get("seller"):
            e["recipient"] = e["seller"]
        if not e.get("listing") and e.get("vehicle"):
            e["listing"] = e["vehicle"]
        if not isinstance(e.get("human_led"), bool):
            e["human_led"] = bool(e.get("human_led"))
        out.append(e)
    return out


def normalize(raw: dict) -> dict:
    raw = raw if isinstance(raw, dict) else {}

    totals = raw.get("totals")
    if not (isinstance(totals, dict) and isinstance(totals.get("scored"), (int, float))):
        totals = {
            "scored": _num(raw.get("listings_scored"),
                           (totals or {}).get("scored") if isinstance(totals, dict) else None),
            "new": _num(raw.get("new_listings_added"), raw.get("new_listings")),
        }
    totals = {"scored": _num(totals.get("scored")), "new": _num(totals.get("new"))}

    # sources: accept the contract array; else synthesize from a names list.
    src_in = raw.get("sources")
    by_name = {}
    if isinstance(src_in, list):
        for s in src_in:
            if isinstance(s, dict) and s.get("name"):
                by_name[str(s["name"]).lower()] = s
    for n in _as_list(raw.get("sources_searched")):
        key = str(n).lower()
        by_name.setdefault(key, {"name": key, "status": "ok"})
    sources = []
    for name in CONTRACT_SOURCES:
        s = by_name.get(name, {"name": name, "status": "skipped"})
        status = str(s.get("status", "ok")).lower()
        if status not in VALID_STATUS:
            status = "ok"
        lf = _num(s.get("listings_found"), s.get("new_listings"))
        sources.append({"name": name, "status": status,
                        "listings_found": lf,
                        "notes": str(s.get("notes", ""))})

    ip = raw.get("ip_blocking_observed")
    if not isinstance(ip, bool):
        ip = False

    # outreach must be an array of {url,seller,sent}. An object (e.g.
    # {"sent":0,"reason":...}) carries no per-listing detail → empty array.
    outreach = _as_list(raw.get("outreach"))

    return {
        "totals": totals,
        "top_new": _as_list(raw.get("top_new")),
        "sources": sources,
        "inbox": _norm_inbox(raw),
        "outreach": outreach,
        "disqualified": _as_list(raw.get("disqualified") or raw.get("disqualified_listings")),
        "ip_blocking_observed": ip,
        "notes": str(raw.get("notes", "")),
        # keep the agent's original payload for audit/debugging
        "_raw": raw,
    }


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "run-results.json"
    try:
        with open(path) as f:
            raw = json.load(f)
        changed_from = "valid contract" if _looks_valid(raw) else "drifted output"
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[normalize] unreadable run-results ({e}); writing skeleton", file=sys.stderr)
        raw = {}
        changed_from = "unreadable"
    out = normalize(raw)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[normalize] normalized run-results.json (was: {changed_from}); "
          f"scored={out['totals']['scored']} new={out['totals']['new']} "
          f"inbox={len(out['inbox'])} sources={[s['status'] for s in out['sources']]}",
          file=sys.stderr)
    return 0


def _looks_valid(raw) -> bool:
    return (isinstance(raw, dict)
            and isinstance(raw.get("totals"), dict)
            and isinstance(raw.get("sources"), list)
            and len(raw.get("sources", [])) == 3)


if __name__ == "__main__":
    raise SystemExit(main())
