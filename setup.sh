#!/usr/bin/env bash
# One entrypoint: get this machine ready, regenerate the Rawy vault, open it.
#
#   bash setup.sh
#
# Three stages, each skippable if already done:
#   1. Environment  — tools/scripts/setup-mac.sh (Homebrew, Python, Codex,
#      PDF tools, Obsidian, pip deps). Idempotent: already-installed pieces
#      are detected and skipped, so re-running this costs seconds, not minutes.
#   2. Vault        — story_pipeline.py build-vault regenerates Rawy's
#      Dashboard, Clients.base config, and every client page from book.json.
#      Nothing here is hand-edited; running it is always safe.
#   3. Open         — launches Obsidian on the Rawy vault so the result is on
#      screen, not just in a terminal.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$ROOT/tools"
PIPELINE="$TOOLS/scripts/story_pipeline.py"
RAWY="$ROOT/Rawy"

BOLD=$'\033[1m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RESET=$'\033[0m'

ok()   { printf '%s✓%s %s\n' "$GREEN" "$RESET" "$*" >&2; }
warn() { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
step() { printf '\n%s==>%s %s\n' "$BOLD" "$RESET" "$*" >&2; }

step "1/3 — البيئة / Environment"
if [[ "$(uname -s)" == "Darwin" ]]; then
  bash "$TOOLS/scripts/setup-mac.sh"
else
  warn "setup-mac.sh targets macOS only — skipping on $(uname -s)."
  warn "Install manually: Python 3.9+, pip install -r $TOOLS/requirements.txt, Codex CLI, Obsidian."
fi

python3 "$PIPELINE" doctor >/dev/null \
  && ok "doctor: البيئة جاهزة / environment ready" \
  || warn "doctor found gaps — see 'python3 $PIPELINE doctor' for detail"

step "2/3 — الفولت / Rawy vault"
python3 "$PIPELINE" build-vault
ok "Dashboard, Clients.base, and every client page regenerated"

step "3/3 — فتح Obsidian / Open Obsidian"
if [[ "$(uname -s)" == "Darwin" ]]; then
  if [[ -d /Applications/Obsidian.app || -d "$HOME/Applications/Obsidian.app" ]]; then
    open -a Obsidian "$RAWY"
    ok "Rawy مفتوح في Obsidian"
  else
    warn "Obsidian غير مثبت — افتحه يدويًا بعد التثبيت: $RAWY"
  fi
else
  warn "Open Obsidian manually and pick this vault: $RAWY"
fi

printf '\n%sجاهز.%s ابدأ من Rawy/Dashboard.md، أو قول \xe2\x80\x9c\xd8\xa7\xd8\xa8\xd8\xaf\xd8\xa3\xe2\x80\x9d للـAgent.\n' "$GREEN" "$RESET"
