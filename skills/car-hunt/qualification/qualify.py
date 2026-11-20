#!/usr/bin/env python3
"""Workflow-invoked qualification step (deterministic; runs after the agent).

Pipeline position: the agent (the NLU) has already read every Messenger thread and
written `run-results.json` with an `inbox[]` array — each entry carries the
interpreted thread state PLUS, for contacted listings, the extracted Minimal-3
slot values. This script turns those slots into a determination using the
Pydantic ledger + the FSM, mutates state deterministically, and emits drafts
for the user to send by hand. It NEVER sends a message (no browser here).

What it does, per non-human-led thread matched to a contacted listing:
  1. merge the slot values the agent extracted into the durable ledger
  2. recompute determination (pending | qualified | disqualified) via the FSM
  3. disqualified  -> remove the listing from active-listings.json
     qualified     -> surface "ready to test drive" + a scheduling draft
     pending        -> surface a draft follow-up asking the unanswered questions
  4. write the updated ledger + active-listings, and a markdown summary

Usage:
    python qualify.py --results run-results.json --ledger conversations.json \
        --active active-listings.json --summary qualification-summary.md

All paths default to the current directory. Missing ledger/active files are
treated as empty. Exit code is 0 unless inputs are unreadable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from ledger import Conversation, Ledger, Slot
from determination import assess, closing_eligible, draft_closing, followup_eligible

VERDICTS = {"pass", "fail", "unknown"}
FOLLOWUP_CAP = 3  # max auto-sent qualification follow-ups per run
CLOSING_CAP = 5   # max auto-sent disqualification closings per run


def _read(path: str) -> Optional[str]:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None


def _slot_from(raw: dict) -> Slot:
    """Build a Slot from the agent's extracted slot dict, defensively."""
    verdict = str(raw.get("verdict", "unknown")).lower()
    if verdict not in VERDICTS:
        verdict = "unknown"
    value = raw.get("value")
    answered = bool(raw.get("answered", value is not None or verdict != "unknown"))
    return Slot(
        answered=answered,
        value=value,
        verdict=verdict,
        evidence=raw.get("evidence"),
    )


def _merge_slot(existing: Slot, incoming: Slot) -> Slot:
    """Latest non-unknown reading wins; otherwise keep what we had.

    The agent re-reads the full thread every run, so a real answer should update
    the ledger, but a run that simply couldn't see the answer (unknown) must
    not erase a previously captured one.
    """
    if incoming.verdict != "unknown" or (incoming.answered and incoming.value):
        return incoming
    return existing


