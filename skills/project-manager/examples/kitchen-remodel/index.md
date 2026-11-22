---
title: Kitchen Remodel (fictional sample)
created: 2026-10-20
modified: 2026-11-18T00:00:00Z
---

# Kitchen Remodel — a fictional sample project

Everything in this folder is invented, to show the shape of a project the skill manages: the
notes stay hand-written, and `pm.py render` fills only the blocks between `pm:begin` and `pm:end`.

## Executive summary

<!-- pm:begin status -->
_Generated from `project.yaml` by the project-manager skill. Edit the YAML, not this block._

**Project status:** active · **Owners:** Parent A, Parent B · **Hard deadline:** 2027-03-15

Two of three contractor bids are in; Ridge Builders' bid fails the license requirement until
they send proof. Cabinet lead time (8–10 weeks) is the critical path: the order must be placed by
2026-12-04 to finish before the deadline. The permit application is waiting on the contractor's
drawing set.
<!-- pm:end status -->

## Decisions

<!-- pm:begin decisions -->
_Generated from `project.yaml` by the project-manager skill. Edit the YAML, not this block._

| ID | Decision | Status | Date |
| :-- | :--- | :--- | :--- |
| D1 | Keep the current layout; no walls move | ✅ DECIDED | 2026-10-20 |
| D2 | Which contractor to hire | ⏳ OPEN |  |
<!-- pm:end decisions -->

## Open actions

<!-- pm:begin actions -->
_Generated from `project.yaml` by the project-manager skill. Edit the YAML, not this block._

| # | Action | Owner | Due | Status | Next step |
| :-- | :--- | :--- | :--- | :--- | :--- |
| A1 | Get proof of license and insurance from Ridge Builders | Pat Rivera | 2026-11-24 | waiting | Chase by email if nothing arrives by 11-24; their bid is not comparable without it |
| A2 | Choose the contractor | Parent A | 2026-12-01 | open | Side-by-side table of the passing bids, recommendation, and the cost of waiting |
| A3 | Place the cabinet order | Parent B | 2026-12-04 | open | Confirm the final quote matches door style 3 and the measured plan before ordering |

_1 closed action(s) still in `project.yaml`; older ones are in `project-archive.yaml`._
<!-- pm:end actions -->

## Clocks

<!-- pm:begin clocks -->
_Generated from `project.yaml` by the project-manager skill. Edit the YAML, not this block._

| Due | Item | Owner | If missed |
| :--- | :--- | :--- | :--- |
| 2026-12-04 | Cabinet order — the last date that still finishes by the hard deadline at a 10-week lead time | Parent B | Installation slips past 2027-03-15 |
| 2027-01-15 | Okafor & Sons quote expires | Okafor & Sons Cabinetry | Prices re-quoted at the new year's rates |
<!-- pm:end clocks -->

## Questions for a human

<!-- pm:begin questions -->
_Generated from `project.yaml` by the project-manager skill. Edit the YAML, not this block._

1. **[Q1]** Is the $48,000 budget firm, or can it stretch to the higher passing bid if that one is faster? — for Parent A · **blocking:** A2 · raised 2026-11-18
<!-- pm:end questions -->

## Bid notes (hand-written)

| Contractor | Bid | Itemized | License proof | Notes |
| :--- | ---: | :--- | :--- | :--- |
| Ridge Builders | $44,900 | yes | missing | Fastest start (January) |
| Okafor & Sons (cabinets only) | $17,200 | yes | n/a | Lead time 8–10 weeks |
| Chen Home Renovation | — | — | — | Declined 2026-11-05: booked through spring |

## Activity Log

### 2026-11-18 — Third bid in; cabinet lead time sets the critical path
Okafor & Sons quoted $17,200 with an 8–10 week lead time, which puts the last workable order date
at 12-04 (clock C1). Ridge Builders' bid is itemized but still lacks license proof (A1).
