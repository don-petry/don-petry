#!/usr/bin/env python3
"""Tests for verify_sources.py, the fail-closed source verification gate.

Offline: a fake fetcher replaces the network (ALISON, CourtListener, eCFR, Cornell LII,
irs.gov) and returns canned responses, so the adapters' own parsing is exercised.
    python3 -m pytest test_verify_sources.py     (or: python3 -m unittest)

The canaries are the point. The gate must fail the fabricated Varghese citation
from Mata v. Avianca, an altered quotation, an empty source page, a real citation
pinned to the wrong case name, another state's code section, a state section when no
state adapter is active, and a stale edition of an IRS publication.
"""

import json
import pathlib
import sys
import tempfile
import unittest
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
for _p in (HERE.parent / "scripts", HERE):   # self-private: scripts/; public repo: tools/ (beside this file)
    if (_p / "verify_sources.py").exists():
        sys.path.insert(0, str(_p))
        break

import verify_sources as vs  # noqa: E402

AGE_OF_MAJORITY = (
    "Age of Majority Designated as 19 Years. (a) Any person in this state, at the arrival at the age of 19 "
    "years, shall be relieved of his or her disabilities of minority and thereafter shall have the same legal "
    "rights and abilities as persons over 21 years of age."
)
ABERNATHY = "Abernathy v. Colbert County Hospital Bd."
CFR_152_4 = (
    "<div class='section'><h4>§ 1.152-4 Special rule for a child of divorced or separated parents or parents "
    "who live apart.</h4><p>(a) <i>In general.</i> A taxpayer may claim a dependency deduction for a child (as "
    "defined in section 152(f)(1)) only if the child is the qualifying child of the taxpayer under section "
    "152(c) or the qualifying relative of the taxpayer under section 152(d).</p></div>"
)
PUB_969 = (
    "<html><head><title>Publication 969 (2025), Health Savings Accounts and Other Tax-Favored Health Plans"
    "</title></head><body><h1>Publication 969 (2025), Health Savings Accounts and Other Tax-Favored Health "
    "Plans</h1><p>A health savings account (HSA) is a tax-exempt trust or custodial account that you set up "
    "with a qualified HSA trustee to pay or reimburse certain medical expenses you incur.</p></body></html>"
)
FCRA_1681I = (
    "<html><body><h1>15 U.S. Code § 1681i - Procedure in case of disputed accuracy</h1><p>If the completeness "
    "or accuracy of any item of information contained in a consumer's file at a consumer reporting agency is "
    "disputed by the consumer and the consumer notifies the agency directly of such dispute, the agency shall "
    "conduct a reasonable reinvestigation.</p></body></html>"
)


