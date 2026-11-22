# State card template

`onboarding-discovery` writes one card per area at `<cards>/<area-id>-<slug>.md` (config `paths.cards`).
Every field carries a source and a status: `sourced`, `conflict` (two sources disagree — both recorded,
neither picked) or `gap` (no source). Goals and intent are always gaps until a respondent states them.

A source is one of: a notes path with section or id; a document link with its date; a mail message's date,
sender and subject; a calendar event; or "<respondent>, <date>" for an earlier answer.

A fictional filled-in example: [`../examples/sample-card.md`](../examples/sample-card.md).

```markdown
---
title: "State card — <area id> <area name>"
created: <date>
modified: <date>
<config note_frontmatter keys, if any>
status: draft — discovery <date>
---

# State card — <area id> <area name>

**Lands in:** <config areas.<id>.lands_in> · **Team owner:** <from references/areas.md> · **Discovery:** <date>

## ESCALATION            <!-- only if one fired: court date, deadline inside 14 days, claim against a household member, document to sign -->

**Already answered elsewhere — not re-asked:** <pointers to facts already on file>

## Past — timeline
| Date | Event | Source | Status |

## Current
| Field | Value | Source | Status |      <!-- include who can act, and under what authority -->

## Future
| Field | Value | Source | Status |      <!-- goals, dated clocks, pending decisions, reopen triggers -->

## Open for the interview
| # | Kind (confirm / conflict / gap / intent / policy) | Question | Why it matters | Who answers |

## Documents missing (upload checklist)

## Coverage of this pass
<which of notes / documents / mail / calendar / connectors were searched, with the queries used;
anything not searched is named as not searched>
```
