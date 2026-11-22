# Session log template

`onboarding-interviewer` writes one log per session at `<sessions>/<date>-<area-id>.md` (config
`paths.sessions`). Answers are attributed and dated ("Parent B, 2026-03-14") and verbatim where the
respondent typed them. `writeback` fills the last table.

```markdown
---
title: "Onboarding session — <area id> <area name> — <date>"
created: <date>
modified: <date>
<config note_frontmatter keys, if any>
---

# Onboarding session — <area id> <area name> — <date>

**Respondent:** <name | joint> · **Medium:** <live | async | transcript> · **Card:** <link>

## ESCALATION     <!-- only if one stopped the session; then hand off per the advisory contract -->

## Questions and answers
| # | Kind | Question | Answer | By, date |

## Finding tasks
| Task | Owner | Where to look |

## To write back       <!-- filled by writeback: each answer → the canonical file it lands in -->
| Answer # | Lands in | Change |
```

**Kinds,** in the fixed order: confirm → conflict → gap → past → intent → policy. At most 12 questions.
An unanswered async question keeps a blank Answer cell; it is not dropped.
