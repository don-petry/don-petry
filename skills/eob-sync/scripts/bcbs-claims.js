// In-page readers for the Blue Cross claims app (BCBS of Alabama myBlueCross and Credence Blue,
// claims-search.html) — the worked example; write one in this shape for your insurer. Verified 2026-11-08.
// Paste the whole file into the page (JavaScript console, or your agent's run-JavaScript tool) once
// signed in and on the claims page. Read-only: it
// pages the list and opens claim details by clicking the portal's own links; nothing is submitted.
// Each call stops after ~38 s (the tool's limit is 45 s); call again until it reports all claims read.

const __sleep = ms => new Promise(r => setTimeout(r, ms));
const __cardLinks = () => [...document.querySelectorAll('a.inline-link[href*="summary-of-claim"]')];
const __idOf = a => new URLSearchParams(a.href.split('summary-of-claim?')[1]).get('claimNumber');
const __listIds = () => __cardLinks().map(__idOf);
const __waitList = async prev => {
  for (let k = 0; k < 40; k++) { await __sleep(300); const l = __listIds(); if (l.length && l.join() !== prev) return l; }
  return __listIds();
};

// Every claim card on every page: "MM/DD/YYYY|Member|Provider|claim|billed|discount|paid|owe".
window.__listAll = async () => {
  const first = document.querySelector('button[aria-label="First Page"]');
  if (first && !first.disabled) { const p = __listIds().join(); first.click(); await __waitList(p); }
  const rows = new Map();
  const grab = () => {
    const t = document.body.innerText;
    // Credence cards can carry a service span ("04/13/2026 08/17/2026"); the first date is kept.
    const re = /Date\s+Member\s+(\d\d\/\d\d\/\d{4})(?:\s+\d\d\/\d\d\/\d{4})?\s+(.+?)\s+Provider\s+Claim Number\s+(.+?)\s+#(\d+)\s+Billed Charges\s+\$([\d.,]+)\s+(?:Member Discount\s+\(\$([\d.,]+)\)\s+)?Your Benefit Paid\s+\(?\$([\d.,]+)\)?\s+You May Owe\s+\$([\d.,]+)/g;
    let m; while ((m = re.exec(t))) rows.set(m[4], [m[1], m[2], m[3], m[4], m[5], m[6] || '0', m[7], m[8]].join('|'));
  };
  grab();
  for (let i = 0; i < 20; i++) {
    const n = document.querySelector('button[aria-label="Next Page"]');
    if (!n || n.disabled) break;
    const p = __listIds().join(); n.click(); await __waitList(p); grab();
  }
  window.__rows = [...rows.values()];
  return window.__rows.length + ' claims\n' + window.__rows.join('\n');
};

// Open each claim (only those not yet in window.__det) and keep its detail text.
window.__det = window.__det || {};
window.__readAllClaims = async (ids, budgetMs = 38000) => {
  ids = ids || (window.__rows || []).map(r => r.split('|')[3]);
  const t0 = Date.now();
  for (const id of ids) {
    if (window.__det[id]) continue;
    if (Date.now() - t0 > budgetMs) break;
    const back = [...document.querySelectorAll('a,button')].find(x => /Back to Claims Search/i.test(x.innerText));
    if (back) back.click();
    let l = await __waitList('');
    const first = document.querySelector('button[aria-label="First Page"]');
    if (first && !first.disabled && !l.includes(id)) { const p = l.join(); first.click(); l = await __waitList(p); }
    for (let g = 0; g < 20 && !l.includes(id); g++) {
      const n = document.querySelector('button[aria-label="Next Page"]');
      if (!n || n.disabled) break;
      const p = l.join(); n.click(); l = await __waitList(p);
    }
    const a = __cardLinks().find(a => __idOf(a) === id);
    if (!a) return 'not found ' + id;
    a.click();
    let t = '';
    for (let k = 0; k < 40; k++) { await __sleep(300); t = document.body.innerText; if (t.includes('Claim Number\n' + id) && t.includes('Processed Date')) break; }
    const s = t.indexOf('Summary of Claim\n#' + id), e = t.indexOf('EXPLANATION ON HEADINGS', s);
    if (s < 0) return 'no summary ' + id;
    window.__det[id] = t.slice(s, e > 0 ? e : s + 5000);
  }
  return Object.keys(window.__det).length + '/' + ids.length + ' read';
};

// One line per claim: processed date, deductible, discount, per-line SERVICE(billed/eligible[note]/[noncovered/]paid), remarks.
window.__claimLines = () => Object.entries(window.__det).map(([id, t]) => {
  const g = re => (t.match(re) || [])[1] || '';
  const lines = t.split('\nDate of Service\n').slice(1).map(p => {
    const svc = (p.match(/^\n?(.+?)\nServices/) || [])[1];
    const nums = [...p.matchAll(/\$([\d.,]+)\n(Billed Charges|Eligible Charges|Noncovered Charges|Your Benefit Paid)/g)].map(m => m[1]);
    return svc + '(' + nums.join('/') + ')';
  }).join('; ');
  const remarks = [...t.matchAll(/\n\n(\d) ([A-Z][^\n]+)/g)].map(m => m[1] + ': ' + m[2]).join(' || ');
  return [id, g(/Processed Date: (\S+)/), 'ded ' + g(/Applied To Deductible\n\$([\d.,]+)/),
          'disc ' + g(/Member Discount\n\(\$([\d.,]+)\)/), lines, remarks].join('|');
}).join('\n');
'bcbs-claims ready';
