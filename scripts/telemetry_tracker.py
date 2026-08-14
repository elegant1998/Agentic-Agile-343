#!/usr/bin/env python3
"""Append-only task event ledger and trustworthy P0 measurement derivation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from runtime_context import load_trusted_verification_context

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
TASK_RE = re.compile(r"^(?:[A-Z0-9]+-)*T-[A-Z0-9]+(?:-[A-Z0-9]+)*$")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _metric(value, status, source, evidence=None, measured_at=None):
    return {
        "value": value, "status": status, "source": source,
        "evidence": list(evidence or []), "measured_at": measured_at,
    }


def _ledger(project):
    return Path(project).resolve() / "governance/telemetry/execution-events.jsonl"


def _index(project):
    return Path(project).resolve() / "governance/telemetry/execution-events.index.sqlite3"


def _open_index(project):
    path = _index(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, task_id TEXT, event TEXT, offset INTEGER)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS events_task ON events(task_id, offset)")
    connection.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    return connection


def _ensure_index(project):
    ledger = _ledger(project)
    connection = _open_index(project)
    indexed = connection.execute("SELECT value FROM meta WHERE key='ledger_size'").fetchone()
    actual_size = ledger.stat().st_size if ledger.is_file() else 0
    if indexed and int(indexed[0]) == actual_size:
        return connection
    connection.execute("DELETE FROM events")
    offset = 0
    if ledger.is_file():
        with ledger.open("rb") as stream:
            for raw in stream:
                try:
                    item = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    offset += len(raw)
                    continue
                if item.get("event_id"):
                    connection.execute(
                        "INSERT OR IGNORE INTO events(event_id, task_id, event, offset) VALUES(?,?,?,?)",
                        (item["event_id"], item.get("task_id"), item.get("event"), offset),
                    )
                offset += len(raw)
    connection.execute(
        "INSERT INTO meta(key,value) VALUES('ledger_size',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(actual_size),),
    )
    connection.commit()
    return connection


def read_events(project, task_id=None):
    path = _ledger(project)
    if not path.is_file():
        return []
    if task_id:
        connection = _ensure_index(project)
        offsets = [row[0] for row in connection.execute(
            "SELECT offset FROM events WHERE task_id=? ORDER BY offset", (task_id,)
        )]
        connection.close()
        events = []
        with path.open("rb") as stream:
            for offset in offsets:
                stream.seek(offset)
                try:
                    events.append(json.loads(stream.readline().decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
        return events
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
    connection = _ensure_index(project)
    existing = connection.execute("SELECT 1 FROM events WHERE event_id=?", (payload["event_id"],)).fetchone()
    if not existing:
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        offset = path.stat().st_size if path.is_file() else 0
        with path.open("ab") as stream:
            stream.write(rendered)
        connection.execute(
            "INSERT INTO events(event_id, task_id, event, offset) VALUES(?,?,?,?)",
            (payload["event_id"], task_id, event, offset),
        )
        connection.execute(
            "INSERT INTO meta(key,value) VALUES('ledger_size',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(offset + len(rendered)),),
        )
        connection.commit()
    connection.close()
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


def _normalized_task_id(value):
    return str(value or "").strip().strip("`").upper()


def _artifact_task_id(path, text, *, evidence=False):
    patterns = (
        r"(?:\*\*)?(?:任务\s*ID|task[_\s-]*id)(?:\*\*)?\s*[：:]\s*`?([A-Z0-9][A-Z0-9_-]*)",
        r"^\s*\|\s*(?:任务\s*ID|task[_\s-]*id)\s*\|\s*`?([A-Z0-9][A-Z0-9_-]*)",
        r"^\s*#\s*(?:Evidence\s+Bundle\s*[—-]|Intent\s+Contract)\s+`?([A-Z0-9][A-Z0-9_-]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            return _normalized_task_id(match.group(1))
    stem = path.stem
    prefixes = ("EB-", "Evidence_Bundle_") if evidence else ("Intent_Contract_",)
    for prefix in prefixes:
        if stem.lower().startswith(prefix.lower()):
            stem = stem[len(prefix):]
            break
    return _normalized_task_id(stem)


def _find_task_artifact(directory, task, *, evidence=False):
    if not directory.is_dir():
        return None
    expected = _normalized_task_id(task)
    suffixes = {".md"} if evidence else {".md", ".yaml", ".yml"}
    matches = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _artifact_task_id(path, text, evidence=evidence) == expected:
            matches.append((path, text))
    return matches[0] if len(matches) == 1 else None


def _has_explicit_status(text, status):
    escaped = re.escape(status)
    patterns = (
        rf"^\s*>?\s*(?:\*\*)?状态(?:\*\*)?\s*[：:]\s*\*{{0,2}}{escaped}\b",
        rf"^\s*\|\s*(?:状态|Status)\s*\|\s*\*{{0,2}}{escaped}\b",
        rf"^\s*status\s*:\s*['\"]?{escaped}\b",
    )
    return any(re.search(pattern, text, re.I | re.M) for pattern in patterns)


def _closed_contract_has_signature(text):
    signer = re.search(
        r"(?:签署人|确认人)(?:（?IO）?)?(?:\*\*)?\s*[：:|]\s*(?!无\b|N/?A\b|UNKNOWN\b)\S+",
        text, re.I,
    )
    signed_at = re.search(r"签署日期(?:\*\*)?\s*[：:|]\s*\d{4}-\d{2}-\d{2}", text, re.I)
    return bool(_has_explicit_status(text, "CLOSED") and signer and signed_at)


def _signed_contract(project, task):
    """Return the signed contract; completion is derived separately.

    ``SIGNED`` is the immutable IO authorization state for an Intent
    Contract. A completed task must not mutate the contract into another
    status; ``tasks_completed`` is derived from passing Evidence instead.
    """
    base = Path(project).resolve() / "governance/contracts"
    artifact = _find_task_artifact(base, task)
    if artifact is None:
        return None
    path, text = artifact
    status = re.escape(CONTRACT_AUTHORIZATION_STATUS)
    signed = re.search(rf"\b{status}\b", text, re.I) and re.search(
        r"(?:IO|确认人|签署人|意图主理人)", text, re.I
    )
    if signed or _closed_contract_has_signature(text):
        return path
    return None


def _markdown_cells(line):
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_row(cells):
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _is_pass_result(value):
    raw = str(value or "").strip().strip("*` ")
    if raw in {"✅", "✓", "✔", "☑"}:
        return True
    return bool(re.match(r"^(?:PASS(?:ED)?|APPROVED|VERIFIED)(?:\b|\s|[:：,，])", raw, re.I))


def _evidence_declares_pass(text):
    patterns = (
        r"^\s*>?\s*(?:\*\*)?状态(?:\*\*)?\s*[：:]\s*.*\b全部\s*AC\s*PASS\b",
        r"^\s*\|\s*(?:技术裁决|最终裁决|Technical\s+Verdict|Final\s+Verdict)\s*\|\s*(?:PASS|APPROVED|VERIFIED)\b",
    )
    return any(re.search(pattern, text, re.I | re.M) for pattern in patterns)


def _passing_evidence(project, task, contract=None):
    base = Path(project).resolve() / "governance/evidence"
    artifact = _find_task_artifact(base, task, evidence=True)
    if artifact is None:
        return None
    path, text = artifact
    ac_results, constraint_results = [], []
    result_index = None
    for line in text.splitlines():
        cells = _markdown_cells(line)
        if len(cells) < 2 or _is_separator_row(cells):
            continue
        headers = [cell.strip().lower() for cell in cells]
        if any(cell in {"结果", "result", "status", "verdict", "裁决"} for cell in headers):
            result_index = next(
                index for index, cell in enumerate(headers)
                if cell in {"结果", "result", "status", "verdict", "裁决"}
            )
            continue
        identifier = cells[0].strip().upper()
        value_index = result_index if result_index is not None and result_index < len(cells) else 1
        if re.fullmatch(r"AC-[0-9]+(?:/AC-[0-9]+)*", identifier):
            ac_results.append(cells[value_index])
        elif re.match(r"^C-[A-Z]+-[0-9]+(?:\s|$)", identifier):
            constraint_results.append(cells[value_index])
    if not ac_results or not all(_is_pass_result(value) for value in ac_results):
        return None
    if constraint_results:
        return path if all(_is_pass_result(value) for value in constraint_results) else None
    if contract is None:
        return None
    contract_text = Path(contract).read_text(encoding="utf-8", errors="ignore")
    return path if _closed_contract_has_signature(contract_text) and _evidence_declares_pass(text) else None


def _passing_verification_context(project, task):
    base = Path(project).resolve() / "governance/telemetry/verification-runs"
    if not base.is_dir():
        return None
    expected = _normalized_task_id(task)
    matches = []
    for path in sorted(base.glob("*.json")):
        payload, _reason = load_trusted_verification_context(path, project)
        if payload is None:
            continue
        task_id = _normalized_task_id(payload.get("task_id") or path.stem)
        if task_id != expected:
            continue
        total = int(payload.get("total") or 0)
        passed = int(payload.get("passed") or 0)
        failed = int(payload.get("failed") or 0)
        errors = int(payload.get("errors") or 0)
        if str(payload.get("status") or "").upper() == "PASS" and total > 0 and passed == total and not failed and not errors:
            matches.append((path, payload))
    return matches[0] if len(matches) == 1 else None


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
        evidence = _passing_evidence(project, task_id, contract)
        if evidence:
            result["tasks_completed"] = _metric(1, "DERIVED", "passing_evidence", [_relative(evidence, project)], now)
            if result["tasks_first_pass"]["status"] == "UNKNOWN":
                run = _passing_verification_context(project, task_id)
                if run:
                    run_path, payload = run
                    result["tasks_first_pass"] = _metric(
                        1, "DERIVED", "verification_run_context",
                        [_relative(run_path, project)], payload.get("finished_at") or now,
                    )
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
