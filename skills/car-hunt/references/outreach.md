# car-hunt — Outreach, Messenger Reading and Seller Qualification (Steps 7 and 8)

Read this before contacting any seller (Step 7) or reading seller threads (Step 8).

## Step 7: Automatic Outreach (Optional)

After Step 6 (spreadsheet export, in `../SKILL.md`), offer this option:

> "Want me to message the top uncontacted listings on Facebook Marketplace?"

Only run this step if the user explicitly confirms — either at the start of a run (e.g., "also send messages") or when prompted here.

### Message Template

Use `CONFIG.outreach.opener_template` from `config/household.yaml`. If it is empty, ask the user for their wording once and save it, along with two or three distinctive fragments of it as `CONFIG.outreach.opener_fingerprint` (used by the fail-closed composer check and Step 8 turn attribution). A good opener is short, says why you're buying, asks to meet for a test drive, and asks whether the title is clean and in hand, e.g.:

```
Hey [FIRST_NAME] - Very interested in your car! Could we meet up for a test drive? And do you have a clean title in hand? Thanks!
```

Replace `[FIRST_NAME]` with the **actual message recipient's first name** — read it from the open message modal (the modal title `Message {Name}`, or the send button's `aria-label="Send message to {Name}"`), **NOT** from the listing's "Seller details" sidebar. The sidebar name and the real recipient can differ (e.g., the sidebar showed a real full name but the message actually went to an account with a joke handle) — addressing the wrong person is worse than no name. If the recipient name can't be read, or isn't a plausible human first name (e.g., a joke handle, a business name, all-symbols), **omit it entirely and open with "Hey -"**.

### How to Execute

**For each candidate in the top N uncontacted qualified listings (default N=3):**

1. **Open the listing tab** — navigate to the FB Marketplace listing URL in the automated browser.

2. **Check message history** — run this JS on the listing page:
   ```javascript
   const text = document.body.innerText;
   const alreadyMessaged = text.includes('Message again');
   JSON.stringify({ alreadyMessaged });
   ```
   - If `alreadyMessaged` is `true` → skip this listing (already contacted), move to next candidate
   - Also check the sheet's `Contacted` column — if it has a date, skip
   - **Do not read the seller name here** — the greeting name is taken from the message modal in step 4 (the authoritative recipient), not the listing sidebar.

3. **Show dry run first** — before sending anything, show the user:
   ```
   Proposed messages (dry run):
   1. [Seller name] — [Year Make Model] — "Hey [Name] - Very interested!..."
   2. ...
   
   Proceed?
   ```
   Wait for explicit confirmation before sending.

4. **Send via modal dialog** (the only reliable method on FB Marketplace):
   - Click the blue "Message" button at the top of the listing (not the inline Send button at the bottom)
   - Wait for the "Message [Seller Name]" modal to appear
   - **Read the recipient name from the modal NOW** — capture the modal title (`Message {Name}`) or the send button's `aria-label="Send message to {Name}"`. This is the authoritative recipient; personalize the greeting from this name (see Message Template). If it isn't a plausible first name, open with "Hey -".
   - Click the textarea in the modal
   - Type the personalized message (built with the recipient name from the modal)
   - Click "Send message" button in the modal
   - Confirm send by checking for "Sending" button state
   - **Record** the recipient name actually used in the `outreach` entry's `seller` field (so logs reflect who was really messaged, not the sidebar name)

5. **Update the sheet** — after successful send, write `YYYY-MM-DD sent` to the `Contacted` column for that listing's row.

### Important Rules

