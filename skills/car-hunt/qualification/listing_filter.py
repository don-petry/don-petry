#!/usr/bin/env python3
"""Deterministic listing-content disqualifier — the PRE-CONTACT gate.

Why this exists: the seller-reply qualification engine (determination.py)
already moved the consequential "should we keep this seller?" decision out of
LLM judgment and into tested Python. The *pre-contact* decision — "should we
even message this seller?" — was still pure LLM judgment against a prose
keyword list in SKILL.md Step 2, and it missed a listing whose description
plainly said the car doesn't run. This module makes that gate deterministic
and unit-tested so a non-running / parts-only / branded-title / scam listing
can never receive an opener.

Run the full scraped description (title + structured fields + seller's
free-form text) through `disqualifying_reason(text)`. If it returns a string,
the listing is disqualified for that reason and must NOT be contacted.

CLI (used by the workflow as a hard gate before any opener send):
    printf '%s' "$DESCRIPTION" | python3 listing_filter.py
    -> prints "OK" and exits 0 when clear
    -> prints "DISQUALIFIED: <reason>" and exits 1 when it should be skipped
"""
from __future__ import annotations

import re
import sys
from typing import List, Optional, Tuple

# A word/phrase right before a hit that flips a bad term into a good one:
# "no salvage", "not running"->(handled), "never overheats", "doesn't knock",
# "without rust", "zero issues". `n't` covers doesn't/isn't/won't via the
# trailing apostrophe-t.
NEGATORS = r"(?:no|not|never|without|zero|isn'?t|aren'?t|wasn'?t|don'?t|doesn'?t|didn'?t|won'?t|n'?t)"
# A repair/resolution word right after a symptom that means it was fixed:
# "head gasket replaced", "new transmission", "engine rebuilt".
RESOLUTION = r"(?:replaced|rebuilt|brand[-\s]?new|\bnew\b|done|fixed|repaired|serviced|installed|redone|already\s+\w+)"

# Symptom terms whose meaning flips when a repair word follows (a fixed
# head gasket is fine; a present one is a red flag). Negation guard applies to
# ALL families; the resolution guard applies only to these.
_RESOLVABLE = {"non-running"}

# (family label, [regex patterns]). First matching family wins.
_FAMILIES: List[Tuple[str, List[str]]] = [
    ("non-running", [
        r"do(?:es)?n'?t\s+run\b",
        r"\bnot\s+runn?ing\b",
        r"\bnon[-\s]?runn?ing\b",
        r"\bnon[-\s]?runner\b",
        r"\bwon'?t\s+run\b",
        r"\bwill\s+not\s+run\b",
        r"\b(?:does\s+)?not\s+run\b",
        r"do(?:es)?n'?t\s+(?:start|crank|turn\s+over|move|drive|shift)\b",
        r"\bwon'?t\s+(?:start|crank|turn\s+over|move|drive|shift)\b",
        r"\bno\s+(?:start|crank)\b",
        r"\bcranks?\s+but\s+won'?t\s+start\b",
        # needs a powertrain (but NOT "needs engine oil/filter/service/mount")
        r"\bneeds?\s+(?:a\s+)?(?:motor|engine|transmission|trans|head\s+gasket)"
        r"\b(?!\s*(?:oil|fluid|filter|mount|service|flush|coolant|gasket\s+done))",
        r"\bblown\s+(?:motor|engine|transmission|trans|head\s+gasket)\b",
        r"\b(?:motor|engine|transmission|trans)\s+(?:is\s+)?blown\b",
        r"\b(?:transmission|trans|engine|motor)\s+(?:is\s+)?(?:shot|gone|dead)\b",
        r"\bseized\b",
        r"\block(?:ed)?\s+up\b",
        r"\bmotor\s+locked\b",
        r"\brod\s+knock\b",
        r"\b(?:engine|motor)\s+knock\b",
        r"\bproject\s+car\b",
        r"\bmechanic'?s?\s+special\b",
        r"\bparts?\s+(?:car|only|or\s+repair)\b",
        r"\bfor\s+parts\b",
        r"\bneeds?\s+work\s+to\s+run\b",
        r"\bnon[-\s]?op(?:erational)?\b",
        r"\bneeds?\s+(?:to\s+be\s+)?towed\b",
        r"\bmust\s+be\s+towed\b",
        r"\bran\s+when\s+parked\b",
    ]),
    ("branded-title", [
        r"\bsalvage\b",
        r"\brebuilt\s+title\b",
        r"\bbranded\s+title\b",
        r"\bjunk\s+title\b",
        r"\bflood(?:ed)?\s+title\b",
        r"\bno\s+title\b",
        r"\blost\s+title\b",
        r"\bbill\s+of\s+sale\s+only\b",
        r"\btitle\s+(?:is\s+)?(?:not\s+in|isn'?t\s+in)\s+my\s+name\b",
    ]),
    ("scam-signal", [
        r"\bzelle\b",
        r"\bcash\s*app\b",
        r"\bvenmo\s+(?:deposit|first|before)\b",
        r"\bwire\s+(?:transfer|money|the)\b",
        r"\bgift\s*cards?\b",
        r"\bshipping\s+(?:available|only|included)\b",
        r"\bwill\s+ship\b",
        r"\bdeposit\s+to\s+hold\b",
        r"\bmessenger\s+(?:is\s+)?(?:broken|not\s+working)\b",
        r"\bemail\s+(?:me\s+)?(?:only|at)\b",
    ]),
]

# Pre-compile.
_COMPILED: List[Tuple[str, List[re.Pattern]]] = [
    (label, [re.compile(p, re.IGNORECASE) for p in pats]) for label, pats in _FAMILIES
]
_NEG_RE = re.compile(NEGATORS + r"\s+(?:\S+\s+){0,2}$", re.IGNORECASE)
_RES_RE = re.compile(r"^(?:\s+\S+){0,3}\s+" + RESOLUTION, re.IGNORECASE)


def _negated(text: str, start: int) -> bool:
    """True if a negator sits within ~2 words before the match (no salvage)."""
    pre = text[max(0, start - 28):start]
    return _NEG_RE.search(pre) is not None


def _resolved(text: str, end: int) -> bool:
    """True if a repair word follows within ~3 words (head gasket replaced)."""
    post = text[end:end + 40]
    return _RES_RE.search(post) is not None


def disqualifying_reason(text: Optional[str]) -> Optional[str]:
    """Return 'family: matched phrase' if the listing must NOT be contacted.

    Scans the full concatenated listing text. Applies a negation guard to every
    family (so "clean title, not salvage" and "no knocking" stay clear) and a
    resolution guard to non-running symptoms (so "head gasket replaced" and
    "new transmission" stay clear). Returns None when the listing is clear.
    """
    if not text:
        return None
    for label, patterns in _COMPILED:
        for rx in patterns:
            for m in rx.finditer(text):
                if _negated(text, m.start()):
                    continue
                if label in _RESOLVABLE and _resolved(text, m.end()):
                    continue
                phrase = re.sub(r"\s+", " ", m.group(0)).strip().lower()
                return f"{label}: \"{phrase}\""
    return None


def is_contactable(text: Optional[str]) -> bool:
    """Convenience inverse of disqualifying_reason (True = safe to contact)."""
    return disqualifying_reason(text) is None


def main() -> int:
    text = sys.stdin.read()
    reason = disqualifying_reason(text)
    if reason:
        print(f"DISQUALIFIED: {reason}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
