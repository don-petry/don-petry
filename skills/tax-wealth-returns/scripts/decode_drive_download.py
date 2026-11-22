#!/usr/bin/env python3
"""Turn a Drive download result into a PDF on disk (skill: tax-wealth-returns).

Drive connectors return file content as base64 inside JSON: {"content": ..., "title": ..., "mimeType": ...}.
When the result is too large for the conversation, the harness saves that JSON to a file — pass its path.

Usage (from the skill folder): python3 scripts/decode_drive_download.py <result.json> <out.pdf>
PDFs go to a scratch folder, never into the repo: returns stay in your document store; only extracted data is committed.
"""
import base64
import json
import sys

if len(sys.argv) != 3:
    sys.exit(__doc__)
with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)
data = base64.b64decode(d["content"])
if not data.startswith(b"%PDF"):
    sys.exit("not a PDF: %s" % d.get("mimeType"))
with open(sys.argv[2], "wb") as f:
    f.write(data)
print("%s -> %s (%d bytes)" % (d.get("title"), sys.argv[2], len(data)))
