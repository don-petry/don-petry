# Tax & wealth engines

Deterministic scripts do the math; the model does judgment. Every figure a draft states comes from one of
these, saved as a write-once run file and cited `[run:<id>]` (`reference/verification.md` §2). Paths are
relative to this skill's folder; the household's own inputs live in config `paths.engine_dir`, and
`examples/` holds fictional inputs for each script.

| Script | What it does | Needs | Tests |
| :--- | :--- | :--- | :--- |
| `scripts/runstamp.py` | Run ids (`<prefix>-<hash of engine, version, inputs>`) and write-once run files, shared by every engine | stdlib | through the engines' tests |
| `scripts/compute.py` | PolicyEngine-US wrapper: a household with named cases → one stamped run file. Models wages and payroll, capital gains, dividends, Schedule C, itemized deductions, cash-basis state tax paid, a state 529 deduction, dependent care, and scholarship-granting-organization (SGO) credits — the Alabama Accountability Act credit (example state) and the federal §25F credit. `--smoke` checks the IRS-sourced known answer (the 2026 MFJ standard deduction) | `scripts/requirements.txt` (T-POLICYENGINE) | `test_compute_sgo.py` (engine cases skip without PolicyEngine) |
| `scripts/equity_scenarios.py` | Equity-offer scenarios: after-tax cash over a horizon plus after-tax equity proceeds at a range of exit values, break-even exit values, QSBS / LTCG / ordinary treatment, an optional liquidity grid. Refuses any rate without a `run:` or `src:` source | stdlib | `test_equity_scenarios.py` |
| `scripts/offer_cash.py` | Salaried offers without equity: base, bonus and employer retirement contribution against a "stay" baseline, year one vs a steady year, and the break-even base. Pre-tax only; after-tax needs `compute.py` | stdlib | — |
| `scripts/retirement.py` | Owl planner wrapper: one plan per scenario (last working year per person) and objective (maximum spending, or estate at a spending level); `verify` reproduces Owl's own published example results | `scripts/owl-requirements.txt`, in its own venv (T-OWL) | `test_retirement.py` (skips without Owl) |
| `scripts/ssa_pia.py` | Social Security PIA from a my Social Security earnings record transcribed to JSON, recomputed for each last working year; checks itself against the statement's printed PIA first | PolicyEngine-US parameter files (wage index, bend points) | `test_ssa_pia.py` (skips without PolicyEngine) |

## Install

```bash
python3 -m venv ~/.venvs/tax-wealth && ~/.venvs/tax-wealth/bin/pip install -r scripts/requirements.txt
~/.venvs/tax-wealth/bin/python scripts/compute.py --smoke          # SMOKE OK — policyengine-us <version>

# Owl pins numpy/pandas/scipy differently, so it gets its own venv:
python3 -m venv ~/.venvs/owl && ~/.venvs/owl/bin/pip install -r scripts/owl-requirements.txt
~/.venvs/owl/bin/python scripts/retirement.py verify                # VERIFY OK
```

The household's venv locations are config `engines.venv` and `engines.owl_venv`. Household inputs stay on the
machine; no engine sends them anywhere.

## Inputs

- `compute.py` — `examples/household-2026.example.json`; the full field list is in the script's docstring.
  Per-person fields are `<adult id>.<field>`; tax-unit fields are `tu.<field>`; SGO fields are `sgo.<field>`.
  A state must be in `STATE_OUTPUTS` before a household in it can run — Alabama (`AL`) is the one mapped
  today, as the example; add a state's output variables from PolicyEngine-US's own parameter tree.
- `equity_scenarios.py` — every rate is `{"value": …, "source": "run:<id>" | "src:<rule key>"}`; decision
  assumptions (probability of payout, years to liquidity, discount rate) may carry `assumption:<whose>`.
- `retirement.py` — `examples/retirement-case.example.json`: people, balances by tax treatment, wages and
  retirement contributions (`contrib_today`, and `contrib_<start year>_remaining` for the first year),
  pensions, Social Security (a PIA per last working year from `ssa_pia.py`, or an annual benefit at an age),
  spending, return rates, allocation, events, scenarios and objectives. Its limits (standard deduction only,
  no early-commencement pension reductions, no 72(t)) are in trigger T-OWL; cross-check a year's tax against
  `compute.py` before citing a tax total.
- `ssa_pia.py` — `examples/ssa-statement.example.json`: date of birth, full retirement age, the statement's
  monthly estimates by claim age, and FICA earnings by year.

Tests that need household data read config `engines.retirement_case` and `engines.ssa_statement` when
`config/household.yaml` sets them, and the fictional `examples/` otherwise.
