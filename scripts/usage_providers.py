#!/usr/bin/env python3
"""Tool-neutral usage snapshots and task-delta validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class UsageProvider(Protocol):
    provider_id: str

    def snapshot(self, identity: dict, task_id: str | None = None) -> dict:
        ...


def _unknown(identity: dict, provider_id: str, detail: str, task_id: str | None) -> dict:
    return {
        "provider_id": provider_id, "counter_id": None,
        "project_uid": identity.get("project_uid"), "project_root": identity.get("project_root"),
        "task_id": task_id, "host_tool": "other", "token_client": None,
        "input": None, "output": None, "value": None, "measured_at": None,
        "status": "UNKNOWN", "scope": "task_snapshot", "source": "unavailable",
        "evidence": [], "detail": detail, "provider_metadata": {},
    }


def normalize_usage_snapshot(raw: dict, identity: dict, provider_id: str,
                             task_id: str | None = None) -> dict:
    if not isinstance(raw, dict):
        return _unknown(identity, provider_id, "provider returned a non-object snapshot", task_id)
    snapshot = {
        **_unknown(identity, provider_id, "", task_id),
        **raw,
        "provider_id": str(raw.get("provider_id") or provider_id),
        "project_uid": raw.get("project_uid") or identity.get("project_uid"),
        "project_root": raw.get("project_root") or identity.get("project_root"),
        "evidence": list(raw.get("evidence") or []),
        "provider_metadata": dict(raw.get("provider_metadata") or {}),
    }
    if snapshot["project_uid"] != identity.get("project_uid"):
        return {**snapshot, "value": None, "status": "UNKNOWN",
                "detail": "provider snapshot project does not match requested project"}
    supplied_task = raw.get("task_id")
    if task_id and supplied_task and supplied_task != task_id:
        return {**snapshot, "value": None, "status": "UNKNOWN",
                "detail": "provider snapshot task does not match requested task"}
    if snapshot.get("scope") == "task_snapshot" and task_id and not supplied_task:
        return {**snapshot, "value": None, "status": "UNKNOWN",
                "detail": "task-scoped provider snapshot is missing task binding"}
    try:
        snapshot["value"] = int(snapshot["value"]) if snapshot.get("value") is not None else None
        for key in ("input", "output"):
            snapshot[key] = int(snapshot[key]) if snapshot.get(key) is not None else None
    except (TypeError, ValueError):
        return {**snapshot, "value": None, "status": "UNKNOWN",
                "detail": "provider snapshot contains non-numeric usage counters"}
    if snapshot["value"] is None or not snapshot.get("counter_id"):
        return {**snapshot, "value": None, "status": "UNKNOWN",
                "detail": snapshot.get("detail") or "provider snapshot is missing value or counter_id"}
    return snapshot


class StructuredFileUsageProvider:
    """Consume a host-neutral JSON snapshot emitted by any AI tool or bridge."""

    provider_id = "structured-file"

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()

    def snapshot(self, identity: dict, task_id: str | None = None) -> dict:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return _unknown(identity, self.provider_id, f"structured usage file unavailable: {exc}", task_id)
        raw = dict(raw) if isinstance(raw, dict) else raw
        if isinstance(raw, dict):
            raw.setdefault("source", f"measured:file:{self.path}")
            raw.setdefault("evidence", [str(self.path)])
        return raw


def collect_usage_snapshot(identity: dict, task_id: str | None,
                           providers: list[UsageProvider]) -> dict:
    failures = []
    for provider in providers:
        provider_id = str(getattr(provider, "provider_id", provider.__class__.__name__))
        try:
            raw = provider.snapshot(identity, task_id)
        except Exception as exc:
            failures.append(f"{provider_id}: {exc}")
            continue
        snapshot = normalize_usage_snapshot(raw, identity, provider_id, task_id)
        if snapshot.get("value") is not None and snapshot.get("status") not in {"UNKNOWN", "UNAVAILABLE"}:
            return snapshot
        failures.append(f"{provider_id}: {snapshot.get('detail') or snapshot.get('status')}")
    return _unknown(identity, "none", "; ".join(failures) or "no usage provider configured", task_id)


def usage_delta(baseline: dict | None, current: dict | None) -> dict:
    current = dict(current or {})
    required = ("provider_id", "counter_id", "project_uid")
    compatible = bool(baseline and current)
    if compatible:
        compatible = all(baseline.get(key) and baseline.get(key) == current.get(key) for key in required)
    if compatible and (baseline.get("task_id") or current.get("task_id")):
        compatible = bool(baseline.get("task_id") and
                          baseline.get("task_id") == current.get("task_id"))
    try:
        monotonic = (baseline.get("value") is not None and current.get("value") is not None and
                     int(current["value"]) >= int(baseline["value"]))
    except (AttributeError, TypeError, ValueError):
        monotonic = False
    if not compatible or not monotonic:
        return {**current, "value": None, "status": "UNKNOWN", "scope": "task_delta",
                "detail": "provider/counter/project/task binding changed or counter reset"}
    return {**current, "value": int(current["value"]) - int(baseline["value"]),
            "status": "MEASURED", "scope": "task_delta",
            "detail": "end_snapshot_minus_start_snapshot"}
