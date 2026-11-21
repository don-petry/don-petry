---
name: drive-cleanup
description: Audit, deduplicate, and repair Google Drive files. Identifies and repairs broken/dangling
  shortcuts, trashes zero-byte corrupted files, resolves case-conflict naming collisions, and safely deduplicates
  byte-for-byte identical files with full JSON undo logging and Google Drive Trash safety. Use whenever
  the user asks to clean up Drive, check for duplicates, fix conflict files, or remove broken files in
  Google Drive.
license: MIT
metadata:
  argument-hint: '[audit | dry-run | execute | rollback | conflicts | zero-byte]'
---

# Google Drive Cleanup & Maintenance (`drive-cleanup`)

This skill audits, cleans up, deduplicates, and repairs Google Drive storage — the whole of My Drive,
or only the top-level folders you list in the config.

## Setup

- **Python 3** with `google-api-python-client`, `google-auth` and `PyYAML` (`pip install -r scripts/requirements.txt`).
- **An rclone Google Drive remote** with the full `drive` scope (`rclone config`). The script reuses
  that remote's OAuth token from `~/.config/rclone/rclone.conf`, so there is no separate sign-in.
- **`config/household.yaml`** — the rclone remote name and, optionally, the folder IDs that bound the
  duplicate and zero-byte checks. If it is missing, copy `config/household.example.yaml` and ask the
  user for the remote name; with no `root_folders` the checks cover every folder.

---

## Quick Execution

The skill provides a CLI engine at `scripts/run.sh` (or `scripts/drive_cleanup.py`), run from the skill folder:

```bash
# 1. Audit only (read-only scan, prints summary without changing anything)
./scripts/run.sh --audit

# 2. Dry-run all maintenance tasks (simulates all fixes, shows what would change)
./scripts/run.sh --all

# 3. Live execution of all maintenance tasks (moves to Trash + logs undo actions)
./scripts/run.sh --all --execute

# 4. Rollback last run (restores trashed files and reverts renames from undo log)
./scripts/run.sh --rollback
```

### Targeted Flags

| Flag | Purpose |
|---|---|
| `--audit` | Read-only scan reporting broken files, duplicates, collisions, and conflicts. |
| `--fix-broken-shortcuts` | Detects shortcuts pointing to deleted (`404`) targets and trashes them. |
| `--trash-zero-byte` | Finds empty 0-byte binaries (`.pdf`, `.docx`) that cannot render and moves them to Trash. |
| `--dedupe-identical` | Removes redundant byte-for-byte duplicate copies in the same directory (keeps 1 copy). |
| `--rename-collisions` | Safely appends `(version 2)` to same-name files in the same folder that have different content. |
| `--normalize-conflicts` | Strips `(case conflict)` from filenames without deleting photos (preserves all media). |
| `--execute` | Performs live changes on Google Drive. If omitted, runs in safe **dry-run** mode. |
| `--rollback` | Reverts all operations recorded in `~/.config/drive_cleanup_undo.json`. |
| `--config PATH` / `--remote NAME` | Use another settings file, or override the rclone remote. |

---

## 5 Maintenance Dimensions

1. **Broken & Dangling Shortcuts**:
   Google Drive shortcuts whose target file was moved or deleted return `404 Not Found`. The skill detects these and cleans them up, checking for companion files that may have minor whitespace typos.
2. **Zero-Byte Corrupt Files**:
   Files that failed during upload or sync often have 0 bytes and fail with "Unable to load document" or "Corrupt file". The skill identifies true zero-byte files (excluding native Google Docs) and trashes them safely.
3. **Conflict-Named Files (`(case conflict)`)**:
   Created by sync discrepancies between case-insensitive OS filesystems (macOS) and case-sensitive cloud storage. The skill normalizes filenames without data loss (see [rules.md](./references/rules.md)).
4. **Exact In-Folder Duplicates**:
   Google Drive allows identically named files in the same directory. When MD5 hashes match, the redundant file is moved to Trash.
5. **Divergent Collisions (Versioning)**:
   When two files in the same folder share a name but differ in content (different MD5), neither is deleted; the second is cleanly renamed to `(version 2)`.

---

## Safety Guarantees

- **Google Drive Trash Only**: No files are permanently purged. Trashed files remain in Google Drive Trash for 30 days and can be restored at any time.
- **Undo Log**: Every single operation records `file_id`, `action`, `old_name`, `new_name`, and timestamp in `~/.config/drive_cleanup_undo.json`.
- **Zero Media Loss**: 100% of photos and videos are preserved.
- **Ask before `--execute`.** Show the dry-run summary and get an explicit yes before any live run.

For detailed rules and design choices, see [rules.md](./references/rules.md).
