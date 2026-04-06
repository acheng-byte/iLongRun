#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ILONGRUN_HOME = Path(os.environ.get("ILONGRUN_HOME", str(Path.home() / ".copilot-ilongrun")))
DEFAULT_MODEL_CONFIG = ILONGRUN_HOME / "config" / "model-policy.json"
DEFAULT_MODEL_AVAILABILITY = ILONGRUN_HOME / "config" / "model-availability.json"
COPILOT_CONFIG_DIR = Path(os.environ.get("COPILOT_CONFIG_DIR", str(Path.home() / ".copilot")))
KNOWN_MODEL_DISPLAY = {
    "claude-opus-4.6": "Claude Opus 4.6",
    "claude-opus-4.5": "Claude Opus 4.5",
    "claude-sonnet-4.6": "Claude Sonnet 4.6",
    "claude-sonnet-4.5": "Claude Sonnet 4.5",
    "gpt-5.4": "GPT-5.4",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
}
MODEL_ALIASES = {
    "claude opus 4.6": "claude-opus-4.6",
    "claude-opus-4.6": "claude-opus-4.6",
    "opus 4.6": "claude-opus-4.6",
    "opus4.6": "claude-opus-4.6",
    "opus": "claude-opus-4.6",
    "claude opus 4.5": "claude-opus-4.5",
    "claude-opus-4.5": "claude-opus-4.5",
    "opus 4.5": "claude-opus-4.5",
    "claude sonnet 4.6": "claude-sonnet-4.6",
    "claude-sonnet-4.6": "claude-sonnet-4.6",
    "sonnet 4.6": "claude-sonnet-4.6",
    "claude sonnet 4.5": "claude-sonnet-4.5",
    "claude-sonnet-4.5": "claude-sonnet-4.5",
    "sonnet 4.5": "claude-sonnet-4.5",
    "sonnet": "claude-sonnet-4.6",
    "gpt-5.4": "gpt-5.4",
    "gpt 5.4": "gpt-5.4",
    "gpt5.4": "gpt-5.4",
    "gemini 3.1 pro": "gemini-3.1-pro",
    "gemini-3.1-pro": "gemini-3.1-pro",
    "gemini 3.1": "gemini-3.1-pro",
}
RATE_LIMIT_PATTERNS = [
    r"user_model_rate_limited",
    r"hit a rate limit",
    r"please try again in",
    r"rate limit that restricts",
]


class ILongRunError(RuntimeError):
    pass


LongRunError = ILongRunError


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(default)


def write_json_atomic(path: Path, obj: Any) -> Path:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
        json.dump(obj, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    return path


def write_text_atomic(path: Path, text: str) -> Path:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
        tmp.write(text)
        if not text.endswith("\n"):
            tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    return path


def append_jsonl(path: Path, obj: Any) -> Path:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return path


def shallow_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = shallow_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_workspace(path: str | None = None) -> Path:
    return Path(path or os.getcwd()).expanduser().resolve()


def prompt_stem(prompt: str | None) -> str:
    text = (prompt or "").strip()
    if not text:
        return "mission"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    stem = lines[0] if lines else text
    stem = re.sub(r"^/(?:ilongrun|copilot-ilongrun)(?:-[a-z0-9-]+)?\b", "", stem, flags=re.I).strip()
    stem = re.sub(r"^#+\s*", "", stem)
    return stem or "mission"


def default_model_config() -> dict[str, Any]:
    return {
        "defaultPolicy": "ability-first-hybrid",
        "preferred": ["claude-opus-4.6", "claude-opus-4.5"],
        "fallback": ["claude-sonnet-4.6", "claude-sonnet-4.5", "gpt-5.4", "gemini-3.1-pro"],
        "backoffMinutes": [2, 5, 10],
        "availabilityTtlHours": 24,
        "displayNames": KNOWN_MODEL_DISPLAY,
        "aliases": MODEL_ALIASES,
    }


def load_model_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path).expanduser() if path else DEFAULT_MODEL_CONFIG
    config = read_json(config_path, default_model_config())
    merged = default_model_config()
    merged.update({k: v for k, v in config.items() if k not in {"displayNames", "aliases"}})
    merged["displayNames"] = shallow_merge(default_model_config()["displayNames"], config.get("displayNames", {}))
    merged["aliases"] = shallow_merge(default_model_config()["aliases"], config.get("aliases", {}))
    return merged


