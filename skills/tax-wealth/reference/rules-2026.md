# Tax-wealth rules — tax year 2026

The only place a draft may take a threshold, limit, rate, deadline or rule from. Cite an entry as
`[rule:<key>]` (not `[src:]`, which the verification script reads as a local file path). Format and stale-law check: `reference/verification.md` §3. Household-specific notes on how an entry
applies (a plan document, an income level) go in the team config's `rule_notes`, keyed by the entry's key.

Each entry is added the first time a draft needs it, from a **fetched primary source** — never from
memory or from the research notes. Figures in the research report are leads to look up, not entries.

## Entry format

```markdown
### <key>
- **Rule:** one sentence, in plain words.
- **Source:** <primary-source URL> (edition / as-of date)
- **Quote:** "exact text from the source"
- **Fetched:** YYYY-MM-DD · **Law as of:** YYYY-MM-DD · **Jurisdiction:** federal | <state code> (AL entries are the example state)
- **Status:** verified | unverified (reason)
```

## Entries

### std-deduction-2026-mfj
- **Rule:** The 2026 standard deduction for married couples filing jointly is $32,200. It is also the
  known answer for `compute.py --smoke`.
- **Source:** https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill (IRS newsroom)
- **Quote:** "For tax year 2026, the standard deduction increases to $32,200 for married couples filing jointly."
- **Fetched:** 2026-09-26 · **Law as of:** tax year 2026, as amended by the 2025 act · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted; no verification script yet)

### qsbs-applicable-percentage-2025
- **Rule:** For QSBS acquired after July 4, 2025, the share of the gain excluded under §1202 depends on how
  long the stock is held: 50% at 3 years, 75% at 4 years and 100% at 5 years or more. Less than 3 years
  excludes nothing.
- **Source:** https://www.law.cornell.edu/uscode/text/26/1202 (26 U.S.C. §1202(a)(1)(B), (a)(5), (b)(2), as amended by Pub. L. 119-21)
- **Quote:** "the applicable percentage of any gain from the sale or exchange of" … (a)(5) table: 3 years 50 percent · 4 years 75 percent · 5 years or more 100 percent; (b)(2): "held for at least 3 years"
- **Fetched:** 2026-10-10 · **Law as of:** 2026-10-10 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched; the fetch tool truncated quotes at 125 characters)

### qsbs-per-issuer-cap-2025
- **Rule:** The excluded gain from one issuer's stock acquired after July 4, 2025 is capped at the
  greater of $15,000,000 (less prior exclusions from that issuer) or 10 times the basis of the stock sold.
- **Source:** https://www.law.cornell.edu/uscode/text/26/1202 (26 U.S.C. §1202(b)(1), (b)(4))
- **Quote:** "if such stock was acquired by the taxpayer after the applicable date, $15,000,000, reduced by the sum of—"; "10 times the aggregate adjusted bases of qualified small business stock"
- **Fetched:** 2026-10-10 · **Law as of:** 2026-10-10 · **Jurisdiction:** federal
- **Status:** verified (MANUAL); the $15M is inflation-indexed after 2026 — re-check for later tax years

### qsbs-qualification-2025
- **Rule:** QSBS is stock acquired at original issue for money, property or services from a C corporation
  whose gross assets never exceeded $75,000,000 through issuance, in a qualified trade or business — which
  excludes services in fields including engineering, accounting, consulting and financial services, and any
  business whose principal asset is the reputation or skill of its employees. An option is not stock: the
  holding period starts at exercise (or at an early exercise with an 83(b) election).
- **Source:** https://www.law.cornell.edu/uscode/text/26/1202 (26 U.S.C. §1202(c)(1)(B)(ii), (d)(1), (e)(3)(A))
- **Quote:** "as compensation for services provided to such corporation"; "did not exceed $75,000,000,"; "involving the performance of services in the fields of health, law, engineering, architecture, accounting,"
- **Fetched:** 2026-10-10 · **Law as of:** 2026-10-10 · **Jurisdiction:** federal
- **Status:** verified (MANUAL) for the statute text; the option-to-stock holding-period point follows from
  the statute applying to "stock" and is the standard reading — not separately quoted

### qsbs-nonexcluded-rate
- **Rule:** The part of a QSBS gain that is not excluded ("section 1202 gain") is 28-percent rate gain,
  taxed at no more than 28%, and as net gain taken into account in taxable income it is also subject to the
  3.8% net investment income tax above the MAGI threshold — 31.8% combined where the 28% cap binds. The
  excluded part is in neither.
- **Source:** https://www.law.cornell.edu/uscode/text/26/1 (26 U.S.C. §1(h)(1)(F), (h)(4)(A), (h)(7)); https://www.law.cornell.edu/uscode/text/26/1411 (§1411(a)(1), (c)(1)(A)(iii))
- **Quote:** "28 percent of the amount of taxable income in excess of the sum of the amounts on which tax is determined"; "the term “section 1202 gain” means the excess of—"; "a tax equal to 3.8 percent of the lesser of"; "to the extent taken into account in computing taxable income"
- **Fetched:** 2026-10-10 · **Law as of:** 2026-10-10 · **Jurisdiction:** federal
- **Status:** verified (MANUAL); 0.318 is the sum of the two quoted rates at an income where the 28% cap
  binds (ordinary bracket above 28%); household application: config `rule_notes`

### al-qsbs-conformity
- **Rule:** Alabama does not follow the post-2025 §1202 QSBS exclusion: the gain is taxed in full on the
  Alabama return even when it is excluded federally.
