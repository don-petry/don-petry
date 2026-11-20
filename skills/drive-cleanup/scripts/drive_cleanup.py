#!/usr/bin/env python3
"""
Drive Cleanup & Deduplication Engine
====================================
Comprehensive maintenance and repair for Google Drive:
1. Dangling / Broken Shortcuts (points to 404 targets).
2. Zero-byte corrupt files (unreadable/empty).
3. Conflict-named files ('(case conflict)' / '(Case Conflict)').
4. Exact byte-for-byte in-folder duplicates (safe dedupe).
5. Same-folder name collisions with divergent content (safe versioning).

Safety Guarantees:
- Uses Google Drive Trash (soft-delete, 30-day recovery) rather than permanent purge.
- Default mode is always safe inspection/audit or --dry-run.
- Logs every operation to ~/.config/drive_cleanup_undo.json for instant --rollback.
- Never deletes media conflict files if content differs or if original is missing.
"""

import os
import re
import json
import logging
import argparse
from datetime import datetime
from collections import defaultdict
import configparser
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

UNDO_LOG = os.path.expanduser("~/.config/drive_cleanup_undo.json")

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "household.yaml")

# Folder IDs that bound the duplicate and zero-byte checks (config `root_folders`). Empty means
# every folder in My Drive. Filled in main() from the config.
CANONICAL_DOMAIN_IDS = {}


def load_config(path=CONFIG):
    """Read config/household.yaml (see household.example.yaml). Missing file -> defaults."""
    if not os.path.exists(path):
        return {}
    import yaml  # PyYAML
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}

def get_drive_service(remote_name="gdrive"):
    """Load credentials from rclone.conf and initialize Google Drive API v3 client."""
    rclone_path = os.path.expanduser("~/.config/rclone/rclone.conf")
    if not os.path.exists(rclone_path):
        raise FileNotFoundError(f"rclone config not found at {rclone_path}")
        
    cp = configparser.ConfigParser()
    cp.read(rclone_path)
    if not cp.has_section(remote_name):
        raise ValueError(f"Remote '{remote_name}' not found in {rclone_path}")
        
    token_str = cp.get(remote_name, "token")
    token_data = json.loads(token_str)
    client_id = cp.get(remote_name, "client_id", fallback="") or token_data.get("client_id")
    client_secret = cp.get(remote_name, "client_secret", fallback="") or token_data.get("client_secret")
    
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    return build("drive", "v3", credentials=creds)

def trash_file(service, file_id, file_name, dry_run=True, undo_log=None):
    """Move file to Google Drive Trash."""
    logging.info(f"[{'DRY-RUN' if dry_run else 'EXECUTE'}] Trashing: {file_name} (ID: {file_id})")
    if not dry_run:
        try:
            service.files().update(fileId=file_id, body={"trashed": True}, supportsAllDrives=True).execute()
            if undo_log is not None:
                undo_log.append({
                    "action": "trash",
                    "file_id": file_id,
                    "file_name": file_name,
                    "timestamp": datetime.utcnow().isoformat()
                })
        except HttpError as e:
            if "insufficientFilePermissions" in str(e):
                logging.warning(f"Permission denied (external read-only file): {file_name} ({file_id})")
            else:
                logging.error(f"Error trashing {file_name} ({file_id}): {e}")
        except HttpError as e:
            logging.error(f"Unexpected error trashing {file_name} ({file_id}): {e}")

def rename_file(service, file_id, old_name, new_name, dry_run=True, undo_log=None):
    """Rename a file in Google Drive."""
    logging.info(f"[{'DRY-RUN' if dry_run else 'EXECUTE'}] Renaming: '{old_name}' -> '{new_name}' (ID: {file_id})")
    if not dry_run:
        try:
            service.files().update(fileId=file_id, body={"name": new_name}, supportsAllDrives=True).execute()
            if undo_log is not None:
                undo_log.append({
                    "action": "rename",
                    "file_id": file_id,
                    "old_name": old_name,
                    "new_name": new_name,
                    "timestamp": datetime.utcnow().isoformat()
                })
        except HttpError as e:
            logging.error(f"Error renaming {old_name} ({file_id}) to {new_name}: {e}")

