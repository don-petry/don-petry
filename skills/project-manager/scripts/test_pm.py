#!/usr/bin/env python3
"""Tests for pm.py. Run: python3 skills/project-manager/scripts/test_pm.py"""

import copy
import datetime as dt
import json
import os
import sys
import unittest

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pm  # noqa: E402

TODAY = dt.date(2026, 9, 12)

SAMPLE = {
    "id": "sample",
    "title": "Sample project",
    "status": "active",
    "owners": ["Parent A"],
    "notes_root": "01_Household/sample",
    "runtime": "cloud",
    "charter": {"goal": "Prove the engine"},
    "cadence": {"urgency_window_days": 10},
    "watch": {"parties": [
        {"name": "Silent Co", "waiting_on": "a quote", "last_heard": "2026-09-01", "silent_after_days": 7},
        {"name": "Chatty Co", "waiting_on": "a quote", "last_heard": "2026-09-10", "silent_after_days": 7},
        {"name": "Closed Co", "waiting_on": "nothing", "last_heard": "2026-08-01", "silent_after_days": 7,
         "status": "done"},
    ]},
    "decisions": [
        {"id": "D1", "text": "Roof is metal, not shingle", "status": "DECIDED", "date": "2026-07-09"},
        {"id": "D2", "text": "Which carrier for the homes", "status": "OPEN"},
    ],
    "actions": [
        {"id": "A1", "text": "Chase the bid", "owner": "Parent A", "due": dt.date(2026, 9, 15), "status": "open"},
        {"id": "A2", "text": "Pay | invoice", "owner": "Parent A", "due": "2026-09-10", "status": "waiting"},
        {"id": "A3", "text": "Done thing", "owner": "Parent A", "due": "2026-09-01", "status": "done"},
        {"id": "A4", "text": "No date yet", "owner": "Parent A", "status": "open"},
    ],
    "clocks": [
        {"id": "C1", "due": "2026-10-12", "item": "Carrier must answer", "owner": "Insurer"},
        {"id": "C2", "due": "2026-09-13", "item": "Due tomorrow", "owner": "Parent A"},
    ],
    "questions": [
        {"id": "Q1", "text": "Employee ID?", "for": "Parent A", "blocking": "A1", "raised": "2026-09-12"},
        {"id": "Q2", "text": "Nice to know", "for": "Parent A", "raised": "2026-09-12"},
        {"id": "Q3", "text": "Answered", "status": "answered"},
    ],
    "needs_local": [{"id": "L1", "task": "Check LinkedIn", "raised": "2026-09-12"}],
}


def sample():
    return copy.deepcopy(SAMPLE)


class Validate(unittest.TestCase):
    def test_sample_is_valid(self):
        self.assertEqual(pm.validate(sample()), [])

    def test_missing_required_and_bad_enums(self):
        d = sample()
        del d["charter"]
        d["status"] = "someday"
        d["runtime"] = "laptop"
        errors = " ".join(pm.validate(d))
        self.assertIn("charter", errors)
        self.assertIn("status must be", errors)
        self.assertIn("runtime must be", errors)

    def test_duplicate_ids(self):
        d = sample()
        d["actions"].append({"id": "A1", "text": "dup"})
        self.assertTrue(any("duplicate id" in e for e in pm.validate(d)))

    def test_bad_dates(self):
        d = sample()
        d["clocks"][0]["due"] = "on arrival"
        d["watch"]["parties"][0]["last_heard"] = "last week"
        errors = pm.validate(d)
        self.assertTrue(any("C1" in e and "due" in e for e in errors))
        self.assertTrue(any("last_heard" in e for e in errors))

    def test_bad_statuses(self):
        d = sample()
        d["decisions"][1]["status"] = "maybe"
        d["actions"][0]["status"] = "sort of"
        errors = " ".join(pm.validate(d))
        self.assertIn("decision D2", errors)
        self.assertIn("action A1", errors)


class DecidedLock(unittest.TestCase):
    def test_unchanged_is_fine(self):
        self.assertEqual(pm.decided_changes(sample(), sample()), [])

    def test_whitespace_only_change_is_fine(self):
        new = sample()
        new["decisions"][0]["text"] = "Roof is  metal,\nnot shingle"
        self.assertEqual(pm.decided_changes(sample(), new), [])

    def test_removed(self):
        new = sample()
        new["decisions"] = new["decisions"][1:]
        self.assertIn("removed", " ".join(pm.decided_changes(sample(), new)))

    def test_reopened(self):
        new = sample()
        new["decisions"][0]["status"] = "OPEN"
        self.assertIn("reopened", " ".join(pm.decided_changes(sample(), new)))

    def test_reworded(self):
        new = sample()
        new["decisions"][0]["text"] = "Roof is shingle"
        self.assertIn("text has changed", " ".join(pm.decided_changes(sample(), new)))

    def test_open_decisions_can_change_and_be_decided(self):
        new = sample()
        new["decisions"][1] = {"id": "D2", "text": "Homes move to Safeco", "status": "DECIDED", "date": "2026-09-12"}
        self.assertEqual(pm.decided_changes(sample(), new), [])


class Clocks(unittest.TestCase):
    def test_buckets(self):
        r = pm.clocks(sample(), TODAY)
        self.assertEqual([x["id"] for x in r["overdue"]], ["A2"])
        self.assertEqual([x["id"] for x in r["urgent"]], ["C2", "A1"])
        self.assertEqual([x["id"] for x in r["upcoming"]], ["C1"])
        self.assertNotIn("A3", str(r))  # closed
        self.assertNotIn("A4", str(r))  # undated

    def test_silent_parties(self):
        r = pm.clocks(sample(), TODAY)
        self.assertEqual([p["name"] for p in r["silent_parties"]], ["Silent Co"])
        self.assertEqual(r["silent_parties"][0]["days_silent"], 11)

    def test_questions_and_local(self):
        r = pm.clocks(sample(), TODAY)
        self.assertEqual(r["open_questions"], 2)
        self.assertEqual([q["id"] for q in r["blocking_questions"]], ["Q1"])
        self.assertEqual(r["needs_local"], 1)

    def test_keys_and_first_run_escalates(self):
        r = pm.clocks(sample(), TODAY)
        self.assertEqual(set(r["escalate_keys"]), {
            "action:A2:overdue", "clock:C2:due-tomorrow", "action:A1:urgent", "question:Q1",
            "silent:silent-co:2026-09-01"})
        self.assertEqual(r["verdict"], "escalate")

    def test_already_escalated_stays_quiet(self):
        d = sample()
        d["last_run"] = {"escalated": pm.clocks(d, TODAY)["escalate_keys"]}
        r = pm.clocks(d, TODAY)
        self.assertEqual(r["new_keys"], [])
        self.assertEqual(r["verdict"], "quiet")

    def test_worsening_state_escalates_again(self):
        d = sample()
        d["last_run"] = {"escalated": pm.clocks(d, TODAY)["escalate_keys"]}
        r = pm.clocks(d, TODAY + dt.timedelta(days=2))  # A1 now 1 day out; C2 overdue
        self.assertIn("action:A1:due-tomorrow", r["new_keys"])
        self.assertIn("clock:C2:overdue", r["new_keys"])
        self.assertEqual(r["verdict"], "escalate")

    def test_nothing_dated_is_quiet(self):
        d = sample()
        for key in ("actions", "clocks", "questions"):
            d[key] = []
        d["watch"] = {"parties": []}
        self.assertEqual(pm.clocks(d, TODAY)["verdict"], "quiet")


