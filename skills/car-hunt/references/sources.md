# car-hunt — per-source search mechanics (Step 2)

`{city}`, `{state_name}` and the other `CONFIG.*` values come from `config/household.yaml` (see `../SKILL.md` → Household Config).

Read this when running Step 2 of `../SKILL.md`. It holds the details for each listing source; the cross-source rules (data to extract, distance cap, disqualification, parallel strategy) stay in `SKILL.md`.

### AutoTrader

AutoTrader search result pages are JavaScript-rendered and return no usable listing data via WebFetch. **Do not attempt to WebFetch AutoTrader search pages** — always use the WebSearch approach below.

**Reliable approach — WebSearch to find individual listing pages:**

```
WebSearch: site:autotrader.com used {year_min}-{year_max} {make} {model} under ${max_price} {CONFIG.location.search_terms} OR "{nearest city}"
```

Examples:
```
site:autotrader.com used 2002-2015 honda accord under $6000 {city} {state_name}
site:autotrader.com used 2002-2015 toyota camry under $6000 {state_name}
site:autotrader.com used 2002-2015 honda civic 100000 miles {city}
```

From WebSearch results, collect individual AutoTrader listing URLs (format: `autotrader.com/cars-for-sale/vehicledetails.xhtml?listingId=...`). Then WebFetch each listing page — individual pages have price, mileage, trim, and dealer info embedded in the HTML. Extract those fields.

**Run 2–3 WebSearch queries per model** (vary location terms and year ranges) to maximize coverage. Individual listing pages are far more reliable than search results pages.

**AutoTrader outage handling:** If AutoTrader returns 503 / "currently unavailable" for multiple fetch attempts, note the outage in the results summary and continue with other sources. Do NOT skip the whole search — fall back to WebSearch for any individual listing URLs that may still be cached in search indexes.

### CarGurus

**⚠️ DEPRECATED for routine hunting (2026-06-11).** CarGurus' search URL format changes constantly and now redirects to the new-cars landing page, returning no usable listings; automated runs repeatedly logged it `degraded`. Auto.dev covers the same dealer inventory more reliably. Do NOT search CarGurus in the automated/scheduled car-hunt. (This deprecation applies ONLY to routine hunting — **Insurance Claim Comp mode still uses CarGurus** for its sold-listing data and Instant Market Value, which remain valuable there.)

For reference, the legacy routine-hunt approach was: CarGurus search page URL structure changes frequently — the `nl-Used-{Make}-{Model}?zip=...` pattern often 404s. Use WebSearch to find the current working URL:

```
WebSearch: site:cargurus.com used {make} {model} {year_min}-{year_max} {CONFIG.location.search_terms} under ${max_price}
```

From results, collect individual listing URLs (format: `cargurus.com/Cars/new/nl-Used-{Make}-{Model}-d{id}#listing={listingId}`). WebFetch each listing page — CarGurus individual listing pages contain price, mileage, trim, dealer, and posted date in page metadata.

Run 2–3 WebSearch queries per model varying year ranges. If search results surface a working CarGurus search page URL, WebFetch it to extract multiple listings at once.

### Facebook Marketplace

Facebook Marketplace is login-gated. **Individual listing URLs (`facebook.com/marketplace/item/...`) are not publicly accessible** — WebFetch will hit a login wall and return no data. Never put a generic `facebook.com/marketplace` placeholder URL in the output. The link column must contain either a real item URL or "Search manually."

**What actually works:**

**Option A — Google indexes some public listings:**
```
WebSearch: site:facebook.com/marketplace/item {make} {model} {year_range} {city}
```
Example:
```
site:facebook.com/marketplace/item "Toyota Camry" "2012" OR "2013" {city} {state_name}
```
If real `facebook.com/marketplace/item/{id}` URLs appear in search results, record them. Attempt WebFetch — if it returns listing data, extract it. If it redirects to a login page, still record the URL in the Link column so the user can open it themselves.

**Option B — Provide the search URL for manual browsing:**
If Google returns no results, include one row in the output table:
```
| — | Facebook Marketplace | — | — | — | — | — | — | — | {city} | — | https://www.facebook.com/marketplace/{city_id}/vehicles?minYear={YEAR_MIN}&maxPrice={MAX_PRICE} | Manual search required — FB Marketplace not publicly scrapeable |
```
This tells the user exactly where to look without fabricating listings.

