#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import resolve_run_target, verify_scheduler


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ILongRun run state and projections")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    result = verify_scheduler(target)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("OK" if result.get("ok") else "FAIL")
        for item in result.get("deliverables", []):
            print(f"deliverable: {item}")
        for finding in result.get("hardFailures", []):
            print(f"hard-failure: {finding}")
        for finding in result.get("driftFindings", []):
            print(f"drift-finding: {finding}")
        for finding in result.get("softWarnings", []):
            print(f"soft-warning: {finding}")
        if result.get("recommendedAction"):
            print(f"recommended-action: {result.get('recommendedAction')}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
