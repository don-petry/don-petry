# Drafting — project-manager specifics

Everything a run needs to draft is on this page, so a run does not have to read the repo's whole
rulebook to write one reply. If the household keeps its own drafting conventions (config
`paths.drafting_conventions`, usually a section of `paths.house_rules`), those govern where the two
differ — and this page should be brought into line with them.

## Never send

Create and update drafts only. Never send, reply or forward — all three deliver mail. Never trash,
spam, label or delete a message or draft either — a mistaken draft is reported in the run summary,
not removed. A calendar event with an **attendee outside the household** (config
`household.members`) also sends an email invitation on the user's behalf, so it is a send: draft the
invite as a question instead.

## One draft per purpose

- Before drafting, read the action's `draft_id` and list drafts **with a query** (`pm.py query`
  prints one). Never list every draft: the full view overflows the tool limit.
- A **standalone** draft for that purpose: **update it** with what changed.
- A **reply** draft (it lives in someone's thread): **don't update it** — Gmail's draft update has
  no thread field and the draft becomes its own thread. Create a new reply draft in the same thread
  instead (reply-to the message being answered), then add the superseded draft to `discard_drafts`
  in `project.yaml` (`{id, subject, why, raised}`) — index.md lists them for the user — and name it
  in the run summary. Confirm the returned thread id is the original thread.
- Record the new draft id on the action as `draft_id`.
- Reply **in the thread** when answering something. Read the whole thread first; search previews
  show only the oldest messages.

## Formatting

- **Mail clients do not render Markdown.** `**bold**` arrives as literal asterisks. Send an HTML
  body with real tags (`<b>` headings, `<br>` line breaks, `<ul>`/`<ol>` lists) wrapped in one
  `<div>` — and don't HTML-escape the tags. Send the plain-text body as well, with the asterisks
  stripped; with the Gmail draft tools, omitting it clears the plain-text part.
- **Bold section headings, not ALL CAPS**, and no blank line between a heading and the text beneath
  it. One blank line between sections.
- The household's spelling and units (config `paths.house_rules`, if it says).
- No mojibake. Write real em-dashes and accents, never `?` or `â€”`.

## Voice

- **Answer the question asked — nothing more.** If they ask for roof years, send roof years. Don't
  volunteer the furnace and the windows because the data is on hand; it buries the answer.
- **Cut the hedges.** Delete "for what it's worth", "that said", "I'd just rather have it confirmed".
  Make the point once and stop. Never explain why you are making a point.
- **Turn facts into arguments.** "The roof was replaced after a 2011 windstorm" is a fact.
  "This house lost its roof to wind in 2011, so a wind-rated roof makes sense" is the argument.
- **State the real reason.** If the driver is "we want the look of a metal roof", say that — don't
  build a tidier rationale around it.
- **Be warm and brief.** "Hi Sam, Happy Monday!" and "feel free to call me if we need a couple
  of details to land this" cost one line each and do more than a structured *Timing* section.

## Content

- **Chase drafts** to a silent party: one short paragraph naming what we're owed, when it was
  asked for, and a specific date we need it by. No guilt, no recap of the whole effort.
- **Never invent a value.** If the reply needs a fact the repo doesn't hold, leave a visible
  `[[<user>: employee ID]]` placeholder in the draft (config `household.user`) *and* open a question.
- **Money, signatures, acceptance** — a draft may *propose* ("we'd like to proceed with the
  $2,492 premium option"), but the words that bind ("please bind", "we accept") are for the user to
  add. Flag it in the run summary.

## Attachments

- A filled form can be attached if it fits the connector inline (tens of KB). Above that, leave it
  in the drive beside the original, link it in the draft, and say plainly that the user must attach
  it — or queue it to `needs_local` where a local credential can upload it (config
  `local.large_upload`).
- Never imply a file is attached when it isn't.
