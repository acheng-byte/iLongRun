#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT_DIR/scripts/install-bare-commands.sh"
printf '\n---\n\n'
bash "$ROOT_DIR/scripts/install-global-launcher.sh"
printf '\n---\n\n'
if command -v ilongrun-doctor >/dev/null 2>&1; then
  ilongrun-doctor || true
else
  "$HOME/.local/bin/ilongrun-doctor" || true
fi
