#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import (
    ensure_scheduler_defaults,
    init_scheduler_payload,
    load_model_config,
    model_availability_snapshot,
    parse_json_argument,
    read_model_availability_for_ilongrun,
    reconcile_scheduler,
    resolve_run_target,
    scheduler_path,
    shallow_merge,
    sync_projections,
    workstream_by_id,
    write_json_atomic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomic ILongRun scheduler writer")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--replace-json")
    parser.add_argument("--patch-json")
    parser.add_argument("--patch-workstream")
    parser.add_argument("--patch-workstream-json")
    parser.add_argument("--init-from-prompt")
    parser.add_argument("--explicit-model")
    parser.add_argument("--force-profile", choices=["coding", "research", "office"])
    parser.add_argument("--session-model")
    parser.add_argument("--model-control-mode")
    parser.add_argument("--model-config")
    parser.add_argument("--availability-cache")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    if args.replace_json:
        payload = parse_json_argument(args.replace_json, {})
    elif args.init_from_prompt:
        config = load_model_config(args.model_config)
        availability = model_availability_snapshot(config, cache=read_model_availability_for_ilongrun(args.availability_cache), path=args.availability_cache)
        payload = init_scheduler_payload(
            target.run_id,
            args.init_from_prompt,
            explicit_model=args.explicit_model,
            forced_profile=args.force_profile,
            session_model=args.session_model or os.environ.get("LONGRUN_SELECTED_MODEL"),
            model_control_mode=args.model_control_mode or os.environ.get("LONGRUN_MODEL_CONTROL_MODE"),
            config=config,
            availability=availability,
        )
    else:
        current = ensure_scheduler_defaults(json.loads(scheduler_path(target).read_text(encoding="utf-8")))
        patch = parse_json_argument(args.patch_json, {})
        payload = shallow_merge(current, patch)
        if args.patch_workstream and args.patch_workstream_json:
            workstream = workstream_by_id(payload, args.patch_workstream)
            if workstream is None:
                raise SystemExit(f"unknown workstream: {args.patch_workstream}")
            workstream_patch = parse_json_argument(args.patch_workstream_json, {})
            merged = shallow_merge(workstream, workstream_patch)
            for idx, item in enumerate(payload.get("workstreams") or []):
                if item.get("id") == args.patch_workstream:
                    payload["workstreams"][idx] = merged
                    break
    payload = reconcile_scheduler(target, ensure_scheduler_defaults(payload))
    payload["runId"] = target.run_id
    sync_projections(target, payload)
    write_json_atomic(scheduler_path(target), payload)
    if args.do_print:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
