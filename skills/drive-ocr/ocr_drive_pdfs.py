#!/usr/bin/env python3
"""
Find Google Drive PDFs missing a text layer, OCR them with ocrmypdf, and replace in-place.
"""

import argparse
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Iterator, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]
PAGE_SIZE = 100
OCR_TEXT_MIN_CHARS = 50


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="OCR Google Drive PDFs that are missing a text layer."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="List PDFs needing OCR without downloading, processing, or uploading.",
    )
    p.add_argument(
        "--folder-id",
        help="Scope to a specific Drive folder ID (from the Drive URL).",
    )
    p.add_argument(
        "--file-ids",
        help="Path to a log file from a previous run — reprocesses only the 'ocr_applied' entries, "
             "bypassing Drive discovery and the text-layer check. Use to re-run with new OCR settings.",
    )
    p.add_argument(
        "--log-file",
        help="Path to write the summary log (default: ocr_run_YYYYMMDD_HHMMSS.log).",
    )
    p.add_argument(
        "--credentials",
        default=os.path.join(os.path.dirname(__file__), "credentials.json"),
        help="Path to credentials.json (default: ./credentials.json).",
    )
    p.add_argument(
        "--token",
        default=os.path.join(os.path.dirname(__file__), "token.json"),
        help="Path to token.json cache (default: ./token.json).",
    )
    return p.parse_args()


def authenticate(credentials_path: str, token_path: str):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"credentials.json not found at {credentials_path}\n"
                    "See README.md for Google Cloud setup instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def load_file_ids_from_log(log_path: str) -> list[dict]:
    """Parse a previous run's log and return file metas for all ocr_applied entries."""
    entries = []
    with open(log_path) as f:
        for line in f:
            if line.startswith("ocr_applied"):
                parts = line.split(None, 2)
                if len(parts) == 3:
                    _, file_id, name = parts
                    entries.append({"id": file_id.strip(), "name": name.strip(), "size": "?"})
    return entries


def discover_pdfs(service, folder_id: Optional[str]) -> Iterator[dict]:
    query = "mimeType='application/pdf' and trashed=false"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                pageSize=PAGE_SIZE,
                fields="nextPageToken, files(id, name, size, modifiedTime)",
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        for f in response.get("files", []):
            yield f
        page_token = response.get("nextPageToken")
        if not page_token:
            break


def download_pdf(service, file_id: str, dest_path: str) -> None:
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def has_text_layer(pdf_path: str) -> Optional[bool]:
    """
    Returns True if the PDF has sufficient text, False if it needs OCR,
    None if it's unreadable (e.g. encrypted).
    """
    try:
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None  # unreadable / encrypted
        return len(result.stdout.strip()) >= OCR_TEXT_MIN_CHARS
    except subprocess.TimeoutExpired:
        return True  # assume has text if pdftotext hangs; skip safely


def run_ocr(input_path: str, output_path: str) -> bool:
    try:
        result = subprocess.run(
            [
                "ocrmypdf",
                "--force-ocr",          # re-OCR even if text layer present (required for hocr renderer)
                "--pdf-renderer", "hocr", # produces text selectable in Google Drive viewer
                "--rotate-pages",       # auto-correct page rotation
                "--deskew",             # straighten skewed scans
                "--clean",              # pre-clean image before OCR
                input_path,
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        print("\nERROR: ocrmypdf not found. Run: brew install ocrmypdf")
        raise SystemExit(1)


def upload_pdf(service, file_id: str, pdf_path: str) -> None:
    media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)
    service.files().update(
        fileId=file_id,
        media_body=media,
        supportsAllDrives=True,
    ).execute()


def get_page_count(pdf_path: str) -> Optional[int]:
    """Return number of pages in a PDF using pdfinfo, or None on failure."""
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":")[1].strip())
    except Exception:
        pass
    return None


