#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HOME/.local/bin"

backup_if_needed() {
  local target="$1"
  if [ -L "$target" ]; then
    rm -f "$target"
    return
  fi
  if [ -e "$target" ]; then
    local backup="${target}.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$target" "$backup"
    printf 'Backed up existing path: %s -> %s\n' "$target" "$backup"
  fi
}

for name in ilongrun ilongrun-prompt ilongrun-resume ilongrun-status ilongrun-doctor copilot-ilongrun; do
  backup_if_needed "$HOME/.local/bin/$name"
  cp "$ROOT_DIR/scripts/$name" "$HOME/.local/bin/$name"
  chmod +x "$HOME/.local/bin/$name"
done

printf 'Installed launchers into %s\n' "$HOME/.local/bin"
printf 'Commands:\n'
printf '  ilongrun\n'
printf '  ilongrun-prompt\n'
printf '  ilongrun-resume\n'
printf '  ilongrun-status\n'
printf '  ilongrun-doctor\n'
printf '  copilot-ilongrun\n'
printf '\nIf needed, add this to your shell config:\n'
printf '  export PATH="$HOME/.local/bin:$PATH"\n'
