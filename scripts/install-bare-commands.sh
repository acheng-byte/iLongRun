#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ILONGRUN_HOME="${ILONGRUN_HOME:-$HOME/.copilot-ilongrun}"
HELPER_BIN_DIR="$ILONGRUN_HOME/bin"
HELPER_CONFIG_DIR="$ILONGRUN_HOME/config"
HELPER_VENDOR_DIR="$ILONGRUN_HOME/vendor"
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

migrate_model_policy() {
  local source_template="$1"
  local target_config="$2"
  [ -f "$target_config" ] || return 0
  python3 - "$ROOT_DIR/scripts" "$source_template" "$target_config" <<'PY'
import json
import sys
from pathlib import Path

scripts_dir = Path(sys.argv[1])
source_path = Path(sys.argv[2])
target_path = Path(sys.argv[3])
sys.path.insert(0, str(scripts_dir))

from _ilongrun_shared import read_jsonc, write_text_atomic  # type: ignore

DEPRECATED = "gemini-3.1-pro"

source = read_jsonc(source_path, {})
target = read_jsonc(target_path, {})

changed = False

def sanitize_mapping(mapping, template=None):
    global changed
    result = dict(mapping or {})
    for key, value in list(result.items()):
        if value == DEPRECATED:
            changed = True
            replacement = (template or {}).get(key)
            if replacement:
                result[key] = replacement
            else:
                result.pop(key, None)
    return result

fallback = [item for item in (target.get("fallback") or []) if item != DEPRECATED]
if fallback != list(target.get("fallback") or []):
    target["fallback"] = fallback
    changed = True

display_names = dict(target.get("displayNames") or {})
if display_names.pop(DEPRECATED, None) is not None:
    target["displayNames"] = display_names
    changed = True

aliases = dict(target.get("aliases") or {})
clean_aliases = {key: value for key, value in aliases.items() if value != DEPRECATED}
if clean_aliases != aliases:
    target["aliases"] = clean_aliases
    changed = True

for field in ("commandDefaults", "skillDefaults", "roleModels"):
    cleaned = sanitize_mapping(target.get(field) or {}, source.get(field) or {})
    if cleaned != (target.get(field) or {}):
        target[field] = cleaned
        changed = True

if target.get("codingAuditModel") == DEPRECATED:
    target["codingAuditModel"] = source.get("codingAuditModel") or "gpt-5.4"
    changed = True

if changed:
    write_text_atomic(target_path, json.dumps(target, ensure_ascii=False, indent=2))
    print("migrated")
else:
    print("noop")
PY
}

HELPER_REFS_DIR="$ILONGRUN_HOME/references"
mkdir -p "$TARGET_SKILLS_DIR" "$TARGET_AGENTS_DIR" "$HELPER_BIN_DIR" "$HELPER_CONFIG_DIR" "$HELPER_REFS_DIR" "$HELPER_VENDOR_DIR"

find_bin_from_common_locations() {
  local name="$1"
  local path
  for path in \
    "$HOME/.local/bin/$name" \
    "/opt/homebrew/bin/$name" \
    "/usr/local/bin/$name" \
    "$HOME/bin/$name"
  do
    [ -x "$path" ] && { printf '%s\n' "$path"; return 0; }
  done
  command -v "$name" 2>/dev/null || true
}

log() {
  printf '%s\n' "$*"
}

maybe_install_terminal_notifier() {
  [ "$(uname -s)" = "Darwin" ] || return 0
  if find_bin_from_common_locations terminal-notifier >/dev/null 2>&1; then
    log "Enhanced macOS notifications ready: $(find_bin_from_common_locations terminal-notifier)"
    return 0
  fi

  if command -v curl >/dev/null 2>&1 && command -v unzip >/dev/null 2>&1; then
    local tmp_dir archive_url bin_target app_target
    tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/ilongrun-notifier.XXXXXX")"
    archive_url="https://github.com/julienXX/terminal-notifier/releases/download/2.0.0/terminal-notifier-2.0.0.zip"
    bin_target="$HOME/.local/bin/terminal-notifier"
    app_target="$HOME/.local/share/terminal-notifier.app"
    log "Installing terminal-notifier from official release bundle..."
    if curl -fsSL "$archive_url" -o "$tmp_dir/terminal-notifier.zip" \
      && unzip -q "$tmp_dir/terminal-notifier.zip" -d "$tmp_dir" \
      && [ -x "$tmp_dir/terminal-notifier.app/Contents/MacOS/terminal-notifier" ]; then
      mkdir -p "$(dirname "$bin_target")" "$(dirname "$app_target")"
      rm -rf "$app_target"
      cp -R "$tmp_dir/terminal-notifier.app" "$app_target"
      cat > "$bin_target" <<EOF2
#!/usr/bin/env bash
exec "$app_target/Contents/MacOS/terminal-notifier" "\$@"
EOF2
      chmod +x "$bin_target"
      rm -rf "$tmp_dir"
      log "Installed terminal-notifier app bundle to $app_target"
      log "Installed terminal-notifier launcher to $bin_target"
      return 0
    fi
    rm -rf "$tmp_dir"
  fi

  if command -v brew >/dev/null 2>&1; then
    log "Installing terminal-notifier for enhanced macOS notifications..."
    if brew install terminal-notifier >/dev/null 2>&1; then
      log "Installed terminal-notifier via Homebrew."
      return 0
    fi
    log "Could not install terminal-notifier automatically; iLongRun will fall back to basic macOS notifications."
    return 0
  fi

  log "Homebrew not found; iLongRun will fall back to basic macOS notifications."
}

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

