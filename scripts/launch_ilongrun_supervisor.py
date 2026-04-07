#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _ilongrun_lib import (
    final_review_path,
    journal_path,
    load_model_config,
    persist_run_ledger,
    read_model_availability_for_ilongrun,
    reconcile_scheduler,
    resolve_run_target,
    runnable_fleet_waves,
    scheduler_path,
    verify_scheduler,
)
from _ilongrun_shared import (
    append_jsonl,
    classify_failure,
    display_model_name,
    extract_rate_limit,
    model_availability_snapshot,
    model_chain,
    now_iso,
    read_json,
    validate_model_config,
)

MODEL_FALLBACK_PATTERNS = [
    ("model-unavailable", "unknown model"),
    ("model-unavailable", "invalid model"),
    ("model-unavailable", "from --model flag is not available"),
    ("model-unavailable", "not available to your account"),
    ("model-unavailable", "you do not have access"),
    ("model-unavailable", "cannot use model"),
    ("model-unavailable", "model is not supported"),
    ("rate-limited", "user_model_rate_limited"),
]
FLEET_UNSUPPORTED_SNIPPETS = [
    "unknown command",
    "invalid command",
    "unrecognized command",
    "unknown slash command",
    "not a valid command",
]


def record_fleet_dispatch_event(
    sched: dict[str, object],
    *,
    wave_id: str,
    outcome: str,
    reason: str,
    model: str | None = None,
    rc: int | None = None,
    fallback_reason: str | None = None,
    backend_before: str | None = None,
    backend_after: str | None = None,
) -> None:
    runtime = sched.get("runtime") or {}
    fleet_dispatch = runtime.get("fleetDispatch") or {}
    events = list(fleet_dispatch.get("dispatchEvents") or [])
    observed_at = now_iso()
    record = {
        "waveId": wave_id,
        "outcome": outcome,
        "reason": reason,
        "observedAt": observed_at,
        "model": model,
        "rc": rc,
        "fallbackReason": fallback_reason,
        "backendBefore": backend_before,
        "backendAfter": backend_after,
    }
    events.append({key: value for key, value in record.items() if value not in {None, ""}})
    fleet_dispatch["dispatchEvents"] = events[-24:]
    fleet_dispatch["lastDispatchedWave"] = wave_id
    fleet_dispatch["lastOutcome"] = outcome
    fleet_dispatch["lastOutcomeAt"] = observed_at
    runtime["fleetDispatch"] = fleet_dispatch
    sched["runtime"] = runtime


def build_command(args, skill_ref: str, payload: str, model: str) -> list[str]:
    cmd = [args.copilot_bin]
    for item in args.plugin_arg:
        cmd.extend(["--plugin-dir", item])
    if args.mode in {"run", "resume"}:
        cmd.extend(["--autopilot", "--yolo", "--no-ask-user", "--max-autopilot-continues", str(args.max_continues)])
    else:
        cmd.extend(["--yolo", "--no-ask-user"])
    cmd.extend(["--model", model, "-p", f"{skill_ref} {payload}".strip()])
    return cmd


def resolved_run_paths(args, workspace: Path, run_ref: str) -> dict[str, str]:
    target = resolve_run_target(workspace, run_ref)
    return {
        "runDir": args.target_run_dir or str(target.run_dir),
        "schedulerPath": args.target_scheduler_path or str(scheduler_path(target)),
        "workstreamsDir": args.target_workstreams_dir or str(target.run_dir / "workstreams"),
    }


def run_and_stream(cmd: list[str], cwd: Path, env_patch: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    if env_patch:
        env.update(env_patch)
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )
    chunks: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        chunks.append(line)
    rc = process.wait()
    return rc, "".join(chunks)


def detect_fallback_reason(output: str) -> str | None:
    lowered = output.lower()
    if extract_rate_limit(output):
        return "rate-limited"
    for reason, snippet in MODEL_FALLBACK_PATTERNS:
        if snippet in lowered:
            return reason
    return None


def append_journal_event(workspace: Path, run_ref: str | None, event: str, payload: dict[str, object]) -> None:
    if not run_ref:
        return
    try:
        target = resolve_run_target(workspace, run_ref)
    except Exception:
        return
    append_jsonl(journal_path(target), {"ts": now_iso(), "source": "supervisor", "event": event, "payload": payload})


