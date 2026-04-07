#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Iterable


def _clean_items(items: Iterable[str] | None) -> list[str]:
    cleaned: list[str] = []
    for item in items or []:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _bullet_lines(items: Iterable[str] | None, *, none_text: str = "None.") -> list[str]:
    values = _clean_items(items)
    if not values:
        return [f"- {none_text}"]
    return [f"- {value}" for value in values]


def _metadata_lines(pairs: list[tuple[str, Any]]) -> list[str]:
    lines: list[str] = []
    for label, value in pairs:
        rendered = "n/a" if value is None or str(value).strip() == "" else str(value)
        lines.append(f"- {label}: `{rendered}`")
    return lines


def build_final_review_template_markdown(
    *,
    run_id: str = "<run-id>",
    audit_model: str = "gpt-5.4",
    implementation_model: str = "<selected-model>",
) -> str:
    lines = [
        "# ILongRun Final Review",
        "",
        "## Run Metadata",
        *_metadata_lines(
            [
                ("Run ID", run_id),
                ("Audit model", audit_model),
                ("Implementation model", implementation_model),
                ("Review path", "reviews/gpt54-final-review.md"),
            ]
        ),
        "",
        "## Summary",
        "- 审查范围：<本轮审查覆盖的模块 / workstream / 风险面>",
        "- 总发现数：`0`",
        "- 严重性分布：must-fix=`0` / should-fix=`0` / nit=`0`",
        "",
        "## Findings",
        "### Must-Fix (Critical)",
        *_bullet_lines([], none_text="None."),
        "",
        "### Should-Fix (Major)",
        *_bullet_lines([], none_text="None."),
        "",
        "### Nit (Minor)",
        *_bullet_lines([], none_text="None."),
        "",
        "## Suggested Fixes",
        *_bullet_lines([], none_text="None."),
        "",
        "## Residual Risks",
        *_bullet_lines([], none_text="None."),
        "",
        "## Verdict",
        "- PASS / PASS_WITH_CONDITIONS / FAIL",
        "",
    ]
    return "\n".join(lines)


def build_adjudication_report_markdown(
    *,
    run_id: str,
    audit_model: str,
    review_status: str,
    must_fix: list[str],
    should_fix: list[str],
    defer: list[str],
    blocking: bool,
    decision: str,
    assigned_workstream: str,
    assigned_role: str,
    assigned_model: str,
    next_actions: list[str],
) -> str:
    verdict = "RETURN_FOR_FIX" if blocking else "PROCEED_TO_FINALIZE"
    lines = [
        "# ILongRun Adjudication",
        "",
        "## Run Metadata",
        *_metadata_lines(
            [
                ("Run ID", run_id),
                ("Audit model", audit_model),
                ("Review path", "reviews/gpt54-final-review.md"),
                ("Adjudication path", "reviews/adjudication.md"),
            ]
        ),
        "",
        "## Summary",
        f"- Review status: `{review_status}`",
        f"- Must-fix count: `{len(must_fix)}`",
        f"- Should-fix count: `{len(should_fix)}`",
        f"- Residual risk / defer count: `{len(defer)}`",
        "",
        "## Findings Intake",
        "### Must-Fix",
        *_bullet_lines(must_fix, none_text="None."),
        "",
        "### Should-Fix",
        *_bullet_lines(should_fix, none_text="None."),
        "",
        "### Residual Risks / Deferred Items",
        *_bullet_lines(defer, none_text="None."),
        "",
        "## Decision",
        f"- Blocking finalize: `{'yes' if blocking else 'no'}`",
        f"- Decision: `{decision}`",
        f"- Assigned workstream: `{assigned_workstream or 'none'}`",
        f"- Assigned role/model: `{assigned_role or 'mission-governor'}` / `{assigned_model or audit_model}`",
        "",
        "## Next Actions",
        *_bullet_lines(next_actions, none_text="None."),
        "",
        "## Verdict",
        f"- {verdict}",
        "",
    ]
    return "\n".join(lines)


def build_completion_report_markdown(
    *,
    run_id: str,
    status_name: str,
    profile: str,
    selected_model: str,
    headline: str,
    verification_state: str,
    review_status: str,
    adjudication_status: str,
    completion_score: dict[str, Any] | None,
    deliverables: list[str],
    verification_items: list[str],
    blockers: list[str],
) -> str:
    score = completion_score or {}
    layers = score.get("layers") or {}
    lines = [
        "# ILongRun Completion Summary",
        "",
        "## Run Metadata",
        *_metadata_lines(
            [
                ("Run ID", run_id),
                ("State", status_name),
                ("Profile", profile),
                ("Selected model", selected_model),
                ("Completion path", "COMPLETION.md"),
            ]
        ),
        "",
        "## Summary",
        f"- Headline: {headline}",
        f"- Verification state: `{verification_state}`",
        f"- Review gate: `{review_status}`",
        f"- Adjudication gate: `{adjudication_status}`",
        f"- Delivery verdict: `{score.get('deliveryVerdict', 'unknown')}`",
        "",
    ]
    if score:
        lines.extend(
            [
                "## Completion Score",
                f"- Overall: `{score.get('overall', 0)}` / grade=`{score.get('grade', 'N/A')}`",
                f"- Code exists: `{(layers.get('codeExists') or {}).get('score', 'n/a')}`",
                f"- Wired into entry: `{(layers.get('wiredIntoEntry') or {}).get('score', 'n/a')}`",
                f"- Tested: `{(layers.get('tested') or {}).get('score', 'n/a')}`",
                f"- Runtime validated: `{(layers.get('runtimeValidated') or {}).get('score', 'n/a')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Deliverables",
            *_bullet_lines([f"`{item}`" for item in _clean_items(deliverables)], none_text="None recorded."),
            "",
            "## Verification Evidence",
            *_bullet_lines(verification_items, none_text="No explicit verification notes."),
            "",
            "## Blockers",
            *_bullet_lines(blockers, none_text="None."),
            "",
            "## Verdict",
            f"- {'COMPLETE' if str(status_name).strip().lower() == 'complete' else 'BLOCKED'}",
            "",
        ]
    )
    return "\n".join(lines)
