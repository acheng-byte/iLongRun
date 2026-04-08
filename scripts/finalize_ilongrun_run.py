#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_report_templates import build_completion_report_markdown
from _ilongrun_lib import (
    adjudication_path,
    claim_verification_is_complete,
    completion_path,
    final_review_path,
    persist_run_ledger,
    reconcile_scheduler,
    resolve_run_target,
    verify_scheduler,
    write_text_atomic,
)


def build_completion_markdown(sched: dict, headline: str, status_name: str, verification_items: list[str], blockers: list[str]) -> str:
    verification = sched.get("verification") or {}
    reviews = sched.get("reviews") or {}
    return build_completion_report_markdown(
        run_id=str(sched.get("runId") or ""),
        status_name=status_name,
        profile=str(sched.get("profile") or "unknown"),
        selected_model=str(sched.get("selectedModel") or "unknown"),
        headline=headline,
        verification_state=str(verification.get("state") or "pending"),
        review_status=str(reviews.get("status") or "not-required"),
        adjudication_status=str(reviews.get("adjudicationStatus") or "not-required"),
        completion_score=verification.get("completionScore") or {},
        deliverables=list(sched.get("deliverables") or []),
        verification_items=verification_items,
        blockers=blockers,
    )


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize an ILongRun mission")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--status", choices=["complete", "blocked"], required=True)
    parser.add_argument("--headline", required=True)
    parser.add_argument("--delivered-artifact", action="append", default=[])
    parser.add_argument("--verification-item", action="append", default=[])
    parser.add_argument("--blocker", action="append", default=[])
    parser.add_argument("--local-verify", action="store_true")
    parser.add_argument("--force-complete", action="store_true")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    sched = reconcile_scheduler(target)
    if args.delivered_artifact:
        sched["deliverables"] = [item for item in args.delivered_artifact if item]
    verification = verify_scheduler(target, sched, finalize_candidate=True) if args.local_verify else {"ok": True, "hardFailures": [], "softWarnings": [], "driftFindings": [], "recommendedAction": "continue", "failureClass": None}
    if args.status == "complete" and sched.get("profile") == "coding":
        claim_verification = sched.get("claimVerification") or {}
        if not claim_verification_is_complete(claim_verification) and not args.force_complete:
            verification["ok"] = False
            verification.setdefault("hardFailures", []).append(
                f"claimVerification incomplete: {', '.join(claim_verification.get('missingWorkstreams') or []) or 'unknown'}"
            )
        if not final_review_path(target).exists() and not args.force_complete:
            verification["ok"] = False
            verification.setdefault("hardFailures", []).append("reviews/final-review.md is missing")
        if not adjudication_path(target).exists() and not args.force_complete:
            verification["ok"] = False
            verification.setdefault("hardFailures", []).append("reviews/adjudication.md is missing")
        for gate_id, gate_state in ((sched.get("reviews") or {}).get("gateStatus") or {}).items():
            if gate_state != "complete" and not args.force_complete:
                verification["ok"] = False
                verification.setdefault("hardFailures", []).append(f"phase-review gate incomplete: {gate_id}")
        pending = int((sched.get("reviews") or {}).get("pendingMustFixCount") or 0)
        if pending > 0 and not args.force_complete:
            verification["ok"] = False
            verification.setdefault("hardFailures", []).append(f"unresolved must-fix items remain: {pending}")
    if args.status == "complete" and args.local_verify and not verification.get("ok") and not args.force_complete:
        sched["verification"] = {
            "state": "failed",
            "hardFailures": verification.get("hardFailures", []),
            "softWarnings": verification.get("softWarnings", []),
            "driftFindings": verification.get("driftFindings", []),
            "recommendedAction": verification.get("recommendedAction"),
            "failureClass": verification.get("failureClass"),
            "lastVerifiedAt": __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
            "completionScore": verification.get("completionScore"),
        }
        sched["summary"] = args.headline
        persist_run_ledger(
            target,
            sched,
            reason="finalize-precheck-failed",
            actor="ledger-syncer",
        )
        notify(
            target,
            "attention",
            title="iLongRun 需要你回来看看",
            subtitle="有一项检查没有通过",
            message="任务还在，当前进度也已经保留下来了。",
            sound=True,
        )
        if args.do_print:
            print(json.dumps(sched, ensure_ascii=False, indent=2))
        return 1

    sched["state"] = args.status
    sched["summary"] = args.headline
    sched["activeWorkstreams"] = []
    sched["verification"] = {
        "state": "passed" if verification.get("ok") else "failed",
        "hardFailures": verification.get("hardFailures", []),
        "softWarnings": verification.get("softWarnings", []),
        "driftFindings": verification.get("driftFindings", []),
        "recommendedAction": verification.get("recommendedAction"),
        "failureClass": verification.get("failureClass"),
        "lastVerifiedAt": __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        "completionScore": verification.get("completionScore"),
    }
    if sched.get("profile") == "coding":
        sched.setdefault("reviews", {})["status"] = "passed" if int((sched.get("reviews") or {}).get("pendingMustFixCount") or 0) == 0 else "failed"
    completion_file = completion_path(target)
    completion_body = build_completion_markdown(sched, args.headline, args.status, args.verification_item, args.blocker)
    if args.status == "complete":
        write_text_atomic(completion_file, completion_body)
    sched, _ = persist_run_ledger(
        target,
        sched,
        reason=f"finalize-{args.status}",
        actor="ledger-syncer",
        clean_active_on_complete=args.status == "complete",
    )
    write_text_atomic(completion_file, build_completion_markdown(sched, args.headline, args.status, args.verification_item, args.blocker))
    if args.status == "complete":
        notify(
            target,
            "complete",
            title="iLongRun 已经完成了",
            subtitle="结果已经整理好了",
            message="点一下就能打开结果摘要。",
            open_path=completion_file if completion_file.exists() else None,
            sound=True,
        )
    else:
        notify(
            target,
            "blocked",
            title="iLongRun 暂时停住了",
            subtitle="需要你补一个决定或输入",
            message="点一下查看当前情况，再决定下一步。",
            open_path=completion_file if completion_file.exists() else None,
            sound=True,
        )
    if args.do_print:
        print(json.dumps(sched, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
