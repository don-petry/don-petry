# Advisory matters — a `legal:`, `tax_wealth:` or `health:` block

Read this when `pm.py clocks` prints a non-empty `advisory`. **Step A runs before SKILL.md step 2**:
the gate decides whether this run may draft at all, and finding that out after reading the mail is
too late. Steps and section letters are the ones scheduled-run prompts and the advisory skills cite.

A matter worked by an advisory team is still an ordinary project — the six-step loop in SKILL.md runs
unchanged — but the team owns what may be said and to whom, and that authority is not something this
engine may infer. The shared contract is the advisory-teams framework (config
`paths.advisory_contract`; `docs/advisory-teams.md` in the public repo). It defines the gate modes
and the generic `advisory:` fields `capacity` and `personal_interest` — if config
`schema.field_names` maps them to other names, read and write those.

> **Not a lawyer, accountant or clinician.** For these matters the skill prepares the hand-off to a
> licensed professional; it does not replace one. It never files, signs or sends.

**No team skill installed?** If config `skills.advisory` names no skill for the block, treat the
matter as `INFO_ONLY`: sync, reconcile, record, and list the questions for a professional. Draft
nothing outgoing.

**A. Gate first, before the mail.** Invoke the owning skill (config `skills.advisory.<block>`) and run
its first step in order: find the matter, run the gate table, check the escalation list, probe
capabilities, check its capability triggers. Write the result to `<block>.mode` in the project file.
The mode governs the rest of the run:

| Mode | What this run may do |
| :--- | :--- |
| `ESCALATE`, `LAWYER_PREP`, `INFO_ONLY` | Sync, reconcile and record. **No drafting.** The deliverable is the hand-off packet and the questions for the professional. |
| `CONFLICT` | Work the other person's interest. The household member's own claim stays separate and is disclosed in writing. Then continue by the next matching gate row. |
| `TRANSITION` | Add the hand-over plan to the person coming of age, then continue by the next row. |
| `FIDUCIARY_PRESUIT`, `FIDUCIARY_COURT`, `SELF`, `JOINT` | Drafting allowed, into `drafts/` only. |

**B. Say what is degraded.** The capability probe is not decoration. If `pdftotext` is absent, a
quotation from a PDF cannot be verified and must be labeled unverified. If the case-law service
refuses without a token, **no case may be quoted at all**. Record each gap under `advisory.gaps`
with the date and put it in the run summary.

**C. An escalation ends the drive-forward work.** The action-first default stops at an escalation.
When `escalate_when` or the team's own list fires — a release to sign, a capacity challenge, a
medical-exam demand, opposing counsel, a court date, a clock inside 90 days that is not verified —
the job for that item becomes preparing the hand-off, not continuing. Draft nothing outgoing on it.

**D. The draft path is the team's, not the mailbox's.** For an advisory matter, acting.md's "draft it
in the thread" does not apply to a letter, demand, counter, or response to the other side. Instead:

1. Write it into `<notes_root>/drafts/`. Strategy — floors, targets, reasoning — goes in
   `strategy.md`, never in a draft that leaves.
2. Run the source verifier (config `paths.verify_sources`; `tools/verify_sources.py` in the public
   repo) on the draft. Anything not PASS is **fixed or struck, never argued past**. Then the
   `source-verifier` persona checks figures and dates, which the script does not.
3. The `red-team` persona reads it from the other side's seat before it goes anywhere.
4. **An unattended run stops there.** It does not promote the draft to `outbound/`, does not create
   a mail draft of an outgoing legal letter, and does not render a signable PDF. It records what is
   ready and escalates for the human. Promotion happens only in an attended session, and only a
   human signs or sends. A project's `decisions` may record a stricter rule for one matter (config
   `advisory.example_rule`).

**E. Never state a date you computed.** Quote it from a document or record the rule and flag the
deadline calculation (trigger `T-CLOCK`). A clock whose `due` you derived rather than read is a `FAIL`,
not a clock. "No deadline" is itself a claim that needs every candidate clock listed.

**F. The run summary carries the team's banner.** First line of the notification still leads with
the user's action; the body opens with `Mode · escalations · verification PASS/FAIL/BLOCKED`, and
closes with **What I couldn't verify** plus, for a legal matter, the referral line (config
`advisory.referral_line`, or the legal skill's own).

**G. Quiet still means quiet.** The gate runs every time, but a run whose gate result is unchanged,
whose `clocks.verdict` is `quiet` and whose sync found nothing ends like any other: `record --quiet`,
with the mode in `--result` (config `advisory.gate_example` shows the shape), and a one-line
`Quiet —` message. Leave `<block>.mode` alone when it has not changed. The banner in F is for runs
that have something to say.
