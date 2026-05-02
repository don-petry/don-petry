---
name: drive-ocr
description: Find Google Drive PDFs missing an OCR text layer, OCR them with ocrmypdf, and replace in-place via the Drive API. Use when the user says "OCR my Drive PDFs", "fix scanned PDFs in Drive", "add text layer to Drive PDFs", or similar. Handles setup checks, dry runs, and full processing runs.
argument-hint: [--dry-run] [--folder-id FOLDER_ID]
user-invocable: true
allowed-tools: Bash, Read, TodoWrite, AskUserQuestion
---

# Drive OCR

Find Google Drive PDFs missing an embedded text layer (e.g. scanned with the Drive scan tool), OCR them with `ocrmypdf`, and replace the originals in-place — preserving file IDs, names, sharing, and folder location.

**Script location:** `skills/drive-ocr/ocr_drive_pdfs.py`  
**Python env:** `skills/drive-ocr/.venv/bin/python3`

---

## Step 1 — Check prerequisites

```bash
cd skills/drive-ocr

# Verify system tools
ocrmypdf --version
pdftotext -v 2>&1 | head -1
pdfinfo -v 2>&1 | head -1

# Verify Python venv and Drive API packages exist
.venv/bin/python3 -c "import googleapiclient; print('OK')"

# Verify credentials exist
ls credentials.json
```

If any check fails:
- **ocrmypdf / pdftotext / pdfinfo missing:** `brew install ocrmypdf poppler`
- **venv missing:** `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- **credentials.json missing:** Guide the user through GCP setup (see `README.md`)

---

## Step 2 — Determine scope

Ask the user (or infer from their message):
- **All PDFs in Drive** → no extra flags
- **Specific folder** → `--folder-id <ID>` (get from Drive URL: `drive.google.com/drive/folders/<ID>`)

If the user isn't sure, default to `--dry-run` first.

---

## Step 3 — Dry run (always do this first for a new full-Drive run)

```bash
cd skills/drive-ocr
.venv/bin/python3 ocr_drive_pdfs.py --dry-run [--folder-id FOLDER_ID]
```

First run opens a browser for OAuth (one-time). After auth, `token.json` is cached.

Dry run makes no Drive API calls beyond discovery — it lists all PDFs but does not download any.

Report the summary to the user:
- Total PDFs found
- Would be OCR'd (count of files discovered)

Get confirmation before proceeding to the full run.

---

## Step 4 — Full run

```bash
cd skills/drive-ocr
.venv/bin/python3 ocr_drive_pdfs.py [--folder-id FOLDER_ID]
```

Run in background for large drives (>100 PDFs needing OCR). Monitor progress by tailing the output.

Expected throughput: ~30–90 seconds per PDF (depending on page count and scan quality).

---

## Step 5 — Report results

After completion, read the log file (`ocr_run_YYYYMMDD_HHMMSS.log`) and report:
- How many PDFs were OCR'd successfully
- Any failures (`ocr_failed` or `error` status) — list the file names
- Confirm the run is idempotent: files with existing text layers will be skipped on re-run
- Note: to reprocess previously OCR'd files with new settings, use `--reprocess-log <previous-log>`

---

## Status codes

| Status | Meaning |
|---|---|
| `skipped_has_text` | Already has OCR — no action taken |
| `skipped_unreadable` | Encrypted or unreadable by pdftotext |
| `needs_ocr_dry_run` | Would be OCR'd (dry-run only) |
| `ocr_applied` | Successfully OCR'd and replaced in Drive |
| `ocr_failed` | ocrmypdf returned an error |
| `validation_failed` | Output failed safety checks — original left untouched |
| `error` | Unexpected error during download/OCR/upload |

### Validation checks (run before every upload)
- **File size ≥ 50% of input** — catches catastrophic re-encoding
- **Page count matches input** — via `pdfinfo`
- **Text layer present** — `pdftotext` must return ≥ 50 chars on output

---

## Common issues

**`403 Google Drive API has not been used`** — Enable Drive API at console.developers.google.com/apis/api/drive.googleapis.com/overview?project=PROJECT_ID

**`FileNotFoundError: credentials.json`** — User needs to complete GCP setup. See `skills/drive-ocr/README.md`.

**Text not selectable in Drive viewer** — This should not occur with `--pdf-renderer hocr`. If it does, re-run with `--reprocess-log` pointing to the previous log to reprocess affected files.

**`ocrmypdf` timeout** — PDF has too many pages. The 5-min timeout is set conservatively; large vocational reports or IEP documents may hit it. Run with `--folder-id` to process in smaller batches.

**HTTP 429 rate limit** — Too many requests. Run scoped to a folder with `--folder-id` to reduce API call volume.

**`validation_failed` — "output has no readable text layer after OCR"** — The PDF is image-only content that Tesseract cannot extract text from (e.g. architectural drawings, design mockups, hand-drawn diagrams, photos saved as PDF). These are not errors — the original is left untouched in Drive. No action needed; these files simply aren't OCR-able.

**`ocr_failed` on the same files across multiple runs** — Likely a corrupted or non-standard PDF structure that ocrmypdf cannot handle. These are persistently unprocessable; leave them as-is.

---

## Real-world results (first full Drive run, ~3,150 PDFs)

- ~92% of PDFs OCR'd successfully on first pass
- ~7% validation failures — all image-only content (site plans, design files, scanned drawings, IDs) — expected and safe to ignore
- ~1% persistent `ocr_failed` — corrupted or non-standard PDFs
- Default sandwich renderer made text searchable but **not selectable** in Drive viewer — fixed by switching to `--pdf-renderer hocr` with `--force-ocr`
- To re-apply new OCR settings to previously processed files, use `--reprocess-log <previous-log>` — bypasses Drive discovery and text-layer check entirely
