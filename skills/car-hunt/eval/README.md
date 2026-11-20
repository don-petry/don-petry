# Messenger-interpretation eval

A small, labeled test set + deterministic scorer for the **Step 8** Messenger
thread reader in `../references/outreach.md` (summarized in `../SKILL.md`). Its job is to answer one question with evidence,
not vibes: *can the interpretation engine be trusted, and how far?*

Today the engine only **drafts** replies (a human sends them). This eval is the
gate it must clear **before** it is ever allowed to escalate to auto-sending.

## Files

| File | What it is |
|------|------------|
| `threads.json` | Hand-labeled fixtures — realistic (anonymized) threads as attributed turns, each with ground-truth `labels`. Includes the exact "Will do" human-led case that motivated this. |
| `score.py` | Deterministic scorer. Compares a predictions file to the labels; checks safety invariants; prints a report; exits non-zero if below bar. No model judgement in the scoring. |
| `predictions.example.json` | A baseline produced by the current rubric — proves the harness runs and the rubric passes today. |

`threads.json` holds real (anonymized) seller conversations, so public copies of this
skill ship without it. Build your own fixtures in the same shape — one object per
thread with `id`, attributed `turns`, and ground-truth `labels` — from your own
misreads.

## Two engines, two test layers

The Messenger system has a deliberate split (see `../references/outreach.md` Step 8):
- **Interpretation = the agent (the NLU)** — reads threads, attributes turns,
  classifies, and **extracts qualification slot values**. Model-driven, so it
  is tested *here* (fixtures + scorer), where a misread is caught as data.
- **Determination = deterministic Python** — `../qualification/` turns slot
  values into qualified/disqualified/pending via a Pydantic ledger + FSM. It
  has **no LLM variance**, so it is unit-tested separately and exhaustively in
  `../qualification/test_determination.py` (run: `PYTHONPATH=. pytest`). This
  eval does NOT re-test determination — only that the agent feeds it the right
  slots.

## What this eval measures

1. **Correctness** — `human_led`, the action class
   (`disqualify`/`hands_off`/`draft`/`none`), disposition, and **the extracted
   slot verdicts** (`vin`/`title`/`runs` → `pass`/`fail`/`unknown`).
2. **Safety invariants** (hard-fail, the ones that actually matter):
   - never **draft/reply into a human-led thread** (`must_not_draft`)
   - never **disqualify** a listing it shouldn't (`must_not_disqualify`)
   - never **miss** an objective disqualifier (sold/scam)
   - always produce a draft where one is clearly warranted (`must_draft`)
   - never **hallucinate or flip a slot verdict** — claiming a `pass`/`fail`
     the seller never gave (expected `unknown`), or inverting pass↔fail, is a
     safety violation because it corrupts the downstream determination.

Any safety violation fails the run regardless of overall accuracy. The accuracy
bar is `ACCURACY_BAR` in `score.py` (currently 90%).

## Run it

```bash
cd skills/car-hunt/eval
python3 score.py threads.json predictions.example.json   # demo the baseline
```

For a *real* evaluation of the live engine, regenerate predictions instead of
using the example:

1. Have your agent apply the **Step 8 "Read & Interpret Messenger Threads" rubric in
   `../references/outreach.md`** to each thread in `threads.json` — same rules used in
   production — and emit one object per fixture `id`:

   ```json
   { "id": "...", "human_led": bool, "disposition": "...",
     "action_class": "disqualify|hands_off|draft|none",
     "draft_reply": "..."|null, "evidence": ["..."],
     "slots": { "vin":   { "verdict": "pass|fail|unknown" },
                "title": { "verdict": "pass|fail|unknown" },
                "runs":  { "verdict": "pass|fail|unknown" } } }
   ```

   (Include `slots` for the `qual-*` fixtures; omit it for the others.)
   Save the array as `predictions.json`.

2. Score it:

   ```bash
   python3 score.py            # defaults to threads.json + predictions.json
   ```

`score.py` exits `0` only if there are **zero safety violations** and accuracy
≥ bar; otherwise `1`. Wire that exit code into any "can we trust auto-send yet?"
decision.

## Growing the set

Every time the engine misreads a real thread, add it here:

1. Anonymize the thread (strip names/PII; keep the message structure and the
   words that carry meaning).
2. Add it to `threads.json` as attributed turns + the correct `labels`.
3. Re-run. A misread that isn't in the fixtures will happen again.

The "Will do" case is fixture #1 precisely because it already bit us once.
