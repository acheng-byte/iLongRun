#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import reconcile_scheduler, resolve_run_target, scheduler_path, sync_projections, verify_scheduler, write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile ILongRun scheduler with workstream state")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    sched = reconcile_scheduler(target)
    verification = verify_scheduler(target, sched)
    sched["verification"] = {
        "state": "passed" if verification.get("ok") else "failed",
        "hardFailures": verification.get("hardFailures", []),
        "softWarnings": verification.get("softWarnings", []),
        "driftFindings": verification.get("driftFindings", []),
        "recommendedAction": verification.get("recommendedAction"),
        "failureClass": verification.get("failureClass"),
        "lastVerifiedAt": __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
    }
    sync_projections(target, sched)
    write_json_atomic(scheduler_path(target), sched)
    result = {"ok": True, "runId": target.run_id, "state": sched.get("state"), "phase": sched.get("phase"), "completedWorkstreams": sched.get("completedWorkstreams"), "verification": sched.get("verification")}
    if args.do_print:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
