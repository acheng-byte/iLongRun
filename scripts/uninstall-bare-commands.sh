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

for skill in ilongrun ilongrun-coding ilongrun-model ilongrun-prompt ilongrun-resume ilongrun-status; do
  remove_path "$HOME/.copilot/skills/$skill"
done
for agent in ilongrun-mission-governor.agent.md ilongrun-strategy-synthesizer.agent.md ilongrun-phase-planner.agent.md ilongrun-workstream-planner.agent.md ilongrun-executor.agent.md ilongrun-recovery.agent.md ilongrun-gpt54-audit-reviewer.agent.md ilongrun-final-audit-reviewer.agent.md ilongrun-code-reviewer.agent.md ilongrun-test-engineer.agent.md ilongrun-security-auditor.agent.md; do
  remove_path "$HOME/.copilot/agents/$agent"
done
for helper in _ilongrun_delivery_audit.py _ilongrun_shared.py _ilongrun_lib.py _ilongrun_report_templates.py _ilongrun_terminal_theme.py render_ilongrun_doctor_board.py render_ilongrun_install_board.py cleanup_legacy_workspace.py notify_macos.py prepare_ilongrun_run.py render_ilongrun_launch_board.py render_ilongrun_status_board.py write_ilongrun_scheduler.py reconcile_ilongrun_run.py verify_ilongrun_run.py scan_ilongrun_delivery_gaps.py finalize_ilongrun_run.py launch_ilongrun_supervisor.py selftest_ilongrun.py lint_ilongrun_skills.py sync_ilongrun_ledger.py model_policy_info.py manage_ilongrun_model.py probe_models.py probe_fleet_capability.py hook_event.py copilot-ilongrun ilongrun ilongrun-coding ilongrun-model ilongrun-prompt ilongrun-resume ilongrun-status ilongrun-doctor; do
  remove_path "$ILONGRUN_HOME/bin/$helper"
done
for ref in testing-patterns.md security-checklist.md performance-checklist.md skill-engineering-checklist.md skill-pressure-scenarios.md; do
  remove_path "$ILONGRUN_HOME/references/$ref"
done
remove_path "$ILONGRUN_HOME/config/model-policy.jsonc"
remove_path "$ILONGRUN_HOME/config/model-policy.json"
remove_path "$ILONGRUN_HOME/config/coding-protocol.jsonc"
remove_path "$ILONGRUN_HOME/vendor/agent-skills"
