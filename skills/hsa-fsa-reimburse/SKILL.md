---
name: hsa-fsa-reimburse
description: 'A household''s HSA and limited-purpose health FSA "shoebox": plan, package and record reimbursements
  with the saved EOBs as receipts. Holds any claim whose patient''s HSA eligibility is unsettled (the
  tax side decides dependency), routes dental and vision to the FSA while that year''s election has room,
  routes orthodontics to the invoices actually paid, finds ledger or card evidence of out-of-pocket payment,
  builds a submission packet, records what was filed (including claims split between accounts), and clears
  FSA "balance due" substantiation. Reads Alegeus WealthCare portal activity into a register and a Beancount
  ledger. Administrator, account holder and accounts are configured. Part of the health team (health-advocate).
  Use for "reimburse from the HSA", "HSA receipts", "what can we claim", "FSA balance due", "submit the
  FSA claims", "orthodontic FSA", "mark it reimbursed", "HSA shoebox". Never submits, transfers or changes
  an election — the account holder files.'
license: MIT
metadata:
  argument-hint: '[plan [--year Y] | packet --account HSA|FSA | record <claim> --as HSA|FSA|card|n/a |
    status]'
---

# HSA / FSA reimbursement

The household's "shoebox": every out-of-pocket claim on the EOBs, which account can pay it back, and the
proof. Team contract and gate: `skills/health-advocate/SKILL.md` (run its Step 0 first when called on its own).

> **Not tax, medical or legal advice.** The skill applies dated IRS rules and the plan's own documents to the
> household's records and prepares a packet. Whose expenses an HSA may pay is a tax question for whoever
> prepares the household's return (or a CPA/EA); the account holder decides and files.

## Your household (config)

