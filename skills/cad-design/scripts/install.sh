#!/usr/bin/env bash
# Install (or update) the SolidCraft and CADCraft headless CLIs on this Mac and register their
# MCP servers with the agent harness you use. Idempotent: re-run to upgrade.
#
#   scripts/install.sh            # pinned versions below
#   scripts/install.sh --latest   # newest GitHub release of each
#   scripts/install.sh --check    # report what is installed, change nothing
#
# Harness registration: Claude Code is registered automatically when its CLI is on PATH; for any
# other MCP-capable harness (Codex, Gemini CLI, Cursor, VS Code/Copilot, ...) the script prints
# the server definitions to paste into that harness's MCP config.
#
# Layout: ~/.local/share/cad-design/<tool>-<version>/   (unzipped release)
#         ~/.local/bin/solidcraft-cli, cadcraft-cli      (symlinks to the current version)
#         ~/cad-designs/                                 (SolidCraft's only writable folder over MCP)
set -euo pipefail

SOLIDCRAFT_VERSION="0.17.0"   # tangency-labs/solidcraft  (checked 2026-10-20)
CADCRAFT_VERSION="0.8.0"      # storytold/cadcraft        (checked 2026-10-20)
SHARE="$HOME/.local/share/cad-design"; BIN="$HOME/.local/bin"; DESIGNS="$HOME/cad-designs"
MODE="${1:-pinned}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)" >&2; exit 1; }; }
need gh "brew install gh, then gh auth login"; need unzip "part of macOS"; need python3 "part of macOS"
[ "$(uname -s)" = Darwin ] || { echo "this installer covers macOS only; Linux assets exist on both release pages" >&2; exit 1; }

latest() { gh api "repos/$1/releases/latest" --jq .tag_name | sed 's/^v//'; }
if [ "$MODE" = "--latest" ]; then
  SOLIDCRAFT_VERSION="$(latest tangency-labs/solidcraft)"; CADCRAFT_VERSION="$(latest storytold/cadcraft)"
fi

report() { for t in solidcraft-cli cadcraft-cli; do
  if command -v "$t" >/dev/null 2>&1; then printf '%-15s %s  (%s)\n' "$t" "$("$t" --version 2>/dev/null | head -1)" "$(readlink "$BIN/$t" 2>/dev/null || command -v "$t")"
  else printf '%-15s not installed\n' "$t"; fi; done
  if command -v claude >/dev/null 2>&1; then
    echo "Claude Code MCP (user scope):"; claude mcp list 2>/dev/null | grep -E 'solidcraft|cadcraft' || echo "  neither server registered"
  fi; }
if [ "$MODE" = "--check" ]; then report; exit 0; fi

install_one() { # tool repo version asset-name binary
  local tool="$1" repo="$2" ver="$3" asset="$4" dest="$SHARE/$1-$3"
  if [ ! -x "$dest/$tool" ]; then
    local tmp; tmp="$(mktemp -d)"
    echo "downloading $repo v$ver ($asset)"
    gh release download "v$ver" -R "$repo" -p "$asset" -D "$tmp"
    mkdir -p "$dest"; unzip -oq "$tmp/$asset" -d "$tmp/x"
    cp -R "$tmp/x"/*/. "$dest"/; rm -rf "$tmp"
    xattr -dr com.apple.quarantine "$dest" 2>/dev/null || true   # unsigned release; Gatekeeper would block it
    chmod +x "$dest/$tool"
  fi
  mkdir -p "$BIN"; ln -sfn "$dest/$tool" "$BIN/$tool"
  "$BIN/$tool" --version >/dev/null 2>&1 || { echo "$tool does not run after install" >&2; exit 1; }
}
install_one solidcraft-cli tangency-labs/solidcraft "$SOLIDCRAFT_VERSION" "solidcraft-cli-$SOLIDCRAFT_VERSION-macos-universal.zip"
install_one cadcraft-cli   storytold/cadcraft       "$CADCRAFT_VERSION"   "cadcraft-cli-$CADCRAFT_VERSION-macos-universal.zip"
mkdir -p "$DESIGNS"

case ":$PATH:" in *":$BIN:"*) ;; *) echo "note: add $BIN to PATH (zsh: echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc)";; esac

# MCP servers. SolidCraft may only read/write under ~/cad-designs (plus its own scratch and
# recovery folders).
if command -v claude >/dev/null 2>&1; then   # Claude Code: user scope, every session on this machine
  claude mcp remove -s user solidcraft >/dev/null 2>&1 || true
  claude mcp remove -s user cadcraft   >/dev/null 2>&1 || true
  claude mcp add -s user solidcraft -- "$BIN/solidcraft-cli" mcp --allow-path "$DESIGNS"
  claude mcp add -s user cadcraft   -- "$BIN/cadcraft-cli" mcp
fi
cat <<DEFS

MCP server definitions for any other harness:

  JSON (Gemini CLI settings.json, Cursor, VS Code mcp.json, most others) — under "mcpServers":
    "solidcraft": {"command": "$BIN/solidcraft-cli", "args": ["mcp", "--allow-path", "$DESIGNS"]},
    "cadcraft":   {"command": "$BIN/cadcraft-cli",   "args": ["mcp"]}

  TOML (Codex ~/.codex/config.toml):
    [mcp_servers.solidcraft]
    command = "$BIN/solidcraft-cli"
    args = ["mcp", "--allow-path", "$DESIGNS"]
    [mcp_servers.cadcraft]
    command = "$BIN/cadcraft-cli"
    args = ["mcp"]

No MCP at all? scripts/mcpc.py drives either server over stdio (see SKILL.md).
DEFS
report
