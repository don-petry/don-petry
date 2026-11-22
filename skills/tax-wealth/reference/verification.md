# Tax-wealth verification rules

Read by the shared `source-verifier` (`agents/source-verifier.md`) as its `verification_ref` for the
`tax-wealth` domain. Citation and quotation checking is the verifier's job and follows its protocol;
this file adds only what is tax-specific: approved sources, the **numeric rule**, the **stale-law
check**, and the command to run.

## 1. Approved primary sources

| Kind | Source | Notes |
| :--- | :--- | :--- |
| Federal statute | Internal Revenue Code — Cornell LII (`law.cornell.edu/uscode/text/26`) or `uscode.house.gov` | Check the "current through" date against the tax year. The gate script's `federal` adapter checks U.S.C. via LII |
| Federal regulations | 26 CFR — eCFR (`ecfr.gov`, official), with Cornell LII as the fallback when eCFR is unreachable | eCFR shows the as-of date; record it. The gate script's `federal` adapter fetches eCFR first |
| IRS guidance | IRS.gov forms, instructions and publications for the tax year; Internal Revenue Bulletins | Use the edition for the year in question — a prior-year publication is stale. The gate script's `irs` adapter checks "IRS Pub. N" citations against the current edition and the cited year |
| State statute | The home state's official code site, through the gate script's state adapter (config `jurisdiction.home`; Alabama: Code of Alabama Title 40 via ALISON, the example adapter) | Commercial code mirrors often block automation |
| State guidance | The state revenue department (config `jurisdiction.revenue_department`): the individual return booklet, FAQs, notices | No adapter yet — MANUAL (T-VERIFY-TAX-ADAPTERS) |
| Plan rules | The state 529 plan's documents (config `jurisdiction.plan_529`); employer benefit plan documents | Plan rules, not tax law — cite as such |

Secondary sources (practitioner blogs, tax-software help pages, law-firm and CPA articles, the household's
research notes — config `paths.research_notes`) may help **find** a rule. They never verify one.

## 2. Numeric rule — tax-owned

A dollar figure, percentage or computed date in a draft passes only if it carries `[run:<id>]` and
`<runs_dir>/<id>.json` exists with:

```json
{"id": "<id>", "engine": "policyengine-us", "engine_version": "x.y.z",
 "input_sha256": "<hash of the inputs file>", "inputs": "<path>", "run_at": "YYYY-MM-DDTHH:MM:SSZ",
 "outputs": {"<variable>": <value>}}
```

A run file is write-once: the id hashes engine, version and inputs, and the scripts refuse to overwrite
an existing `<id>.json` whose outputs differ (`scripts/runstamp.py`). Engine run 1's
files hash the inputs alone and keep their ids.

and the figure in the draft equals an `outputs` value (or is copied verbatim from a quoted source
document, tagged `[src: path]` for a local file or `[rule:<key>]` for a rules-file entry). Anything
else — mental arithmetic, a rounded restatement, a figure from a model's memory — is **FAIL**. A
threshold or limit stated in law is a *rule*, not a figure: it needs `[rule:<key>]` (§3), not `[run:]`.

## 3. Rules file and stale-law check — tax-owned

Every rule a draft relies on is an entry in `reference/rules-<year>.md`, cited as
`[rule:<key>]`, with URL, the exact quoted text, fetch date, and the date of law it states. The tag is
`[rule:]`, not `[src:]`: the gate script reads `[src: path]` as a local file relative to
the draft, and keeps that meaning for quoting a local document (a W-2, a 1098-T, a plan statement).

Stale-law check — FAIL the item if any is true:

- It is one of the provisions the 2025 reconciliation act (OBBBA) changed — SALT cap, child tax credit,
  standard deduction, charitable deduction rules, 529 qualified expenses, dependent-care limits,
  senior deduction, "Trump accounts", **qualified small business stock (IRC §1202)** — and its source
  was fetched before the tax year it is applied to, or predates the act. For §1202, also check the
  stock's issue date against the act's effective date: the older rules still govern earlier stock.
- It is a state item that depends on federal conformity (529 K-12 withdrawals, a federal-tax deduction,
  dependent definitions, the §1202 exclusion) and its source is federal only. The state's adoption needs a
  state revenue department or state code source of its own (the Alabama example:
  `reference/jurisdictions/AL.md`).
- The publication or form edition is for a different tax year.
- The entry is tagged `unverified` (carried over from research notes without a fetched quote).

Equity compensation adds its own entries, each needed before an equity draft can pass: the 83(b)
window, the ISO first-exercisable limit and its interaction with early exercise, AMT on ISO spread,
and the §1202 company-level tests, tiers and cap.

## 4. Command

The gate script (config `paths.verify_sources`; `tools/verify_sources.py` in the public repo, the shared
gate of the advisory teams) checks **authorities and quotations only**: U.S.C. sections (LII), C.F.R.
sections (eCFR, LII fallback), IRS publications (`irs` adapter), case citations (CourtListener), state code
sections through a state adapter, and local documents cited as `[src: path]`. Run it on every tax draft:

```bash
python3 <gate script> <notes_root>/drafts/<file>.md [--jurisdiction XX] [--authorities DIR] \
    [--forbid TEXT ...] [--forbid-regex RE ...] [--promote]
```

- The state adapter comes from the matter's `project.yaml` `advisory.jurisdiction` (e.g. `[AL, federal]`),
  then `--jurisdiction`, then the environment variable `VERIFY_SOURCES_JURISDICTION`. `--list-adapters`
  shows what this session has; `--adapter-file my_state.py` loads your own.
- `--forbid TEXT` / `--forbid-regex RE` fail the draft if strategy text appears. Every `forbid:` list in the
  matter's `project.yaml` (`tax_wealth.forbid` included) is read automatically on every run.
- `--promote` copies the draft from `drafts/` to `outbound/` on a clean pass. Evidence snapshots and
  the run log go to the matter's `authorities/` folder (override with `--authorities`).

It does **not** check figures, dates, rules-file entries or state revenue department guidance. Those are
checked by `source-verifier` under this file's own rules — §2 (engine `[run:]` provenance), §3
(`[rule:<key>]` entries and the stale-law check), and the deadline calculation for dates — and every such
item is at best **MANUAL** until a state-revenue adapter and a `[run:]` numeric check are added to the gate
script (trigger T-VERIFY-TAX-ADAPTERS; the `irs` adapter is done). A script PASS therefore never promotes a
tax draft that contains a figure, a date or a `[rule:]` citation: those drafts leave `drafts/` only after
`source-verifier` has marked every such item, and the script's `--promote` is run last.

## 5. Red-team seats for this domain

`irs-examiner`, the state examiner (config `jurisdiction.red_team_seat`; `ador-examiner` in the Alabama
example), `skeptical-cpa` — see `SKILL.md` §Working a question.