class Render(unittest.TestCase):
    INDEX = (
        "# Title\n\nHand-written intro.\n\n"
        "<!-- pm:begin status -->\nold status\n<!-- pm:end status -->\n\n"
        "## Analysis\n\nDo not touch this.\n\n"
        "<!-- pm:begin actions -->\n<!-- pm:end actions -->\n\n"
        "<!-- pm:begin questions -->\nstale\n<!-- pm:end questions -->\n"
    )

    def test_rewrites_only_marked_blocks(self):
        out, found = pm.render(sample(), self.INDEX)
        self.assertEqual(found, ["status", "actions", "questions"])
        self.assertIn("Hand-written intro.", out)
        self.assertIn("Do not touch this.", out)
        self.assertNotIn("old status", out)
        self.assertNotIn("stale", out)
        self.assertIn("| A1 | Chase the bid |", out)
        self.assertNotIn("Done thing", out)
        self.assertIn("1 closed action(s)", out)
        self.assertIn("**[Q1]** Employee ID?", out)
        self.assertNotIn("Answered", out)

    def test_idempotent(self):
        once, _ = pm.render(sample(), self.INDEX)
        twice, _ = pm.render(sample(), once)
        self.assertEqual(once, twice)

    def test_no_markers_is_noop(self):
        text = "# Nothing managed here\n"
        self.assertEqual(pm.render(sample(), text), (text, []))

    def test_pipes_are_escaped(self):
        out, _ = pm.render(sample(), self.INDEX)
        self.assertIn("Pay \\| invoice", out)

    def test_utf8_survives(self):
        d = sample()
        d["summary"] = "Roof — FORTIFIED ✅ · 12/15"
        out, _ = pm.render(d, self.INDEX)
        self.assertIn("Roof — FORTIFIED ✅ · 12/15", out)


