#!/usr/bin/env python3
"""Extract clean text from a viewer-watermarked PDF (e.g. a Carta data-room download).

Data-room viewers stamp every page with rotated text (the viewer's name, email and a timestamp). Plain
text extraction interleaves that stamp with the document, so the output reads as gibberish. The real
text is still in the PDF's text layer, set horizontally. This script keeps only horizontal lines and
drops any line matching a watermark pattern, then writes one Markdown file with the text page by page.

Pages with little or no horizontal text (scans, screenshots, image-only charts) are rendered to PNG so
they can be read visually; the Markdown marks each such page `IMAGE-ONLY -> <png path>`.

Watermark patterns: a viewer timestamp is always stripped; the viewer's own name and email come from the
team config (`../tax-wealth/config/household.yaml`, key `watermarks`, a list of regexes) when it exists,
plus any `--watermark REGEX` given.

Usage (from the skill folder; needs pymupdf — scripts/requirements.txt):
    python3 -I scripts/dewatermark_pdf.py <in.pdf> <out.md> \
        [--png-dir DIR] [--watermark REGEX ...] [--min-chars 40] [--dpi 110]
Exit 0 on success; prints a one-line JSON summary (pages, text pages, image pages, chars).
"""
import argparse
import json
import os
import re
import sys

import pymupdf

DEFAULT_MARKS = [r"\b\w{3} \w{3} +\d{1,2} \d{2}:\d{2}:\d{2} \d{4}\b"]   # the viewer's timestamp
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tax-wealth", "config", "household.yaml")


def config_marks(path=CONFIG):
    """The household's own watermark regexes (config `watermarks`), or [] without a config."""
    if not os.path.exists(path):
        return []
    import yaml
    with open(path, encoding="utf-8") as f:
        return [str(m) for m in ((yaml.safe_load(f) or {}).get("watermarks") or [])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("out")
    ap.add_argument("--png-dir")
    ap.add_argument("--watermark", action="append", default=[])
    ap.add_argument("--min-chars", type=int, default=40)
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args(argv)
    marks = re.compile("|".join(DEFAULT_MARKS + config_marks() + a.watermark))
    doc = pymupdf.open(a.pdf)
    parts, text_pages, image_pages, chars = [], 0, [], 0
    for i, page in enumerate(doc, 1):
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                dx, dy = line["dir"]
                if abs(dy) > 0.05 or dx < 0:          # rotated or upside-down: watermark stamp
                    continue
                t = "".join(s["text"] for s in line["spans"]).rstrip()
                if not t.strip() or marks.search(t):
                    continue
                lines.append(t)
        body = "\n".join(lines).strip()
        if len(body) < a.min_chars:
            note = "IMAGE-ONLY"
            if a.png_dir:
                os.makedirs(a.png_dir, exist_ok=True)
                png = os.path.join(a.png_dir, "%s-p%03d.png" % (os.path.splitext(os.path.basename(a.pdf))[0], i))
                page.get_pixmap(dpi=a.dpi).save(png)
                note += " -> " + png
            image_pages.append(i)
            parts.append("## Page %d\n\n%s\n%s" % (i, note, body))
        else:
            text_pages += 1
            chars += len(body)
            parts.append("## Page %d\n\n%s" % (i, body))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts) + "\n")
    print(json.dumps({"pdf": a.pdf, "pages": doc.page_count, "text_pages": text_pages,
                      "image_pages": image_pages, "chars": chars}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
