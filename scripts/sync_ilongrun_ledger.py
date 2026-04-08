#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import (
    is_run_complete_state,
    persist_run_ledger,
    reconcile_scheduler,
    resolve_run_target,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministically sync ILongRun ledger truth into projections")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--clean-active-on-complete", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    sched = reconcile_scheduler(target)
    active_before = target.base.joinpath("state", "active-run-id").read_text(encoding="utf-8").strip() if target.base.joinpath("state", "active-run-id").exists() else ""
    sched, verification = persist_run_ledger(
        target,
        sched,
        reason="sync-cli",
        actor="ledger-syncer",
        verify=True,
        finalize_candidate=is_run_complete_state(sched.get("state")),
        clean_active_on_complete=args.clean_active_on_complete,
    )
    active_after = target.base.joinpath("state", "active-run-id").read_text(encoding="utf-8").strip() if target.base.joinpath("state", "active-run-id").exists() else ""
    active_cleared = bool(active_before == target.run_id and active_after != target.run_id)

    result = {
        "ok": verification.get("ok", False) if verification else False,
        "runId": target.run_id,
        "state": sched.get("state"),
        "phase": sched.get("phase"),
        "taskLists": [item.get("path") for item in sched.get("taskLists") or []],
        "activeCleared": active_cleared,
        "verification": sched.get("verification"),
    }
    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if verification.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
