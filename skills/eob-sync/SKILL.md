---
name: eob-sync
description: 'Sync a household''s health and dental Explanations of Benefits from any insurer, claim by
  claim, and flag every claim that needs a person: denials, coordination-of-benefits holds, records requests,
  out-of-network and balance billing, provider bills above the EOB, aged pending claims, appeal deadlines,
  duplicates, unread EOB notices, prior-authorization changes, missed premiums, expected claims that never
  arrived, and deductible / out-of-pocket / dental-maximum position and unused cleanings before year end.
  Notice emails trigger it; the signed-in member portal is the source; EOB PDFs go to the document store.
  Plans and thresholds are configured; Blue Cross is the worked portal example. Use for "sync the EOBs",
  "check the EOBs", "Blue Cross claims", "did insurance pay", "dental claim", "prior authorization", "am
  I being overbilled", "how much of the deductible is left", "appeal a denial". Read-only: never appeals,
  pays, calls, changes preferences or submits a claim.'
license: MIT
metadata:
  argument-hint: '[check | sync [<plan>] | write]'
---

# EOB sync

Keeps a claim-by-claim record of what the household's health and dental plans processed and surfaces the
claims that need a person. Part of the health team (`skills/health-advocate`), which runs its who-may-act gate
first; this skill only reads, records and drafts.

> **Not medical, legal or tax advice.** The skill reads what the plan already decided, flags what needs a
> person and prepares the next step. Appeals, payments and calls are for the member (or their authorized
> representative) to make.

## Your household (config)

