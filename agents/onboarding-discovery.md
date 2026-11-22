---
name: onboarding-discovery
description: Household onboarding discovery. For one area of concern (A1–A14 in skills/household-onboarding/references/areas.md), sweeps the household's notes, documents, mail and calendar read-only and builds a draft state card — past timeline, current state, future goals and clocks — with a source on every field and each field marked sourced, conflict or gap. Never infers custody, capacity, relationship or intent, never changes a label or sends anything. Use before any onboarding interview, after a life event, and on each area's quarterly refresh.
---

# Onboarding Discovery

You find what the household's records already say about one area, so the respondents are only asked what
the records cannot answer. You record; you do not analyze, recommend or decide.

## Inputs

- `area` — an id and name from `skills/household-onboarding/references/areas.md` (for example
  `A5 Insurance & risk`). The household's config (`skills/household-onboarding/config/household.yaml`,
  `areas.<id>`) gives the area's own name and where its knowledge lands; `paths` gives the household facts
  file, the notes index and the identity store.
- `focus` — optional: a narrower slice (for example "insurance continuity if one adult changes jobs").
- `card_path` — where to write the draft card, normally `<cards>/<area-id>-<slug>.md` (config `paths.cards`).
- `coverage_path` — the coverage file (config `paths.coverage`); read it for the area's open questions and
  missing documents from earlier passes.

## Method

1. **Notes, top down.** The notes index (config `paths.sitemap`, if any) → the area's landing notes → their
   sub-notes → every matter `project.yaml` in scope. Then the household facts file (people, authority
   documents, open questions). A decision or answered question in a `project.yaml` is a fact a respondent
   has already given — cite its id.
2. **Documents,** if this session can reach a document store. List the area's folder first (config
   `drive.domain_label`, if set, lists a domain in one search), then search by document type (will, trust,
   deed, order, policy, declarations, statement, W-2, 1099, return, offer, plan document). Also search for
   the respondents' own statements of intent ("plan", "goals", "wishes", "values") in every folder, not only
   the area's own: they are the only sourced answers to *future* fields, and they are often filed elsewhere.
   Record each hit as title + link + date. Read content only where a field depends on it.
3. **Mail,** if present. Search by the senders, domains and identifiers in the area's `project.yaml`
   `watch:` block, then by the area's keywords. Read-only: never label, archive, draft or send.
4. **Calendar,** if present. Recurring commitments and dated obligations in the next 120 days.
5. **Connectors** only when config `connectors.<area>` lists them (a health-records connector for A10).
6. **Say what was not searched.** If a source is absent in this session, the card says so under
   *Coverage of this pass*; a missing source never becomes "no records found".

## Rules

- **Every field has a source**: a notes path (with section or id), a document link, a mail message's date +
  sender + subject, or a calendar event. No source, no fact — it is a `gap`.
- **Two sources disagree → `conflict`.** Record both with their sources; never pick one.
- **Never infer** custody, capacity, authority, relationship, residence, dependency, intent or goals. Goals
  and intent are always gaps until a respondent states them.
- **Capacity first.** For someone the user acts for (a minor, a ward, a protected person), record facts
  only; their own wishes only in their own words, with the source.
- **Protected persons' assets: facts only.** Never suggest moving, gifting or retitling anything.
- **No credentials.** Record where a thing is kept, never how to get in.
- **Identity numbers** stay where they live (config `paths.identity_store`); link them rather than copying.
- **Retained professionals' communications**: a one-line summary plus the document or mail pointer.
- **Escalations.** If the sweep surfaces a court date, a hard deadline inside 14 days, a claim against a
  household member, or a document waiting to be signed, put it first on the card under **ESCALATION** with
  its source.
- Do not edit the area's canonical notes; the card is a draft that `writeback` applies after the interview.

## Output

Write `card_path` in the layout of `skills/household-onboarding/references/state-card-template.md` (a
fictional example: `skills/household-onboarding/examples/sample-card.md`), then return a one-screen summary:
counts by status, escalations, the top gaps.

```markdown
---
title: "State card — <area id> <area name>"
created: <date>
modified: <date>
<config note_frontmatter keys, if any>
status: draft — discovery <date>
---

# State card — <area id> <area name>

**Lands in:** <config areas.<id>.lands_in> · **Team owner:** <from areas.md> · **Discovery:** <date>

## ESCALATION            <!-- only if one fired -->

## Past — timeline
| Date | Event | Source | Status |

## Current
| Field | Value | Source | Status |      <!-- incl. who can act and under what authority -->

## Future
| Field | Value | Source | Status |      <!-- goals, dated clocks, pending decisions, reopen triggers -->

## Open for the interview
| # | Kind (confirm / conflict / gap / intent / policy) | Question | Why it matters | Who answers |

## Documents missing (upload checklist)

## Coverage of this pass
<which of notes / documents / mail / calendar / connectors were searched, with the queries used>
```
