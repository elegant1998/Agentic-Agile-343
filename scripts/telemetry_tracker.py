#!/usr/bin/env python3
"""Append-only task event ledger and trustworthy P0 measurement derivation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

RAW_METRICS = (
    "tasks_assigned", "tasks_completed", "tasks_first_pass",
    "constraint_failures_total", "auto_healed",
)
CONTRACT_AUTHORIZATION_STATUS = "SIGNED"
EVENTS = {
    "task_assigned", "verification_result", "constraint_failed",
    "constraint_resolved", "constraint_reverified", "task_completed", "tdd_red", "formal_verification",
}
FORMAL_RESULTS = {"VERIFIED", "CONDITIONAL", "BLOCKED"}
TASK_RE = re.compile(r"^T-[0-9]{3,}(?:-[A-Z0-9]+)*$")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _metric(value, status, source, evidence=None, measured_at=None):
    return {
        "value": value, "status": status, "source": source,
        "evidence": list(evidence or []), "measured_at": measured_at,
    }


def _ledger(project):
    return Path(project).resolve() / "governance/telemetry/execution-events.jsonl"


def read_events(project, task_id=None):
    path = _ledger(project)
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not task_id or item.get("task_id") == task_id:
            events.append(item)
    return events


def append_event(project, task_id, event, *, result=None, actor=None,
                 evidence=None, constraint_id=None, occurred_at=None, **extra):
    task_id = str(task_id or "").upper()
    if not TASK_RE.fullmatch(task_id):
        raise ValueError("task id must match T-XXX")
    if event not in EVENTS:
        raise ValueError(f"unsupported event: {event}")
    payload = {
        "task_id": task_id, "event": event, "result": result,
        "actor": actor, "constraint_id": constraint_id,
        "occurred_at": occurred_at or _now(), "evidence": list(evidence or []),
    }
    payload.update(extra)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["event_id"] = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    path = _ledger(project)
    existing = {e.get("event_id") for e in read_events(project)}
    if payload["event_id"] not in existing:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return payload


def append_formal_verification(project, task_id, *, result, prove_status,
                               evidence_status, telemetry_status, source,
                               evidence=None, conditions=None, occurred_at=None):
    result = str(result or "").upper()
    conditions = list(conditions or [])
    if result not in FORMAL_RESULTS:
        raise ValueError("formal verification result must be VERIFIED, CONDITIONAL, or BLOCKED")
    if result == "CONDITIONAL" and not conditions:
        raise ValueError("CONDITIONAL formal verification requires conditions")
    history = [e for e in read_events(project, str(task_id).upper()) if e.get("event") == "formal_verification"]
    evidence = list(evidence or [])
    for prior in reversed(history):
        if (str(prior.get("result", "")).upper(), prior.get("source"), prior.get("evidence", []), prior.get("conditions", [])) == (result, source, evidence, conditions):
            return prior
    return append_event(project, task_id, "formal_verification", result=result, actor="workflow",
                        evidence=evidence, occurred_at=occurred_at, attempt=len(history) + 1,
                        prove_status=prove_status, evidence_status=evidence_status,
                        telemetry_status=telemetry_status, source=source, conditions=conditions)


def formal_result_from_evidence(evidence_path: Path | str) -> tuple[str, list[str]]:
    text = Path(evidence_path).read_text(encoding="utf-8", errors="ignore")
    verdict = "CONDITIONAL" if re.search(r"技术裁决\s*\|\s*CONDITIONAL", text, re.I) else "VERIFIED"
    if re.search(r"技术裁决\s*\|\s*(?:FAIL|BLOCKED)", text, re.I):
        verdict = "BLOCKED"
    conditions = []
    if verdict == "CONDITIONAL":
        conditions = [line.strip() for line in text.splitlines() if "待" in line or "CONDITIONAL" in line.upper()]
        conditions = conditions[:10] or ["evidence contains conditional technical verdict"]
    return verdict, conditions


def _relative(path, project):
    try:
        return str(path.relative_to(Path(project).resolve()))
    except ValueError:
        return str(path)


def _signed_contract(project, task):
    """Return the signed contract; completion is derived separately.

    ``SIGNED`` is the immutable IO authorization state for an Intent
    Contract. A completed task must not mutate the contract into another
    status; ``tasks_completed`` is derived from passing Evidence instead.
    """
    base = Path(project).resolve() / "governance/contracts"
    paths = list(base.glob(f"Intent_Contract_{task}.*")) if base.is_dir() else []
    status = re.escape(CONTRACT_AUTHORIZATION_STATUS)
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"\b{status}\b", text, re.I) and re.search(r"(?:IO|确认人|意图主理人)", text, re.I):
            return path
    return None


def _passing_evidence(project, task):
    path = Path(project).resolve() / f"governance/evidence/EB-{task}.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    ac_results, constraint_results = [], []
    for line in text.splitlines():
        cells = [cell.strip().upper() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if re.fullmatch(r"AC-[0-9]+", cells[0]):
            ac_results.append(cells[1])
        elif re.fullmatch(r"C-[A-Z]+-[0-9]+(?:\s+[^|]*)?", cells[0]):
            constraint_results.append(cells[1])
    return path if ac_results and constraint_results and all(x == "PASS" for x in ac_results + constraint_results) else None


def derive_measurements(project, task_id):
    project = Path(project).resolve()
    task_id = str(task_id).upper()
    now = _now()
    result = {name: _metric(None, "UNKNOWN", "missing_source") for name in RAW_METRICS}
    contract = _signed_contract(project, task_id)
    if contract:
        result["tasks_assigned"] = _metric(1, "DERIVED", "signed_contract", [_relative(contract, project)], now)
    ledger = _ledger(project)
    events = read_events(project, task_id)
    formal = [e for e in events if e.get("event") == "formal_verification"]
    if formal:
        latest = formal[-1]
        latest_result = str(latest.get("result", "")).upper()
        result["tasks_completed"] = _metric(
            1 if latest_result == "VERIFIED" else 0,
            "MEASURED", "formal_verification_event", latest.get("evidence"), latest.get("occurred_at"),
        )
        first = formal[0]
        result["tasks_first_pass"] = _metric(
            1 if str(first.get("result", "")).upper() == "VERIFIED" else 0,
            "MEASURED", "formal_verification_event", first.get("evidence"), first.get("occurred_at"),
        )
    else:
        legacy_formal = [e for e in events if e.get("event") == "verification_result"]
        if legacy_formal:
            first = legacy_formal[0]
            result["tasks_first_pass"] = _metric(
                1 if str(first.get("result", "")).upper() == "PASS" else 0,
                "MEASURED", "execution_event_ledger", first.get("evidence"), first.get("occurred_at"),
            )
        evidence = _passing_evidence(project, task_id)
        if evidence:
            result["tasks_completed"] = _metric(1, "DERIVED", "passing_evidence", [_relative(evidence, project)], now)
    if ledger.is_file():
        failures = [e for e in events if e.get("event") == "constraint_failed" and e.get("constraint_id")]
        unique = {e["constraint_id"]: e for e in failures}
        if not unique:
            na = _metric(None, "NOT_APPLICABLE", "execution_event_ledger", [str(ledger.relative_to(project))], now)
            result["constraint_failures_total"] = dict(na)
            result["auto_healed"] = dict(na)
        else:
            healed = 0
            for cid in unique:
                agent_resolved = any(e.get("event") == "constraint_resolved" and e.get("constraint_id") == cid and e.get("actor") == "agent" for e in events)
                passed = any(e.get("event") == "constraint_reverified" and e.get("constraint_id") == cid and str(e.get("result")).upper() == "PASS" for e in events)
                healed += int(agent_resolved and passed)
            ev = [str(ledger.relative_to(project))]
            result["constraint_failures_total"] = _metric(len(unique), "MEASURED", "execution_event_ledger", ev, now)
            result["auto_healed"] = _metric(healed, "MEASURED", "execution_event_ledger", ev, now)
    return result


def main():
    parser = argparse.ArgumentParser(description="追加遥测执行事件或查看派生度量")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--event", choices=sorted(EVENTS))
    parser.add_argument("--result")
    parser.add_argument("--actor")
    parser.add_argument("--constraint-id")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--occurred-at")
    args = parser.parse_args()
    if args.event:
        payload = append_event(args.project_dir, args.task, args.event, result=args.result,
                               actor=args.actor, constraint_id=args.constraint_id,
                               evidence=args.evidence, occurred_at=args.occurred_at)
    else:
        payload = derive_measurements(args.project_dir, args.task)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
