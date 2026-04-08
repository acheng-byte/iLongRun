#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_report_templates import (
    build_blocked_report_markdown,
    build_completion_report_markdown,
    build_failed_report_markdown,
)
from _ilongrun_lib import (
    adjudication_path,
    blocked_path,
    claim_verification_is_complete,
    clear_terminal_reports,
    completion_path,
    failed_path,
    final_review_path,
    is_run_blocked_state,
    is_run_complete_state,
    is_run_failed_state,
    normalize_run_state,
    persist_run_ledger,
    reconcile_scheduler,
    resolve_run_target,
    terminal_report_path,
    verify_scheduler,
    write_text_atomic,
)


def verification_snapshot(verification: dict[str, Any], *, state: str) -> dict[str, Any]:
    status = "passed" if state == "completed" and verification.get("ok") else "failed"
    return {
        "state": status,
        "hardFailures": verification.get("hardFailures", []),
        "softWarnings": verification.get("softWarnings", []),
        "driftFindings": verification.get("driftFindings", []),
        "recommendedAction": verification.get("recommendedAction"),
        "failureClass": verification.get("failureClass"),
        "lastVerifiedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "completionScore": verification.get("completionScore"),
    }


def build_terminal_markdown(sched: dict[str, Any], *, status_name: str, headline: str, verification_items: list[str], blockers: list[str]) -> str:
    verification = sched.get("verification") or {}
    reviews = sched.get("reviews") or {}
    common = {
        "run_id": str(sched.get("runId") or ""),
        "status_name": status_name,
        "profile": str(sched.get("profile") or "unknown"),
        "selected_model": str(sched.get("selectedModel") or "unknown"),
        "headline": headline,
        "verification_state": str(verification.get("state") or "pending"),
        "review_status": str(reviews.get("status") or "not-required"),
        "adjudication_status": str(reviews.get("adjudicationStatus") or "not-required"),
        "completion_score": verification.get("completionScore") or {},
        "deliverables": list(sched.get("deliverables") or []),
        "verification_items": verification_items,
        "blockers": blockers,
    }
    state = normalize_run_state(status_name)
    if state == "completed":
        return build_completion_report_markdown(**common)
    if state == "blocked":
        return build_blocked_report_markdown(**common)
    return build_failed_report_markdown(**common)


