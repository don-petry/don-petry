# Known pitfalls

What has actually gone wrong, from the run logs of the household this skill was built for. Most of
these are now guarded in `pm.py`; the entry says what the guard is so nobody works around it.
(Config `lessons` may record the household's own incidents behind each one.)

## Runs that never happened

- **A usage limit kills runs that fire just before it resets.** Three of the first four Tuesday
  routines fired at 6am, hours before the agent account's weekly reset, got rejected by the limit
  and ended in one second, logged as a success. Nothing told anyone. *Guard:* schedule daily runs
  clear of the reset (config `routine.scheduler_notes`); every run records, so `pm.py health`
  shows a run that didn't.
- **Clone failures stall a run.** Two runs had no repo source configured, tried to clone by hand,
  and sat waiting for approval all day. A hosted trigger must declare the git source. *Guard:*
  `pm.py routine <id> --deployed`, with config `routine.repo`.
- **A trigger without connectors reads nothing and looks quiet.** Three triggers were created
  without mail, drive or calendar access. *Guard:* the same drift check (config
  `routine.connectors`); and a source that can't be read is recorded as that, never as quiet.

## State that lied

- **Misnamed keys hide state.** A file with `open_questions` and clocks dated by `date` validated
  clean; five questions and eight clocks were invisible and `clocks` said "quiet".
  *Guard:* `validate` rejects unknown keys.
- **Hand-stamped `last_run`.** Rounded times, future times, a duplicated suppression key, a
  suppression key in the wrong grammar that pinged every day, a result string that broke the YAML.
  Four fix-up commits. *Guard:* `pm.py record` writes the block.
- **Overdue and forgotten.** An overdue item pinged once, then sat for two weeks while every run
  said "Quiet". *Guard:* overdue items ping again weekly and come back marked `stale`.
- **Stale framing.** Deadlines get retired (a "bind by the 15th" did). Trust
  `raid.assumptions` and `decisions` over dates found in older notes.

## Mail

- **Search previews lie by omission** — they show the oldest messages. Open the thread.
- **Big results overflow.** A whole-thread read on a long thread and listing drafts without a
  query both exceed the tool limit. Read the newest messages by id and always query drafts.
- **Updating a reply draft detaches it.** Gmail's draft update has no thread field. A test run
  updated three in-thread drafts and each became its own thread; it then tried to trash the copies
  and sat at a permission prompt. Re-create reply drafts instead; never trash.
- **A tool allowlist is not a complete guard.** A labeling tool that can also trash was still
  callable on a trigger limited to read + draft tools — only the permission prompt stopped it.
  Hard stop 1 is the real guard.
- **Mail clients don't render Markdown.** HTML body with real tags, plus the plain-text body.
- **A human working the same thread mid-run.** The user edits drafts and sends their own wording
  while a run is in flight. Re-check sent mail before recording what is outstanding.
- **Hand-written searches drift.** Some dropped `-in:sent`, some the identifiers, some a day of the
  window; keyword terms matched the household's own daily digest every morning. *Guard:*
  `pm.py query`, and `watch.exclude` for recurring noise.

## Publishing

- **Hosted sessions may insist their own branch is pushed** after the record lands on `main`.
  `record --publish` pushes it when config `publish.session_branch_prefix` matches; never open a PR.
- **Three writers, one file.** A scheduled run, an interactive session and the user can all be
  editing the same project. Let a run finish before starting another on the same project. A conflict
  inside a `pm:begin` block is settled by `pm.py render`; one in `project.yaml` is settled by hand.
- **Publishing by hand cost 30–40 seconds a run** (a fresh worktree of a large repo) and sometimes
  a second commit. *Guard:* `record --publish` rebases in place and only falls back to a temporary
  worktree when it must.

## Sessions

- **A resumed session answers and forgets to record.** "I didn't update `project.yaml`, so A1 is
  still open there." Every follow-up that changes something ends with `record`.
- **A long-lived interactive session is the most expensive thing here.** One reached hundreds of
  thousands of tokens of context; each turn re-read all of it. Start fresh for `answer`, `note` and
  `status`.
