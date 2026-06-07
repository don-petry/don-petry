---
name: packaging-scout
description: >-
  Research, compare, and evaluate packaging for a product, then deliver a scored comparison, a ranked
  recommendation, a sourcing list with links, and a PDF report. Use whenever the user wants to find or
  choose packaging — boxes, cartons, sleeves, mailers, tubes, jars, tins, labels, void fill, inserts — for
  something they make or sell. Trigger on requests like "find packaging for my candles," "what box should
  I ship these in," "compare these mailers," "source kraft boxes under $3," or any vendor/MOQ/unit-cost
  packaging comparison — even if the user never says "packaging." Also use to build or update a saved
  packaging spec or vendor catalog. A protective shipping box, mailer, tube, or void fill IS packaging and
  stays in scope even when the user says "ship," "postage," or "protect" — handle the packaging; leave
  postage math to a carrier tool. Send elsewhere only for: designing label artwork/graphics; comparing
  carrier rates (USPS vs UPS) with no packaging choice; or software "package" management (npm, pip, apt).
---

# Packaging Scout

Help a maker/vendor pick the right packaging for a product: gather requirements, research real options,
verify the facts that actually decide it, score them side by side, and hand back a recommendation plus a
polished report they can act on.

The whole point is to turn a vague "what should I put these in?" into a defensible decision backed by
current prices, real suppliers, and a clear-eyed look at the tradeoffs. Do the legwork the user can't be
bothered to do across a dozen vendor tabs.

## Configurable context (read this first)

This skill is product-agnostic, but it works best when it knows who it's working for. If the user has a
maker/vendor profile in memory (business, products, aesthetic, sustainability stance, sales channels,
typical order volumes, region), load it and let those preferences pre-fill the requirement profile so you
don't re-ask things you already know. If there's no profile, infer from the conversation and confirm.

Default house leanings to assume unless told otherwise (override freely): natural/recyclable materials,
plastic-free when affordable, low MOQ (small batches), branding applied via the maker's own sticker/stamp
rather than custom printing, and a preference for domestic (made-in / ships-from same country) suppliers.

## The workflow

Six phases. Don't skip the profile or the verification — those are where bad packaging decisions get made.

1. **Build the requirement profile** — interview the user (briefly) into a concrete spec.
2. **Research options** — cast a wide net across vendor types; use subagents for breadth.
3. **Verify the deciders** — physical fit, country of origin, and total landed cost. Use the browser when sites block automated reads.
4. **Score and compare** — a criteria × options matrix, honestly scored.
5. **Deliver** — comparison matrix, ranked recommendation, sourcing list with links, and a formatted PDF report.
6. **Remember** — save the profile and findings so the next product (and re-runs) start ahead.

---

## Phase 1 — Build the requirement profile

Interview conversationally, not as a wall of dropdowns. Pull what you can from memory/context first, then
ask only the gaps. Capture these fields (this is the spec that drives everything downstream):

- **Product**: what it is, dimensions/weight, and what constrains packaging — fragile? perishable? leaks? heat-sensitive? needs to look giftable? The single most important physical fact is usually one dimension (length for tapers, diameter for jars). Pin it down.
- **Format(s)**: rigid box, folding carton, sleeve/belly band, pillow box, tube, mailer, jar/tin, etc. Users often want a primary plus a cheaper secondary for some channels.
- **Visibility**: do customers need to see the product? Open die-cut window (plastic-free), film window (PET/acetate/compostable), or fully enclosed? Note: "window" usually implies plastic film — surface that tension if they also want plastic-free.
- **Material / sustainability bar**: what's the actual rule — recyclable, recycled content, compostable, plastic-free, or just "looks natural"? This determines what's even on the table. Food-grade or not?
- **Branding method**: custom-printed packaging vs. blank stock + the maker's own sticker/stamp. Blank stock dramatically lowers MOQ and setup cost — confirm which they want.
- **Channels**: in-person (markets/store) vs. shipped vs. wholesale. Shipping demands protection; retail demands shelf appeal. Most makers need both.
- **Volume**: starting order quantity. This is decisive — many attractive options die on MOQ.
- **Target cost**: per-unit (or per-package) ceiling. Get a number or a range.
- **Origin preference**: made-in / ships-from a specific country? If yes, this re-ranks everything (see Phase 3).

Write the profile back to the user as a short bulleted spec and get a nod before researching. Flag obvious
tensions immediately — e.g., "a true rigid two-piece box under $X at only N units is hard; rigid is pricey
at low volume." Naming the tension early saves a research pass.

---

## Phase 2 — Research options

Cast wide. Real options live across several vendor *types*, and each type has a different sweet spot:

- **General packaging distributors** (Uline, Papermart, Nashville Wraps, ClearBags) — in stock, low MOQ, fast domestic shipping, blank. Great for "buy it now."
- **Eco / sustainable specialists** (EcoEnclose, noissue, etc.) — best material story, but custom sizes often gate behind high MOQs.
- **Category specialists** (e.g., candle-box makers) — purpose-built fit and inserts; sometimes the only thing that natively solves the product's protection problem.
- **Custom box shops** — any size + windows + low MOQ, but many are overseas (see origin check) with setup/dieline fees and long lead times.
- **Small-batch makers (Etsy and similar)** — lowest MOQs, rustic/blank, often the best fit for a 50–250 unit first run.

