#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from _ilongrun_report_templates import build_final_review_template_markdown
from _ilongrun_shared import default_model_config

ROOT = Path(__file__).resolve().parent


def run(*args: str, ok: bool = True, env: dict[str, str] | None = None, input_text: str | None = None):
    proc = subprocess.run(
        ["python3", *args],
        capture_output=True,
        text=True,
        input=input_text,
        env={**os.environ, **(env or {})},
    )
    if ok and proc.returncode != 0:
        raise RuntimeError(f"command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def run_inline(code: str, ok: bool = True, env: dict[str, str] | None = None):
    proc = subprocess.run(
        ["python3", "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    if ok and proc.returncode != 0:
        raise RuntimeError(f"inline python failed\ncode={code}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_notify_target(payload: dict, expected: Path) -> None:
    assert payload["backend"] in {"terminal-notifier", "osascript", "none"}
    assert payload.get("resolvedOpen", "") == str(expected.resolve())


def completed_status_payload(ws: dict, *, stamp: str = "2026-04-07T00:01:00Z") -> dict:
    phase_id = str(ws.get("phaseId") or "")
    payload = {
        "id": ws["id"],
        "status": "complete",
        "startedAt": "2026-04-07T00:00:00Z",
        "completedAt": stamp,
        "specRef": ws.get("specRef"),
        "microcycleState": ws.get("microcycleState") or {},
        "reviewSequence": ws.get("reviewSequence") or {},
        "freshEvidence": ws.get("freshEvidence") or {},
        "rootCauseRecord": ws.get("rootCauseRecord") or {},
    }
    if phase_id == "phase-build":
        payload["microcycleState"] = {
            "required": True,
            "status": "complete",
            "currentStep": "handoff",
            "steps": [
                {"id": "spec-lock", "status": "done"},
                {"id": "red", "status": "done"},
                {"id": "verify-red", "status": "done"},
                {"id": "green", "status": "done"},
                {"id": "verify-green", "status": "done"},
                {"id": "self-review", "status": "done"},
                {"id": "spec-review", "status": "done"},
                {"id": "quality-review", "status": "done"},
                {"id": "handoff", "status": "done"},
            ],
            "lastUpdatedAt": stamp,
        }
        payload["reviewSequence"] = {
            "required": True,
            "status": "complete",
            "selfReview": "complete",
            "specReview": "complete",
            "qualityReview": "complete",
            "lastUpdatedAt": stamp,
        }
    if phase_id in {"phase-build", "phase-verify"}:
        payload["freshEvidence"] = {
            "required": True,
            "status": "complete",
            "items": [
                {
                    "command": "python3 -m pytest",
                    "observedAt": stamp,
                    "exitCode": 0,
                    "summary": f"{ws['id']} fresh evidence",
                }
            ],
            "lastUpdatedAt": stamp,
        }
    return payload


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="ilongrun-selftest-"))
    try:
        helper_home = ROOT.parent if ROOT.name == "bin" else (temp_root / "ilongrun-home")
        review_template = build_final_review_template_markdown()
        assert "## Run Metadata" in review_template
        assert "### Must-Fix (Critical)" in review_template
        assert "## Residual Risks" in review_template
        assert "## Verdict" in review_template
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
        assert (run_dir / "projection-sync.jsonl").exists()
        assert list(run_dir.glob("task-list-*.md"))
        prepared_scheduler = read_json(run_dir / "scheduler.json")
        assert prepared_scheduler.get("profile") == "coding"
        assert (prepared_scheduler.get("projectionState") or {}).get("ledgerSyncReason") == "run-prepared"
        assert (prepared_scheduler.get("projectionState") or {}).get("ledgerSyncActor") == "ledger-syncer"
        assert [phase.get("id") for phase in prepared_scheduler.get("phases") or []] == [
            "phase-define",
            "phase-plan",
            "phase-build",
            "phase-verify",
            "phase-review",
            "phase-audit",
            "phase-finalize",
        ]
        assert (prepared_scheduler.get("codingProtocol") or {}).get("version") == "0.7.0"
        assert (prepared_scheduler.get("workspaceIsolation") or {}).get("enabled") is True
        assert (prepared_scheduler.get("phaseGuards") or {}).get("claimVerification")
        assert (prepared_scheduler.get("reviewMatrix") or {}).get("gates")
        assert "gpt54-audit-reviewer" not in ((prepared_scheduler.get("mission") or {}).get("modelAllocation") or {})
        assert (prepared_scheduler.get("mission") or {}).get("modelAllocation", {}).get("code-reviewer") == "gpt-5.4"
        assert (prepared_scheduler.get("mission") or {}).get("modelAllocation", {}).get("test-engineer") == "gpt-5.4"
        assert (prepared_scheduler.get("mission") or {}).get("modelAllocation", {}).get("security-auditor") == "gpt-5.4"

        explicit_workspace = temp_root / "explicit-model-workspace"
        explicit_workspace.mkdir(parents=True, exist_ok=True)
        run(
            str(ROOT / "prepare_ilongrun_run.py"),
            "--workspace", str(explicit_workspace),
            "--task", "修复一个小 bug 并完成最终终审",
            "--force-profile", "coding",
            "--explicit-model", "claude-haiku-4.5",
            "--session-model", "claude-haiku-4.5",
            "--model-control-mode", "explicit-model-locked",
        )
        explicit_run_id = (explicit_workspace / ".copilot-ilongrun" / "state" / "latest-run-id").read_text(encoding="utf-8").strip()
        explicit_scheduler = read_json(explicit_workspace / ".copilot-ilongrun" / "runs" / explicit_run_id / "scheduler.json")
        assert explicit_scheduler.get("selectedModel") == "claude-haiku-4.5"
        assert explicit_scheduler.get("codingAuditModel") == "claude-haiku-4.5"
        assert explicit_scheduler.get("fallbackChain") == []
        assert (explicit_scheduler.get("modelEnforcement") or {}).get("active") is True
        assert (explicit_scheduler.get("modelEnforcement") or {}).get("scope") == "full-chain"
        assert (explicit_scheduler.get("reviews") or {}).get("auditModel") == "claude-haiku-4.5"
        assert set((explicit_scheduler.get("mission") or {}).get("modelAllocation", {}).values()) == {"claude-haiku-4.5"}
        assert "gpt54-audit-reviewer" not in ((explicit_scheduler.get("mission") or {}).get("modelAllocation") or {})
        assert {ws.get("ownerModel") for ws in (explicit_scheduler.get("workstreams") or [])} == {"claude-haiku-4.5"}

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

        model_info_explicit = run(
            str(ROOT / "model_policy_info.py"),
            "--config", str(ROOT.parent / "config" / "model-policy.jsonc"),
            "--subcommand", "coding",
            "--skill", "ilongrun-coding",
            "--explicit-model", "claude-haiku-4.5",
            "--json",
        )
        model_info_explicit_payload = json.loads(model_info_explicit.stdout)
        assert model_info_explicit_payload["selected"] == "claude-haiku-4.5"
        assert model_info_explicit_payload["chain"] == ["claude-haiku-4.5"]

        model_home = temp_root / "model-home"
        install_config_path = model_home / "config" / "model-policy.jsonc"
        install_config_path.parent.mkdir(parents=True, exist_ok=True)
        install_policy = default_model_config()
        install_policy["roleModels"]["code-reviewer"] = "claude-sonnet-4.6"
        install_policy["roleModels"]["test-engineer"] = "claude-sonnet-4.6"
        install_policy["roleModels"]["security-auditor"] = "claude-sonnet-4.6"
        install_config_path.write_text(json.dumps(install_policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        fake_repo = temp_root / "fake-ilongrun-repo"
        (fake_repo / "config").mkdir(parents=True, exist_ok=True)
        (fake_repo / "plugin.json").write_text(json.dumps({"name": "ilongrun"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        repo_policy = default_model_config()
        (fake_repo / "config" / "model-policy.jsonc").write_text(json.dumps(repo_policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        external_workspace = temp_root / "external-workspace"
        external_workspace.mkdir(parents=True, exist_ok=True)
        fake_bin = temp_root / "fake-bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        fake_copilot = fake_bin / "copilot"
        fake_copilot.write_text("#!/usr/bin/env bash\necho OK\n", encoding="utf-8")
        fake_copilot.chmod(0o755)
        refresh_env = {
            "ILONGRUN_HOME": str(model_home),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "COPILOT_GITHUB_TOKEN": "test-token",
        }

        model_show_text = subprocess.run(
            ["python3", str(ROOT / "manage_ilongrun_model.py"), "--workspace", str(external_workspace)],
            capture_output=True,
            text=True,
            env={**os.environ, "ILONGRUN_HOME": str(model_home)},
        )
        assert model_show_text.returncode == 0
        assert "iLongRun 主模型模板" in model_show_text.stdout
        assert "run=`claude-sonnet-4.6`" in model_show_text.stdout

        model_show_explicit = run(
            str(ROOT / "manage_ilongrun_model.py"),
            "--workspace", str(external_workspace),
            "--json",
            "show",
            env={"ILONGRUN_HOME": str(model_home)},
        )
        assert json.loads(model_show_explicit.stdout)["mode"] == "show"

        model_show = run(
            str(ROOT / "manage_ilongrun_model.py"),
            "--workspace", str(external_workspace),
            "--json",
            env={"ILONGRUN_HOME": str(model_home)},
        )
        model_show_payload = json.loads(model_show.stdout)
        assert model_show_payload["repoDetected"] is False
        assert len(model_show_payload["targets"]) == 1
        assert model_show_payload["targets"][0]["scope"] == "install"
        assert model_show_payload["skippedRepoPath"]

        model_refresh = run(
            str(ROOT / "manage_ilongrun_model.py"),
            "--workspace", str(external_workspace),
            "--json",
            "--refresh",
            env=refresh_env,
        )
        model_refresh_payload = json.loads(model_refresh.stdout)
        assert model_refresh_payload["mode"] == "show"
        assert model_refresh_payload["refresh"]["status"] == "refreshed"
        assert model_refresh_payload["refresh"]["models"]["claude-sonnet-4.6"]["status"] == "available"

        model_set = run(
            str(ROOT / "manage_ilongrun_model.py"),
            "--workspace", str(fake_repo),
            "--json",
            "claude-haiku-4.5",
            env={"ILONGRUN_HOME": str(model_home)},
        )
        model_set_payload = json.loads(model_set.stdout)
        assert model_set_payload["mode"] == "set"
        assert model_set_payload["effectiveModel"] == "claude-haiku-4.5"
        assert {item["scope"] for item in model_set_payload["targets"]} == {"install", "repo"}
        install_after_set = read_json(install_config_path)
        repo_after_set = read_json(fake_repo / "config" / "model-policy.jsonc")
        for payload in (install_after_set, repo_after_set):
            assert payload["commandDefaults"]["run"] == "claude-haiku-4.5"
            assert payload["commandDefaults"]["coding"] == "claude-haiku-4.5"
            assert payload["skillDefaults"]["ilongrun"] == "claude-haiku-4.5"
            assert payload["skillDefaults"]["ilongrun-coding"] == "claude-haiku-4.5"
            for role in ("mission-governor", "strategy-synthesizer", "phase-planner", "workstream-planner", "ledger-syncer", "executor", "recovery-agent"):
                assert payload["roleModels"][role] == "claude-haiku-4.5"
            for role in ("code-reviewer", "test-engineer", "security-auditor"):
                assert payload["roleModels"][role] == "gpt-5.4"
            assert payload["codingAuditModel"] == "gpt-5.4"
            assert payload["roleModels"]["final-audit-reviewer"] == "gpt-5.4"
            assert payload["commandDefaults"]["prompt"] == "claude-sonnet-4.6"
            assert payload["commandDefaults"]["resume"] == "claude-sonnet-4.6"
            assert payload["commandDefaults"]["status"] == "claude-sonnet-4.6"
            assert payload["commandDefaults"]["doctor"] == "claude-sonnet-4.6"

        bad_model = run(
            str(ROOT / "manage_ilongrun_model.py"),
            "--workspace", str(fake_repo),
            "--json",
            "definitely-unknown-model",
            ok=False,
            env={"ILONGRUN_HOME": str(model_home)},
        )
        assert bad_model.returncode == 2
        assert json.loads(bad_model.stdout)["ok"] is False

        picker_set = run(
            str(ROOT / "manage_ilongrun_model.py"),
            "--workspace", str(fake_repo),
            "--json",
            "--test-select", "gpt-5-mini",
            env={"ILONGRUN_HOME": str(model_home)},
        )
        picker_set_payload = json.loads(picker_set.stdout)
        assert picker_set_payload["mode"] == "set"
        assert picker_set_payload["selectionSource"] == "picker"
        install_after_picker = read_json(install_config_path)
        repo_after_picker = read_json(fake_repo / "config" / "model-policy.jsonc")
        for payload in (install_after_picker, repo_after_picker):
            assert payload["commandDefaults"]["run"] == "gpt-5-mini"
            assert payload["commandDefaults"]["coding"] == "gpt-5-mini"
            assert payload["roleModels"]["executor"] == "gpt-5-mini"
            assert payload["roleModels"]["code-reviewer"] == "gpt-5.4"
            assert payload["codingAuditModel"] == "gpt-5.4"

        model_reset = run(
            str(ROOT / "manage_ilongrun_model.py"),
            "--workspace", str(fake_repo),
            "--json",
            "reset",
            env={"ILONGRUN_HOME": str(model_home)},
        )
        model_reset_payload = json.loads(model_reset.stdout)
        assert model_reset_payload["mode"] == "reset"
        install_after_reset = read_json(install_config_path)
        repo_after_reset = read_json(fake_repo / "config" / "model-policy.jsonc")
        for payload in (install_after_reset, repo_after_reset):
            assert payload["commandDefaults"]["run"] == "claude-sonnet-4.6"
            assert payload["commandDefaults"]["coding"] == "claude-opus-4.6"
            assert payload["skillDefaults"]["ilongrun"] == "claude-sonnet-4.6"
            assert payload["skillDefaults"]["ilongrun-coding"] == "claude-opus-4.6"
            assert payload["roleModels"]["mission-governor"] == "claude-sonnet-4.6"
            assert payload["roleModels"]["executor"] == "claude-opus-4.6"
            assert payload["roleModels"]["code-reviewer"] == "gpt-5.4"
            assert payload["roleModels"]["test-engineer"] == "gpt-5.4"
            assert payload["roleModels"]["security-auditor"] == "gpt-5.4"

        model_cli = subprocess.run(
            ["bash", str(ROOT / "copilot-ilongrun"), "model"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env={**os.environ, "ILONGRUN_HOME": str(model_home)},
        )
        assert model_cli.returncode == 0
        assert "iLongRun 主模型模板" in model_cli.stdout
        assert "gpt-5.4" in model_cli.stdout

        dry_env = {**os.environ, "ILONGRUN_HOME": str(model_home), "COPILOT_GITHUB_TOKEN": "test-token", "COPILOT_BIN": "python3"}
        run_dry = subprocess.run(
            ["bash", str(ROOT / "copilot-ilongrun"), "run", "--dry-run", "帮我写 README"],
            capture_output=True,
            text=True,
            cwd=str(external_workspace),
            env=dry_env,
        )
        assert run_dry.returncode == 0
        assert "--model claude-sonnet-4.6" in run_dry.stdout
        coding_dry = subprocess.run(
            ["bash", str(ROOT / "copilot-ilongrun"), "coding", "--dry-run", "修一个 bug 并补测试"],
            capture_output=True,
            text=True,
            cwd=str(external_workspace),
            env=dry_env,
        )
        assert coding_dry.returncode == 0
        assert "--model claude-opus-4.6" in coding_dry.stdout

        resume_model_workspace = temp_root / "resume-model-workspace"
        resume_model_workspace.mkdir(parents=True, exist_ok=True)
        run(
            str(ROOT / "prepare_ilongrun_run.py"),
            "--workspace", str(resume_model_workspace),
            "--task", "修一个小 bug 并补测试",
            "--force-profile", "coding",
            "--explicit-model", "claude-haiku-4.5",
            "--session-model", "claude-haiku-4.5",
            "--model-control-mode", "explicit-model-locked",
        )
        resume_dry = subprocess.run(
            ["bash", str(ROOT / "copilot-ilongrun"), "resume", "--dry-run", "latest"],
            capture_output=True,
            text=True,
            cwd=str(resume_model_workspace),
            env=dry_env,
        )
        assert resume_dry.returncode == 0
        assert "--model claude-haiku-4.5" in resume_dry.stdout

        supervisor_coding_chain = run_inline(
            "\n".join(
                [
                    "from pathlib import Path",
                    "import json",
                    "import sys",
                    f"sys.path.insert(0, {str(ROOT)!r})",
                    "import launch_ilongrun_supervisor as sup",
                    "from _ilongrun_shared import load_model_config, model_availability_snapshot",
                    f"cfg = load_model_config({str(ROOT.parent / 'config' / 'model-policy.jsonc')!r})",
                    "av = model_availability_snapshot(cfg, cache={'version': 1, 'accounts': {}})",
                    "class Args:",
                    "    explicit_model = None",
                    "    mode = 'run'",
                    "    force_profile = 'coding'",
                    f"chain = sup.supervisor_model_chain(Args(), workspace=Path({str(explicit_workspace)!r}), run_ref={explicit_run_id!r}, payload='ignored', config=cfg, availability=av)",
                    "print(json.dumps(chain, ensure_ascii=False))",
                ]
            )
        )
        assert json.loads(supervisor_coding_chain.stdout) == ["claude-haiku-4.5"]

        supervisor_resume_chain = run_inline(
            "\n".join(
                [
                    "from pathlib import Path",
                    "import json",
                    "import sys",
                    f"sys.path.insert(0, {str(ROOT)!r})",
                    "import launch_ilongrun_supervisor as sup",
                    "from _ilongrun_shared import load_model_config, model_availability_snapshot",
                    f"cfg = load_model_config({str(ROOT.parent / 'config' / 'model-policy.jsonc')!r})",
                    "av = model_availability_snapshot(cfg, cache={'version': 1, 'accounts': {}})",
                    "class Args:",
                    "    explicit_model = None",
                    "    mode = 'resume'",
                    "    force_profile = None",
                    f"chain = sup.supervisor_model_chain(Args(), workspace=Path({str(resume_model_workspace)!r}), run_ref='latest', payload='latest', config=cfg, availability=av)",
                    "print(json.dumps(chain, ensure_ascii=False))",
                ]
            )
        )
        assert json.loads(supervisor_resume_chain.stdout) == ["claude-haiku-4.5"]

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
            "--version", "0.7.0",
        )
        assert "知识船仓·公益社区" in install_board.stdout
        assert "倾力制作～" in install_board.stdout
        assert "====" in install_board.stdout
        assert "v0.7.0" in install_board.stdout

        doctor_checks = temp_root / "doctor-checks.tsv"
        doctor_checks.write_text(
            "\n".join(
                [
                    "launcher.ilongrun\tok\t/tmp/ilongrun",
                    "launcher.ilongrun-coding\tok\t/tmp/ilongrun-coding",
                    "launcher.ilongrun-model\tok\t/tmp/ilongrun-model",
                    "launcher.ilongrun-prompt\tok\t/tmp/ilongrun-prompt",
                    "launcher.ilongrun-resume\tok\t/tmp/ilongrun-resume",
                    "launcher.ilongrun-status\tok\t/tmp/ilongrun-status",
                    "launcher.ilongrun-doctor\tok\t/tmp/ilongrun-doctor",
                    "launcher.copilot-ilongrun\tok\t/tmp/copilot-ilongrun",
                    "copilot\tok\t/tmp/copilot",
                    "login\tok\ttest-user@https://github.com",
                    "model_policy\tok\t/tmp/model-policy.jsonc",
                    "coding_protocol\tok\t/tmp/coding-protocol.jsonc",
                    "vendor_snapshot\tok\t/tmp/vendor/agent-skills",
                    "coding_playbooks\tok\t/tmp/skills/ilongrun-coding",
                    "coding_agents\tok\t/tmp/agents",
                    "skill_lint\tok\t/tmp/lint_ilongrun_skills.py",
                    "model_helper\tok\t/tmp/manage_ilongrun_model.py",
                    "legacy_skill.ilongrun-model\twarn\t/tmp/skills/ilongrun-model（legacy 会话入口残留，可清理）",
                    "legacy_plugin\tok\t未启用（copilot-mission-control）",
                    "workspace_legacy\tok\t未发现旧工作区残留",
                    "screen\tok\t/usr/bin/screen",
                    "terminal_notifier\tok\t/tmp/terminal-notifier",
                    "selftest\tok\t已通过",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        doctor_model_json = temp_root / "doctor-model.json"
        doctor_model_json.write_text(
            json.dumps(
                {
                    "ok": True,
                    "identity": "test-user@https://github.com",
                    "cache": str(temp_root / "model-availability.json"),
                    "models": {
                        "claude-sonnet-4.6": {"displayName": "Claude Sonnet 4.6", "status": "available", "reason": "probe-success"},
                        "claude-opus-4.6": {"displayName": "Claude Opus 4.6", "status": "available", "reason": "probe-success"},
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        doctor_fleet_json = temp_root / "doctor-fleet.json"
        doctor_fleet_json.write_text(
            json.dumps(
                {
                    "ok": True,
                    "status": "supported",
                    "reason": "probe-success",
                    "probeModel": "claude-sonnet-4.6",
                    "probeModelDisplay": "Claude Sonnet 4.6",
                    "cache": str(temp_root / "capabilities.json"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        doctor_board = run(
            str(ROOT / "render_ilongrun_doctor_board.py"),
            "--checks-file", str(doctor_checks),
            "--model-probe-json", str(doctor_model_json),
            "--fleet-probe-json", str(doctor_fleet_json),
            "--selftest-log", str(temp_root / "selftest.err"),
            "--refresh-cache", "1",
        )
        assert "环境体检看板" in doctor_board.stdout
        assert "模型缓存刷新结果" in doctor_board.stdout
        assert "旧会话入口" in doctor_board.stdout
        assert "倾力制作～" in doctor_board.stdout

        bad_skill = temp_root / "bad-skill" / "SKILL.md"
        bad_skill.parent.mkdir(parents=True, exist_ok=True)
        bad_skill.write_text(
            "---\nname: demo\ndescription: A long summary instead of a trigger.\n---\n\n## Demo\n",
            encoding="utf-8",
        )
        lint_fail = run(
            str(ROOT / "lint_ilongrun_skills.py"),
            "--path", str(bad_skill),
            "--json",
            ok=False,
        )
        lint_fail_payload = json.loads(lint_fail.stdout)
        assert lint_fail.returncode != 0
        assert "frontmatter description must start" in " ".join(lint_fail_payload["results"][0]["findings"])
        bad_skill.write_text(
            "---\nname: demo\ndescription: 当用户需要一个极小的 demo skill 时使用。\n---\n\n## Demo\n\n- ok\n",
            encoding="utf-8",
        )
        lint_fix = run(
            str(ROOT / "lint_ilongrun_skills.py"),
            "--path", str(bad_skill),
            "--json",
        )
        assert json.loads(lint_fix.stdout)["ok"] is True
        lint_repo = run(
            str(ROOT / "lint_ilongrun_skills.py"),
            "--json",
        )
        assert json.loads(lint_repo.stdout)["ok"] is True

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
        assert (coding_sched.get("swarmPolicy") or {}).get("defaultMode") == "swarm-wave"
        assert (coding_sched.get("reviewMatrix") or {}).get("gates")
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
        run(
            str(ROOT / "write_ilongrun_scheduler.py"),
            "--workspace", str(workspace),
            "--run-id", run_id,
            "--patch-json", json.dumps({"summary": "scheduler writer patch"}, ensure_ascii=False),
        )
        writer_scheduler = read_json(run_dir / "scheduler.json")
        assert writer_scheduler.get("summary") == "scheduler writer patch"
        assert (writer_scheduler.get("projectionState") or {}).get("ledgerSyncReason") == "scheduler-write-cli"

        run_inline(
            "from pathlib import Path; "
            f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
            "import launch_ilongrun_supervisor as sup; "
            f"sup.patch_scheduler(Path({str(workspace)!r}), {run_id!r}, selected_model='gpt-5.4', note='selftest-launcher')"
        )
        launcher_scheduler = read_json(run_dir / "scheduler.json")
        assert launcher_scheduler.get("selectedModel") == "gpt-5.4"
        assert (launcher_scheduler.get("projectionState") or {}).get("ledgerSyncReason") == "launcher-model-selected:gpt-5.4"
        run_inline(
            "from pathlib import Path; "
            f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
            "import launch_ilongrun_supervisor as sup; "
            f"sup.update_fleet_runtime(Path({str(workspace)!r}), {run_id!r}, "
            "{'status': 'supported', 'reason': 'probe-success', 'checkedAt': '2026-04-07T01:00:00Z', 'probeModel': 'claude-sonnet-4.6', 'probeModelDisplay': 'Claude Sonnet 4.6', 'cache': '/tmp/fleet-cache.json', 'rawOutput': 'FLEET_OK'} )"
        )
        fleet_scheduler = read_json(run_dir / "scheduler.json")
        fleet_capability = ((fleet_scheduler.get("runtime") or {}).get("fleetCapability") or {})
        assert fleet_capability.get("status") == "supported"
        assert fleet_capability.get("probeModelDisplay") == "Claude Sonnet 4.6"
        assert fleet_capability.get("cache") == "/tmp/fleet-cache.json"
        assert fleet_capability.get("rawOutputDigest")
        assert (fleet_scheduler.get("projectionState") or {}).get("ledgerSyncReason") == "fleet-runtime-updated"
        fleet_wave_id = next(
            (
                wave.get("id")
                for phase in fleet_scheduler.get("phases") or []
                for wave in phase.get("waves") or []
                if str(wave.get("id") or "").startswith("wave-build-")
            ),
            "",
        )
        assert fleet_wave_id, "build fleet wave missing"
        run_inline(
            "from pathlib import Path; import json; "
            f"p = Path({str(run_dir / 'scheduler.json')!r}); "
            "data = json.loads(p.read_text(encoding='utf-8')); "
            f"waves = [wave for phase in data.get('phases') or [] for wave in phase.get('waves') or [] if wave.get('id') == {fleet_wave_id!r}]; "
            f"assert waves, '{fleet_wave_id} missing'; "
            "waves[0]['backend'] = 'fleet'; "
            "p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')"
        )
        run_inline(
            "from pathlib import Path; "
            f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
            "import launch_ilongrun_supervisor as sup; "
            f"sup.mark_fleet_dispatch_started(Path({str(workspace)!r}), {run_id!r}, {fleet_wave_id!r}, 'claude-sonnet-4.6')"
        )
        run_inline(
            "from pathlib import Path; "
            f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
            "import launch_ilongrun_supervisor as sup; "
            f"sup.set_wave_backend(Path({str(workspace)!r}), {run_id!r}, {fleet_wave_id!r}, 'internal', 'selftest degrade', 'degradedWaves', outcome='degraded', model='claude-sonnet-4.6', rc=1, fallback_reason='command-not-recognized')"
        )
        fleet_scheduler = read_json(run_dir / "scheduler.json")
        fleet_dispatch = ((fleet_scheduler.get("runtime") or {}).get("fleetDispatch") or {})
        assert fleet_wave_id in (fleet_dispatch.get("degradedWaves") or [])
        assert fleet_dispatch.get("lastOutcome") == "degraded"
        assert len(fleet_dispatch.get("dispatchEvents") or []) >= 2
        assert any(item.get("outcome") == "dispatch-started" for item in fleet_dispatch.get("dispatchEvents") or [])
        assert any(item.get("fallbackReason") == "command-not-recognized" for item in fleet_dispatch.get("dispatchEvents") or [])

        for ws in workstreams:
            ws_status = completed_status_payload(ws)
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
        failed_scheduler = read_json(run_dir / "scheduler.json")
        assert (failed_scheduler.get("projectionState") or {}).get("ledgerSyncReason") == "finalize-precheck-failed"

        review_dir = run_dir / "reviews"
        review_dir.mkdir(exist_ok=True)
        (review_dir / "final-review.md").write_text(
            "# ILongRun Final Review\n\n## Run Metadata\n- Run ID: `demo`\n- Audit model: `gpt-5.4`\n\n## Summary\n- 审查范围：demo\n- 总发现数：`0`\n\n## Findings\n### Must-Fix (Critical)\n- None.\n\n### Should-Fix (Major)\n- None.\n\n### Nit (Minor)\n- naming polish only\n\n## Suggested Fixes\n- none\n\n## Residual Risks\n- low residual risk\n\n## Verdict\n- PASS\n",
            encoding="utf-8",
        )
        run(str(ROOT / "reconcile_ilongrun_run.py"), "--workspace", str(workspace), "--run-id", run_id)
        reconciled_after_review = read_json(run_dir / "scheduler.json")
        assert (reconciled_after_review.get("reviews") or {}).get("pendingMustFixCount") == 0
        assert (reconciled_after_review.get("reviews") or {}).get("defer") == ["low residual risk"]
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
        assert (final_scheduler.get("projectionState") or {}).get("ledgerSyncReason") == "finalize-complete"
        assert (run_dir / "COMPLETION.md").exists()
        completion_text = (run_dir / "COMPLETION.md").read_text(encoding="utf-8")
        assert "## Run Metadata" in completion_text
        assert "## Summary" in completion_text
        assert "## Completion Score" in completion_text
        assert "## Verification Evidence" in completion_text
        assert "## Verdict" in completion_text
        assert not (workspace / ".copilot-ilongrun" / "state" / "active-run-id").exists()
        status_board = subprocess.run(
            ["bash", str(ROOT / "copilot-ilongrun"), "status", run_id],
            capture_output=True,
            text=True,
            cwd=str(workspace),
            env={**os.environ, "ILONGRUN_HOME": str(helper_home)},
        )
        assert status_board.returncode == 0
        assert "状态看板" in status_board.stdout
        assert "真实完成度" in status_board.stdout
        assert "方法学门禁" in status_board.stdout
        assert "账本与投影" in status_board.stdout
        assert "投影日志" in status_board.stdout
        assert "分发证据" in status_board.stdout
        assert "最终判定" in status_board.stdout

        hook_local = run_dir / "hook-events.jsonl"
        hook_before = hook_local.read_text(encoding="utf-8").splitlines() if hook_local.exists() else []
        (workspace / ".copilot-ilongrun" / "state" / "active-run-id").write_text(run_id, encoding="utf-8")
        final_scheduler["state"] = "completed"
        (run_dir / "scheduler.json").write_text(json.dumps(final_scheduler, ensure_ascii=False, indent=2), encoding="utf-8")
        run(
            str(ROOT / "hook_event.py"),
            env={"HOOK_EVENT": "preToolUse"},
            input_text=json.dumps({"cwd": str(workspace), "toolName": "bash", "toolArgs": {"command": "echo test"}}, ensure_ascii=False),
        )
        hook_after = hook_local.read_text(encoding="utf-8").splitlines() if hook_local.exists() else []
        assert hook_after == hook_before
        assert not (workspace / ".copilot-ilongrun" / "state" / "active-run-id").exists()

        ledger_workspace = temp_root / "ledger-workspace"
        ledger_workspace.mkdir(parents=True, exist_ok=True)
        run(
            str(ROOT / "prepare_ilongrun_run.py"),
            "--workspace", str(ledger_workspace),
            "--task", "实现一个多人原型并输出审计文档",
            "--force-profile", "coding",
        )
        ledger_run_id = (ledger_workspace / ".copilot-ilongrun" / "state" / "latest-run-id").read_text(encoding="utf-8").strip()
        ledger_run_dir = ledger_workspace / ".copilot-ilongrun" / "runs" / ledger_run_id
        ledger_scheduler = read_json(ledger_run_dir / "scheduler.json")
        ledger_scheduler["state"] = "completed"
        ledger_scheduler["taskLists"] = []
        ledger_scheduler["deliverables"] = []
        ledger_scheduler["requestedDeliverables"] = []
        ledger_scheduler.setdefault("mission", {})["requestedDeliverables"] = []
        for ws in ledger_scheduler.get("workstreams") or []:
            ws["status"] = "complete"
            ws["microcycleState"] = completed_status_payload(ws)["microcycleState"]
            ws["reviewSequence"] = completed_status_payload(ws)["reviewSequence"]
            ws["freshEvidence"] = completed_status_payload(ws)["freshEvidence"]
            ws["rootCauseRecord"] = completed_status_payload(ws)["rootCauseRecord"]
            ws.pop("index", None)
            ws.pop("taskListId", None)
            ws.pop("taskListPath", None)
            status_path = ledger_run_dir / ws["statusPath"]
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(
                json.dumps(completed_status_payload(ws), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (ledger_run_dir / ws["resultPath"]).write_text("# Result\n\nDone.\n", encoding="utf-8")
            (ledger_run_dir / ws["evidencePath"]).write_text("# Evidence\n\nVerified.\n", encoding="utf-8")
        (ledger_run_dir / "reviews").mkdir(exist_ok=True)
        (ledger_run_dir / "reviews" / "final-review.md").write_text(
            "# GPT-5.4 Final Review\n\n## Must-fix\n- None.\n\n## Suggested fixes\n- none\n\n## Residual risks\n- low\n",
            encoding="utf-8",
        )
        (ledger_run_dir / "reviews" / "adjudication.md").write_text("# adjudication\n\n- proceed\n", encoding="utf-8")
        (ledger_run_dir / "COMPLETION.md").write_text("# completion\n", encoding="utf-8")
        (ledger_workspace / ".copilot-ilongrun" / "state" / "active-run-id").write_text(ledger_run_id, encoding="utf-8")
        (ledger_run_dir / "scheduler.json").write_text(json.dumps(ledger_scheduler, ensure_ascii=False, indent=2), encoding="utf-8")

        ledger_sync = run(
            str(ROOT / "sync_ilongrun_ledger.py"),
            "--workspace", str(ledger_workspace),
            "--run-id", ledger_run_id,
            "--clean-active-on-complete",
            "--print-json",
        )
        ledger_sync_payload = json.loads(ledger_sync.stdout)
        assert ledger_sync_payload["ok"] is True
        assert ledger_sync_payload["activeCleared"] is True
        synced_scheduler = read_json(ledger_run_dir / "scheduler.json")
        assert synced_scheduler["state"] == "complete"
        assert synced_scheduler.get("taskLists")
        assert synced_scheduler.get("reviews", {}).get("pendingMustFixCount") == 0
        adjudication_text = (ledger_run_dir / "reviews" / "adjudication.md").read_text(encoding="utf-8")
        assert "## Run Metadata" in adjudication_text
        assert "## Findings Intake" in adjudication_text
        assert "## Decision" in adjudication_text
        assert "## Next Actions" in adjudication_text
        assert "## Verdict" in adjudication_text
        task_list_text = (ledger_run_dir / "task-list-1.md").read_text(encoding="utf-8")
        assert "- [x]" in task_list_text

        first_ws = (synced_scheduler.get("workstreams") or [])[0]
        bad_status = read_json(ledger_run_dir / first_ws["statusPath"])
        bad_status["startedAt"] = "2026-04-07T06:55:00Z"
        bad_status["completedAt"] = "2026-04-07T00:32:13Z"
        (ledger_run_dir / first_ws["statusPath"]).write_text(json.dumps(bad_status, ensure_ascii=False, indent=2), encoding="utf-8")
        bad_sync = run(
            str(ROOT / "sync_ilongrun_ledger.py"),
            "--workspace", str(ledger_workspace),
            "--run-id", ledger_run_id,
            "--print-json",
            ok=False,
        )
        bad_sync_payload = json.loads(bad_sync.stdout)
        assert bad_sync.returncode != 0
        assert "completedAt earlier than startedAt" in " ".join(bad_sync_payload["verification"]["driftFindings"])

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
        (drift_legacy / "reviews" / "final-review.md").write_text("# Final Review\n\n## Must-fix\n- None\n", encoding="utf-8")
        run(str(ROOT / "reconcile_ilongrun_run.py"), "--workspace", str(drift_workspace), "--run-id", drift_run_id)
        assert not drift_legacy.exists()
        assert (drift_canonical / "reviews" / "final-review.md").exists()
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

        delivery_workspace = temp_root / "delivery-gap-workspace"
        (delivery_workspace / "src" / "core").mkdir(parents=True, exist_ok=True)
        (delivery_workspace / "src" / "network").mkdir(parents=True, exist_ok=True)
        (delivery_workspace / "src" / "ui").mkdir(parents=True, exist_ok=True)
        (delivery_workspace / "src" / "room").mkdir(parents=True, exist_ok=True)
        (delivery_workspace / "src" / "ai").mkdir(parents=True, exist_ok=True)
        (delivery_workspace / "package.json").write_text(
            json.dumps({"name": "delivery-gap-demo", "private": True}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (delivery_workspace / "src" / "main.ts").write_text(
            "import { GameClient } from './core/GameClient';\nnew GameClient().start();\n",
            encoding="utf-8",
        )
        (delivery_workspace / "src" / "core" / "GameClient.ts").write_text(
            "export class GameClient { start(): void {} }\n",
            encoding="utf-8",
        )
        (delivery_workspace / "src" / "network" / "NetworkManager.ts").write_text(
            "export class NetworkManager { connect(): void {} }\n",
            encoding="utf-8",
        )
        (delivery_workspace / "src" / "ui" / "VoteUI.ts").write_text(
            "export class VoteUI { mount(): void {} }\n",
            encoding="utf-8",
        )
        (delivery_workspace / "src" / "core" / "RoomManager.ts").write_text(
            "export class RoomManager { start(): void {} }\n",
            encoding="utf-8",
        )
        (delivery_workspace / "src" / "room" / "RoomManager.ts").write_text(
            "export class RoomManager { stop(): void {} }\n",
            encoding="utf-8",
        )
        (delivery_workspace / "src" / "ai" / "LLMProvider.ts").write_text(
            "export class NoopLLMProvider { isAvailable(): boolean { return false; } }\n// 空实现 noop placeholder\n",
            encoding="utf-8",
        )
        delivery_scan = run(
            str(ROOT / "scan_ilongrun_delivery_gaps.py"),
            "--workspace", str(delivery_workspace),
            "--json",
            ok=False,
        )
        delivery_scan_payload = json.loads(delivery_scan.stdout)
        assert delivery_scan_payload["supported"] is True
        kinds = [item.get("kind") for item in delivery_scan_payload.get("findings") or []]
        assert "unwired-runtime-module" in kinds
        assert "duplicate-core-module" in kinds
        assert "placeholder-provider" in kinds

        run(
            str(ROOT / "prepare_ilongrun_run.py"),
            "--workspace", str(delivery_workspace),
            "--task", "实现一个多人游戏原型并完成 coding 审计",
            "--force-profile", "coding",
        )
        delivery_run_id = (delivery_workspace / ".copilot-ilongrun" / "state" / "latest-run-id").read_text(encoding="utf-8").strip()
        delivery_verify = run(
            str(ROOT / "verify_ilongrun_run.py"),
            "--workspace", str(delivery_workspace),
            "--run-id", delivery_run_id,
            "--json",
            ok=False,
        )
        delivery_verify_payload = json.loads(delivery_verify.stdout)
        assert any("delivery audit flagged" in item for item in delivery_verify_payload.get("driftFindings") or [])
        delivery_score = delivery_verify_payload.get("completionScore") or {}
        assert delivery_score.get("deliveryVerdict") in {"blocked", "implemented-not-wired"}
        assert ((delivery_score.get("layers") or {}).get("codeExists") or {}).get("score", 0) >= 0
        assert ((delivery_score.get("layers") or {}).get("wiredIntoEntry") or {}).get("score", 100) < 60
        delivery_report = delivery_workspace / ".copilot-ilongrun" / "runs" / delivery_run_id / "reviews" / "delivery-audit.md"
        assert delivery_report.exists()
        delivery_report_text = delivery_report.read_text(encoding="utf-8")
        assert "NetworkManager.ts" in delivery_report_text
        assert "RoomManager" in delivery_report_text
        delivery_status_board = subprocess.run(
            ["python3", str(ROOT / "render_ilongrun_status_board.py"), "--workspace", str(delivery_workspace), "--run-id", delivery_run_id],
            capture_output=True,
            text=True,
        )
        assert delivery_status_board.returncode == 0
        assert "已实现但未接主链" in delivery_status_board.stdout
        assert "delivery-audit.md" in delivery_status_board.stdout

        print("ILongRun selftest passed")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
