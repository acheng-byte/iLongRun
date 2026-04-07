#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILLS_ROOT = (ROOT / "skills") if (ROOT / "skills").exists() else (Path.home() / ".copilot" / "skills")
REQUIRED_CODING_PLAYBOOKS = [
    "phase-define.md",
    "phase-plan.md",
    "phase-build.md",
    "phase-verify.md",
    "phase-review.md",
    "phase-audit.md",
    "phase-finalize.md",
    "swarm-policy.md",
    "js-ts-profile.md",
    "workspace-isolation.md",
    "task-microcycle.md",
    "claim-verification.md",
    "recovery-debug.md",
    "skill-engineering.md",
]
DEFAULT_TARGETS = [
    DEFAULT_SKILLS_ROOT / "ilongrun" / "SKILL.md",
    DEFAULT_SKILLS_ROOT / "ilongrun-coding" / "SKILL.md",
    DEFAULT_SKILLS_ROOT / "ilongrun-resume" / "SKILL.md",
    DEFAULT_SKILLS_ROOT / "ilongrun-status" / "SKILL.md",
]
REQUIRED_HEADINGS = {
    "ilongrun": ["## 总原则", "## 编排要求", "## Verification Checklist"],
    "ilongrun-coding": ["## 协议定位", "## 生命周期路由", "## wave / backend 规则", "## workstream 最小合同字段", "## Skill Engineering"],
    "ilongrun-resume": [],
    "ilongrun-status": ["## Resolve run", "## 读取顺序", "## 输出要求"],
}
TOKEN_BUDGET = {
    "ilongrun": 2600,
    "ilongrun-coding": 3200,
    "ilongrun-resume": 1200,
    "ilongrun-status": 2200,
}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    raw_fm, body = parts
    lines = raw_fm.splitlines()[1:]
    payload: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        payload[key.strip()] = value.strip().strip('"')
    return payload, body


def approx_token_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9_./:+-]+|[\u4e00-\u9fff]", text))


def find_cross_refs(path: Path, text: str) -> list[str]:
    refs = set(re.findall(r"`([^`]+\.(?:md|jsonc|json|py|sh))`", text))
    refs.update(re.findall(r"\]\(([^)]+\.(?:md|jsonc|json|py|sh))\)", text))
    return sorted(refs)


def ref_exists(skill_path: Path, ref: str, skills_root: Path) -> bool:
    raw = ref.strip()
    if not raw or raw.startswith("http://") or raw.startswith("https://"):
        return True
    if "*" in raw:
        return True
    if raw in {"mission.md", "strategy.md", "plan.md", "scheduler.json", "COMPLETION.md", "task-list-N.md"}:
        return True
    if raw.startswith("workstreams/") or raw.startswith("reviews/"):
        return True
    if raw.startswith("docs/"):
        return True
    candidates = [
        skill_path.parent / raw,
        skills_root / raw,
        skills_root.parent / raw,
        ROOT / raw,
    ]
    return any(candidate.exists() for candidate in candidates)


def lint_one(path: Path, *, skills_root: Path) -> dict[str, Any]:
    findings: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return {"path": str(path), "ok": False, "findings": ["file missing"], "warnings": []}
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    skill_name = path.parent.name if path.name == "SKILL.md" else path.stem
    desc = frontmatter.get("description", "")
    if path.name == "SKILL.md":
        if not desc.startswith("Use when"):
            findings.append("frontmatter description must start with 'Use when'")
        for heading in REQUIRED_HEADINGS.get(skill_name, []):
            if heading not in body:
                findings.append(f"missing required heading: {heading}")
        budget = TOKEN_BUDGET.get(skill_name)
        if budget is not None:
            tokens = approx_token_count(body)
            if tokens > budget:
                warnings.append(f"token budget exceeded: {tokens} > {budget}")
    for ref in find_cross_refs(path, text):
        if not ref_exists(path, ref, skills_root):
            findings.append(f"broken cross-reference: {ref}")
    if path.name == "SKILL.md" and skill_name == "ilongrun-coding":
        missing = [name for name in REQUIRED_CODING_PLAYBOOKS if not (path.parent / name).exists()]
        if missing:
            findings.append(f"missing coding playbooks: {', '.join(missing)}")
    return {"path": str(path), "ok": not findings, "findings": findings, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint iLongRun skill frontmatter, headings, token budget, and cross references")
    parser.add_argument("--skills-root", default=str(DEFAULT_SKILLS_ROOT))
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    skills_root = Path(args.skills_root).resolve()
    targets = [Path(item).resolve() for item in args.path] if args.path else [item.resolve() for item in DEFAULT_TARGETS]
    results = [lint_one(path, skills_root=skills_root) for path in targets]
    ok = all(item["ok"] for item in results)
    payload = {"ok": ok, "results": results}

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in results:
            icon = "✅" if item["ok"] else "❌"
            print(f"{icon} {item['path']}")
            for finding in item["findings"]:
                print(f"  - {finding}")
            for warning in item["warnings"]:
                print(f"  - warning: {warning}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
