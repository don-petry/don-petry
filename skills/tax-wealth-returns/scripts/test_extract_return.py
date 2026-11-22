"""Tests for extract_return.py that need no PDF — run:
    python3 -m unittest scripts/test_extract_return.py   (from the skill folder)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import extract_return as er  # noqa: E402


def w(text, x0, top, width=None):
    width = width if width is not None else 6.0 * len(text)
    return {"text": text, "x0": x0, "x1": x0 + width, "top": top}


class Numbers(unittest.TestCase):
    def test_amount_formats(self):
        self.assertEqual(er.to_number("476,889."), 476889.0)
        self.assertEqual(er.to_number("20,572•"), 20572.0)
        self.assertEqual(er.to_number("(3,000.)"), -3000.0)
        # the text layer can split "(" into its own word, leaving only the closing paren
        self.assertEqual(er.to_number("3,000.)"), -3000.0)
        self.assertEqual(er.to_number("-3,000."), -3000.0)
        self.assertEqual(er.to_number("0."), 0.0)
        self.assertIsNone(er.to_number("123-45-6789"))   # SSN-shaped, not an amount
        self.assertIsNone(er.to_number("Schedule"))


class Pairing(unittest.TestCase):
    def test_federal_value_slightly_above_label(self):
        words = [w("15", 488, 148), w("397,992.", 525, 146), w("12e", 486, 100), w("77,801.", 531, 96),
                 w("16", 488, 160), w("80,804.", 531, 156)]
        got = er.pair_lines(words, 612)
        self.assertEqual(got["15"]["value"], 397992.0)
        self.assertEqual(got["12e"]["value"], 77801.0)

    def test_al_value_on_same_row(self):
        words = [w("10", 468, 338), w("474,953", 533, 338), w("11", 352, 386), w("87,212", 423, 386)]
        got = er.pair_lines(words, 612)
        self.assertEqual(got["10"]["value"], 474953.0)
        self.assertEqual(got["11"]["value"], 87212.0)

    def test_prose_numbers_on_left_are_not_values(self):
        # "Form(s): 1 8814 2 4972" sits in the left half of the page and must not pair
        words = [w("1", 302, 160), w("8814", 325, 160), w("2", 360, 160), w("4972", 382, 160)]
        self.assertEqual(er.pair_lines(words, 612), {})

    def test_undotted_numbers_dropped_on_dotted_pages(self):
        words = [w("11a", 486, 40), w("476,889.", 525, 36), w("15", 488, 148), w("397,992.", 525, 146),
                 w("24", 488, 256), w("83,265.", 531, 252), w("76", 400, 98), w("7564", 526, 98)]
        got = er.pair_lines(words, 612)
        self.assertNotIn("76", got)
        self.assertEqual(len(got), 3)

    def test_parenthesized_negative_pairs_on_dotted_page(self):
        for token in ("(3,000.)", "3,000.)"):
            words = [w("1z", 486, 40), w("476,889.", 525, 36), w("9", 488, 148), w("395,439.", 525, 146),
                     w("8", 488, 136), w("1,935.", 531, 132), w("7", 488, 124), w(token, 525, 120)]
            got = er.pair_lines(words, 612)
            self.assertEqual(got["7"]["value"], -3000.0, token)

    def test_1040_p1_middle_column(self):
        # 1040 p1: "3a Qualified dividends . . 3a [1,383.]  b Ordinary dividends . . 3b [2,308.]"
        words = [w("3a", 40, 560), w("3a", 222, 560), w("1,383.", 262, 557), w("3b", 488, 560),
                 w("2,308.", 525, 557), w("2a", 40, 548), w("2a", 222, 548), w("0.", 300, 545),
                 w("2b", 488, 548), w("402.", 540, 545), w("1z", 488, 535), w("418,987.", 525, 532)]
        self.assertEqual(er.value_min_x_ratio("1040", "p1"), 0.35)
        self.assertEqual(er.value_min_x_ratio("1040", "p2"), er.VALUE_MIN_X_RATIO)
        self.assertEqual(er.value_min_x_ratio("schE", "p1"), 0.40)
        got = er.pair_lines(words, 612, er.value_min_x_ratio("1040", "p1"))
        self.assertEqual(got["3a"]["value"], 1383.0)
        self.assertEqual(got["2a"]["value"], 0.0)
        self.assertEqual(got["3b"]["value"], 2308.0)
        self.assertEqual(got["2b"]["value"], 402.0)
        # the old right-column-only threshold never sees the middle boxes
        self.assertNotIn("3a", er.pair_lines(words, 612))

    def test_line_number_tags_are_not_amounts(self):
        # 2025 Schedule B: "... on Form 1040, line 2b   4   1,833.29" — undotted cents, tag "4" beside the amount
        words = [w("2", 440, 312.6), w("1,833.29", 520, 312.6),
                 w("2b", 400, 350.4), w("4", 450, 350.4), w("1,833.29", 520, 348.7),
                 w("3b", 400, 554.4), w("6", 450, 554.4), w("3,758.72", 520, 552.5)]
        # before 0.2.0 the tags themselves were taken: {"2b": 4.0, "3b": 6.0}
        got = er.pair_lines(words, 612)
        self.assertEqual(got["2b"]["value"], 1833.29)
        self.assertEqual(got["4"]["value"], 1833.29)
        self.assertEqual(got["3b"]["value"], 3758.72)
        self.assertEqual(got["6"]["value"], 3758.72)

    def test_label_and_column_tag_pair_with_the_amount(self):
        # AL p1: left label "12", column tag "12", amount — the tag is not the amount
        got = er.pair_lines([w("12", 352, 410), w("12", 440, 410), w("62,637", 533, 410)], 612)
        self.assertEqual(got, {"12": {"value": 62637.0, "token": "62,637", "y": 410}})

    def test_zero_stays_an_amount(self):
        got = er.pair_lines([w("19", 468, 494.6), w("0", 560, 494.6)], 612)
        self.assertEqual(got["19"]["value"], 0.0)


class Classification(unittest.TestCase):
    def test_federal_pages(self):
        self.assertEqual(er.classify("Form 1040 (2025) Page 2\nTax and 11b", "federal"), ("1040", "p2"))
        self.assertEqual(er.classify("mroF\n1040\n2024\nDepartment of the Treasury—Internal Revenue Service\n"
                                     "U.S. Individual Income Tax Return", "federal"), ("1040", "p1"))
        self.assertEqual(er.classify("SCHEDULE E Supplemental Income and Loss", "federal"), ("schE", "p1"))
        self.assertEqual(er.classify("8889 Health Savings Accounts (HSAs)", "federal"), (None, None))

    def test_al_pages(self):
        self.assertEqual(er.classify("FORM\n40\nAlabama\n2025", "al"), ("40", "p1"))
        self.assertEqual(er.classify("Form 40 (2025) Page 2\nPART I", "al"), ("40", "p2"))
        # a federal form page inside the AL section is not an AL form
        self.assertEqual(er.classify("Form 1040 (2025) Page 2", "al"), (None, None))

    def test_al_schedule_a(self):
        for head in ("SCHEDULE\nA\n(Form 40)\nItemized Deductions", "SCHEDULES\nA, B, D\nForm 40\n2023",
                     "SCHEDULES A & B\nFORM 40\nAlabama Itemized Deductions", "SCHEDULE A\nAlabama Department of Revenue"):
            self.assertEqual(er.classify(head, "al"), ("al_schA", "p1"), head)
        # a federal Schedule A attached to the AL return is not the AL schedule
        self.assertEqual(er.classify("SCHEDULE A\n(Form 1040)\nItemized Deductions\nAlabama", "al"), (None, None))
        self.assertEqual(er.classify("SCHEDULE\n| ATP\nForm 40", "al"), ("al_schATP", "p1"))
        self.assertEqual(er.classify("SCHEDULE\nOC\nOther Available Credits", "al"), ("al_schOC", "p1"))

    def test_sections(self):
        self.assertEqual(er.section_of("Electronic Filing Instructions for your 2024 Alabama Tax Return", "federal"), "al")
        self.assertEqual(er.section_of("mroF | 1040 | U.S. Individual Income Tax Return", "al"), "federal")
        self.assertEqual(er.section_of("Schedule OC (Form 40 or 40NR) 2024 Page 2", "al"), "al")


FED_2025 = {  # the committed 2025 federal summary, abridged
    "wages": 465167.0, "taxable_interest": 1833.0, "ordinary_dividends": 3759.0, "ira_taxable": 1.0,
    "capital_gain": 2373.0, "other_income_sch1": 3756.0, "total_income": 476889.0, "adjustments": None,
    "agi": 476889.0, "deductions": 77801.0, "qbi_deduction": 1096.0, "deductions_total": 78897.0,
    "taxable_income": 397992.0, "tax": 80804.0, "nonrefundable_credits": 76.0, "tax_after_credits": 80728.0,
    "other_taxes": 2537.0, "total_tax": 83265.0, "withholding": 66493.0, "total_payments": 66493.0,
    "overpaid": None, "refund": None, "amount_owed": 17166.0, "estimated_tax_penalty": 394.0,
}
AL_2024 = {
    "wages": 417991.0, "interest_dividends": 2710.0, "other_income": -336.0, "total_income": 420365.0,
    "adjustments": 8400.0, "agi": 411965.0, "deductions": 85455.0, "federal_tax_deduction": 66831.0,
    "personal_exemption": 3000.0, "dependent_exemption": 900.0, "deductions_total": 156186.0,
    "taxable_income": 255779.0, "income_tax": 12707.0, "net_tax": 1707.0, "additional_taxes": 0.0,
    "total_tax": 1707.0, "adjusted_total_payments": 18406.0, "amount_owed": None, "overpaid": 16699.0,
    "applied_to_next_year": None, "donations": None, "refund": None,
}


def status(results, name):
    return next(c["status"] for c in results if c["check"].startswith(name))


class Checks(unittest.TestCase):
    def test_cover_mismatch_fails(self):
        res = er.checks({"agi": 100.0}, {"agi": {"value": 101.0}})
        self.assertEqual(res[0]["status"], "FAIL")

    def test_taxable_identity(self):
        res = er.checks({"agi": 1000.0, "deductions_total": 300.0, "taxable_income": 700.0}, {})
        self.assertEqual(status(res, "taxable_income =="), "PASS")

    def test_blank_adjustments_count_as_zero(self):
        self.assertEqual(status(er.checks({"total_income": 100.0, "adjustments": None, "agi": 100.0}, {}),
                                "agi =="), "PASS")
        # a $10 mismatch with line 10 blank is no longer silently dropped
        res = er.checks({"total_income": 100.0, "adjustments": None, "agi": 90.0}, {})
        self.assertEqual(status(res, "agi =="), "GAP")
        self.assertEqual(er.exit_status(res), 1)

    def test_committed_federal_2025_passes(self):
        cover = {k: {"value": v} for k, v in (("agi", 476889.0), ("taxable_income", 397992.0),
                                              ("total_tax", 83265.0), ("total_payments", 66493.0),
                                              ("payment_due", 16772.0), ("penalty_interest", 394.0))}
        res = er.checks(FED_2025, cover, "federal")
        self.assertEqual({c["status"] for c in res}, {"PASS", "SKIPPED"}, [c for c in res if c["status"] != "PASS"])
        self.assertEqual(er.exit_status(res), 0)

    def test_wrong_tax_line_fails(self):
        res = er.checks(dict(FED_2025, total_tax=83000.0), {}, "federal")
        self.assertEqual(status(res, "total_tax =="), "FAIL")

    def test_al_refund_disposition_gap(self):
        res = er.checks(AL_2024, {}, "al")
        self.assertEqual(status(res, "overpaid == max"), "PASS")
        gap = next(c for c in res if c["check"].startswith("refund disposition"))
        self.assertEqual(gap["status"], "GAP")
        self.assertEqual(gap["unread"], ["applied_to_next_year", "donations", "refund"])
        self.assertEqual(er.exit_status(res), 1)
        self.assertEqual(status(er.checks(dict(AL_2024, refund=16699.0), {}, "al"), "refund disposition"), "PASS")

    def test_cover_value_without_return_value_is_a_gap(self):
        res = er.checks({"agi": None}, {"agi": {"value": 395439.0}})
        self.assertEqual(status(res, "cover.agi"), "GAP")
        self.assertEqual(er.exit_status(res), 1)

    def test_empty_extraction_exits_nonzero(self):
        res = er.checks({}, {})
        self.assertEqual({c["status"] for c in res}, {"SKIPPED"})
        self.assertEqual(er.exit_status(res), 1)


if __name__ == "__main__":
    unittest.main()
