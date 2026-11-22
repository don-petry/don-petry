# `routine <id>` — scheduled runs

A scheduled run starts a fresh agent session on a cron, with the household machine off, and
invokes `run <id>`. Any scheduler works: cron or systemd on a home server, a GitHub Actions
schedule, or your agent's own hosted scheduler. Config `routine` says which one this household
uses (`scheduler_notes`) and what a run must carry.

## Source of truth

`<routine.dir>/<id>.md` in this skill's folder (default `routines/<id>.md`): frontmatter holds
`trigger_id`, `trigger_name` and `cron`; the body is the prompt. `pm.py routine <id>` prints exactly
what should be deployed. The project's own `trigger_id` and `cadence.cron` must say the same — the
tests check. These files are deployment details of one household; keep them with your notes.

```markdown
---
trigger_id: null            # the scheduler's id for this job, once it exists
trigger_name: Kitchen remodel — project manager
cron: "CRON_TZ=America/New_York 45 11 * * 1-5"
---
Run the project-manager skill: `run kitchen-remodel`. This run is unattended: no human is watching.
```

**Keep the prompt thin.** It names the project by id and says the run is unattended. Paths, the
definition of quiet, how to record: all of that is engine behavior and lives in SKILL.md. Prompts
that carried a hard-coded path kept it for ten days after the folders were renamed, and prompts that
told the run to "reply with one line and stop" while SKILL.md told it to log and commit made some
quiet runs record and some not.

## Deploy

1. Edit `<routine.dir>/<id>.md` and the project's `trigger_id` / `cadence.cron`; commit and publish
   **first** — the scheduled run uses whatever is on `origin/main`.
2. Create or update the job in your scheduler with the name, the cron and the prompt from
   `pm.py routine <id>`. The job must give the session:
   - a checkout of the notes repo (config `routine.repo`) — without it a run tries to clone by hand
     and stalls;
   - mail, drive and calendar access (config `routine.connectors`) — without them a run reads
     nothing;
   - mail tools limited to **read + draft** — no send, reply, forward, trash or label tools. An
     **empty** allowlist often means *everything is allowed*;
   - a way to notify a human (push, email to self, a chat message).
3. **Read it back and check it — every time.** If your scheduler can export the job as JSON
   (`id`, `cron_expression`, `name`, `job_config`, `mcp_connections`, `notifications`), save it and
   run `pm.py routine <id> --deployed <file>`: it compares the cron, name and prompt, and checks the
   git source, the connectors, the mail allowlist and notifications. Otherwise check the four items
   in step 2 by hand.
4. If the session cannot set connectors or the source, say so plainly, put it in `needs_local`, and
   **do not let the job fire before it is fixed**: a run with no mail tools reports "could not read",
   but it still spends a run to say it.
5. Fire it once by hand, then read its log: the checkout worked, no permission errors, `pm.py record`
   printed `"published": true`, zero send calls.

### Sample: GitHub Actions

A schedule that starts an agent CLI in the notes repo. Replace the agent step with your harness's
non-interactive command; give it read + draft mail access through whatever connector it uses.

```yaml
name: project-manager kitchen-remodel
on:
  schedule:
    - cron: "45 16 * * 1-5"   # Actions cron is UTC and ignores CRON_TZ: 11:45 New York in winter
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    permissions: {contents: write}
    steps:
      - uses: actions/checkout@v4
      - run: pip install pyyaml
      - name: Run the project manager
        run: your-agent --non-interactive "Run the project-manager skill: run kitchen-remodel. Unattended."
```

On cron, the equivalent is one line: `45 11 * * 1-5 cd ~/notes && your-agent --non-interactive "…"`.

## Schedule

- **Write the cron with a zone where the scheduler supports it:** `CRON_TZ=America/New_York 45 11 * * 1-5`
  follows DST, so there is nothing to change in November or March. A bare cron is often UTC; then a
  dated reminder is needed at each change-over. (`pm.py health` understands `CRON_TZ=`.)
- **Stay clear of any usage-limit reset.** A job that fires in the hours before the agent account's
  limit resets can start with nothing left and die in one second — logged as a success. Note the
  reset in config `routine.scheduler_notes` and fire after it.
- Stagger jobs that fire the same morning by 15–20 minutes; they publish to the same branch.

## Checking on scheduled runs

- `pm.py health` — which projects' last scheduled run never recorded. Every run prints it, so a
  job that died is reported by the next one that didn't.
- Your scheduler's run list may only show fires that started a session. A run that hit a usage
  limit may show as an error in its log, or not at all.
- `pm.py list` — every project, its trigger, schedule and last run.