- **Source:** https://www.revenue.alabama.gov/wp-content/uploads/2025/11/OBBBA-Executive-Summary_FinalwAppendixA_10.31.25.pdf (ADOR, "The One, Big, Beautiful Bill Act — Analysis and Tax Provisions", updated 2025-11-10, p. 20)
- **Quote:** "I.R.C. § 1202(a)(1) - Expansion of Qualified Small Business Stock Gain Exclusion … Effective Date: Stock Issued After July 4, 2025  Tied to Federal: No"
- **Fetched:** 2026-10-10 · **Law as of:** 2025-11-10 · **Jurisdiction:** AL
- **Status:** verified (MANUAL — text extracted from the ADOR PDF). Secondary sources agree (Alabama adds back
  the excluded gain). Stale-law check: a 2026 Alabama act could change this; confirm with a CPA before an exit.

### al-income-tax-top-rate
- **Rule:** Alabama taxes a married joint return's taxable income over $6,000 at 5%. With the gain excluded
  federally, federal tax does not rise, so Alabama's deduction for federal income tax does not offset it:
  a QSBS gain bears the full 5% in Alabama.
- **Source:** https://www.revenue.alabama.gov/faqs/what-is-alabamas-individual-income-tax-rate/ (ADOR FAQ, undated)
- **Quote:** "5% All taxable income over $6,000"
- **Fetched:** 2026-10-10 · **Law as of:** undated page; 2025 forms carry the same schedule · **Jurisdiction:** AL
- **Status:** verified (MANUAL); the federal-deduction point is a reading of how the deduction works, not quoted

### al-aaa-credit-individual-limits
- **Rule:** An individual or married couple filing jointly gets an Alabama Accountability Act credit equal to 100% of the contributions *the taxpayer made* to an SGO, up to 100% of liability and capped at $100,000 per individual or married couple.
- **Source:** https://www.revenue.alabama.gov/wp-content/uploads/2024/10/Act2023-418.pdf (Act 2023-418 / SB263 enrolled, amending Ala. Code §16-6D-9(a)(2), p. 21; scanned PDF)
- **Quote:** "in an amount equal to 100 percent of the total contributions the taxpayer made to a scholarship granting organization for educational scholarships during the taxable year for which the credit is claimed, up to 100 percent of the tax liability of the individual taxpayer, not to exceed one hundred thousand dollars ($100,000) per individual taxpayer or married couple"
- **Fetched:** 2026-10-15 · **Law as of:** Act 2023-418 · **Jurisdiction:** AL
- **Status:** verified (MANUAL). The current Code text was not fetched (Justia 403), so a 2024–2026 amendment is not ruled out.

### al-aaa-carryforward
- **Rule:** An unused Accountability Act credit carries forward up to three taxable years.
- **Source:** same Act, §16-6D-9(a)(4)
- **Quote:** "an individual taxpayer, or a married couple filing jointly may carry forward a tax credit earned under the tax credit scholarship program for up to three taxable years."
- **Fetched:** 2026-10-15 · **Law as of:** Act 2023-418 · **Jurisdiction:** AL
- **Status:** verified (MANUAL)

### al-aaa-no-restricted-gifts
- **Rule:** No credit is allowed for a contribution the donor restricts or conditions in any way.
- **Source:** same Act, §16-6D-9(a)(5)–(6)
- **Quote:** "No credit may be claimed for a contribution made to a scholarship granting organization if the contribution is restricted or conditioned in any way by the donor"
- **Fetched:** 2026-10-15 · **Law as of:** Act 2023-418 · **Jurisdiction:** AL
- **Status:** verified (MANUAL)

### al-aaa-claimant-not-transferable
- **Rule:** Apart from owners of pass-through entities, only the donating individual or corporation may claim the credit, and it cannot be assigned or transferred.
- **Source:** https://admincode.legislature.state.al.us/api/chapter/810-3-61 (Ala. Admin. Code r. 810-3-61-.02(2)(f), revised 2022-11-14)
- **Quote:** "credits may only be claimed by the donating individual or corporate entity and may not be assigned or transferred to any other taxpayer."
- **Fetched:** 2026-10-15 · **Law as of:** 2022-11-14 · **Jurisdiction:** AL
- **Status:** verified (MANUAL)

### al-aaa-no-al-deduction
- **Rule:** No Alabama deduction is allowed for a contribution that earns the credit, including a credit carried forward.
- **Source:** same, r. 810-3-61-.02(2)(e)
- **Quote:** "A donor may not claim an income tax deduction on the Alabama tax return for the same contribution for which a credit is allowed on the current year's tax return or for which a credit is carried forward to a future tax year."
- **Fetched:** 2026-10-15 · **Law as of:** 2022-11-14 · **Jurisdiction:** AL
- **Status:** verified (MANUAL)

### al-aaa-bona-fide-gift
- **Rule:** The credit is limited to bona fide gifts. The donor may receive nothing of value from the SGO and may place no restrictions on the gift.
- **Source:** same, r. 810-3-61-.02(1)(a), (2)(a)
- **Quote:** "Credits will be limited to scholarship donations which are bona fide gifts." / "The donor may not receive anything of value from the SGO in return for the gift or place any restrictions on the use of the donated funds."
- **Fetched:** 2026-10-15 · **Law as of:** 2022-11-14 · **Jurisdiction:** AL
- **Status:** verified (MANUAL)

