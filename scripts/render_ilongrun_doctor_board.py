#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _ilongrun_terminal_theme import ad_box, board_line, board_title, detail_line, left_border, open_bottom, open_top, section_heading, section_rule


EXPECTED_LAUNCHERS = [
    "ilongrun",
    "ilongrun-coding",
    "ilongrun-model",
    "ilongrun-prompt",
    "ilongrun-resume",
    "ilongrun-status",
    "ilongrun-doctor",
    "copilot-ilongrun",
]


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t", 2)
        if len(parts) != 3:
            continue
        key, status, value = parts
        rows[key] = {"status": status, "value": value}
    return rows


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def status_icon(status: str) -> str:
    return {
        "ok": "✅",
        "warn": "⚠️",
        "fail": "❌",
        "info": "ℹ️",
        "skip": "⏭️",
    }.get(status, "•")


def status_text(status: str) -> str:
    return {
        "ok": "正常",
        "warn": "提醒",
        "fail": "失败",
        "info": "信息",
        "skip": "已跳过",
    }.get(status, "未知")


def model_status_text(status: str, reason: str) -> str:
    mapping = {
        "available": f"✅ 可用（{reason}）",
        "unavailable": f"❌ 不可用（{reason}）",
        "unknown": f"⚠️ 未确认（{reason}）",
    }
    return mapping.get(status, f"⚠️ 未知（{reason or '未记录'}）")


def fleet_summary(payload: dict) -> tuple[str, str]:
    status = payload.get("status")
    display = payload.get("probeModelDisplay") or payload.get("probeModel") or "默认模型"
    if status == "supported":
        return "ok", f"✅ 已支持（通过 {display} 探测）"
    if status == "unsupported":
        return "warn", f"⚠️ 当前账号暂不支持（{display}）"
    if payload.get("reason") == "skipped-no-login":
        return "skip", "⏭️ 未探测（请先登录 Copilot）"
    return "warn", "⚠️ 暂未确认"


def strip_badge(text: str) -> str:
    parts = text.split(" ", 1)
    return parts[1] if len(parts) == 2 else text


def model_summary(payload: dict, refresh_cache: bool) -> tuple[str, str]:
    reason = payload.get("reason")
    models = payload.get("models") or {}
    if reason == "skipped-no-login":
        return "skip", "⏭️ 未刷新（请先登录 Copilot）"
    if reason == "probe-helper-missing":
        return "warn", "⚠️ 未刷新（模型探测 helper 缺失）"
    if not models:
        return "warn", "⚠️ 暂无模型缓存结果"
    available = sum(1 for item in models.values() if item.get("status") == "available")
    unavailable = sum(1 for item in models.values() if item.get("status") == "unavailable")
    unknown = sum(1 for item in models.values() if item.get("status") == "unknown")
    verb = "已刷新" if refresh_cache else "已读取"
    if unavailable == 0 and unknown == 0:
        return "ok", f"✅ {verb}，{available} 个默认模型可用"
    if unavailable > 0:
        return "warn", f"⚠️ {verb}，{available} 个可用 / {unavailable} 个不可用"
    return "warn", f"⚠️ {verb}，{available} 个可用 / {unknown} 个待确认"


def summarize_selftest(rows: dict[str, dict[str, str]]) -> tuple[str, str]:
    row = rows.get("selftest")
    if not row:
        return "warn", "⚠️ 未执行"
    if row["status"] == "ok":
        return "ok", "✅ 已通过"
    if row["status"] == "fail":
        return "fail", "❌ 未通过"
    return "warn", "⚠️ 有提醒"


def verdict(rows: dict[str, dict[str, str]], model_payload: dict) -> tuple[str, str]:
    statuses = [row["status"] for row in rows.values()]
    has_fail = "fail" in statuses
    has_warn = "warn" in statuses or any((item.get("status") in {"unavailable", "unknown"}) for item in (model_payload.get("models") or {}).values())
    if has_fail:
        return "❌ 需要处理", "当前环境还有关键问题，建议先按下面的“新手下一步”修复。"
    if has_warn:
        return "⚠️ 基本可用", "核心能力已就绪，但还有提醒项，建议顺手处理。"
    return "✅ 环境健康", "命令、模型缓存、自检与能力探测均已通过。"


def summarize_launchers(rows: dict[str, dict[str, str]]) -> tuple[str, list[str], list[str]]:
    ready: list[str] = []
    missing: list[str] = []
    for name in EXPECTED_LAUNCHERS:
        row = rows.get(f"launcher.{name}")
        if row and row["status"] == "ok":
            ready.append(name)
        else:
            missing.append(name)
    if not missing:
        return f"✅ {len(ready)}/{len(EXPECTED_LAUNCHERS)} 已就绪", ready, missing
    return f"⚠️ {len(ready)}/{len(EXPECTED_LAUNCHERS)} 已就绪", ready, missing


