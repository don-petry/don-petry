"""Tests for tools/check_no_pii.py — run: python3 -m pytest tools  (or python3 -m unittest discover tools)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_no_pii as c  # noqa: E402


def hits(rel, text, rules=None):
    return [v["rule"] for v in c.scan_text(rel, text, c.BASE_RULES if rules is None else rules)]


class BaseRules(unittest.TestCase):
    def test_surname_flagged_outside_author_name(self):
        self.assertEqual(hits("skills/x/SKILL.md", "The Petry family flies Delta."), ["Household surname"])

    def test_author_name_and_handle_allowed(self):
        self.assertEqual(hits("skills/x/SKILL.md", "By Don Petry — github.com/don-petry/don-petry"), [])
        self.assertEqual(hits("LICENSE", "Copyright (c) 2026 Don Petry"), [])

    def test_profile_files_skip_surname_and_gmail(self):
        self.assertEqual(hits("CV.md", "Petry · someone@gmail.com"), [])

    def test_gmail_flagged_and_placeholders_allowed(self):
        self.assertEqual(hits("a.md", "write to jane.doe@gmail.com"), ["Personal Gmail address"])
        self.assertEqual(hits("a.md", "your-email@gmail.com or name@example.com"), [])

    def test_ssn(self):
        self.assertEqual(hits("a.md", "SSN 412-55-1234"), ["US Social Security number"])
        self.assertEqual(hits("a.md", "SSN 123-45-6789"), [])

    def test_private_ip_flagged_documentation_range_allowed(self):
        self.assertEqual(hits("a.py", 'HOST = "10.0.0.200"'), ["Private network address"])
        self.assertEqual(hits("a.py", 'HOST = "192.168.1.5"'), ["Private network address"])
        self.assertEqual(hits("a.py", 'HOST = "192.0.2.200"  # version 10.0.1'), [])

    def test_pii_ignore(self):
        self.assertEqual(hits("a.md", "Petry  <!-- pii-ignore -->"), [])


class CustomRules(unittest.TestCase):
    rules = [{"name": "Kid name", "pattern": r"\bAlexandra\b", "whitelist": [r"Alexandra Avenue"]}]

    def test_env_var_rules(self):
        r = c.load_custom_rules({"PII_CUSTOM_RULES_JSON": json.dumps(self.rules)}, Path("/nonexistent"))
        self.assertEqual(hits("a.md", "Alexandra has practice", r), ["Kid name"])
        self.assertEqual(hits("a.md", "123 Alexandra Avenue", r), [])

    def test_file_rules(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".pii-rules.json").write_text(json.dumps(self.rules), encoding="utf-8")
            self.assertEqual(len(c.load_custom_rules({}, Path(td))), 1)

    def test_no_rules(self):
        self.assertEqual(c.load_custom_rules({}, Path("/nonexistent")), [])


class Files(unittest.TestCase):
    def test_binary_and_self_skipped(self):
        self.assertFalse(c.scannable("forms/a.pdf"))
        self.assertFalse(c.scannable(".pii-rules.json"))
        self.assertTrue(c.scannable("scripts/run"))   # extensionless files are scanned

    def test_utf16_decoded(self):
        self.assertIn("Petry", c.decode("Petry".encode("utf-16"), "a.txt"))


if __name__ == "__main__":
    unittest.main()
