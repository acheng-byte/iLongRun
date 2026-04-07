#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import (  # noqa: E402
    ACTIVE_WORKSTREAM_STATUSES,
    COMPLETE_WORKSTREAM_STATUSES,
    active_run_file,
    completion_path,
    compute_completion_score,
    delivery_audit_path,
    ensure_scheduler_defaults,
    final_review_path,
    adjudication_path,
    journal_path,
    load_model_config,
    projection_log_path,
    read_json,
    read_text,
    resolve_run_target,
    scheduler_uses_fleet_runtime,
    scheduler_path,
)
from _ilongrun_delivery_audit import scan_workspace_delivery_gaps  # noqa: E402
from _ilongrun_shared import display_model_name, parse_iso  # noqa: E402
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
    "complete": "已完成",
    "completed": "已完成",
    "done": "已完成",
    "running": "进行中",
    "pending": "待处理",
    "blocked": "已阻塞",
    "failed": "失败",
    "passed": "已通过",
    "verified": "已验证",
    "not-required": "不适用",
    "unknown": "未知",
    "written": "已写入",
}
MODE_LABELS = {
    "direct-lane": "直连模式",
    "wave-swarm": "波次蜂群",
    "super-swarm": "超级蜂群",
    "fleet-governor": "舰队治理",
    "fleet-dispatch": "舰队分发",
    "sentinel-watch": "哨兵观察",
    "complete-and-exit": "完成后退出",
}
PROFILE_LABELS = {
    "coding": "编码",
    "office": "办公",
    "research": "研究",
}
CONTROL_LABELS = {
    "launcher-enforced": "启动器强制",
    "session-inherited": "会话继承",
}
BACKEND_LABELS = {
    "internal": "🏠 内部执行",
    "fleet": "🚀 舰队执行",
}
VERDICT_LABELS = {
    "prototype-ready": "原型可交付",
    "prototype-risk": "原型存在风险",
    "implemented-not-wired": "已实现但未接主链",
    "implemented-not-validated": "已接线但验证不足",
    "blocked": "当前被阻断",
}
PHASE_LABELS = {
    "phase-strategy": "策略制定",
    "phase-define-plan": "定义与规划",
    "phase-build": "构建",
    "phase-core-infra": "核心基础设施",
    "phase-mvp-loop": "MVP 主循环",
    "phase-procedural-gen": "程序化生成",
    "phase-skill-system": "技能系统",
    "phase-ghost-bot": "幽灵与 Bot",
    "phase-polish": "打磨与集成",
    "phase-verify": "验证",
    "phase-review": "评审",
    "phase-audit": "最终审查",
    "phase-finalize": "收尾",
}


def zh(mapping: dict[str, str], raw: str | None, fallback: str = "无") -> str:
    value = str(raw or "").strip()
    return mapping.get(value, value or fallback)


def tone(kind: str, text: str) -> str:
    return paint(text, PALETTE[kind], BOLD)


def status_emoji(raw: str | None) -> str:
    value = str(raw or "").lower()
    if value in {"complete", "completed", "done", "passed", "verified"}:
        return "✅"
    if value in {"blocked", "failed"}:
        return "⛔"
    if value in {"running", "in-progress", "active"}:
        return "🔄"
    if value in {"pending"}:
        return "⏳"
    return "➖"


def tone_status(raw: str | None) -> str:
    value = str(raw or "").lower()
    label = zh(STATE_LABELS, value, fallback=value or "无")
    if value in {"complete", "completed", "done", "passed", "verified"}:
        return tone("ok", f"{status_emoji(value)} {label}")
    if value in {"blocked", "failed"}:
        return tone("err", f"{status_emoji(value)} {label}")
    if value in {"pending"}:
        return tone("warn", f"{status_emoji(value)} {label}")
    return tone("bright", f"{status_emoji(value)} {label}")


def backend_badge(raw: str | None) -> str:
    value = str(raw or "").lower()
    return paint(zh(BACKEND_LABELS, value, fallback=value or "无"), PALETTE["soft"], BOLD)


def progress_bar(done: int, total: int, width: int = 20) -> str:
    total = max(total, 1)
    done = min(max(done, 0), total)
    filled = round(done * width / total)
    return f"{'█' * filled}{'░' * (width - filled)} {round(done * 100 / total)}% ({done}/{total})"


