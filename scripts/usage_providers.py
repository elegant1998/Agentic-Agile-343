#!/usr/bin/env python3
"""Tool-neutral usage snapshots and task-delta validation."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class UsageProvider(Protocol):
    provider_id: str

    def snapshot(self, identity: dict, task_id: str | None = None) -> dict:
        ...


def canonical_task_id(task_id: str | None) -> str | None:
    value = str(task_id or "").strip()
    return value.upper() if value else None


def _unknown(identity: dict, provider_id: str, detail: str, task_id: str | None) -> dict:
    return {
        "provider_id": provider_id, "counter_id": None,
        "project_uid": identity.get("project_uid"), "project_root": identity.get("project_root"),
        "task_id": canonical_task_id(task_id), "principal_id": None,
        "host_tool": "other", "token_client": None,
        "input": None, "output": None, "value": None, "measured_at": None,
        "status": "UNKNOWN", "scope": "task_snapshot", "source": "unavailable",
        "evidence": [], "detail": detail, "provider_metadata": {},
    }


def normalize_usage_snapshot(raw: dict, identity: dict, provider_id: str,
                             task_id: str | None = None) -> dict:
    task_id = canonical_task_id(task_id)
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
    snapshot["task_id"] = canonical_task_id(snapshot.get("task_id") or task_id)
    if snapshot["project_uid"] != identity.get("project_uid"):
        return {**snapshot, "value": None, "status": "UNKNOWN",
                "detail": "provider snapshot project does not match requested project"}
    supplied_task = canonical_task_id(raw.get("task_id"))
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


class CodexRolloutUsageProvider:
    """Read the monotonic counter for the current Codex thread.

    Codex Desktop may keep appending current events to a rollout stored under the
    thread's creation date, so event timestamps and CODEX_THREAD_ID are the only
    trustworthy lookup keys. Project and task binding happens at capture time.
    """

    provider_id = "codex-rollout"

    def __init__(self, codex_home: Path | str | None = None,
                 thread_id: str | None = None):
        self.codex_home = Path(
            codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex"
        ).expanduser()
        self.thread_id = str(thread_id or os.environ.get("CODEX_THREAD_ID") or "").strip()

    def _candidates(self) -> list[Path]:
        if not self.thread_id:
            return []
        pattern = f"rollout-*{self.thread_id}.jsonl"
        matches = []
        sessions = self.codex_home / "sessions"
        if sessions.is_dir():
            matches.extend(sessions.rglob(pattern))
        archived = self.codex_home / "archived_sessions"
        if archived.is_dir():
            matches.extend(archived.glob(pattern))
        return sorted(set(path.resolve() for path in matches))

    def snapshot_at(self, identity: dict, task_id: str | None = None,
                    cutoff: str | None = None) -> dict:
        if not self.thread_id:
            return _unknown(identity, self.provider_id,
                            "CODEX_THREAD_ID is unavailable; refusing to guess an active thread",
                            task_id)
        candidates = self._candidates()
        if len(candidates) != 1:
            detail = ("codex rollout is unavailable" if not candidates else
                      f"ambiguous codex rollouts for thread {self.thread_id}")
            return _unknown(identity, self.provider_id, detail, task_id)

        latest = None
        try:
            with candidates[0].open("r", encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = event.get("payload") or {}
                    if event.get("type") != "event_msg" or payload.get("type") != "token_count":
                        continue
                    timestamp = str(event.get("timestamp") or "")
                    if cutoff and timestamp > cutoff:
                        continue
                    usage = ((payload.get("info") or {}).get("total_token_usage") or {})
                    try:
                        total = int(usage.get("total_tokens"))
                        input_tokens = int(usage.get("input_tokens") or 0)
                        output_tokens = int(usage.get("output_tokens") or 0)
                    except (TypeError, ValueError):
                        continue
                    latest = {
                        "value": total, "input": input_tokens, "output": output_tokens,
                        "measured_at": timestamp,
                    }
        except OSError as exc:
            return _unknown(identity, self.provider_id,
                            f"codex rollout is unreadable: {exc}", task_id)
        if latest is None:
            return _unknown(identity, self.provider_id,
                            "codex rollout contains no token_count event", task_id)
        return {
            **latest,
            "provider_id": self.provider_id,
            "counter_id": f"codex-rollout:{self.thread_id}",
            "project_uid": identity.get("project_uid"),
            "project_root": identity.get("project_root"),
            "task_id": canonical_task_id(task_id),
            "principal_id": None,
            "host_tool": "codex",
            "token_client": "codex",
            "status": "CUMULATIVE_SNAPSHOT",
            "scope": "thread_cumulative_snapshot",
            "source": "measured:codex-rollout",
            "evidence": [str(candidates[0])],
            "detail": "current Codex thread cumulative counter",
            "provider_metadata": {"thread_id": self.thread_id},
        }

    def snapshot(self, identity: dict, task_id: str | None = None) -> dict:
        return self.snapshot_at(identity, task_id)

    def task_delta_between(self, identity: dict, task_id: str,
                           start: str, end: str) -> dict:
        baseline = normalize_usage_snapshot(
            self.snapshot_at(identity, task_id, start), identity, self.provider_id, task_id
        )
        current = normalize_usage_snapshot(
            self.snapshot_at(identity, task_id, end), identity, self.provider_id, task_id
        )
        result = usage_delta(baseline, current)
        if result.get("status") == "MEASURED":
            result["source"] = "measured:codex-rollout-range"
            result["evidence"] = list(dict.fromkeys(
                list(baseline.get("evidence") or []) + list(current.get("evidence") or [])
            ))
            result["provider_metadata"] = {
                **dict(result.get("provider_metadata") or {}),
                "requested_start": start,
                "requested_end": end,
                "baseline_at": baseline.get("measured_at"),
                "current_at": current.get("measured_at"),
            }
            result["input"] = int(current.get("input") or 0) - int(baseline.get("input") or 0)
            result["output"] = int(current.get("output") or 0) - int(baseline.get("output") or 0)
            result["detail"] = "codex rollout counter delta within signed task time window"
        return result


def discover_task_usage_snapshot(project: Path | str, task_id: str | None) -> Path | None:
    """Find one host-neutral per-task snapshot without depending on a host tool."""
    task_id = canonical_task_id(task_id)
    if not task_id:
        return None
    directory = Path(project).resolve() / "governance" / "telemetry" / "usage-snapshots"
    if not directory.is_dir():
        return None
    matches = sorted(
        path for path in directory.glob("*.json")
        if path.stem.casefold() == task_id.casefold()
    )
    if len(matches) > 1:
        raise ValueError(f"ambiguous task usage snapshots for {task_id}")
    return matches[0] if matches else None


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
        compatible = bool(canonical_task_id(baseline.get("task_id")) and
                          canonical_task_id(baseline.get("task_id")) ==
                          canonical_task_id(current.get("task_id")))
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
