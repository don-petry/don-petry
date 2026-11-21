---
title: "Household advisory teams — the shared framework"
created: 2026-11-21
modified: 2026-11-21
---

# Household advisory teams — the shared framework

A household's legal, tax-and-wealth and health questions are worked by **agent teams** that share one
foundation: one state schema, one capacity gate, one escalation table, one verification gate and one way to grow
capabilities. This document is that contract. Each team's skill builds its own playbooks on top of it; nothing here
is specific to one family, one state or one agent harness.

> **These teams are not lawyers, accountants, financial advisers or clinicians, and they do not give legal, tax,
> investment or medical advice.** They help a household understand a matter, find and verify the primary sources,
> catch deadlines, draft for a human's review, and recognize when to hand off. The job ends with a hand-off to a
> licensed professional whenever the escalation table says so. Agents never file, sign, pay or send.

## 1. The teams and who owns what

| Team | Owns | Typical work |
| :--- | :--- | :--- |
| **Legal** | Documents, disputes, courts and rights | Claims and disputes, demand and counter letters, releases, contracts and leases, estate documents (what they say and how they are executed), landlord-tenant, small claims, deadlines and limitation periods |
| **Tax and wealth** | Numbers, filings, titling and money decisions | Returns and notices, estimated tax, dependency, equity compensation, retirement and savings plans, titling and beneficiary inventory, gift and estate tax, entity tax choice |
| **Health** | Coverage and the money of care | Claims and explanations of benefits, appeals within the plan's own process, HSA and FSA reimbursement, who may act for each plan member, open enrollment |

Where a topic touches two teams, one owns it and the other is called for its part:

| Topic | Primary owner | The other team's part |
| :--- | :--- | :--- |
| Estate planning | Legal — what wills, trusts, powers of attorney and advance directives say; execution formalities | Tax and wealth — titling and beneficiary audit, trust funding checklist, estate and gift tax |
| A settlement for someone the household acts for | Legal — the claim, the letters, any court approval | Tax and wealth — tax treatment, kept in **that person's own** project |
| Insurance | Legal — claims and disputes | Tax and wealth — coverage adequacy and policy selection |
| Rental property | Legal — leases, tenant disputes | Tax and wealth — rental income, depreciation |
| A small business or LLC | Legal — contracts, formation documents, the entity in court | Tax and wealth — activity classification, sales tax, entity tax choice |
| Tax controversy | Tax and wealth — notice triage and response preparation | Legal — deadline and escalation rules once it reaches a deficiency notice, lien, levy or court |
| Children and dependency | Legal — custody and guardianship facts (the authority documents) | Tax and wealth — dependency tests, education accounts, a child's own return |
| A job offer or employment agreement | Tax and wealth — cash, equity, benefits lost, scenarios | Legal — agreement terms; non-competes and releases go to an employment lawyer |
| Health coverage | Health — claims, bills, reimbursement, who may act | Tax and wealth — whose expenses the HSA may pay; Legal — disputes that leave the plan's own process (collections, lawsuits, credit reports) |

A matter both teams touch is **one** project with both teams' blocks, not two projects.

## 2. Shared pieces

| Piece | Where (public repo) | What it does |
| :--- | :--- | :--- |
| `source-verifier` persona | `agents/source-verifier.md` | Traces every authority, quotation, figure and date in a draft to a fetched primary source; returns PASS / FAIL / BLOCKED / MANUAL. Never edits the draft |
| `red-team` persona | `agents/red-team.md` | Reads a draft from the other side's seat (opposing party, adjuster, examiner, appeal reviewer, skeptical professional) and returns the strongest objections and missed deadlines. Never edits the draft |
| Verification gate | `tools/verify_sources.py` | The deterministic half of verification: fetch → snapshot with SHA-256 → exact-quote check → PASS / FAIL / BLOCKED, fail-closed. Pluggable source adapters (§6) |
| State schema | each matter's `project.yaml` | One file per matter with the shared `advisory:` block (§3) plus each team's own block |
| Household facts file | one file the household keeps privately | People, relationships, dates of birth, and the **authority documents** (orders, powers of attorney, trusts) the capacity gate reads. One fact finder for every team |
| Escalation table | §5, copied into each household's private notes with real referral contacts | Who a human hand-off goes to |
| Trigger registry | `skills/<team>/reference/triggers.yaml` | How capabilities are added when needed (§8) |

