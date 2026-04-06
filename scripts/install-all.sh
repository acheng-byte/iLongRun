#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_SOURCE="${ILONGRUN_PLUGIN_SOURCE:-${REPO_SLUG:-izscc/iLongRun}}"
ILONGRUN_HOME="${ILONGRUN_HOME:-$HOME/.copilot-ilongrun}"
COMMAND_BIN_DIR="$HOME/.local/bin"
TMP_INSTALL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ilongrun-install-flow.XXXXXX")"
KEEP_INSTALL_LOGS=0

cleanup() {
  if [ "$KEEP_INSTALL_LOGS" = "1" ]; then
    printf '\n⚠️ 安装过程中保留了调试日志：%s\n' "$TMP_INSTALL_DIR"
    return 0
  fi
  rm -rf "$TMP_INSTALL_DIR"
  return 0
}
trap cleanup EXIT

intro_board() {
  cat <<'BOARD'
╭─── 🛠️ iLongRun 一键安装向导 ────────────────────────╮
│                                                    │
│  欢迎使用 iLongRun 一键安装                         │
│  本次会先彻底清理旧 LongRun / iLongRun，再安装新版   │
│  你只需要等待安装完成，然后按提示开始使用即可。      │
│                                                    │
╰────────────────────────────────────────────────────╯
BOARD
  printf '\n'
}

fail_phase() {
  local title="$1"
  local logfile="$2"
  KEEP_INSTALL_LOGS=1
  printf '\n╭─── ❌ iLongRun 安装中断 ────────────────────────────╮\n'
  printf '│  失败阶段   %s\n' "$title"
  printf '│  日志位置   %s\n' "$logfile"
  printf '╰────────────────────────────────────────────────────╯\n\n'
  printf '最近日志摘录：\n'
  sed -n '1,80p' "$logfile" | sed 's/^/  /'
  printf '\n请把上面的日志发给我，我可以继续帮你定位。\n'
  exit 1
}

run_required_phase() {
  local title="$1"
  local detail="$2"
  local logfile="$3"
  shift 3
  printf '🔹 %s\n' "$title"
  printf '   %s\n' "$detail"
  if "$@" >"$logfile" 2>&1; then
    printf '   ✅ 已完成\n\n'
  else
    fail_phase "$title" "$logfile"
  fi
}

run_optional_phase() {
  local title="$1"
  local detail="$2"
  local logfile="$3"
  shift 3
  printf '🔹 %s\n' "$title"
  printf '   %s\n' "$detail"
  if "$@" >"$logfile" 2>&1; then
    printf '   ✅ 已完成\n\n'
    return 0
  fi
  printf '   ⚠️ 已继续：这个步骤有提醒，但不影响本地命令安装\n\n'
  return 1
}

intro_board

run_required_phase \
  '第 1 步：清理旧环境' \
  '卸载旧插件、清理旧命令、旧 skills/agents 和旧状态目录。' \
  "$TMP_INSTALL_DIR/01-cleanup.log" \
  bash "$ROOT_DIR/scripts/cleanup-copilot-longrun-state.sh"

plugin_status="skipped"
if command -v copilot >/dev/null 2>&1; then
  if run_optional_phase \
    '第 2 步：注册新版 Copilot 插件' \
    "尝试从 $PLUGIN_SOURCE 安装最新 iLongRun 插件定义。" \
    "$TMP_INSTALL_DIR/02-plugin.log" \
    copilot plugin install "$PLUGIN_SOURCE"; then
    plugin_status="installed"
  else
    plugin_status="failed"
  fi
else
  cat > "$TMP_INSTALL_DIR/02-plugin.log" <<EOF2
copilot CLI not found; plugin install skipped.
EOF2
  printf '🔹 第 2 步：注册新版 Copilot 插件\n'
  printf '   当前系统未检测到 copilot CLI，已跳过插件注册；本地命令仍会继续安装。\n'
  printf '   ⚪ 已跳过\n\n'
fi

run_required_phase \
  '第 3 步：安装本地 skills / agents / helpers' \
  '把 iLongRun 的核心能力复制到 Copilot 本地目录与 ~/.copilot-ilongrun。' \
  "$TMP_INSTALL_DIR/03-bare.log" \
  bash "$ROOT_DIR/scripts/install-bare-commands.sh"

run_required_phase \
  '第 4 步：安装全局命令入口' \
  '安装 ilongrun / ilongrun-coding / ilongrun-status 等命令。' \
  "$TMP_INSTALL_DIR/04-launchers.log" \
  bash "$ROOT_DIR/scripts/install-global-launcher.sh"

doctor_status=0
DOCTOR_BIN="$HOME/.local/bin/ilongrun-doctor"
if [ -x "$DOCTOR_BIN" ]; then
  if run_optional_phase \
    '第 5 步：执行环境自检' \
    '检查命令入口、模型配置、Copilot 登录、legacy 插件冲突与自检状态。' \
    "$TMP_INSTALL_DIR/05-doctor.log" \
    "$DOCTOR_BIN"; then
    doctor_status=0
  else
    doctor_status=$?
    doctor_status=1
  fi
else
  cat > "$TMP_INSTALL_DIR/05-doctor.log" <<EOF2
ilongrun-doctor not found after launcher install.
EOF2
  doctor_status=1
fi

python3 "$ROOT_DIR/scripts/render_ilongrun_install_board.py" \
  --plugin-status "$plugin_status" \
  --plugin-source "$PLUGIN_SOURCE" \
  --doctor-log "$TMP_INSTALL_DIR/05-doctor.log" \
  --doctor-exit-code "$doctor_status" \
  --command-bin-dir "$COMMAND_BIN_DIR" \
  --helper-dir "$ILONGRUN_HOME/bin" \
  --model-config "$ILONGRUN_HOME/config/model-policy.jsonc"
