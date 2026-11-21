# car-hunt — Reliability Research sources and card format (Step 1)

Read this when running Step 1 of `../SKILL.md`.

### Sources to Query (run all in parallel via WebSearch)

For each make/model in `MAKES_MODELS`, run these searches simultaneously:

| Source | Search query |
|--------|-------------|
| Consumer Reports | `"{make} {model} reliability by year" site:consumerreports.org` |
| JD Power | `"{make} {model} dependability rating" site:jdpower.com` |
| Edmunds | `"{year_min}-{year_max} {make} {model} long-term reliability" site:edmunds.com` |
| RepairPal | `"{make} {model} reliability rating common problems" site:repairpal.com` |
| CarComplaints | `"{make} {model} worst years problems" site:carcomplaints.com` |
| Owner forums | `"{make} {model} years to avoid reddit OR forum"` |

For each source hit, WebFetch the top result and extract:
- **Best model years** (rated reliable / low complaint rate)
- **Worst model years** (high complaints / known defects / TSBs)
- **Top 3 recurring issues** (e.g., "transmission shudder," "oil consumption," "AC compressor failure")
- **Generation boundaries** (e.g., "10th gen Civic = 2016–2021")

### Output — Reliability Card Per Model

After research, output one card per make/model before proceeding to listing search:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RELIABILITY CARD: {Make} {Model}
  Sources: Consumer Reports · JD Power · RepairPal · CarComplaints
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ BEST YEARS TO BUY (within {year_min}–{year_max}):
  {year_a}, {year_b}, {year_c} — {reason, e.g. "10th gen refresh, highest CR score"}

⚠️  YEARS TO APPROACH WITH CAUTION:
  {year_x} — {specific issue, e.g. "transmission shudder reported above 60k miles"}
  {year_y} — {specific issue}

🚫 YEARS TO AVOID (if any in range):
  {year_z} — {reason, e.g. "first model year of gen — high TSB rate"}

🔧 COMMON PROBLEMS (any year):
  1. {problem} — {how common, severity}
  2. {problem}
  3. {problem}

📊 RELIABILITY SCORE:
  RepairPal: {X}/5.0 | JD Power: {X}/100 | CR: [Recommended / Not Recommended]

💡 BUYING TIP:
  {1 sentence: e.g. "Skip 2017, prioritize 2019–2021 — post-recall fix and strong resale"}
```