Personas carry only `name` and `description` frontmatter and work when a harness without subagents reads the file
inline. Shared personas are unprefixed; a team's own personas carry the team prefix (`legal-intake`,
`tax-wealth-intake`). **No persona is named Counsel, Attorney, Lawyer, CPA, Advisor or Doctor** — people over-trust
output that wears a professional title. Use role verbs instead.

## 3. The `advisory:` block

Every advisory matter's `project.yaml` carries this block. It is filled by the team's intake persona from
documents, with a source on every field, and asks rather than infers.

| Field | Meaning |
| :--- | :--- |
| `party` | Whose matter it is — a household member's slug or an entity name |
| `capacity` | In what capacity the household member working the matter acts: `self` · `joint` (spouses) · `parent` · `guardian` · `conservator` · `poa_agent` · `trustee` · `none` |
| `authority_doc` | Path or link to the order, power of attorney or trust that grants that capacity; `null` if none |
| `authority_expires` | When the capacity ends (a minor reaching majority, an order's term), or `null` |
| `personal_interest` | The acting member's own stake in someone else's matter (a reimbursement, a fee, an inheritance), or `null`. Non-null puts the matter in CONFLICT handling |
| `forum` | `presuit` · `agency` (insurer, tax authority, benefits agency) · `court` |
| `jurisdiction` | List of codes, e.g. `[XX, federal]` with `XX` a state's postal code. Selects the verification gate's state adapters (§6). Law outside the forum's own state and federal law escalates |
| `represented` | `true` once a lawyer, CPA or EA is retained on the matter |
| `anticipation_of_litigation` | `true` once a dispute is expected; turns on the hold rule — nothing in the matter is deleted, rewritten or force-pushed |
| `forbid` | Strategy strings (a settlement floor, a target figure) that must never appear in an outgoing draft. The gate reads every `forbid:` list in `project.yaml` on every run |
| `gaps` | Evidence for capability triggers: `- {trigger: T-…, date: YYYY-MM-DD, note: …}` |

Team blocks (`legal:`, `tax_wealth:`, `health:`) sit beside it and hold the team's own state: the derived gate
mode, matter type, years in scope, engine-run folders.

## 4. The capacity gate — runs first, every run

Before any research, drafting or capability setup, the owning team evaluates the gate and the escalation list.
Acting for someone else — a minor, a ward under guardianship, a principal under a power of attorney, a trust's
beneficiaries — is decided by the `advisory:` block, **for money as much as for documents**: acting on another
adult's accounts under a power of attorney carries the same conflict and undue-influence risk as drafting their
documents.

First matching row wins. Record the mode in the team block.

| # | Situation | Mode | What the team may do |
| :-- | :--- | :--- | :--- |
| 1 | Any escalation in §5 fires | ESCALATE | Build the hand-off packet; research only to build it |
| 2 | Another state's law or courts (federal law in the home forum is fine) | ESCALATE | Information and the hand-off packet |
| 3 | Another adult signing or changing a power of attorney, advance directive, will, deed, beneficiary designation or gift | LAWYER_PREP | **No drafts.** Explain, and prepare questions for that person's own lawyer |
| 4 | An entity as a party in court | LAWYER_PREP | An entity appears through counsel |
| 5 | `personal_interest` is set on someone else's matter | CONFLICT | Work the other person's interest; the acting member's own claim is kept separate and disclosed in writing; then continue by the next matching row |
| 6 | `authority_expires` within 30 days | TRANSITION | A hand-over plan to the person coming of age, plus the next matching row |
| 7 | Acting for someone, court forum | FIDUCIARY_COURT | Drafts allowed; every filing is marked for human review and a human submits it |
| 8 | Acting for someone, presuit or agency, authority document on file | FIDUCIARY_PRESUIT | Letters and forms signed "as guardian / agent for …" |
| 9 | A household member's own matter (or spouses' joint matter) | SELF / JOINT | Full team; court filings drafted for human review |
| 10 | Anything else — capacity unknown, no authority document, facts missing | INFO_ONLY | Explain and ask the intake persona's open questions; no drafts until a row above matches |

