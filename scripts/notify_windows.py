#!/usr/bin/env python3
"""
iLongRun Windows notification helper.
Uses PowerShell's BurntToast (if installed) or falls back to msg.exe / balloon tips.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_shared import read_json, resolve_workspace

OFF_VALUES = {"0", "false", "False", "off", "OFF"}

EVENT_TEMPLATES: dict[str, dict[str, str]] = {
    "start": {
        "title": "iLongRun 已经开始了",
        "message": "任务已启动，可以先去忙别的了。",
    },
    "resume": {
        "title": "iLongRun 已重新接上",
        "message": "任务已恢复运行。",
    },
    "recovery": {
        "title": "iLongRun 正在自己换路继续",
        "message": "现在先不用守着，iLongRun 还在继续处理。",
    },
    "attention": {
        "title": "iLongRun 需要你回来看看",
        "message": "任务遇到了需要人工确认的情况。",
    },
    "complete": {
        "title": "iLongRun 已经完成了",
        "message": "所有任务已完成，请查看输出结果。",
    },
    "blocked": {
        "title": "iLongRun 暂时停住了",
        "message": "任务已暂停，等待你的指令。",
    },
    "checkpoint": {
        "title": "iLongRun 已经帮你记住这里",
        "message": "检查点已保存，随时可以恢复。",
    },
}


def notifications_disabled() -> bool:
    for name in ("ILONGRUN_NOTIFICATIONS", "LONGRUN_NOTIFICATIONS"):
        if os.environ.get(name) in OFF_VALUES:
            return True
    return False


def send_powershell_toast(title: str, message: str, dry_run: bool) -> int:
    """Try BurntToast PowerShell module first, fall back to balloon tip."""
    ps_script = (
        "try { "
        "  Import-Module BurntToast -ErrorAction Stop; "
        f" New-BurntToastNotification -Text '{title}', '{message}' "
        "} catch { "
        "  Add-Type -AssemblyName System.Windows.Forms; "
        "  $n = New-Object System.Windows.Forms.NotifyIcon; "
        "  $n.Icon = [System.Drawing.SystemIcons]::Information; "
        "  $n.Visible = $true; "
        f" $n.ShowBalloonTip(5000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::Info); "
        "  Start-Sleep -Milliseconds 5500; "
        "  $n.Visible = $false "
        "}"
    )
    cmd = ["powershell", "-NonInteractive", "-NoProfile", "-Command", ps_script]
    if dry_run:
        print(json.dumps({"backend": "powershell", "command": cmd}, ensure_ascii=False, indent=2))
        return 0
    try:
        subprocess.run(cmd, timeout=15, check=False)
        return 0
    except Exception as exc:
        print(f"notify_windows: powershell failed: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Windows notifications for iLongRun")
    parser.add_argument("--event", default="complete")
    parser.add_argument("--run-id")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--title")
    parser.add_argument("--message")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if notifications_disabled():
        return 0

    tmpl = EVENT_TEMPLATES.get(args.event, EVENT_TEMPLATES["complete"])
    title = args.title or tmpl["title"]
    message = args.message or tmpl["message"]

    return send_powershell_toast(title, message, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
