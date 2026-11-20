"""Typed seller-qualification ledger (Pydantic).

One `Conversation` per contacted listing, holding that domain's Minimal-N
qualification slots (e.g. cars: VIN/title/runs; tractors: hours/title/runs),
each filled by the agent's thread reading. The ledger is the durable,
human-diffable record persisted as JSON on the `car-hunt-state` git branch —
there is no database.

This module is pure data + validation. It performs NO I/O of its own (the
caller loads/saves JSON) and contains NO determination logic (that lives in
`determination.py`), so it is trivially importable and testable in a cold
batch job.

The slots are domain-agnostic: a `Conversation` carries its `domain`, and the
required-slot names + question text come from that domain's `QualSpec`
(`specs.py`). A `model_validator` migrates legacy ledgers — which stored the car
slots (`vin`/`title`/`runs`) as named top-level fields and had no `domain` — into
the generic `slots` dict, so existing `conversations.json` loads unchanged.
"""
from __future__ import annotations

import re
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from specs import CARS, QualSpec, get_spec

Verdict = Literal["pass", "fail", "unknown"]
DeterminationT = Literal["pending", "qualified", "disqualified"]

_FB_ITEM_RE = re.compile(r"/marketplace/item/(\d+)", re.IGNORECASE)


def canonical_listing_key(url: Optional[str]) -> str:
    """Normalize a listing URL to a stable identity key for matching.

    The ledger is keyed by the listing URL the agent reports when reading threads,
    but the *send executor* navigates the browser and may echo a drifted URL
    back in sent.json — Facebook appends `?ref=…`, flips the trailing slash, or
    swaps host (`www.`/`m.`/`web.`). An exact string compare then misses, so a
    confirmed send is never recorded as `followup_sent` and the seller gets
    re-messaged next run (the Eli double-send). Canonicalizing both sides before
    matching fixes that without weakening the "only record confirmed sends" rule.

    Facebook Marketplace URLs collapse to their immutable item id
    (`fb:item:{id}`); everything else is host-lowercased and stripped of query,
    fragment, and trailing slash.
    """
    if not url:
        return ""
    u = url.strip()
    m = _FB_ITEM_RE.search(u)
    if m:
        return f"fb:item:{m.group(1)}"
    u = u.split("#", 1)[0].split("?", 1)[0]
    u = re.sub(r"^(https?://)", lambda x: x.group(1).lower(), u)
    u = re.sub(r"^(https?://)([^/]+)",
               lambda x: x.group(1) + x.group(2).lower(), u)
    return u.rstrip("/")


# Back-compat re-exports: the car defaults used to be defined here. Anything that
# still imports these gets the cars spec's values. New code should resolve slots
# via a Conversation's `.spec()` instead.
REQUIRED_SLOTS: tuple[str, ...] = CARS.required_slots
SLOT_QUESTIONS: Dict[str, str] = CARS.slot_questions

# Legacy ledgers stored these as named top-level Slot fields on each
# conversation; the migrator moves them into the generic `slots` dict on load.
_LEGACY_CAR_SLOTS = ("vin", "title", "runs")


class Slot(BaseModel):
    """One qualification question and what the seller said about it.

    `verdict` is the decision-driving field:
      pass    — seller's answer clears the gate (e.g. clean title in hand)
      fail    — seller's answer is a hard disqualifier (rebuilt title, won't
                run, VIN refused, etc.)
      unknown — not answered yet (still pending) OR answered ambiguously
    `evidence` must be the seller's own words when answered (auditable).
    """

    answered: bool = False
    value: Optional[str] = None
    verdict: Verdict = "unknown"
    evidence: Optional[str] = None


class Conversation(BaseModel):
    """Qualification state for a single contacted listing."""

    url: str
    seller: Optional[str] = None
    vehicle: Optional[str] = None
    # Which domain's QualSpec governs this conversation's slots. Defaults to
    # "cars" so legacy ledgers (no domain field) behave exactly as before.
    domain: str = "cars"
    # Generic slot store, keyed by the domain's required-slot names.
    slots: Dict[str, Slot] = Field(default_factory=dict)
    determination: DeterminationT = "pending"
    disqualify_reason: Optional[str] = None
    # True once we have auto-sent the qualification follow-up. Prevents
    # re-asking the same seller on every run (the Messenger workflow runs every
    # ~3h — without this guard, send mode would spam sellers).
    followup_sent: bool = False
    # True once we have auto-sent the polite closing message after a
    # disqualification (and attempted to archive the thread). Same ask-once
    # guard as followup_sent: a disqualified conversation lives on in the ledger,
    # so without this the courtesy close would re-send every ~3h run.
    closing_sent: bool = False
    last_updated: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_car_slots(cls, data):
        """Lift legacy top-level car slots (vin/title/runs) into `slots`.

        Pre-generalization ledgers serialized the three car slots as named
        top-level fields; new ledgers use the `slots` dict. Merge any legacy
        top-level slot fields into `slots` so existing `conversations.json` on
        car-hunt-state loads without data loss — even a partially-migrated row
        that already carries a `slots` key (an explicit `slots` entry always
        wins; legacy fields only fill slots that are missing). Skips null legacy
        values (they'd fail Slot validation), and never mutates the caller's
        dict. No-op once migrated, so dump()→load() round-trips are idempotent.
        """
        if not isinstance(data, dict):
            return data
        legacy = {name: data[name] for name in _LEGACY_CAR_SLOTS
                  if data.get(name) is not None}
        if not legacy:
            return data
        data = dict(data)                       # copy — don't mutate the caller
        slots = dict(data.get("slots") or {})
        for name, value in legacy.items():
            data.pop(name, None)
            slots.setdefault(name, value)       # explicit slot wins; legacy fills gaps
        data["slots"] = slots
        return data

    def spec(self) -> QualSpec:
        return get_spec(self.domain)

    def slot(self, name: str) -> Slot:
        """Return the slot by name, defaulting to an empty (unknown) Slot."""
        return self.slots.get(name) or Slot()

    def ordered_slots(self) -> List[Slot]:
        """The domain's required slots, in ask-order."""
        return [self.slot(n) for n in self.spec().required_slots]


class Ledger(BaseModel):
    """The whole conversation ledger, keyed by listing URL."""

    conversations: Dict[str, Conversation] = Field(default_factory=dict)

    # ---- (de)serialization helpers: JSON in, JSON out, no DB ----
    @classmethod
    def load(cls, text: Optional[str]) -> "Ledger":
        if not text or not text.strip():
            return cls()
        return cls.model_validate_json(text)

    def dump(self) -> str:
        return self.model_dump_json(indent=2, exclude_none=False)

    def upsert(self, url: str, **kw) -> Conversation:
        conv = self.conversations.get(url)
        if conv is None:
            conv = Conversation(url=url, **kw)
            self.conversations[url] = conv
        else:
            for k, v in kw.items():
                if v is not None and getattr(conv, k, None) in (None, ""):
                    setattr(conv, k, v)
        return conv

    def match(self, url: Optional[str]) -> Optional[Conversation]:
        """Find a conversation by URL, tolerant of FB/redirect URL drift.

        Exact key first (fast path); otherwise compare canonical listing keys so
        a drifted send-executor URL still resolves to the right conversation.
        """
        if url in self.conversations:
            return self.conversations[url]
        key = canonical_listing_key(url)
        if not key:
            return None
        for conv in self.conversations.values():
            if canonical_listing_key(conv.url) == key:
                return conv
        return None
