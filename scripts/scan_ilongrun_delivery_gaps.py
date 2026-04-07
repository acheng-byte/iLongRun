#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_delivery_audit import render_delivery_audit_markdown, scan_workspace_delivery_gaps
from _ilongrun_lib import delivery_audit_path, resolve_run_target
from _ilongrun_shared import write_text_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a JS/TS workspace for fake-completion delivery gaps")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    result = scan_workspace_delivery_gaps(workspace)

    report_target: Path | None = None
    if args.run_id:
        target = resolve_run_target(workspace, args.run_id)
        report_target = delivery_audit_path(target)
    elif args.write_report:
        report_target = workspace / "delivery-audit.md"

    if report_target is not None:
        write_text_atomic(report_target, render_delivery_audit_markdown(result))
        result["reportPath"] = str(report_target)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("OK" if result.get("ok") else "FAIL")
        for item in result.get("findings") or []:
            print(f"{item.get('severity', 'unknown')}: {item.get('summary')}")
        if report_target is not None:
            print(f"report: {report_target}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
