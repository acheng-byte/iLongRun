#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
remove_path() {
  local target="$1"
  if [ -L "$target" ] || [ -f "$target" ]; then
    rm -f "$target"
    printf 'Removed %s\n' "$target"
    return
  fi
  if [ -d "$target" ]; then
    rm -rf "$target"
    printf 'Removed %s\n' "$target"
  fi
}
for name in ilongrun ilongrun-coding ilongrun-prompt ilongrun-resume ilongrun-status ilongrun-doctor copilot-ilongrun; do
  remove_path "$HOME/.local/bin/$name"
done
bash "$ROOT_DIR/scripts/uninstall-bare-commands.sh" || true
