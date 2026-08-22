#!/usr/bin/env python3
"""Mechanical Change Envelope enforcement for a local Git worktree."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


IGNORED_PREFIXES = ("governance/evidence/", "governance/telemetry/")


def load_structured_object(path: Path | str, label: str = "structured file") -> dict[str, Any]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{label} not readable: {path}") from exc
    # 提取 frontmatter（--- 包裹的 YAML 块）
    if text.lstrip().startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError:
            from _bootstrap import ensure_yaml_available
            ensure_yaml_available()
            import yaml  # type: ignore
        try:
            data = yaml.safe_load(text)
        except Exception as exc:
            raise ValueError(f"{label} is not valid YAML/JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be an object")
    return data


def _load(path: Path) -> dict[str, Any]:
    return load_structured_object(path, "Change Envelope")


def find_task_envelope(project_dir: Path | str, task_id: str) -> Path | None:
    """Return the unique task-local envelope, never a legacy global envelope."""
    project = Path(project_dir).expanduser().resolve()
    change_dir = project / "governance" / "change"
    if not change_dir.is_dir():
        return None
    expected = f"Change_Envelope_{str(task_id).strip()}".casefold()
    candidates = sorted(
        path for path in change_dir.iterdir()
        if path.is_file()
        and path.suffix.casefold() in {".yaml", ".yml"}
        and path.stem.casefold() == expected
    )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise ValueError(f"TASK_ENVELOPE_AMBIGUOUS: {task_id}: {names}")
    return candidates[0] if candidates else None


def resolve_task_envelope(project_dir: Path | str, task_id: str) -> Path:
    envelope = find_task_envelope(project_dir, task_id)
    if envelope is None:
        raise ValueError(f"TASK_ENVELOPE_MISSING: governance/change/Change_Envelope_{task_id}.yaml")
    return envelope


def _paths(value: Any, field: str) -> list[str]:
    if not isinstance(value, dict) or not isinstance(value.get("paths"), list):
        raise ValueError(f"{field}.paths must be a list")
    result = []
    for raw in value["paths"]:
        if not isinstance(raw, str):
            raise ValueError(f"{field}.paths entries must be strings")
        item = raw.replace("\\", "/")
        path = Path(item)
        if not item or item in {".", "./", "/"} or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe {field} path: {raw!r}")
        result.append(item)
    return result


def _changed_paths(project: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=project, capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise ValueError("Git status unavailable; Change Envelope cannot be verified")
    records = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    changed: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise ValueError("unparseable Git status record")
        status, path = record[:2], record[3:]
        changed.append(path)
        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                raise ValueError("unparseable Git rename/copy record")
            changed.append(records[index])
            index += 1
    return sorted(set(changed))


def _matches(path: str, rule: str) -> bool:
    return path.startswith(rule) if rule.endswith("/") else path == rule


def _ignored(path: str, envelope_path: Path, project: Path) -> bool:
    if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES):
        return True
    if path.startswith("governance/dashboard") and path.endswith(".html"):
        return True
    try:
        return path == envelope_path.resolve().relative_to(project).as_posix()
    except ValueError:
        return False


def check_envelope(project_dir: Path | str, task_id: str, envelope_path: Path | str | None = None) -> dict[str, Any]:
    project = Path(project_dir).expanduser().resolve()
    if not project.is_dir():
        return _failure(task_id, "INVALID_PROJECT", f"project directory does not exist: {project}")
    try:
        envelope = Path(envelope_path).expanduser() if envelope_path else resolve_task_envelope(project, task_id)
        if not envelope.is_absolute():
            envelope = (project / envelope).resolve()
        data = _load(envelope)
        if data.get("task_id") != task_id:
            raise ValueError(f"task_id mismatch: expected {task_id}")
        if data.get("status") != "AUTHORIZED":
            raise ValueError("Change Envelope status must be AUTHORIZED")
        allowed_rules = _paths(data.get("allowed"), "allowed")
        protected_rules = _paths(data.get("protected"), "protected")
        if not allowed_rules:
            raise ValueError("allowed.paths must not be empty")
        unknown = data.get("unknown")
        if not isinstance(unknown, list):
            raise ValueError("unknown must be a list")
        if unknown:
            raise ValueError("Change Envelope contains unresolved Unknown items")
        changed = _changed_paths(project)
    except ValueError as exc:
        return _failure(task_id, "FAIL_CLOSED", str(exc))

    ignored = sorted(path for path in changed if _ignored(path, envelope, project))
    evaluated = [path for path in changed if path not in ignored]
    protected = sorted(path for path in evaluated if any(_matches(path, rule) for rule in protected_rules))
    outside = sorted(path for path in evaluated if path not in protected and not any(_matches(path, rule) for rule in allowed_rules))
    passed = not protected and not outside
    status = "NO_CHANGES" if passed and not evaluated else ("PASS" if passed else "OUTSIDE_ENVELOPE")
    return {
        "task_id": task_id, "passed": passed, "status": status,
        "changed": changed, "allowed": sorted(path for path in evaluated if path not in protected and path not in outside),
        "protected": protected, "outside": outside, "ignored": ignored, "errors": [],
    }


def _failure(task_id: str, status: str, error: str) -> dict[str, Any]:
    return {"task_id": task_id, "passed": False, "status": status, "changed": [], "allowed": [], "protected": [], "outside": [], "ignored": [], "errors": [error]}


def render_result(result: dict[str, Any], output_format: str = "markdown") -> str:
    if output_format in {"yaml", "yml", "json"}:
        return json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if output_format not in {"markdown", "md"}:
        raise ValueError(f"unsupported format: {output_format}")
    def section(name: str) -> str:
        values = result.get(name.lower(), [])
        return f"## {name}\n\n" + ("\n".join(f"- `{item}`" for item in values) if values else "- None")
    return f"# Change Envelope Check: {result['task_id']}\n\n**Status**: {result['status']}\n**Passed**: {result['passed']}\n\n" + "\n\n".join(section(name) for name in ("Changed", "Allowed", "Protected", "Outside", "Ignored", "Errors")) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Change Envelope mechanical gate")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--task", required=True)
    check.add_argument("--project-dir", default=".")
    check.add_argument("--envelope")
    check.add_argument("--format", choices=("markdown", "md", "yaml", "yml", "json"), default="markdown")
    args = parser.parse_args()
    result = check_envelope(args.project_dir, args.task, args.envelope)
    print(render_result(result, args.format), end="")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__": main()