**Why FB Marketplace matters:** Private-party listings often appear only here at prices well below dealer, with CPM 20–40% better than comparable dealer listings. Always attempt it and always report the outcome honestly.

**Option C — drive a logged-in browser session with a browser-automation tool (preferred when one is available):**

This is what actually works. Use the numeric city ID (`CONFIG.location.fb_marketplace_city_id`) directly and apply all filters in the URL:

```
https://www.facebook.com/marketplace/{CITY_ID}/search?query={make}+{model}&daysSinceListed={N}&maxPrice={MAX_PRICE}&minPrice={MIN_PRICE}&maxMileage={MAX_ODO}&minYear={YEAR_MIN}&radiusKM={RADIUS_KM}&sortBy=creation_time_descend
```

Then via JS in the tab, scroll to load lazy results and extract `<a href="/marketplace/item/{id}/">` URLs plus the brief preview text from each card.

**Critical operational facts (learned the hard way):**

- **City slugs are ambiguous.** `/marketplace/{city-slug}/...` is disambiguated by your IP/cookies and can resolve to a same-named city in another country (a US city slug landing on its UK namesake has happened). **Always use the numeric city ID** from `CONFIG.location.fb_marketplace_city_id`. Look up the numeric ID for any metro by visiting the city's marketplace page in a logged-in browser once and reading it from the URL after FB redirects.
- **The `query=` parameter on `/marketplace/{cityId}/vehicles?...` URLs is silently dropped by the redirect.** Use `/marketplace/{cityId}/search?query=...` instead — same filters, query is honored. The URL gets rewritten to `/marketplace/category/search/?...` after page render, but the actual filtered results respect the query.
- **`daysSinceListed=1`** filters to last 24 hours and is honored.
- **The `radiusKM` parameter takes kilometers, not miles** — 100mi ≈ 160km.
- Some browser-automation tools refuse to return a value that contains a URL with query parameters (one reports `[BLOCKED: Cookie/query string data]`). Strip URLs from returned strings, or write the URL to `window.__foo` and inspect via a separate call.