Rules that travel with the gate:

- **A protected person's assets are never moved by an agent** — no transfer, gift, retitling or beneficiary change.
  Decisions about a ward's money belong to whoever the court appointed.
- **A minor's money is that minor's own matter**: their own project, their own `advisory:` block, never pooled with
  the household's.
- **Joint decisions need both spouses.** A team drafts for both and says so; it never records a family decision on
  one spouse's word.

## 5. The escalation table — the pattern

When a row fires, the drive-forward work stops: the team's job becomes preparing the hand-off packet for the
professional, not continuing the task. An unattended run never works past an escalation.

| Situation | Goes to | Raised by |
| :--- | :--- | :--- |
| Lawsuit, subpoena, court date in a case the household did not start, opposing counsel, criminal exposure, appeal, sanctions | A lawyer licensed in the forum's state (the state bar's lawyer referral service) | legal |
| Guardianship, conservatorship, court approval of a minor's settlement, custody, probate | A lawyer in that court's state | legal |
| Wills, trusts, powers of attorney, advance directives — drafting or execution, for anyone | An estate-planning lawyer | legal (tax and wealth's estate audit routes here) |
| A claim **against** a household member | Tender to the household's liability insurers before any response | legal |
| Insurance dispute, bad faith, appraisal, loss-history or credit-report dispute | Legal team first; a lawyer on escalation | legal |
| Coverage adequacy, policy selection | A licensed insurance broker | tax and wealth |
| Return positions, tax authority notices, estimates | A CPA or enrolled agent | tax and wealth |
| An election with a short, unforgiving window (e.g. an 83(b) election after an early exercise) | A CPA or EA files it; the team records the clock the day it starts | tax and wealth |
| Deficiency notice, lien or levy notice, criminal tax exposure, tax court | A tax lawyer | tax and wealth raises; legal's escalation rules apply |
| Employment agreement, separation terms, non-compete, benefits dispute | An employment lawyer (the money side stays with tax and wealth) | whichever sees it first |
| Government-benefit denial with an appeal window | An elder-law lawyer or legal aid | legal (clock) + tax and wealth (income facts) |
| A medical-plan denial worth contesting after the plan's internal appeal | External review; a patient advocate or lawyer | health |
| Collections, a lawsuit or a credit-report entry for a medical bill | Legal team | health raises |
| Whose expenses the HSA may pay (dependency) | Tax and wealth decides | health raises |
| **Any clinical question** | The treating provider — never an agent | health |
| Any clock inside 90 days that has not been verified | The professional for that matter | any team |

A **release, waiver or settlement offer with an expiry** is not automatically an escalation, but it gets a 24-hour
hold before anyone signs, and the red team reads it first.

The household's private copy of this table adds the real referral contacts (bar referral line, broker, CPA,
insurers). The public pattern keeps the roles only.

## 6. Verification: `drafts/` → verify → `outbound/` → a human

Nothing leaves a matter unverified. The flow:

1. **Draft** into the matter's `drafts/` folder. Strategy (floors, targets, reasoning) goes in a separate
   `strategy.md`, never in a draft that leaves; strategy figures also go in `forbid:` so the gate catches a slip.
2. **Gate script** — `python3 tools/verify_sources.py <matter>/drafts/<file>.md`. It fetches every cited source
   fresh, saves the text with URL, date and SHA-256 to `<matter>/authorities/`, appends to
   `authorities/verification-log.jsonl`, and checks every quotation word for word. Anything shaped like a citation
   that no active adapter recognizes FAILs. BLOCKED (outage, quota, empty page) counts as failure. Agents never
   write the snapshots or the log by hand.
3. **`source-verifier`** reads the script's report and checks what the script does not: **figures** (a number
   passes only when it traces to a quoted document or a stamped engine run — a figure the model computed is FAIL)
   and **dates** (a date passes only when it is printed on a source document or comes from a deterministic
   deadline calculation with a trace). Anything checked by hand is MANUAL, which never counts as PASS.
