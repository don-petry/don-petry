# `project.yaml` — field reference

One file per effort, in that effort's notes folder beside `index.md`. A run that has work to do
reads it in full and edits it by hand; a quiet run reads it only through `pm.py`. `pm.py` writes
two mechanical things — the `last_run` block (`record`) and the removal of closed items
(`archive`) — and nothing else. A filled example is
[`../examples/kitchen-remodel/project.yaml`](../examples/kitchen-remodel/project.yaml) (fictional;
config `paths.example_project` may name a live one of your own); the scaffold is
[`project.template.yaml`](./project.template.yaml).

**Use these key names exactly.** `pm.py validate` rejects any key it does not know, at the top
level and inside every list and block below. The engine ignores what it does not recognise, so a
misnamed key (`open_questions`, a clock dated by `date`) hides state while everything looks fine.

Dates are always `YYYY-MM-DD`. An event-triggered deadline ("when the C.L.U.E. report arrives")
is not a date — put it in `escalate_when` or an action's `next_step`, never in `due`.

## Identity and runtime

| Field | Meaning |
| :--- | :--- |
| `id` | Short slug. Also names the scheduled-run prompt `<routine.dir>/<id>.md` (see routine.md). |
| `title`, `owners` | Display. Owners are the humans who decide. |
| `status` | `active` · `paused` (routine skips work, one line) · `complete` (routine recommends retirement). |
| `hard_deadline` | The date the whole effort is judged against, or `null`. |
| `notes_root` | Repo-relative folder holding this file and `index.md`. |
| `runtime` | `cloud` or `local`. Decides which tools a scheduled run can count on — see acting.md. |
| `trigger_id` | The scheduler's id for this project's job, set by `routine` mode. |
| `cadence.cron` | The schedule, identical to the routine file's `cron`. Write it with a zone — `CRON_TZ=America/New_York 30 11 * * 1-5` — and it follows DST. A bare cron is UTC and does not. |
| `cadence.urgency_window_days` | A dated item inside this many days is *urgent*. Default 10. |
| `cadence.overdue_reping_days` | An overdue item pings again every this-many days until re-dated or closed. Default 7; `0` turns it off. |
| `calendar_for_reminders` | Calendar id where reminders and holds are created. |

## What the effort is

| Field | Meaning |
| :--- | :--- |
| `charter` | `goal`, `scope`, `out_of_scope`, `success_criteria`. |
| `summary` | 3–8 lines of Markdown status. Rewritten by each run; rendered into index.md. |
| `wind_down` | Conditions that, when all true, end the routine. |
| `workstreams` | `{id, title, notes}` — links to existing notes. Never copy their content here. |

## What to watch

`watch.parties[]` — everyone the effort is waiting on or corresponding with:

| Field | Meaning |
| :--- | :--- |
| `name`, `org` | Who. |
| `emails`, `domains` | Gmail search terms (`from:` either). |
| `phones` | Numbers they text from. Informational here; the thread itself is retained by a text-archiving skill, if one is installed (config `skills.texts`). |
| `waiting_on` | What we are owed. Empty = not waiting. |
| `last_heard` | Date of their last substantive inbound message. Update it when one arrives. |
| `silent_after_days` | Past this, `pm.py clocks` lists them in `silent_parties` and the run drafts a chase. |
| `status` | `active` (default), or `done` / `declined` / `dropped` / `paused` — any of the last four stops the chase without deleting the history. |

`watch.identifiers` (policy, claim, permit, invoice numbers), `watch.keywords`,
`watch.drive_folders[{name,id}]`, `watch.calendars[{name,id}]`, `watch.web[{url,check}]`.
`watch.texts[]` — repo folders of retained text-message transcripts for this effort
(`<notes_root>/texts/<party>`), written by a text-archiving skill. `pm.py query` lists each folder's
month files and whether anything landed since the last run.

`watch.exclude` — raw Gmail terms subtracted from the inbound search, for noise a keyword keeps
catching: `["from:parent.a+cc@example.com", "from:ups.com"]` (config `household.self_cc`).

`pm.py query` turns all of this into the searches a run executes. Parties, identifiers, folders and
web checks are each **mandatory** every run once listed; keywords widen the net and are where noise
comes from, so keep them specific. Text folders are mandatory once listed, too.

## How to judge what arrives

| Field | Meaning |
| :--- | :--- |
| `requirements` | Hard tests an incoming quote, bid, or offer must pass. Test these **first**. |
| `do_not` | Standing prohibitions specific to this effort. |
| `playbook_notes` | Judgment the engine can't know ("claim correspondence goes through the portal, not email"). |
| `raid` | `risks`, `assumptions`, `issues`, `dependencies` — strings or `{id, text}`. |
| `escalate_when` | Effort-specific triggers that always need a human, on top of the engine's defaults. |

