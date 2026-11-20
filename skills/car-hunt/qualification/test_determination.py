"""Deterministic unit tests for the qualification FSM (no LLM, no network).

Run:  PYTHONPATH=. pytest test_determination.py
The determination logic is pure Python, so these are the fast, reliable gate
on the qualify/disqualify decision — separate from the model-driven eval that
scores the agent's slot extraction.
"""
from ledger import Conversation, Slot
from specs import CARS
from determination import (
    CLOSING_MESSAGE,
    assess,
    closing_eligible,
    draft_closing,
    draft_followup,
    evaluate,
    followup_eligible,
    next_questions,
)


def conv(**slots) -> Conversation:
    c = Conversation(url="https://fb/item/1", seller="Test", vehicle="Civic")
    for name, verdict in slots.items():
        c.slots[name] = Slot(
            answered=True, value=verdict, verdict=verdict, evidence=f"{name}:{verdict}"
        )
    return c


def test_all_unknown_is_pending_and_asks_all_three():
    c = conv()
    assert evaluate(c) == "pending"
    assert next_questions(c) == ["vin", "title", "runs"]


def test_all_pass_is_qualified():
    c = conv(vin="pass", title="pass", runs="pass")
    assert evaluate(c) == "qualified"
    assert next_questions(c) == []


def test_any_fail_is_disqualified_title():
    c = conv(vin="pass", title="fail", runs="pass")
    assert evaluate(c) == "disqualified"
    assert "title" in (c.disqualify_reason or "")


def test_vin_refused_is_disqualified():
    c = conv(vin="fail", title="pass", runs="unknown")
    assert evaluate(c) == "disqualified"
    assert "vin" in (c.disqualify_reason or "")


def test_partial_answers_pending_asks_remainder_in_order():
    c = conv(title="pass")  # vin + runs still unknown
    assert evaluate(c) == "pending"
    assert next_questions(c) == ["vin", "runs"]


def test_fail_beats_unanswered():
    # a single fail disqualifies even with others unanswered
    c = conv(runs="fail")
    assert evaluate(c) == "disqualified"


def test_idempotent_same_slots_same_result():
    c = conv(vin="pass", title="pass", runs="pass")
    assert evaluate(c) == "qualified"
    assert evaluate(c) == "qualified"  # re-run on same slots, stable


def test_determination_is_pure_function_self_corrects():
    # determination reflects CURRENT slots: a corrected misread recovers.
    c = conv(title="fail")
    assert evaluate(c) == "disqualified"
    c.slots["title"] = Slot(answered=True, value="clean, in hand", verdict="pass",
                            evidence="clean title in my name")
    c.slots["vin"] = Slot(answered=True, verdict="pass")
    c.slots["runs"] = Slot(answered=True, verdict="pass")
    assert evaluate(c) == "qualified"  # self-corrects, not permanently killed


def test_draft_followup_single_question_form():
    c = conv(vin="pass", title="pass")  # only runs missing
    evaluate(c)
    draft = draft_followup(c)
    assert draft and "Does it run and drive without issue?" in draft
    assert "One quick thing" in draft


def test_draft_followup_multi_uses_line_breaks_per_question():
    c = conv()
    evaluate(c)
    draft = draft_followup(c)
    # every question present, each on its own line (blank line between)
    assert CARS.slot_questions["title"] in draft  # state-specific when config sets one
    assert "Does it run and drive without issue?" in draft
    assert "Can you share the VIN" in draft
    assert "\n\n" in draft
    assert "(1)" not in draft  # no inline numbering — whitespace instead


def test_assess_qualified_returns_schedule_draft():
    c = conv(vin="pass", title="pass", runs="pass")
    determination, draft = assess(c)
    assert determination == "qualified"
    assert draft and "test drive" in draft


def test_assess_disqualified_returns_no_draft():
    c = conv(title="fail")
    determination, draft = assess(c)
    assert determination == "disqualified"
    assert draft is None


# --- send-mode eligibility (the safety gate for auto-sending follow-ups) ---

def test_followup_eligible_typical_pending_positive():
    c = conv(title="pass")  # pending, vin/runs unanswered
    assess(c)
    assert followup_eligible(c, "available", human_led=False) is True


def test_followup_not_eligible_when_human_led():
    c = conv(title="pass")
    assess(c)
    assert followup_eligible(c, "available", human_led=True) is False


def test_followup_not_eligible_when_already_sent():
    c = conv(title="pass")
    assess(c)
    c.followup_sent = True
    assert followup_eligible(c, "available", human_led=False) is False


def test_followup_not_eligible_when_qualified_or_disqualified():
    q = conv(vin="pass", title="pass", runs="pass")
    assess(q)
    assert followup_eligible(q, "available", human_led=False) is False
    d = conv(title="fail")
    assess(d)
    assert followup_eligible(d, "available", human_led=False) is False


def test_followup_not_eligible_for_nonpositive_disposition():
    c = conv(title="pass")
    assess(c)
    for disp in ("negotiating", "ghosting", "sold", "unclear", "revealed_disqualifier"):
        assert followup_eligible(c, disp, human_led=False) is False


# --- closing-the-loop on disqualification (auto goodbye + archive) ---

def test_draft_closing_is_the_constant():
    assert draft_closing() == CLOSING_MESSAGE
    assert "good fit" in draft_closing()


def test_closing_eligible_on_answered_fail():
    c = conv(title="fail")
    assess(c)  # -> disqualified
    assert closing_eligible(c, "revealed_disqualifier", human_led=False) is True
    # even if the disposition reads merely "available", a slot fail still closes
    assert closing_eligible(conv_disq(), "available", human_led=False) is True


def conv_disq() -> Conversation:
    c = conv(runs="fail")
    assess(c)
    return c


def test_closing_eligible_on_sold_without_slot_fail():
    c = conv()  # all unknown -> pending
    assess(c)
    assert c.determination == "pending"
    assert closing_eligible(c, "sold", human_led=False) is True


def test_closing_not_eligible_for_scam_or_ghost_or_human_led():
    c = conv(title="fail")
    assess(c)
    assert closing_eligible(c, "scam", human_led=False) is False     # don't engage scammers
    assert closing_eligible(c, "ghosting", human_led=False) is False  # don't ping a ghost
    assert closing_eligible(c, "revealed_disqualifier", human_led=True) is False


def test_closing_not_eligible_for_live_or_already_closed():
    # a still-engaged pending/positive thread is not a close
    live = conv(title="pass")
    assess(live)
    assert closing_eligible(live, "available", human_led=False) is False
    # ask-once: already closed -> never again
    done = conv(title="fail")
    assess(done)
    done.closing_sent = True
    assert closing_eligible(done, "revealed_disqualifier", human_led=False) is False
