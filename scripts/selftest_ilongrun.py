#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args: str, ok: bool = True):
    proc = subprocess.run(["python3", *args], capture_output=True, text=True)
    if ok and proc.returncode != 0:
        raise RuntimeError(f"command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
            "--headline", "should fail without GPT-5.4 review",
            "--local-verify",
            ok=False,
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
        )
        assert ok_finalize.returncode == 0
        final_scheduler = read_json(run_dir / "scheduler.json")
        assert final_scheduler.get("state") == "complete"
        assert (run_dir / "COMPLETION.md").exists()
        print("ILongRun selftest passed")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
