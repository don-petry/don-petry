# Portal notes — Blue Cross (BCBS of Alabama "myBlueCross" and Credence Blue)

**A labeled example.** These notes describe one insurer's member portal as it worked when it was read
(2026-11-08 to 2026-11-19). Write `reference/portals/<insurer>.md` in the same shape for yours and point
config `portal_notes` at it. Portals change; re-verify before relying on a URL.

Both portals run the same claims single-page app, so `scripts/bcbs-claims.js` reads either.

## Claims list

- **Dental (myBlueCross):** `https://www.bcbsal.org/web/member/portal/claims-search.html?meganav=true`
  (menu: Claim Statements). 10 cards a page, newest first, about three years back. Each card shows date,
  member, provider, claim number, billed, (member discount), benefit paid and "You May Owe".
- **Medical (Credence):** `https://www.credenceblue.com/web/member/cb-portal/subs-claim-statement-application.html`
  (redirects to `claims-search.html`). The subscriber's login shows every member's claims; a dependent's login
  shows only their own. Some cards carry a service *span* (`04/13/2026 08/17/2026`). Some claim numbers appear
  twice as adjusted versions; keep the later card.
- **Do not open the claim-statement links from the EOB email** without their one-time tokens: they bounce to the
  public home page and drop the session. After sign-in, go only to portal pages.

## Opening a claim

- *Click* the card's "View Claim Details" link. Setting `location.hash` to its href shows the previously opened
  claim, because the app holds the claim in state. "Back to Claims Search" returns to page 1.
- `await __listAll()` lists every card; `await __readAllClaims(<ids>)` pages and clicks, and keeps each detail
  text in `window.__det`; `__claimLines()` prints line items and remarks. A full page load wipes `window.__det`,
  so parse before leaving, and open other pages in a second tab.
- **Detail page:** processed date, deductible applied, per line DATE / SERVICE CATEGORY (PREVENTIVE, DIAGNOSTIC,
  RESTORATIVE, ORTHODONTICS, GENERAL SERVICES) / billed / eligible / noncovered / paid, numbered remarks with
  CARC codes. A line's footnote digit is glued to the next number (`56.001` = $56.00, note 1). The dental EOB
  states no appeal deadline.
- **Patient names** arrive truncated (first names cut short); map them with `plans.yaml` `portal_names`.
- A hidden browser pane throttles timers, so detail reads take about 10 s each; with the pane showing, 50 read in
  under a minute.

## Benefits, accumulators, prior authorization

- **Dental booklet:** View Benefits and Coverage → iframe → `…/webapps/spd/Dispatch?handler=ShowSPD&o=D&ext=.pdf&docIndex=N`.
  An in-page `fetch` works with the session cookie. The individual dental contract had no online accumulator
  page; sum the EOBs instead.
- **Credence:** the account summary shows the family deductible. Out of Pocket Details is an iframe
  (`/webapps/deductible/Dispatch?…ShowOOPDetail`); read it through `contentDocument`. The Prior Authorization
  Tracker shows only what the signed-in member can see — a dependent's authorizations may appear only on that
  dependent's own login.

## EOB PDFs

- **Many at once:** the EOB PDF is the print view
  `/webapps/claimstatements/Dispatch?application=org.bcbsal.claimstatements.SubsClaimStatementApplication&handler=ClaimRetrievalHandler&forPrintView=true&iframerequest=true&claim=default&value=<claim>&prl=<payrollDate>&pfx=<contractPrefix>&num=<contractNumber>&rej=<rejectCode>&adj=<adjudicationDate>&ver=<version>&ind=<claimSplitIndicator>&clmsrc=<claimSource>&sur=`.
  Every parameter comes from the card's `summary-of-claim?…` link, and an in-page `fetch` with the session returns
  `application/pdf` (~0.8 MB each). Browsers block repeated automatic downloads, so fetch the wanted PDFs, pack
  them into one uncompressed ZIP in the page, and click a single blob link; then unzip, rename, upload.
- **One at a time, without a download:** on a claim's detail page the "Print the Explanation of Benefits" link is
  the PDF. Fetch it in-page and return `content-type|length|base64`; decode it locally, check it starts `%PDF-`
  and the length matches. Use the link's own `href`: its dates are ISO timestamps, not `YYYYMMDD`.

## Notice emails

| Sender (mailbox at domain) | Subject | Kind |
| :--- | :--- | :--- |
| claim notifications at `bcbsal.org` | "Blue Cross and Blue Shield Explanation of Benefits" — masked claim number, no amounts | `eob` |
| Blue Cross payments at `bcbsal.org` | "Blue Cross Payment Confirmation" (~2nd–4th of the month) | `premium_paid` |
| Blue Cross payments at `bcbsal.org` | "Blue Cross and Blue Shield of Alabama Payments" (~11th–13th) | `statement` |
| Credence at `info.credenceblue.com` | "View Your Prior Authorization Status Change" | `prior_auth` |

Put the exact sender addresses from your own notices in `plans.yaml` `notices`.

Credence medical EOB notices go to the subscriber's own address, if anywhere.