def build_fleet_command(args, prompt: str, model: str) -> list[str]:
    cmd = [args.copilot_bin]
    for item in args.plugin_arg:
        cmd.extend(["--plugin-dir", item])
    cmd.extend(["--autopilot", "--yolo", "--no-ask-user", "--max-autopilot-continues", str(args.max_continues)])
    cmd.extend(["--model", model, "-p", prompt])
    return cmd


def probe_fleet_capability(args, model: str) -> dict[str, object]:
    probe = SCRIPT_DIR / "probe_fleet_capability.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(probe),
            "--copilot-bin", args.copilot_bin,
            "--model-config", args.model_config,
            "--availability-cache", args.availability_cache,
            "--model", model,
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        if proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass
    return {"ok": False, "status": "unknown", "reason": f"probe-exit-{proc.returncode}", "rawOutput": proc.stdout or proc.stderr}


def set_wave_backend(
    workspace: Path,
    run_ref: str,
    wave_id: str,
    backend: str,
    reason: str,
    dispatch_key: str,
    *,
    outcome: str | None = None,
    model: str | None = None,
    rc: int | None = None,
    fallback_reason: str | None = None,
) -> None:
    target = resolve_run_target(workspace, run_ref)
    sched = reconcile_scheduler(target)
    previous_backend = None
    for phase in sched.get("phases") or []:
        for wave in phase.get("waves") or []:
            if wave.get("id") == wave_id:
                previous_backend = str(wave.get("backend") or "")
                wave["backend"] = backend
                wave["reason"] = reason
                break
    runtime = sched.get("runtime") or {}
    fleet_dispatch = runtime.get("fleetDispatch") or {}
    history = list(fleet_dispatch.get(dispatch_key) or [])
    if wave_id not in history:
        history.append(wave_id)
    fleet_dispatch[dispatch_key] = history
    fleet_dispatch["lastDispatchedWave"] = wave_id
    runtime["fleetDispatch"] = fleet_dispatch
    sched["runtime"] = runtime
    record_fleet_dispatch_event(
        sched,
        wave_id=wave_id,
        outcome=outcome or ("completed" if dispatch_key == "completedWaves" else "degraded"),
        reason=reason,
        model=model,
        rc=rc,
        fallback_reason=fallback_reason,
        backend_before=previous_backend,
        backend_after=backend,
    )
    persist_run_ledger(
        target,
        sched,
        reason=f"fleet-wave-backend:{wave_id}:{backend}",
        actor="ledger-syncer",
    )


def update_fleet_runtime(workspace: Path, run_ref: str, probe_result: dict[str, object]) -> None:
    if not run_ref:
        return
    try:
        target = resolve_run_target(workspace, run_ref)
    except Exception:
        return
    sched = reconcile_scheduler(target)
    runtime = sched.get("runtime") or {}
    raw_output = str(probe_result.get("rawOutput") or "")
    runtime["fleetCapability"] = {
        "status": probe_result.get("status", "unknown"),
        "reason": probe_result.get("reason", "not-probed"),
        "checkedAt": probe_result.get("checkedAt"),
        "probeModel": probe_result.get("probeModel"),
        "probeModelDisplay": probe_result.get("probeModelDisplay"),
        "cache": probe_result.get("cache"),
        "source": "probe_fleet_capability.py",
        "checkedBy": "launch_ilongrun_supervisor.py",
        "rawOutputDigest": hashlib.sha256(raw_output.encode("utf-8")).hexdigest()[:16] if raw_output else None,
    }
    sched["runtime"] = runtime
    persist_run_ledger(
        target,
        sched,
        reason="fleet-runtime-updated",
        actor="ledger-syncer",
    )


def mark_fleet_dispatch_started(workspace: Path, run_ref: str, wave_id: str, model: str) -> None:
    target = resolve_run_target(workspace, run_ref)
    sched = reconcile_scheduler(target)
    current_backend = None
    for phase in sched.get("phases") or []:
        for wave in phase.get("waves") or []:
            if wave.get("id") == wave_id:
                current_backend = str(wave.get("backend") or "")
                break
    record_fleet_dispatch_event(
        sched,
        wave_id=wave_id,
        outcome="dispatch-started",
        reason="supervisor started fleet wave dispatch",
        model=model,
        backend_before=current_backend,
        backend_after=current_backend,
    )
    persist_run_ledger(
        target,
        sched,
        reason=f"fleet-dispatch-start:{wave_id}",
        actor="ledger-syncer",
    )