if [ -d "$ROOT_DIR/references" ]; then
  for ref_file in "$ROOT_DIR"/references/*.md; do
    [ -f "$ref_file" ] || continue
    ref_name="$(basename "$ref_file")"
    install_copied_file "$ref_file" "$HELPER_REFS_DIR/$ref_name"
    printf 'Installed reference: %s\n' "$ref_name"
  done
fi

helpers=(
  _ilongrun_delivery_audit.py
  _ilongrun_shared.py
  _ilongrun_lib.py
  _ilongrun_report_templates.py
  _ilongrun_terminal_theme.py
  render_ilongrun_doctor_board.py
  render_ilongrun_install_board.py
  cleanup_legacy_workspace.py
  notify_macos.py
  prepare_ilongrun_run.py
  render_ilongrun_launch_board.py
  render_ilongrun_status_board.py
  write_ilongrun_scheduler.py
  reconcile_ilongrun_run.py
  verify_ilongrun_run.py
  scan_ilongrun_delivery_gaps.py
  finalize_ilongrun_run.py
  launch_ilongrun_supervisor.py
  selftest_ilongrun.py
  sync_ilongrun_ledger.py
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

shell_helpers=(
  copilot-ilongrun
  ilongrun
  ilongrun-coding
  ilongrun-prompt
  ilongrun-resume
  ilongrun-status
  ilongrun-doctor
)

for helper in "${shell_helpers[@]}"; do
  install_copied_file "$ROOT_DIR/scripts/$helper" "$HELPER_BIN_DIR/$helper"
  chmod +x "$HELPER_BIN_DIR/$helper"
  printf 'Installed helper launcher: %s\n' "$HELPER_BIN_DIR/$helper"
done

maybe_install_terminal_notifier

if [ -f "$HELPER_CONFIG_DIR/model-policy.jsonc" ]; then
  printf 'Preserved existing model policy: %s\n' "$HELPER_CONFIG_DIR/model-policy.jsonc"
elif [ -f "$HELPER_CONFIG_DIR/model-policy.json" ]; then
  backup_if_needed "$HELPER_CONFIG_DIR/model-policy.json"
  install_copied_file "$ROOT_DIR/config/model-policy.jsonc" "$HELPER_CONFIG_DIR/model-policy.jsonc"
  printf 'Installed refreshed model policy template: %s\n' "$HELPER_CONFIG_DIR/model-policy.jsonc"
else
  install_copied_file "$ROOT_DIR/config/model-policy.jsonc" "$HELPER_CONFIG_DIR/model-policy.jsonc"
  printf 'Installed model policy: %s\n' "$HELPER_CONFIG_DIR/model-policy.jsonc"
fi
migration_result="$(migrate_model_policy "$ROOT_DIR/config/model-policy.jsonc" "$HELPER_CONFIG_DIR/model-policy.jsonc" || true)"
if [ "$migration_result" = "migrated" ]; then
  printf 'Sanitized deprecated model entries in: %s\n' "$HELPER_CONFIG_DIR/model-policy.jsonc"
fi
if [ ! -f "$HELPER_CONFIG_DIR/model-availability.json" ]; then
  install_copied_file "$ROOT_DIR/config/model-availability.json" "$HELPER_CONFIG_DIR/model-availability.json"
  printf 'Installed model availability seed: %s\n' "$HELPER_CONFIG_DIR/model-availability.json"
else
  printf 'Preserved existing model availability cache: %s\n' "$HELPER_CONFIG_DIR/model-availability.json"
fi
install_copied_file "$ROOT_DIR/config/coding-protocol.jsonc" "$HELPER_CONFIG_DIR/coding-protocol.jsonc"
printf 'Installed coding protocol: %s\n' "$HELPER_CONFIG_DIR/coding-protocol.jsonc"
if [ -d "$ROOT_DIR/vendor/agent-skills" ]; then
  install_copied_dir "$ROOT_DIR/vendor/agent-skills" "$HELPER_VENDOR_DIR/agent-skills"
  printf 'Installed vendor snapshot: %s\n' "$HELPER_VENDOR_DIR/agent-skills"
fi

cat <<EOF2

Done.

You can now use these Copilot bare commands:
  /ilongrun
  /ilongrun-prompt
  /ilongrun-resume
  /ilongrun-status

Installed internal discipline skill:
  /ilongrun-coding
  （供 iLongRun 在 coding mission 中自动加载；终端用户入口是后续安装的 shell 命令 `ilongrun-coding`）

ILongRun helper bundle:
  $HELPER_BIN_DIR

Model policy:
  $HELPER_CONFIG_DIR/model-policy.jsonc

Coding protocol:
  $HELPER_CONFIG_DIR/coding-protocol.jsonc

Vendored agent-skills snapshot:
  $HELPER_VENDOR_DIR/agent-skills
EOF2
