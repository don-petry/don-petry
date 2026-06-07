# Finding markets — discovery playbook

The hardest part of market scouting is that the best small/curated markets are **not** indexed by
general web search. They live on Instagram and in local community channels. Cover every channel
below; expect to find different markets in each.

## Channels (in rough order of yield for premium handmade fits)

1. **Instagram-native discovery.** Many markets have no website and are run under a *parent* account:
   - Organizer accounts (e.g., a roving pop-up brand).
   - Neighborhood / town / merchant-association accounts (a market is often promoted under the
     community handle, not a market-specific one).
   - **Brewery event calendars + the brewery's own IG** — breweries host recurring maker markets;
     the brewery's follower count is the real reach signal.
   - Geotags on the venue and local hashtags (e.g., #bhammarket, #shoplocalbham, #<city>market).
2. **Vendor application platforms** — ZAPPlication and Eventeny (juried art/holiday), Submittable
   (Porter Flea-style), EventHub, Marketspread, ManageMyMarket (farmers markets). Searching these by
   region surfaces markets actively recruiting vendors and often their fees.
3. **Official market / festival websites** — for the established juried and holiday shows.
4. **Local roundups** — city "Now" blogs and Mom Collective "holiday markets" / "pop-up markets this
   season" lists catch what search engines miss.
5. **Vendor word-of-mouth / Facebook vendor groups** — frequently the only place booth fees and
   one-day options are stated.

## Regional coverage

Scout the home metro thoroughly, then nearby drivable cities. Out-of-town markets only earn a slot
when the data justifies the drive (they pay a round-trip-hours penalty in the score). For Birmingham:
Tuscaloosa, Huntsville, Auburn, Chattanooga, Atlanta, Nashville/Franklin.

**College towns are a priority lane.** Tuscaloosa (University of Alabama) and Auburn (Auburn
University) are affluent, expendable-income markets that skew eco-friendly / farm-friendly and buy
candles — a strong fit. Scout their game-day markets, downtown merchant associations, and campus-area
pop-ups, but watch the `sport_conflict` flag: home football Saturdays swamp lodging/parking and (for
Auburn) the Iron Bowl already carries the heaviest penalty.

## What to capture per market (so it's ready to Evaluate)

Minimum to add a row: `name`, city, venue, type, and a **source link**. Then, as you research, fill:
- premium/artisan vs family/produce/fine-art positioning;
- IG handle + follower count (and FB);
- booth fee (or "apply-only"), free vs ticketed admission;
- dates (mark announced vs estimated), days, hours/day, one-day option?;
- drive time from home base;
- non-profit/affinity tie; same-day competition; year-over-year momentum signals;
- **junior-vendor / "junior artisan" youth-booth option** — a kid-friendly perk that often isn't
  published; ask the organizer or check vendor groups / prior-year flyers (Bash on the Bluff has one).

## Watch-outs

- **Same-named events in other states** — confirm the city (a "$60 Deck the Heights" booth was a New
  Jersey event; a "$10/day Madison" was Madison *County*, not Madison *City*).
- **Fine-art-only juried shows** look premium but the crowd isn't buying candles/honey — flag
  `fine_art_focus`.
- **Markets that ban candles or body products** — exclude them (verify the vendor rules).
- **Closed/moved markets** — venues sell and markets relocate; verify the current location.
