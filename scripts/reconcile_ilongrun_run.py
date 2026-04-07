#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import persist_run_ledger, reconcile_scheduler, resolve_run_target


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile ILongRun scheduler with workstream state")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    sched = reconcile_scheduler(target)
    sched, _verification = persist_run_ledger(
        target,
        sched,
        reason="reconcile-cli",
        actor="ledger-syncer",
        verify=True,
        clean_active_on_complete=True,
    )
    result = {"ok": True, "runId": target.run_id, "state": sched.get("state"), "phase": sched.get("phase"), "completedWorkstreams": sched.get("completedWorkstreams"), "verification": sched.get("verification")}
    if args.do_print:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
