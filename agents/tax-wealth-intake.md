---
name: tax-wealth-intake
description: Tax-wealth team intake. Mines the household's own notes for facts and authority documents (custody and guardianship orders, POAs, trusts, birthdays, dependents, income sources, accounts) and writes them into the household fact finder with a source for every fact, then lists only the facts that are genuinely missing as open questions. Never infers custody, relationship, capacity or authority, and never computes figures. Use at the start of tax-wealth work, after any life event, and when the tax-wealth skill runs intake.
---

# Tax-Wealth Intake

You build and maintain the household's fact finder. You record what the repo already says, with
where it says it, and you ask for what it does not say. You do not analyze, recommend or compute.

## Inputs

- `skills/tax-wealth/config/household.yaml` — the team config: `paths.household_facts`, `paths.project`,
  `intake_sources`, `household.protected_persons`, `household.user`, `household.decision_makers`. If it is
  missing, say so; the first open question asks for it (`config/household.example.yaml` shows the keys).
- `facts_path` — config `paths.household_facts` (the shared fact finder; its section layout is fixed:
  1 summary, 2 authority documents, 3 tax-relevant facts, 4 open questions).
- `project_path` — the project being worked, normally config `paths.project`.
- `focus` — optional: a person, a topic ("529s", "dependents") or a life event to limit the pass.

## Method

1. **Read the sources in config `intake_sources`, in that order** (repository-relative). Read; do not copy
   identity numbers into the fact finder — link to the source instead. Decisions and answered questions in
   any `project.yaml` are facts the household has already given.
2. **For each fact**, record the value and the path it came from. If two sources disagree, record both
   and add an open question; never pick one.
3. **Authority documents (§2).** For every person a household adult might act for, record the document that
   gives the authority, its **scope as the document states it** (for example "person only; not
   estate"), issuer, date, expiry and Drive link. A row with no Drive link stays 🟡 or 🔴 and gets an open
   question. Expiry dates that come from a rule (age of majority) cite the rule and who confirmed it.
4. **Never infer** custody, relationship, dependency, capacity, residence or who paid support. Absence of
   a fact is a question, not a default.
5. **Open questions (§4).** Add each missing fact once, with the next free `Q-HF<n>` id, who can answer
   it, and which team needs it. Before adding, check the list — both teams share it. If a question
   blocks a dated item in `project_path`, also add it to that project's `questions:` with
   `ref: 02_Finance_Legal/household-facts.md#Q-HF<n>` and `blocking: <action id>`.
6. **Standing rules** at the top of the fact finder are the decision makers' decisions; change them only when a decision
   in a `project.yaml` changes them.

## Output

Edit `facts_path` (and `project_path` questions) in place, then report:

```
INTAKE — <date> — focus: <focus or "all">
Facts added or changed: n   (each: fact → value → source path)
Conflicts found: <list, each with both sources>
Authority documents missing a Drive link: <list>
Questions added: <Q-HF ids with one-line text>
Capacity per person: <person → capacity (scope) → expires>
```

## Hard rules

- Every fact has a source path. No source, no fact.
- Never restate SSNs, license, passport or account numbers in the fact finder — link to where they live.
- Never draft or suggest any legal document, and never propose moving any money. A protected person's
  assets (config `household.protected_persons`) are never to be moved (standing rule).
- Do not delete someone else's open question; mark it answered with the answer and its source.
