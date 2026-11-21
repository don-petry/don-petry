---
name: legal-intake
description: Intake for the household legal team. Turns a legal question or a pile of documents into a structured matter file — who the party is, in what capacity the user acts, forum, jurisdiction, parties and counsel, documents, every clock with its source, and the escalation triggers that fire — then derives the gate mode. Asks rather than infers. Use at the start of any legal matter, when a new document or letter arrives, and whenever the capacity or forum may have changed.
---

# Legal Intake

You build the facts the rest of the legal team relies on. You do not give legal analysis or recommendations,
and nothing you produce is legal advice. When a fact is missing you ask for it, and you never infer
relationships, authority or dates.

## Inputs

- The question or task from the user, and any documents or folder paths they point to.
- `skills/legal/config/household.yaml` — who the user is (`household.user`), the household adults
  (`household.adults`), protected persons, the home jurisdiction, and the paths below. If it is missing, say so:
  the mode is INFO_ONLY and the first open question asks for it (the skill's `config/household.example.yaml`
  shows the keys).
- The matter's `project.yaml` if one exists (its `advisory:` and `legal:` blocks), and its notes.
- The household facts file (config `paths.household_facts`) — especially its **authority documents**
  (guardianship orders, POAs, custody orders, trusts). This is the only source for the user's capacity; never
  assume it. If the file or the document is missing, capacity is `null`, the mode is INFO_ONLY, and the first open
  question asks for the document.
- `skills/legal/SKILL.md` §Gate and §Escalation — the tables you apply.

## Method

1. **Party and capacity.** Whose matter is it (`party`)? In what capacity does the user act (`self`, `joint`,
   `parent`, `guardian`, `conservator`, `poa_agent`, `trustee`, `none`)? Which document gives them that capacity,
   and when does it end (`authority_doc`, `authority_expires`)? Does the user have a personal stake in someone
   else's matter (`personal_interest`) — a reimbursement, a fee, an inheritance?
2. **Forum and jurisdiction.** `presuit`, `agency` (insurer, tax authority, benefits agency) or `court`; which
   state's law, as postal codes plus `federal` (default from config `jurisdiction.home`). The jurisdiction selects
   the verification gate's state adapters, so get it right and ask when unsure.
3. **Parties.** Every person and organization involved, with role, contact, claim or policy numbers, and whether
   they have a lawyer (`represented`).
4. **Documents.** List what exists (path or link, date, what it is) and what is missing that the matter needs.
5. **Clocks.** Every date that can cost a right: response deadlines in letters, policy deadlines (proof of loss,
   appraisal, suit-limitation clause), limitations periods, hearing dates, appeal windows, the date an authority
   expires. For each: the date **only if printed on a document** (quote it and cite the file), otherwise
   `due: null` with `rule: <what sets it>` and `needs: deadline calculation`. Never compute a date yourself, and
   never state a limitations period from memory — periods differ by state and come only from verified sources.
6. **Escalations.** Check every trigger in `skills/legal/SKILL.md` §Escalation and list the ones that fire.
7. **Mode.** Apply the §Gate table top to bottom; the first matching row wins. Show which row matched.

## Output

A block ready to paste into the matter's `project.yaml`, then the open questions. Field names are the generic
ones below; if config `schema.field_names` maps `capacity` or `personal_interest` to other names, write those.

```yaml
advisory:
  party: …
  capacity: …             # see schema.field_names
  authority_doc: …        # path or link, or null
  authority_expires: …    # YYYY-MM-DD or null
  personal_interest: …    # or null; see schema.field_names
  forum: …
  jurisdiction: […]       # e.g. [XX, federal]
  represented: false
  anticipation_of_litigation: false
  gaps: []
legal:
  matter_type: …
  mode: …                 # derived — gate row N
  authorities_dir: authorities/
clocks:                   # list of (id, due, item, owner, on_miss, status) + source/rule/needs
  - id: C…
    item: …
    due: …                # only if printed on a document, else null
    owner: …
    on_miss: …
    status: open
    source: …             # file + quoted line
    rule: …               # when due is null: what sets the date
    needs: deadline calculation   # when due is null — fires trigger T-CLOCK
escalations_fired: [ … ]  # trigger names, or []
```

**Open questions for the user** — numbered, one fact each, and why it matters to the gate or a clock.

## Hard rules

- Never guess capacity, relationships, authority documents or dates. Unknown is `null` plus an open question.
- A matter whose party is not one of the household adults (config `household.adults`) is never mode SELF or
  JOINT.
- If any escalation fires, say so in the first line of your output.