def build_fleet_wave_prompt(run_ref: str, wave: dict[str, object], workstreams: list[dict[str, object]]) -> str:
    lines = [
        "/fleet Execute the pending ILongRun wave below.",
        "",
        "[ILongRun fleet adapter context]",
        f"Run ID: {run_ref}",
        f"Wave ID: {wave.get('id')}",
        "Only execute the listed workstreams.",
        "Update each workstream's result.md, evidence.md, and status.json.",
        "Do not finalize the whole mission.",
        "Do not mint a new run-id.",
        "[/ILongRun fleet adapter context]",
        "",
        "Workstreams:",
    ]
    for ws in workstreams:
        deps = ", ".join(ws.get("dependencies") or []) or "none"
        lines.extend([
            f"- {ws.get('id')} / {ws.get('name')}",
            f"  - Goal: {ws.get('goal')}",
            f"  - Dependencies: {deps}",
            f"  - Result path: {ws.get('resultPath')}",
            f"  - Evidence path: {ws.get('evidencePath')}",
            f"  - Status path: {ws.get('statusPath')}",
        ])
    lines.extend([
        "",
        "完成后仅输出一段简短 summary，并确保文件已经落盘。",
    ])
    return "\n".join(lines)


def dispatch_fleet_waves(args, workspace: Path, run_ref: str, model: str) -> bool:
    target = resolve_run_target(workspace, run_ref)
    paths = resolved_run_paths(args, workspace, run_ref)
    sched = reconcile_scheduler(target)
    pending = runnable_fleet_waves(sched)
    if not pending:
        return False
    probe_result = probe_fleet_capability(args, model)
    update_fleet_runtime(workspace, run_ref, probe_result)
    append_journal_event(workspace, run_ref, "fleet-probe", probe_result)
    if probe_result.get("status") != "supported":
        for item in pending:
            wave = item["wave"]
            reason = f"/fleet unavailable; downgraded to internal ({probe_result.get('reason', 'unknown')})"
            set_wave_backend(
                workspace,
                run_ref,
                str(wave.get("id")),
                "internal",
                reason,
                "degradedWaves",
                outcome="degraded",
                model=model,
                fallback_reason=str(probe_result.get("reason") or "unknown"),
            )
            append_journal_event(workspace, run_ref, "fleet-degraded", {"waveId": wave.get("id"), "reason": reason})
        return True

    changed = False
    for item in pending:
        wave = item["wave"]
        workstreams = item["workstreams"]
        prompt = build_fleet_wave_prompt(run_ref, wave, workstreams)
        cmd = build_fleet_command(args, prompt, model)
        mark_fleet_dispatch_started(workspace, run_ref, str(wave.get("id")), model)
        rc, output = run_and_stream(cmd, workspace, {
            "LONGRUN_SELECTED_MODEL": model,
            "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
            "LONGRUN_RUN_ID": run_ref,
            "LONGRUN_RUN_DIR": paths["runDir"],
            "LONGRUN_SCHEDULER_PATH": paths["schedulerPath"],
            "LONGRUN_WORKSTREAMS_DIR": paths["workstreamsDir"],
            "LONGRUN_LAUNCH_MODE": "ilongrun-fleet-wave",
            "ILONGRUN_FLEET_EXECUTION": "1",
            "ILONGRUN_FLEET_WAVE_ID": str(wave.get("id")),
        })
        lowered = output.lower()
        unsupported = any(snippet in lowered for snippet in FLEET_UNSUPPORTED_SNIPPETS)
        sched = reconcile_scheduler(target)
        current_wave = next((wv for phase in sched.get("phases") or [] for wv in phase.get("waves") or [] if wv.get("id") == wave.get("id")), None)
        wave_complete = current_wave and current_wave.get("status") == "complete"
        if rc != 0 or detect_fallback_reason(output) or unsupported or not wave_complete:
            reason = "fleet wave fallback to internal"
            if unsupported:
                reason = "fleet command not recognized during wave dispatch"
            elif detect_fallback_reason(output):
                reason = f"fleet wave fallback: {detect_fallback_reason(output)}"
            elif rc != 0:
                reason = f"fleet wave exited with rc={rc}"
            set_wave_backend(
                workspace,
                run_ref,
                str(wave.get("id")),
                "internal",
                reason,
                "degradedWaves",
                outcome="degraded",
                model=model,
                rc=rc,
                fallback_reason=detect_fallback_reason(output),
            )
            append_journal_event(workspace, run_ref, "fleet-degraded", {"waveId": wave.get("id"), "reason": reason})
        else:
            set_wave_backend(
                workspace,
                run_ref,
                str(wave.get("id")),
                "fleet",
                str(wave.get("reason")),
                "completedWaves",
                outcome="completed",
                model=model,
                rc=rc,
            )
            append_journal_event(workspace, run_ref, "fleet-complete", {"waveId": wave.get("id")})
        changed = True
    return changed


