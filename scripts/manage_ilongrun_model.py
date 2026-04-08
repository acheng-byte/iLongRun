#!/usr/bin/env python3
from __future__ import annotations

import argparse
import curses
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_shared import (  # noqa: E402
    account_fingerprint,
    current_copilot_identity,
    default_model_config,
    display_model_name,
    fixed_review_role_models,
    load_model_config,
    normalize_model_name,
    primary_model_role_names,
    read_json,
    read_jsonc,
    read_model_availability,
    validate_model_config,
    write_text_atomic,
)
from _ilongrun_terminal_theme import (  # noqa: E402
    BOLD,
    PALETTE,
    ad_box,
    board_line,
    board_title,
    detail_line,
    left_border,
    open_bottom,
    open_top,
    paint,
    section_heading,
    section_rule,
)


ILONGRUN_HOME = Path(os.environ.get("ILONGRUN_HOME", str(Path.home() / ".copilot-ilongrun")))
INSTALL_MODEL_CONFIG = ILONGRUN_HOME / "config" / "model-policy.jsonc"
INSTALL_MODEL_CONFIG_LEGACY = INSTALL_MODEL_CONFIG.with_suffix(".json")
MODEL_AVAILABILITY_CACHE = ILONGRUN_HOME / "config" / "model-availability.json"
PRIMARY_COMMAND_KEYS = ("run", "coding")
PRIMARY_SKILL_KEYS = ("ilongrun", "ilongrun-coding")
FIXED_REVIEW_ROLES = fixed_review_role_models()
PRIMARY_ROLE_NAMES = primary_model_role_names()
TUI_SCOPE_ORDER = ("global", "run", "coding")
TUI_SCOPE_LABELS = {
    "global": "全局默认",
    "run": "run模型",
    "coding": "coding模型",
}
TUI_SCOPE_DESCRIPTIONS = {
    "global": "选择后会同时更新 ilongrun 与 ilongrun-coding 的默认主执行模型。",
    "run": "选择后只会更新 ilongrun 的默认主执行模型。",
    "coding": "选择后只会更新 ilongrun-coding 的默认主执行模型。",
}
STATUS_LABELS = {
    "available": "可用",
    "unavailable": "不可用",
    "unknown": "未确认",
}
STATUS_ICONS = {
    "available": "✓",
    "unavailable": "✗",
    "unknown": "?",
}
MODE_LABELS = {
    "show": ("👁️ 查看模板", "bright"),
    "set": ("✏️ 已更新模板", "ok"),
    "reset": ("♻️ 已恢复默认", "warn"),
}
TARGET_SCOPE_LABELS = {
    "install": "安装态配置",
    "repo": "仓库配置",
}
TARGET_ACTION_LABELS = {
    "show": "查看",
    "set": "写入",
    "reset": "恢复",
}


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


def apply_run_model(policy: dict[str, Any], slug: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(policy))
    command_defaults = dict(updated.get("commandDefaults") or {})
    command_defaults["run"] = slug
    updated["commandDefaults"] = command_defaults

    skill_defaults = dict(updated.get("skillDefaults") or {})
    skill_defaults["ilongrun"] = slug
    updated["skillDefaults"] = skill_defaults
    return updated


def apply_coding_model(policy: dict[str, Any], slug: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(policy))
    command_defaults = dict(updated.get("commandDefaults") or {})
    command_defaults["coding"] = slug
    updated["commandDefaults"] = command_defaults

    skill_defaults = dict(updated.get("skillDefaults") or {})
    skill_defaults["ilongrun-coding"] = slug
    updated["skillDefaults"] = skill_defaults
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


def apply_model_for_scope(policy: dict[str, Any], slug: str, write_scope: str) -> dict[str, Any]:
    if write_scope == "run":
        return apply_run_model(policy, slug)
    if write_scope == "coding":
        return apply_coding_model(policy, slug)
    return apply_primary_model(policy, slug)


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


