#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

COMMANDS = [
    ("ilongrun", "通用长跑入口"),
    ("ilongrun-coding", "显式代码任务入口"),
    ("ilongrun-prompt", "只生成策略骨架"),
    ("ilongrun-resume", "继续上一次任务"),
    ("ilongrun-status", "查看状态看板"),
    ("ilongrun-doctor", "环境体检 / 模型探测"),
    ("copilot-ilongrun", "高级兼容入口"),
]


def line(label: str, value: str, width: int = 50) -> str:
    body = f"  {label:<10} {value}"
    if len(body) > width:
        body = body[: width - 1] + "…"
    return f"│{body:<{width}}│"


def resolve_installed_command(bin_dir: str, name: str) -> str:
    candidate = Path(bin_dir) / name
    if candidate.exists() and os.access(candidate, os.X_OK):
        return str(candidate)
    return ""


def parse_doctor_log(path: Path) -> dict[str, str | int]:
    info: dict[str, str | int] = {
        "ok_count": 0,
        "warn_count": 0,
        "fail_count": 0,
        "login": "未检测到",
        "fleet": "未检测到",
        "selftest": "未检测到",
        "legacy": "未检测到",
    }
    if not path.exists():
        return info
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    info["ok_count"] = sum(1 for line in lines if line.startswith("[OK]"))
    info["warn_count"] = sum(1 for line in lines if line.startswith("[WARN]"))
    info["fail_count"] = sum(1 for line in lines if line.startswith("[FAIL]"))
    for line in lines:
        if line.startswith("[OK] login:"):
            info["login"] = line.split(":", 1)[1].strip()
        elif line.startswith("[FAIL] copilot login missing"):
            info["login"] = "未登录 GitHub Copilot"
        elif line.startswith("[OK] /fleet:"):
            info["fleet"] = line.replace("[OK] ", "").strip()
        elif line.startswith("[WARN] /fleet"):
            info["fleet"] = line.replace("[WARN] ", "").strip()
        elif "ilongrun selftest passed" in line:
            info["selftest"] = "已通过"
        elif "ilongrun selftest failed" in line:
            info["selftest"] = "未通过"
        elif "legacy plugin removed" in line:
            info["legacy"] = "已自动清理旧插件"
        elif "legacy plugin not enabled" in line:
            info["legacy"] = "旧插件未启用"
        elif "legacy plugin still enabled" in line:
            info["legacy"] = "旧插件仍需手动处理"
    return info


def plugin_status_label(status: str, source: str) -> str:
    mapping = {
        "installed": f"✅ 已安装（{source}）",
        "failed": f"⚠️ 插件注册失败，已回退到本地命令（{source}）",
        "skipped": "⚪ 未检测到 Copilot CLI，已跳过插件注册",
    }
    return mapping.get(status, status)


def doctor_status_label(exit_code: int, info: dict[str, str | int]) -> str:
    fail_count = int(info.get("fail_count", 0) or 0)
    warn_count = int(info.get("warn_count", 0) or 0)
    if exit_code == 0 and fail_count == 0:
        return "✅ 自检通过"
    if fail_count > 0:
        return f"⚠️ 自检发现 {fail_count} 项待处理"
    if warn_count > 0:
        return f"⚠️ 自检有 {warn_count} 条提醒"
    return "⚠️ 自检完成，请查看提示"


