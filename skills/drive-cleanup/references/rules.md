# Google Drive Maintenance & Cleanup Rules

## 1. Safety Principles

1. **Trash Before Purge**:
   Never permanently purge files using `files.delete`. Always use `files.update(body={"trashed": True})` to move files into the Google Drive Trash bin. Files remain restorable for 30 days via Google Drive UI or via the `--rollback` script command.

2. **Zero Media Loss Rule**:
   Files with `(case conflict)` in photo/video directories (`Photos/2019`, `Photos/Kids Age 4`, etc.) are frequently the **sole surviving copy** of a photo resulting from macOS/iOS sync naming differences (`IMG_xxxx.JPG` vs `IMG_xxxx.jpg`).
   - If the original base name does not exist: strip the conflict tag directly (`IMG_xxxx.jpg`).
   - If a file with that name exists and MD5 is different: append `_conflict` (`IMG_xxxx_conflict.jpg`).
   - Only trash if the MD5 checksum is 100% identical.

3. **In-Folder Divergent Collisions (Versioning)**:
   Google Drive supports multiple files with the identical filename in the same folder.
   - If MD5 matches: Safe to deduplicate (keep 1 copy, trash duplicate).
   - If MD5 differs: Do **not** delete either! Append ` (version 2)` to eliminate file collision while safeguarding all versions.

4. **Zero-Byte File Verification**:
   Verify that a file is 0 bytes and not an unexported Google Doc format (`application/vnd.google-apps.*`). True 0-byte binaries (`.pdf`, `.docx`, etc.) cannot be rendered and are corrupt.

5. **Dangling Shortcuts**:
   A shortcut is broken when its `shortcutDetails.targetId` returns `404 Not Found` or `trashed: true`. Before trashing the shortcut, verify whether a companion file exists in the directory with a slight typo (e.g., trailing whitespace before extension).
