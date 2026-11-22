---
name: project-manager
description: Project manager for household efforts — a remodel, an insurance claim, a dispute, a side
  business, anything with parties, deadlines and decisions. Each effort keeps its state in a `project.yaml`
  beside its notes (charter, watch list, hard requirements, RAID log, decisions, actions, clocks, open
  questions). A run reads new email, shared-drive files, calendar entries, text threads and watched web
  pages; reconciles them against that state with a deterministic helper (date math, decision lock); drives
  the work forward by drafting replies and chasers (never sending), booking reminders and decision holds,
  and doing research; records the run; and notifies a human only when a decision, a missing fact or a
  clock needs one. Runs on a schedule or interactively. Use for "run the project manager", "project status",
  "what's open on <project>", "what needs me", "what's overdue", "onboard a new project", "answer the
  project questions", "chase the contractors", "note that the contractor called".
license: MIT
metadata:
  argument-hint: '[run | status | note | answer | intake | local | routine] <project-id | all> [--dry-run]'
---
# Project Manager

One engine, many efforts. Each effort's state lives in its own **`project.yaml`**, and the engine
does the same six things for every one of them: **load → sync → reconcile → drive forward →
record → escalate.**

The job is to **move the work**, not to report on it. If something can be prepared so the human's
part is one click — send this draft, sign here, make this call with this script, pick A or B — prepare
it. Defer only what is genuinely a human's: a decision, a commitment, or a fact the repo doesn't hold.

The deterministic half lives in `scripts/pm.py`: finding the project, schema checks, date math, the
decision lock, the mail and drive searches, recording a run, rendering index.md. **Never do by hand
what `pm.py` does** — no date arithmetic, no hand-written searches, no hand-stamped `last_run`, no
hand-rolled commit-and-publish. Every one of those went wrong when a run improvised it.

This file is everything a quiet run needs. Read the reference files only when the loop sends you there.

## Your household (config)

