#!/usr/bin/env bash
set -euo pipefail
ILONGRUN_HOME="${ILONGRUN_HOME:-$HOME/.copilot-ilongrun}"

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

for skill in ilongrun ilongrun-prompt ilongrun-resume ilongrun-status; do
  remove_path "$HOME/.copilot/skills/$skill"
done
for agent in ilongrun-mission-governor.agent.md ilongrun-strategy-synthesizer.agent.md ilongrun-phase-planner.agent.md ilongrun-workstream-planner.agent.md ilongrun-executor.agent.md ilongrun-recovery.agent.md ilongrun-gpt54-audit-reviewer.agent.md; do
  remove_path "$HOME/.copilot/agents/$agent"
done
for helper in _ilongrun_shared.py _ilongrun_lib.py prepare_ilongrun_run.py write_ilongrun_scheduler.py reconcile_ilongrun_run.py verify_ilongrun_run.py finalize_ilongrun_run.py launch_ilongrun_supervisor.py selftest_ilongrun.py model_policy_info.py probe_models.py probe_fleet_capability.py hook_event.py; do
  remove_path "$ILONGRUN_HOME/bin/$helper"
done
