#!/usr/bin/env python3
"""Craigslist source helpers for car-hunt.

Two jobs, both tested:

1. ``extract_listing_urls(html)`` — pull individual listing URLs out of a
   Craigslist search-results page, tolerant of the post-redesign gallery markup
   (absolute or root-relative ``/{sub}/d/{slug}/{id}.html`` anchors).

2. ``diagnose(html, other_sources_total)`` — decide whether a *zero-listing*
   result is genuine "no inventory" or (far more likely) Craigslist blocking /
   JS-gating the request. This is the guard issue #30 asks for: a run that pulls
   0 from Craigslist while other sources returned listings is almost certainly
   broken, not empty, and must be surfaced as such instead of silently logged as
   "no results".

The modern ``/search/cta`` page is a JS app: a plain WebFetch gets back a thin
HTML shell (~a few KB, no listing anchors). That shell is the signature of
gating, and ``diagnose`` keys off it (size + anchor count), not off a brittle
single CSS selector.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Individual CL listing URLs look like:
#   https://atlanta.craigslist.org/cto/d/decatur-2009-honda-civic/7712345678.html
#   /ctd/d/some-slug/7712345678.html        (root-relative, same page)
# The stable, ID-bearing tail is `/d/<slug>/<digits>.html`. We anchor on that
# rather than the section code (cto/ctd/cta) so a section rename can't break us.
_LISTING_RE = re.compile(
    r'href="(?P<url>(?:https?://[a-z0-9.-]+\.craigslist\.org)?/[a-z]{3}/d/[^"\s]+?/\d+\.html)"',
    re.IGNORECASE,
)

# A real results page advertises its count ("1 - 120 of 340" / "340 results").
_RESULT_COUNT_RE = re.compile(r"(\d[\d,]*)\s*results?", re.IGNORECASE)
# Craigslist's honest empty state.
_NO_RESULTS_RE = re.compile(r"no results|0 results|nothing found", re.IGNORECASE)

# Below this many bytes a search page is a gated/JS shell, not real results.
THIN_HTML_BYTES = 20_000


def extract_listing_urls(html: str, *, region: str | None = None) -> list[str]:
    """Return de-duplicated individual listing URLs found in search-page HTML.

    Root-relative hrefs are absolutized against ``region`` (e.g. "atlanta") when
    given, so callers get fetchable URLs. Order is preserved (first-seen).
    """
    seen: dict[str, None] = {}
    for m in _LISTING_RE.finditer(html or ""):
        url = m.group("url")
        if url.startswith("/") and region:
            url = f"https://{region}.craigslist.org{url}"
        seen.setdefault(url, None)
    return list(seen)


def result_count(html: str) -> int | None:
    """The advertised total result count, if the page states one."""
    m = _RESULT_COUNT_RE.search(html or "")
    return int(m.group(1).replace(",", "")) if m else None


@dataclass
class Diagnosis:
    status: str          # "ok" | "empty" | "blocked_or_gated"
    listings: int
    bytes: int
    detail: str

    @property
    def blocked(self) -> bool:
        return self.status == "blocked_or_gated"


def diagnose(html: str, *, other_sources_total: int = 0) -> Diagnosis:
    """Classify a Craigslist search-page fetch.

    - ``ok``               — listing anchors were found.
    - ``empty``            — the page explicitly says no results (genuine).
    - ``blocked_or_gated`` — 0 listings with no honest empty-state: a thin/JS
      shell, or 0-from-CL while other sources returned inventory. This is the
      "do not treat as no-inventory" signal issue #30 wants surfaced.
    """
    html = html or ""
    n = len(html)
    urls = extract_listing_urls(html)
    if urls:
        return Diagnosis("ok", len(urls), n, f"{len(urls)} listing URLs extracted")

    # No listings. Is it an honest empty result, or a gated shell?
    if _NO_RESULTS_RE.search(html) and n >= THIN_HTML_BYTES:
        return Diagnosis("empty", 0, n, "page reports no results (genuine empty)")

    reasons = []
    if n < THIN_HTML_BYTES:
        reasons.append(f"thin HTML ({n} bytes < {THIN_HTML_BYTES}) — likely JS/bot gate")
    if other_sources_total > 0:
        reasons.append(
            f"0 from Craigslist while other sources returned {other_sources_total} — "
            "likely blocked, NOT empty inventory")
    if not reasons:
        reasons.append("0 listing anchors and no honest empty-state marker")
    return Diagnosis("blocked_or_gated", 0, n, "; ".join(reasons))


if __name__ == "__main__":  # tiny CLI: `cat page.html | craigslist.py [other_total]`
    import sys
    other = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    d = diagnose(sys.stdin.read(), other_sources_total=other)
    print(f"{d.status}: {d.detail}")
    sys.exit(2 if d.blocked else 0)
