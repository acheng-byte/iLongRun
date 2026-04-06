#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args: str, ok: bool = True, env: dict[str, str] | None = None):
    proc = subprocess.run(
        ["python3", *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    if ok and proc.returncode != 0:
        raise RuntimeError(f"command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_notify_target(payload: dict, expected: Path) -> None:
    assert payload["backend"] in {"terminal-notifier", "osascript", "none"}
    assert payload.get("resolvedOpen", "") == str(expected.resolve())


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="ilongrun-selftest-"))
    try:
        workspace = temp_root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        run(
            str(ROOT / "prepare_ilongrun_run.py"),
            "--workspace", str(workspace),
            "--task", "重构项目登录模块并补充测试，保存审计报告到 reports/audit.md",
        )
        state_dir = workspace / ".copilot-ilongrun" / "state"
        run_id = (state_dir / "latest-run-id").read_text(encoding="utf-8").strip()
        run_dir = workspace / ".copilot-ilongrun" / "runs" / run_id
        assert (run_dir / "mission.md").exists()
        assert (run_dir / "strategy.md").exists()
        assert (run_dir / "plan.md").exists()
        assert (run_dir / "scheduler.json").exists()
        assert list(run_dir.glob("task-list-*.md"))

        model_info_run = run(
            str(ROOT / "model_policy_info.py"),
            "--config", str(ROOT.parent / "config" / "model-policy.jsonc"),
            "--subcommand", "run",
            "--skill", "ilongrun",
            "--json",
        )
        model_info_run_payload = json.loads(model_info_run.stdout)
        assert model_info_run_payload["selected"] == "claude-sonnet-4.6"

        model_info_coding = run(
            str(ROOT / "model_policy_info.py"),
            "--config", str(ROOT.parent / "config" / "model-policy.jsonc"),
            "--subcommand", "coding",
            "--skill", "ilongrun-coding",
            "--json",
        )
        model_info_coding_payload = json.loads(model_info_coding.stdout)
        assert model_info_coding_payload["selected"] == "claude-opus-4.6"

        doctor_log = temp_root / "doctor.log"
        doctor_log.write_text(
            "\n".join(
                [
                    "[OK] login: test-user@https://github.com",
                    "[OK] /fleet: supported (probe-success) via Claude Sonnet 4.6",
                    "[OK] ilongrun selftest passed",
                    "[OK] legacy plugin not enabled: copilot-mission-control",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        install_board = run(
            str(ROOT / "render_ilongrun_install_board.py"),
            "--plugin-status", "installed",
            "--plugin-source", "izscc/iLongRun",
            "--doctor-log", str(doctor_log),
            "--doctor-exit-code", "0",
            "--command-bin-dir", str(temp_root / "bin"),
            "--helper-dir", str(temp_root / "helpers"),
            "--model-config", str(ROOT.parent / "config" / "model-policy.jsonc"),
        )
        assert "知识船仓·公益社区" in install_board.stdout
        assert "====" in install_board.stdout

        coding_workspace = temp_root / "coding-workspace"
        coding_workspace.mkdir(parents=True, exist_ok=True)
        run(
            str(ROOT / "prepare_ilongrun_run.py"),
            "--workspace", str(coding_workspace),
            "--task", "帮我整理一个前端项目的开发计划，但这次强制按 coding mission 启动",
            "--force-profile", "coding",
        )
        coding_run_id = (coding_workspace / ".copilot-ilongrun" / "state" / "latest-run-id").read_text(encoding="utf-8").strip()
        coding_sched = read_json(coding_workspace / ".copilot-ilongrun" / "runs" / coding_run_id / "scheduler.json")
        assert coding_sched.get("profile") == "coding"
        assert (coding_sched.get("mission") or {}).get("profile") == "coding"
        assert (coding_sched.get("reviews") or {}).get("required") is True
        launch_board = run(
            str(ROOT / "render_ilongrun_launch_board.py"),
            "--workspace", str(coding_workspace),
            "--run-id", coding_run_id,
            "--subcommand", "coding",
            "--log-file", str(coding_workspace / ".copilot-ilongrun" / "launcher" / "coding.log"),
            "--meta-file", str(coding_workspace / ".copilot-ilongrun" / "launcher" / "coding.json"),
            "--selected-model", "claude-opus-4.6",
            "--model-config", str(ROOT.parent / "config" / "model-policy.jsonc"),
        )
        assert "启动看板" in launch_board.stdout
        assert "ilongrun-status" in launch_board.stdout
        launched = run(
            str(ROOT / "notify_macos.py"),
            "--workspace", str(workspace),
            "--run-id", run_id,
            "--event", "launched",
            "--dry-run",
        )
        launched_result = json.loads(launched.stdout)
        assert_notify_target(launched_result, run_dir / "plan.md")

        (run_dir / "COMPLETION.md").write_text("# completion\n", encoding="utf-8")
        complete_notify = run(
            str(ROOT / "notify_macos.py"),
            "--workspace", str(workspace),
            "--run-id", run_id,
            "--event", "complete",
            "--dry-run",
        )
        complete_result = json.loads(complete_notify.stdout)
        assert_notify_target(complete_result, run_dir / "COMPLETION.md")
        (run_dir / "COMPLETION.md").unlink()

        scheduler = read_json(run_dir / "scheduler.json")
        workstreams = scheduler.get("workstreams") or []
        assert workstreams
        for ws in workstreams:
            ws_status = {"id": ws["id"], "status": "complete"}
            (run_dir / ws["statusPath"]).write_text(json.dumps(ws_status, ensure_ascii=False, indent=2), encoding="utf-8")
            (run_dir / ws["resultPath"]).write_text("# Result\n\nDone.\n", encoding="utf-8")
            (run_dir / ws["evidencePath"]).write_text("# Evidence\n\nVerified.\n", encoding="utf-8")
        (workspace / "reports").mkdir(exist_ok=True)
        (workspace / "reports" / "audit.md").write_text("# audit\n", encoding="utf-8")

        failed = run(
            str(ROOT / "finalize_ilongrun_run.py"),
            "--workspace", str(workspace),
            "--run-id", run_id,
            "--status", "complete",
            "--headline", "should fail without final audit review",
            "--local-verify",
            ok=False,
            env={"ILONGRUN_NOTIFICATIONS": "0"},
        )
        assert failed.returncode != 0

        review_dir = run_dir / "reviews"
        review_dir.mkdir(exist_ok=True)
        (review_dir / "gpt54-final-review.md").write_text(
            "# GPT-5.4 Final Review\n\n## Findings\n- none\n\n## Severity\n- low\n\n## Must-fix\n\n## Suggested fixes\n- none\n\n## Residual risks\n- low residual risk\n",
            encoding="utf-8",
        )
        run(str(ROOT / "reconcile_ilongrun_run.py"), "--workspace", str(workspace), "--run-id", run_id)
        ok_finalize = run(
            str(ROOT / "finalize_ilongrun_run.py"),
            "--workspace", str(workspace),
            "--run-id", run_id,
            "--status", "complete",
            "--headline", "finalized with review",
            "--local-verify",
            env={"ILONGRUN_NOTIFICATIONS": "0"},
        )
        assert ok_finalize.returncode == 0
        final_scheduler = read_json(run_dir / "scheduler.json")
        assert final_scheduler.get("state") == "complete"
        assert (run_dir / "COMPLETION.md").exists()

        drift_workspace = temp_root / "drift-workspace"
        drift_workspace.mkdir(parents=True, exist_ok=True)
        run(
            str(ROOT / "prepare_ilongrun_run.py"),
            "--workspace", str(drift_workspace),
            "--task", "实现账户服务并补测试，最终生成审查报告",
            "--force-profile", "coding",
        )
        drift_run_id = (drift_workspace / ".copilot-ilongrun" / "state" / "latest-run-id").read_text(encoding="utf-8").strip()
        drift_canonical = drift_workspace / ".copilot-ilongrun" / "runs" / drift_run_id
        drift_legacy = drift_workspace / ".copilot-ilongrun" / drift_run_id
        drift_legacy.mkdir(parents=True, exist_ok=True)
        drift_scheduler = read_json(drift_canonical / "scheduler.json")
        for ws in drift_scheduler.get("workstreams") or []:
            ws["status"] = "complete"
            ws_dir = drift_legacy / Path(ws["statusPath"]).parent
            ws_dir.mkdir(parents=True, exist_ok=True)
            (drift_legacy / ws["statusPath"]).write_text(json.dumps({"id": ws["id"], "status": "complete"}, ensure_ascii=False, indent=2), encoding="utf-8")
            (drift_legacy / ws["resultPath"]).write_text("# Result\n\nLegacy execution finished.\n", encoding="utf-8")
            (drift_legacy / ws["evidencePath"]).write_text("# Evidence\n\nLegacy evidence finished.\n", encoding="utf-8")
        drift_scheduler["updatedAt"] = "2026-04-07T00:53:00Z"
        drift_scheduler["selectedModel"] = "claude-opus-4.6"
        (drift_legacy / "scheduler.json").write_text(json.dumps(drift_scheduler, ensure_ascii=False, indent=2), encoding="utf-8")
        (drift_legacy / "reviews").mkdir(parents=True, exist_ok=True)
        (drift_legacy / "reviews" / "gpt54-final-review.md").write_text("# Final Review\n\n## Must-fix\n- None\n", encoding="utf-8")
        run(str(ROOT / "reconcile_ilongrun_run.py"), "--workspace", str(drift_workspace), "--run-id", drift_run_id)
        assert not drift_legacy.exists()
        assert (drift_canonical / "reviews" / "gpt54-final-review.md").exists()
        assert (drift_canonical / "workstreams" / "ws-001" / "result.md").read_text(encoding="utf-8").startswith("# Result")
        merge_reports = list((drift_workspace / ".copilot-ilongrun" / "legacy-imports" / "run-merges").glob("*.json"))
        assert merge_reports

        legacy_plugin_workspace = temp_root / "legacy-plugin-workspace"
        legacy_plugin_workspace.mkdir(parents=True, exist_ok=True)
        legacy_root = legacy_plugin_workspace / ".copilot-mission-control"
        (legacy_root / "global").mkdir(parents=True, exist_ok=True)
        (legacy_root / "global" / "hook-events.jsonl").write_text("{\"event\":\"sessionStart\"}\n", encoding="utf-8")
        cleanup = run(
            str(ROOT / "cleanup_legacy_workspace.py"),
            "--workspace", str(legacy_plugin_workspace),
            "--print-json",
        )
        cleanup_payload = json.loads(cleanup.stdout)
        assert cleanup_payload["removed"] is True
        assert not legacy_root.exists()
        assert cleanup_payload["archivePath"]
        assert Path(cleanup_payload["archivePath"]).exists()

        print("ILongRun selftest passed")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
