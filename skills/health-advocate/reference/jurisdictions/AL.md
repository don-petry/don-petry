# State health rules — Alabama (labeled example)

**A labeled example of the shape, not your law.** The health team cites a state rule only from the configured
state's file (config `jurisdiction.notes`). Copy this file to `jurisdictions/<your state code>.md` and fill each
row from your own state's primary source — statute or enrolled act, fetched and quoted, with the date. Same
status meaning as `rules-2027.md`: `verbatim` was compared with the fetched text; `research` is re-fetched by
`source-verifier` before a draft relying on it leaves `drafts/`; a row without a quote is MANUAL.

The rows a household usually needs: **age of majority**, **when a minor may consent to their own care**, and
**a parent's access to a minor's health information** (HIPAA defers to state law here, [rule:hipaa-parent-state-law]).

| Key | Rule | Quote | Source | Fetched | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `al-majority-19` | Alabama majority is 19 | "at the arrival at the age of 19 years, shall be relieved of his or her disabilities of minority" | Ala. Code § 26-1-1 (FindLaw copy; the legislature's site did not render) | 2026-11-08 | research |
| `al-minor-consent-16` | Since 2025-10-01 a minor 16 or older may consent to their own health care (SB101 amending § 22-8-4) | — (quote to be captured from the enrolled act) | [SB101 (2025) enrolled](https://alison.legislature.state.al.us/files/pdf/SearchableInstruments/2025RS/SB101-enr.pdf) | 2026-11-08 | research — **quote missing; MANUAL until captured** |
| `al-parent-access` | A provider may not deny a parent or legal guardian a minor child's health information, with four exceptions (new § 22-8-12) | "no health care provider or governmental entity may deny a parent or legal guardian access to his or her minor child's health information" | SB101 (2025) enrolled, same link | 2026-11-08 | research — whether a legal custodian who is not a court-appointed guardian counts as a "legal guardian" here is open |

**What the rows change in the gate** (SKILL.md Step 0): in a state like this one, a 16- to 18-year-old consents
to their own care while still a minor for everything else, so a parent asks a provider for their information
only by citing the parental-access rule where it applies, or on the young person's signed authorization.
State FindLaw / Justia copies may be read to *find* a section, never to verify one.
