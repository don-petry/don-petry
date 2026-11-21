# Installing these skills

Every skill here is a folder in the [Agent Skills](https://agentskills.io) format: a `SKILL.md`
(frontmatter `name` and `description`, then instructions) plus optional `scripts/`, `references/`,
`assets/` and `config/`. Any harness that reads that format can use them. Nothing in a skill
depends on one vendor's tools; where a skill needs a capability (web search, a browser, Google
Drive, a calendar), it says so in words and lists ways to provide it.

## Quick start (all harnesses at once)

```bash
git clone https://github.com/don-petry/don-petry.git ~/src/don-petry-skills
~/src/don-petry-skills/tools/install-skills.sh ~/my-project              # every skill
~/src/don-petry-skills/tools/install-skills.sh ~/my-project flight-price-optimizer goods-hunt
~/src/don-petry-skills/tools/install-skills.sh --user                    # all projects (home directory)
```

The script symlinks each skill into both discovery folders, so a `git pull` in the clone updates
every project. Use `--copy` for a snapshot instead. Personas in `agents/` are copied.

## Where each harness looks

| Harness | Project skills | Personas |
| :--- | :--- | :--- |
| Codex | `.agents/skills/<name>/` | `.codex/agents/*.toml` pointing at `agents/<name>.md` |
| Gemini CLI | `.agents/skills/<name>/` | `.gemini/agents/` |
| GitHub Copilot | `.agents/skills/<name>/` | `.github/agents/` |
| Antigravity | `.agents/skills/<name>/` | `.agents/agents/` |
| Claude Code | `.claude/skills/<name>/` (user level: `~/.claude/skills/`) | `.claude/agents/` |
| Anything else | Paste `SKILL.md` into the project instructions; run the scripts yourself | Read the persona file inline |

`--user` installs into the same folders under your home directory; whether a harness reads
user-level skills from there varies, so check its documentation.
Harness conventions move quickly; check your harness's documentation if a folder above is not
picked up.

## Your household's settings

Skills that need personal facts (home airport, zip code, printers, Drive folders) read
`config/household.yaml` inside the skill folder. Each ships `config/household.example.yaml`:

```bash
cp skills/flight-price-optimizer/config/household.example.yaml \
   skills/flight-price-optimizer/config/household.yaml
```

Or just run the skill: when the file is missing it copies the example and asks you for the values.
`config/household.yaml` is git-ignored in this repo, so your details never land in a commit here.

## Scripts and dependencies

Scripts are Python 3.9+ or POSIX shell. Most use only the standard library; a skill that needs more
says so in its `SKILL.md` and ships a `requirements.txt`. Run scripts from the skill folder.

## Safety defaults every skill keeps

- Drafts only: no skill sends email or texts on its own.
- No skill types a password into a sign-in form; you sign in, the agent reads.
- Destructive actions (delete, trash, overwrite) run as a dry run first and need your explicit yes.
- Stale data is labeled with its date, never presented as current.
