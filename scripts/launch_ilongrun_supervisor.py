#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    read_model_availability_for_ilongrun,
    reconcile_scheduler,
    resolve_run_target,
    runnable_fleet_waves,
    scheduler_path,
    sync_projections,
    verify_scheduler,
    write_json_atomic,
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


def set_wave_backend(workspace: Path, run_ref: str, wave_id: str, backend: str, reason: str, dispatch_key: str) -> None:
    target = resolve_run_target(workspace, run_ref)
    sched = reconcile_scheduler(target)
    for phase in sched.get("phases") or []:
        for wave in phase.get("waves") or []:
            if wave.get("id") == wave_id:
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
    sync_projections(target, sched)
    write_json_atomic(scheduler_path(target), sched)


def update_fleet_runtime(workspace: Path, run_ref: str, probe_result: dict[str, object]) -> None:
    if not run_ref:
        return
    try:
        target = resolve_run_target(workspace, run_ref)
    except Exception:
        return
    sched = reconcile_scheduler(target)
    runtime = sched.get("runtime") or {}
    runtime["fleetCapability"] = {
        "status": probe_result.get("status", "unknown"),
        "reason": probe_result.get("reason", "not-probed"),
        "checkedAt": probe_result.get("checkedAt"),
        "probeModel": probe_result.get("probeModel"),
    }
    sched["runtime"] = runtime
    sync_projections(target, sched)
    write_json_atomic(scheduler_path(target), sched)


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
            set_wave_backend(workspace, run_ref, str(wave.get("id")), "internal", reason, "degradedWaves")
            append_journal_event(workspace, run_ref, "fleet-degraded", {"waveId": wave.get("id"), "reason": reason})
        return True

    changed = False
    for item in pending:
        wave = item["wave"]
        workstreams = item["workstreams"]
        prompt = build_fleet_wave_prompt(run_ref, wave, workstreams)
        cmd = build_fleet_command(args, prompt, model)
        rc, output = run_and_stream(cmd, workspace, {
            "LONGRUN_SELECTED_MODEL": model,
            "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
            "LONGRUN_RUN_ID": run_ref,
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
            set_wave_backend(workspace, run_ref, str(wave.get("id")), "internal", reason, "degradedWaves")
            append_journal_event(workspace, run_ref, "fleet-degraded", {"waveId": wave.get("id"), "reason": reason})
        else:
            set_wave_backend(workspace, run_ref, str(wave.get("id")), "fleet", str(wave.get("reason")), "completedWaves")
            append_journal_event(workspace, run_ref, "fleet-complete", {"waveId": wave.get("id")})
        changed = True
    return changed


def resume_after_fleet(args, workspace: Path, run_ref: str, model: str) -> bool:
    if not args.resume_skill_ref:
        return False
    payload = run_ref
    cmd = build_command(args, args.resume_skill_ref, payload, model)
    rc, output = run_and_stream(cmd, workspace, {
        "LONGRUN_SELECTED_MODEL": model,
        "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
        "LONGRUN_RUN_ID": run_ref,
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
            "ts": sched.get("updatedAt"),
            "model": selected_model,
            "reason": fallback_reason or note or "launcher-attempt",
        })
        sched["modelAttemptHistory"] = history[-12:]
    if fallback_reason:
        sched["fallbackReason"] = fallback_reason
    write_json_atomic(scheduler_path(target), sched)


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
    sched = reconcile_scheduler(target)
    if sched.get("profile") != "coding":
        return True
    if final_review_path(target).exists() and final_review_path(target).stat().st_size > 0:
        return True
    audit_model = load_model_config(args.model_config).get("codingAuditModel", "gpt-5.4")
    print(f"[ILongRun] pending coding audit; starting GPT-5.4 audit pass ({audit_model})")
    payload = (
        "[ILongRun supervisor context]\n"
        f"Resume existing run-id: {run_ref}\n"
        "Perform pending GPT-5.4 final audit only.\n"
        "Do not mint a new run.\n"
        "[/ILongRun supervisor context]\n\n"
        f"{run_ref}"
    )
    cmd = build_command(args, args.resume_skill_ref or args.skill_ref, payload, audit_model)
    rc, output = run_and_stream(cmd, workspace, {
        "LONGRUN_SELECTED_MODEL": audit_model,
        "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
        "LONGRUN_RUN_ID": run_ref,
        "LONGRUN_RUN_DIR": str(target.run_dir),
        "LONGRUN_LAUNCH_MODE": "ilongrun-gpt54-audit",
        "ILONGRUN_FORCE_AUDIT": "1",
    })
    if rc != 0:
        print("[ILongRun] GPT-5.4 audit pass failed", file=sys.stderr)
        return False
    if detect_fallback_reason(output):
        return False
    refreshed = reconcile_scheduler(target)
    sync_projections(target, refreshed)
    write_json_atomic(scheduler_path(target), refreshed)
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
    if args.mode == "run" and run_ref:
        current_payload = (
            "[ILongRun launcher context]\n"
            f"Assigned run-id: {run_ref}\n"
            "Use this exact run-id and do not mint a different run-id.\n"
            "If any execution wave backend is `fleet`, stop after strategy/phase/workstream/task-list decomposition and wait for external supervisor dispatch.\n"
            "Do not personally execute fleet-tagged workstreams inside the primary planning pass.\n"
            "[/ILongRun launcher context]\n\n"
            f"{args.payload}"
        ).strip()
    elif args.mode == "resume" and run_ref:
        current_payload = (
            "[ILongRun launcher context]\n"
            f"Resume existing run-id: {run_ref}\n"
            "Continue this run and do not create a new run-id.\n"
            "[/ILongRun launcher context]\n\n"
            f"{args.payload}"
        ).strip()

    for index, model in enumerate(chain):
        human = display_model_name(model, config)
        print(f"[ILongRun] attempt {index + 1}/{len(chain)} with model: {human} ({model})")
        patch_scheduler(workspace, run_ref, selected_model=model, note="launcher-attempt")
        cmd = build_command(args, current_skill, current_payload, model)
        rc, output = run_and_stream(cmd, workspace, {
            "LONGRUN_SELECTED_MODEL": model,
            "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
            "LONGRUN_RUN_ID": run_ref,
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
                    maybe_finalize_blocked(workspace, run_ref, "ILongRun GPT-5.4 audit pass failed")
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
                        maybe_finalize_blocked(workspace, run_ref, "ILongRun GPT-5.4 audit pass failed after retry")
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