def availability_cache_path(path: str | Path | None = None) -> Path:
    return Path(path).expanduser() if path else DEFAULT_MODEL_AVAILABILITY


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def current_copilot_identity(config_dir: str | Path | None = None) -> str:
    for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return f"env:{name}"
    cfg_dir = Path(config_dir).expanduser() if config_dir else COPILOT_CONFIG_DIR
    cfg_json = cfg_dir / "config.json"
    obj = read_json(cfg_json, {})
    last = obj.get("last_logged_in_user") or {}
    login = last.get("login")
    host = last.get("host") or "https://github.com"
    if login:
        return f"{login}@{host}"
    return "unknown-account"


def account_fingerprint(identity: str) -> str:
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]


def read_model_availability(path: str | Path | None = None) -> dict[str, Any]:
    cache_path = availability_cache_path(path)
    default = {"version": 1, "accounts": {}}
    raw = read_json(cache_path, default)
    if not isinstance(raw, dict):
        return copy.deepcopy(default)
    raw.setdefault("version", 1)
    raw.setdefault("accounts", {})
    return raw


def write_model_availability(path: str | Path | None, payload: dict[str, Any]) -> Path:
    return write_json_atomic(availability_cache_path(path), payload)


def model_availability_snapshot(config: dict[str, Any], *, cache: dict[str, Any] | None = None, path: str | Path | None = None, identity: str | None = None) -> dict[str, dict[str, Any]]:
    cache_obj = cache or read_model_availability(path)
    ident = identity or current_copilot_identity()
    fingerprint = account_fingerprint(ident)
    ttl_hours = int(config.get("availabilityTtlHours", 24) or 24)
    models = (((cache_obj.get("accounts") or {}).get(fingerprint) or {}).get("models") or {})
    snapshot: dict[str, dict[str, Any]] = {}
    for slug in dict.fromkeys([*config.get("preferred", []), *config.get("fallback", [])]):
        entry = copy.deepcopy(models.get(slug) or {})
        checked = parse_iso(entry.get("checkedAt"))
        if checked is None or (datetime.now(timezone.utc) - checked).total_seconds() > ttl_hours * 3600:
            snapshot[slug] = {"status": "unknown", "reason": "cache-miss" if not entry else "stale-cache", "checkedAt": entry.get("checkedAt")}
            continue
        snapshot[slug] = {"status": entry.get("status", "unknown"), "reason": entry.get("reason", "cached"), "checkedAt": entry.get("checkedAt")}
    return snapshot


def normalize_model_name(value: str | None, config: dict[str, Any] | None = None) -> str | None:
    if not value:
        return None
    cfg = config or default_model_config()
    token = value.strip().lower()
    aliases = {k.lower(): v for k, v in cfg.get("aliases", {}).items()}
    if token in aliases:
        return aliases[token]
    if token in cfg.get("displayNames", {}):
        return token
    simplified = re.sub(r"\s+", " ", token)
    return aliases.get(simplified)


def detect_model_from_text(text: str | None, config: dict[str, Any] | None = None) -> str | None:
    if not text:
        return None
    cfg = config or default_model_config()
    lowered = text.lower()
    aliases = sorted(cfg.get("aliases", {}).items(), key=lambda item: len(item[0]), reverse=True)
    for alias, slug in aliases:
        if re.search(re.escape(alias.lower()), lowered):
            return slug
    return None


def display_model_name(slug: str, config: dict[str, Any] | None = None) -> str:
    cfg = config or default_model_config()
    return cfg.get("displayNames", {}).get(slug, slug)


