#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import completion_path, is_run_complete_state, persist_run_ledger, reconcile_scheduler, resolve_run_target, verify_scheduler
from _ilongrun_shared import append_jsonl, now_iso, read_json, read_text, resolve_workspace, write_json_atomic


def load_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def persist_hook_precheck(cwd: Path, run_id: str, event: str) -> None:
    try:
        target = resolve_run_target(cwd, run_id)
    except Exception:
        return
    sched = reconcile_scheduler(target)
    finalize_candidate = str(sched.get("phase") or "").strip() == "phase-finalize" or is_run_complete_state(sched.get("state"))
    verification = verify_scheduler(target, sched, finalize_candidate=finalize_candidate)
    sched["verification"] = {
        "state": "passed" if verification.get("ok") else "failed",
        "hardFailures": verification.get("hardFailures", []),
        "softWarnings": verification.get("softWarnings", []),
        "driftFindings": verification.get("driftFindings", []),
        "recommendedAction": verification.get("recommendedAction"),
        "failureClass": verification.get("failureClass"),
        "lastVerifiedAt": now_iso(),
        "completionScore": verification.get("completionScore"),
    }
    recovery = dict(sched.get("recoveryState") or {})
    recovery["lastRecommendedAction"] = verification.get("recommendedAction")
    recovery["failureClass"] = verification.get("failureClass")
    sched["recoveryState"] = recovery
    runtime = dict(sched.get("runtime") or {})
    runtime["lastHookPrecheck"] = {
        "event": event,
        "ts": now_iso(),
        "verificationState": sched["verification"]["state"],
        "failureClass": verification.get("failureClass"),
    }
    sched["runtime"] = runtime
    persist_run_ledger(
        target,
        sched,
        reason=f"hook-{event}-precheck",
        actor="hook",
        clean_active_on_complete=is_run_complete_state(sched.get("state")) and completion_path(target).exists() and verification.get("ok"),
    )


def main() -> int:
    event = os.environ.get('HOOK_EVENT', 'unknown')
    data = load_payload()
    cwd = resolve_workspace(data.get('cwd') or os.getcwd())
    base = cwd / '.copilot-ilongrun'
    global_path = base / 'global' / 'hook-events.jsonl'
    record = {'ts': data.get('timestamp') or now_iso(), 'source': 'hook', 'event': event, 'payload': data}
    append_jsonl(global_path, record)

    active_path = base / 'state' / 'active-run-id'
    run_id = read_text(active_path, '').strip() if active_path.exists() else ''
    if run_id:
        run_dir = base / 'runs' / run_id
        scheduler_path = run_dir / 'scheduler.json'
        scheduler = read_json(scheduler_path, {})
        target = None
        try:
            target = resolve_run_target(cwd, run_id)
        except Exception:
            target = None
        if str(scheduler.get('state') or '').lower() in {'complete', 'completed', 'finalized'} and target and completion_path(target).exists():
            active_path.unlink(missing_ok=True)
            run_id = ''
        else:
            append_jsonl(run_dir / 'hook-events.jsonl', record)
            if event == 'errorOccurred':
                scheduler['lastError'] = {
                    'ts': record['ts'],
                    'event': event,
                    'message': data.get('message') or data.get('error') or json.dumps(data, ensure_ascii=False),
                }
                recovery = dict(scheduler.get('recoveryState') or {})
                recovery['lastErrorTs'] = record['ts']
                scheduler['recoveryState'] = recovery
                scheduler['updatedAt'] = now_iso()
                write_json_atomic(scheduler_path, scheduler)
            elif event in {'sessionEnd', 'taskComplete', 'task_complete'}:
                persist_hook_precheck(cwd, run_id, event)

    if event != 'preToolUse' or not run_id:
        return 0

    args = data.get('toolArgs')
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {'raw': args}
    cmd = ''
    if isinstance(args, dict):
        cmd = args.get('command') or args.get('script') or args.get('bash') or ''
    lowered = cmd.lower()
    tool = (data.get('toolName') or '').lower()
    deny = None
    dangerous_patterns = [r'(^|\s)sudo\b', r'rm\s+-rf\s+/', r'\bmkfs\b', r'\bdd\s+if=', r'diskutil\s+erase', r'\bshutdown\b', r'\breboot\b', r':\(\)\s*\{\s*:\|:&\s*\};:']
    allow_git = os.environ.get('ILONGRUN_ALLOW_GIT_SIDE_EFFECTS') == '1'
    if tool in {'bash', 'powershell'} and any(re.search(pattern, lowered) for pattern in dangerous_patterns):
        deny = 'Blocked by ilongrun: dangerous system command.'
    elif tool in {'bash', 'powershell'} and not allow_git:
        if re.search(r'\bgit\s+commit\b', lowered):
            deny = 'Blocked by ilongrun: git commit is disabled by default.'
        elif re.search(r'\bgit\s+push\b', lowered) or re.search(r'\bgit\s+tag\b', lowered):
            deny = 'Blocked by ilongrun: git push/tag is disabled by default.'
        elif re.search(r'\bgh\s+pr\s+(create|merge)\b', lowered) or re.search(r'\bhub\s+pull-request\b', lowered):
            deny = 'Blocked by ilongrun: PR creation/merge is disabled by default.'
    if deny:
        print(json.dumps({'permissionDecision': 'deny', 'permissionDecisionReason': deny}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
