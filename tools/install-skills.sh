#!/usr/bin/env bash
# Link skills (and personas) from this clone into a project, for every agent harness at once.
#
#   tools/install-skills.sh <project-dir> [skill ...]      # no skills named = all of them
#   tools/install-skills.sh --user [skill ...]             # your home directory (all projects)
#   tools/install-skills.sh --copy <project-dir> [skill ...]   # copy instead of symlink
#
# Where each harness looks (Agent Skills format, https://agentskills.io):
#   .agents/skills/<name>   Codex, Gemini CLI, Antigravity, GitHub Copilot
#   .claude/skills/<name>   Claude Code
#   .agents/agents, .claude/agents, .gemini/agents, .github/agents   personas (always copied)
# Symlinks keep the project current with `git pull` in this clone; --copy makes a snapshot.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
MODE=link
[ "${1:-}" = "--copy" ] && { MODE=copy; shift; }
[ $# -ge 1 ] || { sed -n '2,13p' "$0"; exit 2; }
if [ "$1" = "--user" ]; then DEST="$HOME"; else DEST="$(cd "$1" && pwd)"; fi
shift
SKILLS=("$@")
[ ${#SKILLS[@]} -gt 0 ] || SKILLS=($(cd "$SRC/skills" && ls -d */ | tr -d /))

place() {  # place <source> <target>
  mkdir -p "$(dirname "$2")"
  if [ -e "$2" ] || [ -L "$2" ]; then
    if [ -L "$2" ] && [ "$(readlink "$2")" = "$1" ]; then echo "ok      $2"; return; fi
    echo "skip    $2 (exists; remove it to replace)"; return
  fi
  if [ "$MODE" = copy ]; then cp -R "$1" "$2"; echo "copied  $2"; else ln -s "$1" "$2"; echo "linked  $2"; fi
}

for s in "${SKILLS[@]}"; do
  [ -f "$SRC/skills/$s/SKILL.md" ] || { echo "no such skill: $s" >&2; exit 1; }
  for h in .agents .claude; do place "$SRC/skills/$s" "$DEST/$h/skills/$s"; done
  if [ -f "$SRC/skills/$s/config/household.example.yaml" ] && [ ! -f "$SRC/skills/$s/config/household.yaml" ]; then
    echo "        $s: copy config/household.example.yaml to config/household.yaml and fill it in"
  fi
done
# Personas are always copied: Gemini CLI silently skips per-file symlinks.
for p in "$SRC"/agents/*.md; do
  [ -e "$p" ] || continue
  for h in .agents .claude .gemini .github; do
    t="$DEST/$h/agents/$(basename "$p")"; mkdir -p "$(dirname "$t")"
    if [ -e "$t" ] && ! cmp -s "$p" "$t"; then echo "skip    $t (differs; remove it to replace)"; else cp "$p" "$t"; echo "copied  $t"; fi
  done
done