### al-aaa-reservation
- **Rule:** The donor reserves the credit in My Alabama Taxes (Report a Donation to an SGO). The SGO must enter the donation, or no credit is allowed.
- **Source:** https://www.revenue.alabama.gov/individual-corporate/alabama-accountability-act/ ; r. 810-3-61-.04(8)–(9)
- **Quote:** "Then, the taxpayer will need to click on Report a Donation to an SGO (Scholarship Granting Organization)." / "No tax credits will be allowed to donors, if the SGO receiving the donation fails to enter the donation amounts into the system"
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-15 (page) · **Jurisdiction:** AL
- **Status:** verified (MANUAL)

### sgo-sfk-personal-account
- **Rule:** Scholarships for Kids tells individual donors that the check must come from their personal account (the SGO's own guidance, not law).
- **Source:** https://scholarshipsforkids.org/donor-guide/ (updated 2026-04-16)
- **Quote:** "Checks must be for the same amount as the donation amount entered on MAT and must be written from your personal account."
- **Fetched:** 2026-10-15 · **Law as of:** 2026-04-16 · **Jurisdiction:** AL
- **Status:** verified (MANUAL); secondary — evidence of practice, not authority

### fed-170a-state-credit-reduction
- **Rule:** The §170 charitable deduction is reduced by any state tax credit the taxpayer receives or expects to receive in consideration for the payment. A dollar-for-dollar credit leaves nothing to deduct.
- **Source:** https://www.ecfr.gov/current/title-26/section-1.170A-1 (Treas. Reg. §1.170A-1(h)(3)(i))
- **Quote:** "the amount of the taxpayer's charitable contribution deduction under section 170(a) is reduced by the amount of any state or local tax credit that the taxpayer receives or expects to receive in consideration for the taxpayer's payment or transfer."
- **Fetched:** 2026-10-15 · **Law as of:** eCFR current (verifier matched the govinfo 2025 annual edition, revised to 2025-04-01; eCFR blocked) — 2026 stale-law check open; payments after 2018-08-27 · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### fed-170a-15pct-exception
- **Rule:** No reduction applies when the state credits total 15% or less of the payment.
- **Source:** same, (h)(3)(vi)
- **Quote:** "the total amount of the state and local tax credits received or expected to be received by the taxpayer is 15 percent or less of the taxpayer's payment"
- **Fetched:** 2026-10-15 · **Law as of:** current · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### fed-170a-in-consideration-for
- **Rule:** "In consideration for" is tested when the payment is made, and covers a benefit expected from the donee "or any other party".
- **Source:** same, (h)(4)(i)
- **Quote:** "if, at the time the taxpayer makes the payment to such entity, the taxpayer receives or expects to receive goods or services from that entity or any other party in return."
- **Fetched:** 2026-10-15 · **Law as of:** current · **Jurisdiction:** federal
- **Status:** verified (MANUAL). No fetched source addresses a credit claimed on a later DAF grant.

### fed-164-3j-safe-harbor
- **Rule:** An itemizer may treat the disallowed part of a cash payment that earned a state tax credit as a payment of state tax, but only to the extent the credit is applied. It stays inside the SALT cap.
- **Source:** https://www.ecfr.gov/current/title-26/section-1.164-3 (Treas. Reg. §1.164-3(j)(1), (3), (4))
- **Quote:** "may treat as a payment of State or local tax for purposes of section 164 the portion of such payment for which a charitable contribution deduction under section 170 is disallowed under § 1.170A-1(h)(3)."
- **Fetched:** 2026-10-15 · **Law as of:** current (T.D. 9907); verifier matched the govinfo 2025 annual edition — 2026 stale-law check open · **Jurisdiction:** federal
- **Status:** verified (MANUAL); covers only "a payment of cash or cash equivalent"

### salt-cap-2026
- **Rule:** The 2026 SALT cap is $40,400 (half that for married filing separately).
- **Source:** https://www.law.cornell.edu/uscode/text/26/164 (26 U.S.C. §164(b)(6)(B), (b)(7)(A)(ii), as amended by Pub. L. 119-21 §70120)
- **Quote:** "in the case of any taxable year beginning in calendar year 2026, $40,400,"
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-15 · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### salt-phasedown-2026
- **Rule:** The cap falls by 30% of MAGI over $505,000 in 2026, but not below $10,000.
- **Source:** same, §164(b)(7)(B)
- **Quote:** "the applicable limitation amount shall be reduced by 30 percent of the excess (if any) of the taxpayer's modified adjusted gross income over the threshold amount"; "in the case of any taxable year beginning in calendar year 2026, $505,000"; "shall not result in the applicable limitation amount being less than $10,000."
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-15 · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### fed-4967-prohibited-benefit
- **Rule:** A donor or advisor who recommends a DAF grant that gives them a "more than incidental benefit", directly or indirectly, owes a tax of 125% of the benefit; a fund manager who knowingly agrees owes 10% (capped at $10,000).
- **Source:** https://www.law.cornell.edu/uscode/text/26/4967 (26 U.S.C. §4967(a))
- **Quote:** "receiving, directly or indirectly, a more than incidental benefit as a result of such distribution, a tax equal to 125 percent of such benefit."
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-15 · **Jurisdiction:** federal
- **Status:** verified (MANUAL). No fetched source says whether a state tax credit is such a benefit.

### fed-4966-daf-definition
- **Rule:** A DAF is owned and controlled by the sponsoring organization, not the donor.
- **Source:** https://www.law.cornell.edu/uscode/text/26/4966 (§4966(d)(2)(A))
- **Quote:** "which is owned and controlled by a sponsoring organization, and"
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-15 · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### irs-notice-2017-73
- **Rule:** IRS interim guidance treats a DAF grant that relieves the donor of a cost they would otherwise bear as a more-than-incidental benefit. It does not mention state tax credits — an analogy only.
- **Source:** https://www.irs.gov/pub/irs-drop/n-17-73.pdf
- **Quote:** "a distribution from a DAF pursuant to the advice of a Donor/Advisor that subsidizes the Donor/Advisor's attendance or participation in a charity-sponsored event confers on the Donor/Advisor a more than incidental benefit under § 4967."
- **Fetched:** 2026-10-15 · **Law as of:** 2017-12 (proposed approach) · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### fc-impermissible-grants
- **Rule:** Fidelity Charitable approves a grant only if it will not confer a more-than-incidental benefit on the account holder. It may require a grant to be returned, ask for an extra nondeductible contribution, or revoke recommending privileges. No rule names tax credits or SGOs.
- **Source:** https://www.fidelitycharitable.org/content/dam/fc-public/docs/programs/fidelity-charitable-program-guidelines.pdf (Program Guidelines, CGF-PC-04/24, pp. 10–11)
- **Quote:** "that the grant will not confer a more than incidental benefit on an Account Holder, Authorized Person, or other third party;"
- **Fetched:** 2026-10-15 · **Law as of:** 2026 edition · **Jurisdiction:** federal (sponsor policy)
- **Status:** verified (MANUAL). Remedies (same pp.): "requiring that the grant be returned … or that the Account Holder make an additional nondeductible contribution" and "may limit or revoke any or all recommendation privileges".

### fc-grants-own-assets
- **Rule:** Fidelity Charitable says that when it pays a grant it is granting its own assets, not the account holder's.
- **Source:** https://www.fidelitycharitable.org/giving-account-guide/tax-considerations.html
- **Quote:** "When Fidelity Charitable disburses grants to charities, Fidelity Charitable is granting its own assets. Account Holders who make grant recommendations are not eligible for additional charitable deductions for these grants."
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-15 · **Jurisdiction:** federal (sponsor policy)
- **Status:** verified (MANUAL)

### fed-25f-credit
- **Rule:** From 2027, a federal credit applies dollar-for-dollar to cash contributions to a listed SGO in a state that has opted in. It is capped at $1,700 and reduced by any state credit on the same contributions, and the contribution cannot also be deducted under §170.
- **Source:** https://www.law.cornell.edu/uscode/text/26/25F (§25F(a), (b), (e), (f); Pub. L. 119-21 §70411)
- **Quote:** "shall be reduced by the amount allowed as a credit on any State tax return of the taxpayer for qualified contributions made by the taxpayer during the taxable year."
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-15 · **Jurisdiction:** federal
- **Status:** verified (MANUAL). Effective for taxable years ending after December 31, 2026 (note to §25F). The cap for joint filers is unsettled: the statute says $1,700 "any taxpayer"; the proposed regulations treat spouses as separate.

### fed-25f-prop-regs
- **Rule:** Under the proposed regulations, a qualified contribution is cash "made by an individual" and designated for §25F when it is made. Spouses filing jointly are treated as separate taxpayers.
- **Source:** https://www.govinfo.gov/content/pkg/FR-2026-10-02/pdf/2026-20277.pdf (REG-117199-25, prop. §1.25F-1(a)(12), §1.25F-2(a)(2))
- **Quote:** "The term qualified contribution means a charitable contribution of cash made by an individual to an SGO to the extent that the donor designates to the recipient SGO, at the time of making the contribution, that the contribution is intended to be a qualified contribution for purposes of section 25F."
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10-02 (proposed; comments due 2026-12-01) · **Jurisdiction:** federal
- **Status:** verified (MANUAL); proposed, not final

### al-25f-opt-in
- **Rule:** Alabama opted in to the federal §25F program on 2026-01-16 (Executive Order 742), with ADOR as administrator.
- **Source:** https://www.revenue.alabama.gov/?p=69756 (ADOR, "The Education Freedom Tax Credit Program")
- **Quote:** "On January 16, 2026, Governor Kay Ivey signed Executive Order No. 742, naming the Alabama Department of Revenue (ALDOR) as the administering agency and formally opting Alabama into the program."
- **Fetched:** 2026-10-15 · **Law as of:** 2026-10 · **Jurisdiction:** AL
- **Status:** verified (MANUAL); the order itself was not fetched

### ira-limit-2026
- **Rule:** The 2026 IRA contribution limit is $7,500; the age-50 catch-up is $1,100.
- **Source:** https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500 (IRS newsroom)
- **Quote:** "The limit on annual contributions to an IRA is increased to $7,500 from $7,000." / "is increased to $1,100, up from $1,000 for 2025."
- **Fetched:** 2026-10-15 · **Law as of:** tax year 2026 · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### deferral-limit-401k-2026
- **Rule:** The 2026 401(k) elective deferral limit (pre-tax plus Roth) is $24,500; the age-50 catch-up is $8,000.
- **Source:** same IRS newsroom release
- **Quote:** "is increased to $24,500, up from $23,500 for 2025." / "is increased to $8,000, up from $7,500 for 2025."
- **Fetched:** 2026-10-15 · **Law as of:** tax year 2026 · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### roth-phaseout-2026-mfj
- **Rule:** For 2026, a married couple filing jointly cannot contribute to a Roth IRA directly once MAGI passes $252,000 (phase-out $242,000–$252,000).
- **Source:** same IRS newsroom release
- **Quote:** "the income phase-out range is increased to between $242,000 and $252,000."
- **Fetched:** 2026-10-15 · **Law as of:** tax year 2026 · **Jurisdiction:** federal
- **Status:** verified (MANUAL)

### f8606-line6-yearend-value
- **Rule:** The taxable share of a conversion depends on the total value of all your traditional IRAs (including SEP and SIMPLE IRAs) at December 31 of the conversion year; each spouse files a separate Form 8606.
- **Source:** https://www.irs.gov/instructions/i8606 (Instructions for Form 8606, 2025 edition)
- **Quote:** "Enter the total value of all your traditional IRAs as of December 31, 2025, plus any outstanding rollovers." / "If both you and your spouse are required to file 2025 Form 8606, file a separate 2025 Form 8606 for each of you."
- **Fetched:** 2026-10-15 · **Law as of:** tax year 2025 edition · **Jurisdiction:** federal
- **Status:** verified (MANUAL); stale-law check: 2025 edition — re-fetch the 2026 instructions when published

### dc-annual-additions-2026
- **Rule:** For 2026, total contributions to one person's defined-contribution plans with the same employer (employee pre-tax, Roth and after-tax, plus employer contributions) cannot exceed $72,000; plan compensation counts up to $360,000.
- **Source:** https://www.irs.gov/pub/irs-drop/n-25-67.pdf (Notice 2025-67)
- **Quote:** "section 415(c)(1)(A) is increased in 2026 from $70,000 to $72,000." / "The annual compensation limitation under sections 401(a)(17), 404(l), 408(k)(3)(C), and 408(k)(6)(D)(ii) is increased from $350,000 to $360,000."
- **Fetched:** 2026-10-15 · **Law as of:** tax year 2026 · **Jurisdiction:** federal
- **Status:** verified (MANUAL). How an employer's plan applies the limit across its plans is in the plan document; household application: config `rule_notes`

### fed-183-not-for-profit
- **Rule:** An individual's activity not engaged in for profit gets no deductions beyond §183(b), and the extra §183(b)(2) deductions are capped at the activity's gross income, so with no revenue there is nothing to deduct.
- **Source:** https://www.law.cornell.edu/uscode/text/26/183 (LII, current)
- **Quote:** "if such activity is not engaged in for profit, no deduction attributable to such activity shall be allowed under this chapter except as provided in this section" · "(2) a deduction equal to the amount of the deductions which would be allowable under this chapter for the taxable year only if such activity were engaged in for profit, but only to the extent that the gross income derived from such activity for the taxable year exceeds the deductions allowable by reason of paragraph (1)."
- **Fetched:** 2026-10-16 · **Law as of:** 2026-10-16 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-183-presumption
- **Rule:** An activity is presumed to be for profit if its gross income exceeds its deductions in 3 or more of 5 consecutive years.
- **Source:** https://www.law.cornell.edu/uscode/text/26/183 (LII, current), subsection (d)
- **Quote:** "If the gross income derived from an activity for 3 or more of the taxable years in the period of 5 consecutive taxable years which ends with the taxable year exceeds the deductions attributable to such activity (determined without regard to whether or not such activity is engaged in for profit), then, unless the Secretary establishes to the contrary, such activity shall be presumed for purposes of this chapter for such taxable year to be an activity engaged in for profit."
- **Fetched:** 2026-10-16 · **Law as of:** 2026-10-16 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### reg-1-183-2-profit-objective
- **Rule:** A reasonable expectation of profit is not required, but the facts must show the activity was entered into or continued with the objective of making a profit; objective facts outweigh stated intent, and start-up losses are not by themselves a sign of no profit objective.
- **Source:** https://www.ecfr.gov/current/title-26/chapter-I/subchapter-A/part-1/section-1.183-2 (eCFR, current)
- **Quote:** "Although a reasonable expectation of profit is not required, the facts and circumstances must indicate that the taxpayer entered into the activity, or continued the activity, with the objective of making a profit." · "greater weight is given to objective facts than to the taxpayer's mere statement of his intent." · "A series of losses during the initial or start-up stage of an activity may not necessarily be an indication that the activity is not engaged in for profit."
- **Fetched:** 2026-10-16 · **Law as of:** 2026-10-16 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-195-startup
- **Rule:** Start-up expenditures are not deductible except by election: up to $5,000 (reduced by the amount total start-up costs exceed $50,000) in the year the active trade or business begins, the rest over 180 months.
- **Source:** https://www.law.cornell.edu/uscode/text/26/195 (LII, current)
- **Quote:** "the taxpayer shall be allowed a deduction for the taxable year in which the active trade or business begins in an amount equal to the lesser of— (i) the amount of start-up expenditures with respect to the active trade or business, or (ii) $5,000, reduced (but not below zero) by the amount by which such start-up expenditures exceed $50,000, and (B) the remainder of such start-up expenditures shall be allowed as a deduction ratably over the 180-month period beginning with the month in which the active trade or business begins."
- **Fetched:** 2026-10-16 · **Law as of:** 2026-10-16 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-174a-domestic-rd
- **Rule:** Domestic research or experimental expenditures, which include software development, are deductible in the year paid or incurred, for amounts paid or incurred in tax years beginning after 2024. How this interacts with §195 for a business that has not yet begun is a preparer question: the same act amended §195.
- **Source:** https://www.law.cornell.edu/uscode/text/26/174A (LII, current; added by Pub. L. 119–21 §70302)
- **Quote:** "Notwithstanding section 263, there shall be allowed as a deduction any domestic research or experimental expenditures which are paid or incurred by the taxpayer during the taxable year." · "any amount paid or incurred in connection with the development of any software shall be treated as a research or experimental expenditure." · "shall apply to amounts paid or incurred in taxable years beginning after December 31, 2024."
- **Fetched:** 2026-10-16 · **Law as of:** 2026-10-16 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-6654-required-annual-payment
- **Rule:** No federal underpayment penalty if withholding and estimates cover the lesser of 90% of this year's tax or 100% of last year's. Last year's figure rises to 110% when last year's AGI exceeded $150,000.
- **Source:** https://www.law.cornell.edu/uscode/text/26/6654 (LII, current), subsection (d)(1)(B)–(C)
- **Quote:** "the term “ required annual payment ” means the lesser of— (i) 90 percent of the tax shown on the return for the taxable year (or, if no return is filed, 90 percent of the tax for such year), or (ii) 100 percent of the tax shown on the return of the individual for the preceding taxable year." · "If the adjusted gross income shown on the return of the individual for the preceding taxable year beginning in any calendar year exceeds $150,000, clause (ii) of subparagraph (B) shall be applied by substituting “110 percent” for “100 percent”."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-111-recovery
- **Rule:** A recovered amount deducted in a prior year, such as a state income-tax refund, is federal income only to the extent the deduction reduced federal tax.
- **Source:** https://www.law.cornell.edu/uscode/text/26/111 (LII, current), subsection (a)
- **Quote:** "Gross income does not include income attributable to the recovery during the taxable year of any amount deducted in any prior taxable year to the extent such amount did not reduce the amount of tax imposed by this chapter."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### al-529-deduction
- **Rule:** Alabama deducts CollegeCounts contributions up to $10,000 on a joint return only when both spouses contribute, and $5,000 for a single filer, so one contributing spouse counts for up to $5,000. Contributions must be made by December 31.
- **Source:** https://www.collegecounts529.com/tax-benefits/ (CollegeCounts, Alabama's 529 program; Ala. Code § 16-33C-16, which justia.com refused to serve, 403)
- **Quote:** "$10,000 for a married couple, filing jointly when both spouses contribute. $5,000 for single filers. Keep in mind the contribution deadline for the Alabama state income tax deduction is December 31 each year."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** AL
- **ADOR:** https://www.revenue.alabama.gov/faqs/what-is-the-alabama-state-income-tax-deduction-for-contributions-to-the-collegecounts-529-plan/ (fetched 2026-10-31): "Contributions to the CollegeCounts 529 Plan are deductible on a state of Alabama income tax return up to $5,000 per Alabama taxpayer or $10,000 for married Alabama taxpayers filing jointly if both contribute." On recapture (same FAQ page): "the amount withdrawn is added back to the contributing taxpayer’s return, plus a 10 percent penalty". The contributor's identity matters; neither page says how a contribution is attributed to a spouse.
- **Status:** verified (ADOR FAQ and program page; the statute text, Ala. Code § 16-33C-16, could not be fetched: justia and findlaw 403, the legislature's site renders by script). PolicyEngine caps the deduction at $10,000 per joint return without the both-spouses condition, so engine inputs carry the per-spouse limit by hand

### fed-6654g-withholding
- **Rule:** For the underpayment penalty, wage withholding counts as paid in equal parts on each installment date unless you show the actual dates. Extra withholding late in the year therefore covers the earlier quarters too, which a late estimated payment does not.
- **Source:** https://www.law.cornell.edu/uscode/text/26/6654 (LII, current), subsection (g)(1)
- **Quote:** "the amount of the credit allowed under section 31 for the taxable year shall be deemed a payment of estimated tax, and an equal part of such amount shall be deemed paid on each due date for such taxable year, unless the taxpayer establishes the dates on which all amounts were actually withheld"
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-408a-ordering
- **Rule:** Roth IRA distributions come first from regular contributions, then from conversions oldest first, and only then from earnings. The 10% early-withdrawal rule reaches a conversion within 5 years only to the extent the conversion was taxable.
- **Source:** https://www.law.cornell.edu/uscode/text/26/408A (LII, current), subsections (d)(3)(F) and (d)(4)(B)
- **Quote:** "Clause (i) shall apply only to the extent of the amount of the qualified rollover contribution includible in gross income under subparagraph (A)(i)." · "such distribution shall be treated as made— (i) from contributions to the extent that the amount of such distribution, when added to all previous distributions from the Roth IRA , does not exceed the aggregate contributions to the Roth IRA ; and (ii) from such contributions in the following order: (I) Contributions other than qualified rollover contributions to which paragraph (3) applies. (II) Qualified rollover contributions to which paragraph (3) applies on a first-in, first-out basis."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL). How an in-plan 401(k) Roth conversion is tracked after a later rollover to a Roth IRA is a preparer question

### fed-219f3-ira-deadline
- **Rule:** An IRA contribution for a year can be made up to that year's return due date, without extensions, and counts as made on the last day of that year.
- **Source:** https://www.law.cornell.edu/uscode/text/26/219 (LII, current), subsection (f)(3)
- **Quote:** "a taxpayer shall be deemed to have made a contribution to an individual retirement plan on the last day of the preceding taxable year if the contribution is made on account of such taxable year and is made not later than the time prescribed by law for filing the return for such taxable year (not including extensions thereof)."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-170-appreciated-property
- **Rule:** A gift of property is reduced only by gain that would not have been long-term. Long-term appreciated shares are deductible at market value, and the gain is never taxed. Such gifts to public charities, including a donor-advised fund's sponsor, are limited to 30% of the contribution base.
- **Source:** https://www.law.cornell.edu/uscode/text/26/170 (LII, current), subsections (e)(1)(A) and (b)(1)(C)(i)
- **Quote:** "The amount of any charitable contribution of property otherwise taken into account under this section shall be reduced by the sum of— (A) the amount of gain which would not have been long-term capital gain" · "the total amount of contributions of such property which may be taken into account under subsection (a) for any taxable year shall not exceed 30 percent of the taxpayer’s contribution base for such year."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fc-securities-delivery
- **Rule:** Shares from an outside broker go by DTC to Fidelity Charitable's account at National Financial Services, for the benefit of the named Giving Account, with a Contribution Form or Letter of Instruction (or the online "Fund Giving Account" flow) sent alongside; the shares go in kind, not sold.
- **Source:** https://www.fidelitycharitable.org/content/dam/fc-public/docs/forms/broker-dealer-instructions.pdf (Broker-Dealer Instructions) · https://www.fidelitycharitable.org/content/dam/fc-public/docs/forms/contribution-form-and-letter-of-instruction.pdf (form 1.851030.127)
- **Quote:** "Deliver all eligible securities per these instructions. Shares should be transferred in kind and are not to be liquidated. A Contribution Form must accompany all contributed securities." · "For credit to: National Financial Services LLC / For benefit of: Fidelity Charitable® Giving Account® [number] / DTC: 0226 / Account Number: Z97–000442" · "Contact the financial institution directly to obtain their required procedures and forms, and then complete and deliver with the following instructions: Deliver to: DTC 0226 Acct Z97000442 FBO: ACCT#"
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fc-securities-valuation
- **Rule:** Fidelity Charitable values contributed public shares at the average of the day's high and low on the day the shares are received, and that is the deduction figure.
- **Source:** https://www.fidelitycharitable.org/faqs/all/fair-market-value-and-proceeds.html
- **Quote:** "The FMV for publicly traded securities is determined by multiplying the number of shares contributed by the average of the high and low prices for the day on which the shares are received. It is the figure that is used for tax-deduction purposes."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fc-yearend-securities-2026
- **Rule:** For 2026 credit, shares from a firm other than Fidelity must reach Fidelity Charitable by 11:59 p.m. ET on December 31; the transfer typically takes two weeks.
- **Source:** https://www.fidelitycharitable.org/giving-account/what-you-can-donate/charitable-year-end-tax-deadlines.html ("2026 year-end contribution guidelines")
- **Quote:** "Processing times can vary, but typically will take two weeks. Please check with your financial firm. Assets must be received by 11:59 p.m. ET December 31."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fc-third-party-contributions
- **Rule:** A contributor who is not an Account Holder is a third party and gets the receipt in their own name; Account Holders cannot deduct a third party's gift. An Account Holder contributing marks "Account Holder" on the form, and the receipt goes to whoever makes the contribution.
- **Source:** https://www.fidelitycharitable.org/content/dam/fc-public/docs/programs/fidelity-charitable-program-guidelines.pdf (Program Guidelines © 2026) · contribution form 1.851030.127 §1
- **Quote:** "such notification is not a tax receipt, and under federal income tax rules, Account Holders generally are not entitled to claim a deduction for charitable contributions made by third parties." · "The information provided will be used to generate a tax receipt to the person or entity … making the irrevocable contribution."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### irs-gift-date-stock
- **Rule:** A gift of stock is made when it is delivered unconditionally; for shares moved by a broker acting as the donor's agent, the date is when the shares are transferred into the charity's name. FMV is the average of the high and low on that date.
- **Source:** https://www.irs.gov/publications/p561 (Pub 561, Rev. 12/2025) · https://www.irs.gov/publications/p526 (Pub 526, 2025)
- **Quote:** "Ordinarily, the date of a contribution is the date on which the property is delivered to the charity or the title transfer date" · "the FMV of each share or bond is the average price between the highest and lowest quoted selling prices on the valuation date." · "Usually, you make a contribution at the time of its unconditional delivery."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### irs-cwa-daf
- **Rule:** A gift of $250 or more needs a contemporaneous written acknowledgment, received by the earlier of filing or the due date, stating whether goods or services were given; for a DAF it must also say the sponsor has exclusive legal control.
- **Source:** https://www.irs.gov/publications/p526 (Pub 526, 2025)
- **Quote:** "You can claim a deduction for a contribution of $250 or more only if you have a contemporaneous written acknowledgment of your contribution from the qualified organization" · "You can't deduct a contribution to a donor-advised fund if: … You don't have a contemporaneous written acknowledgment from that sponsoring organization that it has exclusive legal control over the assets contributed."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### f8283-public-securities
- **Rule:** Form 8283 is required when noncash gifts exceed $500; publicly traded securities go in Section A at any value, so no qualified appraisal is needed even above $5,000.
- **Source:** https://www.irs.gov/instructions/i8283 (Instructions for Form 8283, Rev. 12/2025)
- **Quote:** "You must file one or more Forms 8283 if the amount of your deduction for each noncash contribution is more than $500." · "For donations of publicly traded securities in any amount, you should only use Section A." · "Items reportable in Section B require a written qualified appraisal by a qualified appraiser."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-170-capgain-carryover
- **Rule:** Capital-gain property given to a public charity is limited to 30% of AGI (less certain other gifts); any excess carries forward up to 5 years.
- **Source:** https://www.irs.gov/publications/p526 (Pub 526, 2025)
- **Quote:** "Your noncash contributions of capital gain property to 50% limit organizations is limited to 30% of your AGI minus all your contributions to 50% limit organizations that are subject to the 60% and 50% limits" · "you may be able to deduct the excess in each of the next 5 years until it is used up, but not beyond that time."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-1014-step-up
- **Rule:** Property inherited from a decedent takes a basis equal to its market value at death, so gain unrealized at death is never taxed to the heir.
- **Source:** https://www.law.cornell.edu/uscode/text/26/1014 (LII, current; last amended Pub. L. 114-41), subsection (a)(1)
- **Quote:** "the basis of property in the hands of a person acquiring the property from a decedent or to whom the property passed from a decedent shall, if not sold, exchanged, or otherwise disposed of before the decedent's death by such person, be— (1) the fair market value of the property at the date of the decedent's death,"
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-1091-wash-sale-loss
- **Rule:** The wash-sale rule disallows a loss when substantially identical stock is bought within 30 days before or after a sale at a loss; it does not touch a disposition at a gain.
- **Source:** https://www.irs.gov/publications/p550 (Pub 550, 2025), "Wash Sales"
- **Quote:** "You cannot deduct losses from sales or trades of stock or securities in a wash sale unless the loss was incurred in the ordinary course of your business as a dealer in stock or securities. A wash sale occurs when you sell or trade stock or securities at a loss and within 30 days before or after the sale you: Buy substantially identical stock or securities"
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-170-cash-60pct
- **Rule:** Cash gifts to public charities (including a DAF sponsor) are deductible up to 60% of AGI, against 30% for appreciated stock.
- **Source:** https://www.irs.gov/publications/p526 (Pub 526, 2025)
- **Quote:** "If you make cash contributions during the year to an organization described earlier under First category of qualified organizations (50% limit organizations) , your deduction for the cash contributions is 60% of your AGI."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### fed-170e-tpp-unrelated-use
- **Rule:** A gift of tangible personal property that the charity sells (an unrelated use) is reduced by the long-term gain, so the deduction is basis (or market value if lower). A DAF sponsor that sells on receipt cannot meet the related-use exception.
- **Source:** https://www.law.cornell.edu/uscode/text/26/170 (LII, current), (e)(1)(B)(i)(I) · https://www.law.cornell.edu/cfr/text/26/1.170A-4 (Treas. Reg. §1.170A-4(b)(3)(i))
- **Quote:** "(B) in the case of a charitable contribution— (i) of tangible personal property— (I) if the use by the donee is unrelated to the purpose or function constituting the basis for its exemption under section 501 … the amount of gain which would have been long-term capital gain if the property contributed had been sold by the taxpayer at its fair market value" · "if the painting is sold and the proceeds used by the organization for educational purposes, the use of the property is an unrelated use"
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** verified (MANUAL — fetched and quoted)

### iau-grantor-trust-gold
- **Rule:** IAU (iShares Gold Trust) is a grantor trust; holders are treated as owning a pro rata share of its gold bullion, and gain on sale is collectibles gain. Applied with fed-170e-tpp-unrelated-use, a gift of IAU to a DAF is most defensibly deducted at basis, not market value. That application rests on inference (no IRS authority directly on point; practitioner consensus agrees), so it is a CPA/EA question before any gift.
- **Source:** https://www.sec.gov/Archives/edgar/data/1278680/000143774926006055/iau20251231_10k.htm (IAU Form 10-K FY2025, filed 2026-02-27) · secondary: https://blog.pgcalc.com/gifts-of-silver-and-gold (PG Calc, 2025-12-15)
- **Quote:** "Shareholders will be treated, for United States federal income tax purposes, as if they directly owned a pro rata share of the underlying assets held in the Trust." · (secondary) "Regardless of whether the donor holds coins, bullion, or shares of an ETF, the asset is considered to be tangible personal property."
- **Fetched:** 2026-10-31 · **Law as of:** 2026-10-31 · **Jurisdiction:** federal
- **Status:** unverified (the look-through to §170(e) is inference; CPA/EA to confirm)

### fed-401a9-mdib-jsa-nonspouse
- **Rule:** A pension joint-and-survivor annuity naming a non-spouse beneficiary can pay the survivor only up to a percentage of the employee's payment. The percentage is set by the age gap: 100% at 10 years or less, falling to 52% at 44 or more. When payments start before the employee's applicable age, the gap is first reduced by the years until that age, which is 75 for anyone born in 1960 or later.
- **Source:** https://www.ecfr.gov/current/title-26/section-1.401(a)(9)-6 (paragraphs (b)(2)(iii) Table 1 and (k)(2), including the daughter example); https://www.ecfr.gov/current/title-26/section-1.401(a)(9)-2 (paragraph (b)(2)(vi))
- **Quote:** "The applicable percentage is based on the employee/beneficiary age difference, which is equal to the excess of the age of the employee over the age of the beneficiary based on their ages on their birthdays in the calendar year that includes the annuity starting date." · "The adjusted employee/beneficiary age difference is determined by first calculating the employee/beneficiary age difference under paragraph (b)(2)(iii) of this section and then reducing that age difference by the number of years by which the employee is younger than the applicable age on the employee's birthday in the calendar year that includes the annuity starting date." · "In the case of an employee born on or after January 1, 1960, the applicable age is age 75." · Table 1 rows used here: "10 years or less 100", "15 84", "20 73", "22 70", "25 66", "44 and greater 52".
- **Fetched:** 2026-11-20 · **Law as of:** 2026-11-20 · **Jurisdiction:** federal
- **Status:** verified (MANUAL). This is a federal ceiling only; which survivor forms and percentages an employer's plan actually offers is set by its plan document and SPD (household application: config `rule_notes`)