When you're the orchestrator, use research subagents to gather breadth in parallel — hand each a
self-contained brief with the full requirement profile and ask for, per option: vendor + product +
**direct URL**, format, material/recyclable, window type, **interior dimensions (does it actually fit?)**,
MOQ, **price per unit at the user's volume tier**, lead time, and origin signals. Tell them to report
findings only (no files) and to say "couldn't verify" rather than guess. (If you're already running as a
subagent and can't spawn more, just do the same searches serially — the breadth target matters, the
parallelism doesn't.)

Research **8–12 options**, but expect the scored matrix to be shorter: many candidates die on fit, and
Phase 4 lists those separately as "disqualified" rather than padding the matrix. For a narrow product
niche, 5–6 genuinely viable options after fit-screening is a healthy result, not a shortfall — don't
manufacture weak options to hit a count.

See `references/evaluation-playbook.md` for the vendor-type cheat sheet and search-term ideas.

---

## Phase 3 — Verify the deciders

Three facts decide most packaging choices, and all three are routinely gotten wrong by headline listings.
Verify them before you rank anything.

**1. Physical fit.** The make-or-break dimension must actually accommodate the product with margin. A box
"for tapers" that maxes at 8" won't hold a 9" candle. Disqualify on fit before considering anything else —
a cheap box that doesn't fit is worth zero. Watch the shape-mismatch trap too: a round product in a square
interior touches the walls at its widest points even when the listed dimensions "fit" (a 3"-diameter pillar
in a 3×3 box is flush, with zero cushioning) — that's a fit *with a protection caveat*, not a clean fit, and
it usually argues for a slightly larger box plus an insert.

**2. Country of origin / where it ships from.** When the user prefers domestic, this re-ranks everything.
Watch for the common pattern: a custom box shop lists a US (or local) mailing address that is just a
**sales office**, while manufacturing and freight are overseas. Tells: "free worldwide shipping" baked into
the unit price, multi-week lead times, no disclosed domestic plant, reviews mentioning overseas shipment.
Distinguish a true domestic *manufacturer* from a domestic *distributor reselling imported stock* — both
"ship from" the country, but only one is "made in" it. State origin with a confidence level and your source.

**3. Total landed cost — not the headline unit price.** Add shipping (or the free-ship threshold) and any
one-time **setup / dieline / plate fees** (common on custom/printed boxes, often hidden until the proof).
A $0.45 box with a $90 dieline fee is not $0.45 at 100 units. Compare apples to apples at the user's actual
starting volume.

**Price verification & fallbacks.** Many vendor sites block automated fetches (return 403 or empty HTML to
scrapers) — Betterbee, Uline, Papermart, ClearBags, and Etsy are frequent offenders. **Do not guess
prices.** Work through the fallbacks in order until one yields a confirmed number:

1. **Chrome extension** (best, when you have it) — open the product page, read the price/quantity-break
   table (a screenshot or `get_page_text` works), record the number with the date. This is the only path
   that reliably gets *quantity-tier* pricing, so reach for it whenever the user's volume sits on a break,
   and it's the only path that works on a fully JS-rendered storefront (see the limit below).
2. **Raw HTML, structured data.** `curl` the page with a browser User-Agent and grep the raw HTML for the
   embedded `schema.org` product data — `application/ld+json` with an `Offer` / `UnitPriceSpecification`, or
   `og:price`/`product:price` meta tags. The price is frequently sitting in that static markup even when the
   rendered page looks blocked or empty. This tactic won repeatedly in testing and is the **workhorse for a
   subagent** that has no extension. Prefer raw `curl` over `WebFetch` here — `WebFetch`'s summarizer often
   hides JSON, returns false "not found," or times out, while `curl` returns the bytes you can grep.
3. **Search-result and shopping snippets** — Google Shopping listings, the price line in a search result, or
   a cached page often expose the unit price even when the live product page blocks you. Good enough for a
   single-quantity confirm; note it's a list price, not necessarily the tier price.
4. **Quote-only / truly unreachable** — label it clearly as an *unverified manual lookup* (or "live quote
   required") rather than inventing one, and flag it as the first thing for the user to confirm.

Note which tier and which method each price came from. **The one hard limit:** a fully client-side-rendered
storefront (price exists only after JS runs, nothing in raw HTML or snippets — EcoEnclose is the known
example) has *no* verified-price path without a live JS browser. If you're a subagent without the extension,
confirm what you can from the static markup (specs, MOQ, origin), mark the price unverified with that
specific reason, and stop — don't burn a dozen attempts on a price that provably isn't reachable from your
toolset. Trust in the numbers is the whole value of this exercise.

**Don't fold on the first failure — an empty page is a clue, not a dead end.** "Unverified" is a last resort
reached only after the ladder above is exhausted, not a label you reach for the moment a fetch comes back
blank. The most common trap: a recorded product URL is *stale and silently redirects* to the category or
shop page (you'll see empty article-text or a parent-page title), and the real price is sitting in a size/
variant grid one inspection away. When a page seems empty or wrong, before declaring it unverified: check
where you actually landed, grep the raw HTML for structured data (step 2), then — if you have the extension —
use `find` / `read_page` / a small DOM query to locate the variant, and try the parent shop page or an
on-site search for the size. The same persistence applies to fit specs and origin. Spend the extra two or
three attempts (but respect the JS-only limit above) — a confirmed number is the deliverable.

---

## Phase 4 — Score and compare

Build a matrix: rows = options, columns = the requirement-profile criteria that matter (fit, window/material,
recyclable, MOQ, under budget, protection for the channel, origin, aesthetic). Score each cell honestly as
**meets / partial / fails**. Partial is not a cop-out — a kraft box with a plastic film cover genuinely
*partially* meets "plastic-free," and saying so is more useful than a fake yes/no.

The matrix exists to make the decision legible at a glance, so the best options visibly clear every column.
Don't pad it with options you've already disqualified on fit — list those separately as "disqualified, and
why."

---

## Phase 5 — Deliver

Produce all four, tailored to what the user asked for (if unsure, produce the matrix + recommendation inline
and offer the report):

1. **Scored comparison matrix** (the Phase 4 table).
2. **Ranked recommendation** — a top pick *per priority*, not a single dogmatic answer. Packaging is a
   tradeoff space: "want zero effort + perfect fit → A; want your exact material at low MOQ → B; want
   cheapest in-stock now → C." Explain what each choice costs the user. Call out the one or two facts still
   worth confirming (a quote, a sample).
3. **Sourcing list** — vendor, product, direct link, MOQ, confirmed price at volume, lead time, origin.
4. **Formatted PDF report** — see below.

### Generating the PDF report

LibreOffice is often **not installed**, so the reliable path is **HTML → headless Chrome → PDF**, which
needs only Google Chrome (almost always present on a Mac).

- Start from `assets/report_template.html` — a branded, landscape report scaffold (cover, requirements,
  methodology note, color-coded comparison matrix, option profiles, decision guide, disqualified list, next
  steps). Fill in the content; keep the structure.
- Convert with the bundled script:
  ```bash
  bash scripts/html_to_pdf.sh /path/to/report.html /path/to/output.pdf
  ```
  It locates Chrome and runs a headless print-to-PDF. Verify the result by reading a couple of pages back.

**Embedding product images (optional but high-impact).** If the user wants product photos, actually go get
them — don't default to placeholders. Two ways to find the main image URL: with the Chrome extension, take
the largest `<img>` by natural dimensions excluding logos/icons (a one-line DOM query over
`naturalWidth`/`naturalHeight`); without it (e.g. a subagent), `curl` the raw HTML and pull the `og:image`
meta tag — it's the listing's hero image and needs no JS. Either way, download it locally with `curl` (use a
browser User-Agent and a matching `Referer`; note some CDNs serve WebP regardless of the `.jpg` you
requested, so check the real type with `file` and rename to match). Reference the local files from the HTML
and keep them in an `images/` folder beside the report so the PDF and source stay portable. The template supports both an
`<img class="thumb">` and a same-size `<div class="thumb ph">image n/a</div>` placeholder — use the
placeholder only for a vendor whose page is genuinely gone (dead/redirecting URL) or that lazy-loads behind
script with no reachable URL after you've actually tried, not as a shortcut to skip the download step. Add a
one-line note that the photos are each vendor's own listing image, shown for reference.

A subagent usually lacks the Chrome extension, so image-pulling is best done by the orchestrator (you) after
research returns, or noted as a quick follow-up — it's a poor reason to ship a report full of placeholders.

---

## Phase 6 — Remember

Save what's durable so re-runs and future products start ahead:

- The **requirement profile** for this product (it'll be revisited and tweaked).
- **Confirmed prices with dates** and origin findings (prices go stale — date them).
- Any **vendor catalog** entries worth reusing across products (good domestic suppliers, MOQs, fee patterns).

If the user maintains memory, write these there. Otherwise offer to save a spec file in the project.

---

## Operating principles

- **The unverified number is the dangerous one.** A confident-looking price that's actually a guess is worse
  than a labeled gap. Date your confirmations; flag what you couldn't reach.
- **Fit first, then origin, then landed cost.** Most regret comes from skipping one of these three.
- **Recommend by priority, not decree.** There's rarely one right box; there's the right box *for what the
  user weights most*. Make the tradeoff explicit and let them choose.
- **Low MOQ is a feature.** Makers start small. An option with a 5,000 minimum is usually irrelevant to a
  100-unit first run, however lovely — note it as a scale-up option and move on.
- **Don't reinvent the report.** Use the template and the PDF script; spend your effort on the analysis.