def resume_after_fleet(args, workspace: Path, run_ref: str, model: str) -> bool:
    if not args.resume_skill_ref:
        return False
    paths = resolved_run_paths(args, workspace, run_ref)
    payload = run_ref
    cmd = build_command(args, args.resume_skill_ref, payload, model)
    rc, output = run_and_stream(cmd, workspace, {
        "LONGRUN_SELECTED_MODEL": model,
        "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
        "LONGRUN_RUN_ID": run_ref,
        "LONGRUN_RUN_DIR": paths["runDir"],
        "LONGRUN_SCHEDULER_PATH": paths["schedulerPath"],
        "LONGRUN_WORKSTREAMS_DIR": paths["workstreamsDir"],
        "LONGRUN_LAUNCH_MODE": "ilongrun-post-fleet-resume",
    })
    return rc == 0 and not detect_fallback_reason(output)


def patch_scheduler(workspace: Path, run_ref: str | None, *, selected_model: str | None = None, note: str | None = None, fallback_reason: str | None = None) -> None:
    if not run_ref:
        return
    try:
        target = resolve_run_target(workspace, run_ref)
    except Exception:
        return
    sched = reconcile_scheduler(target)
    if selected_model:
        sched["selectedModel"] = selected_model
        sched["modelControlMode"] = "launcher-enforced"
        history = list(sched.get("modelAttemptHistory") or [])
        history.append({
            "ts": now_iso(),
            "model": selected_model,
            "reason": fallback_reason or note or "launcher-attempt",
        })
        sched["modelAttemptHistory"] = history[-12:]
    if fallback_reason:
        sched["fallbackReason"] = fallback_reason
    sync_reason = "launcher-scheduler-patch"
    if fallback_reason:
        sync_reason = f"launcher-fallback:{fallback_reason}"
    elif selected_model:
        sync_reason = f"launcher-model-selected:{selected_model}"
    persist_run_ledger(
        target,
        sched,
        reason=sync_reason,
        actor="ledger-syncer",
    )


def notify_event(workspace: Path, run_ref: str | None, event: str, *, title: str, subtitle: str, message: str, sound: bool = False) -> None:
    helper = SCRIPT_DIR / "notify_macos.py"
    if not helper.exists():
        return
    cmd = [
        sys.executable,
        str(helper),
        "--workspace", str(workspace),
        "--event", event,
        "--title", title,
        "--subtitle", subtitle,
        "--message", message,
    ]
    if run_ref:
        cmd.extend(["--run-id", run_ref])
    if sound:
        cmd.append("--sound")
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def maybe_finalize_complete(workspace: Path, run_ref: str) -> bool:
    try:
        target = resolve_run_target(workspace, run_ref)
    except Exception:
        return False
    sched = reconcile_scheduler(target)
    verification = verify_scheduler(target, sched)
    if not verification.get("ok"):
        return False
    finalize = SCRIPT_DIR / "finalize_ilongrun_run.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(finalize),
            "--workspace", str(workspace),
            "--run-id", run_ref,
            "--status", "complete",
            "--headline", "ILongRun auto-finalized after verification",
            "--local-verify",
        ],
        check=False,
    )
    return proc.returncode == 0


def maybe_finalize_blocked(workspace: Path, run_ref: str, note: str) -> None:
    finalize = SCRIPT_DIR / "finalize_ilongrun_run.py"
    subprocess.run(
        [
            sys.executable,
            str(finalize),
            "--workspace", str(workspace),
            "--run-id", run_ref,
            "--status", "blocked",
            "--headline", note,
            "--blocker", note,
        ],
        check=False,
    )


