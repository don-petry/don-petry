# Acting — when a run has something to work

Read this when SKILL.md step 3 says the run is **not** quiet: `clocks.verdict` is `escalate`, or
sync found mail, a sent message, or a file that counts. You have just read the project file in full.
Read [`drafting.md`](drafting.md) before the first draft.

Open `workstreams[].notes` only when something in this run touches that workstream — progressive
disclosure, not a crawl. Closed history is in `project-archive.yaml`; search it when an old item
matters, and never reuse an id listed there.

## Reading what arrived

- **Open every thread that counts, in full.** Search previews show the oldest messages, not the
  newest.
- **A long or attachment-heavy thread overflows a whole-thread read** (60K–300K characters). Take
  the newest message ids from the search result and read those messages one by one.
- **Never list drafts without a query.** A mailbox holds dozens of drafts and the full view
  overflows (212K–269K characters). Use `query.gmail.drafts`, or read the drafts by the ids in
  `query.open_draft_ids`.
- **Texts** (`query.texts`): read the listed month files from the last run's date onward. A text
  sets `last_heard`, closes actions and starts clocks exactly like an email. The folder is only as
  fresh as the last sync (config `texts.sync_host`) — its `index.md` shows the last message on file —
  and a cloud run cannot refresh it, so a stale folder becomes a `needs_local` item, not a guess.
  Read config `texts.caveat` for any known gap in the threads (for example, a phone that does not
  archive the user's own replies): never read such a gap as the user not answering.
- **Re-check before recording what is outstanding.** The user edits drafts and sends their own
  wording while a run is in flight. Look at `gmail.sent` again and never resurrect an ask he has already
  answered his own way; a staged draft he has overtaken is moot — say so and list it to discard.

## Reconcile — what does it change?

For each new item:

1. **Test it against `requirements` before anything else.** A quote that fails one is reported as
   failing, with the requirement it fails — not summarised as a price.
2. Apply `playbook_notes` and `do_not`.
3. Update state in the project file by editing the YAML directly:
   - party `last_heard` when they sent something substantive;
   - actions → `done` (with `done_on`) when the mail or sent folder shows they happened; new actions
     for new asks, with an owner and a `next_step`;
   - clocks added from promised dates ("we'll respond within 30 days" → a clock);
   - RAID entries for new risks, issues, and dependencies;
   - **decisions**: may add OPEN ones; may mark an OPEN one DECIDED only when a human's own words
     (their email, their note) decide it — quote the source in `rationale`. Never touch DECIDED.
   - questions for anything only a human knows or decides.
4. Anything contradicting a DECIDED decision or the notes → a question, and it escalates.
5. **Advisory matters:** test every new item against `escalate_when` and the team skill's own
   escalation list *before* drafting anything. One that fires ends the drive-forward work for that
   item — [`advisory.md`](advisory.md) step C.
6. **Verify before you rewrite the record.** A human's aside ("the roofer dropped out") is a lead, not
   evidence: find the message that proves it, quote the date and channel in the rationale, and only
   then edit parties, decisions or actions. If the evidence isn't there, say so and ask — never
   invent a channel ("must have been by text") to explain why you can't find it.
   **Two people with the same first name is the trap that has actually bitten** (two contractors
   named Andrew, at different firms): when a name is ambiguous, resolve it to an address before
   touching state. (A human telling *this session* directly what happened to them is
   different — that is `note` mode, and their statement is the source.)

**Keep the state small.** An item holds its *current* state. History goes in the Activity Log, not
into `next_step` or a clock's `item` as a growing chain of "UPDATE 09-29: …". `validate` warns when
a field or the file has grown past what a run should have to read; `pm.py archive <id>` lifts
closed items out.

## Stale overdue items

`clocks` marks an overdue row `stale: true` when it has been overdue a week (or another week) and
is pinging again. A clock that sits overdue while the note says "do not chase" is a clock that is
wrong. Before recording, each stale item gets one of:

- **re-dated** to the date now actually expected, with the evidence in `note` / `next_step`;
- **closed** (`status: done` or `dropped`, with `done_on`) because the obligation ended;
- **turned into a question** for the human, when only they know whether it still matters.

## Drive forward — prepare the next move on every open item

Walk open `actions`, `silent_parties`, and new mail. For each, do the most useful preparatory thing
that stays inside the hard stops:

| Situation | Do this |
| :--- | :--- |
| Inbound needs a reply | Draft it in the thread (as a reply to the message being answered), following drafting.md. Record `draft_id` on the action. |
| Party is in `silent_parties` | **First check our ask was actually sent** (`gmail.sent`). If it's still an unsent draft, the action is the human's — say so; don't chase. Otherwise draft a short chase with a date. |
| A draft for this purpose already exists | A **standalone** draft: update it. A **reply** draft (it sits in someone's thread): do **not** update it — Gmail's draft update drops the threading. Create a new reply draft in that thread, record the new `draft_id`, and add the old one to `discard_drafts`. Check the returned thread id matches. |
| A draft has been superseded or overtaken | Add `{id, subject, why, raised}` to `discard_drafts`; index.md lists them for the user. Remove an entry once the draft is gone from Gmail. Never trash it yourself. |
| A dated clock or action exists | Ensure a reminder on `calendar_for_reminders`: all-day event `⏰ <title>: <item>` on the due date (search first; update, don't duplicate). For decisions, book a 30-min **hold** 2 business days before the drop-dead date: `🧭 Decide: <decision>`. Household attendees only. |
| A call is the next step | Write the call script into the action's `next_step` or the notes: who, number, reference numbers, the exact asks in order. |
| **An advisory matter needs a letter, demand, counter or response** | Do **not** write it into a mail draft. If the owning team's skill is installed (config `skills.advisory`), invoke it; draft into `<notes_root>/drafts/` and follow advisory.md step D. Nothing reaches `outbound/` or the mailbox on an unattended run. |
| A form is needed | If a form-filling skill is installed (config `skills.form_fill`), invoke it; otherwise prepare the field values in the notes. Upload the filled copy beside the original in the drive when it fits the connector; attach small files to the draft. Large files or no credential → `needs_local`. Never submit. |
| Research would unblock it | Search the web and fetch pages — carrier ratings, statutes, permit status, contractor licenses, a company's public site. Cite sources in the notes. Logged-in pages, LinkedIn, or social profiles → `needs_local`. |
| It's a decision | Don't decide. Make it decision-ready: options, recommendation with numbers, cost of waiting, drop-dead date → an OPEN decision + a question. |

## What escalates

`record` reports `verdict: escalate` when a key is new: a dated item entering the urgency window,
reaching due-tomorrow, going overdue or re-pinging; a new blocking question; a party newly silent.
Those need no flag. The **engine triggers** below have no dated item, so pass `--event <slug>` to
`record` for each one that fired (`--event revised-plans`):

- a quote, bid, or settlement offer arrived;
- a reply needs a fact the repo doesn't hold;
- something contradicts a DECIDED decision or the notes;
- a party declined;
- a project `escalate_when` rule fired;
- a source could not be read.

`record` keys an event to today's date and keeps it for a month, so the same event does not ping
twice. Don't write suppression keys by hand — the grammar is `pm.py`'s.

## What this session can and cannot do

Check what the session actually has; config `tools` and `local` say how this household's sessions
usually look.

| | Scheduled cloud run | Local (the household machine, config `local.name`) |
| :--- | :--- | :--- |
| Runs when | On schedule, household machine off | Only while the agent is running there |
| Mail / drive / calendar | Through the agent's connectors, if the schedule grants them | Same |
| Push notification | Sometimes — use it when the tool is there; the first line of the final message is the notification of record either way | Usually |
| Browser / social profiles / logged-in sites | No → `needs_local` | Yes (config `local.browser`) |
| Large file uploads | No credential → `needs_local` | Yes (config `local.large_upload`) |
| `gh` CLI | Often not installed (config `tools.cloud_has_gh`) | Usually installed |
| Commits | A session branch; `record --publish` lands them on `main` | `main`, or a worktree branch `record --publish` lands the same way |
