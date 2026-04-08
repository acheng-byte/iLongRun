#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _ilongrun_delivery_audit import render_delivery_audit_markdown, scan_workspace_delivery_gaps
from _ilongrun_report_templates import build_adjudication_report_markdown
from _ilongrun_shared import (
    ILongRunError,
    account_fingerprint,
    append_jsonl,
    availability_cache_path,
    classify_failure,
    current_copilot_identity,
    default_model_config as base_default_model_config,
    detect_model_from_text,
    display_model_name,
    ensure_dir,
    extract_rate_limit,
    load_model_config as load_base_model_config,
    model_availability_snapshot,
    model_chain,
    normalize_model_name,
    now_iso,
    parse_json_argument,
    parse_iso,
    prompt_stem,
    read_json,
    read_model_availability,
    read_text,
    resolve_workspace,
    shallow_merge,
    slugify,
    validate_model_config,
    write_json_atomic,
    write_model_availability,
    write_text_atomic,
)

ILONGRUN_HOME = Path(os.environ.get("ILONGRUN_HOME", str(Path.home() / ".copilot-ilongrun")))
DEFAULT_MODEL_CONFIG = ILONGRUN_HOME / "config" / "model-policy.jsonc"
DEFAULT_MODEL_AVAILABILITY = ILONGRUN_HOME / "config" / "model-availability.json"
MANAGED_PLAN_START = "<!-- ILONGRUN:PLAN:START -->"
MANAGED_PLAN_END = "<!-- ILONGRUN:PLAN:END -->"
MANAGED_STRATEGY_START = "<!-- ILONGRUN:STRATEGY:START -->"
MANAGED_STRATEGY_END = "<!-- ILONGRUN:STRATEGY:END -->"
REVIEW_RELATIVE_PATH = "reviews/gpt54-final-review.md"
ADJUDICATION_RELATIVE_PATH = "reviews/adjudication.md"
DELIVERY_AUDIT_RELATIVE_PATH = "reviews/delivery-audit.md"
COMPLETION_RELATIVE_PATH = "COMPLETION.md"
MODELS_WITH_GPT54_LOGIC = {"gpt-5.4"}
COMPLETE_WORKSTREAM_STATUSES = {"complete", "completed", "verified", "done", "success", "succeeded", "pass", "passed", "finalized"}
ACTIVE_WORKSTREAM_STATUSES = {"running", "pending", "blocked", "in-progress", "active"}
COMPLETE_RUN_STATES = {"complete", "completed", "finalized"}
NON_TASK_LIST_PHASE_TOKENS = {"strategy", "verify", "review", "audit", "finalize"}


@dataclass
class RunTarget:
    workspace: Path
    base: Path
    run_id: str
    run_dir: Path


def default_model_config() -> dict[str, Any]:
    return base_default_model_config()


def load_model_config(path: str | Path | None = None) -> dict[str, Any]:
    return load_base_model_config(path)


def availability_cache_path_for_ilongrun(path: str | Path | None = None) -> Path:
    return Path(path).expanduser() if path else DEFAULT_MODEL_AVAILABILITY


def read_model_availability_for_ilongrun(path: str | Path | None = None) -> dict[str, Any]:
    return read_model_availability(availability_cache_path_for_ilongrun(path))


def write_model_availability_for_ilongrun(path: str | Path | None, payload: dict[str, Any]) -> Path:
    return write_model_availability(availability_cache_path_for_ilongrun(path), payload)


def resolve_run_target(workspace: str | Path | None = None, run_id: str | None = None) -> RunTarget:
    ws = resolve_workspace(str(workspace) if workspace else None)
    base = ws / ".copilot-ilongrun"
    state_dir = base / "state"
    if not run_id or run_id in {"latest", "active"}:
        state_name = "latest-run-id" if run_id in {None, "latest"} else "active-run-id"
        run_id = read_text(state_dir / state_name, "").strip()
    if not run_id:
        raise ILongRunError(f"No ilongrun run id found in workspace: {ws}")
    run_dir = base / "runs" / run_id
    return RunTarget(workspace=ws, base=base, run_id=run_id, run_dir=run_dir)


def mint_run_id(workspace: str | Path | None, prompt: str | None, *, max_slug_len: int = 24) -> str:
    ws = resolve_workspace(str(workspace) if workspace else None)
    runs_dir = ws / ".copilot-ilongrun" / "runs"
    ensure_dir(runs_dir)
    stamp = __import__('datetime').datetime.now().strftime("%Y%m%d-%H%M%S")
    base_slug = slugify(prompt_stem(prompt), max_len=max_slug_len) or "mission"
    candidate = f"{stamp}-{base_slug}"
    counter = 2
    while (runs_dir / candidate).exists():
        suffix = f"-{counter:02d}"
        slug_len = max(8, max_slug_len - len(suffix))
        slug = slugify(base_slug, max_len=slug_len) or "mission"
        candidate = f"{stamp}-{slug}{suffix}"
        counter += 1
    return candidate


def active_run_file(base: Path) -> Path:
    return base / "state" / "active-run-id"


def latest_run_file(base: Path) -> Path:
    return base / "state" / "latest-run-id"


def set_active_run(base: Path, run_id: str) -> Path:
    return write_text_atomic(active_run_file(base), run_id.strip())


def set_latest_run(base: Path, run_id: str) -> Path:
    return write_text_atomic(latest_run_file(base), run_id.strip())


def clear_active_run(base: Path, run_id: str | None = None) -> bool:
    path = active_run_file(base)
    if not path.exists():
        return False
    current = read_text(path, "").strip()
    if run_id is not None and current != run_id.strip():
        return False
    path.unlink(missing_ok=True)
    return True


def normalize_run_state(value: str | None) -> str:
    state = str(value or "").strip().lower()
    if state in COMPLETE_RUN_STATES:
        return "complete"
    if state in {"failed", "error"}:
        return "blocked"
    return state or "running"


def is_run_complete_state(value: str | None) -> bool:
    return normalize_run_state(value) == "complete"


def phase_supports_task_list(phase: dict[str, Any] | str | None) -> bool:
    if isinstance(phase, dict):
        phase_id = str(phase.get("id") or "").strip().lower()
        phase_name = str(phase.get("name") or "").strip().lower()
    else:
        phase_id = str(phase or "").strip().lower()
        phase_name = ""
    haystack = f"{phase_id} {phase_name}"
    return not any(token in haystack for token in NON_TASK_LIST_PHASE_TOKENS)


def scheduler_path(target: RunTarget) -> Path:
    return target.run_dir / "scheduler.json"


def mission_path(target: RunTarget) -> Path:
    return target.run_dir / "mission.md"


def strategy_path(target: RunTarget) -> Path:
    return target.run_dir / "strategy.md"


def plan_path(target: RunTarget) -> Path:
    return target.run_dir / "plan.md"


def journal_path(target: RunTarget) -> Path:
    return target.run_dir / "journal.jsonl"


def projection_log_path(target: RunTarget) -> Path:
    return target.run_dir / "projection-sync.jsonl"


def completion_path(target: RunTarget) -> Path:
    return target.run_dir / COMPLETION_RELATIVE_PATH


def reviews_dir(target: RunTarget) -> Path:
    return target.run_dir / "reviews"


def final_review_path(target: RunTarget) -> Path:
    return target.run_dir / REVIEW_RELATIVE_PATH


def adjudication_path(target: RunTarget) -> Path:
    return target.run_dir / ADJUDICATION_RELATIVE_PATH


def delivery_audit_path(target: RunTarget) -> Path:
    return target.run_dir / DELIVERY_AUDIT_RELATIVE_PATH


def task_list_path(target: RunTarget, index: int) -> Path:
    return target.run_dir / f"task-list-{index}.md"


def task_list_projection_path(target: RunTarget, rel_path: str) -> Path:
    cleaned = (rel_path or "").strip().lstrip("/").replace("\\", "/")
    return target.run_dir / cleaned


def workstreams_dir(target: RunTarget) -> Path:
    return target.run_dir / "workstreams"


def file_is_nonempty(path: Path | None) -> bool:
    return bool(path and path.exists() and path.is_file() and path.stat().st_size > 0)


def workstream_dir(target: RunTarget, workstream_id: str) -> Path:
    return workstreams_dir(target) / workstream_id


def workstream_brief_path(target: RunTarget, workstream_id: str) -> Path:
    return workstream_dir(target, workstream_id) / "brief.md"


def workstream_status_path(target: RunTarget, workstream_id: str) -> Path:
    return workstream_dir(target, workstream_id) / "status.json"


def workstream_result_path(target: RunTarget, workstream_id: str) -> Path:
    return workstream_dir(target, workstream_id) / "result.md"


def workstream_evidence_path(target: RunTarget, workstream_id: str) -> Path:
    return workstream_dir(target, workstream_id) / "evidence.md"


def sources_path(target: RunTarget) -> Path:
    return target.run_dir / "sources.jsonl"


def stable_source_id(url: str, title: str = "") -> str:
    return hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:12]


def legacy_run_dir(target: RunTarget) -> Path:
    return target.base / target.run_id


def legacy_imports_dir(target: RunTarget) -> Path:
    return target.base / "legacy-imports"


def merge_report_dir(target: RunTarget) -> Path:
    return legacy_imports_dir(target) / "run-merges"


def status_rank(status: str | None) -> int:
    order = {
        "pending": 0,
        "running": 1,
        "blocked": 2,
        "complete": 3,
        "verified": 4,
    }
    return order.get((status or "").lower(), 0)


def is_placeholder_work_product(path: Path, text: str | None = None) -> bool:
    body = (text if text is not None else read_text(path, "")).strip()
    if not body:
        return True
    name = path.name
    if name == "result.md" and body.startswith("# Result") and "Pending result for `" in body:
        return True
    if name == "evidence.md" and body.startswith("# Evidence") and "Pending evidence for `" in body:
        return True
    if name == "status.json":
        data = read_json(path, {})
        return (data.get("status") or "").lower() in {"", "pending"}
    return False


def normalize_rel_path(value: str | None, fallback: str) -> str:
    text = (value or "").strip().replace("\\", "/").lstrip("/")
    return text or fallback


def workstream_numeric_index(workstream: dict[str, Any], position: int) -> int:
    raw = workstream.get("index")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    match = re.search(r"(\d+)$", str(workstream.get("id") or ""))
    if match:
        return int(match.group(1))
    return position


def phase_task_list_specs(scheduler: dict[str, Any]) -> dict[str, dict[str, str]]:
    specs: dict[str, dict[str, str]] = {}
    ordinal = 1
    for phase in scheduler.get("phases") or []:
        phase_id = str(phase.get("id") or "")
        if not phase_id or not phase_supports_task_list(phase):
            continue
        task_list_id = f"task-list-{ordinal}"
        specs[phase_id] = {
            "id": task_list_id,
            "path": f"{task_list_id}.md",
            "title": str(phase.get("name") or task_list_id),
        }
        ordinal += 1
    return specs


def default_task_list_binding(scheduler: dict[str, Any], workstream: dict[str, Any]) -> dict[str, str]:
    explicit_path = (workstream.get("taskListPath") or "").strip()
    explicit_id = (workstream.get("taskListId") or "").strip()
    phase_specs = phase_task_list_specs(scheduler)
    if explicit_path:
        path = normalize_rel_path(explicit_path, explicit_path)
        stem = Path(path).stem or explicit_id or "task-list"
        return {"id": explicit_id or stem, "path": path}
    if explicit_id:
        task_list_id = explicit_id.replace(".md", "")
        return {"id": task_list_id, "path": f"{task_list_id}.md"}
    phase_id = str(workstream.get("phaseId") or "")
    if phase_id in phase_specs:
        return {
            "id": phase_specs[phase_id]["id"],
            "path": phase_specs[phase_id]["path"],
        }
    return {"id": "", "path": ""}


def normalize_checklist_items(
    raw_items: list[Any] | None,
    fallback_texts: list[str],
    prefix: str,
) -> list[dict[str, Any]]:
    items = raw_items if isinstance(raw_items, list) else []
    normalized: list[dict[str, Any]] = []
    if not items:
        items = fallback_texts
    for idx, raw in enumerate(items, start=1):
        if isinstance(raw, dict):
            text = str(raw.get("text") or "").strip()
            if not text:
                continue
            status = str(raw.get("status") or "pending").strip().lower()
            normalized.append(
                {
                    "id": str(raw.get("id") or f"{prefix}-{idx}"),
                    "text": text,
                    "status": status if status else "pending",
                    "evidenceRefs": list(raw.get("evidenceRefs") or []),
                }
            )
            continue
        text = str(raw or "").strip()
        if not text:
            continue
        normalized.append(
            {
                "id": f"{prefix}-{idx}",
                "text": text,
                "status": "pending",
                "evidenceRefs": [],
            }
        )
    return normalized


