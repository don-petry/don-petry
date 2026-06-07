#!/usr/bin/env bash
# Convert an HTML file to PDF using headless Google Chrome.
# Reliable on machines without LibreOffice (which is the usual blocker for docx/HTML -> PDF).
#
# Usage: bash html_to_pdf.sh <input.html> <output.pdf>
#
# Notes:
# - Respects @page CSS in the HTML (size/orientation/margins), so set those in the template.
# - Reference local images by relative path from the HTML; they embed fine via file:// .
set -euo pipefail

IN="${1:?usage: html_to_pdf.sh <input.html> <output.pdf>}"
OUT="${2:?usage: html_to_pdf.sh <input.html> <output.pdf>}"

if [[ ! -f "$IN" ]]; then
  echo "Input HTML not found: $IN" >&2
  exit 1
fi

# Resolve an absolute file:// URL so relative image paths resolve correctly.
IN_DIR="$(cd "$(dirname "$IN")" && pwd)"
IN_ABS="$IN_DIR/$(basename "$IN")"

# Locate a Chrome/Chromium binary across common install paths.
CHROME=""
for c in \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Chromium.app/Contents/MacOS/Chromium" \
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
  "$(command -v google-chrome 2>/dev/null || true)" \
  "$(command -v chromium 2>/dev/null || true)" \
  "$(command -v chromium-browser 2>/dev/null || true)" \
  "$(command -v microsoft-edge 2>/dev/null || true)"; do
  if [[ -n "$c" && -x "$c" ]]; then CHROME="$c"; break; fi
done

if [[ -z "$CHROME" ]]; then
  echo "No Chrome/Chromium/Edge binary found. Install Google Chrome, or convert another way." >&2
  exit 1
fi

"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$IN_ABS" 2>/dev/null || \
"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$IN_ABS" 2>/dev/null

if [[ -f "$OUT" ]]; then
  echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
else
  echo "PDF generation failed." >&2
  exit 1
fi
