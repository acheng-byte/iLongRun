#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_shared import (
    account_fingerprint,
    current_copilot_identity,
    default_model_config,
    display_model_name,
    extract_rate_limit,
    load_model_config,
    model_availability_snapshot,
    model_chain,
    now_iso,
    read_json,
    read_model_availability,
    validate_model_config,
    write_json_atomic,
)

DEFAULT_CACHE = Path.home() / '.copilot-ilongrun' / 'config' / 'capabilities.json'
UNSUPPORTED_SNIPPETS = [
    'unknown command',
    'invalid command',
    'unrecognized command',
    'unknown slash command',
    'not a valid command',
]


def choose_probe_model(config: dict, availability_cache_path: str | None) -> str:
    availability = model_availability_snapshot(config, cache=read_model_availability(availability_cache_path), path=availability_cache_path)
    chain = model_chain(config, availability=availability)
    return chain[0] if chain else config.get('preferred', ['claude-opus-4.6'])[0]


def run_cmd(cmd: list[str], timeout: int) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    output = '\n'.join(part for part in [proc.stdout, proc.stderr] if part).strip()
    return proc.returncode, output


def load_cache(path: Path) -> dict:
    return read_json(path, {'version': 1, 'accounts': {}})


def save_cache(path: Path, payload: dict) -> None:
    write_json_atomic(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description='Probe Copilot CLI /fleet capability and cache the result')
    parser.add_argument('--copilot-bin', default='copilot')
    parser.add_argument('--cache', default=str(DEFAULT_CACHE))
    parser.add_argument('--model-config')
    parser.add_argument('--availability-cache')
    parser.add_argument('--model')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--timeout-seconds', type=int, default=90)
    args = parser.parse_args()

    config = load_model_config(args.model_config)
    errors = validate_model_config(config)
    if errors:
        if args.json:
            print(json.dumps({'ok': False, 'errors': errors}, ensure_ascii=False, indent=2))
        else:
            print('\n'.join(errors), file=sys.stderr)
        return 2

    identity = current_copilot_identity()
    fingerprint = account_fingerprint(identity)
    cache_path = Path(args.cache).expanduser()
    cache = load_cache(cache_path)
    accounts = cache.setdefault('accounts', {})
    account = accounts.setdefault(fingerprint, {'identity': identity, 'fleet': {}})
    account['identity'] = identity
    fleet = account.setdefault('fleet', {})

    if fleet.get('status') in {'supported', 'unsupported'} and fleet.get('checkedAt') and not args.refresh:
        payload = {
            'ok': True,
            'identity': identity,
            'accountFingerprint': fingerprint,
            'status': fleet.get('status'),
            'reason': fleet.get('reason'),
            'checkedAt': fleet.get('checkedAt'),
            'probeModel': fleet.get('probeModel'),
            'probeModelDisplay': display_model_name(fleet.get('probeModel'), config) if fleet.get('probeModel') else None,
            'cache': str(cache_path),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"/fleet: {payload['status']} ({payload['reason']})")
        return 0

    probe_model = args.model or choose_probe_model(config, args.availability_cache)
    cmd = [
        args.copilot_bin,
        '--model', probe_model,
        '--no-custom-instructions',
        '--no-ask-user',
        '--yolo',
        '--stream', 'off',
        '--silent',
        '-p', '/fleet Reply with exactly FLEET_OK.',
    ]
    try:
        rc, output = run_cmd(cmd, args.timeout_seconds)
    except subprocess.TimeoutExpired:
        rc, output = 124, 'fleet-probe-timeout'

    lowered = output.lower()
    if rc == 0:
        status, reason = 'supported', 'probe-success'
    elif any(snippet in lowered for snippet in UNSUPPORTED_SNIPPETS):
        status, reason = 'unsupported', 'command-not-recognized'
    elif extract_rate_limit(output):
        status, reason = 'supported', 'rate-limited-during-probe'
    else:
        status, reason = 'unknown', f'probe-exit-{rc}'

    fleet.update({
        'status': status,
        'reason': reason,
        'checkedAt': now_iso(),
        'probeModel': probe_model,
    })
    cache['version'] = 1
    save_cache(cache_path, cache)

    payload = {
        'ok': True,
        'identity': identity,
        'accountFingerprint': fingerprint,
        'status': status,
        'reason': reason,
        'checkedAt': fleet.get('checkedAt'),
        'probeModel': probe_model,
        'probeModelDisplay': display_model_name(probe_model, config),
        'cache': str(cache_path),
        'rawOutput': output if args.json else None,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"/fleet: {status} ({reason}) via {display_model_name(probe_model, config)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
