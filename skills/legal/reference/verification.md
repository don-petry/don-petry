# Legal verification — sources and command

Read by `agents/source-verifier.md` for `domain: legal`. The gate itself is the shared script named in
the legal skill's `config/household.yaml` (`paths.verify_sources`) — `tools/verify_sources.py` in the public repo. Below,
`<gate script>` means that path (its tests: config `paths.verify_sources_tests`).

## Command

```bash
python3 <gate script> <matter>/drafts/<file>.md [--promote]
python3 <gate script> --list-adapters      # what this copy can check
```

State adapters are selected by the matter's `project.yaml` `advisory.jurisdiction` (e.g. `[XX, federal]`), by
`--jurisdiction XX`, or by the `VERIFY_SOURCES_JURISDICTION` environment variable. With no state adapter
selected, a bare `§ 12-3-4` FAILs rather than being guessed at; a state with no adapter FAILs its citations as
unsupported. Load your own state's adapter with `--adapter-file my_state.py` (trigger T-STATE-ADAPTER).

Exit 0 means every authority and quotation passed. The report lists each item; the script writes the snapshots
and `authorities/verification-log.jsonl` itself, and fetches every source fresh on every run (nothing on disk is
trusted as a cache). Strategy text listed under any `forbid:` list in the matter's `project.yaml` (for example
`legal.forbid`) fails the draft if it appears (literal match; `--forbid TEXT` and `--forbid-regex RE` add more for
one run).

Rules the script enforces on quotations: straight or curly double quotes, curly single quotes and `>` blockquotes
are all checked, across hard-wrapped lines; ellipsis segments need at least three words; a bracketed alteration may
replace at most 25 characters; every piece must match on word boundaries. Anything that looks like a citation but
is not in a form below FAILs.

## Approved sources

| Authority | How it is written in a draft | Source the script uses |
|---|---|---|
| U.S. Code | `15 U.S.C. § 1681i` | Cornell LII |
| C.F.R. | `12 C.F.R. § 1026.3` | eCFR (the official edition); Cornell LII if eCFR is down |
| IRS publications | `IRS Pub. 969`, `IRS Pub. 969 (2025)` | irs.gov, current edition — a cited year that does not match the live edition FAILs |
| Federal cases | `Marbury v. Madison, 5 U.S. 137 (1803)` | CourtListener v4 search; name checked against the citation |
| State code | the state's own form, e.g. `Ala. Code § 26-1-1` | the configured jurisdiction's adapter — see `reference/jurisdictions/<code>.md` (Alabama is the example) |
| State cases | regional reporter, e.g. `So. 2d`, `S.E.2d` | CourtListener, only when that state's adapter is active |
| A policy, letter or other document | the quote, then `[src: relative/path.pdf]` in the same paragraph — the path is relative to the draft's folder, must stay inside the repo, and may not point into `drafts/`, `outbound/` or `authorities/` | the local file (PDFs need `pdftotext`) |

Not used: Justia and FindLaw (403 to automated requests); any blog, summary or secondary source.

## What the script cannot do — say so in every report

- **Figures and dates** — `source-verifier` checks them: a date is quoted from a document or comes from the
  deadline calculation (trigger T-CLOCK); a number is traced to its document.
- **Good law** — whether a case was overruled or a statute amended after the snapshot. Always NOT_CHECKED.
- **Quotations from cases** without `COURTLISTENER_TOKEN` — the citation is confirmed, the quote is BLOCKED.
- **State rules of civil procedure, court rules, administrative code** — no adapter unless the jurisdiction notes
  name one. Quote them only with `[src: path]` to a saved copy of the official rule.
- **Law outside the matter's jurisdictions** — FAIL by design; cross-state matters escalate.

## Manual protocol (only when the script cannot run at all)

Fetch the official source above, save it to the matter's `authorities/` folder with URL and date, quote the exact
passage. Status is MANUAL, which never counts as PASS: the draft stays in `drafts/`.
