# The 14 areas of concern

Each area: what it covers, which advisory team owns it, the documents discovery looks for, and a starter
question bank. The banks hold only the questions discovery is unlikely to answer — every session trims its
bank against the draft state card first, and never asks what the records already say.

Config `areas.<id>` gives each area the household's own name, where its knowledge lands (`lands_in`), the
lead respondent (`lead`) and any household note (`note`).

---

## A1 — People, relationships & authority

**Covers:** who is who; dates of birth and majority dates; residence; custody and guardianship orders;
powers of attorney; who may act for whom, on what document, until when. **Owner:** shared — every team's
capacity gate reads it. **Lands in:** the household facts file.
**Look for:** custody and guardianship orders, letters of guardianship, powers of attorney, adoption and
name-change orders, school and medical authorization forms.

- Is each parent a legal guardian of each child, or a step-parent without an order?
- Does an order cover every child in the house, or only some?
- Where are the signed orders (links)?
- Who holds a power of attorney for any adult the household cares for?
- Who decides for each child in an emergency if both parents are unreachable?

## A2 — Estate

**Covers:** wills, trusts, powers of attorney, advance directives, beneficiary designations, titling.
**Owner:** legal (documents) + tax and wealth (titling, tax). **Lands in:** an estate matter `project.yaml`.
**Look for:** wills, trust instruments and amendments, POAs, health-care directives, beneficiary
confirmations, deeds, account titling.

- Where are the signed originals?
- Were the trusts the documents describe actually created and funded?
- What should change now that the household has changed (a marriage, children joining, a move)?
- Who is named guardian for each minor, and executor and trustee?
- What does each of you want to happen to the home, any rental and any business?

## A3 — Legal matters

**Covers:** open, past and foreseeable matters — claims, disputes, contracts in force, court.
**Owner:** legal. **Lands in:** a matter register plus one `project.yaml` per matter.
**Look for:** demand letters, claim numbers, court notices, contracts and leases, settlement papers.

- Anything in progress or threatened that is not on file?
- Past matters worth remembering (amended returns, claims, record clearing)?
- Contracts in force: builders, leases, informal land or animal arrangements.

## A4 — Money: accounts, income, debts, tax

**Covers:** every account by institution and owner, income sources, debts and rates, filed returns,
savings goals. **Owner:** tax and wealth. **Lands in:** the household's money notes and returns data.
**Look for:** statements, W-2s and 1099s, filed returns, loan documents, planner reports.

- Every account by institution and owner (never credentials).
- Debts and their rates.
- Regular income besides wages.
- Savings goals and timelines; risk tolerance.
- What "financially safe" means to each of you.

## A5 — Insurance & risk

**Covers:** every policy, its limits and deductibles, claims history, gaps. **Owner:** tax and wealth
(adequacy) + legal (claims and disputes). **Lands in:** an insurance matter or notes.
**Look for:** declarations pages, renewal notices, claim letters, loss-history reports.

- Anything missing: life, disability, long-term care, business, umbrella, directors-and-officers cover for
  board roles?
- Who would you call first after a loss, and is that on file?

## A6 — Property

**Covers:** the home, any rental or land, outbuildings, archived former homes; titles, mortgages, projects.
**Owner:** tax and wealth + projects. **Lands in:** the property notes and existing projects.
**Look for:** deeds, closing statements, mortgage statements, leases, permits, contractor agreements.

- Plans for each property: keep, sell, when?
- What each outbuilding or parcel is for.
- History of former homes still worth recording.

## A7 — Work & career

**Covers:** each adult's employer, pay, equity and benefits; job searches and offers; retirement targets.
**Owner:** tax and wealth (money) + legal (agreements). **Lands in:** the career notes and matter projects.
**Look for:** offer letters, pay statements, benefits summaries, equity grants, employment agreements.

- Actual compensation and benefits for each adult.
- Career goals for the next five years.
- Retirement age targets.

## A8 — Kids & education

**Covers:** each child's school, plans, accounts and the adults who act for them. **Owner:** tax and wealth
+ the household's kid tools. **A minor's money is that minor's own matter.** **Lands in:** each child's
notes; a separate project for any child's money.
**Look for:** enrollment records, college-savings statements, IEP or 504 plans, court orders on costs.

- Per child, the one to three things that must go right in the next two years.
- Who pays for what in college?
- Any cost-sharing arrangement with another parent.

## A9 — Elder & dependent care

**Covers:** an aging parent or other dependent adult the household cares for — housing, health facts,
money facts, documents, who holds authority. **No transfers, ever.** **Owner:** legal + tax and wealth.
**Lands in:** that person's own notes plus the household facts file.
**Look for:** guardianship or conservatorship letters, POAs, care-facility agreements, benefit letters.

- Where do they live, and under what agreement?
- Their income sources.
- Their care plan; their doctors and advisors.
- Their own wishes — recorded in their own words, never shaped.

## A10 — Health

**Covers:** coverage, member IDs, providers by role, medications only as far as a team needs them,
HSA/FSA. **Owner:** health. **Lands in:** each person's health notes or health project.
**Look for:** insurance cards, explanations of benefits, plan documents, authorizations to share records.

- Who may talk to each adult child's providers, on what signed authorization?
- Any coverage change expected this year?

## A11 — Vehicles

**Covers:** each vehicle, its title holder, insurance, loans, drivers, and plans. **Owner:** projects.
**Lands in:** the vehicle notes.
**Look for:** titles, registrations, bills of sale, loan statements, service records.

- Which vehicles are actually still owned, and who drives each?
- Why was a title moved between owners, if one was?
- Plans to sell or replace.

## A12 — Community & small business

**Covers:** nonprofit and board roles, volunteer commitments, any side business. **Owner:** legal
(governance) + tax and wealth (tax). **Lands in:** the community and business notes.
**Look for:** bylaws, board minutes, sales-tax registrations, consignment agreements, business ledgers.

- Your role and liability in each organization.
- The business's revenue lines and plans.
- Whether to form an entity (a question for professionals).

## A13 — Digital life & continuity

**Covers:** where things are kept, backups, devices, and who can get in if the person who runs it all
cannot. **Credentials stay in the password manager** — this area records where, never how. **Owner:**
shared. **Lands in:** a continuity note.
**Look for:** backup reports, domain and hosting renewals, device inventories, emergency-access settings.

- If the main administrator were unreachable for a month, what would the other adult need, and where is it?
- Which accounts have an emergency or legacy contact set?

## A14 — Family history & values

**Covers:** heritage, faith, and the principles the household wants applied when a choice is close.
**Owner:** shared context. **Lands in:** the values file if the household keeps one
([`plan.md`](plan.md) §8), otherwise the area's notes.
**Look for:** the household's own written plans, rules or mission statements; family-tree records.

- The principles you want the teams to apply when a choice is close.
- Faith or community commitments that affect giving or estate choices.
- A giving target, and what makes an organization one you give to.