def last_error_line(path: Path) -> str:
    if not path.exists():
        return "无"
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if not lines:
        return "无"
    for line in reversed(lines):
        if any(token in line for token in ("AssertionError", "Error", "Exception", "FAIL", "failed")):
            return line
    return lines[-1]


def next_steps(rows: dict[str, dict[str, str]], model_payload: dict, refresh_cache: bool, selftest_log: Path) -> list[str]:
    steps: list[str] = []
    if rows.get("login", {}).get("status") == "fail":
        steps.append("先执行 `copilot login` 完成登录，然后重新运行 `ilongrun-doctor --refresh-model-cache`。")
    if any(rows.get(f"launcher.{name}", {}).get("status") == "fail" for name in EXPECTED_LAUNCHERS):
        steps.append("有命令入口缺失，建议重新执行一键安装脚本完成修复。")
    if rows.get("selftest", {}).get("status") == "fail":
        log_path = rows.get("selftest_log", {}).get("value") or str(selftest_log)
        steps.append(f"自检脚本未通过，可先查看完整日志：{log_path}")
    if any(rows.get(key, {}).get("status") == "fail" for key in ("coding_protocol", "vendor_snapshot", "coding_playbooks", "coding_agents")):
        steps.append("coding protocol bundle 不完整，建议重新执行一键安装脚本补齐 skill playbooks / agents / vendor 快照。")
    if rows.get("legacy_skill.ilongrun-model", {}).get("status") == "warn":
        steps.append("检测到旧 `/ilongrun-model` 会话 skill 残留，建议重跑安装脚本，或手动删除 `~/.copilot/skills/ilongrun-model`。")
    models = model_payload.get("models") or {}
    unavailable = [item.get("displayName") or key for key, item in models.items() if item.get("status") == "unavailable"]
    if unavailable:
        steps.append(f"有默认模型当前不可用：{', '.join(unavailable)}。可去 `model-policy.jsonc` 调整默认模型。")
    if refresh_cache and not steps:
        steps.append("模型缓存已经刷新完成，后续可直接运行 `ilongrun` 或 `ilongrun-coding` 开始任务。")
    if not steps:
        steps.append("当前环境整体正常，建议定期执行 `ilongrun-doctor` 做一次快速体检。")
    return steps[:4]


