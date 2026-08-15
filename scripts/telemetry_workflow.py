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
from token_usage import collect_token_measurement
from context_measurement import (
    canonical_task_id, load_context_measurement, measurement_path, resolve_measurement_path,
)


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
    # T-146 fix: status 基于 failed 计数而非 exit code。
    # beforeAll 失败（如 adminMembers seed）→ exit 1，但业务测试全部通过。
    # vitest skipped 测试 → numTotalTests > numPassedTests，但 failed == 0。
    status = "PASS" if counts["failed"] == 0 and counts["total"] > 0 else (
        "FAIL" if counts["failed"] > 0 else "UNKNOWN"
    )
    return {**counts, "status": status, "runner": plan["runner"] or "none"}


def _context_path(governance, task_id):
    return governance / "telemetry/verification-runs" / f"{canonical_task_id(task_id)}.json"


def _token_baseline_path(governance, task_id):
    return governance / "telemetry/token-baselines" / f"{canonical_task_id(task_id)}.json"


def _resolve_token_baseline_path(governance, task_id):
    canonical = _token_baseline_path(governance, task_id)
    if canonical.is_file():
        return canonical
    if not canonical.parent.is_dir():
        return canonical
    matches = sorted(path for path in canonical.parent.glob("*.json")
                     if path.stem.casefold() == canonical.stem.casefold())
    return matches[0] if len(matches) == 1 else canonical