class FakeFetcher(vs.Fetcher):
    """Replaces Fetcher.get; everything above it (adapters, parsing) is the real code."""

    def __init__(self, base_dir, empty_alison=False, opinion_text=None, outage=False, ecfr_down=False,
                 token=None):
        super().__init__(token, base_dir)
        self.empty_alison, self.opinion_text, self.outage = empty_alison, opinion_text, outage
        self.ecfr_down = ecfr_down
        self.calls = []

    def get(self, url, data=None, headers=None):
        if self.outage:
            raise vs.Blocked(f"{url} unreachable")
        u = urllib.parse.urlparse(url)
        if "alison" in u.netloc:
            section = json.loads(data)["variables"]["d"]
            self.calls.append(("al", section))
            if self.empty_alison:
                rows = [{"displayId": section, "catchLine": "", "content": ""}]
            elif section == "26-1-1":
                rows = [{"displayId": section, "catchLine": "", "content": AGE_OF_MAJORITY}]
            else:
                rows = []
            return json.dumps({"data": {"codesOfAlabama": {"data": rows}}})
        if "courtlistener" in u.netloc and "/search/" in u.path:
            cite = urllib.parse.parse_qs(u.query)["q"][0].strip('"')
            self.calls.append(("case", cite))
            results = []
            if vs.norm_cite(cite) == vs.norm_cite("388 So. 2d 1207"):
                results = [{"citation": ["388 So. 2d 1207"], "absolute_url": "/opinion/1/abernathy/",
                            "caseName": ABERNATHY, "cluster_id": 1}]
            return json.dumps({"results": results})
        if "courtlistener" in u.netloc and "/opinions/" in u.path:
            return json.dumps({"results": [{"plain_text": self.opinion_text}] if self.opinion_text else []})
        if "ecfr.gov" in u.netloc:
            self.calls.append(("ecfr", url))
            if self.ecfr_down:
                raise vs.Blocked(f"{url} returned HTTP 503")
            if urllib.parse.parse_qs(u.query).get("section") == ["1.152-4"]:
                return CFR_152_4
            raise vs.NotFound(f"{url} returned 404")
        if "cornell.edu" in u.netloc:
            self.calls.append(("lii", u.path))
            if u.path.endswith("/26/1.152-4"):
                return CFR_152_4
            if u.path.endswith("/15/1681i"):
                return FCRA_1681I
            raise vs.NotFound(f"{url} returned 404")
        if "irs.gov" in u.netloc:
            self.calls.append(("irs", u.path))
            if u.path == "/publications/p969":
                return PUB_969
            raise vs.NotFound(f"{url} returned 404")
        raise AssertionError(f"unexpected fetch {url}")


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "drafts").mkdir()
        self.adir = self.root / "authorities"

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self, text, jurisdictions=("AL",), **kw):
        draft = self.root / "drafts" / "letter.md"
        draft.write_text(text, encoding="utf-8")
        fetcher = kw.pop("fetcher", None) or FakeFetcher(self.root / "drafts", **kw)
        return vs.verify(draft, fetcher, self.adir, jurisdictions=jurisdictions), fetcher

    # passing cases -------------------------------------------------------------
    def test_exact_statute_quote_passes_and_snapshots(self):
        rep, _ = self.run_gate(
            'Under Ala. Code § 26-1-1, a person "at the arrival at the age of 19 years, shall be relieved of '
            'his or her disabilities of minority".'
        )
        self.assertTrue(rep.ok, vs.render(rep))
        snap = self.adir / "al-code-26-1-1.txt"
        self.assertTrue(snap.exists())
        self.assertIn("sha256: ", snap.read_text(encoding="utf-8"))

    def test_ellipsis_and_curly_quotes_pass(self):
        rep, _ = self.run_gate("§ 26-1-1 says “Any person in this state … shall be relieved of his or her disabilities”.")
        self.assertTrue(rep.ok, vs.render(rep))

    def test_real_case_with_matching_name_passes(self):
        rep, _ = self.run_gate("See Abernathy v. Colbert County Hosp. Bd., 388 So. 2d 1207 (Ala. 1980).")
        self.assertTrue(rep.ok, vs.render(rep))

    def test_every_run_fetches_fresh(self):
        self.run_gate("§ 26-1-1 applies.")
        rep, f = self.run_gate("§ 26-1-1 applies again.")
        self.assertTrue(rep.ok)
        self.assertEqual(f.calls, [("al", "26-1-1")])

    def test_canary_forged_snapshot_is_never_trusted(self):
        import hashlib
        body = "Fabricated section text long enough to be accepted by the gate as a real statute, yes."
        snap = self.adir / "al-code-99-99-99.txt"
        snap.parent.mkdir(parents=True)
        snap.write_text("source: https://x\nfetched: 2099-01-01\nsha256: "
                        + hashlib.sha256(body.encode()).hexdigest() + "\n---\n" + body, encoding="utf-8")
        rep, _ = self.run_gate('Ala. Code § 99-99-99 says "accepted by the gate as a real statute".')
        self.assertFalse(rep.ok)

    # canaries --------------------------------------------------------------------
    def test_canary_fabricated_varghese_citation_fails(self):
        rep, _ = self.run_gate(
            "Varghese v. China Southern Airlines Co., 925 F.3d 1339 (11th Cir. 2019), tolls the limitations period."
        )
        self.assertFalse(rep.ok)
        self.assertEqual(rep.authorities[0].status, vs.FAIL)

    def test_canary_altered_quote_fails(self):
        rep, _ = self.run_gate(
            'Ala. Code § 26-1-1 provides that a person "at the arrival at the age of 18 years, shall be relieved of '
            'his or her disabilities of minority".'
        )
        self.assertFalse(rep.ok)
        self.assertEqual(rep.quotes[0].status, vs.FAIL)

    def test_canary_empty_alison_page_blocks(self):
        rep, _ = self.run_gate("§ 26-1-1 applies.", empty_alison=True)
        self.assertFalse(rep.ok)
        self.assertEqual(rep.authorities[0].status, vs.BLOCKED)

    def test_canary_real_cite_wrong_case_name_fails(self):
        rep, _ = self.run_gate("See Smith v. Jones, 388 So. 2d 1207 (Ala. 1980).")
        self.assertFalse(rep.ok)
        self.assertIn("belongs to", rep.authorities[0].reason)

    def test_canary_nonexistent_alabama_section_fails(self):
        rep, _ = self.run_gate("Ala. Code § 99-99-99 requires it.")
        self.assertEqual(rep.authorities[0].status, vs.FAIL)

    def test_canary_georgia_code_is_not_checked_as_alabama(self):
        rep, f = self.run_gate("O.C.G.A. § 19-9-3 governs custody.")
        self.assertFalse(rep.ok)
        self.assertEqual(rep.authorities[0].kind, "other")
        self.assertEqual(f.calls, [])

    def test_outage_blocks_rather_than_passes(self):
        rep, _ = self.run_gate("§ 26-1-1 applies.", outage=True)
        self.assertEqual(rep.authorities[0].status, vs.BLOCKED)
        self.assertFalse(rep.ok)

    def test_unattributed_quote_fails(self):
        rep, _ = self.run_gate('The adjuster said "we will never pay more than this amount".')
        self.assertEqual(rep.quotes[0].status, vs.FAIL)

    def test_case_quote_without_opinion_text_blocks(self):
        rep, _ = self.run_gate(
            'Abernathy v. Colbert County Hosp. Bd., 388 So. 2d 1207, holds "something the court said about tolling".'
        )
        self.assertEqual(rep.quotes[0].status, vs.BLOCKED)
        self.assertFalse(rep.ok)

    def test_quote_checked_against_local_source(self):
        (self.root / "policy.txt").write_text(
            "PART C - UNINSURED MOTORISTS COVERAGE. We will pay compensatory damages which an insured is legally "
            "entitled to recover from the owner or operator of an uninsured motor vehicle.", encoding="utf-8")
        rep, _ = self.run_gate(
            'The policy promises to "pay compensatory damages which an insured is legally entitled to recover" '
            "[src: ../policy.txt]."
        )
        self.assertTrue(rep.ok, vs.render(rep))

    def test_canary_forbid_is_literal_dollar_figure(self):
        draft = self.root / "drafts" / "letter.md"
        draft.write_text("We are prepared to settle at $20,000.", encoding="utf-8")
        rep = vs.verify(draft, FakeFetcher(self.root), self.adir, forbid=["$20,000"], jurisdictions=["AL"])
        self.assertFalse(rep.ok)

    def test_forbid_read_from_project_yaml(self):
        (self.root / "project.yaml").write_text("legal:\n  forbid: ['$20,000']\n", encoding="utf-8")
        forbid, errors = vs.project_forbid(self.root)
        self.assertEqual((forbid, errors), (["$20,000"], []))

    def test_nothing_cited_passes(self):
        rep, _ = self.run_gate("Please call me to discuss.")
        self.assertTrue(rep.ok)

    # review canaries ----------------------------------------------------------
    def test_canary_wrapped_quote_is_checked(self):
        rep, _ = self.run_gate('Ala. Code § 26-1-1 says "at the arrival at the age of 18 years,\nshall be relieved of '
                               'his or her disabilities".')
        self.assertEqual([q.status for q in rep.quotes], [vs.FAIL])

    def test_canary_blockquote_is_checked(self):
        rep, _ = self.run_gate("Ala. Code § 26-1-1 provides:\n\n> Any person in this state at the age of 18 years "
                               "shall be relieved of all disabilities.")
        self.assertFalse(rep.ok)
        rep, _ = self.run_gate("Ala. Code § 26-1-1 provides:\n\n> Any person in this state, at the arrival at the "
                               "age of 19 years, shall be relieved of his or her disabilities of minority.")
        self.assertTrue(rep.ok, vs.render(rep))

    def test_canary_blockquote_inside_mixed_paragraph_is_checked(self):
        rep, _ = self.run_gate("Ala. Code § 26-1-1 provides:\n> Any person in this state at the age of 18 years "
                               "shall be relieved of all disabilities.")
        self.assertFalse(rep.ok)

    def test_canary_single_curly_quote_is_checked(self):
        rep, _ = self.run_gate("Ala. Code § 26-1-1 says ‘any person at the age of 18 is an adult for all purposes’.")
        self.assertEqual([q.status for q in rep.quotes], [vs.FAIL])

    def test_canary_long_bracket_fails(self):
        rep, _ = self.run_gate('Ala. Code § 26-1-1: "[Insurers must pay punitive damages on every delayed claim] of '
                               'his or her disabilities of minority".')
        self.assertEqual(rep.quotes[0].status, vs.FAIL)

    def test_canary_partial_word_and_stitched_fragments_fail(self):
        self.assertFalse(vs.quote_found("at the arrival at the age of 1", AGE_OF_MAJORITY))
        self.assertFalse(vs.quote_found("Any person ... shall ... have ... legal ... rights", AGE_OF_MAJORITY))

    def test_us_style_period_inside_quote_passes(self):
        rep, _ = self.run_gate('Ala. Code § 26-1-1 says a person "shall be relieved of his or her disabilities of minority."')
        self.assertTrue(rep.ok, vs.render(rep))

    def test_canary_src_cannot_be_the_draft_or_outside_repo(self):
        rep, _ = self.run_gate('The statute says "a person is an adult at age sixteen in Alabama" [src: letter.md].')
        self.assertFalse(rep.ok)
        rep, _ = self.run_gate('Per the file "root:x:0:0:root:/root:/bin/bash" [src: /etc/passwd].')
        self.assertFalse(rep.ok)
        rep, _ = self.run_gate("See [src: .] for the details.")
        self.assertFalse(rep.ok)

    def test_canary_unrecognized_citation_forms_fail(self):
        for text in ["Under Code of Alabama Section 6-2-99, the limitations period is ten years.",
                     "Smith v. Jones, 123 S.E.2d 456 (Ga. 1990), holds the opposite.",
                     "Smith v. Jones, 2019 WL 1234567 (Ala. 2019), is directly on point.",
                     "Smith v. Jones, 250 Ala. 123 (1948).",
                     "Fla. Stat. § 95.11 gives four years.",
                     "Under 42 U.S.C. 99999 the insurer is liable.",
                     "Under 45 CFR 999.999 the insurer is liable.",
                     "Ala. R. Civ. P. 6(a) governs the computation."]:
            rep, _ = self.run_gate(text)
            self.assertFalse(rep.ok, text)

    def test_canary_georgia_spelled_out_is_not_alabama(self):
        rep, f = self.run_gate("Georgia Code § 26-1-1 sets majority at 19.")
        self.assertFalse(rep.ok)
        self.assertEqual(f.calls, [])

    def test_canary_section_range_checks_both_ends(self):
        rep, _ = self.run_gate("Ala. Code §§ 26-1-1 to 26-99-99 apply.")
        self.assertFalse(rep.ok)

    def test_canary_case_name_must_match_both_parties(self):
        for text in ["See Abernathy v. Smith, 388 So. 2d 1207 (Ala. 1980).",
                     "See State v. County, 388 So. 2d 1207 (Ala. 1980).",
                     "See Bert v. Jones, 388 So. 2d 1207 (Ala. 1980)."]:
            rep, _ = self.run_gate(text)
            self.assertFalse(rep.ok, text)

    def test_dates_and_addresses_are_not_citations(self):
        rep, _ = self.run_gate("On 22 Apr. 2026 the car was hit near 123 Main St. Claim No. 0512345.")
        self.assertTrue(rep.ok, vs.render(rep))

    def test_hyphenated_treasury_regulation_is_one_citation(self):
        auths, _ = vs.extract("Under 26 C.F.R. § 1.152-4(d)(1) the custodial parent is determined by nights.")
        self.assertEqual([(a.kind, a.key) for a in auths], [("cfr", "26/1.152-4")])

    def test_quote_matcher(self):
        self.assertTrue(vs.quote_found("[T]he same legal rights", AGE_OF_MAJORITY))
        self.assertFalse(vs.quote_found("the same legal duties", AGE_OF_MAJORITY))


    # adapters and jurisdictions --------------------------------------------------
    def test_no_state_adapter_fails_a_bare_state_section(self):
        rep, f = self.run_gate("§ 26-1-1 applies.", jurisdictions=())
        self.assertFalse(rep.ok)
        self.assertEqual(rep.authorities[0].kind, "unrecognized")
        self.assertIn("no state adapter", rep.authorities[0].reason)
        self.assertEqual(f.calls, [])

    def test_regional_reporter_needs_its_state_adapter(self):
        text = "See Abernathy v. Colbert County Hosp. Bd., 388 So. 2d 1207 (Ala. 1980)."
        rep, _ = self.run_gate(text, jurisdictions=())
        self.assertFalse(rep.ok)
        rep, _ = self.run_gate(text, jurisdictions=("AL",))
        self.assertTrue(rep.ok, vs.render(rep))

    def test_federal_is_always_on(self):
        rep, f = self.run_gate(
            'Under 26 C.F.R. § 1.152-4, a taxpayer "may claim a dependency deduction for a child".', jurisdictions=())
        self.assertTrue(rep.ok, vs.render(rep))
        self.assertTrue(rep.authorities[0].url.startswith("https://www.ecfr.gov/current/title-26/"))
        self.assertEqual([c[0] for c in f.calls], ["ecfr"])

    def test_ecfr_outage_falls_back_to_lii(self):
        rep, f = self.run_gate('26 C.F.R. § 1.152-4 says "only if the child is the qualifying child".',
                               ecfr_down=True)
        self.assertTrue(rep.ok, vs.render(rep))
        self.assertEqual([c[0] for c in f.calls], ["ecfr", "lii"])

    def test_canary_nonexistent_cfr_section_fails_without_fallback(self):
        rep, f = self.run_gate("26 C.F.R. § 1.999-99 requires it.")
        self.assertEqual(rep.authorities[0].status, vs.FAIL)
        self.assertEqual([c[0] for c in f.calls], ["ecfr"])

    def test_usc_quote_passes(self):
        rep, _ = self.run_gate('15 U.S.C. § 1681i requires the agency to "conduct a reasonable reinvestigation".')
        self.assertTrue(rep.ok, vs.render(rep))

    def test_irs_publication_quote_passes(self):
        rep, _ = self.run_gate('IRS Pub. 969 (2025) defines an HSA as "a tax-exempt trust or custodial account '
                               'that you set up with a qualified HSA trustee".')
        self.assertTrue(rep.ok, vs.render(rep))
        self.assertEqual(rep.authorities[0].kind, "irs-pub")

    def test_canary_stale_irs_edition_fails(self):
        rep, _ = self.run_gate("Publication 969 (2024) covers HSAs.")
        self.assertFalse(rep.ok)
        self.assertIn("2025 edition", rep.authorities[0].reason)

    def test_canary_nonexistent_irs_publication_fails(self):
        rep, _ = self.run_gate("IRS Pub. 9999 covers it.")
        self.assertEqual(rep.authorities[0].status, vs.FAIL)

    def test_canary_another_state_named_before_section(self):
        for text in ["Tenn. Code Ann. § 39-13-101 defines assault.", "N.Y. Gen. Oblig. Law § 5-1-101 applies.",
                     "Texas § 26-1-1 is different."]:
            rep, f = self.run_gate(text)
            self.assertFalse(rep.ok, text)
            self.assertEqual(rep.authorities[0].kind, "other", text)
            self.assertEqual(f.calls, [], text)

    def test_jurisdiction_read_from_project_yaml(self):
        (self.root / "project.yaml").write_text("advisory:\n  jurisdiction: [AL, federal, NY]\n", encoding="utf-8")
        codes = vs.project_jurisdictions(self.root)
        self.assertEqual(codes, ["AL", "federal", "NY"])
        adapters, notes = vs.build_adapters(codes)
        self.assertEqual([a.name for a in adapters if a.state], ["AL"])
        self.assertEqual(len(notes), 1)
        self.assertIn("NY", notes[0])

    def test_state_names_normalize_to_codes(self):
        self.assertEqual(vs.normalize_codes(["Alabama", "al", "federal, AL"]), ["AL", "FEDERAL"])

    def test_list_adapters_marks_alabama_as_example(self):
        out = vs.list_adapters()
        self.assertIn("AL", out)
        self.assertIn("example", out)
        for name in ("federal", "irs", "cases", "local"):
            self.assertIn(name, out)


