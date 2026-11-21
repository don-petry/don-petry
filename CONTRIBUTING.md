# Contributing

These skills are generic on purpose: nothing in them may identify a household or depend on one
agent vendor. Three gates enforce that, locally and in CI.

| Gate | What it stops | Where |
| :--- | :--- | :--- |
| `tools/check_no_pii.py` | Names, personal email, SSNs, home-network IPs, plus any household rules you add | pre-commit (`--staged`) and CI (every tracked file) |
| `gitleaks` | API keys, tokens, private keys — in the staged change and in the full git history | pre-commit and CI (`secret-scan` job) |
| `tools/lint_skills.py` | Non-standard frontmatter, harness-only tool names or paths, oversize descriptions | pre-commit and CI |

## Set up once per clone

```bash
git config core.hooksPath .githooks     # or: pre-commit install (see .pre-commit-config.yaml)
brew install gitleaks                   # or your platform's package
```

## Your own PII rules

The public checker only knows generic patterns. Add the things only you would recognize — your
family's first names, street, school, employer, account-number formats — to a **gitignored**
`.pii-rules.json` in the repo root:

```json
[
  {"name": "Kid name", "pattern": "\\b(Alexandra|Sam)\\b", "flags": "i"},
  {"name": "Street", "pattern": "Elm Street", "whitelist": ["Elm Street Theater"]}
]
```

In a fork, put the same JSON in a repository secret named `PII_CUSTOM_RULES_JSON` and CI enforces it
without publishing it. Never commit the rules file: it is a list of exactly what you want hidden.

## Personal settings belong in config

A skill that needs household facts reads `skills/<name>/config/household.yaml` (gitignored) and ships
`config/household.example.yaml` with placeholders: `name@example.com`, `205-555-0100`, IPs in
`192.0.2.x`, the NHTSA sample VIN `1HGCM82633A004352`.

## Secrets

Never commit credentials. The `.gitignore` starts with a secrets-only baseline (dotenv files,
cloud keys, token caches, `credentials.*`). If a secret ever lands in a commit, rotate it at the
provider first — removing it from history does not un-leak it.
