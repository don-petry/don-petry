"""Deterministic seller-qualification determination (python-statemachine).

The qualify/disqualify decision is intentionally NOT left to the LLM. The agent
fills the slots (it's the NLU); this finite-state machine turns the validated
slot verdicts into a determination with simple, auditable, unit-testable rules:

    qualifying ──(any slot fails)──▶ disqualified   (terminal)
    qualifying ──(all slots pass)─▶ qualified       (terminal)
    qualifying ──(otherwise)──────▶ stays pending

The machine is reconstructed from the ledger on every cold run (there is no
persistent process); `evaluate()` is idempotent — re-running on the same slots
yields the same determination.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from statemachine import State, StateMachine

from ledger import Conversation


class QualificationMachine(StateMachine):
    """One machine per conversation; guards read the conversation's slots."""

    qualifying = State(initial=True)
    qualified = State(final=True)
    disqualified = State(final=True)

    # A single recompute event with mutually-exclusive guards. Only defined
    # from `qualifying`; once terminal we never fire it (see evaluate() below),
    # so the determination is monotonic and idempotent.
    evaluate = (
        qualifying.to(disqualified, cond="any_fail")
        | qualifying.to(qualified, cond="all_pass")
        | qualifying.to.itself(internal=True)
    )

    def __init__(self, conv: Conversation):
        self.conv = conv
        # Always start fresh and recompute from the CURRENT slots, so the
        # determination is a pure function of what the seller has said so far.
        # This is self-correcting: if the agent misreads a slot one run and fixes
        # it the next, the determination recovers (no permanent kill from a
        # single bad read). A fresh machine fires `evaluate` exactly once.
        super().__init__()

    # ---- guards ----
    def any_fail(self) -> bool:
        return any(s.verdict == "fail" for s in self.conv.ordered_slots())

    def all_pass(self) -> bool:
        return all(s.verdict == "pass" for s in self.conv.ordered_slots())


def _state_to_determination(state_id: str) -> str:
    return {"qualifying": "pending"}.get(state_id, state_id)


def disqualify_reason(conv: Conversation) -> Optional[str]:
    """Human-readable reason built from the seller's own words on failed slots."""
    fails = [
        f"{name} — {conv.slot(name).evidence or conv.slot(name).value or 'failed'}"
        for name in conv.spec().required_slots
        if conv.slot(name).verdict == "fail"
    ]
    return "seller reply: " + "; ".join(fails) if fails else None


def evaluate(conv: Conversation) -> str:
    """Advance the FSM from the conversation's slots; write determination back.

    Returns the determination string (pending|qualified|disqualified) and
    mutates `conv.determination` / `conv.disqualify_reason` in place.
    """
    machine = QualificationMachine(conv)
    machine.evaluate()
    determination = _state_to_determination(machine.current_state.id)
    conv.determination = determination  # type: ignore[assignment]
    conv.disqualify_reason = (
        disqualify_reason(conv) if determination == "disqualified" else None
    )
    return determination


def next_questions(conv: Conversation) -> List[str]:
    """Required slot keys still unanswered, in ask-order (empty if none)."""
    return [
        name
        for name in conv.spec().required_slots
        if not conv.slot(name).answered or conv.slot(name).verdict == "unknown"
    ]


def draft_followup(conv: Conversation) -> Optional[str]:
    """Compose a draft follow-up asking ONLY the still-unanswered questions.

    Draft only — this text is surfaced for the user to send by hand; nothing
    here sends a message.
    """
    pending = next_questions(conv)
    if not pending:
        return None
    # One question per line, blank line between, for easy reading on a phone.
    questions = "\n\n".join(conv.spec().slot_questions[k] for k in pending)
    lead = (
        "Thanks! One quick thing before we come out:"
        if len(pending) == 1
        else "Thanks! A few quick things before we come out:"
    )
    return f"{lead}\n\n{questions}\n\nAppreciate it!"


def draft_schedule() -> str:
    """Draft sent once a conversation is qualified (user sends by hand)."""
    return (
        "That all sounds great!\n\n"
        "When could we come by to take a look and test drive?"
    )


# The single polite close-out sent (or drafted) when a seller's reply
# disqualifies the listing. Kept as a module constant so the verbatim executor
# sends exactly this text and it's trivial to tweak in one place.
CLOSING_MESSAGE = (
    "Thank you so much for the quick reply!\n\n"
    "It looks like this may not be a good fit for us, but I really appreciate "
    "your time. Best of luck with the sale!"
)


def draft_closing() -> str:
    """The courtesy closing message for a disqualified conversation."""
    return CLOSING_MESSAGE


# Dispositions that disqualify on their own (the seller's words close the door)
# even when no Minimal-3 slot is a hard `fail` — e.g. the car already sold, or
# the reply revealed a branded/lost title in passing.
DISQUALIFYING_DISPOSITIONS = {"sold", "revealed_disqualifier"}

# Never send a closing into these: don't engage a scammer, and don't ping a
# seller who simply went silent (a goodbye to a ghost is noise, not closure).
NO_CLOSING_DISPOSITIONS = {"scam", "ghosting"}


def closing_eligible(conv: Conversation, disposition: Optional[str],
                     human_led: bool) -> bool:
    """Deterministic gate: should we AUTO-SEND the closing + archive the thread?

    The disqualification mirror of `followup_eligible`. All conditions must
    hold; the decision lives here in tested code, not in the LLM.
    """
    if human_led:
        return False                       # never message a thread you're in
    if conv.closing_sent:
        return False                       # already closed once — don't re-send
    disp = (disposition or "").lower()
    if disp in NO_CLOSING_DISPOSITIONS:
        return False                       # don't engage scammers / ghosts
    # Disqualified by their answers (slot fail) OR by a closing disposition.
    return conv.determination == "disqualified" or disp in DISQUALIFYING_DISPOSITIONS


# Dispositions where the seller is engaged enough that asking the qualifying
# questions is appropriate. (Negotiating/ghosting/sold/scam are excluded.)
POSITIVE_DISPOSITIONS = {"available", "asking_question", "scheduling", "interested"}


def followup_eligible(conv: Conversation, disposition: Optional[str],
                      human_led: bool) -> bool:
    """Deterministic gate: should we AUTO-SEND a qualification follow-up?

    All conditions must hold. This is the safety control for send mode — the
    send decision lives here in tested code, not in the LLM.
    """
    if human_led:
        return False                       # never send into a thread you're in
    if conv.followup_sent:
        return False                       # already asked once — don't re-nag
    if conv.determination != "pending":
        return False                       # qualified/disqualified → no questions
    if (disposition or "").lower() not in POSITIVE_DISPOSITIONS:
        return False                       # only engaged, positive sellers
    if not next_questions(conv):
        return False                       # nothing left to ask
    return True


def assess(conv: Conversation) -> Tuple[str, Optional[str]]:
    """Full per-conversation pass: determination + the draft to surface.

    Returns (determination, draft_text|None).
    """
    determination = evaluate(conv)
    if determination == "pending":
        return determination, draft_followup(conv)
    if determination == "qualified":
        return determination, draft_schedule()
    return determination, None  # disqualified → no draft