def workstream_done(status: str | None) -> bool:
    return str(status or "").lower() in COMPLETE_WORKSTREAM_STATUSES


def workstream_active(status: str | None) -> bool:
    return str(status or "").lower() in ACTIVE_WORKSTREAM_STATUSES


def compute_snapshot(sched: dict[str, Any], target) -> dict[str, Any]:
    workstreams = sched.get("workstreams") or []
    ws_map = {item.get("id"): item for item in workstreams}
    completed_ws = [ws for ws in workstreams if workstream_done(ws.get("status"))]
    active_ws = [ws for ws in workstreams if workstream_active(ws.get("status"))]

    phase_rows: list[dict[str, Any]] = []
    for phase in sched.get("phases") or []:
        waves = phase.get("waves") or []
        ws_ids = [ws_id for wave in waves for ws_id in wave.get("workstreams") or []]
        total = len(ws_ids)
        done = sum(1 for ws_id in ws_ids if workstream_done((ws_map.get(ws_id) or {}).get("status")))
        phase_rows.append(
            {
                "id": phase.get("id"),
                "name": phase.get("name"),
                "status": phase.get("status"),
                "waveCount": len(waves),
                "done": done,
                "total": total,
                "waves": waves,
            }
        )

    review_exists = final_review_path(target).exists()
    adjudication_exists = adjudication_path(target).exists()
    completion_exists = completion_path(target).exists()
    active_pointer = read_text(active_run_file(target.base), "").strip()
    verification = sched.get("verification") or {}
    completion_score = verification.get("completionScore") or {}
    delivery_audit_file = delivery_audit_path(target)
    delivery_audit_exists = delivery_audit_file.exists()

    risks = []
    for item in verification.get("hardFailures") or []:
        risks.append(f"硬失败：{item}")
    for item in verification.get("driftFindings") or []:
        risks.append(f"漂移：{item}")
    for item in verification.get("softWarnings") or []:
        risks.append(f"警告：{item}")
    if active_pointer and active_pointer == target.run_id and str(sched.get("state") or "").lower() in {"complete", "completed", "blocked"}:
        risks.append("active-run-id 仍指向当前已完成/阻塞 run")
    if str(sched.get("state") or "").lower() in {"complete", "completed"} and not completion_exists:
        risks.append("scheduler 已完成但 COMPLETION.md 缺失")

    next_steps: list[str] = []
    if verification.get("recommendedAction"):
        next_steps.append(str(verification.get("recommendedAction")))
    verdict = str(completion_score.get("deliveryVerdict") or "").strip()
    if verdict == "implemented-not-wired":
        next_steps.append("优先查看 `reviews/delivery-audit.md`，把未接主链模块真正接入入口链。")
    elif verdict == "implemented-not-validated":
        next_steps.append("优先补运行态验证与终审证据，避免只停留在静态通过。")
    if not review_exists and sched.get("profile") == "coding":
        next_steps.append("补齐 `reviews/gpt54-final-review.md`。")
    if not adjudication_exists and sched.get("profile") == "coding":
        next_steps.append("补齐 `reviews/adjudication.md`。")
    if not completion_score:
        next_steps.append("先执行一次 verify/finalize，生成最新 completion score。")
    if not next_steps:
        if str(sched.get("state") or "").lower() in {"complete", "completed"} and not risks:
            next_steps.append("当前 run 已稳定完成，可归档或进入下一轮任务。")
        else:
            next_steps.append("继续通过 `ilongrun-resume <run-id>` 收敛剩余问题。")

    if not completion_score and str(sched.get("profile") or "") == "coding":
        delivery_audit = scan_workspace_delivery_gaps(target.workspace)
        completion_score = compute_completion_score(
            target,
            sched,
            hard_failures=[str(item) for item in verification.get("hardFailures") or []],
            drift_findings=[str(item) for item in verification.get("driftFindings") or []],
            delivery_audit=delivery_audit,
        )

    has_fleet_wave = scheduler_uses_fleet_runtime(sched)
    runtime = sched.get("runtime") or {}
    fleet_capability = runtime.get("fleetCapability") or {}
    fleet_dispatch = runtime.get("fleetDispatch") or {}

    recent_ledger_event = None
    journal = journal_path(target)
    if journal.exists():
        lines = [line for line in journal.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        for line in reversed(lines[-40:]):
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("event") == "ledger-sync":
                recent_ledger_event = payload
                break
    recent_projection_event = None
    projection_log = projection_log_path(target)
    projection_events = 0
    if projection_log.exists():
        lines = [line for line in projection_log.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        projection_events = len(lines)
        for line in reversed(lines[-40:]):
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("event") == "projection-sync":
                recent_projection_event = payload
                break

    return {
        "completedWorkstreams": len(completed_ws),
        "totalWorkstreams": len(workstreams),
        "activeWorkstreams": len(active_ws),
        "phaseRows": phase_rows,
        "reviewExists": review_exists,
        "adjudicationExists": adjudication_exists,
        "completionExists": completion_exists,
        "activePointer": active_pointer,
        "deliveryAuditExists": delivery_audit_exists,
        "deliveryAuditPath": str(delivery_audit_file),
        "completionScore": completion_score,
        "risks": risks,
        "nextSteps": next_steps[:4],
        "hasFleetWave": has_fleet_wave,
        "fleetCapability": fleet_capability,
        "fleetDispatch": fleet_dispatch,
        "recentLedgerEvent": recent_ledger_event,
        "recentProjectionEvent": recent_projection_event,
        "projectionEventCount": projection_events,
    }


def final_verdict(sched: dict[str, Any], snapshot: dict[str, Any]) -> str:
    state = str(sched.get("state") or "").lower()
    verification = sched.get("verification") or {}
    if verification.get("hardFailures") or state in {"blocked", "failed"}:
        return tone("err", "已阻塞")
    if state in {"complete", "completed"} and not snapshot.get("risks"):
        return tone("ok", "已完成")
    if snapshot.get("completionScore"):
        verdict = zh(VERDICT_LABELS, (snapshot.get("completionScore") or {}).get("deliveryVerdict"), fallback="可继续")
        return tone("warn" if "未" in verdict or "风险" in verdict else "bright", verdict)
    return tone("bright", "可继续")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render deterministic ILongRun status board")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--model-config")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    sched = ensure_scheduler_defaults(read_json(scheduler_path(target), {}))
    config = load_model_config(args.model_config)
    snapshot = compute_snapshot(sched, target)
    verification = sched.get("verification") or {}
    reviews = sched.get("reviews") or {}
    projection = sched.get("projectionState") or {}
    score = snapshot.get("completionScore") or {}

    print(open_top(board_title("🧭", "状态看板"), tail_width=28))
    print(left_border())
    print(board_line("🆔 运行 ID", tone("soft", target.run_id)))
    print(board_line("📊 当前状态", tone_status(sched.get("state"))))
    print(board_line("🎯 当前阶段", tone("soft", zh(PHASE_LABELS, sched.get("phase"), fallback=str(sched.get("phase") or "无")))))
    print(board_line("🔧 运行模式", tone("warm", zh(MODE_LABELS, sched.get("mode"), fallback=str(sched.get("mode") or "无")))))
    print(board_line("🌐 任务画像", tone("warm", zh(PROFILE_LABELS, sched.get("profile"), fallback=str(sched.get("profile") or "无")))))
    print(board_line("🤖 执行模型", tone("bright", display_model_name(sched.get("selectedModel") or "unknown", config))))
    print(board_line("🔑 控制模式", tone("soft", zh(CONTROL_LABELS, sched.get("modelControlMode"), fallback=str(sched.get("modelControlMode") or "无")))))
    print(board_line("🕐 最近更新", tone("soft", str(sched.get("updatedAt") or "无"))))
    print(left_border())
    print(open_bottom())
    print("")

    print(section_heading("📈 真实完成度"))
    print(section_rule())
    if score:
        print(detail_line("总分", tone("bright", f"{score.get('overall')} / 100  等级 {score.get('grade')}")))
        print(detail_line("交付判定", tone("warn" if score.get("deliveryVerdict") != "prototype-ready" else "ok", zh(VERDICT_LABELS, score.get("deliveryVerdict"), fallback=str(score.get("deliveryVerdict") or "无")))))
        layers = score.get("layers") or {}
        for label, key in [("代码存在", "codeExists"), ("主链接线", "wiredIntoEntry"), ("测试证据", "tested"), ("运行验证", "runtimeValidated")]:
            layer = layers.get(key) or {}
            print(detail_line(label, f"{progress_bar(int(layer.get('score') or 0), 100)}"))
    else:
        print("  - 尚未生成 completion score。")
    print("")

    print(section_heading("📋 阶段进度"))
    print(section_rule())
    phase_rows = snapshot.get("phaseRows") or []
    for row in phase_rows:
        label = zh(PHASE_LABELS, row.get("id"), fallback=row.get("name") or str(row.get("id") or "未命名阶段"))
        print(f"  {status_emoji(row.get('status'))} {label}  {tone_status(row.get('status'))}  [{row.get('waveCount', 0)} 个波次]")
    done_phases = sum(1 for row in phase_rows if str(row.get("status") or "").lower() == "complete")
    print(f"  {progress_bar(done_phases, len(phase_rows) or 1)}")
    print("")

    print(section_heading("🌊 波次详情"))
    print(section_rule())
    for row in phase_rows:
        label = zh(PHASE_LABELS, row.get("id"), fallback=row.get("name") or str(row.get("id") or "未命名阶段"))
        print(f"  📌 阶段：{label}")
        waves = row.get("waves") or []
        if not waves:
            print("    └── 无")
            continue
        for index, wave in enumerate(waves):
            branch = "└──" if index == len(waves) - 1 else "├──"
            child_prefix = "    " if index == len(waves) - 1 else "│   "
            ws_ids = ", ".join(str(item) for item in wave.get("workstreams") or []) or "无"
            print(f"    {branch} {wave.get('id')}  {backend_badge(wave.get('backend'))}  {tone_status(wave.get('status'))}")
            print(f"    {child_prefix}└── 工作流：{ws_ids}")
    print("")

    print(section_heading("⚡ 工作流进度"))
    print(section_rule())
    workstreams = sched.get("workstreams") or []
    for ws in workstreams[:12]:
        owner = f"{ws.get('ownerRole') or 'unknown'}"
        print(f"  {status_emoji(ws.get('status'))} {ws.get('id')}  {ws.get('name')}  {backend_badge(ws.get('backend'))}  {owner}")
    if len(workstreams) > 12:
        print(f"  … 其余 {len(workstreams) - 12} 个工作流省略")
    print(f"  {progress_bar(int(snapshot.get('completedWorkstreams') or 0), int(snapshot.get('totalWorkstreams') or 1))}")
    print("")

    if str(sched.get("profile") or "") == "coding":
        print(section_heading("🔒 质量门禁"))
        print(section_rule())
        review_gate = "待终审"
        if reviews.get("pendingMustFixCount"):
            review_gate = f"需返工（must-fix {reviews.get('pendingMustFixCount')}）"
        elif reviews.get("status") in {"passed", "not-required"} and snapshot.get("reviewExists"):
            review_gate = "已通过"
        elif snapshot.get("reviewExists"):
            review_gate = "已生成"
        print(detail_line("代码审查", tone_status(reviews.get("status"))))
        print(detail_line("最终终审", tone("warn" if "返工" in review_gate or "待" in review_gate else "ok", review_gate)))
        print(detail_line("裁决", tone("ok" if snapshot.get("adjudicationExists") else "warn", "已写入" if snapshot.get("adjudicationExists") else "未写入")))
        print(detail_line("必须修复", tone("err" if int(reviews.get("pendingMustFixCount") or 0) > 0 else "ok", f"{int(reviews.get('pendingMustFixCount') or 0)} 项")))
        print("")

    print(section_heading("🛡️ 验证状态"))
    print(section_rule())
    print(detail_line("状态", tone_status(verification.get("state"))))
    print(detail_line("失败分类", tone("soft", str(verification.get("failureClass") or "无"))))
    print(detail_line("建议动作", tone("soft", str(verification.get("recommendedAction") or "无"))))
    print(detail_line("最近验证", tone("soft", str(verification.get("lastVerifiedAt") or "尚未验证"))))
    last_error = sched.get("lastError")
    if isinstance(last_error, dict):
        last_error_text = str(last_error.get("message") or json.dumps(last_error, ensure_ascii=False))
    else:
        last_error_text = str(last_error or "无")
    print(detail_line("最近错误", tone("soft", last_error_text)))
    print("")

    print(section_heading("🧾 账本与投影"))
    print(section_rule())
    print(detail_line("task-list 数", tone("soft", str(len(sched.get("taskLists") or [])))))
    print(detail_line("投影同步", tone("soft", str(projection.get("taskListsSyncedAt") or "无"))))
    print(detail_line("账本同步", tone("soft", f"{projection.get('ledgerSyncedAt') or '无'} / {projection.get('ledgerSyncActor') or 'unknown'} / {projection.get('ledgerSyncReason') or 'unknown'}")))
    print(detail_line("账本验证", tone("soft", f"{projection.get('lastLedgerVerificationState') or 'pending'} @ {projection.get('ledgerVerifiedAt') or '无'}")))
    print(detail_line("active 指针", tone("warn" if snapshot.get("activePointer") == target.run_id else "soft", snapshot.get("activePointer") or "none")))
    if snapshot.get("recentLedgerEvent"):
        event = snapshot["recentLedgerEvent"]
        payload = event.get("payload") or {}
        print(detail_line("最近同步事件", tone("soft", f"{event.get('ts') or '无'} / {payload.get('reason') or 'unknown'} / state={payload.get('state') or 'unknown'}")))
    if snapshot.get("recentProjectionEvent"):
        event = snapshot["recentProjectionEvent"]
        payload = event.get("payload") or {}
        projected_paths = list(payload.get("projectedPaths") or [])
        print(detail_line("投影日志", tone("soft", f"{snapshot.get('projectionEventCount') or 0} 条 / reason={payload.get('reason') or 'unknown'} / drift={payload.get('driftCount') or 0}")))
        if projected_paths:
            preview = ", ".join(projected_paths[:3])
            if len(projected_paths) > 3:
                preview += f" …(+{len(projected_paths) - 3})"
            print(detail_line("最近改写", tone("soft", preview)))
    print("")

    if snapshot.get("hasFleetWave") or str((snapshot.get("fleetCapability") or {}).get("status") or "") != "unknown":
        print(section_heading("🚢 舰队运行态"))
        print(section_rule())
        capability = snapshot.get("fleetCapability") or {}
        dispatch = snapshot.get("fleetDispatch") or {}
        print(detail_line("能力状态", tone("soft", f"{capability.get('status') or 'unknown'} ({capability.get('reason') or 'not-probed'})")))
        probe_model = capability.get("probeModelDisplay") or capability.get("probeModel") or "无"
        print(detail_line("探测模型", tone("soft", str(probe_model))))
        print(detail_line("探测时间", tone("soft", str(capability.get("checkedAt") or "无"))))
        degraded = ", ".join(str(item) for item in dispatch.get("degradedWaves") or []) or "无"
        completed = ", ".join(str(item) for item in dispatch.get("completedWaves") or []) or "无"
        print(detail_line("降级波次", tone("warn", degraded) if degraded != "无" else tone("soft", degraded)))
        print(detail_line("完成波次", tone("soft", completed)))
        print(detail_line("最近分发", tone("soft", str(dispatch.get("lastDispatchedWave") or "无"))))
        print(detail_line("最近结果", tone("soft", f"{dispatch.get('lastOutcome') or '无'} @ {dispatch.get('lastOutcomeAt') or '无'}")))
        dispatch_events = list(dispatch.get("dispatchEvents") or [])
        print(detail_line("分发证据", tone("soft", f"{len(dispatch_events)} 条")))
        for event in dispatch_events[-2:]:
            summary = f"{event.get('waveId') or 'unknown'} / {event.get('outcome') or 'unknown'} / {event.get('reason') or 'n/a'}"
            print(detail_line("事件", tone("soft", summary)))
        print("")

    print(section_heading("⚠️ 阻塞 / 风险"))
    print(section_rule())
    risks = snapshot.get("risks") or []
    if risks:
        for item in risks[:8]:
            print(f"  - {item}")
        if len(risks) > 8:
            print(f"  - … 其余 {len(risks) - 8} 项省略")
    else:
        print("  （无阻塞）")
    if snapshot.get("deliveryAuditExists"):
        print(f"  - 交付审计：`{snapshot.get('deliveryAuditPath')}`")
    print("")

    print(section_heading("💡 下一步建议"))
    print(section_rule())
    for item in snapshot.get("nextSteps") or ["继续观察当前 run 状态。"]:
        print(f"  - {item}")
    print("")

    print(f"{section_heading('📌 最终判定')}：{final_verdict(sched, snapshot)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