def validate_ocr_output(input_path: str, output_path: str) -> tuple[bool, str]:
    """
    Validate the OCR'd PDF against the original.
    Returns (ok, reason) where ok=False means the output should not be uploaded.
    """
    if not os.path.exists(output_path):
        return False, "output file does not exist"

    input_size = os.path.getsize(input_path)
    output_size = os.path.getsize(output_path)

    # Output must be at least 50% of input size — catches catastrophic re-encoding
    if input_size > 0 and output_size < input_size * 0.5:
        return False, f"output too small: {output_size} bytes vs input {input_size} bytes"

    # Page count must match
    input_pages = get_page_count(input_path)
    output_pages = get_page_count(output_path)
    if input_pages is not None and output_pages is not None:
        if input_pages != output_pages:
            return False, f"page count mismatch: input {input_pages} pages, output {output_pages} pages"

    # Output must now have a text layer
    try:
        result = subprocess.run(
            ["pdftotext", output_path, "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or len(result.stdout.strip()) < OCR_TEXT_MIN_CHARS:
            return False, "output has no readable text layer after OCR"
    except subprocess.TimeoutExpired:
        pass  # very large file — assume ok if pdftotext hangs

    return True, "ok"


def process_file(service, file_meta: dict, tmpdir: str, dry_run: bool, force: bool = False) -> dict:
    file_id = file_meta["id"]
    name = file_meta["name"]
    result = {"id": file_id, "name": name, "status": "unknown", "error": None}

    input_path = os.path.join(tmpdir, f"{file_id}_input.pdf")
    output_path = os.path.join(tmpdir, f"{file_id}_output.pdf")

    try:
        download_pdf(service, file_id, input_path)

        if not force:
            text_check = has_text_layer(input_path)
            if text_check is True:
                result["status"] = "skipped_has_text"
                return result
            if text_check is None:
                result["status"] = "skipped_unreadable"
                return result

        if dry_run:
            result["status"] = "needs_ocr_dry_run"
            return result

        if not run_ocr(input_path, output_path):
            result["status"] = "ocr_failed"
            return result

        valid, reason = validate_ocr_output(input_path, output_path)
        if not valid:
            result["status"] = "validation_failed"
            result["error"] = reason
            return result

        upload_pdf(service, file_id, output_path)
        result["status"] = "ocr_applied"

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    finally:
        for p in [input_path, output_path]:
            if os.path.exists(p):
                os.remove(p)

    return result


def run_pipeline(service, args: argparse.Namespace) -> None:
    stats = {
        "total": 0,
        "skipped_has_text": 0,
        "skipped_unreadable": 0,
        "needs_ocr": 0,
        "ocr_applied": 0,
        "ocr_failed": 0,
        "validation_failed": 0,
        "errors": 0,
    }
    results = []

    force = bool(args.file_ids)
    mode = " [DRY RUN]" if args.dry_run else ""
    reprocess_note = f" [reprocessing from {os.path.basename(args.file_ids)}]" if args.file_ids else ""
    print(f"Drive OCR{mode}{reprocess_note} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.folder_id:
        print(f"Scoped to folder: {args.folder_id}")
    print()

    if args.file_ids:
        file_list = load_file_ids_from_log(args.file_ids)
        print(f"Loaded {len(file_list)} file(s) from log.")
    else:
        file_list = None  # will use discover_pdfs

    def iter_files():
        if file_list is not None:
            yield from file_list
        else:
            yield from discover_pdfs(service, args.folder_id)

    with tempfile.TemporaryDirectory(prefix="drive_ocr_") as tmpdir:
        for file_meta in iter_files():
            stats["total"] += 1
            size_kb = int(str(file_meta.get("size", 0)).replace("?", "0")) // 1024
            print(
                f"[{stats['total']:4d}] {file_meta['name'][:60]:<60s} ({size_kb:>5d} KB) ... ",
                end="",
                flush=True,
            )

            result = process_file(service, file_meta, tmpdir, args.dry_run, force=force)
            results.append(result)
            print(result["status"])

            key = result["status"]
            if key == "skipped_has_text":
                stats["skipped_has_text"] += 1
            elif key == "skipped_unreadable":
                stats["skipped_unreadable"] += 1
            elif key == "needs_ocr_dry_run":
                stats["needs_ocr"] += 1
            elif key == "ocr_applied":
                stats["ocr_applied"] += 1
            elif key == "ocr_failed":
                stats["ocr_failed"] += 1
            elif key == "validation_failed":
                stats["validation_failed"] += 1
            elif key in ("error", "unknown"):
                stats["errors"] += 1

    write_log(results, stats, args.log_file)
    print_summary(stats, args.dry_run)


def write_log(results: list, stats: dict, log_path: Optional[str]) -> None:
    if log_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(os.path.dirname(__file__), f"ocr_run_{ts}.log")
    with open(log_path, "w") as f:
        f.write(f"Drive OCR Run — {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n")
        for r in results:
            f.write(f"{r['status']:25s}  {r['id']}  {r['name']}\n")
            if r["error"]:
                f.write(f"  ERROR: {r['error']}\n")
        f.write("=" * 80 + "\n")
        for k, v in stats.items():
            f.write(f"  {k}: {v}\n")
    print(f"\nLog written to: {log_path}")


def print_summary(stats: dict, dry_run: bool) -> None:
    print()
    print("=" * 40)
    print("Summary")
    print("=" * 40)
    print(f"  Total PDFs found:    {stats['total']}")
    print(f"  Already have text:   {stats['skipped_has_text']}")
    if stats["skipped_unreadable"]:
        print(f"  Unreadable/encrypted:{stats['skipped_unreadable']}")
    if dry_run:
        print(f"  Need OCR (dry run):  {stats['needs_ocr']}")
    else:
        print(f"  OCR applied:         {stats['ocr_applied']}")
        if stats["ocr_failed"]:
            print(f"  OCR failed:          {stats['ocr_failed']}")
        if stats["validation_failed"]:
            print(f"  Validation failed:   {stats['validation_failed']}")
        if stats["errors"]:
            print(f"  Errors:              {stats['errors']}")
    print("=" * 40)


def main() -> None:
    args = parse_args()
    service = authenticate(args.credentials, args.token)
    run_pipeline(service, args)


if __name__ == "__main__":
    main()
