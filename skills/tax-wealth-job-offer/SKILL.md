---
name: tax-wealth-job-offer
description: Analyze a job offer or job change for a household adult from the tax, wealth and asset-management
  side — cash vs. equity structures, stock options, ISO/NSO, early exercise and 83(b), QSBS, AMT, break-even
  exit values, liquidity and concentration risk, and the benefits lost by leaving the current employer
  (group umbrella and life insurance, disability, 401(k) match, HSA/FSA) — with every figure from the
  deterministic equity and offer scripts or a tax engine. Routes offer-letter and equity-plan terms to
  legal and an employment attorney, and the 83(b) filing to a CPA or EA. Not tax, legal or investment
  advice; never recommends accepting, signing, exercising or electing. Use for "job offer", "equity offer",
  "offer structures", "cash vs equity", "stock options", "83(b)", "QSBS", "should I take the equity",
  "compare offers", "what do we lose if I leave".
license: MIT
metadata:
  argument-hint: <opportunity notes folder> [review <existing brief> | analyze | questions]
---

# Tax-Wealth Job Offer

> **Not tax, legal or investment advice.** This workflow lays out the tax events, the scenario table and the
> wealth picture so the decision makers can decide and their CPA, EA or attorney can check. It prepares the
> hand-off; it does not replace them.

A tax & wealth workflow for a job offer or change. It is the household adults' own money, so the capacity is
`joint` (or `self`); the offer is a matter of its own, with a `project.yaml` beside the opportunity's notes.

**Config:** the team's `../tax-wealth/config/household.yaml` — `household.decision_makers`, `paths.project`,
`paths.opportunities`, `paths.insurance_notes`, `employment.benefits_lost_on_leaving`, `paths.pm`,
`watermarks`. Script paths below are relative to the repository root as `skills/<skill>/scripts/…`.

## Run

1. **Gate and escalations** — run the `tax-wealth` skill's Step 0. For an offer, also:
   - an offer letter, equity plan or grant agreement to sign → legal's contract review and, for employment
     terms (non-compete, IP assignment, termination), an employment attorney;
   - a signed grant with early exercise → the **83(b) window is a hard clock**: record it in the matter with
     its source, and put the filing with the CPA or EA before it opens.
2. **Matter state.** Create or open `<notes folder>/project.yaml` with `advisory:` (`party: joint`, capacity
   `joint`, `forum: presuit`) and `tax_wealth:` (`scope: household`, `related_projects` pointing to the
   household project and any insurance project). Validate it with the project script if config `paths.pm` is
   set.
3. **Read the documents.** A data-room PDF stamped with the viewer's name and a timestamp reads as gibberish;
   `python3 -I skills/tax-wealth-job-offer/scripts/dewatermark_pdf.py <in.pdf> <out.md> [--png-dir DIR]` keeps
   the horizontal text and drops lines matching config `watermarks` (needs `scripts/requirements.txt`).
4. **Modes.**

   | Mode | Does |
   | :--- | :--- |
   | `review <brief>` | Checks an existing brief: every figure and rule it relies on gets a status (engine-backed, sourced, or unverified), and every missing perspective is listed. Writes `drafts/review-<date>.md` |
   | `questions` | The questions for the company, for the CPA or EA, and for the attorney — from `agents/tax-wealth-equity-analyst.md` method steps 1–3 |
   | `analyze` | The full analysis: dispatch `tax-wealth-equity-analyst` (or read it inline) with `{matter_path, documents, household_project, rules_ref}` |

5. **Engines.** `skills/tax-wealth/scripts/equity_scenarios.py` (equity) and
   `skills/tax-wealth/scripts/offer_cash.py` (salaried, pre-tax) need no install. The household's marginal and
   AMT rates need a PolicyEngine run (`skills/tax-wealth/scripts/compute.py`) — fire T-POLICYENGINE as a
   question to the user if the session has none. Without it, the scenario table is not produced; the
   questions and tax-event map still are.
6. **Verify and red-team** the draft: `source-verifier` (`domain: tax-wealth`), then `red-team` from
   `skeptical-cpa` (the plan), `irs-examiner` (QSBS, 83(b) and ISO positions) and `opposing-party` (the
   company's side of the terms).
7. **Present** the decision frame, not a recommendation to accept, sign, exercise or elect. The decision
   makers decide.
8. **Commit** after the team config's `commit_checks`, per its `commit_rule`.

## What this workflow always covers

- **Tax liability:** ordinary income on cash; the tax event map for the equity; AMT exposure; 83(b); QSBS
  federal **and state** treatment (each state decides its own conformity — the Alabama example is in
  `skills/tax-wealth/reference/jurisdictions/AL.md`); the effect of the company's liquidity path on all of it.
- **Wealth:** after-tax value by scenario and the break-even exit value; cash to exercise; concentration in one
  illiquid company; emergency-fund cover.
- **Asset management and protection:** benefits that end with the current job and their replacement cost —
  config `employment.benefits_lost_on_leaving` lists the household's, so the insurance project gets an action
  before any start date; retirement plan rollover (T-OWL); HSA/FSA run-out; health coverage for the household.
