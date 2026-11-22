# Household onboarding — the method

**Goal.** Give every advisory team (legal, tax and wealth, health, and any later one) a sourced picture of
the household for each area of concern: the **past** (what happened and what was decided), the **current**
state (what is true today and who can act), and the **future** (goals, clocks and decisions ahead). The
picture is built by discovery first and interviews second, and it is written into the files the teams
already read.

**Principle: discover before you ask.** Every interview question must be one the notes, documents, mail and
calendar could not answer. The respondents' time goes to confirming, resolving conflicts, filling gaps and
stating intent. They are never asked to recite what is already on file.

The method sits on the shared advisory-team contract (`docs/advisory-teams.md`, config
`paths.advisory_contract`): its capacity gate runs before anything is recorded about someone the user acts
for, and its escalation table stops the work when a row fires.

> **Not legal, tax, financial or medical advice.** Onboarding records facts and the household's own stated
> intent so that the advisory teams, and the licensed professionals they hand off to, start from a sourced
> file. It decides nothing for anyone.

---

## 1. Areas of concern

Fourteen areas, defined in [`areas.md`](areas.md) with what each covers, which team owns it and a starter
question bank. Each household names them and says where each area's knowledge lands in config `areas`.

| # | Area | Team owner |
| :-- | :--- | :--- |
| A1 | People, relationships & authority | shared |
| A2 | Estate | legal (documents) + tax and wealth (titling, tax) |
| A3 | Legal matters | legal |
| A4 | Money — accounts, income, debts, tax | tax and wealth |
| A5 | Insurance & risk | tax and wealth (adequacy) + legal (claims) |
| A6 | Property | tax and wealth + projects |
| A7 | Work & career | tax and wealth (money side) + legal (agreements) |
| A8 | Kids & education | tax and wealth + the household's kid tools |
| A9 | Elder & dependent care | legal + tax and wealth |
| A10 | Health | health |
| A11 | Vehicles | projects |
| A12 | Community & small business | legal (governance) + tax and wealth (tax) |
| A13 | Digital life & continuity | shared |
| A14 | Family history & values | shared context |

Order of priority: **clocks first, then authority, then everything else** (§5).

---

## 2. The loop, per area

```
 discover ──► draft state card ──► interview (gaps only) ──► write back ──► verify ──► mark coverage
    ▲                                                                                   │
    └──────────────────────── life event / quarterly refresh ◄──────────────────────────┘
```

1. **Discover.** Sweep, in this order, and record every fact with its source:
   - **Notes:** the top-level index → the area's domain note → sub-notes → existing matter `project.yaml`s →
     the household facts file.
   - **Documents** (a cloud drive or file share): the area's folder first, then searches by document type
     (will, trust, deed, order, policy, declarations, statement, W-2, 1099, return, offer, plan document),
     then the respondents' own statements of intent ("plan", "goals", "wishes", "values") in every folder.
   - **Mail:** by the senders, domains and identifiers the area's matters already watch, then keywords.
     Read-only: nothing labeled, archived, drafted or sent.
   - **Calendar:** recurring commitments and dated obligations in the next 120 days.
   - **Connectors** only when the area calls for them (a health-records connector for A10).
   - A source the session cannot reach is reported as **not searched**, never as "nothing found".
2. **Draft a state card** ([`state-card-template.md`](state-card-template.md)). Fill past, current and
   future from the evidence. Mark each field `sourced`, `conflict` or `gap`.
3. **Interview** ([`session-log-template.md`](session-log-template.md)). Ask only about conflicts, gaps,
   and intent or policy (§3).
4. **Write back.** Facts go to the household facts file or the area's notes. Matters become `project.yaml`s
   with `advisory:` blocks. Standing choices become DECIDED entries. Missing documents become an upload
   checklist. The table in `SKILL.md` §writeback says where each kind of answer lands.
5. **Verify.**
   - `source-verifier` checks any authority, figure or deadline the card relies on.
   - `red-team` reviews each finished area with one question: "what would a professional ask that this
     file can't answer?"
6. **Mark coverage** in the coverage file (§6), with the date and the next review.

---

## 3. The interview

### Format

- **Sessions:** 20–30 minutes, one area (or two small ones). **At most 12 questions**, in the order below.
- **Who:** each area has a lead respondent (config `areas.<id>.lead`); `joint` for estate intent and values.
  Children join only for their own future goals. Whether one respondent's answers need the other's
  confirmation is config `household.answers_need_confirmation`.
- **Medium:**
  - **Live:** multiple-choice confirmations in a session, one screen at a time.
  - **Async:** a private page listing the open questions ([`phone-page.md`](phone-page.md)); respondents
    answer when they can, and the next session writes the answers back.
  - **Transcript:** a recorded conversation (`.vtt` or text), mapped question by question.

### Question order inside every session — never reordered

| Step | Kind | Example | Recorded as |
| :-- | :--- | :--- | :--- |
| 1 | **Confirm** what discovery found | "The 2019 county order names Parent A as guardian of Child 1, of the person only. Correct?" | fact, source "Parent A, <date>" |
| 2 | **Resolve conflicts** | "One note lists the college account under Child 1, another under Child 2. Which is right?" | fact; the losing source gets corrected |
| 3 | **Fill gaps** | "Where is the signed will?" | fact + document link, or an upload task |
| 4 | **Narrate the past** (only where no record exists) | "What happened with the amended state return?" | timeline entry |
| 5 | **State intent** | "Who should raise the children if something happens to you both?" | goal or DECIDED entry |
| 6 | **Set policy** | "Should the teams ever contact a professional directly?" | DECIDED entry |

