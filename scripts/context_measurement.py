#!/usr/bin/env python3
"""Deterministic Context Pack measurement independent of the host AI tool."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "context-pack-measurement/v1"


def measurement_path(governance: Path | str, task_id: str) -> Path:
    return Path(governance) / "telemetry" / "context-measurements" / f"{task_id}.json"


def _payload(text: str) -> dict:
    encoded = text.encode("utf-8")
    return {
        "units": len(encoded), "unit": "utf8_bytes",
        "estimated_tokens": math.ceil(len(encoded) / 4),
        "token_status": "ESTIMATED", "token_estimator": "utf8-bytes/4-v1",
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _ratio(numerator: int, denominator: int, *, empty_status: str = "NOT_APPLICABLE") -> dict:
    if denominator == 0:
        return {"value": None, "status": empty_status}
    return {"value": round(numerator / denominator, 4), "status": "MEASURED"}


def build_context_measurement(
    *, task_id: str, project: Path | str, candidate_text: str, injected_text: str,
    candidate_sources: list[str] | None = None, injected_sources: list[str] | None = None,
    required_sources: list[str] | None = None, candidate_trace_ids: list[str] | None = None,
    retained_trace_ids: list[str] | None = None, budget_tokens: int | None = None,
) -> dict:
    from token_usage import project_identity

    candidate_sources = list(dict.fromkeys(candidate_sources or []))
    injected_sources = list(dict.fromkeys(injected_sources or []))
    required_sources = list(dict.fromkeys(required_sources or []))
    candidate_traces = list(dict.fromkeys(candidate_trace_ids or []))
    retained_traces = [item for item in dict.fromkeys(retained_trace_ids or [])
                       if item in candidate_traces]
    retained_required = [item for item in required_sources if item in injected_sources]
    missing_required = [item for item in required_sources if item not in injected_sources]
    candidate = _payload(candidate_text)
    injected = _payload(injected_text)
    required = _ratio(len(retained_required), len(required_sources))
    if required["value"] is not None:
        required["status"] = "MEASURED" if not missing_required else "INCOMPLETE"
    required.update({"retained": retained_required, "required": required_sources,
                     "missing": missing_required})
    trace = _ratio(len(retained_traces), len(candidate_traces))
    trace.update({"retained": retained_traces, "candidate": candidate_traces})
    budget = _ratio(injected["estimated_tokens"], int(budget_tokens or 0))
    if budget["value"] is not None:
        budget["status"] = "ESTIMATED"
    budget.update({"estimated_tokens": injected["estimated_tokens"],
                   "budget_tokens": budget_tokens, "estimator": "utf8-bytes/4-v1"})
    return {
        "schema": SCHEMA, "task_id": task_id,
        "project_uid": project_identity(project)["project_uid"],
        "counter": "utf8_bytes", "measured_at": datetime.now(timezone.utc).isoformat(),
        "status": "MEASURED", "source": "crop_context",
        "candidate": candidate, "injected": injected,
        "candidate_sources": candidate_sources, "injected_sources": injected_sources,
        "compression_ratio": _ratio(candidate["units"], injected["units"]),
        "required_retention": required, "trace_coverage": trace,
        "budget_utilization": budget,
    }


def validate_context_measurement(measurement: dict, task_id: str | None = None,
                                 project_uid: str | None = None) -> bool:
    if not isinstance(measurement, dict) or measurement.get("schema") != SCHEMA:
        return False
    if task_id and measurement.get("task_id") != task_id:
        return False
    if project_uid and measurement.get("project_uid") != project_uid:
        return False
    candidate, injected = measurement.get("candidate"), measurement.get("injected")
    return bool(isinstance(candidate, dict) and isinstance(injected, dict) and
                candidate.get("unit") == injected.get("unit") == measurement.get("counter") and
                isinstance(candidate.get("units"), int) and isinstance(injected.get("units"), int))


def write_context_measurement(path: Path | str, measurement: dict) -> Path:
    path = Path(path)
    if not validate_context_measurement(measurement):
        raise ValueError("invalid context measurement")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(measurement, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_context_measurement(path: Path | str, task_id: str | None = None,
                             project_uid: str | None = None) -> dict | None:
    try:
        measurement = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return measurement if validate_context_measurement(measurement, task_id, project_uid) else None