def maybe_run_gpt54_audit(args, workspace: Path, run_ref: str) -> bool:
    target = resolve_run_target(workspace, run_ref)
    paths = resolved_run_paths(args, workspace, run_ref)
    sched = reconcile_scheduler(target)
    if sched.get("profile") != "coding":
        return True
    if final_review_path(target).exists() and final_review_path(target).stat().st_size > 0:
        return True
    audit_model = load_model_config(args.model_config).get("codingAuditModel", "gpt-5.4")
    print(f"[ILongRun] pending coding audit; starting final audit pass ({display_model_name(audit_model, load_model_config(args.model_config))} / {audit_model})")
    payload = (
        "[ILongRun supervisor context]\n"
        f"Resume existing run-id: {run_ref}\n"
        f"Canonical run dir: {paths['runDir']}\n"
        f"Canonical scheduler path: {paths['schedulerPath']}\n"
        f"Canonical workstreams dir: {paths['workstreamsDir']}\n"
        f"Perform pending final audit only with `{audit_model}`.\n"
        "Do not mint a new run.\n"
        "[/ILongRun supervisor context]\n\n"
        f"{run_ref}"
    )
    cmd = build_command(args, args.resume_skill_ref or args.skill_ref, payload, audit_model)
    rc, output = run_and_stream(cmd, workspace, {
        "LONGRUN_SELECTED_MODEL": audit_model,
        "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
        "LONGRUN_RUN_ID": run_ref,
        "LONGRUN_RUN_DIR": paths["runDir"],
        "LONGRUN_SCHEDULER_PATH": paths["schedulerPath"],
        "LONGRUN_WORKSTREAMS_DIR": paths["workstreamsDir"],
        "LONGRUN_LAUNCH_MODE": "ilongrun-final-audit",
        "ILONGRUN_FORCE_AUDIT": "1",
    })
    if rc != 0:
        print("[ILongRun] final audit pass failed", file=sys.stderr)
        return False
    if detect_fallback_reason(output):
        return False
    refreshed = reconcile_scheduler(target)
    persist_run_ledger(
        target,
        refreshed,
        reason="final-audit-refresh",
        actor="ledger-syncer",
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="ILongRun Copilot supervisor with model fallback")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--copilot-bin", required=True)
    parser.add_argument("--mode", choices=["run", "resume", "prompt", "status"], required=True)
    parser.add_argument("--skill-ref", required=True)
    parser.add_argument("--resume-skill-ref", default="")
    parser.add_argument("--payload", required=True)
    parser.add_argument("--max-continues", default="100")
    parser.add_argument("--explicit-model")
    parser.add_argument("--model-config")
    parser.add_argument("--availability-cache")
    parser.add_argument("--target-run-id", default="")
    parser.add_argument("--target-run-dir", default="")
    parser.add_argument("--target-scheduler-path", default="")
    parser.add_argument("--target-workstreams-dir", default="")
    parser.add_argument("--force-profile", choices=["coding", "research", "office"])
    parser.add_argument("--plugin-arg", action="append", default=[])
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    config = load_model_config(args.model_config)
    errors = validate_model_config(config)
    if errors:
        for error in errors:
            print(f"[model-config-error] {error}", file=sys.stderr)
        return 2

    availability_cache = read_model_availability_for_ilongrun(args.availability_cache)
    availability = model_availability_snapshot(config, cache=availability_cache)
    chain = model_chain(config, explicit_model=args.explicit_model, prompt_text=args.payload, availability=availability)
    current_skill = args.skill_ref
    current_payload = args.payload
    run_ref = args.target_run_id or ""
    target_paths = resolved_run_paths(args, workspace, run_ref) if run_ref else {}
    if args.mode == "run" and run_ref:
        force_profile_line = ""
        if args.force_profile:
            force_profile_line = (
                f"Force mission profile: {args.force_profile}\n"
                "Treat this as that exact mission profile even if the task wording is mixed.\n"
            )
        current_payload = (
            "[ILongRun launcher context]\n"
            f"Assigned run-id: {run_ref}\n"
            "Use this exact run-id and do not mint a different run-id.\n"
            f"Canonical run dir: {target_paths.get('runDir')}\n"
            f"Canonical scheduler path: {target_paths.get('schedulerPath')}\n"
            f"Canonical workstreams dir: {target_paths.get('workstreamsDir')}\n"
            f"{force_profile_line}"
            "If any execution wave backend is `fleet`, stop after strategy/phase/workstream/task-list decomposition and wait for external supervisor dispatch.\n"
            "Do not personally execute fleet-tagged workstreams inside the primary planning pass.\n"
            "Do not create `.copilot-ilongrun/<run-id>/`; only use the canonical `runs/<run-id>/` directory.\n"
            "[/ILongRun launcher context]\n\n"
            f"{args.payload}"
        ).strip()
    elif args.mode == "resume" and run_ref:
        current_payload = (
            "[ILongRun launcher context]\n"
            f"Resume existing run-id: {run_ref}\n"
            "Continue this run and do not create a new run-id.\n"
            f"Canonical run dir: {target_paths.get('runDir')}\n"
            f"Canonical scheduler path: {target_paths.get('schedulerPath')}\n"
            f"Canonical workstreams dir: {target_paths.get('workstreamsDir')}\n"
            "Do not create `.copilot-ilongrun/<run-id>/`; only use the canonical `runs/<run-id>/` directory.\n"
            "[/ILongRun launcher context]\n\n"
            f"{args.payload}"
        ).strip()

    notified_recovery = False
    for index, model in enumerate(chain):
        human = display_model_name(model, config)
        print(f"[ILongRun] attempt {index + 1}/{len(chain)} with model: {human} ({model})")
        patch_scheduler(workspace, run_ref, selected_model=model, note="launcher-attempt")
        cmd = build_command(args, current_skill, current_payload, model)
        rc, output = run_and_stream(cmd, workspace, {
            "LONGRUN_SELECTED_MODEL": model,
            "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
            "LONGRUN_RUN_ID": run_ref,
            "LONGRUN_RUN_DIR": target_paths.get("runDir", ""),
            "LONGRUN_SCHEDULER_PATH": target_paths.get("schedulerPath", ""),
            "LONGRUN_WORKSTREAMS_DIR": target_paths.get("workstreamsDir", ""),
            "LONGRUN_LAUNCH_MODE": "ilongrun-launcher",
        })
        fallback_reason = detect_fallback_reason(output)
        if rc == 0 and not fallback_reason:
            if args.mode in {"run", "resume"} and run_ref:
                fleet_changed = dispatch_fleet_waves(args, workspace, run_ref, model)
                if fleet_changed and not resume_after_fleet(args, workspace, run_ref, model):
                    maybe_finalize_blocked(workspace, run_ref, "ILongRun post-fleet resume failed")
                    return 1
                if not maybe_run_gpt54_audit(args, workspace, run_ref):
                    maybe_finalize_blocked(workspace, run_ref, "ILongRun final audit pass failed")
                    return 1
                if maybe_finalize_complete(workspace, run_ref):
                    return 0
                verification = verify_scheduler(resolve_run_target(workspace, run_ref), read_json(scheduler_path(resolve_run_target(workspace, run_ref)), {}))
                if verification.get("ok"):
                    return 0
                maybe_finalize_blocked(workspace, run_ref, "ILongRun verification failed after execution")
                return 1
            return 0
        if not fallback_reason:
            if run_ref:
                maybe_finalize_blocked(workspace, run_ref, "ILongRun launcher run failed without model fallback")
            return rc or 1
        patch_scheduler(workspace, run_ref, selected_model=model, fallback_reason=fallback_reason)
        if not notified_recovery and args.mode in {"run", "resume"} and run_ref:
            notify_event(
                workspace,
                run_ref,
                "recovery",
                title="iLongRun 正在自己换路继续",
                subtitle="刚才那一步没有走通",
                message="现在先不用守着，iLongRun 还在继续处理。",
            )
            notified_recovery = True
        if args.mode in {"run", "resume"} and args.resume_skill_ref:
            current_skill = args.resume_skill_ref
            current_payload = run_ref or "latest"
        if index + 1 < len(chain):
            continue
        backoff_minutes = list(config.get("backoffMinutes", []))[:3]
        for backoff in backoff_minutes:
            print(f"[ILongRun] {fallback_reason}; backoff {backoff}m before retry")
            time.sleep(backoff * 60)
            retry_cmd = build_command(args, current_skill, current_payload, model)
            rc, output = run_and_stream(retry_cmd, workspace, {
                "LONGRUN_SELECTED_MODEL": model,
                "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
                "LONGRUN_RUN_ID": run_ref,
                "LONGRUN_LAUNCH_MODE": "ilongrun-backoff",
            })
            retry_reason = detect_fallback_reason(output)
            if rc == 0 and not retry_reason:
                if args.mode in {"run", "resume"} and run_ref:
                    fleet_changed = dispatch_fleet_waves(args, workspace, run_ref, model)
                    if fleet_changed and not resume_after_fleet(args, workspace, run_ref, model):
                        maybe_finalize_blocked(workspace, run_ref, "ILongRun post-fleet resume failed after retry")
                        return 1
                    if not maybe_run_gpt54_audit(args, workspace, run_ref):
                        maybe_finalize_blocked(workspace, run_ref, "ILongRun final audit pass failed after retry")
                        return 1
                    if maybe_finalize_complete(workspace, run_ref):
                        return 0
                return 0
        if run_ref:
            maybe_finalize_blocked(workspace, run_ref, f"{fallback_reason}; exhausted fallback chain and backoff budget")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
