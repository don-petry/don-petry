# Per-domain interpretation evals

Each domain that works toward **auto-sending** seller messages must first clear a
labeled-fixture eval here — the same discipline that got the car Messenger flow to
14/15 before it was trusted to send. New domains run **draft-only** until they do.

Mirror `skills/car-hunt/eval/` (its `README.md`, `score.py`, `threads.json`):

```
skills/goods-hunt/eval/
  <domain>/
    threads.json   # anonymized, attributed-turn fixtures + ground-truth labels
    (score.py is shared from car-hunt/eval — reuse it; don't fork the scorer)
```

What an eval measures (unchanged from car-hunt): correctness of `human_led`, the
action class (`disqualify`/`hands_off`/`draft`/`none`), disposition, and the
extracted qualification **slot verdicts** for that domain's `QualSpec`; plus the
hard safety invariants (never draft into a human-led thread, never disqualify
wrongly, never miss an objective disqualifier, never hallucinate/flip a slot
verdict). Zero safety violations + accuracy ≥ bar → the domain may be considered
for auto-send.

**Status:** no domain eval exists yet. The first is `tractors/` (Phase 2, #28) —
seed it from real misreads during the tractor hunt, then it gates any move from
draft-only to auto-send for tractors.