def process(results: dict, ledger: Ledger, active: List[dict], today: str,
            autosend: bool = False, domain: str = "cars"):
    active_by_url = {a.get("url"): a for a in active if a.get("url")}
    drafts: List[dict] = []
    removed: List[dict] = []
    to_send: List[dict] = []   # deterministic send queue (when autosend on)

    for entry in results.get("inbox", []) or []:
        url = entry.get("url")
        if not url:
            continue  # unmatched thread — qualification needs a known listing
        if entry.get("human_led"):
            continue  # hands off — the user is in this thread

        slots_raw = entry.get("slots") or {}
        disposition = (entry.get("disposition") or "").lower()

        is_new = url not in ledger.conversations
        conv = ledger.conversations.get(url) or Conversation(
            url=url, domain=entry.get("domain") or domain)
        # Accept the `seller`/`vehicle` aliases too, in case this runs on a
        # results file that didn't pass through normalize_results.py.
        conv.seller = conv.seller or entry.get("recipient") or entry.get("seller")
        conv.vehicle = conv.vehicle or entry.get("listing") or entry.get("vehicle")

        # Don't seed the durable ledger with an unidentifiable orphan. A
        # brand-new thread that has no seller AND no real slot answer isn't
        # actionable for qualification — persisting it only litters the ledger
        # and emits "None (None) — answered: none yet" junk drafts.
        has_slot_answer = any(
            isinstance(slots_raw.get(n), dict)
            and str(slots_raw[n].get("verdict", "unknown")).lower() in {"pass", "fail"}
            for n in conv.spec().required_slots
        )
        if is_new and not conv.seller and not has_slot_answer:
            continue

        for name in conv.spec().required_slots:
            if name in slots_raw and isinstance(slots_raw[name], dict):
                conv.slots[name] = _merge_slot(conv.slot(name), _slot_from(slots_raw[name]))

        determination, draft = assess(conv)
        # Don't nudge a seller who has gone silent or marked it sold — keep the
        # slots/determination, but suppress the pending follow-up draft.
        if determination == "pending" and disposition in {"ghosting", "sold"}:
            draft = None
        conv.last_updated = today
        ledger.conversations[url] = conv

        # Deterministic send decision (the safety control). Only when send mode
        # is on, the seller is eligible, and we're under the per-run cap.
        n_followup = sum(1 for x in to_send if x.get("kind") == "followup")
        queued = (
            autosend
            and draft is not None
            and followup_eligible(conv, disposition, human_led=False)
            and n_followup < FOLLOWUP_CAP
        )
        if queued:
            to_send.append({"url": url, "seller": conv.seller,
                            "vehicle": conv.vehicle, "message": draft,
                            "kind": "followup", "archive": False})

        # Disqualified-by-reply → close the loop. Surface the courtesy message
        # whenever the conversation is a closing candidate (so it's a hand-send
        # draft even in draft-only mode), and queue it for auto-send + archive
        # when send mode is on and we're under the closing cap.
        close_candidate = closing_eligible(conv, disposition, human_led=False)
        closing_text = draft_closing() if close_candidate else None
        n_closing = sum(1 for x in to_send if x.get("kind") == "closing")
        close_queued = autosend and close_candidate and n_closing < CLOSING_CAP
        if close_queued:
            to_send.append({"url": url, "seller": conv.seller,
                            "vehicle": conv.vehicle, "message": closing_text,
                            "kind": "closing", "archive": True})

        drafts.append({
            "url": url,
            "seller": conv.seller,
            "vehicle": conv.vehicle,
            "determination": determination,
            "disposition": disposition,
            "answered": [n for n in conv.spec().required_slots
                         if conv.slot(n).verdict != "unknown"],
            "draft": draft,
            "queued": queued,
            "closing": closing_text,
            "closing_queued": close_queued,
            "disqualify_reason": conv.disqualify_reason,
        })

        if determination == "disqualified" and url in active_by_url:
            removed.append(active_by_url.pop(url))

    new_active = list(active_by_url.values())
    return drafts, removed, new_active, to_send


def render_summary(drafts: List[dict], removed: List[dict]) -> str:
    if not drafts:
        return "## Seller Qualification\n\n_No active qualification conversations this run._\n"
    by = {"qualified": [], "pending": [], "disqualified": []}
    for d in drafts:
        by.setdefault(d["determination"], []).append(d)
    out = ["## Seller Qualification\n"]
    if by["qualified"]:
        out.append("### ✅ Qualified — ready to test drive (scheduling draft ready)")
        for d in by["qualified"]:
            out.append(f"- **{d['seller']}** ({d['vehicle']})")
            if d["draft"]:
                out.append(f"    Suggested: \"{d['draft']}\"")
    if by["pending"]:
        out.append("### 🟡 Awaiting answers")
        for d in by["pending"]:
            asked = ", ".join(d["answered"]) or "none yet"
            out.append(f"- **{d['seller']}** ({d['vehicle']}) — answered: {asked}")
            if d.get("queued"):
                out.append(f"    📤 Auto-sending follow-up: \"{d['draft']}\"")
            elif d["draft"]:
                out.append(f"    Suggested (draft — send by hand): \"{d['draft']}\"")
    if by["disqualified"]:
        out.append("### 🔴 Disqualified by their answers (removed)")
        for d in by["disqualified"]:
            out.append(f"- **{d['seller']}** ({d['vehicle']}) — {d['disqualify_reason']}")
    closings = [d for d in drafts if d.get("closing")]
    if closings:
        out.append("### 🔻 Closing the loop (disqualified / not a fit)")
        for d in closings:
            reason = d.get("disqualify_reason") or f"disposition: {d.get('disposition')}"
            out.append(f"- **{d['seller']}** ({d['vehicle']}) — {reason}")
            if d.get("closing_queued"):
                out.append(f"    📤 Auto-sending closing + archiving: \"{d['closing']}\"")
            else:
                out.append(f"    Closing (draft — send by hand): \"{d['closing']}\"")
    return "\n".join(out) + "\n"


