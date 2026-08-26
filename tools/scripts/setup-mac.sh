#!/usr/bin/env bash
# Hekayati Mac bootstrap — install everything except `codex login`.
# Usage:
#   bash tools/scripts/setup-mac.sh
#   python3 tools/scripts/story_pipeline.py setup
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS="$ROOT/tools"
REQS="$TOOLS/requirements.txt"
MIN_PY_MAJOR=3
MIN_PY_MINOR=9

BOLD=$'\033[1m'
DIM=$'\033[2m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
RESET=$'\033[0m'

ok()   { printf '%s✓%s %s\n' "$GREEN" "$RESET" "$*" >&2; }
warn() { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
fail() { printf '%s✗%s %s\n' "$RED" "$RESET" "$*" >&2; exit 1; }
step() { printf '\n%s==>%s %s\n' "$BOLD" "$RESET" "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

ensure_path_line() {
  local line="$1"
  local rc=""
  case "${SHELL:-}" in
    */zsh)  rc="$HOME/.zprofile" ;;
    */bash) rc="$HOME/.bash_profile" ;;
    *)      rc="$HOME/.zprofile" ;;
  esac
  touch "$rc"
  if ! grep -Fqx "$line" "$rc" 2>/dev/null; then
    printf '\n# Hekayati / Homebrew / npm\n%s\n' "$line" >>"$rc"
    ok "Added PATH line to $rc"
  fi
  # shellcheck disable=SC2086
  eval "$line"
}

python_ok() {
  local bin="$1"
  "$bin" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
}

pick_python() {
  local cand
  for cand in python3.12 python3.11 python3.10 python3; do
    if have "$cand" && python_ok "$cand"; then
      echo "$cand"
      return 0
    fi
  done
  return 1
}

install_homebrew() {
  if have brew; then
    ok "Homebrew already installed"
    return
  fi
  step "Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    ensure_path_line 'eval "$(/opt/homebrew/bin/brew shellenv)"'
  elif [[ -x /usr/local/bin/brew ]]; then
    ensure_path_line 'eval "$(/usr/local/bin/brew shellenv)"'
  fi
  have brew || fail "Homebrew install finished but brew not on PATH. Open a new terminal and re-run."
  ok "Homebrew ready"
}

install_python() {
  # Prints chosen interpreter path on stdout only (status → stderr via ok/warn).
  step "Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+"
  local py
  if py="$(pick_python)"; then
    ok "Using $($py --version 2>&1) via $py"
    printf '%s\n' "$py"
    return
  fi
  warn "No Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ found — installing via Homebrew"
  brew install python@3.12
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    ensure_path_line 'eval "$(/opt/homebrew/bin/brew shellenv)"'
  fi
  py="$(pick_python)" || fail "Python still missing after brew install"
  ok "Using $($py --version 2>&1) via $py"
  printf '%s\n' "$py"
}

install_node() {
  step "Node.js (needed if Codex installs via npm)"
  if have node && have npm; then
    ok "Node $(node --version) / npm $(npm --version)"
    return
  fi
  brew install node
  ok "Node $(node --version)"
}

install_pdf_tools() {
  step "PDF inspection and rendering (Poppler + qpdf)"
  local missing=()
  if ! have pdftoppm || ! have pdfinfo; then
    missing+=(poppler)
  fi
  have qpdf || missing+=(qpdf)
  if [[ "${#missing[@]}" -eq 0 ]]; then
    ok "pdftoppm, pdfinfo, and qpdf already available"
    return
  fi
  brew install "${missing[@]}"
  have pdftoppm && have pdfinfo && have qpdf \
    || fail "PDF tools still missing after Homebrew install"
  ok "PDF tools installed"
}

install_codex() {
  step "Codex CLI"
  if have codex; then
    ok "Codex already on PATH: $(codex --version 2>/dev/null | head -1 || echo present)"
    return
  fi

  # Prefer official Homebrew cask binary on Mac.
  if brew install --cask codex; then
    if have codex; then
      ok "Codex installed via Homebrew cask"
      return
    fi
  fi

  warn "Brew cask failed or codex not on PATH — falling back to npm"
  have npm || fail "npm missing; cannot install Codex"
  mkdir -p "$HOME/.local"
  npm install -g --prefix "$HOME/.local" @openai/codex
  ensure_path_line 'export PATH="$HOME/.local/bin:$PATH"'
  export PATH="$HOME/.local/bin:$PATH"
  have codex || fail "codex still not on PATH after npm install"
  ok "Codex installed via npm → $HOME/.local/bin/codex"
}

install_python_deps() {
  local py="$1"
  step "Python packages (images, PDF, Arabic shaping)"
  [[ -f "$REQS" ]] || fail "Missing $REQS"
  "$py" -m pip install --upgrade pip >/dev/null
  "$py" -m pip install -r "$REQS"
  "$py" - <<'PY'
from PIL import Image  # noqa: F401
import arabic_reshaper  # noqa: F401
from bidi.algorithm import get_display  # noqa: F401
import reportlab  # noqa: F401
import pypdf  # noqa: F401
print("imports ok")
PY
  ok "Python deps installed"
}

check_dispatch() {
  step "codex-imagegen dispatch"
  local personal="$HOME/.cursor/skills/codex-imagegen/scripts/dispatch.py"
  if [[ -f "$personal" ]]; then
    ok "Found $personal"
  else
    fail "codex-imagegen dispatch.py not found under ~/.cursor/skills; install the Codex imagegen skill for this user"
  fi
}

check_login() {
  step "Codex login (manual — not automated)"
  if ! have codex; then
    warn "codex missing — skip login check"
    return 1
  fi
  local status
  status="$(codex login status 2>&1 || true)"
  if printf '%s' "$status" | grep -qiE 'logged in|authenticated|yes'; then
    ok "Already logged in"
    printf '%s\n' "$status" | sed 's/^/    /'
    return 0
  fi
  warn "Not logged in yet. After this script finishes, run:"
  printf '    %scodex login%s\n' "$BOLD" "$RESET"
  return 1
}

print_summary() {
  local py="$1"
  local logged_in="$2"
  printf '\n%s────────────────────────────%s\n' "$DIM" "$RESET"
  printf '%sHekayati setup complete%s\n' "$BOLD" "$RESET"
  printf '  python:  %s (%s)\n' "$("$py" --version 2>&1)" "$py"
  printf '  codex:   %s\n' "$(have codex && (codex --version 2>/dev/null | head -1) || echo MISSING)"
  printf '  tools:   %s\n' "$TOOLS"
  printf '  verify:  python3 %s/scripts/story_pipeline.py doctor\n' "$TOOLS"
  if [[ "$logged_in" -eq 1 ]]; then
    printf '\n%sReady.%s قول ابدأ في Cursor.\n' "$GREEN" "$RESET"
  else
    printf '\n%sNext (only remaining step):%s\n' "$BOLD" "$RESET"
    printf '  codex login\n'
    printf '  ثم ابدأ كتاب: ابدأ / start في Cursor مع skill hekayati\n'
  fi
}

main() {
  step "Hekayati Mac setup"
  printf '  repo: %s\n' "$ROOT"

  [[ "$(uname -s)" == "Darwin" ]] || fail "This script is for macOS only (got $(uname -s))"

  install_homebrew
  local py
  py="$(install_python)"
  [[ -n "$py" ]] || fail "Could not resolve python binary"
  install_node
  install_pdf_tools
  install_codex
  install_python_deps "$py"
  check_dispatch

  local logged_in=0
  if check_login; then
    logged_in=1
  fi

  print_summary "$py" "$logged_in"
}

main "$@"
