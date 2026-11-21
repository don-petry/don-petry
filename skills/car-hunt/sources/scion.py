#!/usr/bin/env python3
"""Scion (discontinued make) helpers for car-hunt — issue #31.

Facebook Marketplace dropped the make/model *facet* for Scion (Toyota killed the
brand in 2016), so the only way to find Scions on FB is a **free-text** search
(`/marketplace/{cityId}/search?query=Scion+tC`). Free-text search is fuzzy: it
returns plenty of non-Scion noise (random Toyotas, anything sharing a token).
This module post-filters those card texts down to *genuine* Scions of the
requested model, so they can flow into scoring instead of being dropped as
"mileage unavailable / not a match".

``is_genuine_scion(text, model)`` is the predicate; ``filter_scion`` applies it
to a list of {text, url, ...} cards.
"""
from __future__ import annotations

import re
from typing import Iterable

# Distinctive Scion model tokens. The hunt targets tC/xD, but recognizing the
# whole lineup lets us correctly REJECT a genuine-but-wrong-model Scion when a
# specific model was requested (e.g. an xB result for a "tC" query).
SCION_MODELS = {"tc", "xd", "xa", "xb", "iq", "ia", "im", "frs"}

# Other makes that FB's fuzzy search drags in. If one of these appears and there
# is no explicit "scion" token, it's noise, not a re-badged Scion listing.
_COMPETING_MAKES = re.compile(
    r"\b(toyota|honda|nissan|mazda|ford|chevy|chevrolet|hyundai|kia|subaru|"
    r"volkswagen|vw|bmw|civic|corolla|camry|accord)\b",
    re.IGNORECASE,
)
_SCION_WORD = re.compile(r"\bscion\b", re.IGNORECASE)


def _model_token(model: str) -> str:
    """Normalize a model string to its bare token: 'fr-s' -> 'frs', 'tC' -> 'tc'."""
    return re.sub(r"[^a-z0-9]", "", (model or "").lower())


def _has_model_token(text: str, token: str) -> bool:
    if token in {"frs"}:  # FR-S is written many ways
        return re.search(r"\bfr[\s-]?s\b", text, re.IGNORECASE) is not None
    return re.search(rf"\b{re.escape(token)}\b", text, re.IGNORECASE) is not None


def is_genuine_scion(text: str, model: str | None = None) -> bool:
    """True if ``text`` is a real Scion listing (of ``model`` when specified).

    Genuine when EITHER the word "Scion" is present, OR a distinctive Scion
    model token appears with no competing make to explain it away. When a
    ``model`` is given, that model's token must also be present — so a "tC"
    query won't accept an xB, and a "Toyota Camry" noise card is rejected.
    """
    text = text or ""
    has_scion = bool(_SCION_WORD.search(text))

    if model:
        token = _model_token(model)
        if token not in SCION_MODELS or not _has_model_token(text, token):
            return False
        # Right model token present. Accept if "Scion" is stated, or the token
        # stands alone without a competing make claiming it.
        return has_scion or not _COMPETING_MAKES.search(text)

    # No specific model requested: any Scion signal counts.
    if has_scion:
        return True
    if _COMPETING_MAKES.search(text):
        return False
    return any(_has_model_token(text, t) for t in SCION_MODELS)


def filter_scion(cards: Iterable[dict], model: str | None = None,
                 text_key: str = "text") -> list[dict]:
    """Keep only the cards whose ``text_key`` is a genuine Scion (of ``model``)."""
    return [c for c in cards if is_genuine_scion(c.get(text_key, ""), model)]


if __name__ == "__main__":  # quick check: `scion.py tc <<< "2008 Scion tC"`
    import sys
    mdl = sys.argv[1] if len(sys.argv) > 1 else None
    txt = sys.stdin.read()
    print("genuine" if is_genuine_scion(txt, mdl) else "noise")
