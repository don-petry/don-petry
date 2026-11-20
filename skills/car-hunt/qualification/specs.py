"""Per-domain qualification spec — the seam that replaces hardcoded car slots.

A domain "pack" supplies the qualification questions; everything else in the
qualification engine (the FSM, the send-eligibility gate, the drafts) is
identical across domains. This module is what makes the engine domain-agnostic:
the Minimal-N slots and their question text used to be hardcoded constants in
`ledger.py` (`REQUIRED_SLOTS` / `SLOT_QUESTIONS`, car-only); now they live in a
`QualSpec` that a `Conversation` carries by `domain`.

Pure data + a tiny registry, no determination logic. The only I/O is reading the
buyer's title state once at import (env `CAR_HUNT_TITLE_STATE`, else
`location.state_name` in the skill's `config/household.yaml`), so the car `title`
question can name it.

(Phase 0 of the goods-hunt generalization — see skills/goods-hunt/DESIGN.md.
Specs live here as Python for now; a later phase can load them from the markdown
domain packs without changing any call site, since the engine only ever asks a
`Conversation` for its spec.)
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

HOUSEHOLD_CONFIG = Path(__file__).resolve().parent.parent / "config" / "household.yaml"


def load_title_state(path: Path = HOUSEHOLD_CONFIG) -> Optional[str]:
    """The buyer's state for the title question, or None for a state-neutral one.

    Order: env `CAR_HUNT_TITLE_STATE` (empty string = neutral), then
    `location.state_name` in config/household.yaml. PyYAML is optional — without
    it a line scan reads the key. Missing/unreadable config → None.
    """
    env = os.environ.get("CAR_HUNT_TITLE_STATE")
    if env is not None:
        return env.strip() or None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        import yaml  # optional dependency

        data = yaml.safe_load(text) or {}
        value = (data.get("location") or {}).get("state_name")
    except Exception:
        m = re.search(r"^\s+state_name:\s*[\"']?([^\"'#\n]*?)[\"']?\s*(?:#.*)?$", text, re.M)
        value = m.group(1) if m else None
    value = str(value).strip() if value else ""
    return value or None


def title_question(state: Optional[str]) -> str:
    """Seller question for the `title` slot, naming the buyer's state when known."""
    if state:
        return f"Is the title from {state} and in your name and in hand?"
    return "Is the title clean, in your name, and in hand?"


class QualSpec(BaseModel):
    """The qualification questions for one domain.

    `required_slots` — the Minimal-N slot keys, in the order they are asked.
    `slot_questions` — one complete, standalone sentence per slot (so drafts can
                       put one question per line with a blank line between).
    """

    domain: str
    required_slots: Tuple[str, ...]
    slot_questions: Dict[str, str]

    def questions_for(self, names: List[str]) -> List[str]:
        return [self.slot_questions[n] for n in names if n in self.slot_questions]


# --- built-in domain specs -------------------------------------------------

# Cars: the original Minimal-3 (VIN, title, runs-and-drives). Verbatim text from
# the pre-generalization ledger.py constants — the parity gate depends on this.
# The title question names the buyer's state from config (see title_question).
CARS = QualSpec(
    domain="cars",
    required_slots=("vin", "title", "runs"),
    slot_questions={
        "vin": "Can you share the VIN, or a photo of the driver door-jamb sticker?",
        "title": title_question(load_title_state()),
        "runs": "Does it run and drive without issue?",
    },
)

# Tractors & attachments: hour-meter ≈ odometer, ownership/title, runs +
# hydraulics + PTO ≈ runs-and-drives. (Phase 1 — see domains/tractors.md.)
TRACTORS = QualSpec(
    domain="tractors",
    required_slots=("hours", "title", "runs"),
    slot_questions={
        "hours": "What does the hour-meter read, and is it the original meter?",
        "title": "Do you have clear ownership/a bill of sale in hand?",
        "runs": "Does it start cold, and do the hydraulics and PTO work without leaks or faults?",
    },
)

DEFAULT_DOMAIN = "cars"

REGISTRY: Dict[str, QualSpec] = {spec.domain: spec for spec in (CARS, TRACTORS)}


def get_spec(domain: str | None = None) -> QualSpec:
    """Resolve a domain's spec; unknown/empty domains fall back to cars.

    The fallback keeps legacy ledgers (which predate the `domain` field and so
    default to "cars") and any unexpected value working as the original car
    behavior, never crashing the qualification step.
    """
    return REGISTRY.get(domain or DEFAULT_DOMAIN, CARS)
