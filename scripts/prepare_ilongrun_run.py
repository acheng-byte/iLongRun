#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import (
    append_jsonl,
    ensure_run_layout,
    init_scheduler_payload,
    journal_path,
    load_model_config,
    mint_run_id,
    model_availability_snapshot,
    read_model_availability_for_ilongrun,
    resolve_run_target,
    scheduler_path,
    set_active_run,
    set_latest_run,
    sync_projections,
    write_json_atomic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a fresh ILongRun run directory and scheduler")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--explicit-model")
    parser.add_argument("--session-model")
    parser.add_argument("--model-control-mode")
    parser.add_argument("--model-config")
    parser.add_argument("--availability-cache")
    parser.add_argument("--launcher-mode", default="launcher-preallocated")
    parser.add_argument("--print-json", action="store_true", dest="do_print")
    args = parser.parse_args()

    run_id = args.run_id or mint_run_id(args.workspace, args.task)
    target = resolve_run_target(args.workspace, run_id)
    existing = scheduler_path(target).exists()
    if existing and not args.allow_existing:
        raise SystemExit(f"prepare_ilongrun_run: run already exists: {target.run_id}")

    ensure_run_layout(target)
    set_active_run(target.base, target.run_id)
    set_latest_run(target.base, target.run_id)

    if existing and args.allow_existing:
        scheduler = json.loads(scheduler_path(target).read_text(encoding="utf-8"))
    else:
        config = load_model_config(args.model_config)
        availability = model_availability_snapshot(config, cache=read_model_availability_for_ilongrun(args.availability_cache), path=args.availability_cache)
        scheduler = init_scheduler_payload(
            target.run_id,
            args.task,
            explicit_model=args.explicit_model,
            session_model=args.session_model,
            model_control_mode=args.model_control_mode,
            config=config,
            availability=availability,
        )
        scheduler["launcherMode"] = args.launcher_mode
    scheduler["runId"] = target.run_id
    scheduler["updatedAt"] = scheduler.get("updatedAt")
    sync_projections(target, scheduler)
    write_json_atomic(scheduler_path(target), scheduler)
    append_jsonl(journal_path(target), {"ts": scheduler.get("createdAt"), "source": "helper", "event": "run-prepared", "payload": {"runId": target.run_id, "launcherMode": args.launcher_mode}})

    result = {"workspace": str(target.workspace), "runId": target.run_id, "runDir": str(target.run_dir), "schedulerPath": str(scheduler_path(target))}
    if args.do_print:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(target.run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