- **Always check history before sending** — use both JS detection (`Message again` text) and the sheet's `Contacted` column to avoid duplicate outreach
- **Never send without dry-run approval** — show proposed messages first; wait for "proceed" / "yes" / "go ahead"
- **Never fabricate or guess a seller name** — personalize ONLY from the message-modal recipient name (step 4). Never use the listing sidebar's "Seller details" name for the greeting — it can differ from the real recipient. If the modal name is missing or implausible, drop the name and open with "Hey -"
- **Skip non-FB listings** — this outreach flow only works on FB Marketplace; other sources require manual contact
- **Skip listings where the modal doesn't open** — some FB profiles block messages; note it and move on
- **Log every send attempt** — update the sheet regardless of whether the send succeeded or failed (note "FAILED" if the modal didn't respond)

---

## Step 8: Read & Interpret Messenger Threads (Option C / logged-in only)

**Purpose:** Understand each seller conversation well enough to (a) disqualify listings on objective facts the seller revealed, and (b) *draft* (never auto-send) a proposed reply when one is warranted — so the user never has to relay updates and always has the next move teed up. Runs at the **start** of a run (before ranking) so disqualifiers take effect before re-ranking/re-contacting.

**Only possible in Option C** (a browser-automation tool with a live logged-in FB session). If not logged in, skip entirely and note "Messenger reading unavailable (not logged in)".

> **The hard lesson this design encodes:** a single latest line ("Will do", "ok", "sure") is meaningless without the turn before it, and a thread the *human* has been typing in is NOT ours to answer. The old single-message reader once invented "confirmed availability tomorrow evening" from a bare "Will do" in a thread the user was already handling. The rules below exist to make that class of error impossible: read the whole thread, attribute every turn to a speaker, quote your evidence, and hard-stop on human-led threads.

### How to Execute

1. **Open the Marketplace inbox** — navigate `https://www.facebook.com/marketplace/inbox/` (fallback `https://www.facebook.com/messages/t/`). Wait for the thread list to render.

2. **Open EVERY recent thread (~20). Do NOT gate on unread/bold state** — opening a thread marks it read, so unread-gating would action a reply at most once and miss it after a failed run. Re-read every run; all actions below are **idempotent**.

3. **Read the FULL recent thread as attributed turns — not just the last line.** Capture the last ~10–15 messages in order as `turns: [{ speaker, text, outbound }]`, where `outbound` is true for messages sent from this account (FB renders them right-aligned / in the sent-bubble style) and false for the seller's. Determine `speaker` for each turn:
   - **seller** — any inbound (non-outbound) message.
   - **automation** — an OUTBOUND message that is EITHER (i) our standard opener template (an outbound turn containing a `CONFIG.outreach.opener_fingerprint` fragment), OR (ii) a **bare Facebook prefill opener** — the low-information default FB seeds the composer with, e.g. "Hi, is this available?" / "Hello, is this still available?" / "Is this still available?" (case/punctuation-insensitive, optional "still"). The automation never types a bare availability question by choice, so a thread whose only outbound turn is this prefill is **automation-led, not human-led** — this is what lets a thread recover after a composer-replacement failure sent the prefill instead of our opener. (See the Step 7 fail-closed guard, which stops that send going forward.)
   - **human (the user)** — an OUTBOUND message that is **anything other** than the standard opener or a recognized bare FB prefill opener. If the user typed something real, it won't match either.

4. **Compute the thread state** (structured, auditable — every conclusion needs a quote):
   - `listing` — the Marketplace listing card at the top of the thread (vehicle + price); used to match a contacted listing by URL/vehicle.
   - `last_speaker` — `seller` | `automation` | `human` (who sent the most recent turn).
   - `human_led` — **true if ANY turn has `speaker: human`.** Once the user has typed in a thread, it is human-led.
   - `disposition` — `available` | `sold` | `negotiating` | `revealed_disqualifier` | `asking_question` | `scheduling` | `ghosting` | `unclear`.
   - `open_item` — what (if anything) awaits a reply, and from whom (e.g. "seller asked if we can come Saturday — awaiting our answer"). `null` if nothing is pending on us.
   - `evidence` — **direct quotes** from the turns backing `disposition` and `open_item`. If you cannot quote it, you may not assert it. A bare acknowledgment ("Will do" / "ok") is NOT evidence of anything on its own — interpret it only via the turn it answers, and if that turn was `human`, treat the whole thread as human-led.
   - `confidence` — `high` | `medium` | `low`. Use `low` whenever the latest turn is a context-dependent fragment, the thread is ambiguous, or attribution is uncertain.

5. **Decide the action** from the state — in this strict order:
   - **a. Objective disqualifier (always safe, even in human-led threads):** if `disposition == revealed_disqualifier` (seller's own words say rebuilt / salvage / branded / lost / no title / "bill of sale only"), or seller says **sold/pending/unavailable**, or a **scam** signal (off-platform payment, shipping, Zelle/CashApp before seeing, broker/agent language) — **disqualify the matched listing**: remove it from `active-listings.json` and append to `disqualified` with `reason: "seller reply: {quote}"`. Idempotent (no-op if already gone). Requires a matched listing and a quote; if unmatched, surface but don't remove.
   - **b. Human-led → HANDS OFF (no draft):** if `human_led` is true and it's not a disqualifier, set `action: "none — human-led, you're handling this"`. **Never draft or send into a thread the user is in.**
   - **c. Draftable → DRAFT ONLY:** if the thread is automation-led, `last_speaker == seller`, there's an `open_item` on us, it's not a disqualifier, and `confidence` is `high` — compose a *proposed* reply and put it in `draft_reply` (see below). **Do NOT send it.** If `confidence` is `medium`/`low`, do not draft; set `action: "none — needs your read (low confidence)"` and rely on the summary.
   - **d. Nothing actionable:** `last_speaker` is `automation` (seller hasn't replied) or `disposition == ghosting` → `action: "none"`.

   **`draft_reply` rules:** short, specific to the `open_item`, never invents facts not present in the thread, plain-text, a *suggestion for the user to send* (never auto-sent). **Put each sentence on its own line with a blank line between them** — the whitespace makes the message much easier to read on a phone. Example: open_item "seller asked when we can come" → `draft_reply: "That works!\n\nCould we come by Saturday afternoon to take a look and test drive?"`.

6. **Surface everything** — add an `inbox` array to `run-results.json`, one object per thread that has a seller message:
   ```json
   { "recipient": str, "listing": str, "url": str|null,
     "last_speaker": str, "human_led": bool, "disposition": str,
     "open_item": str|null, "evidence": [str], "confidence": str,
     "action": str, "draft_reply": str|null }
   ```
   And add a **"Messenger Threads"** section to `run-summary.md` (→ the run-log issue), grouped by what the user must do, e.g.:
   ```
   ## Messenger Threads (4)
   ### 🟡 Needs your reply (drafts ready — review & send)
   - Isaiah (2007 Civic) — seller: "still available, when can you come?" [high]
       Suggested: "Could we come by Saturday afternoon to take a look and test drive?"
   ### 🔵 You're handling (human-led — no action taken)
   - Kolton (2009 Civic) — last: seller "Will do" (you replied earlier) [low]
   ### 🔴 Disqualified
   - Luhkane (2006 Camry) — "the car has a rebuilt title" → removed
   ### ⚪ No reply yet / nothing to do
   - Dario (2007 Camry, dealer) — ghosting
   ```

### Important Rules

- **Read-only on Messenger.** This step NEVER types or sends — not even drafts. Drafts are text in the report for the user to send by hand. The only writes are to the dedup state file (disqualify/remove), committed by a later workflow step.
- **Quote or it didn't happen.** Every `disposition`/`open_item`/disqualifier must be backed by a direct quote in `evidence`. No quote → downgrade to `unclear` / `confidence: low` / no action.
- **Human-led threads are off-limits** for drafting or replying — disqualification on objective facts is the only action permitted there.
- **A bare acknowledgment is not a signal.** "Will do", "ok", "sure", "👍" carry no standalone meaning — never derive availability, scheduling, or commitments from them alone.
- **Match conservatively.** Only disqualify when the thread clearly matches a known contacted listing (by listing card vehicle/price/URL). Otherwise surface with `action: "none (unmatched)"`.
- **Never disqualify on ambiguous language.** "needs a little work", "as-is", "no warranty" are NOT title problems. Only rebuilt/salvage/branded/lost/no-title/bill-of-sale-only.

### Seller Qualification — Minimal-3 slots → deterministic determination

When a contacted seller's first reply is positive, we automatically qualify them against three required questions. **Interpretation is the agent's job; the determination is NOT.** The agent extracts the slot values; a small deterministic Python engine (`skills/car-hunt/qualification/`, Pydantic ledger + a `python-statemachine` FSM) turns those values into the qualify/disqualify decision. This keeps the consequential decision testable and decoupled from LLM variance (see the research that drove this design). The split:

**What the agent does (per contacted, non-human-led thread):** read the whole thread and fill the `slots` object in that thread's `inbox` entry. For each of `vin`, `title`, `runs`, emit `{ answered, value, verdict: "pass"|"fail"|"unknown", evidence }` with the seller's own words as `evidence`:

| Slot | `pass` | `fail` (disqualifies) | `unknown` |
|------|--------|------------------------|-----------|
| `vin` | VIN or door-jamb photo provided | refuses / evades (a documented red flag) | not asked/answered |
| `title` | clean, in seller's name, in hand | rebuilt / salvage / branded / flood / junk / lost / no-title / lien-unreleased / bill-of-sale-only / not in their name | not stated |
| `runs` | runs & drives, no warning lights / major issues | won't run/start, or major mechanical (transmission, engine knock, overheating, head gasket) | not stated |

**Never guess a `pass` or `fail` — use `unknown` when unsure.** Do NOT compute the determination or write the follow-up yourself.

The follow-up question text lives in `qualification/specs.py`. The `title` question names the buyer's state when `config/household.yaml` sets `location.state_name` ("Is the title from {state} and in your name and in hand?"); otherwise it asks a state-neutral version.

**What the deterministic step does (after the agent, in Python):** merges the slots into the durable ledger (`conversations.json` on the `car-hunt-state` branch; latest non-`unknown` reading wins, so a prior answer is never erased by a run that couldn't see it), then recomputes determination as a pure function of the current slots:
- **any slot `fail` → `disqualified`** — the listing is removed from `active-listings.json` with the seller's quoted words as the reason, and a polite **closing message is sent to close the loop** (see "Closing the loop" below).
- **all three `pass` → `qualified`** — surfaced as "ready to test drive" with a drafted scheduling message.
- **otherwise → `pending`** — a follow-up is drafted asking ONLY the still-unanswered questions.

Determination is a pure function of the latest slots (self-correcting: a corrected misread recovers, no permanent kill). All drafts are **draft-only** — surfaced in the run-log issue for the user to send by hand.

**Send mode (live in the Messenger workflow, after the eval passed 14/15 on 2026-06-11):** the standard qualification questions are **auto-sent** to eligible sellers; everything else (free-form replies, the scheduling message) stays draft-only. The send decision is **deterministic, not LLM-driven** — `qualify.py` (via `followup_eligible`) picks who gets a follow-up under strict rules and writes a `to_send.json` queue; a separate verbatim-executor step then sends exactly that text. Guard rails, all enforced in tested code:
- **Eligible only:** automation-led (never a thread you're in), positive disposition, determination `pending`, has unanswered questions.
- **Ask once:** the ledger's `followup_sent` flag means a seller is never re-asked (critical — the Messenger workflow runs every ~3h; without this it would spam).
- **Cap 3 per run**, never on a dry-run, master kill-switch = repo variable `QUAL_SEND_ENABLED` (set to anything but `true` to instantly revert to draft-only).
The opener still auto-sends from the full search workflow; qualification follow-ups auto-send from the Messenger workflow — a clean split. The FSM + eligibility are unit-tested (`qualification/test_determination.py`); the interpretation engine is scored by `skills/car-hunt/eval/`.

**Closing the loop (auto goodbye + archive on disqualification):** when a seller's reply disqualifies the listing, we send one short, courteous sign-off — *"Thank you so much for the quick reply! It looks like this may not be a good fit for us, but I really appreciate your time. Best of luck with the sale!"* — so the conversation ends cleanly and a human scanning the inbox can see the outcome at a glance. After the send, the verbatim executor **archives** that Messenger thread (best-effort; never deletes). This reuses the exact send-mode safety model as follow-ups — the decision lives in tested Python (`closing_eligible` in `determination.py`), not the LLM:
- **Triggers on:** an answered-`fail` (`determination == disqualified`) **or** a closing disposition (`sold` / `revealed_disqualifier`).
- **Never on:** `scam` or `ghosting` dispositions (don't engage a scammer; don't ping a ghost), and never a `human_led` thread.
- **Send once:** the ledger's `closing_sent` flag (mirrors `followup_sent`) means a disqualified seller is closed out exactly once, even though the conversation lives on in the ledger and the Messenger workflow re-runs every ~3h.
- **Cap 5 per run**, never on a dry-run, same master kill-switch (`QUAL_SEND_ENABLED`). In draft-only mode the closing is surfaced under a "🔻 Closing the loop" section of the run-log for the user to send by hand. `closing_sent` is recorded by `mark_sent` from the executor's `sent.json` (`kind: "closing"`, plus an `archived` flag).

> **Evaluation:** the interpretation rubric above is the single source of truth for the `eval/` harness (`skills/car-hunt/eval/`). Before this engine is ever trusted to *auto-send* (a future phase — today it only drafts), run the eval against the labeled threads and clear the accuracy bar. See `eval/README.md`.