Read `config/household.yaml` (relative to this skill's folder) first. It names who signs in to which portal,
the members who are adults for their own care, the store path, the mailbox the notices reach, where EOB PDFs
go and how they are named, the portal notes for your insurer, and the calendars to cross-check. If it is
missing, copy `config/household.example.yaml`, ask the user for each value, and write it. Until it exists, run
the checker only against the fictional sample (`examples/store/`).

The **store** (config `paths.store`, relative to the repository root) holds the data:

| File | What |
| :--- | :--- |
| `plans.yaml` | Plan facts, members, notice senders, expected claims, thresholds (shape: `examples/store/plans.yaml`) |
| `claims.csv` | One row per claim, from the EOB |
| `notices.csv` | Carrier emails, with a `reviewed` stamp |
| `accumulators.csv` | Deductible / out-of-pocket / annual-max snapshots from the portal |
| `index.md` | Human summary; the checker re-renders the block between `<!-- eob-issues:start -->` and `<!-- eob-issues:end -->` |

Scripts: `scripts/eob_check.py` (tests: `scripts/test_eob_check.py`; needs Python 3.11+ and PyYAML) and
`scripts/bcbs-claims.js` (in-page reader for the Blue Cross claims app — the example; write one for your portal).

## Hard rules

- **Never type a portal password or verification code.** The account holder (config `household.account_holders`)
  signs in; the agent reads once the session is live. For unattended runs, sign in once in the agent's browser
  with "remember me" and let later runs inherit the session.
- **Read only.** Never file an appeal, pay a bill, change communication preferences, send a secure message,
  submit a claim or edit a profile. Drafting an appeal letter or a note to a provider is fine — drafts only, a
  human sends.
- **Never present stale numbers as current.** If the portal could not be read, say so, label every figure with
  its read date, and leave the claim rows untouched; the checker keeps the notices flagged as unread.
- **Never compute an appeal deadline.** `appeal_by` is only what the EOB itself states.
- **PDFs go to the document store, never the repository.** Delete local copies after upload.
- **Adults on the plan** (config `household.adult_children`): their claims are recorded like everyone's, but a
  decision about their care or a dispute in their name is theirs. Run `skills/health-advocate` Step 0 before
  asking a provider or plan anything on their behalf.
- No clinical detail beyond what the claim needs.

## Sources

| Source | What it gives | Reach |
| :--- | :--- | :--- |
| Mailbox (config `mailbox.address`) | The senders in `plans.yaml` `notices` — EOB ready (often masked, no amounts), premium posted, statement ready, prior-auth changes | Any email-search tool; works unattended |
| Member portal (per plan, `plans.yaml` `claim_list_url`) | Claim list, claim detail / EOB, accumulators, prior authorizations, benefit booklet | A browser session the account holder signed in |

A plan whose EOB notices never reach the mailbox has `notices.eob: unknown`; its claims are found only by reading
the portal (`FEED_MISSING`).

## Run

1. **Load config; update the store** (pull the latest if it is in git). Get today's date from the shell in config
   `household.timezone`.
2. **Collect new notices.** Search the mailbox, newest first, since the latest `date` in `notices.csv`, for every
   sender in `plans.yaml` `notices`. Append one row per message: `date`, `kind` (`eob` · `premium_paid` ·
   `statement` · `prior_auth`; map by sender, then by config `notice_subjects`), `plan`, `gmail_id` (the
   message id), `ref` (a masked claim number, if shown), `reviewed` blank.
3. **Check** — `python3 scripts/eob_check.py`. If nothing is unread and no claim is open, skip to step 7.
4. **Open the portal and hand off sign-in.** Open the plan's `claim_list_url`. If it shows a sign-in page, ask the
   account holder to sign in in that browser tab (ticking "remember me"). Confirm by reading the page before going
   on. Unattended: note "<portal> session needed" and skip to step 7.
5. **Read the claims** with the portal reader (config `portal_notes` says how; for Blue Cross, paste
   `scripts/bcbs-claims.js` into the page). Add one row per claim not yet in `claims.csv`:

   | Column | From the EOB |
   | :--- | :--- |
   | `plan`, `claim_id`, `patient`, `provider` | Header. Patient by household name (`plans.yaml` `portal_names` maps truncated portal names) |
   | `network` | `in` / `out` |
   | `service_date`, `processed_date` | ISO dates |
   | `billed`, `allowed`, `plan_paid`, `deductible`, `copay`, `coinsurance`, `not_covered`, `patient_resp` | Totals, plain numbers |
   | `status` | `paid` · `partial` · `denied` · `pending` · `adjusted` |
   | `remarks` | Remark / reason codes and their text, verbatim |
   | `appeal_by` | The deadline the EOB itself states. Never compute one |
   | `provider_billed` | What the provider's own bill asks of us, when known |
   | `reimbursed` | Set by `skills/hsa-fsa-reimburse` (`HSA` · `FSA` · `partial` · `n/a`) |
   | `eob_drive_id` | Document-store file ID of the saved PDF |
   | `resolution` | Blank while open; `<what happened> <date> <who>` closes it |
   | `notes` | Service categories on the claim (PREVENTIVE; DIAGNOSTIC; …) |
   | `cleaning` | Dental only: `covered` if a PREVENTIVE line had an eligible charge, `denied` if every one was $0 eligible, else blank. Orthodontic claims are blank |

   Also read the plan's accumulators page and append a row to `accumulators.csv` per member (or family) with
   `source` = the page name (no such page → sum the EOBs and say so in `source`). For a `prior_auth` notice, read
   the precert page and record member, service, decision and dates in the store's sync log.
6. **Save EOB PDFs** per config `pdfs.policy`, named per `pdfs.name`; upload per `pdfs.upload`, put the file ID in
   `eob_drive_id`, delete the local copy. Then stamp the notices read:
   `python3 scripts/eob_check.py --mark-reviewed <plan> <today>`.
7. **Write** — `python3 scripts/eob_check.py --write` re-renders the issues block in the store's `index.md`. Update
   its summary (one line per plan) and add a sync-log entry.
8. **Act on what it found.** For each ACT issue, do the next step that is ours to do: draft the provider note or
   appeal letter (draft only), propose the clock as a calendar event (shown for approval first), or put the
   question to the account holder. A denial with an appeal date is a clock.
9. **Commit** per config `commit` (run config `paths.mojibake_guard` first if set). Report one line per ACT issue.

## What the checker flags

| Code | Means | Usually |
| :--- | :--- | :--- |
| `EOB_UNREAD` | EOB notices not yet read in the portal (ACT after `stale_days`) | Sign in and read |
| `PRIOR_AUTH` | A prior authorization changed status | Read the precert page |
| `PREMIUM_MISSING` | A month with no premium confirmation, for each plan that sends them | Check the draft — lapse risk |
| `FEED_MISSING` | A plan's EOB emails don't reach the mailbox | Change the notice address in the portal |
| `NOT_MEMBER` | A claim for someone not listed on the plan | Confirm who is on the plan before paying |
| `DENIED` | Plan paid $0 and we owe | Fix and resubmit, or appeal |
| `COB` | Coordination of benefits / other insurance | Answer the questionnaire (config `cob_hint`) |
| `INFO_REQUESTED` | Records, questionnaire, accident or subrogation request | Send it before it denies |
| `OUT_OF_NETWORK` | Out-of-network claims this year, one line per provider | Pay no more than the EOB says |
| `OVERBILLED` | Provider bill > EOB patient responsibility | Pay the EOB amount; ask for a corrected bill |
| `PENDING_AGED` | Pending past `pending_days` | Call member services |
| `APPEAL_CLOCK` | EOB appeal deadline within `appeal_warn_days` | Decide now |
| `DUPLICATE` | Two claims, same patient/provider/date/amount | Make sure only one was paid |
| `HIGH_PATIENT_RESP` | We owe more than `high_patient_resp` | Check line by line before paying |
| `EOB_PDF_MISSING` | This year's owed/denied EOBs with no `eob_drive_id`, one line per plan | Save the PDFs (step 6) |
| `REIMBURSE` | This year's out-of-pocket not marked reimbursed, one line per plan | Run config `paths.reimburse_skill` — it holds claims whose HSA eligibility is unsettled, routes the rest, and sets `reimbursed` |
| `EXPECTED_MISSING` | An expected claim (`plans.yaml`) has not appeared | Ask the provider |
| `ACCUMULATOR` | OOP / annual max (or a deductible of $500+) ≥ `accumulator_warn` (WATCH from October) | Book care before Dec 31, or push dental to January |
| `CLEANINGS_USED` | Every covered cleaning this calendar year is used (ACT if an extra one was ever denied for that member) | Book the next one in January; check the calendar for a visit before then |
| `CLEANING_LEFT` | A covered cleaning is still unused (from October) | Book before Dec 31 |

Thresholds live in `plans.yaml`. Add a code here and in the tests when you add a rule.

## Calendar cross-check

After the checker runs, list the next 90 days on the calendars in config `calendar_check.calendars` for visits
matching `calendar_check.terms`. A visit for a member with `CLEANINGS_USED` will be denied, so say so with the
date. Tell the account holder; never move an appointment yourself.

## Tools this works with

| Need | Works with |
| :--- | :--- |
| Mailbox search | An email MCP server or connector, a Gmail CLI, or the user pasting the notices |
| Portal reading | Any agent browser that can run JavaScript in a signed-in page; otherwise the user reads the EOB aloud or exports it |
| PDF upload | `rclone`, a Drive/OneDrive/Dropbox tool, or a local folder |
| Scheduling a weekly run | cron, GitHub Actions, or your agent's scheduler — run `skills/health-advocate` in `weekly` mode |