def install_status_label(plugin_status: str, doctor_exit: int, command_ready: bool) -> str:
    if not command_ready:
        return "❌ 安装未完成"
    if plugin_status == "failed" or doctor_exit != 0:
        return "✅ 安装完成（附带提醒）"
    return "✅ 安装成功"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the iLongRun install summary board")
    parser.add_argument("--plugin-status", required=True)
    parser.add_argument("--plugin-source", required=True)
    parser.add_argument("--doctor-log", required=True)
    parser.add_argument("--doctor-exit-code", type=int, required=True)
    parser.add_argument("--command-bin-dir", required=True)
    parser.add_argument("--helper-dir", required=True)
    parser.add_argument("--model-config", required=True)
    args = parser.parse_args()

    doctor_info = parse_doctor_log(Path(args.doctor_log))
    resolved_commands = [(name, desc, resolve_installed_command(args.command_bin_dir, name)) for name, desc in COMMANDS]
    installed_count = sum(1 for _, _, path in resolved_commands if path)
    command_ready = installed_count == len(COMMANDS)
    path_ready = args.command_bin_dir in os.environ.get("PATH", "").split(":")

    print("╭─── 🛠️ iLongRun 安装看板 ────────────────────────────╮")
    print("│                                                    │")
    print(line("📦 安装状态", install_status_label(args.plugin_status, args.doctor_exit_code, command_ready)))
    print(line("🧹 清理策略", "先彻底清理，再安装新版"))
    print(line("🔌 插件注册", plugin_status_label(args.plugin_status, args.plugin_source)))
    print(line("🧩 本地能力", "✅ skills / agents / helpers 已就绪"))
    print(line("🚀 命令入口", f"✅ {installed_count}/{len(COMMANDS)} 个命令可直接使用"))
    print(line("🛡️ 环境自检", doctor_status_label(args.doctor_exit_code, doctor_info)))
    print("│                                                    │")
    print("╰────────────────────────────────────────────────────╯")
    print("")

    print("📁 安装位置")
    print("──────────────────────────────────")
    print(f"  命令目录      {args.command_bin_dir}")
    print(f"  Helper 目录   {args.helper_dir}")
    print(f"  模型配置      {args.model_config}")
    print(f"  插件来源      {args.plugin_source}")
    print("")

    print("🎛️ 想改默认模型，就改这里")
    print("──────────────────────────────────")
    print(f"  配置文件      {args.model_config}")
    print("  通用命令      改 commandDefaults")
    print("  内部 skill     改 skillDefaults")
    print("  最终终审      改 codingAuditModel")
    print("  修改完成后    建议执行：ilongrun-doctor --refresh-model-cache")
    print("")

    print("🧭 新手下一步")
    print("──────────────────────────────────")
    print('  1. 通用任务：ilongrun "用自然语言描述你的任务"')
    print('  2. 代码任务：ilongrun-coding "实现功能并补测试，最后做终审"')
    print('  3. 查看进度：ilongrun-status latest')
    print('  4. 接着继续：ilongrun-resume latest')
    print('  5. 环境体检：ilongrun-doctor')
    print('  6. 刷新模型：ilongrun-doctor --refresh-model-cache')
    if os.uname().sysname == "Darwin":
        print('  7. 提醒测试：ilongrun-doctor --notify-test')
    print("")

    print("📎 环境摘要")
    print("──────────────────────────────────")
    print(f"  Copilot 登录   {doctor_info['login']}")
    print(f"  自检结果       {doctor_info['selftest']}")
    print(f"  /fleet 能力    {doctor_info['fleet']}")
    print(f"  旧插件冲突     {doctor_info['legacy']}")
    print("")

    print("🧰 命令清单")
    print("──────────────────────────────────")
    for name, desc, path in resolved_commands:
        if path:
            print(f"  ✅ {name:<16} {desc}")
        else:
            print(f"  ⚠️ {name:<16} {desc}（当前未检测到）")
    print("")

    if path_ready:
        print("🛣️ PATH 检查")
        print("──────────────────────────────────")
        print("  已检测到 ~/.local/bin 在当前 PATH 中，可以直接使用以上命令。")
        print("")
    else:
        print("🛠️ 如果命令暂时找不到")
        print("──────────────────────────────────")
        print('  请把下面这行加入你的 shell 配置后重新打开终端：')
        print('  export PATH="$HOME/.local/bin:$PATH"')
        print("")

    if args.doctor_exit_code == 0 and command_ready:
        print("✅ 安装成功，iLongRun 已准备就绪。")
    elif command_ready:
        print("✅ 安装已经完成，但还有少量环境提醒；按上面的引导先跑 `ilongrun-doctor` 看详情即可。")
    else:
        print("⚠️ 安装已执行，但仍有命令未就绪；建议先执行 `ilongrun-doctor` 排查。")
    print("欢迎加入zscc.in 知识船仓·公益社区 - 这里是终身学习者的后花园")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
