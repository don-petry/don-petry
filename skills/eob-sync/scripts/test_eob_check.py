"""Tests for eob_check.py:  python3 -m unittest skills/eob-sync/scripts/test_eob_check.py"""
import datetime as dt
import pathlib
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import eob_check  # noqa: E402

PLANS = textwrap.dedent("""
    plans:
      dental:
        members: [Parent A, Child 1]
        notices: {eob: eob-notices@example.com}
    expected_claims:
      - {id: ortho, plan: dental, patient: Child 1, provider: Example Orthodontics,
         what: ortho benefit, expect_by: 2026-10-01}
    thresholds: {high_patient_resp: 250, pending_days: 30, appeal_warn_days: 30,
                 stale_days: 14, accumulator_warn: 0.8}
""")
HEAD = ("plan,claim_id,patient,provider,network,service_date,processed_date,billed,allowed,plan_paid,"
        "deductible,copay,coinsurance,not_covered,patient_resp,status,remarks,appeal_by,provider_billed,"
        "reimbursed,eob_drive_id,resolution,notes\n")


class EobCheckTest(unittest.TestCase):
    def store(self, claims="", notices="date,kind,plan,gmail_id,ref,reviewed\n", acc=""):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "plans.yaml").write_text(PLANS, encoding="utf-8")
        (d / "claims.csv").write_text(HEAD + claims, encoding="utf-8")
        (d / "notices.csv").write_text(notices, encoding="utf-8")
        (d / "accumulators.csv").write_text(
            "as_of,plan,member,deductible_met,deductible_limit,oop_met,oop_limit,annual_max_used,annual_max,source\n"
            + acc, encoding="utf-8")
        return d

    def codes(self, d, today=dt.date(2026, 11, 8)):
        return {i["code"] for i in eob_check.run(d, today)}

    def test_denied_cob_and_overbilled(self):
        d = self.store("dental,C1,Parent A,Example Dental,in,2026-09-08,2026-09-20,200,150,0,0,0,0,150,150,"
                       "denied,Other insurance on file,2026-12-01,180,,,,\n")
        self.assertTrue({"DENIED", "COB", "OVERBILLED", "APPEAL_CLOCK", "REIMBURSE"} <= self.codes(d))

    def test_resolved_claim_is_quiet(self):
        d = self.store("dental,C1,Parent A,Example Dental,in,2026-09-08,2026-09-20,200,150,0,0,0,0,150,150,"
                       "denied,x,,,HSA,,appealed and paid 2026-10-30,\n")
        self.assertNotIn("DENIED", self.codes(d))

    def test_not_member_pending_and_expected(self):
        d = self.store("dental,C2,Relative 1,Example Dental,in,2026-09-01,,100,,,,,,,0,pending,,,,,,,\n")
        self.assertTrue({"NOT_MEMBER", "PENDING_AGED", "EXPECTED_MISSING"} <= self.codes(d))

    def test_unread_notice_and_premium_gap(self):
        notices = ("date,kind,plan,gmail_id,ref,reviewed\n"
                   "2026-08-04,premium_paid,dental,a,,\n"
                   "2026-10-02,premium_paid,dental,b,,\n"
                   "2026-10-04,eob,dental,c,,\n")
        issues = eob_check.run(self.store(notices=notices), dt.date(2026, 11, 8))
        gaps = [i["ref"] for i in issues if i["code"] == "PREMIUM_MISSING"]
        self.assertEqual(gaps, ["2026-09", "2026-11"])
        self.assertIn("EOB_UNREAD", {i["code"] for i in issues})

    def test_mark_reviewed(self):
        notices = "date,kind,plan,gmail_id,ref,reviewed\n2026-10-04,eob,dental,c,,\n2026-11-20,eob,dental,d,,\n"
        d = self.store(notices=notices)
        self.assertEqual(eob_check.mark_reviewed(d, "dental", dt.date(2026, 11, 8)), 1)

    def test_cleanings(self):
        d = self.store(
            "dental,A,Parent A,Example Dental,out,2025-12-17,,55,,0,,,,,55,denied,CARC 119: limit,,,,,,,denied\n"
            "dental,B,Parent A,Example Dental,out,2026-02-25,,55,,5,,,,,50,paid,,,,,,,,covered\n"
            "dental,C,Parent A,Example Dental,out,2026-08-25,,55,,55,,,,,0,paid,,,,,,,,covered\n"
            "dental,D,Child 1,Sample Family Dental,in,2026-05-26,,55,,40,,,,,0,paid,,,,,,,,covered\n",
        )
        (d / "claims.csv").write_text((d / "claims.csv").read_text().replace("notes\n", "notes,cleaning\n", 1))
        (d / "plans.yaml").write_text(PLANS.replace("members: [Parent A, Child 1]",
                                                    "members: [Parent A, Child 1]\n    cleanings_per_year: 2"))
        issues = {(i["code"], i["ref"], i["sev"]) for i in eob_check.run(d, dt.date(2026, 11, 8))}
        self.assertIn(("CLEANINGS_USED", "Parent A", "ACT"), issues)
        self.assertIn(("CLEANING_LEFT", "Child 1", "INFO"), issues)

    def test_premium_gap_is_per_plan(self):
        notices = ("date,kind,plan,gmail_id,ref,reviewed\n"
                   "2026-10-02,premium_paid,vision,a,,\n"
                   "2026-11-02,premium_paid,vision,b,,\n")
        issues = eob_check.run(self.store(notices=notices), dt.date(2026, 11, 8))
        self.assertEqual([i["plan"] for i in issues if i["code"] == "PREMIUM_MISSING"], [])

    def test_sample_store_runs(self):
        store = pathlib.Path(__file__).resolve().parents[1] / "examples" / "store"
        codes = {i["code"] for i in eob_check.run(store, dt.date(2026, 11, 8))}
        self.assertTrue({"DENIED", "OVERBILLED", "CLEANINGS_USED", "EXPECTED_MISSING"} <= codes)

    def test_accumulator_yearend(self):
        d = self.store(acc="2026-11-01,medical,Parent B,3400,3400,5600,6800,,,portal\n")
        self.assertIn("ACCUMULATOR", self.codes(d))


if __name__ == "__main__":
    unittest.main()
