#!/usr/bin/env python3
"""Gate-maintenance channel for low-risk deterministic tooling defects.

Records use JSON syntax in ``.yaml`` files. JSON is valid YAML while keeping
this safety-critical path on the Python standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


ELIGIBILITY_FIELDS = (
    "deterministic_tool_defect",
    "reproducible",
    "business_scope_unchanged",
    "gate_strength_preserved",
    "permissions_unchanged",
    "approval_boundaries_unchanged",
)
RISK_FLAGS = (
    "changes_gate_semantics",
    "changes_signing_semantics",
    "expands_permissions",
    "adds_bypass_or_exception",
)
ID_PATTERN = re.compile(r"^M-[0-9]{3,}$")


def _validate_id(maintenance_id: str) -> str:
    maintenance_id = maintenance_id.upper()
    if not ID_PATTERN.fullmatch(maintenance_id):
        raise ValueError("maintenance id must match M-XXX")
    return maintenance_id


def _record_path(project_dir: Path, maintenance_id: str) -> Path:
    return project_dir.resolve() / "governance" / "maintenance" / f"{_validate_id(maintenance_id)}.yaml"


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"maintenance record not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"maintenance record is not valid JSON-compatible YAML: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("maintenance record root must be an object")
    return payload


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_command(command: Any, cwd: Path) -> dict[str, Any]:
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        return {"returncode": -1, "stdout": "", "stderr": "command must be a non-empty string array"}
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}


def open_record(project_dir: Path, maintenance_id: str, affected_task: str) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    maintenance_id = _validate_id(maintenance_id)
    path = _record_path(project_dir, maintenance_id)
    if path.exists():
        return {"id": maintenance_id, "action": "skipped", "path": str(path)}

    payload = {
        "schema_version": "1.0",
        "id": maintenance_id,
        "affected_task": affected_task,
        "created": date.today().isoformat(),
        "status": "REPORTED",
        "report": {"symptom": "PENDING", "expected": "PENDING", "actual": "PENDING"},
        "eligibility": {field: None for field in ELIGIBILITY_FIELDS},
        "risk_flags": {field: False for field in RISK_FLAGS},
        "reproduction": {"command": []},
        "red_evidence": None,
        "verification": {"full_test_command": []},
        "decision": {"route": "PENDING", "reasons": []},
    }
    _write(path, payload)
    return {"id": maintenance_id, "action": "created", "path": str(path), "status": "REPORTED"}


def check_record(project_dir: Path, maintenance_id: str) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    path = _record_path(project_dir, maintenance_id)
    payload = _load(path)
    if payload.get("status") == "RED":
        return {"id": payload["id"], "eligible": True, "action": "already-red", "reasons": []}
    if payload.get("status") == "CLOSED":
        return {"id": payload["id"], "eligible": True, "action": "already-closed", "reasons": []}

    eligibility = payload.get("eligibility") if isinstance(payload.get("eligibility"), dict) else {}
    risk_flags = payload.get("risk_flags") if isinstance(payload.get("risk_flags"), dict) else {}
    reasons = [field for field in ELIGIBILITY_FIELDS if eligibility.get(field) is not True]
    reasons.extend(field for field in RISK_FLAGS if risk_flags.get(field) is not False)

    if reasons:
        payload["status"] = "ESCALATED"
        payload["decision"] = {"route": "AMENDMENT_OR_NEW_CONTRACT", "reasons": reasons}
        _write(path, payload)
        return {"id": payload["id"], "eligible": False, "action": "escalated", "reasons": reasons}

    red = _run_command(payload.get("reproduction", {}).get("command"), project_dir)
    if red["returncode"] <= 0:
        reasons = ["reproduction did not produce a real RED"]
        payload["status"] = "ESCALATED"
        payload["decision"] = {"route": "AMENDMENT_OR_NEW_CONTRACT", "reasons": reasons}
        _write(path, payload)
        return {"id": payload["id"], "eligible": False, "action": "escalated", "reasons": reasons}

    payload["status"] = "RED"
    payload["red_evidence"] = red
    payload["decision"] = {"route": "MAINTENANCE", "reasons": []}
    _write(path, payload)
    return {"id": payload["id"], "eligible": True, "action": "red-recorded", "reasons": []}


def close_record(project_dir: Path, maintenance_id: str) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    path = _record_path(project_dir, maintenance_id)
    payload = _load(path)
    if payload.get("status") == "CLOSED":
        return {"id": payload["id"], "closed": True, "action": "already-closed", "reasons": []}
    if payload.get("status") != "RED" or not payload.get("red_evidence"):
        return {"id": payload.get("id", maintenance_id), "closed": False, "action": "blocked", "reasons": ["prior RED evidence missing"]}

    reasons: list[str] = []
    focused = _run_command(payload.get("reproduction", {}).get("command"), project_dir)
    if focused["returncode"] != 0:
        reasons.append("focused GREEN verification failed")
    full = _run_command(payload.get("verification", {}).get("full_test_command"), project_dir)
    if full["returncode"] != 0:
        reasons.append("full regression failed")

    maintenance_id = _validate_id(maintenance_id)
    evidence = project_dir / "governance" / "maintenance" / "evidence" / f"ME-{maintenance_id}.md"
    telemetry = project_dir / "governance" / "telemetry" / "runs" / f"telemetry-{maintenance_id}.json"
    graph = project_dir / "governance" / "Intent_Graph.md"
    if not evidence.exists():
        reasons.append("maintenance evidence missing")
    if not telemetry.exists():
        reasons.append("maintenance telemetry missing")
    if not graph.exists() or maintenance_id not in graph.read_text(encoding="utf-8"):
        reasons.append("Intent Graph lesson missing")

    if reasons:
        return {"id": maintenance_id, "closed": False, "action": "blocked", "reasons": reasons}

    payload["status"] = "CLOSED"
    payload["verification"]["focused_result"] = focused
    payload["verification"]["full_result"] = full
    payload["decision"] = {"route": "MAINTENANCE", "reasons": []}
    _write(path, payload)
    return {"id": maintenance_id, "closed": True, "action": "closed", "reasons": []}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Low-risk gate maintenance channel")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("open", "check", "close"):
        child = subparsers.add_parser(command)
        child.add_argument("--id", required=True, dest="maintenance_id")
        child.add_argument("--project-dir", default=".")
        if command == "open":
            child.add_argument("--task", required=True, dest="affected_task")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "open":
            result = open_record(Path(args.project_dir), args.maintenance_id, args.affected_task)
        elif args.command == "check":
            result = check_record(Path(args.project_dir), args.maintenance_id)
        else:
            result = close_record(Path(args.project_dir), args.maintenance_id)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("eligible") is False or result.get("closed") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
