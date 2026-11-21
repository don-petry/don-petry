# Playbook — insurance claim or dispute

For first-party and UM/UIM claims, liability claims made by a household member, and disputes with an insurer
(valuation, denial, loss history). A live matter, if the household has one, is named in config
`matters.insurance-claim`. Claims made **against** a household member are not this playbook: tender them to the
carrier and escalate (SKILL.md §Escalation).

Everything below marked **(verify)** is a lead for research, not a statement of law. It reaches a draft only
after the gate script passes it. Statutes and periods differ by state: take them from the configured
jurisdiction's notes (`reference/jurisdictions/<code>.md`) and its primary sources — never from this playbook.

## 1. Intake checklist

- Policy: declarations page, full policy form and endorsements (UM limits, stacking, med-pay, the notice,
  cooperation, proof-of-loss, appraisal and suit-limitation clauses). Save each as a file the gate can quote with
  `[src: …]`.
- Claim number, adjuster, every letter and email with dates; any recorded statement given.
- Capacity: whose claim it is. A minor's claim → the user acts as parent/guardian (gate rows 7–8); the user's own
  reimbursement for medical bills they paid → CONFLICT row, kept separate.
- Damages file: specials (bills, wages, mileage), records, provider narrative, photos, witness statements.

## 2. Clocks to find (never compute — record the rule and flag T-CLOCK)

| Clock | Where it comes from |
|---|---|
| Insurer's response deadline in a demand | the demand letter itself |
| Offer expiry | the offer letter |
| Policy notice / proof-of-loss / suit-limitation | the policy form — quote it |
| Tort limitations period against the at-fault party | the jurisdiction's statute (verify) |
| Contract limitations period against the insurer (UM claim) | the jurisdiction's statute (verify) — may differ from the tort period |
| Tolling for a minor | the jurisdiction's statute (verify), and whether it covers a parent's own claim for medical expenses |
| Majority / end of guardian authority | the jurisdiction's age-of-majority statute (verify) and the authority document |

"No time pressure" is a claim: list every row above with its verified source before saying it.

## 3. Letters

- **Demand / counter.** Facts, liability or coverage basis, itemized specials with records, general damages
  with the reasoning, the number, a response date. No settlement floor, no internal targets — those live in
  `strategy.md`, and the draft is run with `forbid` on them.
- **Tone.** Firm and factual. No threats of bad-faith litigation in a first counter; bad-faith facts are an
  escalation, not a bargaining chip.
- **Record requests.** Ask in writing for the insurer's coverage position (e.g. stacking) and a certified policy.

## 4. Offers and releases

- Read every release before any number is agreed: who is released, which claims, liens and reimbursement
  language, confidentiality, Medicare/Medicaid representations, and whether it binds a minor.
- **24-hour hold** between receiving final release language and anyone signing; the red team reads it first.
- **A minor's settlement usually needs court approval** (verify — the procedure and statute in the configured
  jurisdiction; some states call it a *pro ami* settlement). Drafting the petition is allowed (gate row 7); a human
  reviews it before it is filed; ask the court clerk (config `jurisdiction.court_clerk`) whether a guardian may
  file for the ward without a lawyer, and whether the court will appoint a guardian ad litem.
- Check what the authority document covers (config `guardianship_notes.insurance-claim`): a guardianship of the
  person alone does not let the guardian take the money — where it goes is the court's decision. Tax treatment of
  the settlement belongs to the tax-and-wealth team, in the minor's own project.

## 5. Disputes over loss history (C.L.U.E. / A-PLUS)

- Consumer reports are disputed under the FCRA (verify — 15 U.S.C. § 1681i) — a federal-law matter in the home
  forum, allowed by the gate.
- Keep the dispute letter to the reporting agency factual and document-backed; the insurer's underwriting
  decision is a separate conversation.

## 6. Outside help before court

- The state insurance regulator's consumer complaint (config `regulators.insurance`) — for delay, non-response or
  unfair handling.
- The lawyer-referral line (config `referral.line`). Many injury lawyers take UM claims on contingency; a consult
  before a court-approval hearing is cheap insurance.

## 7. Done means

Every authority in the outgoing letter passed the gate, the red team (`seat: insurer`) was read and answered, the
matter's clocks are in `project.yaml`, and the user has the draft in `outbound/` to review, sign and send
themselves.
