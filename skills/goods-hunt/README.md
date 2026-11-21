# Goods Hunt

A domain-agnostic engine for finding, scoring, qualifying, and acquiring
high-value used goods — the generalization of `skills/car-hunt`. The **engine**
owns the pipeline; a **domain pack** owns the knowledge. Value is ranked by
**CPRU** (Cost Per Remaining Useful-life Unit), the generalization of car-hunt's
CPM.

## Files

| File | What it is |
|---|---|
| `SKILL.md` | **The engine.** The generic pipeline (load pack → buy-policy routing → Quality Card → multi-source search → CPRU scoring + location-tier + seller-trust → deep-dive → export → outreach → messenger qualification → scheduling) and Comp/Valuation mode. Reads all domain data from the active pack. |
| `DESIGN.md` | **Rationale of record** — why generalize, what's generic vs domain-specific, the abstraction, hard problems, and the phased plan. Not the operational spec (that's `SKILL.md`). |
| `PARITY.md` | Section-by-section map of the live `car-hunt/SKILL.md` → engine + cars pack, proving nothing was dropped. The regression reference for any cutover. |
| `domains/cars.md` | **The reference pack** — full car knowledge; with the engine it reproduces car-hunt behavior. |
| `config/household.example.yaml` | Template for the household's own values (home ZIP, Marketplace city ID, Craigslist regions, per-pack settings). Copied to `config/household.yaml` on first run; that file stays private. |
| `domains/tractors.md`, `furniture.md`, `beekeeping.md`, `generic.md` | **Illustrative sketches** — pack drafts for the next domains. Not yet wired/run. The first real tractor hunt's parameters live in `config/household.yaml`. |
| `eval/` | Per-domain interpretation evals (mirrors `skills/car-hunt/eval/`); the gate a domain must clear before auto-send. See `eval/README.md`. |
| `PHASE2-TRACTOR-HANDOFF.md` | Paste-into-a-new-session prompt for Phase 2 (tractors). Hunt params are canonical in `config/household.yaml` (`packs.tractors.hunt`). |

The qualification **code** lives at `skills/car-hunt/qualification/` (Pydantic
ledger + FSM + per-domain `QualSpec` in `specs.py`); it is already
domain-agnostic and shared by both `car-hunt` and `goods-hunt`.

## Phase tracker

| Phase | Scope | Status |
|---|---|---|
| **0** | Qualification engine domain-agnostic (pack-injected `QualSpec`) | ✅ Done (PR #25) |
| **1** (#27) | Generic `SKILL.md` engine + `cars` pack + `PARITY.md` | ✅ Done (PR #25) |
| **2** (#28) | Tractor hunt — build the pack, run for real (home ZIP, JD/Kubota, ≤$14k; params in `config/household.yaml`) | 🏃 First run done 2026-06-13 (`runs/2026-06-13-tractors.md`); draft-only |
| **3+** | Furniture → beekeeping → generic, each behind its own eval | 🔲 Planned |
| **Cutover** | Make `/car-hunt` delegate to the engine + cars pack | 🔲 Later, eval-gated |

`/car-hunt` and its scheduled workflows remain the **live production entry point**
and are untouched by `goods-hunt` until the cutover.

## How to run (when invoked)

`goods-hunt --domain <name> [search terms]`, or let Step 0 infer the domain from
keywords. New domains run **interactive + draft-only** until they earn scheduling
and auto-send through their own eval.