def model_chain(config: dict[str, Any], explicit_model: str | None = None, prompt_text: str | None = None, *, availability: dict[str, dict[str, Any]] | None = None) -> list[str]:
    detected = normalize_model_name(explicit_model, config)
    if not detected:
        detected = detect_model_from_text(prompt_text, config)
    base_preferred = list(dict.fromkeys(config.get("preferred", [])))
    base_fallback = list(dict.fromkeys(config.get("fallback", [])))
    base_chain = [*base_preferred, *base_fallback]

    def status_of(slug: str) -> str:
        if not availability:
            return "unknown"
        return (availability.get(slug) or {}).get("status", "unknown")

    def ordered(seq: list[str]) -> tuple[list[str], list[str], list[str]]:
        return (
            [item for item in seq if status_of(item) == "available"],
            [item for item in seq if status_of(item) == "unknown"],
            [item for item in seq if status_of(item) == "unavailable"],
        )

    if detected:
        remainder = [item for item in base_chain if item != detected and status_of(item) != "unavailable"]
        unavailable = [item for item in base_chain if item != detected and status_of(item) == "unavailable"]
        return [detected, *remainder, *unavailable]

    preferred_available, preferred_unknown, _ = ordered(base_preferred)
    fallback_available, fallback_unknown, fallback_unavailable = ordered(base_fallback)
    chain = [*preferred_available, *preferred_unknown, *fallback_available, *fallback_unknown]
    return chain or [*base_chain, *fallback_unavailable]


def validate_model_config(config: dict[str, Any]) -> list[str]:
    known = set(KNOWN_MODEL_DISPLAY)
    errors: list[str] = []
    for field in ("preferred", "fallback"):
        for value in config.get(field, []):
            if value not in known:
                errors.append(f"{field} contains unknown model slug: {value}")
    for alias, slug in config.get("aliases", {}).items():
        if slug not in known:
            errors.append(f"alias '{alias}' points to unknown model slug: {slug}")
    backoff = config.get("backoffMinutes", [])
    if not isinstance(backoff, list) or not backoff or not all(isinstance(x, int) and x > 0 for x in backoff):
        errors.append("backoffMinutes must be a non-empty list of positive integers")
    ttl = config.get("availabilityTtlHours", 24)
    if not isinstance(ttl, int) or ttl <= 0:
        errors.append("availabilityTtlHours must be a positive integer")
    return errors


def slugify(text: str, max_len: int = 48) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    lowered = re.sub(r"-+", "-", lowered)
    return (lowered[:max_len] or "mission").strip("-")


def extract_rate_limit(output: str) -> bool:
    lowered = output.lower()
    return any(re.search(pattern, lowered) for pattern in RATE_LIMIT_PATTERNS)


def parse_json_argument(raw: str | None, default: Any = None) -> Any:
    if raw is None:
        return copy.deepcopy(default)
    if raw.startswith("@"):
        return read_json(Path(raw[1:]).expanduser(), default)
    return json.loads(raw)


def summarize_model_strategy(config: dict[str, Any], availability: dict[str, dict[str, Any]] | None = None) -> str:
    availability = availability or model_availability_snapshot(config)
    available_preferred = [item for item in config.get("preferred", []) if availability.get(item, {}).get("status") == "available"]
    latest_opus = display_model_name(available_preferred[0], config) if available_preferred else "None detected"
    preferred = " -> ".join(display_model_name(item, config) for item in config.get("preferred", []))
    fallback = " -> ".join(display_model_name(item, config) for item in config.get("fallback", []))
    backoff = " -> ".join(f"{m}m" for m in config.get("backoffMinutes", []))
    return (
        f"默认策略: {config.get('defaultPolicy', 'ability-first-hybrid')}\n"
        f"当前账号可用的最新 Opus: {latest_opus}\n"
        f"优先模型: {preferred}\n"
        f"回退链: {fallback}\n"
        f"限流退避: {backoff}"
    )


def classify_failure(hard_failures: Iterable[str] | None = None, drift_findings: Iterable[str] | None = None, *, last_error: str | None = None) -> tuple[str | None, str]:
    issues = " ".join([*(hard_failures or []), *(drift_findings or []), last_error or ""]).lower()
    if "dangerous shell expansion" in issues:
        return "shell_block", "rewrite shell checks to helper-first or python heredoc, then retry verify"
    if "plan.md" in issues or "drift" in issues or "scheduler" in issues or "activeworkstreams" in issues:
        return "state_drift", "run reconcile_ilongrun_run.py before the next verify/finalize"
    if "deliverable" in issues:
        return "verification_gap", "fix deliverable paths or produce the missing deliverable before finalize"
    if extract_rate_limit(issues):
        return "rate_limited", "wait for backoff or fallback model recovery, then retry"
    if issues.strip():
        return "tool_failure", "inspect the last failed step and retry with a smaller change"
    return None, "continue"
