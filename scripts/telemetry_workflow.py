#!/usr/bin/env python3
"""Cross-platform telemetry orchestration; no Bash is required."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from project_snapshot import ProjectSnapshot
from runtime_context import parse_test_output, resolve_test_plan, verification_context_checksum


def _test_command(project):
    return resolve_test_plan(project)["argv"]


def _source_digest(project, snapshot=None):
    return (snapshot or ProjectSnapshot.capture(project)).source_digest()


def _execute_tests(project, command):
    if not command:
        return {"total": 0, "passed": 0, "failed": 0, "status": "UNKNOWN", "runner": "none"}
    plan = resolve_test_plan(project)
    completed = subprocess.run(command, cwd=str(project), capture_output=True, text=True,
                               timeout=plan["timeout"], shell=False)
    output = (completed.stdout or "") + (completed.stderr or "")
    counts = parse_test_output(plan["runner"], output)
    status = "PASS" if completed.returncode == 0 and counts["total"] else (
        "FAIL" if completed.returncode != 0 or counts["total"] else "UNKNOWN"
    )
    return {**counts, "status": status, "runner": plan["runner"] or "none"}


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
        (context.get("context_sha256") == verification_context_checksum(context), "checksum_changed"),
    ]
    for valid, reason in checks:
        if not valid:
            return None, reason
    return context, "trusted_context"


def _write_context(path, project, task_id, command, source_digest, tests, plan=None):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    context = {"schema": "verification-run-context/v1", "task_id": task_id,
               "project_root": str(project), "source_digest": source_digest,
               "runner": tests.get("runner"), "argv": command,
               "cwd": (plan or {}).get("cwd", "."),
               "timeout": (plan or {}).get("timeout", 300),
               "started_at": now, "finished_at": now, **tests}
    context["context_sha256"] = verification_context_checksum(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return context


def record_verification_context(project_dir, task_id, tests, command=None):
    project = Path(project_dir).resolve()
    governance = project / "governance"
    plan = resolve_test_plan(project)
    command = command or plan["argv"]
    if command != plan["argv"]:
        plan = {**plan, "argv": command, "runner": tests.get("runner") or plan.get("runner")}
    snapshot = ProjectSnapshot.capture(project)
    return _write_context(_context_path(governance, task_id), project, task_id,
                          command, _source_digest(project, snapshot), tests, plan)


def _run_collector(command, project, timeout):
    completed = subprocess.run(command, cwd=str(project), capture_output=True, text=True,
                               timeout=timeout, shell=False)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout or "collector failed")[-2000:])
    return completed.stdout[-4000:]


def _progress(stage, status, started=None):
    event = {"stage": stage, "status": status}
    if started is not None:
        event["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    print(json.dumps(event, ensure_ascii=False), file=sys.stderr, flush=True)


def run(task_id, governance_dir, timeout=300, refresh_only=False, prepare_only=False):
    governance = Path(governance_dir).resolve()
    project = governance.parent
    if refresh_only:
        started = time.monotonic()
        _progress("metrics_refresh", "started")
        context_path = _context_path(governance, task_id)
        context = json.loads(context_path.read_text(encoding="utf-8"))
        collector = Path(__file__).resolve().parent / "collect_telemetry.py"
        output = _run_collector(
            [sys.executable, str(collector), "--project", project.name, "--task", task_id,
             "--test-total", str(context.get("total", 0)), "--test-passed", str(context.get("passed", 0)),
             "--token-usage", "0", "--token-source", "unavailable",
             "--skip-matrix-tests", "--skip-matrix-check", "--test-runner", str(context.get("runner") or "unknown"),
             "--verification-context", str(context_path),
             "--output", str(governance / "telemetry.json")],
            project, timeout,
        )
        _progress("metrics_refresh", "completed", started)
        return {"task_id": task_id, "refresh_only": True,
                "schedule": {"test_execution_count": 0, "internal_test_execution_count": 0,
                             "total_test_execution_count": 0, "test_reuse_count": 1,
                             "total_test_reuse_count": 1, "reuse_reason": "metrics_only_refresh",
                             "stages": {
                                 "project_snapshot": {"execution_count": 0, "reuse_count": 1},
                                 "source_digest": {"execution_count": 0, "reuse_count": 1},
                                 "map_context": {"execution_count": 0, "reuse_count": 0},
                                 "harness": {"execution_count": 0, "reuse_count": 1},
                                 "collector": {"execution_count": 1, "reuse_count": 0},
                                 "persist": {"execution_count": 1, "reuse_count": 0},
                             }},
                "collector_output": output}
    snapshot_started = time.monotonic()
    snapshot = ProjectSnapshot.capture(project)
    snapshot_elapsed = int((time.monotonic() - snapshot_started) * 1000)
    test_plan = resolve_test_plan(project)
    test_command = test_plan["argv"]
    digest_started = time.monotonic()
    source_digest = _source_digest(project, snapshot)
    digest_elapsed = int((time.monotonic() - digest_started) * 1000)
    context_path = _context_path(governance, task_id)
    context, reason = _load_context(context_path, project, task_id, test_command, source_digest)
    if context is None:
        tests = _execute_tests(project, test_command)
        context = _write_context(context_path, project, task_id, test_command, source_digest, tests, test_plan)
        schedule = {"test_execution_count": 1, "test_reuse_count": 0, "rerun_reason": reason}
    else:
        tests = {key: context.get(key) for key in ("total", "passed", "failed", "status", "runner")}
        schedule = {"test_execution_count": 0, "test_reuse_count": 1, "reuse_reason": reason}
    if prepare_only:
        schedule.update({
            "internal_test_execution_count": 0,
            "total_test_execution_count": schedule["test_execution_count"],
            "total_test_reuse_count": schedule["test_reuse_count"],
            "context": str(context_path),
            "context_sha256": context.get("context_sha256"),
            "stages": {
                "project_snapshot": {"execution_count": 1, "reuse_count": 0, "elapsed_ms": snapshot_elapsed},
                "source_digest": {"execution_count": 1, "reuse_count": 0, "elapsed_ms": digest_elapsed},
                "harness": {"execution_count": 0, "reuse_count": 0},
                "collector": {"execution_count": 0, "reuse_count": 0},
                "persist": {"execution_count": 0, "reuse_count": 0},
            },
        })
        return {"task_id": task_id, "prepare_only": True, "tests": tests, "schedule": schedule}
    collector = Path(__file__).resolve().parent / "collect_telemetry.py"
    command = [
        sys.executable, str(collector), "--project", project.name, "--task", task_id,
        "--test-total", str(tests["total"]), "--test-passed", str(tests["passed"]),
        "--token-usage", "0", "--token-source", "unavailable",
        "--skip-matrix-tests", "--test-runner", str(tests.get("runner") or "unknown"),
        "--verification-context", str(context_path),
        "--output", str(governance / "telemetry.json"),
    ]
    collector_started = time.monotonic()
    collector_output = _run_collector(command, project, timeout)
    collector_elapsed = int((time.monotonic() - collector_started) * 1000)
    schedule.update({"internal_test_execution_count": 0,
                     "total_test_execution_count": schedule["test_execution_count"],
                     "total_test_reuse_count": schedule["test_reuse_count"]})
    schedule["stages"] = {
        "project_snapshot": {"execution_count": 1, "reuse_count": 0, "elapsed_ms": snapshot_elapsed},
        "source_digest": {"execution_count": 1, "reuse_count": 0, "elapsed_ms": digest_elapsed},
        "map_context": {"execution_count": 0, "reuse_count": 0, "elapsed_ms": 0},
        "harness": {"execution_count": 1, "reuse_count": 0, "elapsed_ms": None, "included_in": "collector"},
        "collector": {"execution_count": 1, "reuse_count": 0, "elapsed_ms": collector_elapsed},
        "persist": {"execution_count": 1, "reuse_count": 0, "elapsed_ms": None, "included_in": "collector"},
    }
    schedule.update({"context": str(context_path), "context_sha256": context.get("context_sha256")})
    return {"task_id": task_id, "tests": tests, "schedule": schedule, "collector_output": collector_output}


def main():
    parser = argparse.ArgumentParser(description="跨平台遥测主流程")
    parser.add_argument("task_id")
    parser.add_argument("governance_dir", nargs="?", default="governance")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--refresh-only", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.task_id, args.governance_dir, args.timeout, args.refresh_only, args.prepare_only)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
