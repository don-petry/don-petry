# The other modes

`PM=<skill>/scripts/pm.py`. Every command takes the project id. Config: `config/household.yaml`.

## `status <id|all>` — read-only

For each project (`pm.py list` for `all`): `pm.py clocks <id>` + `pm.py queue <id>`, then
`pm.py health` once. Present one compact block per project — status, overdue and urgent items with
day counts (flag the `stale` ones), silent parties, open questions (blocking first), the
`needs_local` count, drafts waiting to be discarded — and, at the top, any project whose scheduled
run was missed. No commit.

Asked what the routines cost: `pm.py usage <id> [--days 30]` rolls up that project's `runs.csv` —
runs, median seconds and turns, and tokens, with quiet runs split from the ones that did work.

## `note <id> "<what happened>"` — a human reports what mail can't show

Contractors text. Meetings happen in the driveway. A decision gets made over dinner. None of that
reaches the inbox, so it reaches the project only when someone says it here — in a session, or by
resuming a scheduled run's session from a phone. (Text threads the household chose to retain arrive
by themselves through a text-archiving skill and `watch.texts`; `note` is for everything else.)

1. Take the statement as the source: the person telling you was there. Record it as theirs, with
   the date and channel they give ("Parent A, 10-01, by phone with Pat"). Ask one question only if
   the statement is ambiguous about *who* (the same-first-name trap) or *what was decided*.
2. Read the project file and [`acting.md`](acting.md), then apply it exactly as a run would:
   `last_heard`, actions, clocks from any promised date, decisions the human made (DECIDED, quoting
   them), drafts now moot → `discard_drafts`.
3. Drive forward on what it unblocks, then `pm.py record <id> --headline … --commit --publish`.

A note that reverses a DECIDED decision needs the human to say so explicitly; only then pass
`--allow-decision-change`.

## `answer <id>`

Load open questions (`pm.py queue <id>`), blocking first. Ask them with the harness's question
dialog if it has one (up to 4 at a time), otherwise in plain text, offering concrete options when the question has them. Write each answer back
(`status: answered`, `answer`), apply what it unblocks — update the action, fill the
`[[placeholder]]` in its draft, mark a decision DECIDED when the human decided it — then `record`.

**Start a fresh session for this.** Answering in a session that has been open for days re-reads
its whole history on every turn: one two-sentence answer in a week-old session cost millions of
tokens.

## `intake <slug> <notes-folder>` — onboarding

1. Read the folder's `index.md` and siblings. For a folder with no notes yet, start empty.
2. Ask — no more than 4 at a time: goal and definition of done, hard deadline, owners (default
   config `household.decision_makers`), scope and out-of-scope, and whether it should run on a schedule.
3. Mine what exists: parties from `contacts.md` / the notes; Gmail for the top correspondents on
   the project's keywords over the last 90 days (propose them, don't assume); decisions and actions
   already written as prose; dated promises → clocks.
4. **Open each party's most recent thread in full before giving them a status.** A search preview
   shows the oldest message. The first onboarding listed a contractor as "silent since July" who
   had declined in August; the first run chased him, and a later run mixed him up with another
   Andrew — two commits to undo.
5. Copy `reference/project.template.yaml` to `<notes-folder>/project.yaml` and fill it in (the
   reminder calendar and cron default from config `calendar_for_reminders` and `routine.default_cron`;
   `examples/kitchen-remodel/` shows a filled one). Use the template's key names exactly — `validate`
   rejects any other. Decisions already made in the notes
   go in as DECIDED, citing where.
6. Add managed-block markers to `index.md` — `status` under the executive summary; `decisions`,
   `actions`, `clocks`, `questions` where the notes keep next steps — and an `## Activity Log`
   heading. **Never delete hand-written content**; retitle an old next-actions list as historical
   if the managed table replaces it.
7. `pm.py validate <path>` → `pm.py render <path>` → show the human the result → commit.
8. **`run <slug> --dry-run` and show the human what it would do** before any live run. The first
   live run after the first onboarding rewrote three of the user's own drafts.
9. Offer `routine <slug>`.

## `local <id>` — the household-machine queue

Work each open `needs_local` item on the household machine (config `local`): a signed-in browser
the agent can drive (`local.browser`), or a local upload tool with the machine's own credential
(`local.large_upload`). **Never type credentials.** If a site needs a login, open it, hand off
to the human, and read once they're signed in. Mark items `done` with `done_on`, then `record`.

## Housekeeping

- `pm.py archive <id>` lifts closed actions, clocks and `needs_local` items older than 14 days into
  `project-archive.yaml`. Run it when `validate` warns the file is large; commit the two files with
  the next `record`. Answered questions stay unless you pass `--questions` — an answer is often the
  only place a fact from a human lives.