def _emit_output(key: str, value: str) -> None:
    """Write a GitHub Actions step output (no-op locally)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{key}={value}\n")


def mark_sent(ledger_path: str, sent_path: str) -> int:
    """Post-send: record what actually sent so we never re-send it.

    Sets `followup_sent` or `closing_sent` per the queued `kind`. Falls back to
    the determination when `kind` is absent (older executor output): a
    disqualified conversation's send was the closing; anything else, a follow-up.
    """
    ledger = Ledger.load(_read(ledger_path))
    sent = json.loads(_read(sent_path) or "[]")
    n = 0
    unmatched = []
    for item in sent:
        url = item.get("url")
        if not item.get("sent"):
            continue
        # Match tolerant of FB/redirect URL drift — an exact-string compare
        # here is what let the Eli double-send slip through (the executor
        # echoed a drifted URL, so followup_sent was never recorded).
        conv = ledger.match(url)
        if conv is None:
            unmatched.append(url)
            continue
        kind = (item.get("kind") or "").lower()
        if kind == "closing" or (not kind and conv.determination == "disqualified"):
            conv.closing_sent = True
        else:
            conv.followup_sent = True
        n += 1
    with open(ledger_path, "w") as f:
        f.write(ledger.dump())
    print(f"[qualify] recorded {n} sends (followup_sent/closing_sent)", file=sys.stderr)
    if unmatched:
        # Loud, because an unrecorded send becomes a re-send (spam) next run.
        print(f"::warning::[qualify] {len(unmatched)} sent item(s) matched NO "
              f"ledger conversation — followup/closing NOT recorded, will re-send: "
              f"{unmatched}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="run-results.json")
    p.add_argument("--ledger", default="conversations.json")
    p.add_argument("--active", default="active-listings.json")
    p.add_argument("--summary", default="qualification-summary.md")
    p.add_argument("--to-send", default="to_send.json")
    p.add_argument("--today", default=os.environ.get("RUN_DATE", ""))
    # Post-send pass: --mark-sent <sent.json> just records what was sent.
    p.add_argument("--mark-sent", default=None)
    args = p.parse_args()

    if args.mark_sent:
        return mark_sent(args.ledger, args.mark_sent)

    autosend = os.environ.get("QUAL_AUTOSEND", "").lower() == "true"

    results_text = _read(args.results)
    if results_text is None:
        print(f"!! results file not found: {args.results}", file=sys.stderr)
        return 1
    results = json.loads(results_text)
    ledger = Ledger.load(_read(args.ledger))
    active = json.loads(_read(args.active) or "[]")

    # A run targets one domain; cars omit it (legacy) → defaults to "cars".
    domain = results.get("domain", "cars")
    drafts, removed, new_active, to_send = process(
        results, ledger, active, args.today, autosend=autosend, domain=domain)

    with open(args.ledger, "w") as f:
        f.write(ledger.dump())
    with open(args.active, "w") as f:
        json.dump(new_active, f, indent=2)
    summary = render_summary(drafts, removed)
    with open(args.summary, "w") as f:
        f.write(summary)
    with open(args.to_send, "w") as f:
        json.dump(to_send, f, indent=2)
    # Tell the workflow whether (and how many) follow-ups to send.
    _emit_output("to_send_count", str(len(to_send)))

    print(summary)
    print(f"[qualify] conversations={len(ledger.conversations)} "
          f"drafts={len(drafts)} queued-to-send={len(to_send)} "
          f"disqualified-removed={len(removed)} active-now={len(new_active)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
