// In-page reader for an Alegeus WealthCare portal (*.wealthcareportal.com) — the consumer portal behind
// many HSA / FSA administrators (Alight Smart-Choice is one). Verified 2026-11-08.
// Read-only: two GET endpoints the portal's own Account Activity page calls.
// Open Account Activity in a signed-in session (some administrators open it as a popup that only a human
// click can launch), then paste this whole file into the page's JavaScript console or your agent's
// run-JavaScript tool. The result is one JSON object; save it to a file (agents often spill a reply this
// large to a file on their own) and feed that file to:
//   python3 skills/hsa-fsa-reimburse/scripts/alegeus_sync.py merge <file>
await (async () => {
  const get = async u => (await fetch(u + (u.includes('?') ? '&' : '?') + '_=' + Date.now(),
    { credentials: 'include', headers: { 'X-Requested-With': 'XMLHttpRequest' } })).json();
  const day = s => (s || '').slice(0, 10);
  const txt = s => (s == null ? '' : String(s)).replace(/<br\/?>/g, ' / ').replace(/\s+/g, ' ').trim();
  const accounts = (await get('/Accounts/List')).map(a => ({
    acct: a.AccountName, plan: a.PlanId, start: day(a.PlanStartDate), end: day(a.PlanEndDate),
    election: a.MainFields?.AnnualElection ?? null, deposits: a.MainFields?.PayrollDepositsYtd ?? null,
    spent: a.Spent, available: a.AvailableBalance, total: a.TotalBalance, balance_due: a.BalanceDue,
    portfolio: a.PortfolioBalance, rollover_in: a.MainFields?.RolloverIn ?? null, last_claim: day(a.LastDayToSubmitClaim),
  }));
  const { Years: years } = await get('/AccountActivity/GetYears');
  const activity = [];
  for (const y of years) {
    const q = '/AccountActivity/GetPage?pageParams.pageNo=1&pageParams.pageSize=1000' +
      [1, 2, 4, 5, 3].map((s, i) => `&searchParams.SimplifiedStatuses%5B${i}%5D=${s}`).join('') +
      `&searchParams.Year=${y}&sortParams.Direction=2&sortParams.FieldName=FullDate&withAvailableFilters=true`;
    const page = (await get(q)).Page;
    if (page.Total > page.Data.length) throw new Error(`year ${y}: ${page.Data.length} of ${page.Total} rows`);
    for (const d of page.Data) {
      const c = d.CardTransactionDetails || {};
      activity.push({
        key: d.TransactionKey || '', item: d.ItemId || '', seq: d.SeqNumber, date: day(d.Date), settled: d.SettlementDate || '', type: txt(d.Type), acct: d.AcctTypeCode,
        merchant: txt(c.MerchantName || d.Description), mcc: txt(c.MerchantType), amount: d.Amount,
        paid: d.AccountsPaidAmount, status: txt(d.Status), claimant: txt(d.Claimant),
        svc_start: day(d.ServiceStartDate), svc_end: day(d.ServiceEndDate), provider: txt(d.Provider),
        patient: txt(d.PatientName), balance_due: d.BalanceDue, ineligible: c.IneligibleAmount || 0,
        reason: txt(c.IneligibleReason || d.DenialReason), claim_id: txt(d.ClaimId), receipts: !!d.HasReceipts,
      });
    }
  }
  return JSON.stringify({ captured: new Date().toISOString(), years, accounts, activity });
})();
