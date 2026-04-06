#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_shared import ensure_dir, now_iso, resolve_workspace, write_json_atomic  # noqa: E402


TRIVIAL_RELATIVE_PATHS = {
    ".DS_Store",
    "global/hook-events.jsonl",
    "state/active-run-id",
    "state/latest-run-id",
}


def classify_legacy_dir(path: Path) -> tuple[list[str], list[str]]:
    files: list[str] = []
    significant: list[str] = []
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(path).as_posix()
        files.append(rel)
        if rel not in TRIVIAL_RELATIVE_PATHS:
            significant.append(rel)
    return files, significant


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive and remove legacy .copilot-mission-control workspace state")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--print-json", action="store_true", dest="do_print")
    args = parser.parse_args()

    workspace = resolve_workspace(args.workspace)
    legacy_root = workspace / ".copilot-mission-control"
    if not legacy_root.exists():
        payload = {"ok": True, "workspace": str(workspace), "action": "noop", "removed": False}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.do_print else json.dumps(payload, ensure_ascii=False))
        return 0

    files, significant = classify_legacy_dir(legacy_root)
    ilongrun_root = workspace / ".copilot-ilongrun"
    archive_root = ilongrun_root / "legacy-imports"
    ensure_dir(archive_root)
    timestamp = now_iso().replace(":", "").replace("-", "")
    archive_path = archive_root / f"copilot-mission-control-{timestamp}"
    report_path = archive_root / f"copilot-mission-control-{timestamp}.json"

    action = "deleted-empty"
    archived = False
    if files:
        shutil.move(str(legacy_root), str(archive_path))
        archived = True
        action = "archived-and-removed" if significant else "archived-trivial-and-removed"
    else:
        shutil.rmtree(legacy_root, ignore_errors=True)

    report = {
        "ts": now_iso(),
        "workspace": str(workspace),
        "legacyRoot": str(legacy_root),
        "archivePath": str(archive_path) if archived else None,
        "fileCount": len(files),
        "files": files,
        "significantFiles": significant,
        "action": action,
        "removed": True,
    }
    write_json_atomic(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.do_print else json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
