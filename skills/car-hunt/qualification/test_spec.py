"""Tests for the domain-agnostic qualification seam (specs + legacy migration).

These guard the Phase 0 generalization: the FSM/determination logic is unchanged,
but the slots it operates on now come from a per-domain QualSpec, and legacy
car ledgers must still load. Run: PYTHONPATH=. pytest test_spec.py
"""
from determination import assess, draft_followup, evaluate, next_questions
from ledger import Conversation, Ledger, Slot
from specs import TRACTORS, get_spec, load_title_state, title_question


# --- spec resolution -------------------------------------------------------

def test_default_domain_is_cars():
    c = Conversation(url="u")
    assert c.domain == "cars"
    assert c.spec().required_slots == ("vin", "title", "runs")


def test_unknown_domain_falls_back_to_cars():
    assert get_spec("does-not-exist").domain == "cars"
    assert get_spec(None).domain == "cars"


# --- a non-car domain drives different slots/questions ---------------------

def _tractor(**slots) -> Conversation:
    c = Conversation(url="https://fb/item/9", seller="T", vehicle="Kubota L3901",
                     domain="tractors")
    for name, verdict in slots.items():
        c.slots[name] = Slot(answered=True, value=verdict, verdict=verdict,
                             evidence=f"{name}:{verdict}")
    return c


def test_tractor_asks_its_own_slots_in_order():
    c = _tractor()
    assert evaluate(c) == "pending"
    assert next_questions(c) == ["hours", "title", "runs"]


def test_tractor_draft_uses_tractor_questions():
    c = _tractor(title="pass")  # hours + runs still unknown
    evaluate(c)
    draft = draft_followup(c)
    assert draft and "hour-meter" in draft          # tractor-specific wording
    assert "VIN" not in draft                         # not the car question


def test_tractor_all_pass_qualifies():
    c = _tractor(hours="pass", title="pass", runs="pass")
    determination, draft = assess(c)
    assert determination == "qualified"
    assert draft and "test drive" in draft


def test_tractor_hours_fail_disqualifies():
    c = _tractor(hours="fail", title="pass", runs="unknown")
    assert evaluate(c) == "disqualified"
    assert "hours" in (c.disqualify_reason or "")


# --- legacy ledger migration (the live conversations.json shape) -----------

LEGACY_JSON = """
{
  "conversations": {
    "https://fb/item/1": {
      "url": "https://fb/item/1",
      "seller": "Pat",
      "vehicle": "2008 Honda Accord",
      "vin": {"answered": true, "verdict": "pass", "evidence": "1HG..."},
      "title": {"answered": true, "verdict": "fail", "evidence": "rebuilt title"},
      "runs": {"answered": false, "verdict": "unknown"},
      "determination": "disqualified",
      "followup_sent": false
    }
  }
}
"""


def test_legacy_named_slots_migrate_into_slots_dict():
    led = Ledger.load(LEGACY_JSON)
    c = led.conversations["https://fb/item/1"]
    assert c.domain == "cars"                       # absent in legacy → defaults
    # the three named fields are now in the generic slots dict
    assert c.slot("vin").verdict == "pass"
    assert c.slot("title").verdict == "fail"
    assert c.slot("runs").verdict == "unknown"
    # and determination still reads them correctly
    assert evaluate(c) == "disqualified"
    assert "title" in (c.disqualify_reason or "")


def test_legacy_then_dump_is_new_format_and_round_trips():
    led = Ledger.load(LEGACY_JSON)
    dumped = led.dump()
    assert '"slots"' in dumped                       # rewritten to new shape
    # reloading the dumped (new-format) JSON preserves everything
    again = Ledger.load(dumped)
    c = again.conversations["https://fb/item/1"]
    assert c.slot("title").verdict == "fail"
    assert c.vehicle == "2008 Honda Accord"


def test_new_format_with_explicit_domain_round_trips():
    c = _tractor(hours="pass", title="pass", runs="pass")
    led = Ledger(conversations={c.url: c})
    again = Ledger.load(led.dump())
    rc = again.conversations[c.url]
    assert rc.domain == "tractors"
    assert rc.spec().required_slots == TRACTORS.required_slots
    assert evaluate(rc) == "qualified"


# --- migrator robustness (hardening, from review) --------------------------

def test_legacy_null_slot_field_is_skipped_not_crash():
    # a legacy field serialized as null must not crash ledger load (it'd fail
    # Slot validation); it should fall back to a default unknown slot.
    j = ('{"conversations":{"u":{"url":"u","vin":null,'
         '"title":{"verdict":"fail","evidence":"rebuilt"},'
         '"runs":{"verdict":"unknown"}}}}')
    c = Ledger.load(j).conversations["u"]
    assert c.slot("vin").verdict == "unknown"        # null → default, no crash
    assert c.slot("title").verdict == "fail"
    assert evaluate(c) == "disqualified"


def test_legacy_field_alongside_slots_is_merged_not_dropped():
    # a row with BOTH a slots dict and a leftover legacy field must not drop
    # the legacy field (which would silently lose a disqualifier).
    j = ('{"conversations":{"u":{"url":"u",'
         '"slots":{"vin":{"verdict":"pass"}},'
         '"title":{"verdict":"fail","evidence":"rebuilt"}}}}')
    c = Ledger.load(j).conversations["u"]
    assert c.slot("vin").verdict == "pass"           # explicit slot preserved
    assert c.slot("title").verdict == "fail"         # legacy field merged in
    assert evaluate(c) == "disqualified"


def test_migrator_does_not_mutate_caller_dict():
    import json
    raw = json.loads('{"url":"u","vin":{"verdict":"pass"},'
                     '"title":{"verdict":"pass"},"runs":{"verdict":"pass"}}')
    Conversation.model_validate(raw)
    assert "vin" in raw and "slots" not in raw       # caller's dict untouched


# --- the car title question names the buyer's state from config ------------

def test_title_question_names_state_when_known():
    assert title_question("Ohio") == "Is the title from Ohio and in your name and in hand?"


def test_title_question_is_state_neutral_without_config():
    assert title_question(None) == "Is the title clean, in your name, and in hand?"


def test_load_title_state_reads_location_state_name(tmp_path, monkeypatch):
    monkeypatch.delenv("CAR_HUNT_TITLE_STATE", raising=False)
    cfg = tmp_path / "household.yaml"
    cfg.write_text("location:\n  zip: \"00000\"\n  state_name: Ohio   # comment\n"
                   "jurisdiction:\n  state_name: Texas\n", encoding="utf-8")
    assert load_title_state(cfg) == "Ohio"
    assert load_title_state(tmp_path / "missing.yaml") is None


def test_load_title_state_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CAR_HUNT_TITLE_STATE", "Utah")
    assert load_title_state(tmp_path / "missing.yaml") == "Utah"
    monkeypatch.setenv("CAR_HUNT_TITLE_STATE", "")
    assert load_title_state(tmp_path / "missing.yaml") is None
