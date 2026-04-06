#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import (
    completion_path,
    final_review_path,
    reconcile_scheduler,
    resolve_run_target,
    scheduler_path,
    sync_projections,
    verify_scheduler,
    write_json_atomic,
    write_text_atomic,
)


def build_completion_markdown(sched: dict, headline: str, status_name: str, verification_items: list[str], blockers: list[str]) -> str:
    lines = [
        "# ILongRun Completion Summary",
        "",
        f"- Status: `{status_name}`",
        f"- Headline: {headline}",
        "",
        "## Deliverables",
    ]
    deliverables = sched.get("deliverables") or []
    if deliverables:
        lines.extend(f"- `{item}`" for item in deliverables)
    else:
        lines.append("- None recorded")
    lines.extend(["", "## Verification"])
    if verification_items:
        lines.extend(f"- {item}" for item in verification_items)
    else:
        lines.append("- No explicit verification notes")
    if blockers:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in blockers)
    return "\n".join(lines) + "\n"


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
        if not final_review_path(target).exists() and not args.force_complete:
            verification["ok"] = False
            verification.setdefault("hardFailures", []).append("reviews/gpt54-final-review.md is missing")
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
        }
        sched["summary"] = args.headline
        sched["updatedAt"] = __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        sync_projections(target, sched)
        write_json_atomic(scheduler_path(target), sched)
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
    }
    if sched.get("profile") == "coding":
        sched.setdefault("reviews", {})["status"] = "passed" if int((sched.get("reviews") or {}).get("pendingMustFixCount") or 0) == 0 else "failed"
    sched["updatedAt"] = __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    sync_projections(target, sched)
    write_json_atomic(scheduler_path(target), sched)
    write_text_atomic(completion_path(target), build_completion_markdown(sched, args.headline, args.status, args.verification_item, args.blocker))
    if args.do_print:
        print(json.dumps(sched, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
