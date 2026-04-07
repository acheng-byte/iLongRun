#!/usr/bin/env bash
set -euo pipefail

COPILOT_HOME="${COPILOT_HOME:-$HOME/.copilot}"
ILONGRUN_HOME="${ILONGRUN_HOME:-$HOME/.copilot-ilongrun}"
LEGACY_LONGRUN_HOME="${LEGACY_LONGRUN_HOME:-$HOME/.copilot-mission-control}"
LOCAL_BIN_DIR="${LOCAL_BIN_DIR:-$HOME/.local/bin}"
PLUGIN_CACHE_ROOT="$COPILOT_HOME/installed-plugins"

log() {
  printf '[iLongRun cleanup] %s\n' "$*"
}

remove_path() {
  local target="$1"
  if [ -L "$target" ] || [ -f "$target" ]; then
    rm -f "$target"
    log "Removed $target"
    return 0
  fi
  if [ -d "$target" ]; then
    rm -rf "$target"
    log "Removed $target"
  fi
}

try_copilot_uninstall() {
  local name="$1"
  if ! command -v copilot >/dev/null 2>&1; then
    return 0
  fi
  if copilot plugin uninstall "$name" >/dev/null 2>&1; then
    log "Uninstalled Copilot plugin: $name"
  else
    log "Copilot plugin not installed (or already removed): $name"
  fi
}

scrub_copilot_config() {
  local config_path="$COPILOT_HOME/config.json"
  [ -f "$config_path" ] || return 0
  python3 - "$config_path" <<'PY'
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
plugins = data.get("installed_plugins", [])
filtered = []
removed = []
for item in plugins:
    payload = json.dumps(item, ensure_ascii=False).lower()
    if any(token in payload for token in ("ilongrun", "longrun", "copilot-mission-control", "mission-control")):
        removed.append(item.get("name") or item.get("cache_path") or "<unknown>")
        continue
    filtered.append(item)
data["installed_plugins"] = filtered
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if removed:
    print("\\n".join(str(x) for x in removed))
PY
}

remove_plugin_caches() {
  [ -d "$PLUGIN_CACHE_ROOT" ] || return 0
  while IFS= read -r -d '' path; do
    rm -rf "$path"
    log "Removed plugin cache $path"
  done < <(find "$PLUGIN_CACHE_ROOT" -maxdepth 3 \( -iname '*ilongrun*' -o -iname '*longrun*' -o -iname '*mission-control*' \) -print0 2>/dev/null)
}

remove_global_launchers() {
  [ -d "$LOCAL_BIN_DIR" ] || return 0
  while IFS= read -r -d '' path; do
    rm -f "$path"
    log "Removed launcher $path"
  done < <(find "$LOCAL_BIN_DIR" -maxdepth 1 -type f \( -name 'ilongrun*' -o -name 'longrun*' -o -name 'copilot-ilongrun*' -o -name 'copilot-longrun*' \) -print0 2>/dev/null)
}

scrub_personal_definitions() {
  python3 - "$COPILOT_HOME" <<'PY'
from pathlib import Path
import shutil
import sys

copilot_home = Path(sys.argv[1])
known_skill_names = {
    "ilongrun",
    "ilongrun-coding",
    "ilongrun-prompt",
    "ilongrun-resume",
    "ilongrun-status",
}
known_agent_names = {
    "ilongrun-mission-governor.agent.md",
    "ilongrun-strategy-synthesizer.agent.md",
    "ilongrun-phase-planner.agent.md",
    "ilongrun-workstream-planner.agent.md",
    "ilongrun-executor.agent.md",
    "ilongrun-recovery.agent.md",
    "ilongrun-gpt54-audit-reviewer.agent.md",
    "ilongrun-final-audit-reviewer.agent.md",
    "ilongrun-code-reviewer.agent.md",
    "ilongrun-test-engineer.agent.md",
    "ilongrun-security-auditor.agent.md",
}
content_markers = (
    "ilongrun",
    "copilot-ilongrun",
    ".copilot-ilongrun",
    "copilot-mission-control",
    ".copilot-mission-control",
    "你是 longrun",
    " longrun ",
    "longrun mission",
)
name_markers = ("ilongrun", "longrun", "mission-control")
removed = []

def rm(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(str(path))

def should_remove(path: Path) -> bool:
    lower_name = path.name.lower()
    if path.parent.name == "skills" and lower_name in known_skill_names:
        return True
    if path.parent.name == "agents" and lower_name in known_agent_names:
        return True
    if any(marker in lower_name for marker in name_markers):
        return True
    file_candidates = []
    if path.is_file():
        file_candidates = [path]
    elif path.is_dir():
        file_candidates = [p for p in path.rglob('*') if p.is_file()]
    for file_path in file_candidates:
        try:
            text = file_path.read_text(encoding='utf-8', errors='ignore').lower()
        except Exception:
            continue
        if any(marker in text for marker in content_markers):
            return True
    return False

for bucket in ("skills", "agents"):
    root = copilot_home / bucket
    if not root.exists():
        continue
    for path in list(root.iterdir()):
        if should_remove(path):
            rm(path)

if removed:
    print("\\n".join(removed))
PY
}

main() {
  log "Starting full cleanup for legacy LongRun / iLongRun install state"

  try_copilot_uninstall "ilongrun"
  try_copilot_uninstall "copilot-mission-control"
  try_copilot_uninstall "longrun"

  local scrubbed
  scrubbed="$(scrub_copilot_config || true)"
  if [ -n "$scrubbed" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] && log "Removed plugin definition from config: $line"
    done <<< "$scrubbed"
  fi

  remove_plugin_caches
  remove_global_launchers

  local removed_defs
  removed_defs="$(scrub_personal_definitions || true)"
  if [ -n "$removed_defs" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] && log "Removed personal definition: $line"
    done <<< "$removed_defs"
  fi

  remove_path "$ILONGRUN_HOME"
  remove_path "$LEGACY_LONGRUN_HOME"

  log "Cleanup complete. Historical command/log/session traces under $COPILOT_HOME are preserved."
}

main "$@"