class AdapterInterfaceTest(unittest.TestCase):
    """A test double for the adapter interface: a fictional state, 'ZZ', with an in-memory code."""

    CODE = {"12.34": "Section 12.34. Notice of claim. A claimant shall give written notice of the claim within "
                     "ninety days after the loss, stating the time, place and cause of the loss."}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "drafts").mkdir()
        code = self.CODE

        class FictionalState(vs.Adapter):
            name = "ZZ"
            label = "Fictional state code (test double)"
            state = True
            kinds = ("zz-code",)
            cite = __import__("re").compile(r"Z\.S\.\s*§\s*(\d+\.\d+)")

            def extract(self, par):
                return [vs.Hit("zz-code", m.group(1), f"Z.S. § {m.group(1)}", m.span()) for m in self.cite.finditer(par)]

            def fetch(self, kind, key, fetcher):
                if key not in code:
                    raise vs.NotFound(f"no section {key}")
                return vs.Fetched(f"https://code.example/zz/{key}", code[key])

        vs.register(FictionalState)

    def tearDown(self):
        vs.STATE_ADAPTERS.pop("ZZ", None)
        vs.STATE_ADAPTERS.pop("ZY", None)
        self.tmp.cleanup()

    def gate(self, text, codes):
        draft = self.root / "drafts" / "d.md"
        draft.write_text(text, encoding="utf-8")
        return vs.verify(draft, vs.Fetcher(base_dir=draft.parent), self.root / "authorities", jurisdictions=codes)

    def test_plugin_adapter_verifies_when_selected(self):
        rep = self.gate('Z.S. § 12.34 requires notice "within ninety days after the loss".', ["ZZ"])
        self.assertTrue(rep.ok, vs.render(rep))
        self.assertTrue((self.root / "authorities" / "zz-code-12-34.txt").exists())

    def test_plugin_adapter_is_off_unless_selected(self):
        rep = self.gate('Z.S. § 12.34 requires notice "within ninety days after the loss".', ["AL"])
        self.assertFalse(rep.ok)

    def test_canary_plugin_missing_section_fails(self):
        rep = self.gate("Z.S. § 99.99 requires notice.", ["ZZ"])
        self.assertEqual(rep.authorities[0].status, vs.FAIL)

    def test_adapter_file_is_loaded_by_main(self):
        plugin = self.root / "zy_state.py"
        plugin.write_text(
            "import verify_sources as vs\n\n"
            "@vs.register\n"
            "class ZY(vs.Adapter):\n"
            "    name = 'ZY'\n    label = 'plug-in test double'\n    state = True\n    kinds = ('zy-code',)\n"
            "    def extract(self, par):\n"
            "        import re\n"
            "        return [vs.Hit('zy-code', m.group(1), m.group(0), m.span())\n"
            "                for m in re.finditer(r'ZY § (\\d+)', par)]\n"
            "    def fetch(self, kind, key, fetcher):\n"
            "        return vs.Fetched('https://code.example/zy/' + key,\n"
            "                          'Section 7. Every request for records shall be answered in writing promptly.')\n",
            encoding="utf-8")
        draft = self.root / "drafts" / "d.md"
        draft.write_text('ZY § 7 says requests "shall be answered in writing promptly".', encoding="utf-8")
        code = vs.main([str(draft), "--adapter-file", str(plugin), "--jurisdiction", "ZY",
                        "--authorities", str(self.root / "authorities")])
        self.assertEqual(code, 0)

if __name__ == "__main__":
    unittest.main()
