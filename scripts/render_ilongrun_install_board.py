#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from _ilongrun_terminal_theme import (
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

COMMANDS = [
    ("ilongrun", "通用长跑入口"),
    ("ilongrun-coding", "显式代码任务入口"),
    ("ilongrun-model", "交互式选择默认主模型（支持全局/run/coding）"),
    ("ilongrun-prompt", "只生成策略骨架"),
    ("ilongrun-resume", "继续上一次任务"),
    ("ilongrun-status", "查看状态看板"),
    ("ilongrun-doctor", "环境体检 / 模型探测"),
    ("copilot-ilongrun", "高级兼容入口"),
]


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
    if any("环境体检看板" in line for line in lines):
        for line in lines:
            normalized = re.sub(r"\s+", " ", line.strip())
            if "👤 Copilot" in normalized:
                info["login"] = normalized.split("👤 Copilot", 1)[1].strip()
            elif "🧪 自检脚本" in normalized:
                info["selftest"] = normalized.split("🧪 自检脚本", 1)[1].strip()
                if "❌" in normalized:
                    info["fail_count"] = max(int(info.get("fail_count", 0) or 0), 1)
                elif "⚠️" in normalized:
                    info["warn_count"] = max(int(info.get("warn_count", 0) or 0), 1)
            elif "🚢 /fleet 能力" in normalized:
                info["fleet"] = normalized.split("🚢 /fleet 能力", 1)[1].strip()
            elif re.search(r"(?:旧插件|旧插件冲突)\s", normalized):
                info["legacy"] = re.split(r"(?:旧插件|旧插件冲突)", normalized, maxsplit=1)[1].strip()
    return info


def tone(kind: str, text: str) -> str:
    return paint(text, PALETTE[kind], BOLD)


def plugin_status_label(status: str, source: str) -> tuple[str, str]:
    mapping = {
        "installed": ("ok", f"✅ 已安装（{source}）"),
        "failed": ("warn", f"⚠️ 插件注册失败，已回退到本地命令（{source}）"),
        "skipped": ("soft", "⚪ 未检测到 Copilot CLI，已跳过插件注册"),
    }
    return mapping.get(status, ("soft", status))


def doctor_status_label(exit_code: int, info: dict[str, str | int]) -> tuple[str, str]:
    fail_count = int(info.get("fail_count", 0) or 0)
    warn_count = int(info.get("warn_count", 0) or 0)
    if exit_code == 0 and fail_count == 0:
        return "ok", "✅ 自检通过"
    if fail_count > 0:
        return "warn", f"⚠️ 自检发现 {fail_count} 项待处理"
    if warn_count > 0:
        return "warn", f"⚠️ 自检有 {warn_count} 条提醒"
    return "warn", "⚠️ 自检完成，请查看提示"


def install_status_label(plugin_status: str, doctor_exit: int, command_ready: bool) -> tuple[str, str]:
    if not command_ready:
        return "err", "❌ 安装未完成"
    if plugin_status == "failed" or doctor_exit != 0:
        return "warn", "✅ 安装完成（附带提醒）"
    return "ok", "✅ 安装成功"


def emphasize_path(path: str) -> str:
    return paint(path, PALETTE["soft"], BOLD)


def command_line(name: str, desc: str, ready: bool) -> str:
    badge = tone("ok", "✅") if ready else tone("warn", "⚠️")
    cmd_name = paint(f"{name:<16}", PALETTE["bright"], BOLD)
    return f"  {badge} {cmd_name} {desc}"