def workstream_projection_state(target: RunTarget, workstream: dict[str, Any]) -> dict[str, Any]:
    result_path = workstream_result_path(target, workstream["id"])
    evidence_path = workstream_evidence_path(target, workstream["id"])
    status_path = workstream_status_path(target, workstream["id"])
    result_ready = result_path.exists() and not is_placeholder_work_product(result_path)
    evidence_ready = evidence_path.exists() and not is_placeholder_work_product(evidence_path)
    status_ready = status_path.exists() and not is_placeholder_work_product(status_path)
    claimed_done = str(workstream.get("status") or "").lower() in COMPLETE_WORKSTREAM_STATUSES
    work_product_ready = result_ready and evidence_ready and status_ready
    drift = claimed_done and not work_product_ready
    return {
        "resultReady": result_ready,
        "evidenceReady": evidence_ready,
        "statusReady": status_ready,
        "workProductReady": work_product_ready,
        "claimedDone": claimed_done,
        "drift": drift,
    }


def checklist_mark(item: dict[str, Any]) -> str:
    return "x" if str(item.get("status") or "").lower() == "done" else " "


def append_unique_jsonl(dst: Path, src: Path) -> int:
    existing_lines = set(read_text(dst, "").splitlines()) if dst.exists() else set()
    appended = 0
    ensure_dir(dst.parent)
    for line in read_text(src, "").splitlines():
        if not line or line in existing_lines:
            continue
        with dst.open("a", encoding="utf-8") as handle:
            handle.write(line.rstrip() + "\n")
        existing_lines.add(line)
        appended += 1
    return appended


def scheduler_signal_score(scheduler: dict[str, Any]) -> tuple[int, str]:
    raw_workstreams = scheduler.get("workstreams") or []
    if isinstance(raw_workstreams, dict):
        workstreams = list(raw_workstreams.values())
    else:
        workstreams = list(raw_workstreams)
    completed = len([ws for ws in workstreams if isinstance(ws, dict) and (ws.get("status") or "").lower() in COMPLETE_WORKSTREAM_STATUSES])
    reviews = scheduler.get("reviews") or {}
    deliverables = len([item for item in scheduler.get("deliverables") or [] if item])
    state_bonus = {"complete": 40, "blocked": 20, "running": 10}.get((scheduler.get("state") or "").lower(), 0)
    score = (
        completed * 10
        + deliverables * 3
        + (15 if reviews.get("status") in {"passed", "failed"} else 0)
        + (8 if (reviews.get("pendingMustFixCount") or 0) == 0 and reviews.get("status") in {"passed", "not-required"} else 0)
        + state_bonus
    )
    updated = scheduler.get("updatedAt") or ""
    return score, updated


def normalize_legacy_scheduler_shape(canonical: dict[str, Any], legacy: dict[str, Any], run_id: str) -> dict[str, Any]:
    if isinstance(legacy.get("workstreams"), list):
        return legacy
    if not isinstance(legacy.get("workstreams"), dict):
        return legacy

    imported = ensure_scheduler_defaults(copy.deepcopy(canonical))
    imported["runId"] = run_id
    imported["profile"] = legacy.get("profile") or imported.get("profile")
    imported["createdAt"] = legacy.get("created") or imported.get("createdAt")
    imported["updatedAt"] = legacy.get("updated") or imported.get("updatedAt")
    imported["summary"] = "Imported legacy root-directory run state"

    legacy_items = list((legacy.get("workstreams") or {}).values())
    all_done = legacy_items and all(str((item or {}).get("status", "")).lower() in {"done", "complete", "verified", "pass", "passed"} for item in legacy_items)
    if all_done:
        for ws in imported.get("workstreams") or []:
            ws["status"] = "complete"
        imported["completedWorkstreams"] = [ws["id"] for ws in imported.get("workstreams") or []]
        imported["activeWorkstreams"] = []
        imported["phase"] = "phase-finalize"

    gates = legacy.get("gates") or {}
    audit_gate = str(gates.get("gpt54Audit") or "").lower()
    if audit_gate in {"fail", "failed", "blocked"}:
        imported["state"] = "blocked"
        imported["phase"] = "phase-audit"
        imported.setdefault("reviews", {})["status"] = "failed"
        imported["reviews"]["pendingMustFixCount"] = max(int((imported.get("reviews") or {}).get("pendingMustFixCount") or 0), 1)
    elif str(legacy.get("status") or "").lower() in {"finalized", "complete", "completed"} and all_done:
        imported["state"] = "complete"

    return imported


