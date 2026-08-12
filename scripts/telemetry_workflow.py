#!/usr/bin/env python3
"""Cross-platform telemetry orchestration; no Bash is required."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _test_command(project):
    tests = project / "tests"
    if not tests.is_dir():
        return []
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    if (tests / "__init__.py").is_file():
        command.extend(["-t", "."])
    return command


def _source_digest(project):
    digest = hashlib.sha256()
    roots = [project / "tests", project / "scripts", project / "src"]
    files = sorted(path for root in roots if root.is_dir() for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    for path in files:
        digest.update(path.relative_to(project).as_posix().encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _execute_tests(project, command):
    if not command:
        return {"total": 0, "passed": 0, "failed": 0, "status": "UNKNOWN", "runner": "none"}
    completed = subprocess.run(command, cwd=str(project), capture_output=True, text=True, shell=False)
    output = (completed.stdout or "") + (completed.stderr or "")
    match = re.search(r"Ran (\d+) tests?", output)
    total = int(match.group(1)) if match else 0
    failures = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", output))
    return {"total": total, "passed": max(0, total - failures), "failed": failures,
            "status": "PASS" if completed.returncode == 0 and total else "FAIL" if total else "UNKNOWN",
            "runner": "unittest"}


def _context_path(governance, task_id):
    return governance / "telemetry/verification-runs" / f"{task_id}.json"


def _load_context(path, project, task_id, command, source_digest):
    try:
        context = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "missing_or_invalid_context"
    checks = [
        (context.get("schema") == "verification-run-context/v1", "schema_changed"),
        (context.get("task_id") == task_id, "task_changed"),
        (context.get("project_root") == str(project), "project_changed"),
        (context.get("argv") == command, "command_changed"),
        (context.get("source_digest") == source_digest, "source_changed"),
    ]
    for valid, reason in checks:
        if not valid:
            return None, reason
    return context, "trusted_context"


def _write_context(path, project, task_id, command, source_digest, tests):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    context = {"schema": "verification-run-context/v1", "task_id": task_id,
               "project_root": str(project), "source_digest": source_digest,
               "runner": tests.get("runner"), "argv": command,
               "started_at": now, "finished_at": now, **tests}
    canonical = json.dumps(context, ensure_ascii=False, sort_keys=True).encode()
    context["context_sha256"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return context


def record_verification_context(project_dir, task_id, tests, command=None):
    project = Path(project_dir).resolve()
    governance = project / "governance"
    command = command or _test_command(project)
    return _write_context(_context_path(governance, task_id), project, task_id,
                          command, _source_digest(project), tests)


def _run_collector(command, project, timeout):
    completed = subprocess.run(command, cwd=str(project), capture_output=True, text=True,
                               timeout=timeout, shell=False)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout or "collector failed")[-2000:])
    return completed.stdout[-4000:]


def run(task_id, governance_dir, timeout=1800):
    governance = Path(governance_dir).resolve()
    project = governance.parent
    test_command = _test_command(project)
    source_digest = _source_digest(project)
    context_path = _context_path(governance, task_id)
    context, reason = _load_context(context_path, project, task_id, test_command, source_digest)
    if context is None:
        tests = _execute_tests(project, test_command)
        context = _write_context(context_path, project, task_id, test_command, source_digest, tests)
        schedule = {"test_execution_count": 1, "test_reuse_count": 0, "rerun_reason": reason}
    else:
        tests = {key: context.get(key) for key in ("total", "passed", "failed", "status", "runner")}
        schedule = {"test_execution_count": 0, "test_reuse_count": 1, "reuse_reason": reason}
    collector = Path(__file__).resolve().parent / "collect_telemetry.py"
    command = [
        sys.executable, str(collector), "--project", project.name, "--task", task_id,
        "--test-total", str(tests["total"]), "--test-passed", str(tests["passed"]),
        "--token-usage", "0", "--token-source", "unavailable",
        "--output", str(governance / "telemetry.json"),
    ]
    collector_output = _run_collector(command, project, timeout)
    schedule.update({"context": str(context_path), "context_sha256": context.get("context_sha256")})
    return {"task_id": task_id, "tests": tests, "schedule": schedule, "collector_output": collector_output}


def main():
    parser = argparse.ArgumentParser(description="跨平台遥测主流程")
    parser.add_argument("task_id")
    parser.add_argument("governance_dir", nargs="?", default="governance")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    try:
        result = run(args.task_id, args.governance_dir, args.timeout)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
