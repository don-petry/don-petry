---
name: onenote-migration
description: Migrate a personal Microsoft OneNote account (outlook.com, hotmail.com, live.com) into a Git repository of Markdown files through Microsoft Graph — every notebook, section, page and subpage, with attachments, images, YAML front matter and one backdated commit per page. Use when the user wants to export, back up or leave OneNote, move notes to Markdown, Obsidian or GitHub, or resume an interrupted OneNote migration.
license: MIT
---

# OneNote → Markdown migration

`onenote_migrate.py` exports a personal OneNote account to a Git repo of Markdown files. Full
setup, options and output layout are in [README.md](README.md); this file is the runbook an agent
follows.

## Before the first run

1. **Requirements:** Python 3.10+, [Pandoc](https://pandoc.org/installing.html) on PATH, and
   `pip install -r requirements.txt` (run from this folder).
2. **Azure app registration (the user does this, ~5 minutes):** portal.azure.com → App
   registrations → New registration, "Personal Microsoft accounts only", no redirect URI; then API
   permissions → Microsoft Graph → Delegated → `Notes.Read.All` and `User.Read`. No secret needed.
   Ask the user for the **Application (client) ID**.
3. `export ONENOTE_CLIENT_ID=<client id>` (or pass `--client-id`).

## Run

```bash
python onenote_migrate.py --dry-run                 # always first: shows what would be migrated
python onenote_migrate.py --repo ./onenote-vault    # full run; re-run to resume, finished pages are skipped
```

The first run prints a device code. **The user signs in** at microsoft.com/devicelogin with that
code; never type their password for them. Graph rate limits (HTTP 429/503) are retried with
back-off automatically — a long account can take hours, and re-running resumes.

## After

- Show the user the notebook/section/page counts and any pages that failed.
- Publishing the vault anywhere (e.g. a **private** GitHub repo) is the user's call; personal
  notes usually hold personal data, so never push to a public remote.
- Tests: `python -m unittest test_migrate -v`.