def get_all_canonical_folders(service):
    """Build a mapping of folder IDs to metadata for all folders under canonical domains."""
    logging.info("Indexing folder hierarchy...")
    folders = {}
    page_token = None
    while True:
        res = service.files().list(
            q="mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="nextPageToken, files(id, name, parents)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        for f in res.get("files", []):
            folders[f["id"]] = f
        page_token = res.get("nextPageToken")
        if not page_token:
            break
            
    if not CANONICAL_DOMAIN_IDS:
        # No roots configured: every folder is in scope, plus My Drive's root itself.
        root_id = service.files().get(fileId="root", fields="id").execute()["id"]
        return folders, set(folders) | {root_id}

    canonical_folder_ids = set(CANONICAL_DOMAIN_IDS.values())
    changed = True
    while changed:
        changed = False
        for fid, fmeta in folders.items():
            if fid not in canonical_folder_ids:
                parents = fmeta.get("parents", [])
                if any(p in canonical_folder_ids for p in parents):
                    canonical_folder_ids.add(fid)
                    changed = True
                    
    return folders, canonical_folder_ids

def audit_drive(service):
    """Perform a comprehensive audit of Google Drive and return structured findings."""
    logging.info("Starting comprehensive Drive audit...")
    folders, canonical_folder_ids = get_all_canonical_folders(service)
    
    findings = {
        "dangling_shortcuts": [],
        "zero_byte_files": [],
        "conflict_files": [],
        "same_folder_dupes": [],
        "same_folder_collisions": []
    }
    
    # 1. Audit shortcuts
    logging.info("Checking shortcuts for broken links...")
    shortcuts = []
    page_token = None
    while True:
        res = service.files().list(
            q="mimeType = 'application/vnd.google-apps.shortcut' and trashed = false",
            fields="nextPageToken, files(id, name, parents, shortcutDetails)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        shortcuts.extend(res.get("files", []))
        page_token = res.get("nextPageToken")
        if not page_token:
            break
            
    for sc in shortcuts:
        target_id = sc.get("shortcutDetails", {}).get("targetId")
        if not target_id:
            findings["dangling_shortcuts"].append(sc)
        else:
            try:
                target = service.files().get(fileId=target_id, fields="id, name, trashed", supportsAllDrives=True).execute()
                if target.get("trashed"):
                    findings["dangling_shortcuts"].append(sc)
            except HttpError:
                findings["dangling_shortcuts"].append(sc)

    # 2. Audit conflict files
    logging.info("Scanning for unhandled conflict-named files...")
    page_token = None
    while True:
        res = service.files().list(
            q="(name contains 'case conflict' or name contains 'Case Conflict' or name contains 'conflicted copy' or name contains 'conflict copy') and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, size, md5Checksum, parents)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        findings["conflict_files"].extend(res.get("files", []))
        page_token = res.get("nextPageToken")
        if not page_token:
            break

    # 3. Audit documents in canonical domains for zero-byte & duplicates
    logging.info("Scanning files in Canonical Domains...")
    doc_mimes = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain"
    ]
    mime_query = " or ".join([f"mimeType = '{m}'" for m in doc_mimes])
    q = f"({mime_query}) and trashed = false"
    
    files = []
    page_token = None
    while True:
        res = service.files().list(
            q=q,
            fields="nextPageToken, files(id, name, mimeType, size, md5Checksum, parents, modifiedTime)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files.extend(res.get("files", []))
        page_token = res.get("nextPageToken")
        if not page_token:
            break
            
    domain_files = [f for f in files if any(p in canonical_folder_ids for p in f.get("parents", []))]
    
    # Check zero-byte
    for f in domain_files:
        if f.get("size") == "0" or f.get("size") == 0:
            findings["zero_byte_files"].append(f)

    # Check same-folder duplicates & collisions
    by_folder_name = defaultdict(list)
    for f in domain_files:
        for p in f.get("parents", []):
            if p in canonical_folder_ids:
                by_folder_name[(p, f["name"])].append(f)
                
    for (pid, name), flist in by_folder_name.items():
        if len(flist) > 1:
            hashes = set(f.get("md5Checksum") for f in flist)
            folder_name = folders.get(pid, {}).get("name", pid)
            entry = {"folder_id": pid, "folder_name": folder_name, "name": name, "files": flist}
            if len(hashes) == 1:
                findings["same_folder_dupes"].append(entry)
            else:
                findings["same_folder_collisions"].append(entry)

    return findings

def execute_rollback(service):
    """Revert changes logged in UNDO_LOG."""
    if not os.path.exists(UNDO_LOG):
        logging.error(f"Undo log not found at {UNDO_LOG}")
        return
        
    with open(UNDO_LOG) as f:
        log_entries = json.load(f)
        
    logging.info(f"Reverting {len(log_entries)} operations from {UNDO_LOG}...")
    for op in reversed(log_entries):
        fid = op["file_id"]
        action = op["action"]
        try:
            if action == "trash":
                logging.info(f"Restoring file from Trash: {op['file_name']} ({fid})")
                service.files().update(fileId=fid, body={"trashed": False}, supportsAllDrives=True).execute()
            elif action == "rename":
                logging.info(f"Reverting rename: '{op['new_name']}' -> '{op['old_name']}' ({fid})")
                service.files().update(fileId=fid, body={"name": op["old_name"]}, supportsAllDrives=True).execute()
        except (HttpError, KeyError, TypeError) as e:
            logging.error(f"Error reverting operation on {fid}: {e}")
            
    logging.info("Rollback complete.")

def main():
    parser = argparse.ArgumentParser(description="Google Drive Cleanup & Maintenance Engine")
    parser.add_argument("--audit", action="store_true", help="Audit Drive and print report (read-only)")
    parser.add_argument("--execute", action="store_true", help="Apply fixes live (defaults to dry-run)")
    parser.add_argument("--rollback", action="store_true", help="Revert previous run using undo log")
    parser.add_argument("--fix-broken-shortcuts", action="store_true", help="Trash broken shortcuts")
    parser.add_argument("--trash-zero-byte", action="store_true", help="Trash 0-byte corrupt files")
    parser.add_argument("--dedupe-identical", action="store_true", help="Dedupe exact byte identical files in same folder")
    parser.add_argument("--rename-collisions", action="store_true", help="Version same-folder collisions with divergent content")
    parser.add_argument("--normalize-conflicts", action="store_true", help="Normalize (case conflict) file names")
    parser.add_argument("--all", action="store_true", help="Run all maintenance tasks")
    parser.add_argument("--config", default=CONFIG, help="Settings file (default: ../config/household.yaml)")
    parser.add_argument("--remote", help="rclone remote name (overrides the config's rclone_remote)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    CANONICAL_DOMAIN_IDS.update(cfg.get("root_folders") or {})
    service = get_drive_service(args.remote or cfg.get("rclone_remote") or "gdrive")

    if args.rollback:
        execute_rollback(service)
        return

    findings = audit_drive(service)
    
    print("\n" + "="*50)
    print("GOOGLE DRIVE AUDIT SUMMARY")
    print("="*50)
    print(f"Broken / Dangling Shortcuts:            {len(findings['dangling_shortcuts'])}")
    print(f"Zero-Byte Corrupted Files:             {len(findings['zero_byte_files'])}")
    print(f"Active Conflict-Named Files:           {len(findings['conflict_files'])}")
    print(f"Exact Same-Folder Duplicate Groups:    {len(findings['same_folder_dupes'])}")
    print(f"Same-Folder Collision Groups:          {len(findings['same_folder_collisions'])}")
    print("="*50 + "\n")

    if args.audit or (not args.all and not any([
        args.fix_broken_shortcuts, args.trash_zero_byte,
        args.dedupe_identical, args.rename_collisions,
        args.normalize_conflicts
    ])):
        print("Audit mode completed. To apply fixes, specify remediation flags with --execute (or dry-run by default).")
        return

    dry_run = not args.execute
    undo_log = []

    # 1. Broken shortcuts
    if args.all or args.fix_broken_shortcuts:
        for sc in findings["dangling_shortcuts"]:
            trash_file(service, sc["id"], f"Shortcut '{sc['name']}' (dangling target)", dry_run, undo_log)

    # 2. Zero-byte files
    if args.all or args.trash_zero_byte:
        for z in findings["zero_byte_files"]:
            trash_file(service, z["id"], f"Zero-byte file '{z['name']}'", dry_run, undo_log)

    # 3. Exact duplicates in same folder
    if args.all or args.dedupe_identical:
        for group in findings["same_folder_dupes"]:
            files = group["files"]
            for redundant in files[1:]:
                trash_file(service, redundant["id"], f"Redundant copy of '{group['name']}' in {group['folder_name']}", dry_run, undo_log)

    # 4. Same-folder collisions
    if args.all or args.rename_collisions:
        for group in findings["same_folder_collisions"]:
            files = group["files"]
            base, ext = os.path.splitext(group["name"])
            for idx, f in enumerate(files[1:], start=2):
                new_name = f"{base} (version {idx}){ext}"
                rename_file(service, f["id"], group["name"], new_name, dry_run, undo_log)

    # 5. Normalize conflict files
    if args.all or args.normalize_conflicts:
        # Pre-cache directory file listings for conflict file parent directories
        parent_ids = list(set([f.get("parents", [None])[0] for f in findings["conflict_files"] if f.get("parents")]))
        folder_files = defaultdict(dict)
        for pid in parent_ids:
            tok = None
            while True:
                r = service.files().list(
                    q=f"'{pid}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, size, md5Checksum)",
                    pageSize=1000,
                    pageToken=tok
                ).execute()
                for f in r.get("files", []):
                    folder_files[pid][f["name"].lower()] = f
                tok = r.get("nextPageToken")
                if not tok:
                    break

        for f in findings["conflict_files"]:
            fid = f["id"]
            old_name = f["name"]
            pid = f.get("parents", [None])[0]
            clean_name = re.sub(r"\s*\((case )?conflict\)", "", old_name, flags=re.IGNORECASE).strip()
            base, ext = os.path.splitext(clean_name)
            
            existing = folder_files.get(pid, {}).get(clean_name.lower())
            if not existing or existing["id"] == fid:
                rename_file(service, fid, old_name, clean_name, dry_run, undo_log)
                folder_files[pid][clean_name.lower()] = f
            else:
                if existing.get("md5Checksum") and existing.get("md5Checksum") == f.get("md5Checksum"):
                    trash_file(service, fid, f"{old_name} (duplicate of {existing['name']})", dry_run, undo_log)
                else:
                    new_conflict_name = f"{base}_conflict{ext}"
                    rename_file(service, fid, old_name, new_conflict_name, dry_run, undo_log)

    if not dry_run and undo_log:
        existing = []
        if os.path.exists(UNDO_LOG):
            try:
                with open(UNDO_LOG) as uf:
                    existing = json.load(uf)
            except (OSError, ValueError):
                existing = []
        existing.extend(undo_log)
        with open(UNDO_LOG, "w") as uf:
            json.dump(existing, uf, indent=2)
        logging.info(f"Successfully recorded {len(undo_log)} actions to {UNDO_LOG}")

if __name__ == "__main__":
    main()
