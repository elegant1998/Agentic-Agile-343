#!/usr/bin/env python3
"""Finalize one Evidence Bundle by collecting its telemetry and dashboards.

This module is the single write-oriented handoff between a completed task
Evidence Bundle and the cross-platform ``telemetry_workflow.py`` collector. It does
not approve or modify evidence, and it deliberately keeps ``gate_check.py``
read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from gov_common import find_contract, find_evidence_bundle
from telemetry_tracker import append_formal_verification, formal_result_from_evidence


TASK_ID_PATTERN = re.compile(r"^T-[0-9]{3,}(?:-[A-Z0-9]+)*$")
AC_RESULT_PATTERN = re.compile(
    r"\bAC-[0-9]+\b[^\n]*(?:PASS|FAIL|UNKNOWN|CONDITIONAL|ESCALATED)", re.IGNORECASE
)
CONSTRAINT_RESULT_PATTERN = re.compile(
    r"\bC-[A-Z]+-[0-9]+\b[^\n]*(?:PASS|FAIL|UNKNOWN|CONDITIONAL|ESCALATED)",
    re.IGNORECASE,
)


class FinalizeError(RuntimeError):
    """Evidence cannot be finalized with trustworthy telemetry."""


def _validate_task_id(raw: str) -> str:
    task_id = str(raw or "").strip().upper()
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("task id must match T-XXX or T-XXX-SUFFIX")
    return task_id


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path)


def _output_state(paths: list[Path]) -> dict[Path, tuple[int, int, str] | None]:
    state: dict[Path, tuple[int, int, str] | None] = {}
    for path in paths:
        if path.is_file():
            stat = path.stat()
            state[path] = (stat.st_mtime_ns, stat.st_size, _sha256(path))
        else:
            state[path] = None
    return state


def _assert_evidence_ready(evidence: Path, task_id: str) -> str:
    try:
        text = evidence.read_text(encoding="utf-8")
    except OSError as exc:
        raise FinalizeError(f"Evidence 无法读取: {evidence}: {exc}") from exc
    if task_id not in text:
        raise FinalizeError(f"Evidence 任务 ID 与 {task_id} 不一致")
    if not AC_RESULT_PATTERN.search(text):
        raise FinalizeError("Evidence 缺少带裁决状态的 AC 验证结果")
    if not CONSTRAINT_RESULT_PATTERN.search(text):
        raise FinalizeError("Evidence 缺少带裁决状态的约束检查结果")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FinalizeError(f"缺少{label}: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalizeError(f"{label}不可解析: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FinalizeError(f"{label}根节点必须是对象: {path}")
    return payload


def _verify_outputs(project: Path, task_id: str, before: dict[Path, tuple[int, int, str] | None]) -> dict[str, str]:
    governance = project / "governance"
    run_path = governance / "telemetry" / "runs" / f"telemetry-{task_id}.json"
    project_path = governance / "telemetry.json"
    project_dashboard = governance / "dashboard.html"
    task_dashboard = governance / f"dashboard-{task_id}.html"
    required = [run_path, project_path, project_dashboard, task_dashboard]

    for path in required:
        if not path.is_file():
            raise FinalizeError(f"遥测收口缺少产物: {path}")
        previous = before.get(path)
        current = _output_state([path])[path]
        if previous is not None and current == previous:
            raise FinalizeError(f"遥测收口未更新既有产物: {path}")

    run = _read_json(run_path, "单任务遥测")
    if (run.get("meta") or {}).get("task_id") != task_id:
        raise FinalizeError("单任务遥测 meta.task_id 与契约不一致")

    aggregate = _read_json(project_path, "项目累计遥测")
    runs = aggregate.get("runs")
    if not isinstance(runs, list):
        raise FinalizeError("项目累计遥测 runs 必须是数组")
    matches = [item for item in runs if isinstance(item, dict) and item.get("task_id") == task_id]
    if len(matches) != 1:
        detail = "重复" if len(matches) > 1 else "缺失"
        raise FinalizeError(f"项目累计遥测 runs 中目标任务{detail}: {task_id}")
    run_count = (aggregate.get("meta") or {}).get("run_count")
    if run_count != len(runs):
        raise FinalizeError(f"项目累计遥测 meta.run_count={run_count} 与 runs={len(runs)} 不一致")

    return {
        "contract_telemetry": str(run_path),
        "project_telemetry": str(project_path),
        "project_dashboard": str(project_dashboard),
        "contract_dashboard": str(task_dashboard),
    }


def finalize_evidence(project_dir: Path | str, task_id: str, timeout_seconds: int = 1800) -> dict[str, Any]:
    project = Path(project_dir).resolve()
    task_id = _validate_task_id(task_id)
    if not project.is_dir():
        raise FinalizeError(f"项目目录不存在: {project}")

    contract = find_contract(project, task_id)
    if contract is None:
        raise FinalizeError(f"未找到契约: {task_id}")
    evidence = find_evidence_bundle(project, task_id)
    if evidence is None:
        raise FinalizeError(f"未找到 Evidence Bundle: {task_id}")
    evidence_digest = _assert_evidence_ready(evidence, task_id)

    governance = project / "governance"
    outputs = [
        governance / "telemetry" / "runs" / f"telemetry-{task_id}.json",
        governance / "telemetry.json",
        governance / "dashboard.html",
        governance / f"dashboard-{task_id}.html",
    ]
    before = _output_state(outputs)
    collector = Path(__file__).resolve().parent / "telemetry_workflow.py"
    if not collector.is_file():
        raise FinalizeError(f"Python 遥测编排器不存在: {collector}")
    command = [sys.executable, str(collector), task_id, str(governance)]
    try:
        completed = subprocess.run(
            command,
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FinalizeError(f"telemetry workflow 执行失败: {type(exc).__name__}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "无输出").strip()[-2000:]
        raise FinalizeError(f"telemetry workflow 退出码 {completed.returncode}: {detail}")

    artifacts = _verify_outputs(project, task_id, before)
    if _sha256(evidence) != evidence_digest:
        raise FinalizeError("Evidence Bundle 在遥测收口过程中被修改；拒绝完成")
    result, conditions = formal_result_from_evidence(evidence)
    append_formal_verification(
        project, task_id, result=result, prove_status="PASS",
        evidence_status="READY_FOR_HITL" if result == "CONDITIONAL" else "PASS",
        telemetry_status="FINALIZED", source="evidence_finalize",
        evidence=[_relative(evidence, project), _relative(Path(artifacts["contract_telemetry"]), project)],
        conditions=conditions,
    )
    # Recompute once after the event exists so P0 metrics consume the new fact.
    try:
        completed = subprocess.run(
            command, cwd=str(project), capture_output=True, text=True,
            timeout=timeout_seconds, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FinalizeError(f"formal verification telemetry refresh failed: {type(exc).__name__}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "无输出").strip()[-2000:]
        raise FinalizeError(f"formal verification telemetry refresh exited {completed.returncode}: {detail}")
    return {
        "status": "EVIDENCE_FINALIZED_WITH_TELEMETRY",
        "task_id": task_id,
        "contract": str(contract),
        "evidence": str(evidence),
        "artifacts": artifacts,
        "collector_output": completed.stdout[-4000:],
        "formal_verification": {"result": result, "conditions": conditions},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence 完成后调用遥测工作流，按 tracker/collector 事实生成契约遥测与双 Dashboard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    finalize = subparsers.add_parser("finalize", help="校验证据并自动完成遥测收口")
    finalize.add_argument("--task", required=True)
    finalize.add_argument("--project-dir", default=".")
    finalize.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    try:
        result = finalize_evidence(args.project_dir, args.task, args.timeout)
    except (ValueError, FinalizeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