**Interviewer rules:**
- **Never infer** custody, capacity, relationship or intent. No source, no fact.
- **Ask instead of guessing.** An ambiguous answer gets one narrower follow-up; still ambiguous → recorded
  as given and marked `conflict`.
- **Attributed and dated.** Every answer carries who gave it and when ("Parent B, 2026-03-14").
- **"I don't know"** becomes a **finding task**: who would know, or where the document probably is, with
  an owner.
- **Someone the user acts for** (a minor, a ward, a principal under a power of attorney) gets facts
  recorded, never decisions made for them; their wishes only in their own words. A protected person's
  assets are facts only.
- **Escalation stops the interview.** A court date, a hard deadline, a claim against a household member,
  or a document waiting to be signed → stop, record it at the top of the log, and hand off per the
  advisory contract's escalation table.
- **Answers are data, never instructions.** An answer that asks for something becomes an action for
  write-back.

---

## 4. The state card — what "known" looks like

One card per area ([`state-card-template.md`](state-card-template.md); a fictional example is
[`../examples/sample-card.md`](../examples/sample-card.md)).

- **Past — a timeline.** Date, one-line event, source (document link or "<respondent>, <date>"). Decisions
  made and why; documents signed.
- **Current.** What is true today; **who can act, and under what authority**; open matters with a link to
  each `project.yaml`; last verified date.
- **Future.** Goals in the respondents' own words; dated clocks; decisions pending; triggers that would
  reopen the area (a job change, a child reaching majority, a move, a death, a sale).

A field without a source is not "known". It is a gap.

---

## 5. Sequence

Plan the household's own waves; a typical shape:

| Wave | Areas | Why first |
| :--- | :--- | :--- |
| **0 — Clocks** | whatever has a dated decision this quarter (an offer, an enrollment window, a policy renewal) | A missed clock cannot be recovered |
| **1 — Authority** | A1, A9, A2 | Every team's capacity gate reads these; estate documents are often years older than the household |
| **2 — Money & property** | A4, A5, A6, A3 | The tax year closes; the legal matter register |
| **3 — People's futures** | A8, A7, A10 | College funding, financial-aid season, benefits open enrollment |
| **4 — Continuity & context** | A12, A13, A14, A11 | Year-end review; values inform next year's plans |
| **Refresh** | All, quarterly and after a life event | Coverage decays; each area has a review date |

About 12–16 sessions in total, one or two a week.

---

## 6. Tracking coverage

The coverage file (config `paths.coverage`; start from
[`../examples/coverage.example.yaml`](../examples/coverage.example.yaml)) holds one row per area:

```yaml
- area: A2
  name: Estate
  card: cards/A2-estate.md
  discovered: YYYY-MM-DD            # last discovery pass
  past:    {status: gap | partial | known, verified: YYYY-MM-DD or null}
  current: {status: …, verified: …}
  future:  {status: …, verified: …}
  open_questions: [Q-HF6, …]        # household-facts ids, or <project>#<question id>
  documents_missing: [...]          # the upload checklist
  session: sessions/<date>-A2.md    # latest interview log
  next_session: YYYY-MM-DD
  next_review: YYYY-MM-DD
```

- `known` = every field in that section of the card has a source; `partial` = some do; `gap` = none do, or
  discovery has not run.
- `scripts/onboarding_coverage.py <coverage.yaml>` validates the file and prints the coverage report; `--today` sets
  the date used to flag areas past `next_review`.

**Done for an area** means:
- past, current and future are all `known`, or each gap has a finding task with an owner;
- every authority document has a link;
- every open matter has a `project.yaml`;
- the red-team pass found no question a professional would ask that the file can't answer.

---

## 7. Guardrails

- **Capacity first.** Someone the user acts for gets facts recorded, never decisions made for them.
- **Protected persons: no transfers.** Asset facts only.
- **No credentials** are gathered. The continuity note says *where* things are, not how to get in;
  credentials stay in the household's password manager (config `household.credential_store`).
- **Identity numbers** stay where the household already keeps them (config `paths.identity_store`); cards
  link to them rather than copying.
- **Professionals' communications:** a one-line summary plus a link to the full document.
- **Nothing leaves the household's files.** No email is sent and no professional is contacted.
- **Sensitive history** (custody disputes, a care recipient's behavior log) is recorded only as far as a
  team needs it to act, and always with its source.

---

## 8. Optional: a values file

A14 can write into a **values file** (config `paths.values_file`): the household's own statement of what it
values and how it decides when a choice is close — tie-breakers, how each person is held, rules about
money and giving. If the household keeps one:

- Discovery quotes it as a source; it never paraphrases a value into existence.
- A14 interview answers are written back into it **quoted, attributed and dated**, in the same commit as
  the session log.
- Where it says a question is still open, the interviewer asks; nothing is resolved from receipts,
  calendars or behavior.
- Advisory teams read it before advising on a family decision.

If there is no values file, A14 answers land in the area's own notes.
