# Health verification rules

Read by the shared `source-verifier` (`agents/source-verifier.md`) as its `verification_ref` for the
`health` domain. Citation and quotation checking follows the verifier's own protocol; this file adds what is
health-specific. Paths below are relative to this skill's folder unless they name `skills/…`; config means
`config/household.yaml`.

## 1. Approved primary sources

| Kind | Source | Notes |
| :--- | :--- | :--- |
| Federal regulations | eCFR (`ecfr.gov`), with Cornell LII (`law.cornell.edu/cfr`) as fallback — 29 CFR 2560 / 2590 (ERISA, group plans), 45 CFR 147–149 (ACA, No Surprises Act), 45 CFR 164 (HIPAA), 42 CFR 433 (Medicaid), 26 CFR 1.501(r) | Record the as-of date |
| IRS guidance | Pub 969, Pub 502, Revenue Procedures, Chief Counsel memoranda on irs.gov | Use the edition for the year in question |
| CMS / DOL / HHS consumer pages | `cms.gov/nosurprises`, `dol.gov/agencies/ebsa`, `medicaid.gov` | For procedure and contact routes, not for the rule itself when a regulation exists |
| State statute | The configured state's legislature site or enrolled acts (the gate script's state adapter, if one exists — config `jurisdiction`); `reference/jurisdictions/<code>.md` holds the rows | FindLaw and Justia may be read to find a section, never to verify one |
| Plan documents | The group plan's SPD and benefit booklet, an individual policy's booklet, the FSA plan rules, the HSA custodian's terms | Plan rules, not law — cite as `[src: <document link or path>]` |
| The household's own records | `<eob_store>/claims.csv` (EOB rows, by `claim_id`), saved EOB PDFs (`eob_drive_id`), provider statements, orthodontic invoices | Figures come from here |

Secondary sources (KFF, patient-advocate blogs, vendor pages) may help **find** a rule. They never verify one.

## 2. Figure rule

A dollar figure or date in a draft passes only if it is one of:

- an EOB value, tagged `[eob:<plan>:<claim_id>:<column>]`, that matches that row of `claims.csv`;
- the output of `skills/hsa-fsa-reimburse/scripts/reimburse.py` or `skills/eob-sync/scripts/eob_check.py`
  for a stated run date, tagged `[script:<name>:<date>]`;
- copied verbatim from a quoted document, tagged `[src: …]`, or a limit in `rules-2027.md`, tagged `[rule:<key>]`.

Model arithmetic — a sum, a remaining balance, a computed deadline — is **FAIL**.

## 3. Deadline rule

An appeal, claim-filing, run-out or response date passes only if the document that sets it is quoted (the EOB,
denial letter, plan booklet or FSA plan rules). A rule-based clock (`erisa-appeal-180`, `external-review-4mo`)
is recorded as the rule plus the trigger date and flagged for T-CLOCK; it is never stated as a computed date.

## 4. Command

```bash
<config paths.verify_sources> <draft>        # authorities and quotations (tools/verify_sources.py in the public repo)
python3 skills/hsa-fsa-reimburse/scripts/reimburse.py status   # figures the draft cites from the register
```

The gate script fetches CFR from eCFR with LII as fallback, and IRS publications by edition year. A
`research`-status entry in `rules-2027.md` or the state file is re-fetched before it counts as PASS; until then it
is MANUAL.