def notify(target, event: str, *, title: str, subtitle: str, message: str, open_path: Path | None = None, sound: bool = False) -> None:
    helper = SCRIPT_DIR / "notify_macos.py"
    if not helper.exists():
        return
    cmd = [
        sys.executable,
        str(helper),
        "--workspace", str(target.workspace),
        "--run-id", target.run_id,
        "--event", event,
        "--title", title,
        "--subtitle", subtitle,
        "--message", message,
    ]
    if open_path:
        cmd.extend(["--open", str(open_path)])
    if sound:
        cmd.append("--sound")
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def completed_precheck_failures(target, sched: dict[str, Any], verification: dict[str, Any]) -> list[str]:
    failures = list(verification.get("hardFailures") or [])
    if not verification.get("ok"):
        return failures
    claim_verification = sched.get("claimVerification") or {}
    reviews = sched.get("reviews") or {}
    if sched.get("profile") == "coding":
        if not claim_verification_is_complete(claim_verification):
            missing = ", ".join(claim_verification.get("missingWorkstreams") or []) or "unknown"
            failures.append(f"claimVerification incomplete: {missing}")
        if not final_review_path(target).exists():
            failures.append("reviews/final-review.md is missing")
        if not adjudication_path(target).exists():
            failures.append("reviews/adjudication.md is missing")
        for gate_id, gate_state in ((reviews.get("gateStatus") or {}).items()):
            if gate_state != "complete":
                failures.append(f"phase-review gate incomplete: {gate_id}")
        pending = int(reviews.get("pendingMustFixCount") or 0)
        if pending > 0:
            failures.append(f"unresolved must-fix items remain: {pending}")
        final_verdict = str(reviews.get("finalVerdict") or "pending").upper()
        if final_verdict not in {"PASS", "PASS_WITH_CONDITIONS"}:
            failures.append(f"final review verdict not finalizable: {final_verdict.lower()}")
        if str(reviews.get("adjudicationDecision") or "pending").lower() != "proceed-to-finalize":
            failures.append("adjudication decision is not proceed-to-finalize")
        if str(reviews.get("status") or "pending").lower() != "passed":
            failures.append(f"reviews.status is not passed: {reviews.get('status')}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize an ILongRun mission")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--status", choices=["completed", "blocked", "failed"], required=True)
    parser.add_argument("--headline", required=True)
    parser.add_argument("--delivered-artifact", action="append", default=[])
    parser.add_argument("--verification-item", action="append", default=[])
    parser.add_argument("--blocker", action="append", default=[])
    parser.add_argument("--local-verify", action="store_true")
    parser.add_argument("--force-complete", action="store_true")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    desired_state = normalize_run_state(args.status)
    sched = reconcile_scheduler(target)
    if args.delivered_artifact:
        sched["deliverables"] = [item for item in args.delivered_artifact if item]

    verification = (
        verify_scheduler(target, sched, finalize_candidate=desired_state == "completed")
        if args.local_verify
        else {"ok": True, "hardFailures": [], "softWarnings": [], "driftFindings": [], "recommendedAction": "continue", "failureClass": None, "completionScore": None}
    )

    if desired_state == "completed":
        precheck_failures = completed_precheck_failures(target, sched, verification)
        if precheck_failures and not args.force_complete:
            verification = dict(verification)
            verification["ok"] = False
            verification["hardFailures"] = precheck_failures
            sched["summary"] = args.headline
            sched["verification"] = verification_snapshot(verification, state="failed")
            sched, _ = persist_run_ledger(
                target,
                sched,
                reason="finalize-precheck-failed",
                actor="ledger-syncer",
            )
            notify(
                target,
                "attention",
                title="iLongRun 需要你回来看看",
                subtitle="完成前校验没有通过",
                message="任务还在，当前进度已保留。请先处理阻断项。",
                sound=True,
            )
            if args.do_print:
                print(json.dumps(sched, ensure_ascii=False, indent=2))
            return 1

    sched["state"] = desired_state
    sched["summary"] = args.headline
    sched["activeWorkstreams"] = []
    sched["verification"] = verification_snapshot(verification, state=desired_state)
    reviews = sched.setdefault("reviews", {})
    if sched.get("profile") == "coding":
        if desired_state == "completed":
            reviews["status"] = "passed"
            reviews["adjudicationStatus"] = "complete"
            reviews["adjudicationDecision"] = "proceed-to-finalize"
        elif desired_state == "blocked":
            if str(reviews.get("finalVerdict") or "pending").upper() == "FAIL" or int(reviews.get("pendingMustFixCount") or 0) > 0 or str(reviews.get("adjudicationDecision") or "pending").lower() == "return-for-fix":
                reviews["status"] = "failed"
        elif desired_state == "failed" and str(reviews.get("status") or "").lower() == "passed":
            reviews["status"] = "failed"

    if desired_state in {"blocked", "failed"} and not args.blocker:
        args.blocker.append(args.headline)

    terminal_path = terminal_report_path(target, desired_state)
    if terminal_path is None:
        raise SystemExit(f"unsupported terminal state: {desired_state}")
    clear_terminal_reports(target, keep=desired_state)
    write_text_atomic(
        terminal_path,
        build_terminal_markdown(
            sched,
            status_name=desired_state,
            headline=args.headline,
            verification_items=args.verification_item,
            blockers=args.blocker,
        ),
    )
    sched, _ = persist_run_ledger(
        target,
        sched,
        reason=f"finalize-{desired_state}",
        actor="ledger-syncer",
        clean_active_on_complete=desired_state == "completed",
    )
    clear_terminal_reports(target, keep=desired_state)
    write_text_atomic(
        terminal_path,
        build_terminal_markdown(
            sched,
            status_name=desired_state,
            headline=args.headline,
            verification_items=args.verification_item,
            blockers=args.blocker,
        ),
    )

    if desired_state == "completed":
        notify(
            target,
            "complete",
            title="iLongRun 已完成",
            subtitle="结果已收敛为 completed",
            message="点一下查看完成摘要。",
            open_path=completion_path(target) if completion_path(target).exists() else None,
            sound=True,
        )
    elif desired_state == "blocked":
        notify(
            target,
            "blocked",
            title="iLongRun 已阻断结束",
            subtitle="当前 run 进入 blocked",
            message="点一下查看阻断摘要并决定下一步。",
            open_path=blocked_path(target) if blocked_path(target).exists() else None,
            sound=True,
        )
    else:
        notify(
            target,
            "blocked",
            title="iLongRun 运行失败",
            subtitle="当前 run 进入 failed",
            message="点一下查看失败摘要。",
            open_path=failed_path(target) if failed_path(target).exists() else None,
            sound=True,
        )

    if args.do_print:
        print(json.dumps(sched, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
