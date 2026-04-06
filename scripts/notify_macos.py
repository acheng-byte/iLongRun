#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import completion_path, plan_path, resolve_run_target, strategy_path
from _ilongrun_shared import read_json, resolve_workspace, write_json_atomic

DEFAULT_COPY: dict[str, dict[str, object]] = {
    "launched": {
        "title": "iLongRun 已经开始了",
        "subtitle": "任务正在后台继续进行",
        "message": "你现在可以关掉终端，稍后回来查看进度。",
        "sound": False,
        "dedupe_seconds": 30,
    },
    "resumed": {
        "title": "iLongRun 已重新接上",
        "subtitle": "任务又继续往前跑了",
        "message": "进度已经接回去，你不用重新从头开始。",
        "sound": False,
        "dedupe_seconds": 30,
    },
    "recovery": {
        "title": "iLongRun 正在自己换路继续",
        "subtitle": "刚才那一步没有走通",
        "message": "现在先不用守着，iLongRun 还在继续处理。",
        "sound": False,
        "dedupe_seconds": 900,
    },
    "attention": {
        "title": "iLongRun 需要你回来看看",
        "subtitle": "有一项检查没有通过",
        "message": "任务还在，当前进度也已经保留下来了。",
        "sound": True,
        "dedupe_seconds": 900,
    },
    "complete": {
        "title": "iLongRun 已经完成了",
        "subtitle": "结果已经整理好了",
        "message": "点一下就能打开结果摘要。",
        "sound": True,
        "dedupe_seconds": 30,
    },
    "blocked": {
        "title": "iLongRun 暂时停住了",
        "subtitle": "需要你补一个决定或输入",
        "message": "点一下查看当前情况，再决定下一步。",
        "sound": True,
        "dedupe_seconds": 300,
    },
    "checkpoint": {
        "title": "iLongRun 已经帮你记住这里",
        "subtitle": "稍后可以从这里接着来",
        "message": "当前进度已经保存好，不用担心丢失。",
        "sound": False,
        "dedupe_seconds": 300,
    },
}

OFF_VALUES = {"0", "false", "False", "off", "OFF"}


def terminal_notifier_path() -> str | None:
    candidate = shutil.which("terminal-notifier")
    if candidate:
        return candidate
    for path in (
        "/opt/homebrew/bin/terminal-notifier",
        "/usr/local/bin/terminal-notifier",
        str(Path.home() / ".local" / "bin" / "terminal-notifier"),
    ):
        if Path(path).exists():
            return path
    return None


def file_uri(path: Path) -> str:
    try:
        return path.resolve().as_uri()
    except ValueError:
        return "file://" + quote(str(path.resolve()))


def notification_state_path(workspace: Path, run_id: str | None) -> Path:
    state_dir = workspace / ".copilot-ilongrun" / "state"
    name = f"notify-{run_id}.json" if run_id else "notify-global.json"
    return state_dir / name


def should_send(workspace: Path, run_id: str | None, event: str, message: str, dedupe_seconds: int) -> bool:
    state_path = notification_state_path(workspace, run_id)
    state = read_json(state_path, {})
    key = f"{event}:{hashlib.sha1(message.encode('utf-8')).hexdigest()[:12]}"
    current = datetime.now(timezone.utc).timestamp()
    last = ((state.get("events") or {}).get(key) or {}).get("ts")
    if isinstance(last, (int, float)) and current - last < dedupe_seconds:
        return False
    events = dict(state.get("events") or {})
    events[key] = {"ts": current, "event": event}
    state["events"] = events
    write_json_atomic(state_path, state)
    return True