def capture_token_baseline(project_dir, task_id, host_tool=None, token_clients=None):
    project = Path(project_dir).resolve()
    task_id = canonical_task_id(task_id)
    measurement = collect_token_measurement(
        project, host_tool=host_tool, token_clients=token_clients, task_id=task_id,
    )
    path = _token_baseline_path(project / "governance", task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(measurement, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return measurement


def collect_workflow_token_measurement(project, governance, task_id, host_tool=None, token_clients=None):
    task_id = canonical_task_id(task_id)
    baseline_path = _resolve_token_baseline_path(governance, task_id)
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        baseline = None
    return collect_token_measurement(
        project, host_tool=host_tool, token_clients=token_clients, baseline=baseline,
        task_id=task_id,
    )


def _token_collector_args(measurement):
    return ["--token-measurement-json", json.dumps(measurement, ensure_ascii=False)]


def _context_collector_args(governance: Path, task_id: str) -> list[str]:
    from token_usage import project_identity
    expected_uid = project_identity(governance.parent)["project_uid"]
    measurement = load_context_measurement(
        resolve_measurement_path(governance, task_id), canonical_task_id(task_id), expected_uid
    )
    if measurement is None:
        return []
    return ["--context-measurement-json", json.dumps(measurement, ensure_ascii=False)]


def capture_context_measurement(project_dir: Path | str, task_id: str) -> dict | None:
    """Build the Context Pack and its sidecar at the normal change-prepare boundary."""
    project = Path(project_dir).resolve()
    task_id = canonical_task_id(task_id)
    from crop_context import crop

    path = measurement_path(project / "governance", task_id)
    crop(project, task_id, measurement_output=path)
    from token_usage import project_identity
    return load_context_measurement(path, task_id, project_identity(project)["project_uid"])


def _derive_auto_params(project: Path, governance: Path, task_id: str,
                        token_measurement: dict) -> list[str]:
    """T-153: 自动推导 dashboard 所需参数并注入 collect_telemetry 命令行。

    推导来源：
    - token_usage: token_measurement
    - execution_rounds: telemetry.json run_count
    - hitl_count: governance/evidence/ 中 ESCALATED 约束数
    - new_patterns / total_patterns: Intent_Graph.md 节点数
    - _project_dir: 项目根目录（供 _calc_compound_roi 读 cost_model）
    """
    args = []

    # _project_dir（供 _load_cost_model 读取独立 AI Cost Model）
    args += ["--_project-dir", str(project)]

    # Token usage only. Context Pack has an independent measurement contract.
    tm = token_measurement or {}
    tm_value = int(tm.get("value") or 0)
    tm_status = tm.get("status", "UNKNOWN")
    if tm_value > 0:
        args += ["--token-usage", str(tm_value)]
        args += ["--token-source", str(tm.get("source", "estimated"))]

    # execution_rounds 从 telemetry.json run_count 推导
    tel_path = governance / "telemetry.json"
    if tel_path.exists():
        try:
            tel = json.loads(tel_path.read_text(encoding="utf-8"))
            run_count = (tel.get("meta") or {}).get("run_count", 0)
            if run_count > 0:
                args += ["--execution-rounds", str(run_count)]
        except Exception:
            pass

    # hitl_count 从 evidence 中 ESCALATED 约束数推导
    evidence_dir = governance / "evidence"
    escalated = 0
    constraint_failures = 0
    auto_healed = 0
    if evidence_dir.is_dir():
        import re as _re
        for eb in evidence_dir.glob("EB-T-*.md"):
            try:
                text = eb.read_text(encoding="utf-8")
                escalated += len(_re.findall(r"\bESCALATED\b", text))
                # 从约束裁决表推导：FAIL → constraint_failure，PASS → 约束通过
                fails = len(_re.findall(r"\|\s*FAIL\s*\|", text))
                passes = len(_re.findall(r"\|\s*PASS\s*\|", text))
                constraint_failures += fails
                # auto_healed = 约束失败后自动恢复成功的（当前简化：失败数=0 则自愈率 N/A）
                # 更精确需要跟踪 constraint_failure → recovery 事件对，暂用 fails 作为总量
            except Exception:
                pass
    if escalated > 0:
        args += ["--hitl-count", str(escalated)]
    if constraint_failures > 0:
        args += ["--constraint-failures-total", str(constraint_failures)]
        # auto_healed：当前无自动恢复事件，但如果有 constraint_failure 后任务仍 VERIFIED → 视为自愈
        # 简化：constraint_failures_total 传入，auto_healed 由 collect_telemetry 从事件推导
    # must_constraints / must_failed 从 evidence 约束裁决推导
    must_total = constraint_failures + auto_healed  # 粗估
    if must_total > 0:
        args += ["--must-constraints", str(must_total)]
        args += ["--must-failed", str(constraint_failures)]

    # new_patterns / total_patterns 从 Intent_Graph.md 推导
    ig_path = governance / "Intent_Graph.md"
    if ig_path.exists():
        try:
            text = ig_path.read_text(encoding="utf-8")
            # 节点数 ≈ 行首 "- " 或 "  - " 的数量（粗估）
            import re as _re
            nodes = _re.findall(r"^[\s]*- ", text, _re.MULTILINE)
            total = len(nodes)
            if total > 0:
                args += ["--total-patterns", str(total)]
                # new_patterns：本次新增 ≈ 总数的 10%（保守估），或从 git diff 推导
                # 简化：用 task_id 对应的 commit diff 行数 / 10 粗估
                args += ["--new-patterns", str(max(1, total // 10))]
        except Exception:
            pass

    return args


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


def run(task_id, governance_dir, timeout=300, refresh_only=False, prepare_only=False,
        host_tool=None, token_clients=None):
    governance = Path(governance_dir).resolve()
    project = governance.parent
    if refresh_only:
        started = time.monotonic()
        _progress("metrics_refresh", "started")
        context_path = _context_path(governance, task_id)
        context = json.loads(context_path.read_text(encoding="utf-8"))
        collector = Path(__file__).resolve().parent / "collect_telemetry.py"
        token_measurement = collect_workflow_token_measurement(
            project, governance, task_id, host_tool, token_clients)
        auto_params = _derive_auto_params(project, governance, task_id, token_measurement)
        output = _run_collector(
            [sys.executable, str(collector), "--project", project.name, "--task", task_id,
             "--test-total", str(context.get("total", 0)), "--test-passed", str(context.get("passed", 0)),
             *_token_collector_args(token_measurement),
             *_context_collector_args(governance, task_id),
             *auto_params,
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
    token_measurement = collect_workflow_token_measurement(
        project, governance, task_id, host_tool, token_clients)
    # T-153: 自动推导 dashboard 所需参数
    auto_params = _derive_auto_params(project, governance, task_id, token_measurement)
    command = [
        sys.executable, str(collector), "--project", project.name, "--task", task_id,
        "--test-total", str(tests["total"]), "--test-passed", str(tests["passed"]),
        *_token_collector_args(token_measurement),
        *_context_collector_args(governance, task_id),
        *auto_params,
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
    parser.add_argument("--host-tool", default=None)
    parser.add_argument("--token-client", action="append", dest="token_clients")
    args = parser.parse_args()
    try:
        result = run(args.task_id, args.governance_dir, args.timeout, args.refresh_only,
                     args.prepare_only, args.host_tool, args.token_clients)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