class LastRun(unittest.TestCase):
    """Runs have hand-written at/runtime/escalated wrong; validate now catches it."""

    def run_errors(self, run, now=None):
        return pm.last_run_errors(run, now or dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.timezone.utc))

    def test_past_instant_is_fine(self):
        self.assertEqual(self.run_errors({"at": "2026-09-19T11:20:00Z", "runtime": "cloud"}), [])

    def test_future_stamp_is_rejected(self):
        errs = self.run_errors({"at": "2026-09-19T12:45:00Z"})
        self.assertTrue(any("future" in e for e in errs), errs)

    def test_naive_stamp_is_rejected(self):
        self.assertTrue(any("ISO-8601" in e for e in self.run_errors({"at": "2026-09-19 11:20:00"})))

    def test_offset_stamp_is_fine(self):
        self.assertEqual(self.run_errors({"at": "2026-09-19T06:20:00-05:00"}), [])

    def test_runtime_vocabulary(self):
        self.assertEqual(self.run_errors({"runtime": "interactive"}), [])
        self.assertTrue(self.run_errors({"runtime": "robot"}))

    def test_escalated_keys(self):
        ok = ["clock:C3:urgent", "action:A2:overdue", "question:Q5", "event:revised_plans:2026-09-17"]
        self.assertEqual(self.run_errors({"escalated": ok}), [])

    def test_escalated_key_drift_is_rejected(self):
        for bad in ["question:Q3:blocking", "escalate_when:revised_plans_09-17", "C3", "clock:C3"]:
            with self.subTest(bad=bad):
                self.assertTrue(self.run_errors({"escalated": [bad]}), bad)

    def test_validate_surfaces_last_run(self):
        data = sample()
        data["last_run"] = {"at": "2026-09-19T12:45:00Z", "escalated": ["question:Q3:blocking"]}
        errs = pm.validate(data, now=dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(len(errs), 2, errs)


class PartyStatus(unittest.TestCase):
    def test_declined_party_is_not_chased(self):
        data = sample()
        data["watch"]["parties"][0]["status"] = "declined"
        report = pm.clocks(data, TODAY)
        self.assertEqual(report["silent_parties"], [])

    def test_declined_is_valid_unknown_is_not(self):
        data = sample()
        data["watch"]["parties"][0]["status"] = "declined"
        self.assertEqual(pm.validate(data), [])
        data["watch"]["parties"][0]["status"] = "ghosted"
        self.assertTrue(any("status must be one of" in e for e in pm.validate(data)))

    def test_trailing_comment_on_status_is_tolerated(self):
        data = sample()
        data["watch"]["parties"][0]["status"] = "done   # fee waived"
        self.assertEqual(pm.validate(data), [])


class FrontMatter(unittest.TestCase):
    NOTE = "---\ntitle: \"X\"\ncreated: 2026-07-05T00:00:00Z\nmodified: 2026-09-13T00:00:00Z\n---\n\n# X\n"

    def test_bumps_modified(self):
        out = pm.bump_modified(self.NOTE, dt.date(2026, 9, 19))
        self.assertIn("modified: 2026-09-19T00:00:00Z", out)
        self.assertIn("created: 2026-07-05T00:00:00Z", out)

    def test_idempotent_same_day(self):
        once = pm.bump_modified(self.NOTE, dt.date(2026, 9, 19))
        self.assertEqual(once, pm.bump_modified(once, dt.date(2026, 9, 19)))

    def test_no_frontmatter_untouched(self):
        body = "# X\n\nmodified: never\n"
        self.assertEqual(pm.bump_modified(body, dt.date(2026, 9, 19)), body)


class Files(unittest.TestCase):
    def test_yaml_dates_load_as_dates(self):
        loaded = yaml.safe_load("due: 2026-10-12\n")
        self.assertEqual(pm.as_date(loaded["due"]), dt.date(2026, 10, 12))

    def test_template_is_valid(self):
        path = os.path.join(HERE, "..", "reference", "project.template.yaml")
        self.assertEqual(pm.validate(pm.load(path)), [])


class UnknownKeys(unittest.TestCase):
    """The 09-28 failure: misnamed keys validated clean and hid the state."""

    def test_misnamed_top_level_key_is_an_error_with_a_hint(self):
        d = sample()
        d["open_questions"] = d.pop("questions")
        errors = " ".join(pm.validate(d))
        self.assertIn("unknown top-level key 'open_questions'", errors)
        self.assertIn("'questions'", errors)

    def test_misnamed_item_key_is_an_error(self):
        d = sample()
        d["clocks"][0]["date"] = d["clocks"][0].pop("due")
        errors = " ".join(pm.validate(d))
        self.assertIn("clocks (C1): unknown key 'date'", errors)
        self.assertIn("'due'", errors)

    def test_misnamed_nested_and_party_keys(self):
        d = sample()
        d["watch"]["drive_folder"] = []
        d["watch"]["parties"][0]["email"] = ["a@example.com"]
        d["last_run"] = {"escalate": []}
        errors = " ".join(pm.validate(d))
        self.assertIn("watch: unknown key 'drive_folder'", errors)
        self.assertIn("watch.parties (Silent Co): unknown key 'email'", errors)
        self.assertIn("last_run: unknown key 'escalate'", errors)

    def test_advisory_blocks_ride_along(self):
        d = sample()
        d["advisory"] = {"party": "child-1", "anything": 1}
        d["legal"] = {"mode": "SELF"}
        self.assertEqual(pm.validate(d), [])

    def test_health_block_rides_along(self):
        d = sample()
        d["advisory"] = {"party": "tide"}
        d["health"] = {"hsa_eligible": {"status": "unknown"}}
        self.assertEqual(pm.validate(d), [])

    def test_bad_cron_is_an_error_but_monthly_is_tolerated(self):
        d = sample()
        d["cadence"]["cron"] = "0 11 * *"
        self.assertIn("cadence.cron", " ".join(pm.validate(d)))
        d["cadence"]["cron"] = "0 11 1 * *"
        self.assertEqual(pm.validate(d), [])

    def test_warnings_are_not_errors(self):
        d = sample()
        d["actions"][0]["next_step"] = "x" * 2000
        self.assertEqual(pm.validate(d), [])
        self.assertIn("next_step is 2000 characters", " ".join(pm.warnings(d)))


class OverdueReping(unittest.TestCase):
    def setUp(self):
        self.d = sample()
        self.d["actions"] = []
        self.d["questions"] = []
        self.d["watch"] = {"parties": []}
        self.d["clocks"] = [{"id": "C9", "due": "2026-09-10", "item": "Quote owed", "owner": "Magnum"}]

    def key(self, day):
        return pm.clocks(self.d, day)["escalate_keys"]

    def test_first_week_uses_the_plain_key(self):
        self.assertEqual(self.key(dt.date(2026, 9, 11)), ["clock:C9:overdue"])
        self.assertEqual(self.key(dt.date(2026, 9, 16)), ["clock:C9:overdue"])

    def test_pings_again_each_week_overdue(self):
        self.assertEqual(self.key(dt.date(2026, 9, 17)), ["clock:C9:overdue:7d"])
        self.assertEqual(self.key(dt.date(2026, 9, 23)), ["clock:C9:overdue:7d"])
        self.assertEqual(self.key(dt.date(2026, 9, 24)), ["clock:C9:overdue:14d"])

    def test_a_reping_is_new_and_marked_stale(self):
        self.d["last_run"] = {"escalated": ["clock:C9:overdue"]}
        r = pm.clocks(self.d, dt.date(2026, 9, 17))
        self.assertEqual(r["verdict"], "escalate")
        self.assertTrue(r["overdue"][0]["stale"])
        self.d["last_run"] = {"escalated": ["clock:C9:overdue:7d"]}
        self.assertEqual(pm.clocks(self.d, dt.date(2026, 9, 18))["verdict"], "quiet")

    def test_cadence_can_change_or_disable_it(self):
        self.d["cadence"]["overdue_reping_days"] = 3
        self.assertEqual(self.key(dt.date(2026, 9, 14)), ["clock:C9:overdue:3d"])
        self.d["cadence"]["overdue_reping_days"] = 0
        self.assertEqual(self.key(dt.date(2026, 10, 30)), ["clock:C9:overdue"])

    def test_work_says_in_words_what_each_new_key_needs(self):
        self.d["last_run"] = {"escalated": ["clock:C9:overdue"]}
        work = pm.clocks(self.d, dt.date(2026, 9, 17))["work"]
        self.assertEqual(work[0]["key"], "clock:C9:overdue:7d")
        self.assertIn("clock C9 (Quote owed) is 7 day(s) overdue and still open", work[0]["what"])
        self.assertIn("re-date it", work[0]["what"])

    def test_reping_keys_are_in_the_grammar(self):
        self.assertEqual(pm.last_run_errors({"escalated": ["clock:C9:overdue:14d", "silent:ridge-builders:2026-09-01"]}), [])
        self.assertTrue(pm.last_run_errors({"escalated": ["clock:C9:overdue:two-weeks"]}))


class SilentKeys(unittest.TestCase):
    def test_new_silence_escalates_once_per_episode(self):
        d = sample()
        d["actions"], d["clocks"], d["questions"] = [], [], []
        r = pm.clocks(d, TODAY)
        self.assertEqual(r["escalate_keys"], ["silent:silent-co:2026-09-01"])
        self.assertIn("Silent Co has been silent 11 days on: a quote", r["work"][0]["what"])
        d["last_run"] = {"escalated": r["escalate_keys"]}
        self.assertEqual(pm.clocks(d, TODAY + dt.timedelta(days=5))["verdict"], "quiet")
        d["watch"]["parties"][0]["last_heard"] = "2026-09-20"  # they answered, then went quiet again
        self.assertIn("silent:silent-co:2026-09-20", pm.clocks(d, dt.date(2026, 10, 1))["new_keys"])


class Query(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 9, 15, 0, tzinfo=dt.timezone.utc)

    def project(self):
        d = sample()
        d["watch"] = {
            "parties": [
                {"name": "Ridge", "emails": ["Pat@example.com", "office@example.com"],
                 "domains": ["example.com"]},
                {"name": "Tile Co", "emails": ["jw.tile@example.org"]},
            ],
            "identifiers": ["26-0709"],
            "keywords": ["standing seam", "FORTIFIED"],
            "exclude": ["from:parent.a+cc@example.com"],
            "drive_folders": [{"name": "Plans", "id": "FOLDER1"}],
            "web": [{"url": "https://example.gov/permit", "check": "permit status"}],
        }
        d["last_run"] = {"at": "2026-10-08T11:22:49Z"}
        d["actions"][0]["draft_id"] = "r-1"
        return d

    def test_window_opens_a_day_before_the_last_run(self):
        self.assertEqual(pm.query(self.project(), self.NOW)["since"], "2026-10-07")

    def test_no_last_run_looks_back_two_weeks(self):
        d = self.project()
        d["last_run"] = {}
        self.assertEqual(pm.query(d, self.NOW)["since"], "2026-09-25")

    def test_inbound_search(self):
        q = pm.query(self.project(), self.NOW)["gmail"]["inbound"]
        self.assertTrue(q.startswith("after:2026/10/07 -in:sent -in:draft ("))
        self.assertIn("from:jw.tile@example.org OR from:example.com", q)
        self.assertNotIn("pat@example.com", q)  # the domain already covers it
        self.assertIn('26-0709 OR "standing seam" OR FORTIFIED', q)
        self.assertTrue(q.endswith(") -from:parent.a+cc@example.com"))

    def test_sent_and_draft_searches(self):
        g = pm.query(self.project(), self.NOW)["gmail"]
        self.assertEqual(g["sent"], "after:2026/10/07 in:sent (to:jw.tile@example.org OR cc:jw.tile@example.org OR "
                                    "to:example.com OR cc:example.com) -from:parent.a+cc@example.com")
        self.assertEqual(g["drafts"], "(to:jw.tile@example.org OR to:example.com)")

    def test_drive_web_and_what_is_mandatory(self):
        plan = pm.query(self.project(), self.NOW)
        self.assertEqual(plan["drive"][0]["query"],
                         "parentId = 'FOLDER1' and modifiedTime > '2026-10-07T00:00:00Z'")
        self.assertEqual(plan["open_draft_ids"], ["r-1"])
        self.assertEqual(plan["mandatory"], ["gmail.inbound", "gmail.sent", "drive", "web"])

    def test_nothing_to_watch_means_nothing_mandatory(self):
        d = sample()
        d["watch"] = {"parties": []}
        self.assertEqual(pm.query(d, self.NOW)["mandatory"], [])

    def test_text_folders_list_the_months_in_the_window(self):
        import shutil
        import tempfile
        top = tempfile.mkdtemp(prefix="pm-texts-")
        try:
            folder = os.path.join(top, "notes", "texts", "cyrus")
            os.makedirs(folder)
            for name in ("2026-08.md", "2026-10.md", "index.md"):
                with open(os.path.join(folder, name), "w") as f:
                    f.write("x\n")
            d = self.project()
            d["watch"]["texts"] = ["notes/texts/cyrus", "notes/texts/nobody-yet"]
            d["watch"]["parties"][0]["phones"] = ["205-555-0100"]
            self.assertEqual(pm.validate(d), [])
            plan = pm.query(d, self.NOW, top=top)
            self.assertIn("texts", plan["mandatory"])
            self.assertEqual(plan["texts"][0]["files"], ["notes/texts/cyrus/2026-10.md"])
            self.assertTrue(plan["texts"][0]["new_since_last_run"])  # not a git repo: assume new
            self.assertEqual(plan["texts"][1], {"folder": "notes/texts/nobody-yet", "files": [],
                                                "new_since_last_run": False})
        finally:
            shutil.rmtree(top, ignore_errors=True)


class Cron(unittest.TestCase):
    def at(self, text):
        return dt.datetime.fromisoformat(text).replace(tzinfo=dt.timezone.utc)

    def test_utc_weekday_range(self):
        fire = pm.last_fire("20 11 * * 2-6", self.at("2026-10-09T15:00:00"))  # a Friday
        self.assertEqual(pm._utc(fire), "2026-10-09T11:20:00Z")
        fire = pm.last_fire("20 11 * * 2-6", self.at("2026-10-12T15:00:00"))  # Monday → Saturday's
        self.assertEqual(pm._utc(fire), "2026-10-10T11:20:00Z")

    def test_before_todays_fire_falls_back_a_day(self):
        fire = pm.last_fire("20 11 * * 2-6", self.at("2026-10-09T11:00:00"))
        self.assertEqual(pm._utc(fire), "2026-10-08T11:20:00Z")

    def test_cron_tz_follows_dst(self):
        summer = pm.last_fire("CRON_TZ=America/Chicago 30 11 * * 2-6", self.at("2026-10-09T20:00:00"))
        winter = pm.last_fire("CRON_TZ=America/Chicago 30 11 * * 2-6", self.at("2026-11-06T20:00:00"))
        self.assertEqual(pm._utc(summer), "2026-10-09T16:30:00Z")  # CDT
        self.assertEqual(pm._utc(winter), "2026-11-06T17:30:00Z")  # CST

    def test_sunday_is_zero_or_seven(self):
        for expr in ("0 12 * * 0", "0 12 * * 7"):
            self.assertEqual(pm._utc(pm.last_fire(expr, self.at("2026-10-09T15:00:00"))), "2026-10-04T12:00:00Z")

    def test_garbage_is_rejected(self):
        for expr in ("every day", "61 11 * * 2", "CRON_TZ=Mars/Olympus 0 6 * * 1"):
            with self.assertRaises(ValueError):
                pm.parse_cron(expr)


class Health(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 6, 18, 0, tzinfo=dt.timezone.utc)  # Tuesday afternoon

    def project(self, last):
        d = sample()
        d["cadence"]["cron"] = "20 11 * * 2-6"
        d["last_run"] = {"at": last}
        return d

    def test_a_run_that_never_recorded_is_missed(self):
        row = pm.health_row(self.project("2026-10-03T11:22:00Z"), self.NOW)
        self.assertTrue(row["missed"])
        self.assertEqual(row["expected"], "2026-10-06T11:20:00Z")
        self.assertEqual(row["hours_late"], 6.7)

    def test_a_run_after_the_fire_is_fine(self):
        self.assertFalse(pm.health_row(self.project("2026-10-06T11:23:10Z"), self.NOW)["missed"])

    def test_grace_window(self):
        early = dt.datetime(2026, 10, 6, 12, 0, tzinfo=dt.timezone.utc)
        self.assertFalse(pm.health_row(self.project("2026-10-03T11:22:00Z"), early)["missed"])

    def test_a_scheduled_local_project_is_checked(self):
        d = self.project("2026-10-03T11:22:00Z")
        d["runtime"] = "local"
        self.assertTrue(pm.health_row(d, self.NOW)["missed"])

    def test_paused_and_unscheduled_projects_are_skipped(self):
        d = self.project("2026-09-01T00:00:00Z")
        d["runtime"] = "local"
        d["cadence"]["cron"] = None
        self.assertFalse(pm.health_row(d, self.NOW)["missed"])
        d = self.project("2026-09-01T00:00:00Z")
        d["status"] = "paused"
        self.assertFalse(pm.health_row(d, self.NOW)["missed"])


YAML_TEXT = """\
# A project file with comments that must survive.
id: sample
title: Sample project
status: active
owners: [Parent A]
notes_root: notes
runtime: cloud
charter:
  goal: Prove the engine
cadence:
  urgency_window_days: 10

decisions:
  - {id: D1, text: Roof is FORTIFIED, status: DECIDED, date: 2026-07-09}

actions:
  # the bid chase
  - id: A1
    text: "Chase the bid: \\"final\\" number"
    owner: Parent A
    due: 2026-09-15
    status: open
  - id: A2
    text: Old thing
    owner: Parent A
    status: done
    done_on: 2026-08-01
    next_step: >-
      a folded
      scalar
  - {id: A3, text: Recent thing, owner: Parent A, status: done, done_on: 2026-09-10}

clocks:
  - {id: C1, due: 2026-08-15, item: Finished clock, owner: Insurer, status: done, done_on: 2026-08-15}

questions:
  - {id: Q1, text: "Budget?", for: Parent A, raised: 2026-08-01, status: answered, answer: TBD}

needs_local: []

last_run:
  at: null
  runtime: null
  result: null
  escalated: [clock:C1:urgent, "event:old-thing:2026-07-01", "event:recent-thing:2026-09-05"]

# trailing comment
"""

INDEX_TEXT = """\
---
title: Sample
modified: 2026-09-01T00:00:00Z
---

# Sample

<!-- pm:begin status -->
<!-- pm:end status -->

## Detailed Log

<details open><summary><b>Activity Log</b></summary>

### 2026-09-10 — Something happened
Body of the older entry.

</details>
"""


class Scratch(unittest.TestCase):
    """A throwaway project folder on disk."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="pm-test-")
        self.notes = os.path.join(self.dir, "notes")
        os.makedirs(self.notes)
        self.yaml = os.path.join(self.notes, "project.yaml")
        self.index = os.path.join(self.notes, "index.md")
        self.write(self.yaml, YAML_TEXT)
        self.write(self.index, INDEX_TEXT)
        # A test must not meter the real session that happens to be running it.
        self.session = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)
        if self.session is not None:
            os.environ["CLAUDE_CODE_SESSION_ID"] = self.session

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()


class Record(Scratch):
    NOW = dt.datetime(2026, 9, 12, 16, 30, 5, tzinfo=dt.timezone.utc)

    def record(self, **kw):
        kw.setdefault("now", self.NOW)
        kw.setdefault("today", TODAY)
        return pm.record(self.yaml, kw.pop("result", "Nothing new."), kw.pop("runtime", "cloud"), **kw)

    def test_stamps_from_the_clock_and_keeps_everything_else(self):
        out, errors = self.record(headline="Broker answered", result='She said: "drops down" — gap is $200k')
        self.assertEqual(errors, [])
        self.assertEqual(out["at"], "2026-09-12T16:30:05Z")
        text = self.read(self.yaml)
        self.assertIn("# A project file with comments that must survive.", text)
        self.assertIn("  # the bid chase", text)
        self.assertTrue(text.rstrip().endswith("# trailing comment"))
        run = yaml.safe_load(text)["last_run"]
        self.assertEqual(run["result"], 'She said: "drops down" — gap is $200k')
        self.assertEqual(run["runtime"], "cloud")
        self.assertEqual(pm.validate(yaml.safe_load(text), self.NOW), [])

    def test_escalated_carries_current_keys_and_recent_events_only(self):
        out, _ = self.record(headline="x", events=["Revised plans!"])
        self.assertEqual(out["escalated"], ["action:A1:urgent", "event:recent-thing:2026-09-05",
                                            "event:revised-plans:2026-09-12"])
        self.assertEqual(out["new_keys"], ["action:A1:urgent", "event:revised-plans:2026-09-12"])
        self.assertIn("action A1", out["new"][0]["what"])
        self.assertIn("is due 2026-09-15 (in 3 day(s))", out["new"][0]["what"])
        self.assertEqual(out["verdict"], "escalate")
        out, _ = self.record(quiet=True)
        self.assertEqual(out["verdict"], "quiet")

    def test_log_entry_goes_on_top_and_index_is_rendered(self):
        self.record(headline="Broker answered", log="The broker replied.\nDraft staged.")
        text = self.read(self.index)
        self.assertLess(text.index("### 2026-09-12 — Broker answered"), text.index("### 2026-09-10 — Something happened"))
        self.assertIn("The broker replied.\nDraft staged.\n\n### 2026-09-10", text)
        self.assertIn("**Last managed run:** 2026-09-12T16:30:05Z (cloud)", text)
        self.assertIn("modified: 2026-09-12T00:00:00Z", text)
        self.assertTrue(text.rstrip().endswith("</details>"))

    def test_quiet_runs_roll_one_entry_forward(self):
        self.record(quiet=True, result="No new mail.")
        self.record(quiet=True, result="Still nothing.", today=TODAY + dt.timedelta(days=1),
                    now=self.NOW + dt.timedelta(days=1))
        self.record(quiet=True, result="Third quiet day.", today=TODAY + dt.timedelta(days=2),
                    now=self.NOW + dt.timedelta(days=2))
        text = self.read(self.index)
        self.assertEqual(text.count("— Quiet (since"), 1)
        self.assertIn("### 2026-09-14 — Quiet (since 2026-09-12)\nThird quiet day.\n\n### 2026-09-10", text)

    def test_a_real_entry_ends_the_quiet_streak(self):
        self.record(quiet=True)
        self.record(headline="Quote arrived", today=TODAY + dt.timedelta(days=1), now=self.NOW + dt.timedelta(days=1))
        self.record(quiet=True, today=TODAY + dt.timedelta(days=2), now=self.NOW + dt.timedelta(days=2))
        text = self.read(self.index)
        self.assertEqual(text.count("— Quiet (since"), 2)
        self.assertIn("### 2026-09-14 — Quiet (since 2026-09-14)", text)

    def test_missing_log_section_is_created(self):
        self.write(self.index, "# Bare note\n")
        out, errors = self.record(headline="First run")
        self.assertEqual(errors, [])
        self.assertIn("## Activity Log\n\n### 2026-09-12 — First run", self.read(self.index))

    def test_an_invalid_file_is_not_written(self):
        self.write(self.yaml, YAML_TEXT.replace("questions:", "open_questions:"))
        before = self.read(self.yaml), self.read(self.index)
        out, errors = self.record(headline="x")
        self.assertIn("unknown top-level key 'open_questions'", " ".join(errors))
        self.assertEqual((self.read(self.yaml), self.read(self.index)), before)

    def test_block_style_escalated_round_trips(self):
        self.record(headline="one")
        out, errors = self.record(headline="two")
        self.assertEqual(errors, [])
        self.assertEqual(self.read(self.yaml).count("last_run:"), 1)


class Publish(Scratch):
    """record --commit --publish against a real (local) remote."""

    def git(self, *args, cwd=None):
        import subprocess
        done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
                              + list(args), cwd=cwd or self.dir, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def setUp(self):
        super().setUp()
        self.remote = self.dir + "-remote.git"
        self.git("init", "-q", "--bare", "-b", "main", self.remote, cwd=os.path.dirname(self.dir))
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "t")
        self.git("config", "user.email", "t@t")
        self.git("config", "commit.gpgsign", "false")
        self.git("remote", "add", "origin", self.remote)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-b", "claude/session")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.remote, ignore_errors=True)
        super().tearDown()

    def run_record(self, *extra):
        return pm.main(["record", self.yaml, "--result", "ok", "--runtime", "cloud", "--today", "2026-09-12"] + list(extra))

    def other_push(self, name):
        """Someone else lands a commit on origin/main while this session works."""
        clone = self.dir + "-other"
        self.git("clone", "-q", self.remote, clone, cwd=os.path.dirname(self.dir))
        with open(os.path.join(clone, name), "w") as f:
            f.write("x\n")
        self.git("add", "-A", cwd=clone)
        self.git("commit", "-q", "-m", "ingestion: " + name, cwd=clone)
        self.git("push", "-q", "origin", "main", cwd=clone)
        import shutil
        shutil.rmtree(clone, ignore_errors=True)

    def test_commit_and_publish_lands_on_main(self):
        self.assertEqual(self.run_record("--quiet", "--commit", "--publish"), 0)
        self.assertEqual(self.git("log", "-1", "--format=%s", "origin/main"), "sample: quiet run 2026-09-12")
        self.assertEqual(self.git("rev-list", "--count", "origin/main..HEAD"), "0")

    def test_rebases_when_main_moved(self):
        self.other_push("a.txt")
        self.assertEqual(self.run_record("--headline", "Quote arrived", "--commit", "--publish",
                                         "--trailer", "Co-Authored-By: Test <t@t>"), 0)
        log = self.git("log", "-2", "--format=%s", "origin/main").split("\n")
        self.assertEqual(log, ["sample: Quote arrived", "ingestion: a.txt"])
        self.assertIn("Co-Authored-By: Test <t@t>", self.git("log", "-1", "--format=%B", "origin/main"))

    def test_dirty_tree_publishes_without_touching_other_work(self):
        stray = os.path.join(self.dir, "unrelated.txt")
        self.write(stray, "seed\n")
        self.git("add", "unrelated.txt")
        self.git("commit", "-q", "-m", "seed stray")
        self.git("push", "-q", "origin", "HEAD:main")
        self.other_push("c.txt")
        self.write(stray, "someone else's uncommitted edit\n")
        self.assertEqual(self.run_record("--headline", "Reply drafted", "--commit", "--publish"), 0)
        self.assertEqual(self.git("log", "-1", "--format=%s", "origin/main"), "sample: Reply drafted")
        self.assertEqual(self.read(stray), "someone else's uncommitted edit\n")
        self.assertNotIn("unrelated", self.git("show", "--stat", "--format=", "origin/main"))

    def test_only_the_project_folder_is_committed(self):
        self.write(os.path.join(self.dir, "elsewhere.md"), "not ours\n")
        self.assertEqual(self.run_record("--headline", "x", "--commit"), 0)
        self.assertEqual(sorted(self.git("show", "--name-only", "--format=", "HEAD").split("\n")),
                         ["notes/index.md", "notes/project.yaml", "notes/runs.csv"])


class Archive(Scratch):
    def test_moves_old_closed_items_and_keeps_layout(self):
        out, errors = pm.archive(self.yaml, TODAY)
        self.assertEqual(errors, [])
        self.assertEqual(out["archived"], {"actions": ["A2"], "clocks": ["C1"]})
        text = self.read(self.yaml)
        self.assertIn("# the bid chase", text)
        self.assertIn("clocks: []", text)
        data = yaml.safe_load(text)
        self.assertEqual([a["id"] for a in data["actions"]], ["A1", "A3"])  # A3 closed too recently
        self.assertEqual([q["id"] for q in data["questions"]], ["Q1"])      # answers stay by default
        kept = pm.load_archive(self.yaml)
        self.assertEqual(kept["actions"][0]["next_step"], "a folded scalar")
        self.assertEqual(kept["clocks"][0]["id"], "C1")
        self.assertEqual(pm.validate(data), [])

    def test_questions_only_on_request(self):
        out, _ = pm.archive(self.yaml, TODAY, questions=True)
        self.assertEqual(out["archived"]["questions"], ["Q1"])

    def test_second_pass_appends(self):
        pm.archive(self.yaml, TODAY)
        out, _ = pm.archive(self.yaml, TODAY + dt.timedelta(days=30))
        self.assertEqual(out["archived"], {"actions": ["A3"]})
        self.assertEqual([a["id"] for a in pm.load_archive(self.yaml)["actions"]], ["A2", "A3"])

    def test_dry_run_writes_nothing(self):
        before = self.read(self.yaml)
        pm.archive(self.yaml, TODAY, write=False)
        self.assertEqual(self.read(self.yaml), before)
        self.assertFalse(os.path.exists(pm.archive_path(self.yaml)))

    def test_an_archived_id_cannot_be_reused(self):
        pm.archive(self.yaml, TODAY)
        data = pm.load(self.yaml)
        data["actions"].append({"id": "A2", "text": "New thing", "owner": "Parent A", "status": "open"})
        errors = pm.archive_collisions(data, pm.load_archive(self.yaml))
        self.assertIn("actions A2", " ".join(errors))


class Routine(unittest.TestCase):
    SETTINGS = {"repo": "example/household-notes", "connectors": ["Gmail", "Google-Drive", "Google-Calendar"]}
    SPEC = {"id": "sample", "trigger_id": "trig_1", "name": "Sample — project manager",
            "cron": "CRON_TZ=America/Chicago 30 11 * * 2-6", "prompt": "Run `project-manager`: `run sample`.\n"}

    def deployed(self, **change):
        trig = {
            "id": "trig_1", "enabled": True, "name": "Sample — project manager",
            "cron_expression": "CRON_TZ=America/Chicago 30 11 * * 2-6",
            "job_config": {"ccr": {
                "events": [{"data": {"message": {"content": "Run `project-manager`:  `run sample`.", "role": "user"}}}],
                "session_context": {"sources": [{"git_repository": {"url": "https://github.com/example/household-notes"}}]}}},
            "mcp_connections": [
                {"name": "Gmail", "permitted_tools": ["search_threads", "get_message", "create_draft"]},
                {"name": "Google-Drive", "permitted_tools": []},
                {"name": "Google-Calendar", "permitted_tools": []}],
            "notifications": {"channel": {"push": True}},
        }
        trig.update(change)
        return {"trigger": trig}

    def test_in_sync(self):
        project = {"trigger_id": "trig_1", "cadence": {"cron": "CRON_TZ=America/Chicago 30 11 * * 2-6"}}
        self.assertEqual(pm.routine_drift(self.SPEC, self.deployed(), project, self.SETTINGS), [])

    def test_everything_that_drifted_in_october(self):
        bad = self.deployed(
            cron_expression="0 11 * * 6", name="⚡ Insurance Manager",
            mcp_connections=[{"name": "Gmail", "permitted_tools": []}],
            notifications={"channel": {"push": False}})
        bad["trigger"]["job_config"]["ccr"]["events"][0]["data"]["message"]["content"] = "old path prompt"
        bad["trigger"]["job_config"]["ccr"]["session_context"]["sources"] = []
        drift = " | ".join(pm.routine_drift(self.SPEC, bad, {"trigger_id": None, "cadence": {"cron": "0 11 * * 2-6"}},
                                             self.SETTINGS))
        for needle in ("cron:", "name:", "prompt:", "git source", "connector missing: Google-Drive",
                       "connector missing: Google-Calendar", "no permitted_tools", "push notifications",
                       "project.yaml trigger_id", "project.yaml cadence.cron"):
            self.assertIn(needle, drift)

    def test_gmail_send_tools_are_flagged(self):
        bad = self.deployed()
        bad["trigger"]["mcp_connections"][0]["permitted_tools"] += ["send_message", "trash_thread"]
        self.assertIn("send_message, trash_thread", " ".join(pm.routine_drift(self.SPEC, bad, settings=self.SETTINGS)))

    def test_without_repo_or_connectors_configured_those_checks_are_skipped(self):
        bad = self.deployed(mcp_connections=[])
        bad["trigger"]["job_config"]["ccr"]["session_context"]["sources"] = []
        drift = " ".join(pm.routine_drift(self.SPEC, bad, settings={}))
        self.assertNotIn("git source", drift)
        self.assertNotIn("connector missing", drift)

    def test_every_routine_file_parses_and_matches_its_project(self):
        top = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
        folder = pm.routine_dir()
        if not (pm.CONFIG.get("routine") or {}).get("dir") or not os.path.isdir(folder):
            self.skipTest("no routine files configured in this checkout")
        projects = {data["id"]: data for _, data in pm.registry(top)}
        for name in sorted(f for f in os.listdir(folder) if f.endswith(".md")):
            pid = name[:-3]
            spec = pm.routine_spec(pid)
            self.assertTrue(spec["trigger_id"] and spec["name"] and spec["prompt"].strip(), name)
            pm.parse_cron(spec["cron"])
            self.assertIn("run %s" % pid, spec["prompt"], name)
            if pid in projects:  # absent in a checkout without the notes
                self.assertEqual(projects[pid].get("trigger_id"), spec["trigger_id"], name)
                self.assertEqual(projects[pid]["cadence"]["cron"], spec["cron"], name)


class Registry(unittest.TestCase):
    def test_ids_are_unique_and_every_project_validates(self):
        top = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
        rows = pm.registry(top)
        ids = [data["id"] for _, data in rows]
        self.assertEqual(len(ids), len(set(ids)))
        for rel, data in rows:
            self.assertEqual(pm.validate(data), [], rel)


def transcript(*entries):
    return "".join(json.dumps(e) + "\n" for e in entries)


def said(text, at):
    return {"type": "user", "timestamp": at, "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def tool_result(at):
    return {"type": "user", "timestamp": at,
            "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}


def call(mid, at, inp, out, read=0, write=0, model="claude-sonnet-5-5"):
    return {"type": "assistant", "timestamp": at,
            "message": {"id": mid, "model": model, "usage": {
                "input_tokens": inp, "output_tokens": out,
                "cache_read_input_tokens": read, "cache_creation_input_tokens": write}}}


class SessionUsage(Scratch):
    NOW = dt.datetime(2026, 10, 9, 16, 39, 0, tzinfo=dt.timezone.utc)

    def home_with(self, text, sid="sess-1"):
        folder = os.path.join(self.dir, "home", ".claude", "projects", "-home-user-notes")
        os.makedirs(folder, exist_ok=True)
        self.write(os.path.join(folder, sid + ".jsonl"), text)
        return os.path.join(self.dir, "home")

    def test_counts_this_turn_only_and_each_call_once(self):
        home = self.home_with(transcript(
            said("Run kitchen-remodel", "2026-10-06T11:20:00Z"),
            call("m0", "2026-10-06T11:20:05Z", 9000, 900),          # an earlier turn, days ago
            said("he called — they're out", "2026-10-09T16:38:10Z"),  # the turn being recorded
            call("m1", "2026-10-09T16:38:12Z", 3, 40, read=100, write=20000),
            call("m1", "2026-10-09T16:38:13Z", 3, 120, read=100, write=20000),  # same call, final line
            tool_result("2026-10-09T16:38:14Z"),
            call("m2", "2026-10-09T16:38:20Z", 5, 300, read=20100, write=500),
            "not json",
        ) + "garbage\n")
        usage = pm.session_usage(self.NOW, "sess-1", home)
        self.assertEqual(usage, {"turns": 2, "model": "claude-sonnet-5-5", "input_tokens": 8,
                                 "output_tokens": 420, "cache_read_tokens": 20200,
                                 "cache_write_tokens": 20500, "seconds": 50})

    def test_no_session_or_no_transcript_is_empty_not_an_error(self):
        self.assertEqual(pm.session_usage(self.NOW, None, self.dir), {})
        self.assertEqual(pm.session_usage(self.NOW, "missing", self.home_with("")), {})
        self.assertEqual(pm.session_usage(self.NOW, "sess-1", self.home_with(transcript(said("hi", "2026-10-09T16:38:10Z")))), {})

    def test_start_mark_times_a_run_without_a_transcript(self):
        began = self.NOW - dt.timedelta(seconds=42)
        pm.mark_start("mark-test", began)
        pm.mark_start("mark-test", began + dt.timedelta(seconds=30))   # a second query does not reset it
        self.assertEqual(pm.seconds_since_mark("mark-test", self.NOW), 42)
        self.assertIsNone(pm.seconds_since_mark("mark-test", self.NOW))  # cleared once read


class RunLedger(Scratch):
    NOW = dt.datetime(2026, 9, 12, 16, 30, 5, tzinfo=dt.timezone.utc)

    def test_every_recorded_run_gets_a_row(self):
        usage = {"seconds": 31, "turns": 9, "model": "claude-sonnet-5-5", "input_tokens": 40,
                 "output_tokens": 900, "cache_read_tokens": 150000, "cache_write_tokens": 30000}
        out, errors = pm.record(self.yaml, "No new mail.", "cloud", quiet=True, now=self.NOW, today=TODAY, usage=usage)
        self.assertEqual(errors, [])
        self.assertEqual(out["cost"]["turns"], 9)
        pm.record(self.yaml, "Quote in.", "cloud", headline="Magnum quoted, with a comma",
                  now=self.NOW + dt.timedelta(days=1), today=TODAY + dt.timedelta(days=1))
        rows = pm.read_runs(self.yaml)
        self.assertEqual(self.read(pm.runs_path(self.yaml)).count("at,runtime,outcome"), 1)  # one header
        self.assertEqual([r["outcome"] for r in rows], ["quiet", "acted"])
        self.assertEqual(rows[0]["seconds"], "31")
        self.assertEqual(rows[0]["cache_read_tokens"], "150000")
        self.assertEqual(rows[1]["headline"], "Magnum quoted, with a comma")
        self.assertEqual(rows[1]["turns"], "")  # no transcript: the run is still on the ledger

    def test_nothing_is_logged_when_the_record_is_refused(self):
        self.write(self.yaml, YAML_TEXT.replace("questions:", "open_questions:"))
        pm.record(self.yaml, "x", "cloud", headline="x", now=self.NOW, today=TODAY)
        self.assertFalse(os.path.exists(pm.runs_path(self.yaml)))

    def test_summary_splits_quiet_from_acted(self):
        rows = [
            {"at": "2026-10-01T16:31:00Z", "outcome": "quiet", "seconds": "30", "turns": "8", "input_tokens": "10",
             "output_tokens": "500", "cache_read_tokens": "100000", "cache_write_tokens": "20000"},
            {"at": "2026-10-02T16:31:00Z", "outcome": "quiet", "seconds": "50", "turns": "10", "input_tokens": "20",
             "output_tokens": "700", "cache_read_tokens": "140000", "cache_write_tokens": "20000"},
            {"at": "2026-10-03T16:31:00Z", "outcome": "quiet", "seconds": "", "turns": ""},     # unmetered
            {"at": "2026-10-03T18:00:00Z", "outcome": "acted", "seconds": "300", "turns": "40", "input_tokens": "90",
             "output_tokens": "9000", "cache_read_tokens": "900000", "cache_write_tokens": "80000"},
            {"at": "2026-08-01T16:31:00Z", "outcome": "acted", "seconds": "999", "turns": "99"},  # before the window
        ]
        got = pm.usage_summary(rows, dt.date(2026, 9, 15))
        self.assertEqual(got["quiet"]["runs"], 3)
        self.assertEqual(got["quiet"]["metered_runs"], 2)
        self.assertEqual(got["quiet"]["median_seconds"], 40)
        self.assertEqual(got["quiet"]["tokens_per_run"]["cache_read_tokens"], 120000)
        self.assertEqual(got["acted"]["runs"], 1)
        self.assertEqual(got["acted"]["tokens"]["output_tokens"], 9000)


class Example(unittest.TestCase):
    """The fictional sample project that ships with the skill must stay valid and rendered."""
    FOLDER = os.path.join(HERE, "..", "examples", "kitchen-remodel")

    def load(self):
        return pm.load(os.path.join(self.FOLDER, "project.yaml"))

    def test_sample_validates(self):
        data = self.load()
        path = os.path.join(self.FOLDER, "project.yaml")
        self.assertEqual(pm.validate(data) + pm.archive_collisions(data, pm.load_archive(path)), [])

    def test_sample_index_is_rendered(self):
        with open(os.path.join(self.FOLDER, "index.md"), encoding="utf-8") as f:
            text = f.read()
        after, found = pm.render(self.load(), text)
        self.assertEqual(found, pm.BLOCKS)
        self.assertEqual(after, text, "run: pm.py render examples/kitchen-remodel/project.yaml")

    def test_sample_clocks_on_a_fixed_day(self):
        report = pm.clocks(self.load(), dt.date(2026, 11, 21))
        self.assertEqual(report["verdict"], "escalate")
        self.assertEqual([r["id"] for r in report["urgent"]], ["A1", "A2"])
        self.assertEqual([p["name"] for p in report["silent_parties"]], ["Pat Rivera"])  # Chen declined
        self.assertIn("question:Q1", report["escalate_keys"])

    def test_sample_query_is_complete(self):
        plan = pm.query(self.load(), dt.datetime(2026, 11, 21, 17, 0, tzinfo=dt.timezone.utc), top=self.FOLDER)
        self.assertEqual(plan["mandatory"], ["gmail.inbound", "gmail.sent", "web"])
        self.assertIn("BP-2026-04417", plan["gmail"]["inbound"])
        self.assertTrue(plan["gmail"]["inbound"].endswith(" -from:parent.a+cc@example.com"))


class Config(Scratch):
    def test_missing_config_is_empty_not_an_error(self):
        self.assertEqual(pm.load_config(os.path.join(self.dir, "nope.yaml")), {})

    def test_config_is_read(self):
        path = os.path.join(self.dir, "household.yaml")
        self.write(path, "timezone: America/Chicago\nroutine: {dir: routines}\n")
        self.assertEqual(pm.load_config(path)["timezone"], "America/Chicago")

    def test_home_today_follows_the_configured_zone(self):
        evening = dt.datetime(2026, 10, 9, 2, 30, tzinfo=dt.timezone.utc)   # 9:30pm the day before in Chicago
        self.assertEqual(pm.home_today(evening, "America/Chicago"), dt.date(2026, 10, 8))
        self.assertEqual(pm.home_today(evening, "UTC"), dt.date(2026, 10, 9))

    def test_routine_dir_comes_from_config(self):
        self.assertTrue(pm.routine_dir(settings={"dir": "routines/cloud"}).endswith(os.path.join("routines", "cloud")))
        self.assertTrue(pm.routine_dir(settings={}).endswith("routines"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