**Discontinued makes — Scion (issue #31).** Toyota killed Scion in 2016, so FB Marketplace has **no make/model facet for Scion** — the structured `vehicles?make=...` filter returns nothing. Find them with a **free-text** query instead, one per model:

```
https://www.facebook.com/marketplace/{CITY_ID}/search?query=Scion+tC&maxPrice={MAX_PRICE}&minYear={YEAR_MIN}&radiusKM={RADIUS_KM}&sortBy=creation_time_descend
https://www.facebook.com/marketplace/{CITY_ID}/search?query=Scion+xD&maxPrice={MAX_PRICE}&minYear={YEAR_MIN}&radiusKM={RADIUS_KM}&sortBy=creation_time_descend
```

Free-text search is **fuzzy** — it returns non-Scion noise (random Toyotas, anything sharing a token). **Post-filter every card** through the tested helper `skills/car-hunt/sources/scion.py` → `is_genuine_scion(card_text, model)` (or `filter_scion(cards, model)`): it keeps only real Scions **of the requested model** (a "tC" query won't accept an xB, and "Toyota Camry" noise is dropped). Unit-tested in `sources/test_scion.py`.

Then run the surviving Scion cards through the **same mileage extraction** as every other model so they get a CPM and rank normally (Scion tC/xD share the **250,000-mi** expected-life bucket — see the expected-miles table). Do **not** drop them as "mileage unavailable": if a card hides the odometer, open the listing (or message) to get it, exactly as for Honda/Toyota. Auto.dev still covers Scion via its normal `--make Scion --model tC|xD` query — keep using it; this fixes the FB private-party gap.

**Inline message composer (Step 7 outreach) — what actually works:**

After clicking the listing's "Message" button, the composer appears as an inline field to the right of the listing details (typically `top:~798, left:~1180, width:~406`). FB seeds it with a **generic prefill** — historically "Hi, is this available?", more recently "Hello, is this still available?". **That prefill must NEVER be what we send** (see the fail-closed guard below — sending it both spams the seller with a useless message and breaks thread attribution downstream). To replace it:

1. **Find the field, textarea OR contenteditable** (FB has shipped both). Try `document.querySelectorAll('textarea')` first; if none is visible, fall back to `document.querySelectorAll('[contenteditable="true"][role="textbox"]')`. Filter for visible (`r.width > 50 && r.height > 10`).
2. **Set the value the way the field type requires** — `el.value = msg` does NOT work on either:
   - **textarea (React-controlled):** prototype setter `Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, msg)`, then dispatch `new Event('input', {bubbles: true})` and `new Event('change', {bubbles: true})`.
   - **contenteditable:** focus it, select-all and delete any prefill, then insert text via `document.execCommand('insertText', false, msg)` (fires the React input path); if that's unavailable, set `el.textContent = msg` and dispatch a bubbling `new InputEvent('input', {bubbles: true})`.
3. **🛑 FAIL-CLOSED VERIFY BEFORE SENDING.** Re-read the field's current content (`ta.value` or `el.textContent`). Proceed to send **only if** it contains our distinctive opener text (match on a stable fragment from `CONFIG.outreach.opener_fingerprint`). If it is empty, still shows a generic availability prefill (matches `/is this( still)? available/i`), or doesn't contain our fragment → **DO NOT click send.** Abort this listing, record the outreach entry as `"sent": false` with a `"FAILED: composer not set"` note, and move on. Never send the prefill.
4. The send button is `document.querySelector('[aria-label^="Send message to"]')` (its label is `"Send message to {Seller Name}"`). Click it only after step 3 passes.
5. Confirm send by checking `/Message again/.test(document.body.innerText)` after a 2.5s delay.

**Seller name extraction for personalization:** The seller's full name appears in the page text after the literal string `"Seller details "`. Match `/Seller details ([^()\n]+?)(?:\(|Joined|Profile|Message|$)/` and split the captured name on whitespace — first whitespace-delimited token is the first name. If that match fails, fall back to `[aria-label^="Send message to"]` and parse the suffix after `"to "`.

**Seller profile extraction (for Seller Trust Score — Step 3, Option C only):** This extraction is only possible when using Option C (a browser-automation tool with a live logged-in session). Options A and B have no sidebar to extract from — default those to NEUTRAL. After extracting listing fields, extract seller profile signals from the same "Seller details" sidebar. Run these against `document.body.innerText`:

```
/Joined Facebook (\d+) (year|month)s? ago/i
/Joined Facebook (\d+) weeks? ago/i
/Joined Facebook \d+ days? ago/i
/(\d+\.\d+) \((\d+) ratings?\)/i
/(\d+) active listings?/i
```

Convert to canonical form:
- "Joined Facebook 3 years ago" → `joined_months = 36` (multiply years × 12)
- "Joined Facebook 1 year ago" → `joined_months = 12`
- "Joined Facebook 8 months ago" → `joined_months = 8`
- "Joined Facebook N weeks ago" → `joined_months = 0` (force CAUTION — account is days/weeks old)
- "Joined Facebook N days ago" → `joined_months = 0` (force CAUTION)
- Rating not found → `fb_rating = null`, `fb_rating_count = 0`
- Active listings not found → `active_listings = null` (not a flag — treated as low)

**Failure handling:** If any regex fails (login wall crept in mid-session, React re-render changed DOM), default `seller_trust = NEUTRAL` and note `(profile unreadable)` in the Seller column. Never retry or block — one extraction attempt per listing, then move on.

**Already-messaged detection:** `Message again` appearing on the listing page means a prior message was sent in this account. Always check this before opening the composer; never message twice. Also cross-check the sheet's `Contacted` column.

**Stale composer state:** If a prior listing's composer is still floating in the page, you may see its `aria-label` ("Write to {Name} · 2008 Honda Accord") on the contenteditable element. That's a different, dismissible chat panel — the inline `<textarea>` for the *current* listing is the one to target. Don't be misled by the contenteditable.

### Craigslist

> ⚠️ **The modern `/search/cta` page is a JavaScript app.** A plain WebFetch of the search URL now often returns a **thin (~a few KB) shell with zero listing anchors** — that is bot/JS gating, **not** "no inventory" (issue #30). Treat a thin shell, or 0-from-Craigslist while other sources returned N, as **blocked**: surface it as such and fall through to the fallbacks below. **Never silently report "0 listings".**

**Authoritative guard — use the tested helper, not eyeballing.** Run each fetched search page through `skills/car-hunt/sources/craigslist.py`: `extract_listing_urls(html, region=...)` pulls individual listing URLs (tolerant of absolute *and* root-relative `/{sub}/d/{slug}/{id}.html`, and section-code agnostic), and `diagnose(html, other_sources_total=N)` returns `ok` | `empty` | `blocked_or_gated`. Drive the run-summary wording from its verdict — on `blocked_or_gated`, log e.g. `Craigslist: BLOCKED/gated (thin HTML, N KB, 0 links) — not zero inventory` rather than "0 results". (Unit-tested in `sources/test_craigslist.py` against a representative gallery fixture + the thin shell, so a future markup/selector change is caught as a test regression.)

**Approach 1 — WebFetch the regional search pages** (still works when not gated; plain HTML with real listing URLs). Paginate with `&s=120`, `&s=240`, … until the advertised count is exhausted:

```
https://{region}.craigslist.org/search/cta?query={make}+{model}&max_price={MAX_PRICE}&auto_miles_max={MAX_ODOMETER}&sort=priceasc
```

Run one URL per `{region}` in `CONFIG.location.craigslist_regions` (the home region plus drivable neighbors), e.g.:

```
https://atlanta.craigslist.org/search/cta?query=honda+civic&max_price=6000&auto_miles_max=250000&sort=priceasc
```

Run `diagnose()` on each page. If `ok`, extract the individual URLs and WebFetch each (individual listing pages are still plain HTML — price, odometer, year, description, post date). If `blocked_or_gated`, do NOT stop — go to Approach 2.

**Approach 2 — browser fallback (browser automation, when available).** The thin-shell gate only blocks headless WebFetch; a real browser runs the JS and renders results. Open the same `/search/cta?...` URL in the browser tab (the same mechanism Facebook uses above), scroll to load results, and extract anchors via JS: `document.querySelectorAll('a[href*="/d/"]')`, keeping hrefs matching `/d/.../<digits>.html`. Feed the rendered HTML back through `diagnose()` to confirm.

**Approach 3 — WebSearch fallback** (last resort; often returns category pages, not individual listings): `site:craigslist.org "{make} {model}" "{year}" "{city}" -"wanted"`.

**Link rule:** Use only the exact URL scraped/rendered from the page. Never construct or guess a Craigslist listing URL — IDs are not predictable and a wrong ID is a 404.

### Auto.dev (dealer inventory — structured API)

Auto.dev's listings API provides clean, structured dealer inventory without JS rendering or scraping fragility. It **complements** private-seller sources (Craigslist, FB Marketplace) rather than replacing them — its coverage skews toward dealer lots.

**Check auth first:**
```bash
npx @auto.dev/sdk whoami 2>&1
```
If not logged in, skip this section and note "Auto.dev: skipped (not logged in)" in the Step 2 summary.

**Run one model first to inspect field names:**
```bash
npx @auto.dev/sdk listings --make Honda --model Civic --limit 1 --json 2>&1
```
Verify the actual JSON field paths for price, mileage, year, trim, location, and listing URL before building the full query.

**Full search per make/model:**
```bash
npx @auto.dev/sdk listings \
  --make {make} \
  --model {model} \
  --year {YEAR_MIN}-{YEAR_MAX} \
  --price 0-{MAX_PRICE} \
  --miles 0-{MAX_ODOMETER} \
  --state {CONFIG.location.state} \
  --sort "price:asc" \
  --limit 50 \
  --json 2>&1
```

Run one query per (make, model) pair. Run all in parallel.

**Extract per listing:**
- `price`, `mileage` (odometer), `year`, `make`, `model`, `trim`, `location` (city/state), `listing URL` or dealer name
- Mark `dealer` column as the dealership name (Auto.dev listings are dealer inventory; mark `Private? = No`)
- `retailListing.miles` field path; `vehicle.year/make/model/trim`; `retailListing.price/city/state/dealer`

**⚠️ 0-miles guard:** Auto.dev sometimes returns `"miles": 0` for listings where the dealer didn't report odometer data. A 0-miles reading is **not** a new car — it means the mileage is unknown. **Skip CPM calculation for any listing where `miles == 0`**; include the listing in a separate "Mileage not reported" section at the end of Step 2 output. Do NOT let these rank #1 — at 0 miles the CPM formula produces an artifically low number (e.g., $3,500 / 250,000 = $0.014/mi) that is meaningless.


**Deduplication:** If a listing URL from Auto.dev matches one already found via AutoTrader or CarGurus scraping, keep the scraped version (richer description for disqualification scanning) and note "also on Auto.dev" in Notes.

**Why this matters:** When AutoTrader/CarGurus scraping fails (JS rendering issues, 503s, URL structure changes), Auto.dev provides a stable structured fallback for dealer listings.

### WebSearch Fallback (any source)

If a source's page is unreachable or returns no data, fall back to WebSearch:

```
used {year_min}-{year_max} {make} {model} under ${max_price} {CONFIG.location.search_terms} site:autotrader.com
used {make} {model} {year_range} ${max_price} {city} site:cargurus.com
used {make} {model} {year_range} {state_name} craigslist.org
```

Then WebFetch individual listing URLs surfaced by the search results.

### Distance estimation (Nominatim + Haversine)

After collecting all unique listing cities, geocode them in bulk and compute driving-distance estimates. The cap and display rules are in `../SKILL.md` → Distance Estimation.

**Step 1 — Geocode user ZIP:**
```
GET https://nominatim.openstreetmap.org/search?postalcode={ZIP}&countrycodes=us&format=json
```
Extract `lat` and `lon` for the user's home location.

**Step 2 — Geocode each unique listing city (run in parallel):**
```
GET https://nominatim.openstreetmap.org/search?q={city},{state}&countrycodes=us&format=json&limit=1
```
Extract `lat` and `lon` for each city. Cache results — if two listings share the same city, only geocode once.

**Step 3 — Compute distance via Haversine, then apply road correction:**
```python
import math

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

straight_line = haversine(user_lat, user_lon, listing_lat, listing_lon)
driving_est   = round(straight_line * 1.3)  # 1.3 correction factor for road routing
```

### Disqualification keyword lists

Documentation for the hard filters summarized in `../SKILL.md` Step 2. The authoritative gate is `qualification/listing_filter.py`.

1. **Dealer/finance language:** Any mention of "down payment," "monthly payment," "buy here pay here," "BHPH," "in-house financing," or "we finance" → skip. These are dealer tactics, not private party.
2. **Title problems:** Any mention of "no title," "lost title," "salvage," "rebuilt title," "lien," or "lien release" → skip. Clean title is required.
3. **Non-running / major mechanical:** Any mention of **"doesn't run," "does not run," "not running," "non-running," "non-runner,"** "won't crank," "will not crank," "won't start," "doesn't start," "no start," "won't move," "doesn't move," "won't shift," **"project car," "mechanic special," "parts car," "parts only," "for parts,"** "needs motor," "needs engine," "needs transmission," "blown engine/motor/transmission," "blown head gasket," "seized," "locked up," "rod knock," "engine knock," "transmission is shot/gone," "needs work to run," "non-op," "ran when parked," "needs to be towed," "must be towed" → skip. The buyer needs a running car. (This is the phrasing that has slipped through — "doesn't run" and "project car" are the most common.)
4. **Scam signals:** Any of the following redirect patterns → skip immediately, do not contact:
   - "Messenger broken" / "my messenger doesn't work" / "can't receive messages"
   - "Contact me at [email]" or "email only" when posted on a platform with messaging
   - Asks to text an out-of-platform number as the only contact method with urgency
   - Price is dramatically below market for no stated reason (e.g., "selling quick, moving")
5. **Mileage/data inconsistency:** Mileage that is implausibly low for the model year (e.g., <30K mi on a vehicle 10+ years old) without explicit explanation (low-mileage garage queen, second car with documented service history) → flag as potential typo or rollback and skip auto-contact. Log for human review.
