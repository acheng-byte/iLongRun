#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_shared import append_jsonl, now_iso, read_json, read_text, resolve_workspace, write_json_atomic


def load_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


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
        append_jsonl(run_dir / 'hook-events.jsonl', record)
        if event == 'errorOccurred':
            scheduler_path = run_dir / 'scheduler.json'
            scheduler = read_json(scheduler_path, {})
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