## State the run maintains

| List | Fields | Rules |
| :--- | :--- | :--- |
| `decisions` | `id, text, status (OPEN\|DECIDED), date, rationale, ref` | **DECIDED is locked.** `pm.py validate` fails if one is removed, reopened, or reworded versus HEAD. Contradicting evidence becomes a question. |
| `actions` | `id, text, owner, due, status, next_step, blocked_by, draft_id, ref, done_on` | Status: `open, in_progress, waiting, blocked, done, dropped`. `draft_id` is the Gmail draft prepared for it, so the next run updates rather than duplicates. `next_step` holds the *current* next step, not its history. |
| `clocks` | `id, due, item, owner, on_miss, status, done_on, note, source` | Dated obligations — ours or theirs. When the date moves, change `due`; don't append "UPDATE …" to `item`. |
| `questions` | `id, text, for, blocking, raised, status, answer` | The queue for a human. `blocking` makes it escalate. Status: `open, answered, withdrawn`. |
| `needs_local` | `id, task, why, raised, status, done_on` | Work a cloud run can't do: logged-in browsing, social profiles, large PDFs, form uploads over the connector limit. |
| `discard_drafts` | `id, subject, why, raised` | Gmail drafts that were superseded or overtaken. The engine never deletes; index.md lists these for a human to discard. Remove the entry once the draft is gone. |
| `last_run` | `at, runtime, result, escalated[]` | **Written by `pm.py record`, never by hand.** `at` is the instant the run recorded; `runtime` is `cloud`, `local` or `interactive`; `escalated` holds the keys already notified, so the same item doesn't ping daily. |

Closed actions, clocks and `needs_local` items older than two weeks move to `project-archive.yaml`
beside this file when `pm.py archive` is run. Ids listed there are spent — `validate` rejects reuse.

## `runs.csv` — the run ledger

`pm.py record` appends one row per run to `runs.csv` beside this file; nothing else writes it.

| Column | Meaning |
| :--- | :--- |
| `at`, `runtime` | The same stamp and runtime as `last_run`. |
| `outcome` | `quiet` or `acted`. |
| `verdict` | `quiet` or `escalate` — whether the run had something new to notify. |
| `seconds` | From the prompt that started the turn to the record step (from the transcript), else from `pm.py query`. The closing message is not included; nor is sandbox start-up. |
| `turns` | Model calls in that turn. |
| `model` | The model that ran it. |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | Summed over those calls, from the session's own transcript. Cache reads are most of a run and the cheapest kind. |
| `headline` | The Activity Log headline of a run that acted. |

Cost columns are blank when the session left no readable transcript (Claude Code's are found
automatically; another harness can point `$PM_TRANSCRIPT` at a JSONL transcript of the same shape); the row is still written, so
the file is a complete list of runs either way. `pm.py usage <id>` summarises it.

## Managed blocks in `index.md`

`pm.py render` rewrites only what sits between markers; everything else is hand-written and left
alone. Use any subset, anywhere in the file:

```markdown
<!-- pm:begin status -->
<!-- pm:end status -->
```

Blocks: `status`, `decisions`, `actions`, `clocks`, `questions`.

## Notification behavior (see SKILL.md §Escalate)

`pm.py clocks` emits `escalate_keys`: `clock:C1:urgent`, `action:A2:due-tomorrow`,
`action:A2:overdue`, `clock:C3:overdue:14d`, `question:Q1`, `silent:ridge-builders:2026-09-22`. An
`escalate_when` trigger has no dated item; `record --event <slug>` keys it
`event:<slug>:<YYYY-MM-DD>` and keeps it a month. Keys outside the grammar never match, so the item
would re-escalate every run — validate rejects them. The verdict is `escalate` only when a key is
**new** since `last_run.escalated`.

- An item re-escalates when it worsens: `urgent` → `due-tomorrow` → `overdue`.
- Once overdue it pings again every `overdue_reping_days` (`overdue:7d`, `overdue:14d`, …).
- A party past `silent_after_days` pings once per silence, keyed by the date last heard from.

## Extensions — advisory teams (legal, tax-wealth, health)

For households that run advisory-team skills on top of this engine (the framework in
`docs/advisory-teams.md` of the public repo; config `paths.advisory_contract`). **The core schema
above works without any of this.** `pm.py validate` knows these top-level blocks by name
(`advisory`, plus `ADVISORY_TEAMS` in `pm.py`) and does not look inside them, so the teams can add
fields without code changes; the clocks, decisions, actions and questions they generate still go in
the ordinary lists above, so the scheduled run and the decision lock see them.

