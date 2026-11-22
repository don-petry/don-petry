# Health rules — dated entries drafts cite as `[rule:<key>]`

Each entry: the rule in one line, the exact quote, the URL, the fetch date and who fetched it. A draft may
cite only an entry here or in the configured state's `jurisdictions/<code>.md` (config `jurisdiction.notes`).
These are **federal** rules and IRS figures; state rules (minor consent, a parent's access to a minor's records,
age of majority) live in the state file — `jurisdictions/AL.md` is the labeled example. **Status** is `verbatim` (the quote was compared with the fetched page text in a
session) or `research` (quoted by the 2026-11-08 research pass from a page it fetched — `source-verifier`
re-fetches before a draft relying on it leaves `drafts/`). Anything else is not a rule yet.

Refresh every entry each November (new IRS limits) and whenever a cited page changes.

## HSA and FSA

| Key | Rule | Quote | Source | Fetched | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `hsa-whose-expenses` | HSA money may pay the account holder's, spouse's and dependents' expenses | "Qualified medical expenses include those incurred by the following persons. You and your spouse. All dependents you claim on your tax return. Any person you could have claimed as a dependent on your return except that:" | [IRS Pub 969 (2025)](https://www.irs.gov/publications/p969), Distributions From an HSA | 2026-11-08 | verbatim |
| `hsa-divorced-parents` | A child of parents living apart is the dependent of both for HSA purposes | "For this purpose, a child of parents that are divorced, separated, or living apart for the last 6 months of the calendar year is treated as the dependent of both parents whether or not the custodial parent releases the claim to the child’s exemption." | Pub 969, same section (Tip) | 2026-11-08 | verbatim |
| `hsa-no-annual-withdrawal` | No yearly deadline to take money out | "You don’t have to make withdrawals from your HSA each year." | Pub 969, Distributions From an HSA | 2026-11-08 | verbatim |
| `hsa-incurred-after` | Only expenses incurred after the HSA was established qualify | "For HSA purposes, expenses incurred before you establish your HSA aren’t qualified medical expenses." | Pub 969, Qualified medical expenses | 2026-11-08 | verbatim |
| `hsa-records` | Keep records proving each distribution; don’t file them | "You must keep records sufficient to show that: The distributions were exclusively to pay or reimburse qualified medical expenses, The qualified medical expenses hadn’t been previously paid or reimbursed from another source, and The medical expenses hadn’t been taken as an itemized deduction in any year. Don’t send these records with your tax return." | Pub 969, Recordkeeping | 2026-11-08 | verbatim |
| `hsa-nonqualified` | A non-qualified distribution is taxed and may carry 20% | "the amount you withdraw will be subject to income tax and may be subject to an additional 20% tax." | Pub 969, Distributions From an HSA | 2026-11-08 | verbatim |
| `lpfsa-compatible` | A limited-purpose FSA does not break HSA eligibility | "an employee can make contributions to an HSA while covered under an HDHP and one or more of the following arrangements. Limited-purpose health FSA or HRA." | Pub 969, Other employee health plans | 2026-11-08 | verbatim |
| `hsa-limit-2026` | 2026 HSA limits: $4,400 self-only, $8,750 family | "For 2026, if you have self-only HDHP coverage, you can contribute up to $4,400. If you have family HDHP coverage, you can contribute up to $8,750." | Pub 969, Limit on Contributions (Tip) | 2026-11-08 | verbatim |
| `hsa-limit-2027` | 2027 family HSA limit $9,000 | "is $9,000" (family coverage, 2027) | [Rev. Proc. 2026-24](https://www.irs.gov/pub/irs-drop/rp-26-24.pdf) | 2026-11-08 | research |
| `fsa-limits-2027` | 2027 health FSA limit $3,500; carryover cap $700 | "the maximum carryover amount is $700" | IR-2026-133 (2026-11-05) / Rev. Proc. 2026-35, irs.gov newsroom | 2026-11-08 | research |
| `fsa-substantiation` | Every FSA card charge needs third-party substantiation unless auto-substantiated; a plan that skips it is not a cafeteria plan | "is not a cafeteria plan within the meaning of section 125" | [CCA 202317020](https://www.irs.gov/pub/irs-wd/202317020.pdf) (citing Prop. Reg. § 1.125-6) | 2026-11-08 | research |
| `records-3yr` | Keep tax records 3 years by default | "Keep records for 3 years if situations (4), (5), and (6) below do not apply to you." | [IRS — How long should I keep records](https://www.irs.gov/businesses/small-businesses-self-employed/how-long-should-i-keep-records) | 2026-11-08 | research |

## Claims and appeals

| Key | Rule | Quote | Source | Fetched | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `erisa-appeal-180` | Group health plans give at least 180 days to appeal a denial | "at least 180 days following receipt of a notification of an adverse benefit determination" | [29 CFR 2560.503-1(h)(3)(i)](https://www.ecfr.gov/current/title-29/section-2560.503-1) | 2026-11-08 | research |
| `erisa-claim-file` | The claimant gets the claim file free on request | "upon request and free of charge, reasonable access to, and copies of, all documents" | 29 CFR 2560.503-1(h)(2)(iii) | 2026-11-08 | research |
| `external-review-4mo` | Federal external review must be requested within four months of the final denial | "within four months after the date of receipt of a notice" | [29 CFR 2590.715-2719](https://www.ecfr.gov/current/title-29/section-2590.715-2719) | 2026-11-08 | research — whether a group plan is self-funded (federal process) or insured (state process) is a plan fact to confirm from the SPD |
| `dental-excepted` | Stand-alone individual dental is an excepted benefit — no ACA external review | "The requirements of this part and part 147 … do not apply to any individual coverage" | [45 CFR 148.220](https://www.ecfr.gov/current/title-45/section-148.220) | 2026-11-08 | research |
| `medicaid-last` | Medicaid pays after every other payer | "all other available third party resources must meet their legal obligation to pay claims before the Medicaid program pays" | [Medicaid.gov — COB and TPL](https://www.medicaid.gov/medicaid/eligibility-policy/coordination-of-benefits-third-party-liability/index.html); [42 CFR 433.139](https://www.ecfr.gov/current/title-42/section-433.139) | 2026-11-08 | research |

## Bills

| Key | Rule | Quote | Source | Fetched | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `nsa-balance-billing` | Emergency care and non-network clinicians at in-network facilities may not bill above in-network cost-sharing | "must not bill, and must not hold liable" | [45 CFR 149.410](https://www.ecfr.gov/current/title-45/section-149.410) | 2026-11-08 | research |
| `nsa-gfe-400` | Self-pay patients can dispute a bill $400+ over the Good Faith Estimate | "at least $400 more than the total amount of expected charges listed on the good faith estimate" | [45 CFR 149.620](https://www.ecfr.gov/current/title-45/section-149.620) | 2026-11-08 | research |
| `nsa-complaint` | No Surprises complaints by phone or online | "Submit a complaint over the phone:" (the helpline number follows on the page; read it there) | [CMS — submit a complaint](https://www.cms.gov/initiatives/your-patient-rights/medical-bill-rights/get-help/submit-complaint) | 2026-11-08 | research |
| `501r-120-240` | A nonprofit hospital takes no collection action for 120 days after the first post-discharge bill | "for at least 120 days from the date the hospital facility provides the first post-discharge billing statement" | [26 CFR 1.501(r)-6](https://www.ecfr.gov/current/title-26/section-1.501(r)-6) | 2026-11-08 | research |
| `medical-debt-credit` | The CFPB medical-debt rule was vacated | "the U.S. District Court of the Eastern District of Texas vacated the Consumer Financial Protection Bureau's rule" | [CFPB](https://www.consumerfinance.gov/rules-policy/final-rules/prohibition-on-creditors-and-consumer-reporting-agencies-concerning-medical-information-regulation-v/) | 2026-11-08 | research |
| `tic-estimator` | Group plans must offer an online cost estimator for all covered items | "with respect to all covered items and services, for plan years beginning on or after January 1, 2024" | [29 CFR 2590.715-2715A2](https://www.ecfr.gov/current/title-29/section-2590.715-2715A2) | 2026-11-08 | research |

## Records access

| Key | Rule | Quote | Source | Fetched | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `hipaa-parent-state-law` | A parent's access to a minor's information follows state law | "If, and to the extent, permitted or required by an applicable provision of State or other law" | [45 CFR 164.502(g)(3)](https://www.ecfr.gov/current/title-45/section-164.502) | 2026-11-08 | research |
| `hipaa-auth-elements` | A valid authorization needs an expiry (among other elements) | "An expiration date or an expiration event" | [45 CFR 164.508(c)](https://www.ecfr.gov/current/title-45/section-164.508) | 2026-11-08 | research |

CFR links point to eCFR (`ecfr.gov`); Cornell LII (`law.cornell.edu/cfr`) is the fallback when eCFR is unreachable.
