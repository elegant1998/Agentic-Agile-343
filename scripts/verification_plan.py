#!/usr/bin/env python3
"""Risk-driven verification planning and evidence independence checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LAYERS = ("unit", "component", "interface", "ui_journey", "sit", "performance", "security", "data", "uat", "production")
INDEPENDENCE = {"SELF": 0, "CROSS_CHECK": 1, "INDEPENDENT": 2, "HUMAN_ACCEPTANCE": 3}
VERDICTS = {"PASS", "FAIL", "UNKNOWN", "CONDITIONAL", "ESCALATED"}
RISK_DEFAULTS = {
    "low": (["unit"], "SELF"),
    "medium": (["unit", "interface"], "CROSS_CHECK"),
    "high": (["unit", "security"], "INDEPENDENT"),
    "safety_critical": (["unit", "security", "uat"], "HUMAN_ACCEPTANCE"),
}
TRACE_RE = re.compile(r"^(?:AC|PRESERVE|CONSTRAINT)-[A-Za-z0-9][A-Za-z0-9._-]*$")
TASK_RE = re.compile(r"^T-[A-Za-z0-9][A-Za-z0-9.-]*$")
AI_MARKERS = ("ai", "agent", "codex", "claude", "model", "oa")


def _load(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"not readable: {path}") from exc
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
            raise ValueError(f"not valid YAML/JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"root must be an object: {path}")
    return data


def _dump(data: dict[str, Any]) -> str:
    """JSON is valid YAML and keeps the public tool dependency-free."""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _validate_task(task_id: str) -> str:
    if not TASK_RE.fullmatch(task_id):
        raise ValueError(f"invalid task id: {task_id!r}")
    return task_id


def plan_path_for(project_dir: Path | str, task_id: str) -> Path:
    return Path(project_dir).expanduser().resolve() / "governance" / "verification" / f"Verification_Plan_{_validate_task(task_id)}.yaml"


def build_plan(task_id: str, risk: str = "medium", traces: list[str] | None = None) -> dict[str, Any]:
    _validate_task(task_id)
    if risk not in RISK_DEFAULTS:
        raise ValueError(f"unsupported risk: {risk}")
    traces = traces or ["AC-001"]
    if not traces or any(not isinstance(item, str) or not TRACE_RE.fullmatch(item) for item in traces):
        raise ValueError("traces must contain AC-, PRESERVE-, or CONSTRAINT- identifiers")
    layers, independence = RISK_DEFAULTS[risk]
    obligations = []
    for index, trace in enumerate(traces, 1):
        obligations.append({
            "id": f"VP-{index:03d}", "traces_to": trace, "risk": risk,
            "required_layers": list(layers), "evidence_sources": [],
            "producer": "TBD", "verifier": "TBD",
            "independence_required": independence, "freshness_hours": 24,
            "verdict": "UNKNOWN",
        })
    return {"version": "1.0", "task_id": task_id, "status": "DRAFT", "obligations": obligations}


def apply_plan(project_dir: Path | str, plan: dict[str, Any]) -> Path:
    path = plan_path_for(project_dir, str(plan.get("task_id", "")))
    if path.exists():
        raise FileExistsError(f"plan already exists; refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(plan), encoding="utf-8")
    return path


def _safe_evidence_path(project: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw or any(token in raw for token in ("$(", "`")):
        raise ValueError(f"unsafe evidence path: {raw!r}")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe evidence path: {raw!r}")
    resolved = (project / path).resolve()
    try:
        resolved.relative_to(project)
    except ValueError as exc:
        raise ValueError(f"evidence outside project: {raw!r}") from exc
    return resolved


def _parse_time(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("generated_at is missing")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at is not ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _declared_verdict(item: dict[str, Any], errors: list[str]) -> str:
    verdict = item.get("verdict")
    if verdict not in VERDICTS:
        errors.append(f"invalid verdict: {verdict!r}")
        return "UNKNOWN"
    if verdict == "CONDITIONAL":
        missing = [name for name in ("condition", "owner", "deadline", "reverify") if not item.get(name)]
        if missing:
            errors.append("CONDITIONAL missing: " + ", ".join(missing))
            return "UNKNOWN"
    return verdict


def _check_obligation(project: Path, task_id: str, item: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return {"id": "UNKNOWN", "verdict": "UNKNOWN", "errors": ["obligation must be an object"]}
    identifier = item.get("id", "UNKNOWN")
    trace = item.get("traces_to")
    if not isinstance(trace, str) or not TRACE_RE.fullmatch(trace):
        errors.append(f"invalid traces_to: {trace!r}")
    risk = item.get("risk")
    if risk not in RISK_DEFAULTS:
        errors.append(f"invalid risk: {risk!r}")
    required = item.get("required_layers")
    if not isinstance(required, list) or not required or any(layer not in LAYERS for layer in required):
        errors.append("required_layers must contain supported layers")
        required = []
    required_independence = item.get("independence_required")
    if required_independence not in INDEPENDENCE:
        errors.append(f"invalid independence_required: {required_independence!r}")
        required_independence = "HUMAN_ACCEPTANCE"
    freshness = item.get("freshness_hours")
    if freshness is not None and (not isinstance(freshness, (int, float)) or freshness < 0):
        errors.append("freshness_hours must be non-negative or null")
        freshness = 0
    sources = item.get("evidence_sources")
    if not isinstance(sources, list) or not sources:
        errors.append("missing evidence_sources")
        sources = []

    covered: set[str] = set()
    source_ids: set[str] = set()
    duplicate_source = False
    actual_independence = -1
    llm_only = bool(sources)
    human_invalid = False
    now = datetime.now(timezone.utc)
    for index, source in enumerate(sources, 1):
        if not isinstance(source, dict):
            errors.append(f"evidence {index} must be an object")
            continue
        layer = source.get("layer")
        if layer not in LAYERS:
            errors.append(f"evidence {index} has invalid layer")
        try:
            path = _safe_evidence_path(project, source.get("path"))
            evidence = _load(path)
            if evidence.get("task_id", evidence.get("task")) != task_id:
                raise ValueError("task mismatch")
            if evidence.get("verdict", evidence.get("result")) != "PASS":
                raise ValueError("evidence verdict is not PASS")
            generated = _parse_time(evidence.get("generated_at"))
            if freshness is not None and (now - generated).total_seconds() > freshness * 3600:
                raise ValueError("evidence is stale")
            fingerprint = str(evidence.get("source_id") or hashlib.sha256(path.read_bytes()).hexdigest())
            if fingerprint in source_ids:
                duplicate_source = True
            source_ids.add(fingerprint)
            if layer in LAYERS:
                covered.add(layer)
        except (OSError, ValueError) as exc:
            errors.append(f"evidence {index}: {exc}")
            continue
        independence = source.get("independence")
        if independence not in INDEPENDENCE:
            errors.append(f"evidence {index} has invalid independence")
        else:
            actual_independence = max(actual_independence, INDEPENDENCE[independence])
        kind = str(source.get("kind", "")).lower()
        llm_only &= kind == "llm_judge"
        if required_independence == "HUMAN_ACCEPTANCE":
            verifier = str(source.get("verifier", "")).strip().lower()
            tokens = set(re.findall(r"[a-z]+", verifier))
            if not verifier or any(marker in tokens for marker in AI_MARKERS):
                human_invalid = True

    missing_layers = sorted(set(required) - covered)
    if missing_layers:
        errors.append("missing required layers: " + ", ".join(missing_layers))
    if actual_independence < INDEPENDENCE[required_independence]:
        errors.append(f"independence below {required_independence}")
    if duplicate_source:
        errors.append("same source fingerprint reused; renamed/copied evidence is not independent")
    if llm_only and risk in {"high", "safety_critical"}:
        errors.append("LLM-as-Judge cannot be the only key evidence")

    declared = _declared_verdict(item, errors)
    if human_invalid:
        verdict = "ESCALATED"
        errors.append("HUMAN_ACCEPTANCE requires a qualified human verifier")
    elif errors:
        verdict = "FAIL" if any("verdict is not PASS" in error for error in errors) else "UNKNOWN"
    else:
        verdict = declared
    return {"id": identifier, "traces_to": trace, "verdict": verdict, "errors": errors, "covered_layers": sorted(covered)}


def _aggregate(items: list[dict[str, Any]]) -> str:
    verdicts = {item["verdict"] for item in items}
    for verdict in ("FAIL", "ESCALATED", "UNKNOWN", "CONDITIONAL"):
        if verdict in verdicts:
            return verdict
    return "PASS" if items and verdicts == {"PASS"} else "UNKNOWN"


def check_plan(project_dir: Path | str, task_id: str, plan_path: Path | str | None = None) -> dict[str, Any]:
    project = Path(project_dir).expanduser().resolve()
    try:
        _validate_task(task_id)
        if not project.is_dir():
            raise ValueError(f"project directory does not exist: {project}")
        path = Path(plan_path).expanduser() if plan_path else plan_path_for(project, task_id)
        if not path.is_absolute():
            path = (project / path).resolve()
        try:
            path.resolve().relative_to(project)
        except ValueError as exc:
            raise ValueError("verification plan must be inside project") from exc
        data = _load(path)
        if data.get("task_id", data.get("task")) != task_id:
            raise ValueError(f"task_id mismatch: expected {task_id}")
        if data.get("status") != "AUTHORIZED":
            raise ValueError("Verification Plan status must be AUTHORIZED")
        raw_items = data.get("obligations")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("obligations must be a non-empty list")
    except ValueError as exc:
        return {"task_id": task_id, "status": "FAIL_CLOSED", "verdict": "UNKNOWN", "passed": False, "obligations": [], "errors": [str(exc)]}
    items = [_check_obligation(project, task_id, item) for item in raw_items]
    verdict = _aggregate(items)
    return {"task_id": task_id, "status": "CHECKED", "verdict": verdict, "passed": verdict == "PASS", "obligations": items, "errors": []}


def render_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Risk-driven Verification Plan and independent evidence checker")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="create a DRAFT plan; dry-run unless --apply")
    plan.add_argument("--task", required=True)
    plan.add_argument("--project-dir", default=".")
    plan.add_argument("--risk", choices=tuple(RISK_DEFAULTS), default="medium")
    plan.add_argument("--trace", action="append", dest="traces")
    plan.add_argument("--apply", action="store_true")
    for name in ("check", "status"):
        command = sub.add_parser(name, help=f"{name} an AUTHORIZED plan without executing commands")
        command.add_argument("--task", required=True)
        command.add_argument("--project-dir", default=".")
        command.add_argument("--plan")
    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = build_plan(args.task, args.risk, args.traces)
            if args.apply:
                result["path"] = str(apply_plan(args.project_dir, result))
            print(render_result(result), end="")
            return
        result = check_plan(args.project_dir, args.task, args.plan)
        print(render_result(result), end="")
        sys.exit(0 if result["passed"] else 1)
    except (ValueError, FileExistsError) as exc:
        print(json.dumps({"verdict": "UNKNOWN", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
