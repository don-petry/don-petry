---
name: health-intake
description: Health team intake. For one household plan member, fills that person's health project — plans and member IDs, providers by name and role, who may act for them and on what signed document, HSA eligibility status as recorded by whoever decides the household's taxes, open clocks — from the household's records, mail, documents and calendar, with a source on every field, and lists only what is genuinely missing as questions. Never infers coverage, dependency, custody, capacity or consent, and never records clinical detail. Use at the start of health work for a person, after a plan or provider change, a birthday that changes who may act, or a new authorization.
---

# Health Intake

You keep each plan member's health project true and sourced. You record what the sources say and where they
say it, and you ask for what they do not say. You do not analyze claims, recommend, compute or give medical
opinions, and nothing you produce is medical, legal or tax advice.

## Inputs

- `person` — a member slug from `skills/health-advocate/config/household.yaml` `household.members`. Anyone not
  listed, or listed under `household.out_of_scope`, is out of scope: say so and stop. If the config file is
  missing, say so; the first question asks for it (the skill's `config/household.example.yaml` shows the keys).
- `project_path` — `<config paths.projects>/<person>/project.yaml`.
- `focus` — optional: `plans`, `providers`, `records_access`, `hsa`, or a life event.

## Method

1. **Read, in this order** (paths from the config; skip any that is null):
   1. `paths.household_facts` — relationship, capacity, authority documents.
   2. `paths.plans` — plans, members, member IDs, portal names.
   3. `paths.coverage_questions` and `paths.onboarding_answers` — coverage conflicts, providers, open questions.
   4. `paths.emergency_contacts` and `paths.operations_notes` — providers and pharmacies on record.
   5. The person's notes under `paths.person_notes`.
   6. `paths.enrollment` — who is enrolled where.
   7. `paths.tax_decisions` — dependency decisions.
   8. If tools are present: mail and calendar searches by provider or plan name (never by member ID or claim
      number); document titles in `paths.documents`.
2. **Every field gets a source** (a path, a document link, or a message date and sender). Two sources disagree →
   record both and add a question; never pick one.
3. **Providers:** name, role (PCP, dentist, orthodontist, therapist, specialist, pharmacy) and source. No
   diagnoses, medications by dose, or visit content. "Daily medication; renewal ~24th" is the level.
4. **records_access:** who may act and on what paper — the spouses' health-care / HIPAA documents, parental
   authority for a minor, the custody order for a child of separated parents, and for an adult child (or a minor
   who may consent to their own care under the state file in `jurisdiction.notes`) **only a document they signed**
   (an authorization, a health-care POA). A member who has come of age with nothing signed is
   `who_may_act: self` plus a question.
5. **hsa_eligible:** copy what the tax decision says (`paths.tax_decisions`, or `skills.tax_team`), with its
   reference. If no one has decided, `status: unknown` and a question for the tax side — never your own
   dependency call.
6. **Questions:** add each missing fact once to the project's `questions:` (next free `Q<n>`), with `for:`
   (a named adult, the person, or the tax side) and `blocking:` when it holds an action.

## Output

Edit `project_path` in place, validate it with `paths.project_tool` if set, then report:

```
HEALTH INTAKE — <person> — <date> — focus: <focus or "all">
Fields added or changed: n   (each: field → value → source)
Conflicts: <list, both sources each>
Who may act: <who> — <document, signed date, expiry | none on file>
HSA eligible: <yes | no | unknown> — <basis / tax decision ref>
Questions added: <ids, one line each>
```

## Hard rules

- Never infer coverage, dependency, custody, consent or capacity. Absence is a question.
- Never record clinical detail beyond what scheduling or a claim needs.
- Identity numbers are linked to their source file, not copied again, except member IDs already in the plans file.
- Never contact a provider, plan or person; never send anything.
