# Jurisdiction notes — Alabama (EXAMPLE)

**This file is an example of the shape, for one state.** It holds research *leads*, not law. Nothing here
reaches a draft until the gate script fetches the cited section from the official source and passes it. Statutes
are amended; re-verify every lead in every matter. For another state, copy this file to
`reference/jurisdictions/<postal code>.md` and fill it from that state's official sources.

## Sources

| Authority | Citation form in a draft | Official source | Gate adapter |
|---|---|---|---|
| Code of Alabama | `Ala. Code § 26-1-1`, `§§ 32-7-23, 6-2-8` | ALISON, the Legislature's GraphQL API (`alison.legislature.state.al.us`) | `AL` (built in, the example state adapter) |
| Alabama cases | `… , 388 So. 2d 1207 (Ala. 1980)` | CourtListener | `cases`, with `AL` active for the Southern Reporter |
| Rules of Civil Procedure, court rules, Administrative Code | — | no adapter yet | quote only with `[src: path]` to a saved copy of the official rule |

Not usable for the gate: the ALISON web page (a JavaScript shell with no text); Justia and FindLaw (refuse
automated requests).

## Leads for the insurance-claim playbook (verify each)

| Clock | Lead |
|---|---|
| Tort limitations period against the at-fault driver | Ala. Code § 6-2-38 (verify) |
| Contract limitations period against the insurer (UM claim) | Ala. Code § 6-2-34 (verify) |
| Tolling for a minor | Ala. Code § 6-2-8 (verify), and whether it covers a parent's own claim for medical expenses |
| Age of majority / end of guardian authority | Ala. Code § 26-1-1 (passed the gate 2026-09-26: majority at 19 — re-verify) |
| Court approval of a minor's settlement (*pro ami*) | Ala. Code § 26-2A-6 (verify) and the circuit or probate court's local practice |

## Time computation

Alabama Rules of Civil Procedure Rule 6(a), with Alabama state and federal holidays — the rule set the shared
deadline calculation needs for this state (trigger T-CLOCK).

## Outside help

The Alabama State Bar runs a lawyer referral service, and the Alabama Department of Insurance takes consumer
complaints. Look up current contact details and fees from the source; a household records its own in config
`referral.line` and `regulators.insurance`.