def main() -> int:
    parser = argparse.ArgumentParser(description="Render beginner-friendly iLongRun doctor board")
    parser.add_argument("--checks-file", required=True)
    parser.add_argument("--model-probe-json", required=True)
    parser.add_argument("--fleet-probe-json", required=True)
    parser.add_argument("--selftest-log", required=True)
    parser.add_argument("--refresh-cache", type=int, default=0)
    parser.add_argument("--notify-test", type=int, default=0)
    args = parser.parse_args()

    rows = read_rows(Path(args.checks_file))
    model_payload = read_json(Path(args.model_probe_json))
    fleet_payload = read_json(Path(args.fleet_probe_json))
    selftest_log = Path(args.selftest_log)

    verdict_title, verdict_desc = verdict(rows, model_payload)
    launcher_summary, ready_launchers, missing_launchers = summarize_launchers(rows)
    model_tone, model_line = model_summary(model_payload, bool(args.refresh_cache))
    selftest_tone, selftest_line = summarize_selftest(rows)
    fleet_tone, fleet_line = fleet_summary(fleet_payload)

    login_row = rows.get("login", {"status": "fail", "value": "未登录 GitHub Copilot"})
    copilot_row = rows.get("copilot", {"status": "fail", "value": "未检测到 copilot CLI"})
    policy_row = rows.get("model_policy", {"status": "fail", "value": "未检测到模型配置"})

    print(open_top(board_title("🩺", "环境体检看板"), tail_width=24))
    print(left_border())
    print(board_line("🧾 体检结论", verdict_title))
    print(board_line("🧰 命令入口", launcher_summary))
    print(board_line("👤 Copilot", f"{status_icon(login_row['status'])} {login_row['value']}"))
    print(board_line("🧠 模型缓存", model_line))
    print(board_line("🧪 自检脚本", selftest_line))
    print(board_line("🚢 /fleet 能力", fleet_line))
    if args.notify_test:
        notify_row = rows.get("notify_test", {"status": "warn", "value": "未执行"})
        print(board_line("🔔 提醒测试", f"{status_icon(notify_row['status'])} {notify_row['value']}"))
    print(left_border())
    print(open_bottom())
    print("")
    print(verdict_desc)
    print("")

    print(section_heading("📦 基础环境"))
    print(section_rule())
    print(detail_line("Copilot CLI", f"{status_icon(copilot_row['status'])} {copilot_row['value']}"))
    print(detail_line("登录账号", f"{status_icon(login_row['status'])} {login_row['value']}"))
    print(detail_line("模型配置", f"{status_icon(policy_row['status'])} {policy_row['value']}"))
    protocol_row = rows.get("coding_protocol")
    if protocol_row:
        print(detail_line("Coding 协议", f"{status_icon(protocol_row['status'])} {protocol_row['value']}"))
    vendor_row = rows.get("vendor_snapshot")
    if vendor_row:
        print(detail_line("Vendor 快照", f"{status_icon(vendor_row['status'])} {vendor_row['value']}"))

    legacy_row = rows.get("legacy_plugin")
    if legacy_row:
        print(detail_line("旧插件", f"{status_icon(legacy_row['status'])} {legacy_row['value']}"))
    legacy_skill_row = rows.get("legacy_skill.ilongrun-model")
    if legacy_skill_row:
        print(detail_line("旧会话入口", f"{status_icon(legacy_skill_row['status'])} {legacy_skill_row['value']}"))
    workspace_row = rows.get("workspace_legacy")
    if workspace_row:
        print(detail_line("工作区旧状态", f"{status_icon(workspace_row['status'])} {workspace_row['value']}"))
    archive_row = rows.get("workspace_archive")
    if archive_row:
        print(detail_line("归档位置", archive_row["value"]))
    screen_row = rows.get("screen")
    if screen_row:
        print(detail_line("screen", f"{status_icon(screen_row['status'])} {screen_row['value']}"))
    notifier_row = rows.get("terminal_notifier")
    if notifier_row:
        print(detail_line("提醒组件", f"{status_icon(notifier_row['status'])} {notifier_row['value']}"))
    print(detail_line("命令就绪", ", ".join(ready_launchers) if ready_launchers else "无"))
    if missing_launchers:
        print(detail_line("缺失命令", ", ".join(missing_launchers)))
    print("")

    playbooks_row = rows.get("coding_playbooks")
    agents_row = rows.get("coding_agents")
    if playbooks_row or agents_row:
        print(section_heading("🧬 Coding Protocol Bundle"))
        print(section_rule())
        if playbooks_row:
            print(detail_line("Skill Playbooks", f"{status_icon(playbooks_row['status'])} {playbooks_row['value']}"))
        if agents_row:
            print(detail_line("专项 Agents", f"{status_icon(agents_row['status'])} {agents_row['value']}"))
        print("")

    print(section_heading("🧠 模型缓存刷新结果" if args.refresh_cache else "🧠 模型缓存概览"))
    print(section_rule())
    if model_payload.get("identity"):
        print(detail_line("当前账号", model_payload.get("identity")))
    if model_payload.get("cache"):
        print(detail_line("缓存文件", model_payload.get("cache")))
    if model_payload.get("reason") == "skipped-no-login":
        print("  ⏭️ 当前未登录 Copilot，暂时跳过模型缓存刷新。")
    else:
        for model_key, item in (model_payload.get("models") or {}).items():
            name = item.get("displayName") or model_key
            print(detail_line(name, model_status_text(item.get("status", "unknown"), item.get("reason", "未记录"))))
    print("")

    print(section_heading("🧪 深度自检"))
    print(section_rule())
    selftest_row = rows.get("selftest", {"status": "warn", "value": "未执行"})
    print(detail_line("自检结果", f"{status_icon(selftest_row['status'])} {selftest_row['value']}"))
    if selftest_row["status"] == "fail":
        print(detail_line("失败摘要", last_error_line(selftest_log)))
        if rows.get("selftest_log"):
            print(detail_line("完整日志", rows["selftest_log"]["value"]))
    print(detail_line("/fleet", f"{status_icon(fleet_tone)} {strip_badge(fleet_line)}"))
    if fleet_payload.get("cache"):
        print(detail_line("fleet 缓存", fleet_payload.get("cache")))
    if args.notify_test:
        notify_row = rows.get("notify_test", {"status": "warn", "value": "未执行"})
        print(detail_line("提醒测试", f"{status_icon(notify_row['status'])} {notify_row['value']}"))
    print("")

    print(section_heading("💡 新手下一步"))
    print(section_rule())
    for idx, step in enumerate(next_steps(rows, model_payload, bool(args.refresh_cache), selftest_log), start=1):
        print(f"  {idx}. {step}")
    print("")

    print(ad_box("iLongRun - 由 zscc.in 知识船仓·公益社区 倾力制作～\n欢迎加入我们，这里是终身学习者的后花园"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
