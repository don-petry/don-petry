"""Tests for alegeus_sync.py:  python3 -m unittest skills/hsa-fsa-reimburse/scripts/test_alegeus_sync.py"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import alegeus_sync as al  # noqa: E402


def row(acct="HSA", type_="CARD TRANSACTION", paid=10, amount=10, status="Paid", merchant="CORNER PHARMACY #12",
        mcc="Drug Stores and Pharmacies", date="2026-03-01", key="k1", balance_due=0, seq=1, svc=""):
    return {"key": key, "item": "", "seq": seq, "date": date, "settled": "", "type": type_, "acct": acct,
            "merchant": merchant, "mcc": mcc, "amount": amount, "paid": paid, "status": status, "claimant": "Parent B",
            "svc_start": svc, "svc_end": "", "provider": "", "patient": "", "balance_due": balance_due,
            "ineligible": 0, "reason": "", "claim_id": "", "receipts": False}


ACCOUNTS = [
    {"acct": "HSA", "plan": "HSA", "start": "2020-01-01", "end": "2099-12-31", "available": 100.0, "portfolio": 50.0,
     "rollover_in": None, "last_claim": "2099-12-31", "election": None, "deposits": None, "spent": None,
     "total": 150.0, "balance_due": 0},
    {"acct": "FSA", "plan": "FSACV", "start": "2024-01-01", "end": "2024-12-31", "available": 12.5, "portfolio": None,
     "rollover_in": 600, "last_claim": "2025-03-31", "election": 3000, "deposits": 3000, "spent": 2987.5,
     "total": 3600, "balance_due": 0},
]


class PostingTests(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(al.posting(row()), (-10.0, "Expenses:Healthcare:Pharmacy"))
        self.assertIsNone(al.posting(row(status="Denied")))
        self.assertIsNone(al.posting(row(acct="ERR")))
        self.assertEqual(al.posting(row(type_="DEPOSIT", merchant="Payroll Deposit", mcc="")),
                         (10.0, "Income:Salary:Employer"))
        self.assertEqual(al.posting(row(type_="INVESTMENT ACCOUNT FEE", amount=2.5, paid=-2.5)),
                         (-2.5, "Expenses:Financial:BankFees"))
        self.assertEqual(al.posting(row(type_="REFUND", amount=-35, paid=35, mcc="", merchant="AFFINITY")),
                         (35.0, "Expenses:Healthcare:Medical"))
        self.assertEqual(al.posting(row(acct="DCA", type_="MANUAL CLAIM", paid=375.14, amount=500, mcc="",
                                        merchant="Dependent Care / SAMPLE AFTERCARE", status="Partially Paid")),
                         (-375.14, "Equity:Transfers"))
        self.assertEqual(al.posting(row(acct="FSA", paid=0, amount=45, balance_due=45, status="Ineligible Purchase",
                                        merchant="EXAMPLE FAMILY DENTAL", mcc="Dentists, Orthodontists")),
                         (-45.0, "Expenses:Healthcare:Dental"))
        self.assertEqual(al.posting(row(acct="DCA", type_="MEMBER CLAIM", paid=4166.80, amount=5000, mcc="",
                                        merchant="Sample Aftercare", status="Partially Paid")),
                         (-4166.8, "Equity:Transfers"))
        self.assertIsNone(al.posting(row(acct="", type_="MEMBER CLAIM", paid=0, amount=5000, status="Under Review")))
        with self.assertRaises(ValueError):
            al.posting(row(type_="SOMETHING NEW"))

    def test_ids_are_unique_and_stable(self):
        rows = al.with_ids([row(key="a"), row(key="a"), row(key="", date="2026-01-01", amount=5)])
        ids = [r["id"] for r in rows]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(ids, [r["id"] for r in al.with_ids([row(key="a"), row(key="a"),
                                                              row(key="", date="2026-01-01", amount=5)])])

    def test_capture_day_is_the_household_zone(self):
        self.assertEqual(al.local_day("2026-11-09T02:31:13.657Z", "America/Chicago"), "2026-11-08")
        self.assertEqual(al.local_day("2026-11-09T02:31:13.657Z"), "2026-11-09")

    def test_config_maps_codes_accounts_and_hints(self):
        st = al.Settings({"administrator": {"codes": {"hsa": "BANK"}, "short_name": "Admin Co"},
                          "ledger": {"accounts": {"payroll": "Income:Salary:Acme"},
                                     "category_hints": {"dental": ["smiles"]}}})
        self.assertEqual(al.posting(row(acct="BANK", type_="DEPOSIT", mcc=""), st), (10.0, "Income:Salary:Acme"))
        self.assertIsNone(al.posting(row(acct="HSA"), st))
        self.assertEqual(al.category(row(acct="BANK", mcc="", merchant="BIG SMILES LLC"), st),
                         "Expenses:Healthcare:Dental")


class LedgerTests(unittest.TestCase):
    def test_ledger_has_pads_assertions_rollover_and_forfeit(self):
        acts = [dict(r, id=f"x{i}") for i, r in enumerate([
            row(type_="DEPOSIT", amount=100, paid=100, date="2024-01-12", merchant="Employee Contribution", mcc=""),
            row(acct="FSA", type_="DEPOSIT", amount=3000, paid=3000, date="2024-01-12", merchant="Payroll Deposit", mcc=""),
            row(acct="FSA", status="Denied", date="2024-02-01"),
        ])]
        text = al.ledger_text(acts, [dict(a, as_of="2026-11-08") for a in ACCOUNTS])
        self.assertIn("2024-01-11 pad Assets:HSA:Cash Equity:Opening-Balances", text)
        self.assertIn("2026-11-09 balance Assets:HSA:Cash 100.00 USD", text)
        self.assertIn("2026-11-09 balance Assets:HSA:Invested 50.00 USD", text)
        self.assertIn("rollover in from 2023", text)
        self.assertIn("2025-04-01 * \"Administrator\" \"Health FSA 2024: left after the 2025-03-31 claim deadline", text)
        self.assertEqual(text.count("alegeus_id"), 2)                  # the denial moved no money

    def test_merge_replaces_captured_years_only(self):
        with tempfile.TemporaryDirectory() as d:
            store = pathlib.Path(d)
            cap = {"captured": "2026-11-09T02:00:00Z", "years": [2026], "accounts": ACCOUNTS,
                   "activity": [row(key="a"), row(key="old", date="2025-05-01")]}
            self.assertEqual(al.merge(cap, store), (2, 2))
            cap2 = dict(cap, activity=[row(key="b")])
            total, added = al.merge(cap2, store)
            ids = [r["id"] for r in al.read_csv(store / "activity.csv")]
            self.assertEqual((total, added), (2, 1))
            self.assertTrue(any("old" in i for i in ids) and any("|b|" in i for i in ids))
            path = store / "cap.json"
            path.write_text(json.dumps([{"type": "text", "text": json.dumps(json.dumps(cap))}]), encoding="utf-8")
            self.assertEqual(al.load_capture(path)["years"], [2026])


if __name__ == "__main__":
    unittest.main()
