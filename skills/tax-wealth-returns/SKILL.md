---
name: tax-wealth-returns
description: 'Extract a household''s filed tax returns (federal Form 1040 with schedules, and a mapped
  state return — Alabama Form 40 is the worked example) from the PDFs into structured JSON — every line
  with its page and source token, a key-lines summary, identity checks and cross-checks against the preparer''s
  cover summary — and keep a multi-year table for quick reference and analysis. Deterministic: no figure
  is typed by a model. Use for "extract our tax returns", "pull last year''s return", "what was our AGI
  / taxable income / total tax in <year>", "add the <year> return", "tax history", "compare our returns",
  "did we itemize", "how much did we owe", or when a tax-wealth analysis needs actual filed figures (calibrating
  an engine, a projection, the CPA packet). Part of the tax & wealth team; not tax advice.'
license: MIT
metadata:
  argument-hint: '[<year> | all-pending | summary]'
---

# Tax-Wealth Returns

Part of the tax & wealth team (the `tax-wealth` skill). Turns filed-return PDFs into data that drafts can cite
as `[src:return-<year>-<kind>:<field>]`. A filed return is a primary source for what was reported. It is not a
statement of what the law required, and nothing here is tax advice.

**Config:** the team's `../tax-wealth/config/household.yaml` (see that skill's §Your household). This skill
reads `household.adults`, `paths.returns_dir`, `returns.inventory`, `returns.link_template`,
`jurisdiction.return_kind` and `engines.venv`. Paths below are relative to this skill's folder unless they
name a config key.

| What | Where |
| :--- | :--- |
| Extracted data | `<returns_dir>/<year>/{federal,<state kind>}.json` |
| Multi-year table and `summary.json` | `<returns_dir>/` (`index.md`) |
| Inventory of return PDFs in your document store | config `returns.inventory` |
| Line maps (summary field → form:page:line, per year) | `reference/line-maps.json` |
| Scripts | `scripts/decode_drive_download.py`, `scripts/extract_return.py`, `scripts/summarize_returns.py` (+ `scripts/test_extract_return.py`); needs `scripts/requirements.txt` |

## Rules

- **PDFs stay in your document store** (a cloud drive, a NAS). Download to a scratch folder and delete when
  done; commit only the JSON.
- **No hand-typed figures.** Every value comes from `extract_return.py` reading the PDF's text layer. If a line
  cannot be read, it stays `null` and is listed in `summary_missing`. Never fill it in from memory or from
  reading the page yourself. `null` means "blank on the form **or** not read". When a null is a known
  extraction gap rather than a blank line, say why in the file's `summary_notes`; the table then shows `n/e`.
- **A year's line map is added only after its extraction passes the checks.** Line numbers move between form
  editions: in 2023–2024 lines 12–15 are on page 1 of the 1040, and in 2025 AGI is line 11a and deductions are
  line 12e. Never copy a map to a new year without re-running the checks.
- **Amended returns supersede.** Extract the amended return too and note which one the figures come from.
- **Only the household adults' own returns** (config `household.adults`, `advisory: joint` or `self`). A
  child's or someone else's return found in the store is marked `not-ours` in the inventory and is not
  extracted into this folder — a minor's return is that minor's own project.
- **A new state** needs its page classifiers (`AL_PAGES` is the example), identities and line map before
  `--kind <state>` works; until then extract the federal return only.

## Run

1. **Find** the return in the inventory. For a new year, search the document store for PDFs titled with
   "Form 1040", "Tax Return" or "Return - Federal/<state>" and add rows.
2. **Download** it. A document-store tool that returns the file as base64 inside JSON
   (`{"content", "title", "mimeType"}`) — when the result is too large for the conversation the harness saves
   it to a file — becomes a PDF with:
   `python3 scripts/decode_drive_download.py <saved result> <scratch>/<year>.pdf`
3. **Extract** in the tax-wealth venv (config `engines.venv`):
   `python scripts/extract_return.py <scratch>/<year>.pdf --year <year> --kind federal --drive-id <id> --link-template "<config returns.link_template>" --title "<title>" --out <returns_dir>/<year>/federal.json`
   Then run it again with `--kind <config jurisdiction.return_kind>` on the same PDF if it holds both returns.
   The extractor splits sections itself.
4. **Map a new year.** If `summary_missing` is long or a check is SKIPPED or GAP because a field is null, add
   or fix that year's map in `reference/line-maps.json` from the extracted `forms` block. After a map change,
   `python3 scripts/extract_return.py --recheck <returns_dir>/<year>/*.json` recomputes the summary and checks
   from the committed `forms` block without the PDF. The extractor exits non-zero on any FAIL or GAP, and
   when no check PASSes (an empty extraction).
   - **FAIL:** an identity does not hold on lines that were all read. The map or a pairing is wrong. Never
     commit a FAIL.
   - **GAP:** an identity does not hold, or a cover figure has no return value, and a null line is involved.
     A line was probably not read. Commit a GAP only with the reason in `summary_notes` and a follow-up in
     `<returns_dir>/index.md`.
5. **Summarize:** `python3 scripts/summarize_returns.py --root <returns_dir>` refreshes `summary.json` and the
   table in `<returns_dir>/index.md`.
6. **Update the inventory** row to `extracted`, delete the scratch PDF, then commit (team config
   `commit_checks`, `commit_rule`).

## What the checks prove, and what they don't

They prove two things. First, the extraction matches the preparer's cover summary: AGI, taxable income, total
tax, payments, refund, and payment due plus penalty. Second, these identities hold between the extracted
lines. A blank line inside an identity counts as zero.

- **Federal:** total income, AGI, total deductions, taxable income, tax after credits, total tax, total
  payments, amount owed less the penalty, overpaid, and refund disposition (34 = 35a + 36).
- **Alabama (the state example):** total income, AGI, total deductions, taxable income, total tax (18 + 19;
  line 20 is not mapped), amount owed, overpaid, and refund disposition (32 = 33 + 34 + 35).

They do not check every line. Lines outside these identities, such as qualified dividends, the Schedule B
detail and the Alabama payment lines 24–26, are read but not cross-checked. The checks also do not prove the
return was right. Positions on a filed return are the preparer's, and questions about them go to a CPA or EA.