def command_summary(installed_count: int, total: int, ready: bool) -> str:
    icon = "✅" if ready else "⚠️"
    tone_key = "ok" if ready else "warn"
    return tone(tone_key, f"{icon} {installed_count}/{total} 个命令可直接使用")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the iLongRun install summary board")
    parser.add_argument("--plugin-status", required=True)
    parser.add_argument("--plugin-source", required=True)
    parser.add_argument("--doctor-log", required=True)
    parser.add_argument("--doctor-exit-code", type=int, required=True)
    parser.add_argument("--command-bin-dir", required=True)
    parser.add_argument("--helper-dir", required=True)
    parser.add_argument("--model-config", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    doctor_info = parse_doctor_log(Path(args.doctor_log))
    resolved_commands = [(name, desc, resolve_installed_command(args.command_bin_dir, name)) for name, desc in COMMANDS]
    installed_count = sum(1 for _, _, path in resolved_commands if path)
    command_ready = installed_count == len(COMMANDS)
    path_ready = args.command_bin_dir in os.environ.get("PATH", "").split(":")

    install_tone, install_text = install_status_label(args.plugin_status, args.doctor_exit_code, command_ready)
    plugin_tone, plugin_text = plugin_status_label(args.plugin_status, args.plugin_source)
    doctor_tone, doctor_text = doctor_status_label(args.doctor_exit_code, doctor_info)

    print(open_top(board_title("🛠️", f"安装看板 · v{args.version}"), tail_width=18))
    print(left_border())
    print(board_line("📦 安装状态", tone(install_tone, install_text)))
    print(board_line("🏷️ 当前版本", tone("bright", f"iLongRun v{args.version}")))
    print(board_line("🧹 清理策略", tone("warm", "先彻底清理，再安装新版")))
    print(board_line("🔌 插件注册", tone(plugin_tone, plugin_text)))
    print(board_line("🧩 本地能力", tone("ok", "✅ skills / agents / helpers 已就绪")))
    print(board_line("🚀 命令入口", command_summary(installed_count, len(COMMANDS), command_ready)))
    print(board_line("🛡️ 环境自检", tone(doctor_tone, doctor_text)))
    print(left_border())
    print(open_bottom())
    print("")

    print(section_heading("📁 安装位置"))
    print(section_rule())
    print(detail_line("命令目录", emphasize_path(args.command_bin_dir)))
    print(detail_line("Helper 目录", emphasize_path(args.helper_dir)))
    print(detail_line("模型配置", emphasize_path(args.model_config)))
    print(detail_line("插件来源", tone("bright", args.plugin_source)))
    print("")

    print(section_heading("🎛️ 想改默认模型，就改这里"))
    print(section_rule())
    print(detail_line("配置文件", emphasize_path(args.model_config)))
    print(detail_line("通用命令", tone("warm", "改 commandDefaults")))
    print(detail_line("内部 skill", tone("warm", "改 skillDefaults")))
    print(detail_line("最终终审", tone("warm", "改 codingAuditModel")))
    print(detail_line("修改完成后", tone("soft", "建议执行：ilongrun-doctor --refresh-model-cache")))
    print("")

    print(section_heading("🧭 新手下一步"))
    print(section_rule())
    print(f"  1. 通用任务：{tone('bright', 'ilongrun')} \"用自然语言描述你的任务\"")
    print(f"  2. 代码任务：{tone('bright', 'ilongrun-coding')} \"实现功能并补测试，最后做终审\"")
    print(f"  3. 查看进度：{tone('bright', 'ilongrun-status')} latest")
    print(f"  4. 接着继续：{tone('bright', 'ilongrun-resume')} latest")
    print(f"  5. 环境体检：{tone('bright', 'ilongrun-doctor')}")
    print(f"  6. 刷新模型：{tone('bright', 'ilongrun-doctor')} --refresh-model-cache")
    if getattr(os, "uname", lambda: type("u", (), {"sysname": ""})()).sysname == "Darwin":
        print(f"  7. 提醒测试：{tone('bright', 'ilongrun-doctor')} --notify-test")
    print("")

    print(section_heading("📎 环境摘要"))
    print(section_rule())
    print(detail_line("Copilot 登录", tone("soft", str(doctor_info["login"]))))
    print(detail_line("自检结果", tone("soft", str(doctor_info["selftest"]))))
    print(detail_line("/fleet 能力", tone("soft", str(doctor_info["fleet"]))))
    print(detail_line("旧插件冲突", tone("soft", str(doctor_info["legacy"]))))
    print("")

    print(section_heading("🧰 命令清单"))
    print(section_rule())
    for name, desc, path in resolved_commands:
        print(command_line(name, desc, bool(path)))
    print("")

    if path_ready:
        print(section_heading("🛣️ PATH 检查"))
        print(section_rule())
        print(f"  已检测到 {tone('bright', '~/.local/bin')} 在当前 PATH 中，可以直接使用以上命令。")
        print("")
    else:
        print(section_heading("🛠️ 如果命令暂时找不到"))
        print(section_rule())
        print("  请把下面这行加入你的 shell 配置后重新打开终端：")
        print("  " + tone("soft", 'export PATH="$HOME/.local/bin:$PATH"'))
        print("")

    if args.doctor_exit_code == 0 and command_ready:
        print(tone("ok", "✅ 安装成功，iLongRun 已准备就绪。"))
    elif command_ready:
        print(tone("warn", "✅ 安装已经完成，但还有少量环境提醒；按上面的引导先跑 `ilongrun-doctor` 看详情即可。"))
    else:
        print(tone("warn", "⚠️ 安装已执行，但仍有命令未就绪；建议先执行 `ilongrun-doctor` 排查。"))
    print("")
    print(ad_box("iLongRun - 由 zscc.in 知识船仓·公益社区 倾力制作～\n欢迎加入我们，这里是终身学习者的后花园"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
