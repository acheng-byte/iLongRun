#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import load_model_config, read_json, resolve_run_target, scheduler_path  # noqa: E402
from _ilongrun_shared import display_model_name  # noqa: E402


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
    "phase-execution": "执行",
    "phase-audit": "最终审查",
    "phase-finalize": "收尾",
}


def zh(mapping: dict[str, str], raw: str | None) -> str:
    return mapping.get(raw or "", raw or "无")


def line(label: str, value: str) -> str:
    return f"│  {label:<10} {value}"


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
    audit_model = (sched.get("reviews") or {}).get("auditModel") or sched.get("codingAuditModel") or config.get("codingAuditModel") or "gpt-5.4"
    state = sched.get("state") or "running"
    phase = sched.get("phase") or "phase-strategy"
    mode = sched.get("mode") or "direct-lane"
    profile = sched.get("profile") or ("coding" if args.subcommand == "coding" else "office")
    updated = sched.get("updatedAt") or "刚刚"

    print("╭─── 🚀 iLongRun 启动看板 ────────────────────────────╮")
    print("│                                                    │")
    print(line("🆔 运行 ID", target.run_id))
    print(line("📊 当前状态", f"🟢 后台运行（{zh(STATE_LABELS, state)}）"))
    print(line("🎯 当前阶段", zh(PHASE_LABELS, phase)))
    print(line("🔧 运行模式", zh(MODE_LABELS, mode)))
    print(line("🌐 任务画像", zh(PROFILE_LABELS, profile)))
    print(line("🤖 执行模型", f"{display_model_name(selected, config)} ({selected})"))
    print(line("🔍 最终终审", f"{display_model_name(audit_model, config)} ({audit_model})"))
    print(line("🕐 最近更新", updated))
    print("│                                                    │")
    print("╰────────────────────────────────────────────────────╯")
    print("")
    print("📁 路径")
    print("──────────────────────────────────")
    print(f"  工作区        {target.workspace}")
    print(f"  运行目录      {target.run_dir}")
    print(f"  日志文件      {args.log_file}")
    print(f"  元信息文件    {args.meta_file}")
    print("")
    print("💡 快捷命令")
    print("──────────────────────────────────")
    print(f"  ilongrun-status {target.run_id}")
    print(f"  ilongrun-resume {target.run_id}")
    print("")
    print("📌 下一步建议")
    print("──────────────────────────────────")
    print("  - 现在可以先关掉当前终端，iLongRun 会继续在后台推进。")
    print("  - 若想看完整状态，请执行上面的 ilongrun-status 命令。")
    print("  - 若任务中途受阻，可直接用 ilongrun-resume 继续收敛。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
