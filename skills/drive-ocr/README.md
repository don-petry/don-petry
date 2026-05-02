# Drive OCR

Finds Google Drive PDFs missing an embedded text layer (e.g. scanned with the Drive scan tool), OCRs them with `ocrmypdf`, and replaces the originals in-place — preserving file IDs, names, sharing, and folder location.

## Prerequisites

### System tools
```bash
brew install ocrmypdf   # includes Tesseract, deskew, cleaning tools
```

### Python dependencies
```bash
pip3 install -r requirements.txt
```

## Google Cloud Setup (one-time, ~10 minutes)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project (e.g. "drive-ocr").

2. Enable the **Google Drive API**:
   - APIs & Services → Library → search "Google Drive API" → Enable

3. Configure the OAuth consent screen:
   - APIs & Services → OAuth consent screen
   - User Type: **External**
   - Fill in app name (e.g. "drive-ocr"), your email, and save
   - Under **Test users**, add your Google account email

4. Create OAuth credentials:
   - APIs & Services → Credentials → Create Credentials → **OAuth client ID**
   - Application type: **Desktop app**
   - Download the JSON and save it as `credentials.json` in this directory

## First Run (OAuth authorization)

The first run opens a browser window to authorize the app with your Google account. After you approve, `token.json` is saved and future runs skip the browser step.

```bash
cd scripts/drive-ocr

# Dry run: lists PDFs needing OCR without changing anything
python3 ocr_drive_pdfs.py --dry-run
```

## Usage

```
python3 ocr_drive_pdfs.py [OPTIONS]

Options:
  --dry-run              List PDFs needing OCR, no changes made
  --folder-id FOLDER_ID  Scope to a specific folder (get ID from Drive URL)
  --log-file PATH        Summary log path (default: ocr_run_YYYYMMDD_HHMMSS.log)
  --credentials PATH     Path to credentials.json (default: ./credentials.json)
  --token PATH           Path to token.json cache (default: ./token.json)
```

### How to find a folder ID

Open the folder in Google Drive. The URL looks like:
```
https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        this is the folder ID
```

### Example runs

```bash
# Dry run on a specific folder
python3 ocr_drive_pdfs.py --dry-run --folder-id 1BxiMVs0XRA...

# Process a specific folder
python3 ocr_drive_pdfs.py --folder-id 1BxiMVs0XRA...

# Process all PDFs in Drive
python3 ocr_drive_pdfs.py

# Save log to a specific path
python3 ocr_drive_pdfs.py --log-file ~/Desktop/ocr_results.log
```

## What the script does

For each PDF in Drive (or the specified folder):

1. **Downloads** the PDF to a temp directory
2. **Checks for existing text** using `pdftotext` — skips the file if it already has ≥ 50 characters of text
3. **OCRs** with `ocrmypdf --force-ocr --pdf-renderer hocr --rotate-pages --deskew --clean`
   - `--force-ocr`: re-OCR even if a text layer is present (required for hocr renderer)
   - `--pdf-renderer hocr`: produces text that is selectable in Google Drive's viewer
   - `--rotate-pages`: auto-correct 90/180/270° rotation from phone scanning
   - `--deskew`: straighten slightly tilted scans
   - `--clean`: reduce noise before OCR
4. **Uploads** the OCR'd PDF back to Drive using `files().update()`, replacing the original in-place — same file ID, name, sharing, and folder location
5. **Cleans up** temp files immediately after each PDF

The script is fully idempotent — re-running it skips already-OCR'd files quickly.

## Status codes in output

| Status | Meaning |
|---|---|
| `skipped_has_text` | PDF already has a text layer |
| `skipped_unreadable` | Encrypted or unreadable by pdftotext |
| `needs_ocr_dry_run` | Would be OCR'd (dry-run mode only) |
| `ocr_applied` | Successfully OCR'd and uploaded in-place |
| `ocr_failed` | ocrmypdf returned an error |
| `validation_failed` | OCR output failed safety checks (see below) |
| `error` | Unexpected error during download/OCR/upload |

## OCR output validation

Before uploading, the script validates the OCR'd PDF against the original:

1. **File size** — output must be ≥ 50% of input size (catches catastrophic re-encoding failures)
2. **Page count** — output must have the same number of pages as the input (via `pdfinfo`)
3. **Text layer** — output must now have ≥ 50 characters of extractable text (via `pdftotext`)

If any check fails, the original in Drive is left untouched and the failure is logged with the reason.

## Notes

- **Rate limits**: If you have thousands of PDFs and hit Drive API quota errors (HTTP 429), use `--folder-id` to process in smaller batches.
- **Large files**: Multi-page scanned documents can take 30–90 seconds each. The script has a 5-minute timeout per file.
- **Shared drives**: Included automatically (`includeItemsFromAllDrives=True`).
- **Security**: `credentials.json` and `token.json` contain sensitive OAuth credentials — they are gitignored, do not commit them.
