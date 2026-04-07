#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


SOURCE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".turbo",
    ".vite",
    ".cache",
    ".idea",
    ".vscode",
    "coverage",
    "dist",
    "build",
    "out",
    "node_modules",
    ".copilot-ilongrun",
}
ENTRY_BASENAMES = ("main", "app", "server", "client")
RISKY_SUFFIX_RE = re.compile(r"(Manager|System|Agent|Controller|Service|Engine|Predictor|Interpolator|UI|Provider|Client)$")
NOOP_HINT_RE = re.compile(r"(noop|空实现|placeholder|stub|not implemented|todo)", re.IGNORECASE)
EXPORT_HINT_RE = re.compile(r"\bexport\s+(?:default\s+)?(?:class|function|const|interface|type)\b")
IMPORT_SPEC_RE = re.compile(
    r"""(?:import|export)\s+(?:type\s+)?(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)


def _is_ignored(path: Path, workspace: Path) -> bool:
    try:
        rel = path.relative_to(workspace)
    except ValueError:
        return True
    return any(part in IGNORED_DIRS for part in rel.parts)


def _is_test_file(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    return (
        "__tests__" in parts
        or "tests" in parts
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".test.js")
        or name.endswith(".test.jsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
        or name.endswith(".spec.js")
        or name.endswith(".spec.jsx")
    )


def _is_barrel_file(path: Path) -> bool:
    return path.stem == "index"


def _collect_source_files(workspace: Path) -> list[Path]:
    files: list[Path] = []
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SOURCE_EXTENSIONS:
            continue
        if _is_ignored(path, workspace):
            continue
        files.append(path.resolve())
    return sorted(files)


def _nearest_package_root(path: Path, workspace: Path) -> Path:
    current = path.parent
    while current != workspace and current != current.parent:
        if (current / "package.json").exists():
            return current
        current = current.parent
    return workspace


def _resolve_local_import(base: Path, specifier: str) -> Path | None:
    cleaned = specifier.split("?", 1)[0].split("#", 1)[0].strip()
    if not cleaned.startswith("."):
        return None
    target = (base.parent / cleaned).resolve()
    candidates = []
    if target.suffix in SOURCE_EXTENSIONS:
        candidates.append(target)
    else:
        candidates.extend(target.with_suffix(ext) for ext in SOURCE_EXTENSIONS)
        candidates.extend((target / f"index{ext}") for ext in SOURCE_EXTENSIONS)
    for item in candidates:
        if item.exists() and item.is_file():
            return item.resolve()
    return None


def _extract_local_imports(path: Path) -> set[Path]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    imports: set[Path] = set()
    for match in IMPORT_SPEC_RE.finditer(text):
        specifier = match.group(1) or match.group(2) or ""
        resolved = _resolve_local_import(path, specifier)
        if resolved:
            imports.add(resolved)
    return imports


def _workspace_rel(path: Path, workspace: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return path.as_posix()


def _candidate_entry_roots(package_root: Path, package_files: list[Path]) -> list[Path]:
    by_name = defaultdict(list)
    for path in package_files:
        if _is_test_file(path):
            continue
        by_name[path.stem].append(path)
    roots: list[Path] = []
    for stem in ENTRY_BASENAMES:
        roots.extend(sorted(by_name.get(stem) or []))
    if roots:
        return sorted(set(roots))
    return sorted(set(by_name.get("index") or []))


def _is_risky_runtime_module(path: Path, text: str) -> bool:
    if _is_test_file(path) or _is_barrel_file(path):
        return False
    if "ignore delivery audit" in text.lower():
        return False
    if not EXPORT_HINT_RE.search(text):
        return False
    return bool(RISKY_SUFFIX_RE.search(path.stem))


def _analyze_package(package_root: Path, package_files: list[Path], workspace: Path) -> dict[str, Any]:
    graph: dict[Path, set[Path]] = {}
    reverse_graph: dict[Path, set[Path]] = defaultdict(set)
    file_texts: dict[Path, str] = {}
    for path in package_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        file_texts[path] = text
        deps = {dep for dep in _extract_local_imports(path) if dep in package_files}
        graph[path] = deps
        for dep in deps:
            reverse_graph[dep].add(path)

    entry_roots = _candidate_entry_roots(package_root, package_files)
    reachable: set[Path] = set()
    queue: deque[Path] = deque(entry_roots)
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for dep in graph.get(node) or set():
            if dep not in reachable:
                queue.append(dep)

    findings: list[dict[str, Any]] = []
    risky_files: list[Path] = []
    for path, text in file_texts.items():
        if _is_risky_runtime_module(path, text):
            risky_files.append(path)

    for path in risky_files:
        if path in reachable:
            continue
        importers = sorted(reverse_graph.get(path) or set())
        non_test_importers = [item for item in importers if not _is_test_file(item)]
        runtime_importers = [item for item in non_test_importers if item in reachable]
        barrel_only = bool(non_test_importers) and all(_is_barrel_file(item) for item in non_test_importers)
        severity = "high" if not runtime_importers else "medium"
        evidence = [
            f"package root: {_workspace_rel(package_root, workspace)}",
            "runtime entries: " + (", ".join(_workspace_rel(item, workspace) for item in entry_roots) if entry_roots else "none"),
        ]
        if non_test_importers:
            evidence.append("non-test importers: " + ", ".join(_workspace_rel(item, workspace) for item in non_test_importers))
        else:
            evidence.append("non-test importers: none")
        if barrel_only:
            evidence.append("only barrel/test references observed")
        findings.append(
            {
                "kind": "unwired-runtime-module",
                "severity": severity,
                "file": _workspace_rel(path, workspace),
                "summary": f"runtime entry 无法到达高风险模块 `{_workspace_rel(path, workspace)}`",
                "evidence": evidence,
            }
        )

    duplicates: dict[str, list[Path]] = defaultdict(list)
    for path in risky_files:
        duplicates[path.stem].append(path)
    for stem, items in sorted(duplicates.items()):
        if len(items) < 2:
            continue
        severity = "high" if any(item in reachable for item in items) else "medium"
        findings.append(
            {
                "kind": "duplicate-core-module",
                "severity": severity,
                "symbol": stem,
                "files": [_workspace_rel(item, workspace) for item in sorted(items)],
                "summary": f"发现重名核心模块 `{stem}`，可能造成实现漂移或误接线",
                "evidence": [_workspace_rel(item, workspace) for item in sorted(items)],
            }
        )

    for path in risky_files:
        text = file_texts[path]
        lowered = text.lower()
        if "provider" not in path.stem.lower() and "adapter" not in path.stem.lower() and "noop" not in lowered:
            continue
        if not NOOP_HINT_RE.search(text):
            continue
        evidence = []
        if "isavailable" in lowered and "return false" in lowered:
            evidence.append("contains `isAvailable() { return false; }` pattern")
        if "noop" in lowered:
            evidence.append("contains noop marker")
        findings.append(
            {
                "kind": "placeholder-provider",
                "severity": "medium",
                "file": _workspace_rel(path, workspace),
                "summary": f"检测到占位/空实现 provider：`{_workspace_rel(path, workspace)}`",
                "evidence": evidence or ["placeholder/noop hints detected in source"],
            }
        )

    return {
        "packageRoot": _workspace_rel(package_root, workspace),
        "entryRoots": [_workspace_rel(item, workspace) for item in entry_roots],
        "filesScanned": len(package_files),
        "reachableFiles": len(reachable),
        "findings": findings,
    }


def scan_workspace_delivery_gaps(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    files = _collect_source_files(workspace)
    if not files:
        return {
            "ok": True,
            "supported": False,
            "workspace": str(workspace),
            "language": None,
            "findings": [],
            "packages": [],
            "summary": {"filesScanned": 0, "high": 0, "medium": 0, "low": 0},
        }

    package_map: dict[Path, list[Path]] = defaultdict(list)
    for path in files:
        package_map[_nearest_package_root(path, workspace)].append(path)

    packages: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for package_root, package_files in sorted(package_map.items(), key=lambda item: str(item[0])):
        result = _analyze_package(package_root, package_files, workspace)
        packages.append(result)
        findings.extend(result["findings"])

    high = sum(1 for item in findings if item.get("severity") == "high")
    medium = sum(1 for item in findings if item.get("severity") == "medium")
    low = sum(1 for item in findings if item.get("severity") == "low")
    return {
        "ok": high == 0,
        "supported": True,
        "workspace": str(workspace),
        "language": "javascript-typescript",
        "findings": findings,
        "packages": packages,
        "summary": {
            "filesScanned": len(files),
            "high": high,
            "medium": medium,
            "low": low,
        },
    }


def render_delivery_audit_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Delivery Gap Audit",
        "",
        f"- Workspace: `{result.get('workspace')}`",
        f"- Language: `{result.get('language') or 'unsupported'}`",
        f"- Supported: `{'yes' if result.get('supported') else 'no'}`",
        f"- High-confidence findings: `{(result.get('summary') or {}).get('high', 0)}`",
        f"- Medium-confidence findings: `{(result.get('summary') or {}).get('medium', 0)}`",
        f"- Files scanned: `{(result.get('summary') or {}).get('filesScanned', 0)}`",
        "",
    ]
    findings = result.get("findings") or []
    if not findings:
        lines.extend(["## Findings", "", "- No delivery gap findings.", ""])
    else:
        lines.extend(["## Findings", ""])
        for item in findings:
            lines.append(f"### [{item.get('severity', 'unknown')}] {item.get('kind')}")
            lines.append(f"- Summary: {item.get('summary')}")
            if item.get("file"):
                lines.append(f"- File: `{item.get('file')}`")
            if item.get("files"):
                lines.append("- Files:")
                lines.extend(f"  - `{entry}`" for entry in item.get("files") or [])
            evidence = item.get("evidence") or []
            if evidence:
                lines.append("- Evidence:")
                lines.extend(f"  - {entry}" for entry in evidence)
            lines.append("")
    lines.extend(["## Package reachability", ""])
    for package in result.get("packages") or []:
        lines.append(f"### `{package.get('packageRoot')}`")
        roots = package.get("entryRoots") or []
        lines.append(f"- Runtime entries: {', '.join(f'`{item}`' for item in roots) if roots else 'none'}")
        lines.append(f"- Files scanned: `{package.get('filesScanned', 0)}`")
        lines.append(f"- Reachable files: `{package.get('reachableFiles', 0)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def print_scan_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