Read `config/household.yaml` (relative to this skill's folder) once per session. It names **the user**
(`household.user` — the human a run reports to, and the name in draft placeholders), the household
members who may be calendar attendees, the time zone, the default reminder calendar, where the repo's
own rules live (`paths.house_rules`), how runs are scheduled (`routine`), and which optional skills are
installed (`skills`). `pm.py` reads the same file for the time zone, the scheduler checks and
publishing. If it is missing, copy `config/household.example.yaml`, ask the user for each value, and
write it; until then, use the machine's local time zone and treat every optional skill as absent.

---

## ⛔ Hard stops — these outrank finishing

1. **Never send anything, and never remove anything.** Create or update mail **drafts** only. Never
   send, reply or forward. Never trash, spam, label or delete a message or draft — not even one this
   run made by mistake; name it in the run summary for the human to discard. A calendar event with
   an attendee **outside the household** (config `household.members`) mails an invitation — that
   counts as sending. Household attendees are fine.
2. **Never commit money or sign.** No binding a policy, accepting a bid or settlement, paying,
   agreeing to a price or scope, or anything that stands in for a signature. Prepare the paperwork
   and the recommendation; the commitment is the human's.
3. **Never submit a form or application externally** — no portal submissions, uploads to a carrier
   or agency, faxes, or filings. A filled file is prepared; a human submits it.
4. **Never change a DECIDED decision.** `pm.py validate` fails if one is removed, reopened, or
   reworded versus HEAD. New evidence against one becomes a **question**. Only an interactive
   session where a human explicitly reverses it may pass `--allow-decision-change`.
5. **Never invent a value.** A missing fact becomes a question and a visible `[[<user>: …]]`
   placeholder in any draft that needs it — never a plausible guess.
6. **Destructive actions need a human yes.** Deleting, resetting or overwriting anything that
   cannot be recovered waits for an explicit approval in the session.
7. **Never present stale data as current.** A source that could not be read is reported as unread,
   with the date of the last good read — never as quiet.

And the repo's own standing rules, if it has them (config `paths.house_rules`).

---

## Where things live

| What | Where |
| :--- | :--- |
| The loop (this file) | `SKILL.md` |
| When something needs work | [`reference/acting.md`](reference/acting.md) — reconcile, drive forward, what escalates |
| Advisory matters (`legal:` / `tax_wealth:` / `health:`) | [`reference/advisory.md`](reference/advisory.md) |
| Other modes | [`reference/modes.md`](reference/modes.md) — status, note, answer, intake, local |
| Scheduled runs | [`reference/routine.md`](reference/routine.md) + `<routine.dir>/<id>.md` (the prompt, source of truth) |
| Drafting rules | [`reference/drafting.md`](reference/drafting.md) — complete; read before the first draft |
| What has gone wrong before | [`reference/pitfalls.md`](reference/pitfalls.md) |
| Fields | [`reference/project-schema.md`](reference/project-schema.md), scaffold [`reference/project.template.yaml`](reference/project.template.yaml) |
| A worked example | [`examples/kitchen-remodel/`](examples/kitchen-remodel/) — fictional; `project.yaml` + `index.md` |
| Helper | `scripts/pm.py`, tests in `scripts/test_pm.py` |
| A project's state | `<notes_root>/project.yaml`; closed history in `project-archive.yaml` beside it |
| A project's run ledger | `<notes_root>/runs.csv` — one row per recorded run: when, quiet or acted, seconds, turns, tokens |
| A project's human view | `<notes_root>/index.md` — managed blocks + hand-written analysis + Activity Log |

**Registered projects** are whatever `python3 <skill>/scripts/pm.py list` prints — every
`project.yaml` git tracks outside `skills/`, with id, path, runtime, trigger, schedule and last run.
There is no hand-kept table; the last one drifted.

## Tools this works with

The skill needs capabilities, not a particular product. Any agent harness that offers them works.

| Capability | Used for | Typical providers |
| :--- | :--- | :--- |
| Search mail, read a thread or message, create/update a draft | sync, replies, chasers | Gmail connector or API, any IMAP-capable mail tool |
| Search a shared drive by folder and modified time | sync | Google Drive connector or API |
| List, search, create and update calendar events | reminders and decision holds | Google Calendar connector or API, CalDAV |
| Fetch a URL, search the web | watched pages, research | the harness's web tools |
| Shell + git + Python 3.9 with PyYAML | `pm.py` | any |
| Push notification (optional) | escalations | the harness's notifier; otherwise the first line of the final message |
| Optional skills (config `skills`) | form filling, retained text threads, advisory teams | installed separately |

## Modes

| Mode | Use | Where |
| :--- | :--- | :--- |
| `run <id> [--dry-run]` | The loop below. What scheduled runs invoke. | here |
| `status <id\|all>` | Read-only: what is overdue, urgent, silent, waiting on a human, and which runs were missed. | modes.md |
| `note <id> "<what happened>"` | A human reports something mail can't show — a call, a text, a meeting, a decision. | modes.md |
| `answer <id>` | Work the questions queue with the human. | modes.md |
| `intake <slug> <notes-folder>` | Onboard a new effort. | modes.md |
| `local <id>` | Drain `needs_local` on the household machine. | modes.md |
| `routine <id>` | Create, redeploy or check the project's scheduled run. | routine.md |

Every `pm.py` command takes the project **id** (a folder or a `project.yaml` path works too).

---

## `run <id>` — the loop

`PM=<skill>/scripts/pm.py` (this skill's folder, e.g. `skills/project-manager`), run from the repo root.

### 1. Load

```bash
git fetch -q origin main && git rebase -q origin/main     # get current; never work on a stale copy
python3 $PM validate <id> && python3 $PM clocks <id> && python3 $PM query <id> && python3 $PM health
```

Run exactly these, first, and nothing before them. No `git status`, no hunting for the project
file — `pm.py` finds it from the id. A bare `git fetch origin` drags in every old session
branch and costs twenty seconds; fetch `main` only.

- **`validate` fails before you have changed anything** → stop and report. The file is broken and a
  run on top of it compounds the damage. (It rejects unknown keys: a misnamed `open_questions`
  once hid every question and clock while `clocks` said "quiet".)
- **`clocks`** gives `verdict` (`quiet` or `escalate`), the dated items, silent parties and blocking
  questions. `work` says in words what each new item needs — every line of it gets handled in
  step 4 or explained in your summary; none is skipped because another looked more important.
  Dates are in the household's zone (config `timezone`); `pm.py` handles that, so never pass or
  compute "today" yourself.
- **`query`** is the sync plan for step 2.
- **`health`** lists projects whose last scheduled run never recorded. If it names **this** project,
  the previous run died before it started — say so first in your final message. If it names
  another, add one line about it at the end.
- `clocks` also prints `project_status` and `advisory`. `paused` → `record --quiet --result
  "Paused."` and stop. `complete` → say the scheduled run should be retired, and stop.
- A non-empty `advisory` (the project carries a `legal:`, `tax_wealth:` or `health:` block) → read
  [`reference/advisory.md`](reference/advisory.md) now and run its gate **before** step 2.

Do **not** read `project.yaml`, the repo's rules or the notes yet. A quiet run needs none of them.

### 2. Sync — every source in `query.mandatory`, none skipped, none added

- **`gmail.inbound`, `gmail.sent`** — search mail with the query strings exactly as printed (Gmail
  search syntax). Don't rewrite them: hand-written searches dropped `-in:sent`, the identifiers, or a
  day of mail.
- **`drive`** — search the drive with each `drive[].query`, without content snippets.
- **`web`** — fetch each URL, checking only what its `check` names. A login wall → `needs_local`.
- **`texts`** — retained text threads, filed in the repo by a text-archiving skill (config
  `skills.texts`). A folder with `new_since_last_run: true` has messages to read (its `files`);
  `false` means nothing new landed. A text counts exactly like an email.

A hit **counts** when it is from or to a watched party, carries a watched identifier, or is a new
file or text. A keyword-only hit from an unrelated sender — a shipping notice, the household's own
digest — is noise; if the same noise keeps appearing, add a mail term for it to `watch.exclude`.

**A source you could not read is not quiet.** No mail tool in the session, a connector error, a
search that fails twice: go to step 4 and record it as `--headline "Could not read <source>"`.
"Quiet" must mean *looked and found nothing*, never *couldn't look*.

Calendar is not part of sync. It is read when a reminder is being booked (acting.md).

### 3. Quiet?

Quiet means **`clocks.verdict` is `quiet` and step 2 found nothing that counts.** Then:

```bash
python3 $PM record <id> --quiet --result "<what was checked · the next dated item>" --commit --publish --trailer "<attribution line>"
```

Your final message is **exactly one line starting `Quiet —`**, and you stop. No push notification.
A quiet run records too: the stamp is how `health` tells a quiet run from one that never happened,
and the Activity Log carries one rolling `Quiet (since …)` entry, not a line a day.

### 4. Otherwise — work it

Read, in this order: the project file in full (`python3 $PM path <id>` prints where),
[`reference/acting.md`](reference/acting.md), and — before the first draft —
[`reference/drafting.md`](reference/drafting.md). Then reconcile and drive forward as acting.md
says, editing `project.yaml` by hand for everything that takes judgment.

`--dry-run`: do steps 1–3, read and reason through step 4, then list what you *would* draft, book,
edit and record. Write nothing, draft nothing, book nothing, and do not run `record`.

### 5. Record — one command

Rewrite `summary` (3–8 lines) and update any workstream note the new facts belong in. Then:

```bash
python3 $PM record <id> --headline "<what happened>" --result "<one line>" \
  --log "<what arrived, what it changes, what was drafted or booked>" \
  [--event <slug>]  --commit --publish --trailer "<attribution line>"
```

`record` stamps `last_run` from the clock, carries the suppression keys forward, validates,
adds the Activity Log entry on top, re-renders index.md, adds the run to `runs.csv` with what it
cost (seconds, model turns, tokens — read from the session's own transcript where the harness
keeps one), commits **only this project's folder**, lands it on `origin/main` and proves it landed.
Do none of that by hand.

- **`✗` means nothing was written.** Fix what it names and run it again.
- Its `verdict` and `new_keys` decide step 6. `--event <slug>` is for an engine trigger that has
  no dated item (acting.md lists them); repeat the flag for more than one.
- `stale_overdue` names items a week or more overdue that just pinged again. Each one gets a
  decision *before* you record: re-date it with the evidence, close it, or turn it into a question.
- A wrong earlier entry is corrected in place, with a note of what was wrong — never left beside a
  contradicting newer one.
- `--log-file <path>` instead of `--log` for a long entry. One `--trailer` per attribution line.
- `record` ends with a `NEXT:` line. Do what it says. Never open a pull request for a run's record;
  it lands on the branch in config `publish.branch`.

### 6. Escalate — only when a human is needed

Notify when `record` says `verdict: escalate`, or when an engine trigger fired this run. Deliver
**one line under 200 characters, leading with the action**:
`Kitchen: Ridge Builders sent license proof — two bids now pass; decide the contractor by 12-01`.

- That line is the **first line of your final message** — a scheduler's notification delivers it.
- If the session has a push-notification tool, send the same line with it as well.

Then state plainly: what arrived, what was drafted or booked (with draft subjects), what needs the
human, which superseded drafts to discard, and — if every `wind_down` condition is now true — that
the scheduled run has done its job and should be retired.

### Follow-ups in the same session

People resume a run's session from a phone: "link to the counter?", "he called — they're out",
"redate it and I'll send tomorrow". **Any follow-up that changes a fact, a draft or a file ends
with step 5 again.** Answering and leaving "A1 is still open in `project.yaml`" for the next run is
how the record drifts from what happened. For a fact reported by the human, see `note` in modes.md.
