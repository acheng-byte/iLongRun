#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_shared import (  # noqa: E402
    default_model_config,
    fixed_review_role_models,
    load_model_config,
    normalize_model_name,
    primary_model_role_names,
    read_json,
    read_jsonc,
    validate_model_config,
    write_text_atomic,
)


ILONGRUN_HOME = Path(os.environ.get("ILONGRUN_HOME", str(Path.home() / ".copilot-ilongrun")))
INSTALL_MODEL_CONFIG = ILONGRUN_HOME / "config" / "model-policy.jsonc"
INSTALL_MODEL_CONFIG_LEGACY = INSTALL_MODEL_CONFIG.with_suffix(".json")
PRIMARY_COMMAND_KEYS = ("run", "coding")
PRIMARY_SKILL_KEYS = ("ilongrun", "ilongrun-coding")
FIXED_REVIEW_ROLES = fixed_review_role_models()
PRIMARY_ROLE_NAMES = primary_model_role_names()


def load_raw_policy(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return read_json(path, default_model_config())
    return read_jsonc(path, default_model_config())


def find_ilongrun_repo_root(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        plugin_json = candidate / "plugin.json"
        model_policy = candidate / "config" / "model-policy.jsonc"
        if not plugin_json.exists() or not model_policy.exists():
            continue
        plugin = read_json(plugin_json, {})
        if plugin.get("name") == "ilongrun":
            return candidate
    return None


def install_target_path() -> Path:
    if INSTALL_MODEL_CONFIG.exists():
        return INSTALL_MODEL_CONFIG
    if INSTALL_MODEL_CONFIG_LEGACY.exists():
        return INSTALL_MODEL_CONFIG_LEGACY
    return INSTALL_MODEL_CONFIG


def target_paths(workspace: Path) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = [("install", install_target_path())]
    repo_root = find_ilongrun_repo_root(workspace)
    if repo_root:
        repo_path = repo_root / "config" / "model-policy.jsonc"
        if repo_path.resolve() != targets[0][1].resolve():
            targets.append(("repo", repo_path))
    return targets


def primary_template_defaults() -> dict[str, Any]:
    defaults = default_model_config()
    role_models = defaults.get("roleModels") or {}
    return {
        "commandDefaults": {key: (defaults.get("commandDefaults") or {}).get(key) for key in PRIMARY_COMMAND_KEYS},
        "skillDefaults": {key: (defaults.get("skillDefaults") or {}).get(key) for key in PRIMARY_SKILL_KEYS},
        "roleModels": {key: role_models.get(key) for key in PRIMARY_ROLE_NAMES},
        "reviewRoles": FIXED_REVIEW_ROLES,
    }


def apply_primary_model(policy: dict[str, Any], slug: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(policy))
    command_defaults = dict(updated.get("commandDefaults") or {})
    for key in PRIMARY_COMMAND_KEYS:
        command_defaults[key] = slug
    updated["commandDefaults"] = command_defaults

    skill_defaults = dict(updated.get("skillDefaults") or {})
    for key in PRIMARY_SKILL_KEYS:
        skill_defaults[key] = slug
    updated["skillDefaults"] = skill_defaults

    role_models = dict(updated.get("roleModels") or {})
    for key in PRIMARY_ROLE_NAMES:
        role_models[key] = slug
    for key, value in FIXED_REVIEW_ROLES.items():
        role_models[key] = value
    updated["roleModels"] = role_models
    return updated


def apply_reset(policy: dict[str, Any]) -> dict[str, Any]:
    defaults = primary_template_defaults()
    updated = json.loads(json.dumps(policy))
    command_defaults = dict(updated.get("commandDefaults") or {})
    for key, value in defaults["commandDefaults"].items():
        command_defaults[key] = value
    updated["commandDefaults"] = command_defaults

    skill_defaults = dict(updated.get("skillDefaults") or {})
    for key, value in defaults["skillDefaults"].items():
        skill_defaults[key] = value
    updated["skillDefaults"] = skill_defaults

    role_models = dict(updated.get("roleModels") or {})
    for key, value in defaults["roleModels"].items():
        role_models[key] = value
    for key, value in defaults["reviewRoles"].items():
        role_models[key] = value
    updated["roleModels"] = role_models
    return updated


def summarize_policy(policy: dict[str, Any]) -> dict[str, Any]:
    role_models = policy.get("roleModels") or {}
    return {
        "runModel": (policy.get("commandDefaults") or {}).get("run"),
        "codingModel": (policy.get("commandDefaults") or {}).get("coding"),
        "reviewModels": {role: role_models.get(role) for role in FIXED_REVIEW_ROLES},
        "auditModel": policy.get("codingAuditModel"),
        "finalAuditReviewer": role_models.get("final-audit-reviewer"),
    }


def write_policy(path: Path, policy: dict[str, Any]) -> None:
    if path.suffix == ".json":
        path = path.with_suffix(".jsonc")
    write_text_atomic(path, json.dumps(policy, ensure_ascii=False, indent=2))


def build_target_result(scope: str, path: Path, policy: dict[str, Any], *, action: str, changed: bool) -> dict[str, Any]:
    summary = summarize_policy(policy)
    return {
        "scope": scope,
        "path": str(path.with_suffix(".jsonc") if path.suffix == ".json" else path),
        "action": action,
        "changed": changed,
        **summary,
    }


def text_report(payload: dict[str, Any]) -> str:
    current = dict(payload.get("current") or {})
    run_model = current.get("runModel") or payload["defaults"]["commandDefaults"]["run"]
    coding_model = current.get("codingModel") or payload["defaults"]["commandDefaults"]["coding"]
    review_models = current.get("reviewModels") or FIXED_REVIEW_ROLES
    review_display = "/".join(str(review_models.get(role) or "unknown") for role in FIXED_REVIEW_ROLES)
    final_audit = current.get("finalAuditReviewer") or current.get("auditModel") or "gpt-5.4"
    lines = [
        "iLongRun 主模型模板",
        f"- 操作: `{payload['mode']}`",
    ]
    if payload.get("requestedModel"):
        lines.append(f"- 请求模型: `{payload['requestedModel']}`")
    lines.append(f"- 主执行模板: run=`{run_model}` / coding=`{coding_model}`")
    lines.append(f"- 审查模板: code/test/security=`{review_display}` / final-audit=`{final_audit}`")
    lines.append("")
    lines.append("写入目标：")
    for target in payload.get("targets", []):
        lines.append(
            f"- [{target['scope']}] {target['action']} {'(changed)' if target.get('changed') else '(unchanged)'} {target['path']}"
        )
    if payload.get("skippedRepoPath"):
        lines.append(f"- [repo] skipped (当前目录不是 iLongRun 仓库) {payload['skippedRepoPath']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Show, set, or reset iLongRun primary model templates")
    parser.add_argument("model", nargs="?", help="Model slug/alias to set, or 'reset'")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    repo_root = find_ilongrun_repo_root(workspace)
    targets = target_paths(workspace)
    mode = "show"
    requested = (args.model or "").strip()
    effective_model: str | None = None
    defaults = primary_template_defaults()

    if requested:
        if requested.lower() == "reset":
            mode = "reset"
        else:
            effective_model = normalize_model_name(requested, load_model_config())
            if not effective_model:
                message = {"ok": False, "error": f"unknown model: {requested}"}
                if args.json:
                    print(json.dumps(message, ensure_ascii=False, indent=2))
                else:
                    print(f"Error: unknown model: {requested}", file=sys.stderr)
                return 2
            mode = "set"

    results: list[dict[str, Any]] = []
    for scope, path in targets:
        raw = load_raw_policy(path)
        if mode == "set" and effective_model:
            updated = apply_primary_model(raw, effective_model)
        elif mode == "reset":
            updated = apply_reset(raw)
        else:
            updated = raw
        errors = validate_model_config(updated)
        if errors:
            message = {"ok": False, "error": f"invalid model policy for {path}", "details": errors}
            if args.json:
                print(json.dumps(message, ensure_ascii=False, indent=2))
            else:
                print(f"Error: invalid model policy for {path}", file=sys.stderr)
                for item in errors:
                    print(f"  - {item}", file=sys.stderr)
            return 2
        changed = updated != raw
        if mode in {"set", "reset"} and changed:
            write_policy(path, updated)
        results.append(build_target_result(scope, path, updated, action=mode, changed=changed))

    repo_hint_path = str((workspace / "config" / "model-policy.jsonc").resolve())
    payload = {
        "ok": True,
        "mode": mode,
        "requestedModel": requested or None,
        "effectiveModel": effective_model,
        "defaults": defaults,
        "targets": results,
        "current": results[0] if results else {},
        "repoDetected": bool(repo_root),
        "skippedRepoPath": None if repo_root else repo_hint_path,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