def resolve_open_target(workspace: Path, run_id: str | None, event: str, explicit_open: str | None) -> Path | None:
    if explicit_open:
        return Path(explicit_open).expanduser().resolve()
    if not run_id:
        return workspace
    target = None
    try:
        target = resolve_run_target(workspace, run_id)
    except Exception:
        fallback_run_dir = workspace / ".copilot-ilongrun" / "runs" / run_id
        if fallback_run_dir.exists():
            candidate = fallback_run_dir / "plan.md"
            if candidate.exists():
                return candidate
            candidate = fallback_run_dir / "strategy.md"
            if candidate.exists():
                return candidate
            return fallback_run_dir
        return workspace

    if event in {"complete", "blocked"}:
        candidate = completion_path(target)
        if candidate.exists():
            return candidate
    for candidate in (plan_path(target), strategy_path(target), target.run_dir):
        if candidate.exists():
            return candidate
    return workspace


def send_terminal_notifier(path: str, title: str, subtitle: str, message: str, group: str, open_target: Path | None, sound: bool, dry_run: bool) -> int:
    cmd = [path, "-title", title, "-subtitle", subtitle, "-message", message, "-group", group]
    if open_target:
        cmd.extend(["-open", file_uri(open_target)])
    if sound:
        cmd.extend(["-sound", "default"])
    if dry_run:
        print(json.dumps({
            "backend": "terminal-notifier",
            "command": cmd,
            "open": str(open_target) if open_target else "",
            "resolvedOpen": str(open_target) if open_target else "",
        }, ensure_ascii=False, indent=2))
        return 0
    completed = subprocess.run(cmd, capture_output=True, text=True)
    return completed.returncode


def send_osascript(title: str, subtitle: str, message: str, open_target: Path | None, dry_run: bool) -> int:
    script = f'display notification {json.dumps(message)} with title {json.dumps(title)} subtitle {json.dumps(subtitle)}'
    cmd = ["osascript", "-e", script]
    if dry_run:
        print(json.dumps({
            "backend": "osascript",
            "command": cmd,
            "open": "",
            "resolvedOpen": str(open_target) if open_target else "",
        }, ensure_ascii=False, indent=2))
        return 0
    completed = subprocess.run(cmd, capture_output=True, text=True)
    return completed.returncode


def notifications_disabled() -> bool:
    for name in ("ILONGRUN_NOTIFICATIONS", "LONGRUN_NOTIFICATIONS"):
        if os.environ.get(name) in OFF_VALUES:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Send lightweight macOS notifications for iLongRun")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--event", choices=sorted(DEFAULT_COPY), required=True)
    parser.add_argument("--title")
    parser.add_argument("--subtitle")
    parser.add_argument("--message")
    parser.add_argument("--open")
    parser.add_argument("--group", default="")
    parser.add_argument("--sound", action="store_true")
    parser.add_argument("--no-sound", action="store_true")
    parser.add_argument("--dedupe-seconds", type=int, default=-1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if notifications_disabled():
        return 0

    workspace = resolve_workspace(args.workspace)
    run_id = args.run_id.strip() or None
    copy = DEFAULT_COPY[args.event]
    title = args.title or str(copy["title"])
    subtitle = args.subtitle or str(copy["subtitle"])
    message = args.message or str(copy["message"])
    sound = bool(copy["sound"])
    if args.sound:
        sound = True
    if args.no_sound:
        sound = False
    dedupe_seconds = args.dedupe_seconds if args.dedupe_seconds >= 0 else int(copy["dedupe_seconds"])
    group = args.group or f"ilongrun.{run_id or args.event}"

    if not should_send(workspace, run_id, args.event, f"{title}|{subtitle}|{message}", dedupe_seconds):
        return 0

    open_target = resolve_open_target(workspace, run_id, args.event, args.open)
    notifier = terminal_notifier_path() if sys.platform == "darwin" else None
    if notifier:
        rc = send_terminal_notifier(notifier, title, subtitle, message, group, open_target, sound, args.dry_run)
        if rc == 0:
            return 0
    if sys.platform == "darwin" and shutil.which("osascript"):
        return send_osascript(title, subtitle, message, open_target, args.dry_run)
    if args.dry_run:
        print(json.dumps({
            "backend": "none",
            "title": title,
            "subtitle": subtitle,
            "message": message,
            "open": str(open_target) if open_target else "",
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
