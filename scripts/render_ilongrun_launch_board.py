#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import load_model_config, read_json, resolve_run_target, scheduler_path  # noqa: E402
from _ilongrun_shared import display_model_name  # noqa: E402
from _ilongrun_terminal_theme import (  # noqa: E402
    BOLD,
    PALETTE,
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


STATE_LABELS = {
    "running": "进行中",
    "pending": "待处理",
    "blocked": "已阻塞",
    "complete": "已完成",
}
MODE_LABELS = {
    "direct-lane": "直连模式",
    "wave-swarm": "波次蜂群",
    "super-swarm": "超级蜂群",
    "fleet-governor": "舰队治理",
    "sentinel-watch": "哨兵观察",
    "complete-and-exit": "完成后退出",
}
PROFILE_LABELS = {
    "coding": "编码",
    "office": "办公",
    "research": "研究",
}
PHASE_LABELS = {
    "phase-strategy": "策略制定",
    "phase-define": "定义",
    "phase-plan": "规划",
    "phase-build": "构建",
    "phase-verify": "验证",
    "phase-review": "评审",
    "phase-execution": "执行",
    "phase-audit": "最终审查",
    "phase-finalize": "收尾",
}


def zh(mapping: dict[str, str], raw: str | None) -> str:
    return mapping.get(raw or "", raw or "无")


def tone(kind: str, text: str) -> str:
    return paint(text, PALETTE[kind], BOLD)


def state_value(state: str) -> str:
    label = zh(STATE_LABELS, state)
    if state == "complete":
        return tone("ok", f"✅ 已完成（{label}）")
    if state == "blocked":
        return tone("err", f"⛔ 已阻塞（{label}）")
    if state == "pending":
        return tone("warn", f"⏳ 等待执行（{label}）")
    return tone("bright", f"🔄 后台运行（{label}）")


def phase_value(phase: str, sched: dict) -> str:
    phase_text = zh(PHASE_LABELS, phase)
    wave_cursor = sched.get("waveCursor")
    if wave_cursor:
        return tone("soft", f"{phase_text} - 波次 {wave_cursor}")
    return tone("soft", phase_text)


def model_value(raw: str, config: dict) -> str:
    return f"{tone('bright', display_model_name(raw, config))} {paint(f'({raw})', PALETTE['muted'])}"


def path_value(raw: str) -> str:
    return paint(raw, PALETTE["soft"], BOLD)


def command_value(raw: str) -> str:
    return paint(raw, PALETTE["bright"], BOLD)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the detached iLongRun launch summary board")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--subcommand", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--meta-file", required=True)
    parser.add_argument("--selected-model", required=True)
    parser.add_argument("--model-config")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    sched = read_json(scheduler_path(target), {})
    config = load_model_config(args.model_config)
    selected = args.selected_model or sched.get("selectedModel") or "unknown"
    audit_model = (
        (sched.get("reviews") or {}).get("auditModel")
        or sched.get("codingAuditModel")
        or config.get("codingAuditModel")
        or "gpt-5.4"
    )
    state = sched.get("state") or "running"
    phase = sched.get("phase") or "phase-strategy"
    mode = sched.get("mode") or "direct-lane"
    profile = sched.get("profile") or ("coding" if args.subcommand == "coding" else "office")
    updated = sched.get("updatedAt") or "刚刚"
    coding_protocol = sched.get("codingProtocol") or {}
    swarm_policy = sched.get("swarmPolicy") or {}

    print(open_top(board_title("🚀", "启动看板"), tail_width=28))
    print(left_border())
    print(board_line("🆔 运行 ID", tone("soft", target.run_id)))
    print(board_line("📊 当前状态", state_value(state)))
    print(board_line("🎯 当前阶段", phase_value(phase, sched)))
    print(board_line("🔧 运行模式", tone("warm", zh(MODE_LABELS, mode))))
    print(board_line("🌐 任务画像", tone("warm", zh(PROFILE_LABELS, profile))))
    print(board_line("🤖 执行模型", model_value(selected, config)))
    print(board_line("🔍 最终终审", model_value(audit_model, config)))
    if profile == "coding":
        print(board_line("🧬 Coding 协议", tone("soft", f"{coding_protocol.get('version') or '0.6.0'} / {swarm_policy.get('activeMode') or mode}")))
    print(board_line("🕐 最近更新", tone("soft", updated)))
    print(left_border())
    print(open_bottom())
    print("")

    print(section_heading("📁 运行路径"))
    print(section_rule())
    print(detail_line("工作区", path_value(str(target.workspace))))
    print(detail_line("运行目录", path_value(str(target.run_dir))))
    print(detail_line("日志文件", path_value(args.log_file)))
    print(detail_line("元信息", path_value(args.meta_file)))
    print("")

    print(section_heading("⚡ 快捷命令"))
    print(section_rule())
    print(detail_line("查看状态", command_value(f"ilongrun-status {target.run_id}")))
    print(detail_line("继续收敛", command_value(f"ilongrun-resume {target.run_id}")))
    print("")

    print(section_heading("💡 下一步建议"))
    print(section_rule())
    print("  - 现在可以先关掉当前终端，iLongRun 会继续在后台推进。")
    print("  - 若想看完整状态，请执行上面的 ilongrun-status 命令。")
    print("  - 若任务中途受阻，可直接用 ilongrun-resume 继续收敛。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
