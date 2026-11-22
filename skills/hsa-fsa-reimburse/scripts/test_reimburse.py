"""Tests for reimburse.py:  python3 -m unittest skills/hsa-fsa-reimburse/scripts/test_reimburse.py"""
import csv
import datetime as dt
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reimburse as rb  # noqa: E402

FIELDS = ["plan", "claim_id", "patient", "provider", "service_date", "patient_resp", "reimbursed",
          "eob_drive_id", "notes"]
ACCOUNTS = """
hsa: {holder: parent-b, policy: null}
fsa:
  years:
    2026: {election: 100, claim_deadline: 2027-03-31, used_outside_register: 0}
fsa_eligible_plans: [dental]
ortho_match: [Bright Braces, ORTHODONTICS]
people: {Parent A: parent-a, Parent B: parent-b, Child 2: child-2}
"""
PROJECT = "id: x\nhealth:\n  hsa_eligible: {status: %s, basis: test}\n"


def claim(cid, patient="Parent A", plan="medical", amount="40.00", date="2026-03-01", provider="Dr A",
          pdf="drive1", reimbursed="", notes=""):
    return {"plan": plan, "claim_id": cid, "patient": patient, "provider": provider,
            "service_date": date, "patient_resp": amount, "reimbursed": reimbursed,
            "eob_drive_id": pdf, "notes": notes}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.store, self.projects, self.ledger = root / "store", root / "projects", root / "ledger"
        for d in (self.store, self.projects, self.ledger):
            d.mkdir()
        (self.store / "accounts.yaml").write_text(ACCOUNTS, encoding="utf-8")
        for slug, status in (("parent-a", "yes"), ("parent-b", '"yes"'), ("child-2", "unknown")):
            (self.projects / slug).mkdir()
            (self.projects / slug / "project.yaml").write_text(PROJECT % status, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write_claims(self, rows):
        with (self.store / "claims.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def run_plan(self, today="2026-11-08", year=2026):
        accounts, claims, register, elig, ledger, cards = rb.load_all(self.store, self.projects, self.ledger)
        return rb.plan(claims, accounts, register, elig, ledger, year, dt.date.fromisoformat(today), cards)["buckets"]

    def write_activity(self, rows):
        (self.store / "administrator").mkdir(exist_ok=True)
        fields = ["id", "date", "acct", "type", "merchant", "paid", "status", "balance_due"]
        with (self.store / "administrator" / "activity.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(dict(zip(fields, r)) for r in rows)

    def ids(self, rows):
        return [r["claim_id"] for r in rows]


class PlanTests(Base):
    def test_bare_yes_in_yaml_counts_as_eligible(self):
        self.write_claims([claim("1"), claim("2", patient="Parent B")])
        self.assertEqual(self.ids(self.run_plan()["HSA"]), ["1", "2"])

    def test_unknown_eligibility_is_held_whatever_else(self):
        self.write_claims([claim("1", patient="Child 2"), claim("2", patient="Nobody")])
        b = self.run_plan()
        self.assertEqual(self.ids(b["held_eligibility"]), ["1", "2"])
        self.assertEqual(b["HSA"], [])

    def test_dental_fills_fsa_then_overflows_to_hsa(self):
        self.write_claims([claim("1", plan="dental", amount="60", date="2026-02-01"),
                           claim("2", plan="dental", amount="60", date="2026-03-01"),
                           claim("3", plan="dental", amount="40", date="2026-04-01")])
        b = self.run_plan()
        self.assertEqual(self.ids(b["FSA"]), ["1", "3"])
        self.assertEqual(self.ids(b["HSA"]), ["2"])

    def test_fsa_deadline_passed_goes_to_hsa(self):
        self.write_claims([claim("1", plan="dental", amount="10")])
        b = self.run_plan(today="2027-04-01")
        self.assertEqual(self.ids(b["HSA"]), ["1"])

    def test_ortho_routed_apart(self):
        self.write_claims([claim("1", plan="dental", provider="Bright Braces DMD"),
                           claim("2", plan="dental", notes="ORTHODONTICS")])
        self.assertEqual(self.ids(self.run_plan()["ortho"]), ["1", "2"])

    def test_skips_reimbursed_zero_other_year_and_holds_missing_pdf(self):
        self.write_claims([claim("1", reimbursed="HSA"), claim("2", amount="0"),
                           claim("3", date="2025-12-31"), claim("4", pdf="")])
        b = self.run_plan()
        self.assertEqual(self.ids(b["held_no_pdf"]), ["4"])
        self.assertEqual(sum(len(v) for v in b.values()), 1)

    def test_ledger_candidate_matches_amount_in_window(self):
        self.write_claims([claim("1", amount="22.49", date="2026-03-01")])
        (self.ledger / "t.bean").write_text(
            '2026-03-05 * "Doctor" "Healthcare/Medical"\n'
            "  Expenses:Healthcare:Medical  22.49 USD\n  Liabilities:Card  -22.49 USD\n"
            '2027-03-05 * "Late" ""\n  Expenses:Healthcare:Medical  22.49 USD\n', encoding="utf-8")
        row = self.run_plan()["HSA"][0]
        self.assertEqual([t[1] for t in row["ledger"]], ["Doctor"])


    def test_administrator_ledger_is_not_out_of_pocket_evidence(self):
        self.write_claims([claim("1", amount="22.49", date="2026-03-01")])
        (self.ledger / "alegeus_hsa_fsa.bean").write_text(
            '2026-03-05 * "Doctor" "HSA: Card Transaction"\n'
            "  Assets:HSA:Cash  -22.49 USD\n  Expenses:Healthcare:Medical  22.49 USD\n", encoding="utf-8")
        self.assertEqual(self.run_plan()["HSA"][0]["ledger"], [])


class SampleTests(unittest.TestCase):
    def test_fictional_sample_runs(self):
        root = pathlib.Path(__file__).resolve().parents[1] / "examples"
        accounts, claims, register, elig, ledger, cards = rb.load_all(root / "store", root / "projects", None)
        b = rb.plan(claims, accounts, register, elig, ledger, 2026, dt.date(2026, 11, 8), cards)["buckets"]
        self.assertEqual(self.ids(b["FSA"]), ["D1001"])
        self.assertEqual(self.ids(b["HSA"]), ["M2001"])
        self.assertEqual(self.ids(b["held_eligibility"]), ["M2003"])
        self.assertEqual(self.ids(b["ortho"]), ["D1006"])

    def ids(self, rows):
        return [r["claim_id"] for r in rows]


class CardMatchTests(Base):
    def test_unique_amount_matches_even_when_names_differ(self):
        self.write_claims([claim("1", amount="113.87", date="2026-01-27", provider="Jordan Sample MD")])
        self.write_activity([("a", "2026-04-12", "HSA", "CARD TRANSACTION", "SAMPLE PEDIATRICS PC", "113.87", "Paid", "0"),
                             ("b", "2026-04-13", "HSA", "CARD TRANSACTION", "SAMPLE PEDIATRICS PC", "113.87", "Denied", "0")])
        _, claims, register, _, _, cards = rb.load_all(self.store, self.projects, self.ledger)
        sure, unsure = rb.card_matches(claims, register, cards, 2026)
        self.assertEqual([(c["claim_id"], k["id"]) for c, k in sure], [("1", "a")])
        self.assertEqual(unsure, [])

    def test_one_payment_two_claims_is_ambiguous(self):
        self.write_claims([claim("1", amount="50", date="2026-02-25", provider="Avery Example DMD"),
                           claim("2", amount="50", date="2026-03-23", provider="Avery Example DMD")])
        self.write_activity([("a", "2026-06-02", "HSA", "CARD TRANSACTION", "DR. AVERY EXAMPLE DMD", "50", "Paid", "0")])
        _, claims, register, _, _, cards = rb.load_all(self.store, self.projects, self.ledger)
        sure, unsure = rb.card_matches(claims, register, cards, 2026)
        self.assertEqual(sure, [])
        self.assertEqual(len(unsure), 2)

    def test_balance_due_charge_counts_as_paid(self):
        self.write_claims([claim("1", plan="dental", amount="45", date="2026-04-28")])
        self.write_activity([("a", "2026-04-28", "FSA", "CARD TRANSACTION", "DR. AVERY EXAMPLE DMD", "0",
                              "Ineligible Purchase", "45")])
        row = self.run_plan()["FSA"][0]
        self.assertEqual((row["card"][0]["acct"], row["card"][0]["balance_due"]), ("FSA", 45.0))


class RecordTests(Base):
    def test_record_writes_register_and_claims_then_plan_skips(self):
        self.write_claims([claim("1"), claim("2")])
        rb.cmd_record(self.store, "1", "card", "submitted", "2026-11-08", None, "paid by HSA card")
        _, claims = rb.read_csv(self.store / "claims.csv")
        self.assertEqual({c["claim_id"]: c["reimbursed"] for c in claims}, {"1": "HSA", "2": ""})
        _, reg = rb.read_csv(self.store / "reimbursements.csv")
        self.assertEqual((reg[0]["status"], reg[0]["account"], reg[0]["amount"]), ("paid-by-card", "HSA", "40.00"))
        self.assertEqual(self.ids(self.run_plan()["HSA"]), ["2"])

    def test_fsa_record_uses_up_room(self):
        self.write_claims([claim("1", plan="dental", amount="90"), claim("2", plan="dental", amount="20")])
        rb.cmd_record(self.store, "1", "FSA", "submitted", "2026-11-08", None, None)
        self.assertEqual(self.ids(self.run_plan()["HSA"]), ["2"])

    def test_denied_clears_the_mark(self):
        self.write_claims([claim("1")])
        rb.cmd_record(self.store, "1", "HSA", "submitted", "2026-11-08", None, None)
        rb.cmd_record(self.store, "1", "HSA", "denied", "2026-11-09", None, None)
        _, claims = rb.read_csv(self.store / "claims.csv")
        self.assertEqual(claims[0]["reimbursed"], "")
        self.assertEqual(self.ids(self.run_plan()["HSA"]), ["1"])

    def test_split_claim_keeps_the_rest_in_the_plan(self):
        self.write_claims([claim("1", plan="dental", amount="68.40")])
        rb.cmd_record(self.store, "1", "FSA", "submitted", "2026-11-08", "55", "substitute receipt")
        _, claims = rb.read_csv(self.store / "claims.csv")
        self.assertEqual(claims[0]["reimbursed"], "partial")
        rows = self.run_plan()["FSA"]          # $45 of FSA room is left, so the $13.40 rest goes there
        self.assertEqual((self.ids(rows), rows[0]["amount"], rows[0]["already"]), (["1"], 13.4, 55.0))

    def test_record_without_amount_takes_the_rest_and_keeps_both_parts(self):
        self.write_claims([claim("1", plan="dental", amount="68.40")])
        rb.cmd_record(self.store, "1", "FSA", "submitted", "2026-11-08", "55", None)
        rb.cmd_record(self.store, "1", "HSA", "submitted", "2026-11-09", None, None)
        _, reg = rb.read_csv(self.store / "reimbursements.csv")
        self.assertEqual(sorted((r["account"], r["amount"]) for r in reg), [("FSA", "55.00"), ("HSA", "13.40")])
        _, claims = rb.read_csv(self.store / "claims.csv")
        self.assertEqual(claims[0]["reimbursed"], "FSA+HSA")
        self.assertEqual(sum(len(v) for v in self.run_plan().values()), 0)

    def test_over_reimbursing_a_split_claim_refused(self):
        self.write_claims([claim("1", amount="68.40")])
        rb.cmd_record(self.store, "1", "FSA", "submitted", "2026-11-08", "55", None)
        with self.assertRaises(SystemExit):
            rb.cmd_record(self.store, "1", "HSA", "submitted", "2026-11-09", "68.40", None)

    def test_whole_claim_switching_account_replaces_the_old_row(self):
        self.write_claims([claim("1")])
        rb.cmd_record(self.store, "1", "FSA", "submitted", "2026-11-08", None, None)
        rb.cmd_record(self.store, "1", "HSA", "submitted", "2026-11-09", None, None)
        _, reg = rb.read_csv(self.store / "reimbursements.csv")
        self.assertEqual([(r["account"], r["amount"]) for r in reg], [("HSA", "40.00")])

    def test_denied_part_of_a_split_returns_to_the_plan(self):
        self.write_claims([claim("1", amount="68.40")])
        rb.cmd_record(self.store, "1", "FSA", "submitted", "2026-11-08", "55", None)
        rb.cmd_record(self.store, "1", "HSA", "submitted", "2026-11-09", None, None)
        rb.cmd_record(self.store, "1", "HSA", "denied", "2026-11-10", None, None)
        self.assertEqual(self.run_plan()["HSA"][0]["amount"], 13.4)

    def test_unknown_claim_refused(self):
        self.write_claims([claim("1")])
        with self.assertRaises(SystemExit):
            rb.cmd_record(self.store, "9", "HSA", "submitted", "2026-11-08", None, None)


if __name__ == "__main__":
    unittest.main()