Read `config/household.yaml` (relative to this skill's folder) first. It names the account holder, the
administrator and its portal, the account type codes, the store, project and ledger paths, where packets go,
the orthodontic invoice source, and the Beancount account names. If it is missing, copy
`config/household.example.yaml`, ask the user for each value, and write it. Until it exists, run the scripts
only against the fictional sample (`examples/`).

| What | Where |
| :--- | :--- |
| Claims (input; `reimbursed` column is set here) | `<store>/claims.csv` — written by `skills/eob-sync` |
| Accounts, FSA elections and deadlines, HSA policy, name → project | `<store>/accounts.yaml` (shape: `examples/store/accounts.yaml`) |
| Register — one row per claim and account | `<store>/reimbursements.csv` |
| Who may be reimbursed | each person's `<projects>/<slug>/project.yaml` → `health.hsa_eligible` |
| Administrator activity and plan-year balances | `<admin_store>/activity.csv`, `accounts.csv` |
| Scripts | `scripts/reimburse.py` (tests: `test_reimburse.py`); `scripts/alegeus-activity.js` (in-page reader) and `scripts/alegeus_sync.py` (tests: `test_alegeus_sync.py`). Python 3.11+ and PyYAML |
| Packets | config `paths.packets` |
| Ledger (optional) | config `paths.ledger` (searched for payments) and `paths.admin_ledger` (generated from the administrator) |
| Rules | `skills/health-advocate/reference/rules-2027.md` — `hsa-whose-expenses`, `hsa-divorced-parents`, `hsa-no-annual-withdrawal`, `hsa-records`, `lpfsa-compatible`, `fsa-substantiation`, `fsa-limits-2027` |

Try it: `python3 scripts/reimburse.py --store examples/store --projects examples/projects --today 2026-11-08 plan --year 2026 --detail`.

## Hard rules

- **Eligibility first.** A claim is reimbursable only when its patient's `hsa_eligible.status` is `yes`. The
  script holds everything else. Changing a status needs the tax decision (whoever prepares the return), cited in
  `basis` and `source` ([rule:hsa-whose-expenses] — a non-qualified distribution is taxed and may carry 20%,
  [rule:hsa-nonqualified]).
- **Only what was actually paid out of pocket.** The EOB says what we owed; a ledger match or receipt shows it
  was paid from our own money. A claim the HSA debit card paid is already settled — record it `--as card`.
  Never package one twice.
- **Orthodontics:** reimburse the invoices actually paid (config `orthodontics.invoices`), not the EOB amount.
- **The policy is the household's.** `accounts.yaml` `hsa.policy` (`reimburse_now` / `defer`) is set by the
  household (config `decisions.hsa_policy_question` says where the answer is recorded). Pub 969 sets no deadline
  ([rule:hsa-no-annual-withdrawal]), so with `defer` the register still matters — it is the record years later.
- **Never sign in, submit, transfer, or change an election.** Never type a portal password. The account holder
  files; the agent reads a signed-in session only.

## Run

1. Update the store; get the date from the shell. Run `skills/eob-sync` first if its notices are unread — the
   plan is only as current as `claims.csv`.
2. **Plan:** `python3 scripts/reimburse.py plan --year <Y>` (`--detail` lists every held claim). Buckets: ready
   for HSA, ready for FSA, orthodontic, held for eligibility, held for a missing EOB PDF. "ledger: none" usually
   means the HSA card paid it.
3. **Sync the administrator, then settle what the cards already paid.**
   - Open config `administrator.activity_url` in the agent's browser. If it shows a sign-in page, follow config
     `administrator.sign_in` — the account holder signs in. Unattended runs note "<administrator> session needed"
     and skip to step 4.
   - Paste `scripts/alegeus-activity.js` into the page. Save its JSON to a file, then
     `python3 scripts/alegeus_sync.py merge <that file>`, `alegeus_sync.py ledger` (if `paths.admin_ledger` is
     set), and the ledger check in config `paths.bean_check`. `alegeus_sync.py status` prints balances, open plan
     years, claim deadlines and balance-due items.
   - A portal that is not Alegeus: write a reader that emits the same JSON shape (`captured`, `years`, `accounts`,
     `activity`; see the reader's field list), or record card payments by hand with `record --as card`.
   - `reimburse.py match-card --year <Y>` pairs open claims with HSA/FSA card payments of the exact amount (EOB
     providers are clinicians, card merchants are practices, so the name rarely matches); `--record` records each
     unambiguous one `--as card`. Ambiguous ones (one $50 charge, four $50 claims at the same office) are settled
     by hand or left in the plan.
4. **Packet** for what remains, only if `hsa.policy` is `reimburse_now`:
   `reimburse.py packet --year <Y> --account HSA --out <packets>/hsa-packet-<date>.md` (and `--account FSA`).
   Hand it to the account holder, who files in config `administrator.file_in`.
5. **Record** each claim filed: `reimburse.py record <claim> --as HSA --status submitted`, then `--status paid`
   when the money lands. A claim split between accounts (part from the FSA, the rest from the HSA) is recorded
   per account with `--amount`; the plan and packets carry only the unreimbursed rest, `record` without
   `--amount` takes that rest, and `claims.csv` shows `partial` until the parts add up. If you keep a ledger, post
   the bank side by hand (config `paths.manual_ledger`); the HSA side arrives with the next sync.
6. **FSA balance due** (card charges awaiting proof): upload the EOB or an itemized receipt in the administrator's
   portal ([rule:fsa-substantiation]). These are in `accounts.yaml` `used_outside_register` — never re-claim them.
7. **Commit** per config `commit` (run config `paths.mojibake_guard` first if set). Report the plan's bucket totals
   and what the account holder needs to do.

## Year-end

Each fall, before open enrollment: the FSA's unused room and its claim deadline and carryover
([rule:fsa-limits-2027]) go to `health-benefits-analyst` (`agents/health-benefits-analyst.md`), which sizes the
next year's election from the orthodontic schedule and the dental history.

## Tools this works with

| Need | Works with |
| :--- | :--- |
| Administrator activity | Any agent browser that runs JavaScript in a signed-in Alegeus page; otherwise a CSV export or manual `record` |
| Ledger | Beancount (`bean-check`); optional — without it the register and card activity are the evidence |
| Packet hand-off | The Markdown packet, printed or opened beside the administrator's claim form |
