---
name: tax-wealth-intake
description: Build or refresh the household fact finder for the tax & wealth and legal advisory teams
  — people, birthdays, who lives where, custody and guardianship orders, POAs, trusts, dependents' income,
  accounts, side business and household workers — mined from the household's own notes with a source for
  every fact, then list only what is genuinely missing as shared open questions. Never infers custody,
  relationship, capacity or authority, and never computes figures. Use for "tax-wealth intake", "update
  household facts", "authority documents", "what do we still need to know", after any life event (birth,
  move, new order, job change, new account), or when the tax-wealth skill runs intake.
license: MIT
metadata:
  argument-hint: '[all | <person> | <topic> | <life event>]'
---

# Tax-Wealth Intake

Phase 0 of the tax & wealth team. The fact finder it maintains is shared with the legal team; its
**Authority documents** section is what every `advisory:` capacity gate reads. Intake records facts; it
gives no tax or legal advice.

**Config:** the team's `../tax-wealth/config/household.yaml` — `paths.household_facts`, `paths.project`,
`intake_sources`, `household.protected_persons`, `household.decision_makers`, `paths.pm`. If it is missing,
the `tax-wealth` skill's §Your household says how to create it.

## Run

1. **Gate first.** Intake only records facts, so it runs in any capacity, but it never drafts a document or
   proposes a money move. If the request is really an action for someone else (a protected person, a minor),
   stop after intake and hand back to the `tax-wealth` skill.
2. **Do the intake** by following `agents/tax-wealth-intake.md`:
   - with subagents: dispatch `tax-wealth-intake` with `{facts_path, project_path, focus}`;
   - without subagents: read `agents/tax-wealth-intake.md` and follow it inline.

   Defaults: `facts_path` = config `paths.household_facts`, `project_path` = config `paths.project`, `focus`
   from the argument.
3. **Check the result.** Every new fact has a source path; no SSN, license, passport or account number was
   copied in; each new blocking question also appears in the project's `questions:` with a `ref`.
4. **Validate and render** the project with the project script (config `paths.pm` `validate` then `render`),
   if one is set.
5. **Report** the persona's output block to the user, leading with questions only the decision makers can
   answer.
6. **Commit** after the team config's `commit_checks`, per its `commit_rule`.