A matter two teams touch (an estate) is **one** project carrying both blocks. Read
[`advisory.md`](./advisory.md) for how a run treats them.

### `advisory:` — shared, required once any advisory team works the effort

Field names are the framework's generic ones. A household that uses other names maps them in config
`schema.field_names` (for example `capacity: my_capacity`), and runs read and write those.

| Field | Meaning |
| :--- | :--- |
| `party` | Whose matter it is — a household member's slug or an entity name. |
| `capacity` | The user's capacity in it: `self` · `joint` (with a spouse or partner) · `parent` · `guardian` · `conservator` · `poa_agent` · `trustee` · `none`. |
| `authority_doc` | Repo path or drive link to the order, POA or trust that gives the user that capacity; `null` if none. |
| `authority_expires` | Date the capacity ends (a minor reaching majority, an order's term), or `null`. |
| `personal_interest` | The user's own stake in someone else's matter (a reimbursement, a fee, an inheritance), or `null`. A non-null value puts the matter in CONFLICT handling. |
| `forum` | `presuit` · `agency` (insurer, tax authority, benefits agency) · `court`. |
| `jurisdiction` | List of codes, e.g. `[NY]`, `[NY, federal]`. The team skill escalates anything outside the household's configured jurisdictions. |
| `represented` | `true` once a lawyer, CPA or EA is retained on this matter. |
| `anticipation_of_litigation` | `true` once a dispute is expected; turns on the hold rule (no deletes or history rewrites). |
| `gaps` | Evidence for capability triggers: `- {trigger: T-…, date: YYYY-MM-DD, note: …}`. |

### `legal:` — owned by the legal team skill

| Field | Meaning |
| :--- | :--- |
| `matter_type` | `insurance-claim` · `contract` · `estate` · `landlord` · `small-claims` · … (one playbook each). |
| `mode` | Derived by the legal gate each run (SELF, JOINT, FIDUCIARY_PRESUIT, FIDUCIARY_COURT, CONFLICT, LAWYER_PREP, TRANSITION, ESCALATE, INFO_ONLY); recorded for the status banner. |
| `forbid` | Strategy strings (settlement floor, targets) that must never appear in an outgoing draft. The source verifier reads them on every run. |
| `authorities_dir` | Folder of fetched source snapshots, default `<notes_root>/authorities/`. |

### `tax_wealth:` — owned by the tax-wealth team skill

Keep its fields inside this block. **A minor's money is its own project** with its own `advisory:`
block — a child's return, account or settlement never rides on the household project.

| Field | Meaning |
| :--- | :--- |
| `scope` | `household` (the adults' joint finances) · `individual` (one person's own return, account or settlement) · `estate` (alongside a `legal:` block). |
| `taxpayers` | Household slugs whose returns this project covers. |
| `filing_status` | `mfj` · `single` · `dependent` (a child filing their own return) · `none` (no return filed). |
| `tax_years` | Years in scope, e.g. `[2025, 2026]`. |
| `jurisdictions_filed` | Returns filed, e.g. `[federal, NY]`. Anything beyond the configured ones escalates. |
| `preparer` | `self` · `cpa` · `ea` · `software` · `unknown`, plus a link to the engagement letter when retained. A retained professional's communications are stored as a summary in the notes plus a link to the full document. |
| `runs_dir` | Folder of engine outputs, default `<notes_root>/<year>/runs/`. Every figure in a draft carries a `[run:<id>]` tag that resolves to a file here, stamped with engine, version, input hash and date. |
| `rules_ref` | The dated rules file drafts cite (as `[rule:<key>]`). |
| `related_projects` | Other `project.yaml` paths this one hands off to or reads from. |

### `health:` — owned by the health team skill

**One project per person.** An adult's project is their own; another household member acts in it
only on a signed authorization recorded in `records_access`.

| Field | Meaning |
| :--- | :--- |
| `person` | Household member's slug. |
| `plans` | Plan keys the person is a member of, plus any other coverage named in words (e.g. `state-medicaid (secondary — unconfirmed)`). |
| `portal_name` | How the carrier portals print the name, when it differs. |
| `providers` | `- {name, role, source}` — names and roles only, never clinical detail. |
| `hsa_eligible` | `{status: yes · no · unknown, basis, source}` — whether this person's expenses can be paid from the household HSA (IRS Pub 969). `unknown` holds every reimbursement for the person; the tax team decides dependency. |
| `accounts` | Only on the account holder's project: the household HSA and FSA — custodian, sponsor, kind, source. |
| `records_access` | `{who_may_act, document, signed, expires, note}` — who can get this person's records and talk to their providers and plans, and on what paper. |
| `related_projects` | Other `project.yaml` paths this one reads or hands off to. |