def candidate_slugs(config: dict[str, Any], current: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    ordered.extend((config.get("displayNames") or {}).keys())
    ordered.extend(config.get("fallback") or [])
    ordered.extend(
        [
            current.get("runModel"),
            current.get("codingModel"),
            (default_model_config().get("commandDefaults") or {}).get("run"),
            (default_model_config().get("commandDefaults") or {}).get("coding"),
        ]
    )
    deduped: list[str] = []
    for item in ordered:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def availability_lookup(config: dict[str, Any], slugs: list[str]) -> dict[str, dict[str, Any]]:
    cache = read_model_availability(MODEL_AVAILABILITY_CACHE)
    identity = current_copilot_identity()
    fingerprint = account_fingerprint(identity)
    account_models = (((cache.get("accounts") or {}).get(fingerprint) or {}).get("models") or {})
    lookup: dict[str, dict[str, Any]] = {}
    for slug in slugs:
        entry = dict(account_models.get(slug) or {})
        status = entry.get("status") or "unknown"
        reason = entry.get("reason") or ("cache-miss" if not entry else "cached")
        lookup[slug] = {
            "status": status,
            "reason": reason,
            "checkedAt": entry.get("checkedAt"),
            "displayName": entry.get("displayName") or display_model_name(slug, config),
        }
    return lookup


def refresh_model_cache(config_path: Path) -> dict[str, Any]:
    helper = SCRIPT_DIR / "probe_models.py"
    if not helper.exists():
        return {
            "status": "skipped",
            "message": "未刷新：probe_models.py 缺失",
            "cache": str(MODEL_AVAILABILITY_CACHE),
            "models": {},
        }
    copilot_bin = shutil.which(os.environ.get("COPILOT_BIN", "copilot"))
    if not copilot_bin:
        return {
            "status": "skipped",
            "message": "未刷新：未检测到 copilot CLI",
            "cache": str(MODEL_AVAILABILITY_CACHE),
            "models": {},
        }
    cmd = [
        sys.executable,
        str(helper),
        "--copilot-bin",
        copilot_bin,
        "--config",
        str(config_path),
        "--cache",
        str(MODEL_AVAILABILITY_CACHE),
        "--scope",
        "defaults",
        "--refresh",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    payload: dict[str, Any]
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    models = payload.get("models") or {}
    available = sum(1 for item in models.values() if item.get("status") == "available")
    unavailable = sum(1 for item in models.values() if item.get("status") == "unavailable")
    unknown = sum(1 for item in models.values() if item.get("status") == "unknown")
    if proc.returncode == 0 and payload.get("ok"):
        if unavailable == 0 and unknown == 0:
            message = f"已刷新模型缓存：{available} 个默认模型可用"
        elif unavailable > 0:
            message = f"已刷新模型缓存：{available} 个可用 / {unavailable} 个不可用"
        else:
            message = f"已刷新模型缓存：{available} 个可用 / {unknown} 个待确认"
        return {
            "status": "refreshed",
            "message": message,
            "cache": payload.get("cache") or str(MODEL_AVAILABILITY_CACHE),
            "models": models,
        }
    details = payload.get("errors") or payload.get("details") or proc.stderr.strip() or "probe-command-failed"
    return {
        "status": "failed",
        "message": f"刷新模型缓存失败：{details}",
        "cache": payload.get("cache") or str(MODEL_AVAILABILITY_CACHE),
        "models": models,
    }


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, STATUS_LABELS["unknown"])


def status_icon(status: str) -> str:
    return STATUS_ICONS.get(status, STATUS_ICONS["unknown"])


def build_picker_items(config: dict[str, Any], current: dict[str, Any], availability: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    run_slug = current.get("runModel")
    coding_slug = current.get("codingModel")
    for slug in candidate_slugs(config, current):
        item = dict(availability.get(slug) or {})
        badges: list[str] = []
        if slug == run_slug:
            badges.append("当前 run")
        if slug == coding_slug:
            badges.append("当前 coding")
        items.append(
            {
                "slug": slug,
                "displayName": display_model_name(slug, config),
                "status": item.get("status") or "unknown",
                "reason": item.get("reason") or "cache-miss",
                "badges": "、".join(badges),
            }
        )
    return items


def filter_picker_items(items: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    token = query.strip().lower()
    if not token:
        return items
    visible: list[dict[str, str]] = []
    for item in items:
        haystacks = [
            item["slug"].lower(),
            item["displayName"].lower(),
            item.get("badges", "").lower(),
            status_label(item.get("status", "unknown")).lower(),
        ]
        if any(token in hay for hay in haystacks):
            visible.append(item)
    return visible


def ellipsize(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def picker_line(item: dict[str, str], width: int) -> str:
    badge = f" [{item['badges']}]" if item.get("badges") else ""
    summary = f"{status_icon(item['status'])} {item['displayName']}{badge} · {status_label(item['status'])} · {item['slug']}"
    return ellipsize(summary, width)


def safe_addnstr(stdscr: Any, row: int, col: int, text: str, width: int, attr: int = 0) -> None:
    height, screen_width = stdscr.getmaxyx()
    if row < 0 or col < 0 or row >= height or col >= screen_width:
        return
    usable_width = min(max(width, 0), max(0, screen_width - col - 1))
    if usable_width <= 0:
        return
    try:
        stdscr.addnstr(row, col, ellipsize(text, usable_width), usable_width, attr)
    except curses.error:
        return


def preferred_slug_for_scope(current: dict[str, Any], write_scope: str) -> str | None:
    if write_scope == "coding":
        return current.get("codingModel")
    if write_scope == "run":
        return current.get("runModel")
    return current.get("runModel") or current.get("codingModel")


def label_for_scope(write_scope: str) -> str:
    return TUI_SCOPE_LABELS.get(write_scope, TUI_SCOPE_LABELS["global"])


def tone(kind: str, text: str) -> str:
    return paint(text, PALETTE[kind], BOLD)


def emphasize_path(path: str) -> str:
    return paint(path, PALETTE["soft"], BOLD)


def model_text(slug: str | None, config: dict[str, Any]) -> str:
    if not slug:
        return tone("muted", "未设置")
    return f"{tone('bright', display_model_name(slug, config))} ({paint(slug, PALETTE['soft'], BOLD)})"


def scope_hint(write_scope: str) -> str:
    if write_scope == "run":
        return "只更新 ilongrun 默认模型"
    if write_scope == "coding":
        return "只更新 ilongrun-coding 默认模型"
    return "同时更新 ilongrun 与 ilongrun-coding"


def target_line(target: dict[str, Any]) -> str:
    status_text = "未变更" if not target.get("changed") else "已写入"
    if target.get("action") == "reset" and target.get("changed"):
        status_text = "已恢复"
    if target.get("action") == "show":
        status_text = "未变更"
    tone_key = "ok" if target.get("changed") else "muted"
    target_name = TARGET_SCOPE_LABELS.get(target["scope"], target["scope"])
    action_name = TARGET_ACTION_LABELS.get(target["action"], target["action"])
    return f"{tone('bright', target_name)} · {action_name} · {paint(status_text, PALETTE[tone_key], BOLD)} · {emphasize_path(target['path'])}"


def clamp_selected_slug(visible: list[dict[str, str]], selected_slug: str | None, fallback_slug: str | None) -> tuple[int, str | None]:
    if not visible:
        return 0, None
    preferred = selected_slug or fallback_slug
    if preferred:
        for index, item in enumerate(visible):
            if item["slug"] == preferred:
                return index, preferred
    return 0, visible[0]["slug"]


def draw_tabs(stdscr: Any, current_scope: str, width: int) -> None:
    col = 0
    for index, write_scope in enumerate(TUI_SCOPE_ORDER):
        label = f" {label_for_scope(write_scope)} "
        attr = curses.A_REVERSE if write_scope == current_scope else curses.A_NORMAL
        if col < width - 1:
            safe_addnstr(stdscr, 2, col, label, max(0, width - col - 1), attr)
        col += len(label) + 1
        if index < len(TUI_SCOPE_ORDER) - 1 and col < width - 1:
            safe_addnstr(stdscr, 2, col - 1, " ", 1)


def next_scope(current_scope: str, step: int) -> str:
    index = TUI_SCOPE_ORDER.index(current_scope)
    return TUI_SCOPE_ORDER[(index + step) % len(TUI_SCOPE_ORDER)]


def run_picker(items: list[dict[str, str]], current: dict[str, Any]) -> dict[str, str] | None:
    def inner(stdscr: Any) -> dict[str, str] | None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.keypad(True)
        query = ""
        scroll = 0
        write_scope = "global"
        selected_slug = preferred_slug_for_scope(current, write_scope)
        confirm_reset = False
        while True:
            visible = filter_picker_items(items, query)
            selected, selected_slug = clamp_selected_slug(visible, selected_slug, preferred_slug_for_scope(current, write_scope))
            height, width = stdscr.getmaxyx()
            list_top = 7
            list_bottom = max(list_top + 1, height - 3)
            list_height = max(1, list_bottom - list_top)
            if selected < scroll:
                scroll = selected
            if selected >= scroll + list_height:
                scroll = selected - list_height + 1
            if scroll < 0:
                scroll = 0

            stdscr.erase()
            title = "选择 iLongRun 默认主模型"
            safe_addnstr(stdscr, 0, 0, title, width - 1, curses.A_BOLD)
            safe_addnstr(
                stdscr,
                1,
                0,
                f"当前模板：run={current.get('runModel') or '-'} / coding={current.get('codingModel') or '-'}",
                width - 1,
            )
            draw_tabs(stdscr, write_scope, width)
            safe_addnstr(stdscr, 3, 0, TUI_SCOPE_DESCRIPTIONS[write_scope], width - 1)
            safe_addnstr(stdscr, 4, 0, f"搜索：{query or '（输入即过滤）'}", width - 1)
            safe_addnstr(stdscr, 5, 0, "状态：✓ 可用  ✗ 不可用  ? 未确认", width - 1)

            if not visible:
                safe_addnstr(stdscr, list_top, 0, "没有匹配的模型，请修改搜索词。", width - 1)
            else:
                slice_items = visible[scroll : scroll + list_height]
                for row_index, item in enumerate(slice_items, start=list_top):
                    actual_index = scroll + (row_index - list_top)
                    prefix = "> " if actual_index == selected else "  "
                    line = prefix + picker_line(item, max(1, width - 3))
                    attr = curses.A_REVERSE if actual_index == selected else curses.A_NORMAL
                    safe_addnstr(stdscr, row_index, 0, line, width - 1, attr)

            message_line = ""
            if confirm_reset:
                message_line = "确认执行全局 reset 吗？按 y 确认，按 n / Esc 取消。"
            footer = "Tab / Shift+Tab / ←→ 切页 · ↑↓ / j k 移动 · Enter 选择 · r 全局 reset · Esc / q 取消 · Backspace 删除搜索"
            safe_addnstr(stdscr, height - 2, 0, message_line, width - 1, curses.A_BOLD if confirm_reset else curses.A_NORMAL)
            safe_addnstr(stdscr, height - 1, 0, footer, width - 1)
            stdscr.refresh()

            key = stdscr.getch()
            if confirm_reset:
                if key in (ord("y"), ord("Y")):
                    return {"action": "reset", "scope": "global", "pickerTab": write_scope}
                if key in (ord("n"), ord("N"), 27):
                    confirm_reset = False
                continue
            if key in (curses.KEY_UP, ord("k"), ord("K")):
                if visible:
                    selected = max(0, selected - 1)
                    selected_slug = visible[selected]["slug"]
            elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
                if visible:
                    selected = min(len(visible) - 1, selected + 1)
                    selected_slug = visible[selected]["slug"]
            elif key in (10, 13, curses.KEY_ENTER):
                if visible:
                    return {"action": "select", "scope": write_scope, "slug": visible[selected]["slug"]}
            elif key == 9:
                write_scope = next_scope(write_scope, 1)
                selected_slug = preferred_slug_for_scope(current, write_scope)
                scroll = 0
            elif key in (curses.KEY_BTAB, curses.KEY_LEFT):
                write_scope = next_scope(write_scope, -1)
                selected_slug = preferred_slug_for_scope(current, write_scope)
                scroll = 0
            elif key == curses.KEY_RIGHT:
                write_scope = next_scope(write_scope, 1)
                selected_slug = preferred_slug_for_scope(current, write_scope)
                scroll = 0
            elif key in (27, ord("q"), ord("Q")):
                return None
            elif key in (ord("r"), ord("R")):
                confirm_reset = True
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                query = query[:-1]
                scroll = 0
            elif 32 <= key <= 126:
                query += chr(key)
                scroll = 0

    return curses.wrapper(inner)


def text_report(payload: dict[str, Any], config: dict[str, Any]) -> str:
    current = dict(payload.get("current") or {})
    run_model = current.get("runModel") or payload["defaults"]["commandDefaults"]["run"]
    coding_model = current.get("codingModel") or payload["defaults"]["commandDefaults"]["coding"]
    review_models = current.get("reviewModels") or FIXED_REVIEW_ROLES
    review_display = " / ".join(
        display_model_name(str(review_models.get(role) or "unknown"), config)
        for role in FIXED_REVIEW_ROLES
    )
    final_audit = current.get("finalAuditReviewer") or current.get("auditModel") or "gpt-5.4"
    mode_label, mode_tone = MODE_LABELS.get(payload["mode"], (payload["mode"], "bright"))
    refresh = payload.get("refresh") or {}

    lines = [
        open_top(board_title("🎛️", "主模型模板看板"), tail_width=22),
        left_border(),
        board_line("🎯 当前模式", tone(mode_tone, mode_label)),
        board_line("🧭 写入作用域", tone("bright", f"{payload.get('writeScopeLabel', '全局默认')} · {scope_hint(payload.get('writeScope', 'global'))}")),
        board_line("🧠 run 模板", model_text(run_model, config)),
        board_line("💻 coding 模板", model_text(coding_model, config)),
        board_line("🛡️ 审查模板", tone("soft", f"{review_display} / final-audit={display_model_name(str(final_audit), config)}")),
    ]
    if payload.get("selectionSource") == "picker":
        picker_tab = label_for_scope(str(payload.get("pickerTab") or payload.get("writeScope") or "global"))
        lines.append(board_line("🕹️ 选择方式", tone("soft", f"交互式选模器 · 当前页签={picker_tab}")))
    if payload.get("requestedModel"):
        lines.append(board_line("📥 请求模型", model_text(str(payload["requestedModel"]), config)))
    if payload.get("refreshRequested") and refresh.get("status"):
        refresh_tone = "ok" if refresh.get("status") == "refreshed" else "warn"
        lines.append(board_line("🔄 模型缓存", tone(refresh_tone, str(refresh.get("message") or "已处理"))))
    lines.extend([left_border(), open_bottom(), ""])

    lines.append(section_heading("📁 写入目标"))
    lines.append(section_rule())
    for target in payload.get("targets", []):
        lines.append(f"  - {target_line(target)}")
    if payload.get("skippedRepoPath"):
        lines.append(f"  - {tone('warn', '仓库配置 · skipped')} · 当前目录不是 iLongRun 仓库 · {emphasize_path(payload['skippedRepoPath'])}")
    lines.append("")

    lines.append(section_heading("🧷 当前边界"))
    lines.append(section_rule())
    lines.append(detail_line("影响范围", tone("soft", "只影响后续新启动的 ilongrun / ilongrun-coding")))
    lines.append(detail_line("不会改动", tone("soft", "活动 run 的 scheduler.json / 当前 Copilot 会话的原生 /model")))
    lines.append(detail_line("审查模型", tone("soft", "review roles、codingAuditModel、final-audit 保持独立策略")))
    if payload.get("writeScope") in {"run", "coding"}:
        lines.append(detail_line("作用域说明", tone("soft", "当前是浅作用域写入：只改对应 commandDefaults + skillDefaults")))
    lines.append("")

    lines.append(section_heading("🧭 使用提示"))
    lines.append(section_rule())
    lines.append(f"  1. 交互选模：{tone('bright', 'ilongrun-model')}")
    lines.append(f"  2. 脚本查看：{tone('bright', 'ilongrun-model show')}")
    lines.append(f"  3. 全局直设：{tone('bright', 'ilongrun-model <model>')}（命令行直设始终是全局模式）")
    lines.append(f"  4. 刷新缓存：{tone('bright', 'ilongrun-model --refresh')}")
    lines.append(f"  5. 恢复默认：{tone('bright', 'ilongrun-model reset')}")
    lines.append("")
    lines.append(ad_box("iLongRun - 由 zscc.in 知识船仓·公益社区 倾力制作～\n欢迎加入我们，这里是终身学习者的后花园"))
    return "\n".join(lines)


def should_launch_picker(args: argparse.Namespace, requested: str) -> bool:
    if args.json or args.test_select or args.test_reset or args.test_tab:
        return False
    if requested:
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()


def main() -> int:
    parser = argparse.ArgumentParser(description="Show, set, reset, or interactively choose iLongRun primary model templates")
    parser.add_argument("model", nargs="?", help="show / reset / model slug-or-alias")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="refresh model availability cache before show or picker")
    parser.add_argument("--test-select", help=argparse.SUPPRESS)
    parser.add_argument("--test-tab", choices=TUI_SCOPE_ORDER, help=argparse.SUPPRESS)
    parser.add_argument("--test-reset", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    repo_root = find_ilongrun_repo_root(workspace)
    targets = target_paths(workspace)
    config_path = targets[0][1]
    config = load_model_config(config_path)
    defaults = primary_template_defaults()
    requested = (args.model or "").strip()
    refresh_payload = refresh_model_cache(config_path) if args.refresh else {}

    mode = "show"
    effective_model: str | None = None
    selection_source: str | None = None
    write_scope = "global"
    picker_tab: str | None = None

    if should_launch_picker(args, requested):
        current_policy = load_raw_policy(targets[0][1])
        current_summary = summarize_policy(current_policy)
        items = build_picker_items(config, current_summary, availability_lookup(config, candidate_slugs(config, current_summary)))
        try:
            chosen = run_picker(items, current_summary)
        except Exception as exc:  # pragma: no cover - fallback path
            print(f"Warning: 交互式选模器启动失败，已退回 show 模式：{exc}", file=sys.stderr)
            chosen = None
            requested = "show"
        if chosen is None and not requested:
            print("已取消，未写入任何配置。")
            return 130
        if chosen:
            picker_tab = chosen.get("pickerTab") or chosen.get("scope")
            write_scope = chosen.get("scope") or "global"
            selection_source = "picker"
            if chosen.get("action") == "reset":
                requested = "reset"
                write_scope = "global"
            else:
                requested = chosen.get("slug") or ""

    if args.test_select:
        requested = args.test_select.strip()
        selection_source = "picker"
        write_scope = args.test_tab or "global"
        picker_tab = write_scope
    elif args.test_tab:
        picker_tab = args.test_tab
        write_scope = args.test_tab

    if args.test_reset:
        requested = "reset"
        selection_source = "picker"
        picker_tab = args.test_tab or picker_tab or "global"
        write_scope = "global"

    if requested:
        lowered = requested.lower()
        if lowered == "show":
            mode = "show"
        elif lowered == "reset":
            mode = "reset"
        else:
            effective_model = normalize_model_name(requested, config)
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
            updated = apply_model_for_scope(raw, effective_model, write_scope)
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

    current = results[0] if results else summarize_policy(default_model_config())
    repo_hint_path = str((workspace / "config" / "model-policy.jsonc").resolve())
    payload = {
        "ok": True,
        "mode": mode,
        "requestedModel": requested if mode == "set" else None,
        "effectiveModel": effective_model,
        "selectionSource": selection_source,
        "writeScope": write_scope,
        "writeScopeLabel": label_for_scope(write_scope),
        "pickerTab": picker_tab,
        "defaults": defaults,
        "targets": results,
        "current": current,
        "repoDetected": bool(repo_root),
        "skippedRepoPath": None if repo_root else repo_hint_path,
        "refresh": refresh_payload,
        "refreshRequested": bool(args.refresh),
        "availabilityCache": str(MODEL_AVAILABILITY_CACHE),
        "candidates": build_picker_items(config, current, availability_lookup(config, candidate_slugs(config, current))),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text_report(payload, config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
