#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ILONGRUN_HOME="${ILONGRUN_HOME:-$HOME/.copilot-ilongrun}"
HELPER_BIN_DIR="$ILONGRUN_HOME/bin"
HELPER_CONFIG_DIR="$ILONGRUN_HOME/config"
TARGET_SKILLS_DIR="$HOME/.copilot/skills"
TARGET_AGENTS_DIR="$HOME/.copilot/agents"

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

install_copied_dir() {
  local source="$1"
  local target="$2"
  backup_if_needed "$target"
  mkdir -p "$target"
  find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
  cp -R "$source"/. "$target"/
}

install_copied_file() {
  local source="$1"
  local target="$2"
  backup_if_needed "$target"
  mkdir -p "$(dirname "$target")"
  cp "$source" "$target"
}

mkdir -p "$TARGET_SKILLS_DIR" "$TARGET_AGENTS_DIR" "$HELPER_BIN_DIR" "$HELPER_CONFIG_DIR"

for skill_dir in "$ROOT_DIR"/skills/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  install_copied_dir "$skill_dir" "$TARGET_SKILLS_DIR/$skill_name"
  printf 'Installed skill: /%s\n' "$skill_name"
done

for agent_file in "$ROOT_DIR"/agents/*.md; do
  [ -f "$agent_file" ] || continue
  agent_name="$(basename "$agent_file")"
  install_copied_file "$agent_file" "$TARGET_AGENTS_DIR/$agent_name"
  printf 'Installed agent: %s\n' "$agent_name"
done

helpers=(
  _ilongrun_shared.py
  _ilongrun_lib.py
  prepare_ilongrun_run.py
  write_ilongrun_scheduler.py
  reconcile_ilongrun_run.py
  verify_ilongrun_run.py
  finalize_ilongrun_run.py
  launch_ilongrun_supervisor.py
  selftest_ilongrun.py
  model_policy_info.py
  probe_models.py
  probe_fleet_capability.py
  hook_event.py
)

for helper in "${helpers[@]}"; do
  install_copied_file "$ROOT_DIR/scripts/$helper" "$HELPER_BIN_DIR/$helper"
  chmod +x "$HELPER_BIN_DIR/$helper"
  printf 'Installed helper: %s\n' "$HELPER_BIN_DIR/$helper"
done

install_copied_file "$ROOT_DIR/config/model-policy.json" "$HELPER_CONFIG_DIR/model-policy.json"
printf 'Installed model policy: %s\n' "$HELPER_CONFIG_DIR/model-policy.json"
if [ ! -f "$HELPER_CONFIG_DIR/model-availability.json" ]; then
  install_copied_file "$ROOT_DIR/config/model-availability.json" "$HELPER_CONFIG_DIR/model-availability.json"
  printf 'Installed model availability seed: %s\n' "$HELPER_CONFIG_DIR/model-availability.json"
else
  printf 'Preserved existing model availability cache: %s\n' "$HELPER_CONFIG_DIR/model-availability.json"
fi

cat <<EOF2

Done.

You can now use these Copilot bare commands:
  /ilongrun
  /ilongrun-prompt
  /ilongrun-resume
  /ilongrun-status

ILongRun helper bundle:
  $HELPER_BIN_DIR
EOF2