4. **`red-team`** reads the draft from the other side's seat.
5. **Promote** — `python3 tools/verify_sources.py <draft> --promote` copies a fully passing draft to the sibling
   `outbound/` folder. Nothing else ever puts a file there. **An unattended run stops before this step.**
6. **A human** reviews, signs and sends — or submits a court filing. Agents never file, sign or send.

Every report states two limits: **good law is NOT_CHECKED** (there is no free citator — check any case before
relying on it), and figures and dates are outside the script.

### Source adapters

`tools/verify_sources.py --list-adapters` prints what the installed copy can check.

| Adapter | Always on? | Cites it recognizes | Source |
| :--- | :--- | :--- | :--- |
| `federal` | yes | `15 U.S.C. § 1681i`, `26 C.F.R. § 1.152-4` | U.S. Code via Cornell LII; C.F.R. via eCFR (official), LII as fallback |
| `irs` | yes | `IRS Pub. 969`, `Publication 969 (2025)` | irs.gov, current edition — a cited year that does not match the live edition FAILs |
| `cases` | yes | Federal reporters; a state's regional reporter only when that state's adapter is active | CourtListener (`COURTLISTENER_TOKEN` enables quotation checks) |
| `local` | yes | `[src: relative/path]` to a document in the repository (a policy, a letter) | The file itself; PDFs need `pdftotext` |
| State adapters | selected by `advisory.jurisdiction`, `--jurisdiction` or `VERIFY_SOURCES_JURISDICTION` | That state's code sections and regional reporter | One built-in **example** state adapter; add your own |

With no state adapter selected, a bare `§ 12-3-4` FAILs rather than being guessed at. A jurisdiction code with no
adapter is reported, and its citations FAIL as unsupported. To add a state, write a small adapter file (the
interface is in the script's docstring, and its tests include a fictional-state test double) and pass it with
`--adapter-file`.

Each team ships a `reference/verification.md` that names its approved sources, the citation forms it uses and the
exact command the verifier runs.

## 7. Interfaces

1. **Personas.** Dispatch `source-verifier` with `{domain, draft_path, verification_ref}` and `red-team` with
   `{domain, draft_path, adversary}`. Both return a findings table and never edit the draft.
2. **State.** One `project.yaml` per matter: `advisory:` plus one or more team blocks.
3. **Verification.** `reference/verification.md` per team; the gate script for authorities and quotations;
   `source-verifier` for figures and dates under the team's own rules.
4. **Run order, every run.** Gate and escalations → probe capabilities and say what is degraded → check recorded
   gaps and triggers → work.
5. **Records.** A retained professional's communications are stored like everything else: a summary in the
   matter's notes with a link to the full document.

## 8. Capabilities grow by trigger, not by flag

There is no committed "enabled" switch. Each team keeps `reference/triggers.yaml`: the observable signal that a
capability would pay for itself, how to tell **in this session** whether it is present, and how to set it up per
harness. Every run probes what it actually has; git history is the record of what was enabled.

```yaml
- id: T-EXAMPLE
  condition: plain-language description of when the capability pays for itself
  signal: an observable check in the repo (a grep over project.yaml gaps, a file appearing)
  probe: how to tell in THIS session whether the capability is present (a command, an import, a tool name)
  setup: {per-harness: committed config or install step}
  secrets: environment variable names only — never values
  verify: a concrete call that must succeed after setup
  proposed_as: question   # raised to the household as an open question — never self-installed
```

Examples of triggers worth having: an API token that unlocks case-law quotations, a PDF text extractor, a
deadline-calculation engine, a new state adapter the first time a matter in that state arrives.

## 9. Adding a team

1. Write `skills/<team>/SKILL.md` with the gate (§4) and escalation list (§5) at Step 0, and the disclaimer at the
   top: the skill prepares the hand-off to a licensed professional and does not replace one.
2. Add `reference/verification.md` (sources and command) and `reference/triggers.yaml`.
3. Add the team's intake persona to `agents/` (`name` and `description` only; no professional title).
4. Define the team's `project.yaml` block beside `advisory:`; reuse `source-verifier` and `red-team`.
5. Add the team's rows to the ownership table (§1) and the escalation table (§5).