def choose_preferred_scheduler(primary: dict[str, Any], secondary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    primary_score, primary_updated = scheduler_signal_score(primary)
    secondary_score, secondary_updated = scheduler_signal_score(secondary)
    if primary_score > secondary_score:
        return primary, secondary, "higher-signal"
    if secondary_score > primary_score:
        return secondary, primary, "higher-signal"
    primary_dt = parse_iso(primary_updated)
    secondary_dt = parse_iso(secondary_updated)
    if primary_dt and secondary_dt:
        if primary_dt >= secondary_dt:
            return primary, secondary, "newer-updatedAt"
        return secondary, primary, "newer-updatedAt"
    return primary, secondary, "tie-primary"


def merge_scheduler_payloads(canonical: dict[str, Any], legacy: dict[str, Any], run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    legacy = normalize_legacy_scheduler_shape(canonical, legacy, run_id)
    preferred, supplemental, reason = choose_preferred_scheduler(legacy, canonical)
    merged = shallow_merge(supplemental, preferred)
    created_candidates = [value for value in [canonical.get("createdAt"), legacy.get("createdAt")] if value]
    updated_candidates = [value for value in [canonical.get("updatedAt"), legacy.get("updatedAt")] if value]
    if created_candidates:
        merged["createdAt"] = sorted(created_candidates)[0]
    if updated_candidates:
        merged["updatedAt"] = sorted(updated_candidates)[-1]
    merged["runId"] = run_id
    migration = {
        "preferredSource": "legacy" if preferred is legacy else "canonical",
        "reason": reason,
        "canonicalUpdatedAt": canonical.get("updatedAt"),
        "legacyUpdatedAt": legacy.get("updatedAt"),
    }
    return merged, migration


def merge_legacy_run_dir(target: RunTarget) -> dict[str, Any] | None:
    legacy_dir = legacy_run_dir(target)
    if not legacy_dir.exists() or legacy_dir == target.run_dir:
        return None

    ensure_dir(target.run_dir)
    ensure_dir(merge_report_dir(target))
    canonical_scheduler = read_json(scheduler_path(target), {})
    legacy_scheduler = read_json(legacy_dir / "scheduler.json", {})
    merged_scheduler, migration = merge_scheduler_payloads(canonical_scheduler, legacy_scheduler, target.run_id)
    write_json_atomic(scheduler_path(target), merged_scheduler)

    copied_files: list[str] = []
    appended_jsonl: dict[str, int] = {}

    for rel in ["journal.jsonl", "hook-events.jsonl"]:
        src = legacy_dir / rel
        dst = target.run_dir / rel
        if src.exists():
            appended = append_unique_jsonl(dst, src)
            if appended:
                appended_jsonl[rel] = appended

    candidate_patterns = [
        "COMPLETION.md",
        "reviews/*.md",
        "workstreams/*/result.md",
        "workstreams/*/evidence.md",
        "workstreams/*/status.json",
    ]
    for pattern in candidate_patterns:
        for src in legacy_dir.glob(pattern):
            if src.is_dir():
                continue
            rel = src.relative_to(legacy_dir)
            dst = target.run_dir / rel
            ensure_dir(dst.parent)
            if src.name == "status.json":
                src_status = read_json(src, {})
                dst_status = read_json(dst, {})
                if not dst.exists() or status_rank(src_status.get("status")) >= status_rank(dst_status.get("status")):
                    shutil.copy2(src, dst)
                    copied_files.append(str(rel))
                continue
            if rel.as_posix() in {"journal.jsonl", "hook-events.jsonl"}:
                continue
            if not dst.exists():
                shutil.copy2(src, dst)
                copied_files.append(str(rel))
                continue
            src_text = read_text(src, "")
            dst_text = read_text(dst, "")
            should_replace = False
            if is_placeholder_work_product(dst, dst_text) and not is_placeholder_work_product(src, src_text):
                should_replace = True
            elif src.stat().st_mtime >= dst.stat().st_mtime and len(src_text.strip()) > len(dst_text.strip()):
                should_replace = True
            if should_replace:
                shutil.copy2(src, dst)
                copied_files.append(str(rel))

    report = {
        "ts": now_iso(),
        "runId": target.run_id,
        "canonicalRunDir": str(target.run_dir),
        "legacyRunDir": str(legacy_dir),
        "migration": migration,
        "copiedFiles": copied_files,
        "appendedJsonl": appended_jsonl,
    }
    report_path = merge_report_dir(target) / f"{target.run_id}-{now_iso().replace(':', '').replace('-', '')}.json"
    write_json_atomic(report_path, report)
    shutil.rmtree(legacy_dir, ignore_errors=True)
    return report


def profile_from_prompt(prompt: str) -> str:
    lowered = prompt.lower()
    coding_signals = ["代码", "bug", "测试", "构建", "重构", "脚本", "repo", "ci", "fix", "implement", "refactor", "test", "debug", "build", "audit", "review"]
    research_signals = ["调研", "research", "趋势", "分析", "市场", "政策", "法规", "competitive", "benchmark", "industry"]
    office_signals = ["表格", "文档", "汇报", "ppt", "幻灯片", "excel", "csv", "markdown", "报告", "总结", "材料", "slide", "sheet", "doc"]
    if any(signal in lowered for signal in coding_signals):
        return "coding"
    if any(signal in lowered for signal in research_signals):
        return "research"
    if any(signal in lowered for signal in office_signals):
        return "office"
    return "office"


def infer_language(prompt: str | None) -> str:
    return "zh-CN" if re.search(r"[\u4e00-\u9fff]", prompt or "") else "en-US"


def infer_termination_mode(prompt: str) -> str:
    lowered = prompt.lower()
    if any(token in lowered for token in ["持续监控", "watch", "轮询", "deadline", "监控", "keep running"]):
        return "watch-until-deadline"
    if any(token in lowered for token in ["checkpoint", "稍后回来", "先别结束", "保留现场"]):
        return "checkpoint-and-stop"
    return "complete-and-exit"


def infer_mode(prompt: str, profile: str) -> str:
    lowered = prompt.lower()
    if infer_termination_mode(prompt) == "watch-until-deadline":
        return "sentinel-watch"
    independent_signals = sum(token in lowered for token in ["1)", "2)", "3)", "4)", "并行", "parallel", "分别", "专题", "多部分", "多个模块"])
    dependency_signals = sum(token in lowered for token in ["依赖", "然后", "随后", "集成", "整合", "验证", "phase", "阶段"])
    hard_signals = sum(token in lowered for token in ["长跑", "长期", "复杂", "大规模", "重构", "审计", "fleet", "governor"])
    if profile == "coding" and hard_signals >= 1:
        return "fleet-governor"
    if hard_signals >= 2:
        return "fleet-governor"
    if independent_signals >= 3 and dependency_signals == 0:
        return "super-swarm"
    if independent_signals >= 2 or dependency_signals >= 2:
        return "wave-swarm"
    return "direct-lane"


def extract_numbered_items(prompt: str) -> list[str]:
    text = prompt.replace("\n", " ")
    patterns = re.findall(r"(?:^|[：:])\s*(?:1[\)\.、]|1\])\s*(.+)", text)
    if patterns:
        text = patterns[0]
    items = re.findall(r"(?:^|\s)(\d+[\)\.、]|\d+\])\s*([^\d]+?)(?=(?:\s\d+[\)\.、]|\s\d+\])|$)", text)
    result = []
    for _, item in items:
        cleaned = re.sub(r"\s+", " ", item).strip(" ;，。")
        if cleaned:
            result.append(cleaned)
    if result:
        return result[:4]
    bullet_items = []
    for line in prompt.splitlines():
        m = re.match(r"\s*[-*]\s+(.+?)\s*$", line)
        if m:
            bullet_items.append(m.group(1).strip())
    if bullet_items:
        return bullet_items[:4]

    colon_candidates: list[str] = []
    colon_match = re.search(r"[：:]\s*([^。\n]+)", prompt)
    if colon_match:
        colon_candidates.append(colon_match.group(1).strip())
    colon_candidates.append(prompt_stem(prompt))

    stop_prefixes = ("并", "且", "然后", "最后", "再", "并且", "并分别", "分别", "统一", "汇总", "整合")
    for candidate in colon_candidates:
        if not candidate:
            continue
        parts = re.split(r"[、,，;；/]+", candidate)
        cleaned_parts: list[str] = []
        for part in parts:
            cleaned = re.sub(r"\s+", " ", part).strip(" ;，。:：")
            if not cleaned:
                continue
            if cleaned.startswith(stop_prefixes):
                break
            cleaned = re.sub(r"^(?:专题|任务|模块|方向|工作流|workstream)\s*", "", cleaned, flags=re.I)
            if cleaned:
                cleaned_parts.append(cleaned)
        unique_parts: list[str] = []
        for part in cleaned_parts:
            if part not in unique_parts:
                unique_parts.append(part)
        if 2 <= len(unique_parts) <= 4:
            return unique_parts[:4]

    return []


def infer_requested_deliverables(prompt: str) -> list[str]:
    deliverables: list[str] = []
    patterns = [
        r"(?:保存到|保存至|写入|output to|save to|write to)\s*[`\"]?([A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)[`\"]?",
        r"(?:生成|输出为)\s*[`\"]?([A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)[`\"]?",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, prompt, flags=re.I):
            if match not in deliverables:
                deliverables.append(match)
    if not deliverables and profile_from_prompt(prompt) == "coding":
        deliverables.append(REVIEW_RELATIVE_PATH)
    return deliverables


def infer_completeness(prompt: str, profile: str, mode: str) -> list[str]:
    items = [
        "需要生成 strategy.md 解释模式、并行边界、模型分配和降级路径",
        "需要至少一个 task-list-N.md 作为顶层 plan 的可执行展开",
        "所有 required workstream 都要有 result.md 与 evidence.md 占位或实产物",
    ]
    if profile == "coding":
        items.extend([
            "必须保留本地验证步骤与回归检查",
            "finalize 前必须存在最终终审报告",
        ])
    if profile in {"research", "office"}:
        items.append("需要保留证据链和来源说明")
    if mode in {"wave-swarm", "super-swarm", "fleet-governor"}:
        items.append("需要显式记录 phase / wave / workstream 依赖")
    return items


def role_models(config: dict[str, Any]) -> dict[str, str]:
    return copy.deepcopy(config.get("roleModels") or default_model_config().get("roleModels", {}))


def role_model_for(role: str, config: dict[str, Any], *, fallback: str = "claude-opus-4.6") -> str:
    return role_models(config).get(role, fallback)


def supports_fleet_backend(mode: str, profile: str, workstreams: list[dict[str, Any]]) -> bool:
    if mode not in {"super-swarm", "wave-swarm"}:
        return False
    if profile == "coding":
        return False
    independent = [ws for ws in workstreams if not ws.get("dependencies") and ws.get("required", True)]
    if not (2 <= len(independent) <= 4):
        return False
    write_sets = [tuple(ws.get("writeSet") or []) for ws in independent]
    if len(set(write_sets)) != len(write_sets):
        return False
    return all(ws.get("backend") in {None, "internal", "fleet"} for ws in independent)


def short_label(text: str, *, max_len: int = 42) -> str:
    stripped = re.sub(r"[`*_#\[\]]", "", text).strip()
    if len(stripped) <= max_len:
        return stripped
    return stripped[: max_len - 1].rstrip() + "…"


def make_workstream(
    *,
    idx: int,
    name: str,
    goal: str,
    phase_id: str,
    wave_id: str,
    role: str,
    model: str,
    profile: str,
    dependencies: list[str] | None = None,
    outputs: list[str] | None = None,
    backend: str = "internal",
    write_set: list[str] | None = None,
    required: bool = True,
) -> dict[str, Any]:
    ws_id = f"ws-{idx:03d}"
    index = idx
    outputs = list(outputs or [])
    dependencies = list(dependencies or [])
    write_set = list(write_set or [f"workstreams/{ws_id}"])
    acceptance = [
        f"目标达成：{short_label(goal, max_len=80)}",
        f"结果文件存在：`workstreams/{ws_id}/result.md`",
        f"证据文件存在：`workstreams/{ws_id}/evidence.md`",
    ]
    verify = [
        "核对输入依赖是否齐备",
        "检查 result.md 与 evidence.md 内容不是空壳",
    ]
    if profile == "coding":
        verify.append("补充本地验证摘要或回归检查记录")
    return {
        "id": ws_id,
        "index": index,
        "name": short_label(name),
        "goal": goal,
        "phaseId": phase_id,
        "waveId": wave_id,
        "status": "pending",
        "required": required,
        "dependencies": dependencies,
        "inputs": [],
        "outputs": outputs,
        "ownerRole": role,
        "ownerModel": model,
        "backend": backend,
        "retryBudget": 2,
        "writeSet": write_set,
        "acceptance": acceptance,
        "verify": verify,
        "acceptanceChecklist": normalize_checklist_items([], acceptance, f"{ws_id}-acceptance"),
        "verifyChecklist": normalize_checklist_items([], verify, f"{ws_id}-verify"),
        "briefPath": f"workstreams/{ws_id}/brief.md",
        "resultPath": f"workstreams/{ws_id}/result.md",
        "evidencePath": f"workstreams/{ws_id}/evidence.md",
        "statusPath": f"workstreams/{ws_id}/status.json",
        "notes": [],
        "lastUpdatedAt": now_iso(),
    }


def infer_initial_topology(prompt: str, profile: str, mode: str, config: dict[str, Any], requested_deliverables: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    role_map = role_models(config)
    phases: list[dict[str, Any]] = []
    workstreams: list[dict[str, Any]] = []
    phases.append({
        "id": "phase-strategy",
        "name": "Strategy Synthesis",
        "status": "pending",
        "required": True,
        "waves": [
            {"id": "wave-strategy", "name": "Strategy", "status": "pending", "backend": "internal", "required": True, "reason": "顶层策略生成必须由 ilongrun 内核主控", "workstreams": []}
        ],
    })

    extracted = extract_numbered_items(prompt)
    execution_phase = {
        "id": "phase-execution",
        "name": "Execution",
        "status": "pending",
        "required": True,
        "waves": [],
    }
    phases.append(execution_phase)

    seeds: list[str]
    if extracted:
        seeds = extracted[:4]
    else:
        seeds = [prompt_stem(prompt)]

    if mode == "direct-lane":
        backend = "internal"
        ws = make_workstream(
            idx=1,
            name="Primary execution",
            goal=seeds[0],
            phase_id="phase-execution",
            wave_id="wave-execution-1",
            role="executor",
            model=role_map.get("executor", "claude-opus-4.6"),
            profile=profile,
            outputs=requested_deliverables,
            backend=backend,
            write_set=requested_deliverables or ["workspace-mutating" if profile == "coding" else "workstreams/ws-001"],
        )
        workstreams.append(ws)
        execution_phase["waves"].append({"id": "wave-execution-1", "name": "Execution", "status": "pending", "backend": backend, "required": True, "reason": "单主链路任务", "workstreams": [ws["id"]]})
    else:
        first_wave_streams = []
        for idx, seed in enumerate(seeds, start=1):
            ws = make_workstream(
                idx=idx,
                name=f"Workstream {idx}",
                goal=seed,
                phase_id="phase-execution",
                wave_id="wave-execution-1",
                role="executor",
                model=role_map.get("executor", "claude-opus-4.6"),
                profile=profile,
                outputs=[],
                backend="internal",
                write_set=[f"workstreams/ws-{idx:03d}"],
            )
            workstreams.append(ws)
            first_wave_streams.append(ws["id"])
        first_wave_backend = "fleet" if supports_fleet_backend(mode, profile, workstreams[: len(first_wave_streams)]) else "internal"
        for ws in workstreams[: len(first_wave_streams)]:
            ws["backend"] = first_wave_backend
        execution_phase["waves"].append({
            "id": "wave-execution-1",
            "name": "Parallel workstreams",
            "status": "pending",
            "backend": first_wave_backend,
            "required": True,
            "reason": "可分解工作流；若满足条件则允许 /fleet 承载执行波次",
            "workstreams": first_wave_streams,
        })
        integration_id = len(workstreams) + 1
        integration_outputs = requested_deliverables or ([REVIEW_RELATIVE_PATH] if profile == "coding" else [])
        integration = make_workstream(
            idx=integration_id,
            name="Integration",
            goal="整合前序 workstream 结果并准备 gate 验证",
            phase_id="phase-execution",
            wave_id="wave-execution-2",
            role="executor",
            model=role_map.get("executor", "claude-opus-4.6"),
            profile=profile,
            dependencies=first_wave_streams,
            outputs=integration_outputs,
            backend="internal",
            write_set=integration_outputs or [f"workstreams/ws-{integration_id:03d}"] + (["workspace-mutating"] if profile == "coding" else []),
        )
        workstreams.append(integration)
        execution_phase["waves"].append({
            "id": "wave-execution-2",
            "name": "Integration and consolidation",
            "status": "pending",
            "backend": "internal",
            "required": True,
            "reason": "依赖前序结果，必须顺序整合",
            "workstreams": [integration["id"]],
        })

    if profile == "coding":
        phases.append({
            "id": "phase-audit",
            "name": "Final Audit",
            "status": "pending",
            "required": True,
            "waves": [
                {"id": "wave-audit-1", "name": "Final audit", "status": "pending", "backend": "internal", "required": True, "reason": "最终终审不可委托给 /fleet", "workstreams": []}
            ],
        })
    phases.append({
        "id": "phase-finalize",
        "name": "Finalize",
        "status": "pending",
        "required": True,
        "waves": [
            {"id": "wave-finalize-1", "name": "Finalize", "status": "pending", "backend": "internal", "required": True, "reason": "收尾必须由主控执行", "workstreams": []}
        ],
    })
    return phases, workstreams


def default_success_criteria(profile: str, deliverables: list[str]) -> list[str]:
    criteria = ["plan.md、strategy.md、scheduler.json、task-list-N.md 已落盘并同步"]
    if deliverables:
        criteria.extend([f"交付物存在：`{item}`" for item in deliverables])
    if profile == "coding":
        criteria.append("存在最终终审报告且无未处理 must-fix")
    if profile in {"research", "office"}:
        criteria.append("关键 workstream 留下 evidence 说明")
    return criteria


def default_constraints(profile: str, language: str) -> list[str]:
    constraints = [
        "Scope: current workspace only unless explicitly expanded",
        "Git side effects disabled unless explicitly requested",
        f"Language: {language}",
    ]
    if profile in {"research", "office"}:
        constraints.append("Public web allowed for evidence; private SaaS blocked unless access is provided")
    else:
        constraints.append("Local files + shell first; avoid unnecessary network use")
    return constraints


def normalize_workstream_records(payload: dict[str, Any]) -> None:
    phase_specs = phase_task_list_specs(payload)
    normalized_workstreams: list[dict[str, Any]] = []
    task_list_records: dict[str, dict[str, Any]] = {}
    for position, raw in enumerate(payload.get("workstreams") or [], start=1):
        item = copy.deepcopy(raw or {})
        ws_id = str(item.get("id") or f"ws-{position:03d}")
        item["id"] = ws_id
        item["index"] = workstream_numeric_index(item, position)
        item.setdefault("name", short_label(ws_id))
        item.setdefault("goal", "")
        item.setdefault("phaseId", "")
        item.setdefault("waveId", "")
        item.setdefault("status", "pending")
        item.setdefault("required", True)
        item.setdefault("dependencies", [])
        item.setdefault("inputs", [])
        item.setdefault("outputs", [])
        item.setdefault("ownerRole", item.get("role") or "executor")
        item.setdefault("ownerModel", item.get("model") or payload.get("selectedModel") or default_model_config().get("roleModels", {}).get("executor", "claude-opus-4.6"))
        item.setdefault("backend", "internal")
        item.setdefault("retryBudget", 2)
        item.setdefault("writeSet", [f"workstreams/{ws_id}"])
        item.setdefault("notes", [])
        binding = default_task_list_binding(payload, item)
        item["taskListId"] = str(item.get("taskListId") or binding["id"] or "")
        item["taskListPath"] = normalize_rel_path(item.get("taskListPath"), binding["path"]) if (item.get("taskListPath") or binding["path"]) else ""
        item["briefPath"] = normalize_rel_path(item.get("briefPath"), f"workstreams/{ws_id}/brief.md")
        item["resultPath"] = normalize_rel_path(item.get("resultPath"), f"workstreams/{ws_id}/result.md")
        item["evidencePath"] = normalize_rel_path(item.get("evidencePath"), f"workstreams/{ws_id}/evidence.md")
        item["statusPath"] = normalize_rel_path(item.get("statusPath"), f"workstreams/{ws_id}/status.json")
        acceptance_texts = [str(text) for text in item.get("acceptance") or [] if str(text).strip()]
        verify_texts = [str(text) for text in item.get("verify") or [] if str(text).strip()]
        item["acceptanceChecklist"] = normalize_checklist_items(item.get("acceptanceChecklist"), acceptance_texts, f"{ws_id}-acceptance")
        item["verifyChecklist"] = normalize_checklist_items(item.get("verifyChecklist"), verify_texts, f"{ws_id}-verify")
        item["acceptance"] = [entry["text"] for entry in item.get("acceptanceChecklist") or []]
        item["verify"] = [entry["text"] for entry in item.get("verifyChecklist") or []]
        item.setdefault("lastUpdatedAt", now_iso())
        normalized_workstreams.append(item)

        if item["taskListPath"]:
            phase_title = phase_specs.get(str(item.get("phaseId") or ""), {}).get("title") or str(item.get("phaseId") or item["taskListId"])
            record = task_list_records.setdefault(
                item["taskListPath"],
                {
                    "id": item["taskListId"] or Path(item["taskListPath"]).stem,
                    "path": item["taskListPath"],
                    "title": phase_title,
                    "phaseId": item.get("phaseId"),
                    "waveIds": [],
                    "workstreamIds": [],
                },
            )
            if item.get("waveId") and item["waveId"] not in record["waveIds"]:
                record["waveIds"].append(item["waveId"])
            record["workstreamIds"].append(item["id"])

    payload["workstreams"] = normalized_workstreams

    existing_records = {}
    for entry in payload.get("taskLists") or []:
        if not isinstance(entry, dict):
            continue
        path = normalize_rel_path(entry.get("path"), str(entry.get("path") or ""))
        if not path:
            continue
        existing_records[path] = {
            "id": str(entry.get("id") or Path(path).stem),
            "path": path,
            "title": str(entry.get("title") or Path(path).stem),
            "phaseId": entry.get("phaseId"),
            "waveIds": list(entry.get("waveIds") or []),
            "workstreamIds": list(entry.get("workstreamIds") or []),
        }

    merged_task_lists: list[dict[str, Any]] = []
    for path, record in task_list_records.items():
        existing = existing_records.get(path, {})
        merged_task_lists.append(
            {
                "id": existing.get("id") or record["id"],
                "path": path,
                "title": existing.get("title") or record["title"],
                "phaseId": existing.get("phaseId") or record["phaseId"],
                "waveIds": existing.get("waveIds") or record["waveIds"],
                "workstreamIds": existing.get("workstreamIds") or record["workstreamIds"],
            }
        )
    payload["taskLists"] = merged_task_lists


def ensure_scheduler_defaults(scheduler: dict[str, Any] | None) -> dict[str, Any]:
    payload = copy.deepcopy(scheduler or {})
    payload.setdefault("runId", "")
    payload["state"] = normalize_run_state(payload.get("state") or "running")
    payload.setdefault("phase", "strategy")
    payload.setdefault("summary", "ILongRun mission initialized")
    payload.setdefault("profile", "office")
    payload.setdefault("mode", "direct-lane")
    payload.setdefault("language", "zh-CN")
    payload.setdefault("terminationMode", "complete-and-exit")
    payload.setdefault("deliverables", [])
    payload.setdefault("requestedDeliverables", [])
    payload.setdefault("completedWorkstreams", [])
    payload.setdefault("activeWorkstreams", [])
    payload.setdefault("phases", [])
    payload.setdefault("workstreams", [])
    payload.setdefault("taskLists", [])
    payload.setdefault("mission", {})
    payload.setdefault("reviews", {})
    payload.setdefault("verification", {})
    payload.setdefault("recoveryState", {})
    payload.setdefault("projectionState", {})
    payload.setdefault("runtime", {})
    payload.setdefault("modelAttemptHistory", [])
    payload.setdefault("fallbackChain", [])
    payload.setdefault("fallbackReason", None)
    payload.setdefault("lastError", None)
    normalize_workstream_records(payload)
    mission = payload.get("mission") or {}
    mission.setdefault("goal", "")
    mission.setdefault("prompt", "")
    mission.setdefault("profile", payload.get("profile", "office"))
    mission.setdefault("mode", payload.get("mode", "direct-lane"))
    mission.setdefault("terminationMode", payload.get("terminationMode", "complete-and-exit"))
    mission.setdefault("requestedDeliverables", payload.get("requestedDeliverables") or [])
    mission.setdefault("inferredCompleteness", [])
    mission.setdefault("constraints", [])
    mission.setdefault("successCriteria", [])
    mission.setdefault("capabilityBoundary", ["local-files", "shell"])
    mission.setdefault("modelAllocation", {})
    payload["mission"] = mission
    reviews = payload.get("reviews") or {}
    reviews.setdefault("required", payload.get("profile") == "coding")
    reviews.setdefault("finalReviewPath", REVIEW_RELATIVE_PATH)
    reviews.setdefault("adjudicationPath", ADJUDICATION_RELATIVE_PATH)
    reviews.setdefault("deliveryAuditPath", DELIVERY_AUDIT_RELATIVE_PATH)
    reviews.setdefault("auditModel", payload.get("codingAuditModel") or default_model_config().get("codingAuditModel"))
    reviews.setdefault("status", "pending" if reviews.get("required") else "not-required")
    reviews.setdefault("pendingMustFixCount", 0)
    reviews.setdefault("mustFix", [])
    reviews.setdefault("shouldFix", [])
    reviews.setdefault("defer", [])
    reviews.setdefault("adjudicationStatus", "pending" if reviews.get("required") else "not-required")
    payload["reviews"] = reviews
    verification = payload.get("verification") or {}
    verification.setdefault("state", "pending")
    verification.setdefault("hardFailures", [])
    verification.setdefault("softWarnings", [])
    verification.setdefault("driftFindings", [])
    verification.setdefault("recommendedAction", "continue")
    verification.setdefault("failureClass", None)
    verification.setdefault("lastVerifiedAt", None)
    verification.setdefault("completionScore", None)
    payload["verification"] = verification
    recovery = payload.get("recoveryState") or {}
    recovery.setdefault("retryCount", 0)
    recovery.setdefault("phaseAttempts", {})
    recovery.setdefault("lastRecommendedAction", None)
    recovery.setdefault("failureClass", None)
    payload["recoveryState"] = recovery
    projection = payload.get("projectionState") or {}
    projection.setdefault("planSyncedAt", None)
    projection.setdefault("strategySyncedAt", None)
    projection.setdefault("taskListsSyncedAt", None)
    projection.setdefault("adjudicationSyncedAt", None)
    projection.setdefault("ledgerSyncedAt", None)
    projection.setdefault("ledgerSyncReason", None)
    projection.setdefault("ledgerSyncActor", None)
    projection.setdefault("ledgerVerifiedAt", None)
    projection.setdefault("lastLedgerVerificationState", None)
    payload["projectionState"] = projection
    runtime = payload.get("runtime") or {}
    runtime.setdefault(
        "fleetCapability",
        {
            "status": "unknown",
            "reason": "not-probed",
            "checkedAt": None,
            "probeModel": None,
            "probeModelDisplay": None,
            "cache": None,
            "source": None,
            "checkedBy": None,
            "rawOutputDigest": None,
        },
    )
    runtime.setdefault(
        "fleetDispatch",
        {
            "completedWaves": [],
            "degradedWaves": [],
            "lastDispatchedWave": None,
            "lastOutcome": None,
            "lastOutcomeAt": None,
            "dispatchEvents": [],
        },
    )
    payload["runtime"] = runtime
    payload.setdefault("createdAt", now_iso())
    payload.setdefault("updatedAt", now_iso())
    return payload


def init_scheduler_payload(
    run_id: str,
    prompt: str,
    explicit_model: str | None = None,
    *,
    forced_profile: str | None = None,
    session_model: str | None = None,
    model_control_mode: str | None = None,
    config: dict[str, Any] | None = None,
    availability: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = config or load_model_config()
    if forced_profile and forced_profile not in {"coding", "research", "office"}:
        raise ValueError(f"unsupported forced profile: {forced_profile}")
    profile = forced_profile or profile_from_prompt(prompt)
    language = infer_language(prompt)
    mode = infer_mode(prompt, profile)
    termination = infer_termination_mode(prompt)
    requested_deliverables = infer_requested_deliverables(prompt)
    inferred = infer_completeness(prompt, profile, mode)
    preferred_model = normalize_model_name(explicit_model, cfg) or detect_model_from_text(prompt, cfg)
    normalized_session_model = normalize_model_name(session_model, cfg) or session_model
    if normalized_session_model:
        chain = model_chain(cfg, explicit_model=normalized_session_model, availability=availability)
        selected = normalized_session_model
        control_mode = model_control_mode or "launcher-enforced"
        fallback = [item for item in chain if item != selected]
        reason = "launcher-selected" if control_mode == "launcher-enforced" else "explicit-session-model"
    else:
        chain = model_chain(
            cfg,
            explicit_model=preferred_model,
            prompt_text=prompt,
            command="coding" if profile == "coding" else "run",
            skill="ilongrun-coding" if profile == "coding" else "ilongrun",
            role="mission-governor",
            availability=availability,
        )
        selected = chain[0] if chain else role_model_for("mission-governor", cfg)
        control_mode = model_control_mode or "launcher-enforced"
        fallback = [item for item in chain if item != selected]
        reason = "launcher-selected"
    phases, workstreams = infer_initial_topology(prompt, profile, mode, cfg, requested_deliverables)
    scheduler = ensure_scheduler_defaults(
        {
            "runId": run_id,
            "state": "running",
            "phase": phases[0]["id"] if phases else "phase-strategy",
            "summary": "ILongRun mission initialized",
            "profile": profile,
            "mode": mode,
            "language": language,
            "terminationMode": termination,
            "modelPolicy": cfg.get("defaultPolicy", "ability-first-hybrid"),
            "modelPreference": preferred_model,
            "selectedModel": selected,
            "modelControlMode": control_mode,
            "codingAuditModel": cfg.get("codingAuditModel", "gpt-5.4"),
            "modelAttemptHistory": [{"ts": now_iso(), "model": selected, "reason": reason}],
            "fallbackChain": fallback,
            "deliverables": requested_deliverables,
            "requestedDeliverables": requested_deliverables,
            "phases": phases,
            "workstreams": workstreams,
            "mission": {
                "goal": prompt_stem(prompt),
                "prompt": prompt,
                "profile": profile,
                "mode": mode,
                "terminationMode": termination,
                "requestedDeliverables": requested_deliverables,
                "inferredCompleteness": inferred,
                "constraints": default_constraints(profile, language),
                "successCriteria": default_success_criteria(profile, requested_deliverables),
                "capabilityBoundary": ["local-files", "shell"] + (["public-web"] if profile in {"research", "office"} else []),
                "modelAllocation": {
                    role: role_model_for(role, cfg) for role in role_models(cfg)
                } | {"final-audit": cfg.get("codingAuditModel", "gpt-5.4")},
            },
            "completedWorkstreams": [],
            "activeWorkstreams": [ws["id"] for ws in workstreams if not ws.get("dependencies")],
            "reviews": {
                "required": profile == "coding",
                "finalReviewPath": REVIEW_RELATIVE_PATH,
                "adjudicationPath": ADJUDICATION_RELATIVE_PATH,
                "auditModel": cfg.get("codingAuditModel", "gpt-5.4"),
                "status": "pending" if profile == "coding" else "not-required",
                "pendingMustFixCount": 0,
                "mustFix": [],
                "shouldFix": [],
                "defer": [],
            },
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
    )
    return scheduler


def phase_by_id(scheduler: dict[str, Any], phase_id: str) -> dict[str, Any] | None:
    return next((phase for phase in scheduler.get("phases") or [] if phase.get("id") == phase_id), None)


def wave_by_id(scheduler: dict[str, Any], wave_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for phase in scheduler.get("phases") or []:
        for wave in phase.get("waves") or []:
            if wave.get("id") == wave_id:
                return phase, wave
    return None, None


def workstream_by_id(scheduler: dict[str, Any], workstream_id: str) -> dict[str, Any] | None:
    return next((item for item in scheduler.get("workstreams") or [] if item.get("id") == workstream_id), None)


def workstream_requires_task_list(scheduler: dict[str, Any], workstream: dict[str, Any]) -> bool:
    if str(workstream.get("taskListPath") or "").strip():
        return True
    phase = phase_by_id(scheduler, str(workstream.get("phaseId") or ""))
    return phase_supports_task_list(phase or str(workstream.get("phaseId") or ""))


def sync_workstream_status_files(target: RunTarget, scheduler: dict[str, Any]) -> None:
    for ws in scheduler.get("workstreams") or []:
        ws_dir = workstream_dir(target, ws["id"])
        ensure_dir(ws_dir)
        existing = read_json(workstream_status_path(target, ws["id"]), {})
        projection = workstream_projection_state(target, ws)
        auto_done = projection["claimedDone"] and projection["workProductReady"]
        acceptance_checklist = []
        for item in ws.get("acceptanceChecklist") or []:
            entry = copy.deepcopy(item)
            if str(entry.get("status") or "").lower() == "pending" and auto_done:
                entry["status"] = "done"
            acceptance_checklist.append(entry)
        verify_checklist = []
        for item in ws.get("verifyChecklist") or []:
            entry = copy.deepcopy(item)
            if str(entry.get("status") or "").lower() == "pending" and auto_done:
                entry["status"] = "done"
            verify_checklist.append(entry)
        status_payload = shallow_merge(existing, {
            "id": ws["id"],
            "name": ws.get("name"),
            "index": ws.get("index"),
            "status": ws.get("status"),
            "phaseId": ws.get("phaseId"),
            "waveId": ws.get("waveId"),
            "backend": ws.get("backend"),
            "ownerRole": ws.get("ownerRole"),
            "ownerModel": ws.get("ownerModel"),
            "dependencies": ws.get("dependencies") or [],
            "taskListId": ws.get("taskListId"),
            "taskListPath": ws.get("taskListPath"),
            "resultPath": ws.get("resultPath"),
            "evidencePath": ws.get("evidencePath"),
            "acceptanceChecklist": acceptance_checklist,
            "verifyChecklist": verify_checklist,
            "projection": projection,
            "updatedAt": now_iso(),
        })
        normalized_status = str(status_payload.get("status") or "").lower()
        if normalized_status in COMPLETE_WORKSTREAM_STATUSES and not status_payload.get("completedAt"):
            status_payload["completedAt"] = now_iso()
        if normalized_status in ACTIVE_WORKSTREAM_STATUSES and not status_payload.get("startedAt"):
            status_payload["startedAt"] = now_iso()
        write_json_atomic(workstream_status_path(target, ws["id"]), status_payload)
        brief = build_workstream_brief_markdown(target, scheduler, ws)
        write_text_atomic(workstream_brief_path(target, ws["id"]), brief)
        result_path = workstream_result_path(target, ws["id"])
        evidence_path = workstream_evidence_path(target, ws["id"])
        if not result_path.exists() or not read_text(result_path, "").strip():
            write_text_atomic(result_path, f"# Result\n\nPending result for `{ws['id']}`.\n")
        if not evidence_path.exists() or not read_text(evidence_path, "").strip():
            write_text_atomic(evidence_path, f"# Evidence\n\nPending evidence for `{ws['id']}`.\n")


def build_mission_markdown(target: RunTarget, scheduler: dict[str, Any]) -> str:
    mission = scheduler.get("mission") or {}
    lines = [
        "# ILongRun Mission Contract",
        "",
        "## Run Metadata",
        f"- Run ID: `{target.run_id}`",
        f"- State: `{scheduler.get('state')}`",
        f"- Profile: `{scheduler.get('profile')}`",
        f"- Mode: `{scheduler.get('mode')}`",
        f"- Termination mode: `{scheduler.get('terminationMode')}`",
        f"- Selected model: `{scheduler.get('selectedModel')}`",
        "",
        "## Goal",
        mission.get("goal") or prompt_stem(mission.get("prompt")),
        "",
        "## Requested Deliverables",
    ]
    deliverables = mission.get("requestedDeliverables") or scheduler.get("requestedDeliverables") or []
    if deliverables:
        lines.extend(f"- `{item}`" for item in deliverables)
    else:
        lines.append("- None explicitly requested; rely on inferred completeness and run artifacts.")
    lines.extend(["", "## Constraints"])
    lines.extend(f"- {item}" for item in mission.get("constraints") or [])
    lines.extend(["", "## Success Criteria"])
    lines.extend(f"- {item}" for item in mission.get("successCriteria") or [])
    lines.extend(["", "## Original User Prompt", "```text", (mission.get("prompt") or "").rstrip(), "```", ""])
    return "\n".join(lines)


def build_strategy_markdown(target: RunTarget, scheduler: dict[str, Any]) -> str:
    mission = scheduler.get("mission") or {}
    phases = scheduler.get("phases") or []
    runtime = scheduler.get("runtime") or {}
    fleet_capability = runtime.get("fleetCapability") or {}
    audit_model = (scheduler.get("reviews") or {}).get("auditModel") or scheduler.get("codingAuditModel") or "gpt-5.4"
    lines = [
        "# ILongRun Strategy",
        "",
        MANAGED_STRATEGY_START,
        "## Task Profile",
        f"- Run ID: `{target.run_id}`",
        f"- Goal: {mission.get('goal') or prompt_stem(mission.get('prompt'))}",
        f"- Profile: `{scheduler.get('profile')}`",
        f"- Mode: `{scheduler.get('mode')}`",
        f"- Termination mode: `{scheduler.get('terminationMode')}`",
        "",
        "## Inferred Completeness",
    ]
    lines.extend(f"- {item}" for item in mission.get("inferredCompleteness") or [])
    lines.extend([
        "",
        "## Mode Rationale",
        f"- 当前模式 `{scheduler.get('mode')}` 由 Strategy Synthesizer 结合任务画像、依赖关系、完整度推断和并行潜力生成。",
        "- 主代理负责裁决与重规划，不直接吞掉所有执行工作。",
        "- 除 Direct Lane 外，必须先拆 phase / wave / workstream，再进入执行。",
        "",
        "## Phase/Wave/Workstream Topology",
    ])
    for phase in phases:
        lines.append(f"- Phase `{phase.get('id')}` / {phase.get('name')} / status=`{phase.get('status')}`")
        for wave in phase.get("waves") or []:
            lines.append(f"  - Wave `{wave.get('id')}` / backend=`{wave.get('backend')}` / reason={wave.get('reason')}")
            for ws_id in wave.get("workstreams") or []:
                ws = workstream_by_id(scheduler, ws_id)
                if not ws:
                    continue
                deps = ", ".join(f"`{dep}`" for dep in ws.get("dependencies") or []) or "none"
                lines.append(f"    - `{ws['id']}` {ws.get('name')} / owner=`{ws.get('ownerRole')}`:`{ws.get('ownerModel')}` / deps={deps}")
    lines.extend([
        "",
        "## Backend Decisions",
        f"- Fleet capability: `{fleet_capability.get('status', 'unknown')}` ({fleet_capability.get('reason', 'not-probed')})",
    ])
    if fleet_capability.get("checkedAt") or fleet_capability.get("probeModel"):
        lines.append(
            f"- Fleet probe evidence: checkedAt=`{fleet_capability.get('checkedAt')}` / model=`{fleet_capability.get('probeModelDisplay') or fleet_capability.get('probeModel') or 'unknown'}`"
        )
    fleet_dispatch = runtime.get("fleetDispatch") or {}
    if fleet_dispatch.get("completedWaves") or fleet_dispatch.get("degradedWaves"):
        lines.append(
            f"- Fleet dispatch evidence: completed={fleet_dispatch.get('completedWaves') or []} / degraded={fleet_dispatch.get('degradedWaves') or []}"
        )
    for phase in phases:
        for wave in phase.get("waves") or []:
            lines.append(f"- `{wave.get('id')}` -> `{wave.get('backend')}` / {wave.get('reason')}")
    lines.extend(["", "## Model Allocation"])
    for role, model in (mission.get("modelAllocation") or {}).items():
        lines.append(f"- `{role}` -> `{model}`")
    lines.extend([
        "",
        "## Gates & Blockers",
        f"- Coding review gate: `{scheduler.get('reviews', {}).get('status')}`",
        f"- Adjudication gate: `{scheduler.get('reviews', {}).get('adjudicationStatus')}`",
        f"- Verification: `{scheduler.get('verification', {}).get('state')}`",
    ])
    blockers = list(scheduler.get("verification", {}).get("hardFailures") or [])
    if blockers:
        lines.append("- Current blockers:")
        lines.extend(f"  - {item}" for item in blockers)
    else:
        lines.append("- Current blockers: none")
    lines.extend([
        "",
        "## Recovery / Degrade Path",
        "- Gate 失败先走 Recovery Agent。",
        "- /fleet 不可用、回填失败或独立性条件不满足时，必须降级为 `internal` 并记录原因。",
        f"- finalize 前必须通过最终终审（`{audit_model}`）和主代理 adjudication。",
        MANAGED_STRATEGY_END,
        "",
    ])
    return "\n".join(lines)


def build_plan_markdown(target: RunTarget, scheduler: dict[str, Any]) -> str:
    active_run = read_text(active_run_file(target.base), "").strip()
    drift_notes: list[str] = []
    verification = scheduler.get("verification") or {}
    completion_score = verification.get("completionScore") or {}
    drift_notes.extend(str(item) for item in verification.get("driftFindings") or [])
    if is_run_complete_state(scheduler.get("state")) and active_run == target.run_id:
        drift_notes.append("active-run-id 仍指向已完成 run")
    if is_run_complete_state(scheduler.get("state")) and not completion_path(target).exists():
        drift_notes.append("scheduler 已完成但 COMPLETION.md 缺失")
    lines = [
        "# ILongRun Plan",
        "",
        MANAGED_PLAN_START,
        "## Scheduler Overview",
        f"- Run ID: `{target.run_id}`",
        f"- State: `{scheduler.get('state')}`",
        f"- Active phase: `{scheduler.get('phase')}`",
        f"- Mode: `{scheduler.get('mode')}`",
        f"- Selected model: `{scheduler.get('selectedModel')}`",
        "",
        "## Projection & Ledger Consistency",
        "- Truth source: `scheduler.json` + `workstreams/*/status.json`",
        f"- Task-list projections: `{len(scheduler.get('taskLists') or [])}`",
        f"- plan/strategy/task-lists synced at: `{(scheduler.get('projectionState') or {}).get('taskListsSyncedAt')}`",
        f"- Ledger sync: `{(scheduler.get('projectionState') or {}).get('ledgerSyncedAt')}` / `{(scheduler.get('projectionState') or {}).get('ledgerSyncActor') or 'unknown'}` / `{(scheduler.get('projectionState') or {}).get('ledgerSyncReason') or 'unknown'}`",
        f"- Ledger verification: `{(scheduler.get('projectionState') or {}).get('lastLedgerVerificationState') or 'pending'}` @ `{(scheduler.get('projectionState') or {}).get('ledgerVerifiedAt')}`",
        f"- Active run pointer: `{active_run or 'none'}`",
    ]
    if completion_score:
        lines.extend([
            f"- Completion score: `{completion_score.get('overall', 0)}` / grade=`{completion_score.get('grade', 'N/A')}` / verdict=`{completion_score.get('deliveryVerdict', 'unknown')}`",
            "  - code exists: `{}` / wired: `{}` / tested: `{}` / runtime: `{}`".format(
                (completion_score.get("layers") or {}).get("codeExists", {}).get("score", "n/a"),
                (completion_score.get("layers") or {}).get("wiredIntoEntry", {}).get("score", "n/a"),
                (completion_score.get("layers") or {}).get("tested", {}).get("score", "n/a"),
                (completion_score.get("layers") or {}).get("runtimeValidated", {}).get("score", "n/a"),
            ),
        ])
    if drift_notes:
        lines.extend(["- Drift findings:"] + [f"  - {item}" for item in drift_notes])
    else:
        lines.append("- Drift findings: none")
    lines.extend([
        "",
        "## Phase Progress",
        "| Phase | Status | Required | Waves |",
        "|---|---|---:|---|",
    ])
    for phase in scheduler.get("phases") or []:
        wave_labels = ", ".join(f"`{wave['id']}`:{wave.get('backend')}" for wave in phase.get("waves") or []) or "-"
        lines.append(f"| `{phase['id']}` | `{phase.get('status')}` | {str(bool(phase.get('required'))).lower()} | {wave_labels} |")
    lines.extend(["", "## Workstream Progress", "| Workstream | Status | Phase | Wave | Backend | Owner |", "|---|---|---|---|---|---|"])
    for ws in scheduler.get("workstreams") or []:
        lines.append(f"| `{ws['id']}` {ws.get('name')} | `{ws.get('status')}` | `{ws.get('phaseId')}` | `{ws.get('waveId')}` | `{ws.get('backend')}` | `{ws.get('ownerRole')}` / `{ws.get('ownerModel')}` |")
    lines.extend([
        "",
        "## Task-list Projections",
        "| Task list | Phase | Workstreams |",
        "|---|---|---|",
    ])
    for record in scheduler.get("taskLists") or []:
        ws_labels = ", ".join(f"`{ws_id}`" for ws_id in record.get("workstreamIds") or []) or "-"
        lines.append(f"| `{record.get('path')}` | `{record.get('phaseId')}` | {ws_labels} |")
    lines.extend(["", "## Gates", f"- Coding review gate: `{scheduler.get('reviews', {}).get('status')}`", f"- Verification: `{scheduler.get('verification', {}).get('state')}`", MANAGED_PLAN_END, ""])
    return "\n".join(lines)


def task_list_records_for_scheduler(scheduler: dict[str, Any]) -> list[dict[str, Any]]:
    records = list(scheduler.get("taskLists") or [])
    if not records:
        grouped: dict[str, dict[str, Any]] = {}
        for ws in scheduler.get("workstreams") or []:
            path = ws.get("taskListPath")
            if not path:
                continue
            grouped.setdefault(
                path,
                {
                    "id": ws.get("taskListId") or Path(path).stem,
                    "path": path,
                    "title": ws.get("phaseId") or Path(path).stem,
                    "phaseId": ws.get("phaseId"),
                    "waveIds": [],
                    "workstreamIds": [],
                },
            )
            grouped[path]["workstreamIds"].append(ws["id"])
            if ws.get("waveId") and ws["waveId"] not in grouped[path]["waveIds"]:
                grouped[path]["waveIds"].append(ws["waveId"])
        records = list(grouped.values())
    def sort_key(record: dict[str, Any]) -> tuple[int, str]:
        match = re.search(r"(\d+)$", Path(str(record.get("path") or "")).stem)
        return (int(match.group(1)) if match else 10**9, str(record.get("path") or ""))
    return sorted(records, key=sort_key)


def build_task_list_markdown(target: RunTarget, scheduler: dict[str, Any], task_list: dict[str, Any]) -> str:
    phase = phase_by_id(scheduler, str(task_list.get("phaseId") or ""))
    workstream_ids = list(task_list.get("workstreamIds") or [])
    workstreams = [workstream_by_id(scheduler, ws_id) for ws_id in workstream_ids]
    workstreams = [ws for ws in workstreams if ws]
    completed = 0
    lines = [
        f"# {task_list.get('title') or task_list.get('id')}",
        "",
        f"- Task list id: `{task_list.get('id')}`",
        f"- Projection path: `{task_list.get('path')}`",
        f"- Phase: `{task_list.get('phaseId') or 'unknown'}`",
        f"- Workstreams: `{len(workstreams)}`",
    ]
    if phase:
        lines.append(f"- Phase status: `{phase.get('status')}`")
    wave_ids = list(task_list.get("waveIds") or [])
    if wave_ids:
        lines.append(f"- Waves: {', '.join(f'`{wave_id}`' for wave_id in wave_ids)}")
    lines.extend(["", "## Workstreams"])
    for ws in workstreams:
        projection = workstream_projection_state(target, ws)
        ws_done = projection["claimedDone"] and projection["workProductReady"]
        if ws_done:
            completed += 1
        lines.extend(
            [
                f"### {ws['id']}: {ws.get('name')}",
                f"- Status: `{'complete' if ws_done else ws.get('status')}`",
                f"- Goal: {ws.get('goal') or 'n/a'}",
                f"- Owner: `{ws.get('ownerRole')}` / `{ws.get('ownerModel')}`",
                f"- Backend: `{ws.get('backend')}`",
            ]
        )
        if projection["drift"]:
            lines.append("- ⚠ drift: workstream 声称完成，但 result/evidence/status 尚未形成完整闭环")
        lines.extend(["", "**Acceptance**"])
        acceptance_items = ws.get("acceptanceChecklist") or normalize_checklist_items([], ws.get("acceptance") or [], f"{ws['id']}-acceptance")
        if acceptance_items:
            lines.extend(f"- [{checklist_mark(item)}] {item['text']}" for item in acceptance_items)
        else:
            lines.append("- [ ] No acceptance checklist")
        lines.extend(["", "**Verify**"])
        verify_items = ws.get("verifyChecklist") or normalize_checklist_items([], ws.get("verify") or [], f"{ws['id']}-verify")
        if verify_items:
            lines.extend(f"- [{checklist_mark(item)}] {item['text']}" for item in verify_items)
        else:
            lines.append("- [ ] No verify checklist")
        lines.extend(
            [
                "",
                "**Paths**",
                f"- Brief: `{ws.get('briefPath')}`",
                f"- Result: `{'x' if projection['resultReady'] else ' '}` `{ws.get('resultPath')}`",
                f"- Evidence: `{'x' if projection['evidenceReady'] else ' '}` `{ws.get('evidencePath')}`",
                f"- Status: `{'x' if projection['statusReady'] else ' '}` `{ws.get('statusPath')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Summary",
            f"- Completed with full evidence: `{completed}/{len(workstreams)}`",
            f"- Projection synced at: `{(scheduler.get('projectionState') or {}).get('taskListsSyncedAt')}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_workstream_brief_markdown(target: RunTarget, scheduler: dict[str, Any], ws: dict[str, Any]) -> str:
    lines = [
        f"# Workstream Brief: {ws.get('name')}",
        "",
        f"- ID: `{ws.get('id')}`",
        f"- Status: `{ws.get('status')}`",
        f"- Goal: {ws.get('goal')}",
        f"- Owner: `{ws.get('ownerRole')}` / `{ws.get('ownerModel')}`",
        f"- Backend: `{ws.get('backend')}`",
        "",
        "## Dependencies",
    ]
    deps = ws.get("dependencies") or []
    if deps:
        lines.extend(f"- `{dep}`" for dep in deps)
    else:
        lines.append("- None")
    lines.extend(["", "## Expected Outputs"])
    outputs = ws.get("outputs") or []
    if outputs:
        lines.extend(f"- `{item}`" for item in outputs)
    else:
        lines.append("- Update result/evidence files for this workstream")
    return "\n".join(lines)


def select_adjudication_target(scheduler: dict[str, Any]) -> dict[str, Any] | None:
    workstreams = scheduler.get("workstreams") or []
    incomplete = [ws for ws in workstreams if ws.get("required") and str(ws.get("status") or "").lower() not in COMPLETE_WORKSTREAM_STATUSES]
    if incomplete:
        return incomplete[0]
    execution = [ws for ws in workstreams if ws.get("phaseId") == "phase-execution"]
    if execution:
        return execution[-1]
    return workstreams[-1] if workstreams else None


def build_adjudication_markdown(target: RunTarget, scheduler: dict[str, Any]) -> str:
    reviews = scheduler.get("reviews") or {}
    must_fix = list(reviews.get("mustFix") or [])
    should_fix = list(reviews.get("shouldFix") or [])
    defer = list(reviews.get("defer") or [])
    target_ws = select_adjudication_target(scheduler)
    blocking = bool(must_fix)
    audit_model = reviews.get("auditModel") or scheduler.get("codingAuditModel") or "gpt-5.4"
    assigned_model = audit_model if blocking else (target_ws.get("ownerModel") if target_ws else scheduler.get("selectedModel"))
    next_actions = (
        [
            "把所有 must-fix 返还给指定 workstream，并补齐 result/evidence 佐证。",
            f"修复落地后重新执行最终终审（`{audit_model}`），再判断是否可 finalize。",
        ]
        if blocking
        else [
            "允许进入 finalize，但若后续再有代码变更，必须重新执行最终终审。",
            f"如需处理 should-fix / residual risks，按风险优先级排入后续工作流，并保留 `{audit_model}` 复验入口。",
        ]
    )
    return build_adjudication_report_markdown(
        run_id=target.run_id,
        audit_model=audit_model,
        review_status=str(reviews.get("status") or "pending"),
        must_fix=must_fix,
        should_fix=should_fix,
        defer=defer,
        blocking=blocking,
        decision="return-for-fix" if blocking else "proceed-to-finalize",
        assigned_workstream=target_ws.get("id") if target_ws else "none",
        assigned_role=target_ws.get("ownerRole") if target_ws else "mission-governor",
        assigned_model=assigned_model,
        next_actions=next_actions,
    )


def sync_projections(target: RunTarget, scheduler: dict[str, Any]) -> None:
    scheduler = ensure_scheduler_defaults(scheduler)
    write_text_atomic(mission_path(target), build_mission_markdown(target, scheduler))
    write_text_atomic(strategy_path(target), build_strategy_markdown(target, scheduler))
    write_text_atomic(plan_path(target), build_plan_markdown(target, scheduler))
    for record in task_list_records_for_scheduler(scheduler):
        write_text_atomic(task_list_projection_path(target, str(record.get("path") or "")), build_task_list_markdown(target, scheduler, record))
    if scheduler.get("profile") == "coding":
        write_text_atomic(adjudication_path(target), build_adjudication_markdown(target, scheduler))
    sync_workstream_status_files(target, scheduler)
    projection = scheduler.get("projectionState") or {}
    ts = now_iso()
    projection["planSyncedAt"] = ts
    projection["strategySyncedAt"] = ts
    projection["taskListsSyncedAt"] = ts
    if scheduler.get("profile") == "coding":
        projection["adjudicationSyncedAt"] = ts
    scheduler["projectionState"] = projection


def projected_paths_for_scheduler(target: RunTarget, scheduler: dict[str, Any]) -> list[str]:
    paths = [
        mission_path(target).relative_to(target.run_dir).as_posix(),
        strategy_path(target).relative_to(target.run_dir).as_posix(),
        plan_path(target).relative_to(target.run_dir).as_posix(),
    ]
    paths.extend(
        str(record.get("path") or "")
        for record in task_list_records_for_scheduler(scheduler)
        if str(record.get("path") or "").strip()
    )
    if scheduler.get("profile") == "coding":
        paths.append(adjudication_path(target).relative_to(target.run_dir).as_posix())
    return sorted(dict.fromkeys(paths))


def persist_run_ledger(
    target: RunTarget,
    scheduler: dict[str, Any],
    *,
    reason: str,
    actor: str = "ledger-syncer",
    verify: bool = False,
    finalize_candidate: bool = False,
    clean_active_on_complete: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    sched = ensure_scheduler_defaults(copy.deepcopy(scheduler))
    sched["updatedAt"] = now_iso()
    projection = sched.get("projectionState") or {}
    projection["ledgerSyncedAt"] = sched["updatedAt"]
    projection["ledgerSyncReason"] = reason
    projection["ledgerSyncActor"] = actor
    sched["projectionState"] = projection

    active_cleared = False
    if clean_active_on_complete and is_run_complete_state(sched.get("state")):
        active_cleared = clear_active_run(target.base, target.run_id)

    sync_projections(target, sched)
    verification_result: dict[str, Any] | None = None
    if verify:
        verification_result = verify_scheduler(target, sched, finalize_candidate=finalize_candidate)
        sched["verification"] = {
            "state": "passed" if verification_result.get("ok") else "failed",
            "hardFailures": verification_result.get("hardFailures", []),
            "softWarnings": verification_result.get("softWarnings", []),
            "driftFindings": verification_result.get("driftFindings", []),
            "recommendedAction": verification_result.get("recommendedAction"),
            "failureClass": verification_result.get("failureClass"),
            "lastVerifiedAt": now_iso(),
            "completionScore": verification_result.get("completionScore"),
        }
        projection = sched.get("projectionState") or {}
        projection["ledgerVerifiedAt"] = sched["verification"]["lastVerifiedAt"]
        projection["lastLedgerVerificationState"] = sched["verification"]["state"]
        sched["projectionState"] = projection
        sync_projections(target, sched)

    write_json_atomic(scheduler_path(target), sched)
    append_jsonl(
        projection_log_path(target),
        {
            "ts": now_iso(),
            "source": actor,
            "event": "projection-sync",
            "payload": {
                "reason": reason,
                "state": sched.get("state"),
                "phase": sched.get("phase"),
                "activeCleared": active_cleared,
                "verificationState": (sched.get("verification") or {}).get("state"),
                "hardFailureCount": len((sched.get("verification") or {}).get("hardFailures") or []),
                "driftCount": len((sched.get("verification") or {}).get("driftFindings") or []),
                "taskListCount": len(sched.get("taskLists") or []),
                "projectedPaths": projected_paths_for_scheduler(target, sched),
            },
        },
    )
    append_jsonl(
        journal_path(target),
        {
            "ts": now_iso(),
            "source": actor,
            "event": "ledger-sync",
            "payload": {
                "reason": reason,
                "state": sched.get("state"),
                "phase": sched.get("phase"),
                "activeCleared": active_cleared,
                "verificationState": (sched.get("verification") or {}).get("state"),
            },
        },
    )
    return sched, verification_result


def ensure_run_layout(target: RunTarget) -> None:
    ensure_dir(target.run_dir)
    ensure_dir(target.run_dir / "workstreams")
    ensure_dir(target.run_dir / "reviews")
    ensure_dir(target.base / "state")
    ensure_dir(legacy_imports_dir(target))
    for path in [journal_path(target), projection_log_path(target)]:
        ensure_dir(path.parent)
        path.touch(exist_ok=True)


def parse_review_sections(text: str) -> dict[str, list[str]]:
    sections = {"mustFix": [], "shouldFix": [], "defer": []}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if line.startswith("#"):
            current = None
            if re.match(r"^#+\s*must[- ]fix", lowered):
                current = "mustFix"
            elif re.match(r"^#+\s*(suggested fixes|should[- ]fix)", lowered):
                current = "shouldFix"
            elif re.match(r"^#+\s*(residual risks|defer)", lowered):
                current = "defer"
            continue
        item = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line)
        if item and current:
            value = item.group(1).strip()
            normalized = re.sub(r"[.。!！]+$", "", value).strip().lower()
            if normalized not in {"none", "无", "n/a", "na"}:
                sections[current].append(value)
    return sections


def runnable_fleet_waves(scheduler: dict[str, Any]) -> list[dict[str, Any]]:
    runnable: list[dict[str, Any]] = []
    for phase in scheduler.get("phases") or []:
        for wave in phase.get("waves") or []:
            if wave.get("backend") != "fleet":
                continue
            ws_ids = wave.get("workstreams") or []
            if not ws_ids:
                continue
            ws_items = [workstream_by_id(scheduler, ws_id) for ws_id in ws_ids]
            if any(item is None for item in ws_items):
                continue
            pending = [ws for ws in ws_items if str(ws.get("status") or "").lower() not in COMPLETE_WORKSTREAM_STATUSES]
            if not pending:
                continue
            deps_ready = True
            for ws in pending:
                for dep in ws.get("dependencies") or []:
                    dep_ws = workstream_by_id(scheduler, dep)
                    if not dep_ws or str(dep_ws.get("status") or "").lower() not in COMPLETE_WORKSTREAM_STATUSES:
                        deps_ready = False
                        break
                if not deps_ready:
                    break
            if deps_ready:
                runnable.append({"phase": phase, "wave": wave, "workstreams": pending})
    return runnable


def fleet_wave_ids(scheduler: dict[str, Any]) -> list[str]:
    wave_ids: list[str] = []
    for phase in scheduler.get("phases") or []:
        for wave in phase.get("waves") or []:
            if "fleet" in str(wave.get("backend") or "").lower():
                wave_id = str(wave.get("id") or "").strip()
                if wave_id:
                    wave_ids.append(wave_id)
    return wave_ids


def scheduler_uses_fleet_runtime(scheduler: dict[str, Any]) -> bool:
    mode = str(scheduler.get("mode") or "").lower()
    if "fleet" in mode:
        return True
    runtime = scheduler.get("runtime") or {}
    fleet_dispatch = runtime.get("fleetDispatch") or {}
    if fleet_wave_ids(scheduler):
        return True
    if fleet_dispatch.get("completedWaves") or fleet_dispatch.get("degradedWaves") or fleet_dispatch.get("dispatchEvents"):
        return True
    return False


def completion_score_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def compute_completion_score(
    target: RunTarget,
    scheduler: dict[str, Any],
    *,
    hard_failures: list[str],
    drift_findings: list[str],
    delivery_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    required_workstreams = [ws for ws in scheduler.get("workstreams") or [] if ws.get("required", True)]
    denominator = max(len(required_workstreams), 1)
    result_ready = 0
    evidence_ready = 0
    for ws in required_workstreams:
        result_path = target.run_dir / str(ws.get("resultPath") or "")
        evidence_path = target.run_dir / str(ws.get("evidencePath") or "")
        if file_is_nonempty(result_path):
            result_ready += 1
        if file_is_nonempty(evidence_path):
            evidence_ready += 1

    code_exists_score = round(result_ready * 100 / denominator)
    tested_score = round(evidence_ready * 100 / denominator)

    wiring_supported = bool(delivery_audit and delivery_audit.get("supported"))
    if wiring_supported:
        findings = delivery_audit.get("findings") or []
        high = sum(1 for item in findings if item.get("severity") == "high")
        medium = sum(1 for item in findings if item.get("severity") == "medium")
        wiring_score = max(0, 100 - (high * 12) - (medium * 4))
    else:
        high = 0
        medium = 0
        wiring_score = 100

    runtime_checks: list[tuple[str, bool]] = [
        ("noHardFailures", not hard_failures),
        ("noDriftFindings", not drift_findings),
    ]
    if is_run_complete_state(scheduler.get("state")):
        runtime_checks.append(("completionFilePresent", file_is_nonempty(completion_path(target))))
    if scheduler.get("profile") == "coding":
        runtime_checks.append(("finalReviewPresent", file_is_nonempty(final_review_path(target))))
        runtime_checks.append(("adjudicationPresent", file_is_nonempty(adjudication_path(target))))
    if scheduler_uses_fleet_runtime(scheduler):
        runtime = scheduler.get("runtime") or {}
        capability = runtime.get("fleetCapability") or {}
        dispatch = runtime.get("fleetDispatch") or {}
        dispatch_events = list(dispatch.get("dispatchEvents") or [])
        runtime_checks.append((
            "fleetProbeObserved",
            str(capability.get("status") or "") != "unknown",
        ))
        runtime_checks.append((
            "fleetProbeEvidence",
            bool(capability.get("checkedAt") and capability.get("probeModel")),
        ))
        if is_run_complete_state(scheduler.get("state")) or dispatch.get("completedWaves") or dispatch.get("degradedWaves"):
            runtime_checks.append((
                "fleetDispatchEvidence",
                bool(dispatch_events or dispatch.get("completedWaves") or dispatch.get("degradedWaves")),
            ))
    runtime_validated_score = round(sum(1 for _, ok in runtime_checks if ok) * 100 / max(len(runtime_checks), 1))

    overall_components = [code_exists_score, wiring_score, tested_score, runtime_validated_score]
    overall = round(sum(overall_components) / len(overall_components))
    if hard_failures:
        delivery_verdict = "blocked"
    elif wiring_score < 60:
        delivery_verdict = "implemented-not-wired"
    elif runtime_validated_score < 70:
        delivery_verdict = "implemented-not-validated"
    elif overall >= 85:
        delivery_verdict = "prototype-ready"
    else:
        delivery_verdict = "prototype-risk"

    return {
        "overall": overall,
        "grade": completion_score_grade(overall),
        "deliveryVerdict": delivery_verdict,
        "inference": "evidence-based",
        "layers": {
            "codeExists": {
                "score": code_exists_score,
                "numerator": result_ready,
                "denominator": denominator,
                "summary": f"{result_ready}/{denominator} required workstreams have non-empty result.md",
            },
            "wiredIntoEntry": {
                "score": wiring_score,
                "highRiskFindings": high,
                "mediumRiskFindings": medium,
                "supported": wiring_supported,
                "summary": "delivery audit based on runtime entry reachability",
            },
            "tested": {
                "score": tested_score,
                "numerator": evidence_ready,
                "denominator": denominator,
                "summary": f"{evidence_ready}/{denominator} required workstreams have non-empty evidence.md",
            },
            "runtimeValidated": {
                "score": runtime_validated_score,
                "checks": [{"name": name, "ok": ok} for name, ok in runtime_checks],
                "summary": "ledger/runtime gate validation derived from verify/finalize prerequisites",
            },
        },
    }


def reconcile_scheduler(target: RunTarget, scheduler: dict[str, Any] | None = None) -> dict[str, Any]:
    merge_legacy_run_dir(target)
    sched = ensure_scheduler_defaults(copy.deepcopy(scheduler or read_json(scheduler_path(target), {})))
    sched["state"] = normalize_run_state(sched.get("state"))
    completed: list[str] = []
    active: list[str] = []
    for ws in sched.get("workstreams") or []:
        ws_state = read_json(workstream_status_path(target, ws["id"]), {})
        result_text = read_text(workstream_result_path(target, ws["id"]), "").strip()
        evidence_text = read_text(workstream_evidence_path(target, ws["id"]), "").strip()
        status = ws_state.get("status") or ws.get("status") or "pending"
        projection = workstream_projection_state(target, {**ws, "status": status})
        acceptance_checklist = normalize_checklist_items(
            ws_state.get("acceptanceChecklist"),
            [entry.get("text") for entry in ws.get("acceptanceChecklist") or []],
            f"{ws['id']}-acceptance",
        )
        verify_checklist = normalize_checklist_items(
            ws_state.get("verifyChecklist"),
            [entry.get("text") for entry in ws.get("verifyChecklist") or []],
            f"{ws['id']}-verify",
        )
        if projection["claimedDone"] and projection["workProductReady"]:
            for item in acceptance_checklist + verify_checklist:
                if str(item.get("status") or "").lower() == "pending":
                    item["status"] = "done"
        normalized_status = str(status or "").lower()
        if normalized_status in COMPLETE_WORKSTREAM_STATUSES:
            completed.append(ws["id"])
        elif normalized_status in ACTIVE_WORKSTREAM_STATUSES:
            active.append(ws["id"])
        elif result_text and evidence_text and result_text != f"# Result\n\nPending result for `{ws['id']}`." and evidence_text != f"# Evidence\n\nPending evidence for `{ws['id']}`.":
            status = "complete"
            completed.append(ws["id"])
        ws["status"] = status
        ws["acceptanceChecklist"] = acceptance_checklist
        ws["verifyChecklist"] = verify_checklist
        ws["acceptance"] = [entry["text"] for entry in acceptance_checklist]
        ws["verify"] = [entry["text"] for entry in verify_checklist]
        ws["lastUpdatedAt"] = now_iso()
    sched["completedWorkstreams"] = completed
    sched["activeWorkstreams"] = [item for item in active if item not in completed]

    for phase in sched.get("phases") or []:
        phase_ws_ids = [ws_id for wave in phase.get("waves") or [] for ws_id in wave.get("workstreams") or []]
        if not phase_ws_ids:
            phase["status"] = "complete" if phase["id"] == "phase-strategy" and sched.get("state") != "running" else phase.get("status", "pending")
        elif all(workstream_by_id(sched, ws_id) and str(workstream_by_id(sched, ws_id).get("status") or "").lower() in COMPLETE_WORKSTREAM_STATUSES for ws_id in phase_ws_ids):
            phase["status"] = "complete"
        elif any(workstream_by_id(sched, ws_id) and str(workstream_by_id(sched, ws_id).get("status") or "").lower() in ACTIVE_WORKSTREAM_STATUSES for ws_id in phase_ws_ids):
            phase["status"] = "running"
        else:
            phase["status"] = "pending"
        for wave in phase.get("waves") or []:
            wave_ws_ids = wave.get("workstreams") or []
            if not wave_ws_ids:
                wave["status"] = "complete" if phase["status"] == "complete" else wave.get("status", "pending")
            elif all(workstream_by_id(sched, ws_id) and str(workstream_by_id(sched, ws_id).get("status") or "").lower() in COMPLETE_WORKSTREAM_STATUSES for ws_id in wave_ws_ids):
                wave["status"] = "complete"
            elif any(workstream_by_id(sched, ws_id) and str(workstream_by_id(sched, ws_id).get("status") or "").lower() in ACTIVE_WORKSTREAM_STATUSES for ws_id in wave_ws_ids):
                wave["status"] = "running"
            else:
                wave["status"] = "pending"

    phase_candidates = [phase for phase in sched.get("phases") or [] if phase.get("status") != "complete"]
    if phase_candidates:
        sched["phase"] = phase_candidates[0]["id"]
    elif sched.get("state") == "running":
        sched["phase"] = "phase-finalize"
    elif is_run_complete_state(sched.get("state")):
        sched["phase"] = "phase-finalize"

    if sched.get("profile") == "coding":
        review_path = final_review_path(target)
        if review_path.exists() and review_path.stat().st_size > 0:
            sections = parse_review_sections(read_text(review_path, ""))
            sched.setdefault("reviews", {})["mustFix"] = sections["mustFix"]
            sched.setdefault("reviews", {})["shouldFix"] = sections["shouldFix"]
            sched.setdefault("reviews", {})["defer"] = sections["defer"]
            sched["reviews"]["pendingMustFixCount"] = len(sections["mustFix"])
            sched["reviews"]["status"] = "failed" if sections["mustFix"] else "passed"
            adjudication_exists = adjudication_path(target).exists() and adjudication_path(target).stat().st_size > 0
            sched["reviews"]["adjudicationStatus"] = "written" if adjudication_exists else "pending"
            if sections["mustFix"] and normalize_run_state(sched.get("state")) in {"running", "blocked", "complete"}:
                sched["state"] = "blocked"
                sched["phase"] = "phase-audit"
        else:
            sched.setdefault("reviews", {})["status"] = "pending"
            sched["reviews"]["pendingMustFixCount"] = 0
            sched["reviews"]["mustFix"] = []
            sched["reviews"]["shouldFix"] = []
            sched["reviews"]["defer"] = []
            sched["reviews"]["adjudicationStatus"] = "pending"

    sched["updatedAt"] = now_iso()
    return sched


def verify_scheduler(target: RunTarget, scheduler: dict[str, Any] | None = None, *, finalize_candidate: bool = False) -> dict[str, Any]:
    raw_scheduler = copy.deepcopy(scheduler) if scheduler is not None else read_json(scheduler_path(target), {})
    sched = reconcile_scheduler(target, raw_scheduler)
    hard_failures: list[str] = []
    soft_warnings: list[str] = []
    drift_findings: list[str] = []
    delivery_audit: dict[str, Any] | None = None
    if legacy_run_dir(target).exists():
        drift_findings.append("legacy root run directory still exists outside runs/<run-id>")
    if not mission_path(target).exists():
        hard_failures.append("mission.md is missing")
    if not strategy_path(target).exists():
        hard_failures.append("strategy.md is missing")
    if not plan_path(target).exists():
        hard_failures.append("plan.md is missing")
    mission_text = read_text(mission_path(target), "")
    plan_text = read_text(plan_path(target), "")
    strategy_text = read_text(strategy_path(target), "")
    if MANAGED_PLAN_START not in plan_text or MANAGED_PLAN_END not in plan_text:
        drift_findings.append("plan.md is missing the managed ilongrun block")
    if MANAGED_STRATEGY_START not in strategy_text or MANAGED_STRATEGY_END not in strategy_text:
        drift_findings.append("strategy.md is missing the managed ilongrun block")
    mission_state = re.search(r"-\s+State:\s+`([^`]+)`", mission_text)
    if mission_state and normalize_run_state(mission_state.group(1)) != normalize_run_state(sched.get("state")):
        drift_findings.append(f"mission.md state drift: {mission_state.group(1)} != {sched.get('state')}")
    plan_state = re.search(r"-\s+State:\s+`([^`]+)`", plan_text)
    if plan_state and normalize_run_state(plan_state.group(1)) != normalize_run_state(sched.get("state")):
        drift_findings.append(f"plan.md state drift: {plan_state.group(1)} != {sched.get('state')}")
    plan_phase = re.search(r"-\s+Active phase:\s+`([^`]+)`", plan_text)
    if plan_phase and str(plan_phase.group(1)).strip() != str(sched.get("phase") or "").strip():
        drift_findings.append(f"plan.md phase drift: {plan_phase.group(1)} != {sched.get('phase')}")
    workstreams = sched.get("workstreams") or []
    if not workstreams:
        hard_failures.append("scheduler has no workstreams")
    if not (sched.get("taskLists") or []):
        drift_findings.append("scheduler is missing explicit taskLists mapping")
    elif not (isinstance(raw_scheduler.get("taskLists"), list) and raw_scheduler.get("taskLists")):
        drift_findings.append("scheduler taskLists[] mapping was inferred, not explicitly persisted")
    for ws in workstreams:
        task_list_rel = str(ws.get("taskListPath") or "").strip()
        requires_task_list = workstream_requires_task_list(sched, ws)
        if requires_task_list and not task_list_rel:
            drift_findings.append(f"workstream missing taskListPath: {ws['id']}")
        elif task_list_rel and not task_list_projection_path(target, task_list_rel).exists():
            hard_failures.append(f"missing {task_list_rel}")
        status_file = workstream_status_path(target, ws["id"])
        if not status_file.exists():
            hard_failures.append(f"missing {ws['statusPath']}")
        else:
            status_payload = read_json(status_file, {})
            started_at = status_payload.get("startedAt")
            completed_at = status_payload.get("completedAt")
            started_dt = parse_iso(started_at) if started_at else None
            completed_dt = parse_iso(completed_at) if completed_at else None
            if started_at and started_dt is None:
                drift_findings.append(f"invalid startedAt timestamp: {ws['id']} -> {started_at}")
            if completed_at and completed_dt is None:
                drift_findings.append(f"invalid completedAt timestamp: {ws['id']} -> {completed_at}")
            if started_dt and completed_dt and completed_dt < started_dt:
                drift_findings.append(f"completedAt earlier than startedAt: {ws['id']}")
        if ws.get("required") and str(ws.get("status") or "").lower() not in COMPLETE_WORKSTREAM_STATUSES and is_run_complete_state(sched.get("state")):
            hard_failures.append(f"required workstream not complete: {ws['id']}")
        projection = workstream_projection_state(target, ws)
        if projection["drift"]:
            drift_findings.append(f"workstream claims complete without full evidence: {ws['id']}")
    deliverables = [str(item) for item in sched.get("deliverables") or [] if item]
    existing_deliverables: list[str] = []
    for item in deliverables:
        path = target.run_dir / item if str(item).startswith("workstreams/") or str(item).startswith("reviews/") else target.workspace / item
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            existing_deliverables.append(str(path))
        else:
            hard_failures.append(f"missing deliverable: {item}")
    if scheduler_uses_fleet_runtime(sched):
        runtime = sched.get("runtime") or {}
        capability = runtime.get("fleetCapability") or {}
        dispatch = runtime.get("fleetDispatch") or {}
        dispatch_events = list(dispatch.get("dispatchEvents") or [])
        known_wave_ids = {
            str(wave.get("id") or "").strip()
            for phase in sched.get("phases") or []
            for wave in phase.get("waves") or []
            if str(wave.get("id") or "").strip()
        }
        if str(capability.get("status") or "") == "unknown":
            soft_warnings.append("fleet capability status is still unknown; runtime probe evidence is incomplete")
        if str(capability.get("status") or "") != "unknown" and not capability.get("checkedAt"):
            drift_findings.append("fleet capability checkedAt is missing")
        if str(capability.get("status") or "") != "unknown" and not capability.get("probeModel"):
            soft_warnings.append("fleet capability probeModel is missing")
        for key in ("completedWaves", "degradedWaves"):
            for wave_id in dispatch.get(key) or []:
                if str(wave_id) not in known_wave_ids:
                    drift_findings.append(f"fleet dispatch references unknown wave: {wave_id}")
        completed_evidence: set[str] = set()
        degraded_evidence: set[str] = set()
        for event in dispatch_events:
            wave_id = str(event.get("waveId") or "").strip()
            outcome = str(event.get("outcome") or "").strip()
            observed_at = event.get("observedAt")
            if not wave_id:
                drift_findings.append("fleet dispatch event missing waveId")
                continue
            if wave_id not in known_wave_ids:
                drift_findings.append(f"fleet dispatch event references unknown wave: {wave_id}")
            if not outcome:
                drift_findings.append(f"fleet dispatch event missing outcome: {wave_id}")
            if not observed_at:
                drift_findings.append(f"fleet dispatch event missing observedAt: {wave_id}")
            elif parse_iso(str(observed_at)) is None:
                drift_findings.append(f"fleet dispatch event has invalid observedAt: {wave_id} -> {observed_at}")
            if outcome == "completed":
                completed_evidence.add(wave_id)
            if outcome == "degraded":
                degraded_evidence.add(wave_id)
        missing_completed = [wave_id for wave_id in dispatch.get("completedWaves") or [] if str(wave_id) not in completed_evidence]
        missing_degraded = [wave_id for wave_id in dispatch.get("degradedWaves") or [] if str(wave_id) not in degraded_evidence]
        if missing_completed or missing_degraded:
            soft_warnings.append("fleet dispatch summary exists without matching detailed dispatchEvents evidence")
        if is_run_complete_state(sched.get("state")) and known_wave_ids and fleet_wave_ids(sched) and not (dispatch_events or dispatch.get("completedWaves") or dispatch.get("degradedWaves")):
            soft_warnings.append("fleet-involved run completed without any fleet dispatch evidence")
    if sched.get("profile") == "coding":
        delivery_audit = scan_workspace_delivery_gaps(target.workspace)
        write_text_atomic(delivery_audit_path(target), render_delivery_audit_markdown(delivery_audit))
        high_confidence = [item for item in delivery_audit.get("findings") or [] if item.get("severity") == "high"]
        medium_confidence = [item for item in delivery_audit.get("findings") or [] if item.get("severity") == "medium"]
        if high_confidence:
            drift_findings.append(
                f"delivery audit flagged {len(high_confidence)} high-confidence fake-completion risks (see {(sched.get('reviews') or {}).get('deliveryAuditPath') or DELIVERY_AUDIT_RELATIVE_PATH})"
            )
            for item in high_confidence[:3]:
                drift_findings.append(f"delivery audit: {item.get('summary')}")
        elif medium_confidence:
            soft_warnings.append(
                f"delivery audit flagged {len(medium_confidence)} medium-confidence risks (see {(sched.get('reviews') or {}).get('deliveryAuditPath') or DELIVERY_AUDIT_RELATIVE_PATH})"
            )
        review_exists = final_review_path(target).exists() and final_review_path(target).stat().st_size > 0
        adjudication_exists = adjudication_path(target).exists() and adjudication_path(target).stat().st_size > 0
        audit_model = (sched.get("reviews") or {}).get("auditModel") or sched.get("codingAuditModel") or "gpt-5.4"
        if not review_exists:
            hard_failures.append("reviews/gpt54-final-review.md is missing")
        if not adjudication_exists:
            hard_failures.append("reviews/adjudication.md is missing")
        pending = int((sched.get("reviews") or {}).get("pendingMustFixCount") or 0)
        if pending > 0:
            hard_failures.append(f"final audit ({audit_model}) still has unresolved must-fix items: {pending}")
    if is_run_complete_state(sched.get("state")) and sched.get("activeWorkstreams"):
        drift_findings.append("scheduler is finalized but activeWorkstreams is not empty")
    if is_run_complete_state(sched.get("state")) and read_text(active_run_file(target.base), "").strip() == target.run_id:
        drift_findings.append("active-run-id still points at a completed run")
    if is_run_complete_state(sched.get("state")) and not completion_path(target).exists() and not finalize_candidate:
        drift_findings.append("scheduler is complete but COMPLETION.md is missing")
    completion_score = compute_completion_score(
        target,
        sched,
        hard_failures=hard_failures,
        drift_findings=drift_findings,
        delivery_audit=delivery_audit,
    )
    failure_class, recommended_action = classify_failure(hard_failures, drift_findings, last_error=((sched.get("lastError") or {}).get("message") if isinstance(sched.get("lastError"), dict) else str(sched.get("lastError") or "")))
    ok = not hard_failures and not drift_findings
    return {
        "ok": ok,
        "deliverables": existing_deliverables,
        "findings": [*hard_failures, *soft_warnings, *drift_findings],
        "hardFailures": hard_failures,
        "softWarnings": soft_warnings,
        "driftFindings": drift_findings,
        "recommendedAction": recommended_action,
        "failureClass": failure_class,
        "scheduler": sched,
        "deliveryAudit": delivery_audit,
        "completionScore": completion_score,
    }
