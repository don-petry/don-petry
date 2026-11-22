# State notes — Alabama (EXAMPLE)

**This file is an example of the shape, for one state.** It lists where Alabama's tax rules live and what the
team's engines already model for it. It holds leads, not law: a rule reaches a draft only as a dated, quoted
`reference/rules-<year>.md` entry fetched from the official source. For another state, copy this file to
`reference/jurisdictions/<postal code>.md`, fill it from that state's official sources, and set config
`jurisdiction`.

## Sources

| Authority | Citation form | Official source | Gate adapter |
| :--- | :--- | :--- | :--- |
| Code of Alabama, Title 40 (revenue and taxation) | `Ala. Code § 40-18-…` | ALISON, the Legislature's API | `AL` (built in, the example state adapter) |
| Alabama Department of Revenue (ADOR) guidance | `[rule:<key>]` entry quoting the page | `revenue.alabama.gov` — Form 40 booklet and instructions, FAQs, notices | none yet — MANUAL (T-VERIFY-TAX-ADAPTERS) |
| CollegeCounts (Alabama's 529 plan) | `[rule:<key>]` entry quoting the plan document | the plan's program disclosure | none — plan rules, not tax law |

## What the engines already model for Alabama

| Engine | Alabama piece | Rules entries |
| :--- | :--- | :--- |
| `scripts/compute.py` | Alabama income tax (`STATE_OUTPUTS["AL"]`), Alabama itemized deductions and the deduction for federal income tax, the CollegeCounts 529 deduction (`contrib_529`), an Alabama-only AGI offset (`tu.al_agi_offset`) | `al-income-tax-top-rate`, `al-529-deduction` |
| `scripts/compute.py` | Alabama Accountability Act scholarship-granting-organization (SGO) credit (`sgo.al_gift`), solved with the federal safe harbor (`sgo.federal`), and no Alabama deduction for the credited gift | `al-aaa-credit-individual-limits`, `al-aaa-carryforward`, `al-aaa-no-restricted-gifts`, `al-aaa-claimant-not-transferable`, `al-aaa-no-al-deduction`, `al-aaa-bona-fide-gift`, `al-aaa-reservation`, `sgo-sfk-personal-account`, `fed-164-3j-safe-harbor`, `fed-170a-state-credit-reduction` |
| `scripts/compute.py` | Whether Alabama opts in to the federal §25F SGO credit | `al-25f-opt-in`, `fed-25f-credit`, `fed-25f-prop-regs` |
| `scripts/equity_scenarios.py` | `state_conforms_to_qsbs` must be stated and cited | `al-qsbs-conformity` |
| `tax-wealth-returns` `extract_return.py` | Alabama Form 40 and its Schedule A (`--kind al`), identities and line maps | — |

To add a state to `compute.py`, map its PolicyEngine-US output variables in `STATE_OUTPUTS` and
`STATE_ITEMIZED_OUTPUTS`; state credits like the SGO credit need their own function and tests, each constant
quoted in the rules file.

## Conformity to watch

Alabama decides separately whether it follows a federal change. Before applying any federal provision to the
Alabama return — 529 K-12 withdrawals, the §1202 exclusion, dependent definitions, the 2025 reconciliation
act's changes — find the ADOR or Code of Alabama source for Alabama's own treatment (`reference/verification.md`
§3, stale-law check).

## Red-team seat

`ador-examiner` — reads Alabama deductions, conformity questions, CollegeCounts and the SGO credit from the
Department of Revenue's side.
