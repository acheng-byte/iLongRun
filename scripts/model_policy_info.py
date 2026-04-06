#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_shared import (  # noqa: E402
    account_fingerprint,
    configured_default_model,
    current_copilot_identity,
    display_model_name,
    load_model_config,
    model_availability_snapshot,
    model_chain,
    read_model_availability,
    summarize_model_strategy,
    validate_model_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect ILongRun model policy")
    parser.add_argument("--config")
    parser.add_argument("--availability-cache")
    parser.add_argument("--payload")
    parser.add_argument("--explicit-model")
    parser.add_argument("--subcommand")
    parser.add_argument("--skill")
    parser.add_argument("--role")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = load_model_config(args.config)
    availability_cache = read_model_availability(args.availability_cache)
    identity = current_copilot_identity()
    fingerprint = account_fingerprint(identity)
    availability = model_availability_snapshot(config, cache=availability_cache, identity=identity)
    errors = validate_model_config(config)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2) if args.json else "\n".join(errors))
        return 2
    if args.json:
        chain = model_chain(
            config,
            explicit_model=args.explicit_model,
            prompt_text=args.payload,
            command=args.subcommand,
            skill=args.skill,
            role=args.role,
            availability=availability,
        )
        selected = chain[0] if chain else configured_default_model(config, command=args.subcommand, skill=args.skill, role=args.role) or config.get("codingAuditModel")
        print(json.dumps({
            "ok": True,
            "summary": summarize_model_strategy(config, availability),
            "selected": selected,
            "selectedDisplay": display_model_name(selected, config) if selected else None,
            "chain": chain,
            "commandDefault": configured_default_model(config, command=args.subcommand),
            "skillDefault": configured_default_model(config, skill=args.skill),
            "roleDefault": configured_default_model(config, role=args.role),
            "codingAuditModel": config.get("codingAuditModel"),
            "identity": identity,
            "accountFingerprint": fingerprint,
            "availability": availability,
        }, ensure_ascii=False, indent=2))
        return 0
    print(summarize_model_strategy(config, availability))
    if args.payload or args.explicit_model or args.subcommand or args.skill or args.role:
        chain = model_chain(
            config,
            explicit_model=args.explicit_model,
            prompt_text=args.payload,
            command=args.subcommand,
            skill=args.skill,
            role=args.role,
            availability=availability,
        )
        print(f"选中模型: {display_model_name(chain[0], config)} ({chain[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
