## Hi there 👋 I'm Don Petry

**Principal Engineer, Director, Global Tax Technology + Open Source Contributor** · Birmingham, Alabama

I'm a technologist and engineering leader with ~30 years turning business strategy into technical vision — and, increasingly, into working AI systems. Today I'm leading the agentic transformation of the software delivery lifecycle, and proving those patterns in the open through [combsmith](https://github.com/combsmith): an open-source organization that operates like a full software company staffed by AI agents.

- 📄 **CV:** [CV.md](CV.md)
- 🏢 **GitHub Org:** [github.com/combsmith](https://github.com/combsmith)
- 💼 **LinkedIn:** [linkedin.com/in/donaldpetryiii](https://linkedin.com/in/donaldpetryiii)

If you're working on agentic delivery, engineering transformation, or building teams that grow more capable every quarter, I'd love to compare notes.

## 🧰 Shared Skills

Open-source skills for running a household with an AI agent — buying used, booking flights, keeping
Drive tidy, fixing the printer, designing parts. Each is a folder in the open
[Agent Skills](https://agentskills.io) format, so it works with **Codex, Gemini CLI, GitHub
Copilot, Antigravity, Claude Code** or any harness that reads `SKILL.md`. Nothing depends on one
vendor's tools. MIT licensed.

**Install:** `tools/install-skills.sh <your-project> [skill ...]` links skills into every harness's
folder at once — see [docs/install.md](docs/install.md). Skills that need your details (home
airport, zip, printers) read `config/household.yaml`; copy the `household.example.yaml` beside it,
or let the skill ask you.

| Skill | What it does |
| --- | --- |
| [goods-hunt](skills/goods-hunt/SKILL.md) | Finds and ranks used goods — tractors, furniture, bee gear, anything — by cost per remaining useful life, with domain packs and a valuation/comp mode. |
| [car-hunt](skills/car-hunt/SKILL.md) | Finds and ranks used cars by cost per remaining mile, with reliability research, VIN recall and ownership-cost lookups, and an insurance total-loss comp mode. |
| [flight-price-optimizer](skills/flight-price-optimizer/SKILL.md) | Decides when to buy airfare and which ticket is cheapest all-in (bags, seats together, airport drive), prices flexible dates as a grid, answers drive-vs-fly, and runs a fare watch. |
| [drive-cleanup](skills/drive-cleanup/SKILL.md) | Audits and repairs Google Drive: broken shortcuts, zero-byte files, sync-conflict names, exact duplicates — Trash-only, with an undo log. |
| [drive-ocr](skills/drive-ocr/SKILL.md) | Finds Google Drive PDFs without a text layer, OCRs them with `ocrmypdf`, and replaces them in place — keeping file IDs, names, sharing, and folders. |
| [printer-troubleshooting](skills/printer-troubleshooting/SKILL.md) | Diagnoses and recovers Brother network laser printers: offline, stuck queues (PJL reset), deep sleep, consumables, AirPrint across VLANs. |
| [cad-design](skills/cad-design/SKILL.md) | Drives two open-source CAD apps over MCP to model 3D parts (STEP/STL/3MF) and 2D drawings (DXF/PDF), verifying every stage numerically. |
| [packaging-scout](skills/packaging-scout/SKILL.md) | Researches and scores packaging options (boxes, mailers, jars, labels, void fill) for a product, then delivers a ranked recommendation, sourcing list, and PDF report. |
| [onenote-migration](skills/onenote-migration/SKILL.md) | Migrates a personal Microsoft OneNote account to a Git repo of Markdown files via Microsoft Graph, keeping hierarchy, attachments, and version history. |

**Personas** ([agents/](agents/)) — reviewers any skill can call, or you can read inline:
[red-team](agents/red-team.md) argues the other side of a draft (adjuster, examiner, opposing
party); [source-verifier](agents/source-verifier.md) traces every citation, figure and date to a
primary source.

**Tools** ([tools/](tools/)) — `install-skills.sh` (multi-harness installer), `lint_skills.py`
(the agent-neutral standard CI enforces), `check_no_pii.py` (keeps household data out of commits),
`mojibake_guard.py` (stops agents writing `â€"`/`?` damage into UTF-8 notes). Every commit is
gated by the no-PII check, gitleaks (including full history) and the skill lint — see
[CONTRIBUTING.md](CONTRIBUTING.md).

Every skill keeps the same safety defaults: drafts only (it never sends email or texts), you sign
in to accounts yourself, destructive actions are a dry run until you say yes, and stale data is
labeled with its date.
