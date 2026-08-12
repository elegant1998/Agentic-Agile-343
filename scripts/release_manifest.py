#!/usr/bin/env python3
"""Single-project proof-carrying release manifest planner and checker.

This module never builds, tags, pushes, uploads, deploys, or executes commands
declared by a manifest. Git subprocesses are read-only fact queries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASK_RE = re.compile(r"^T-[A-Za-z0-9][A-Za-z0-9.-]*$")
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
AI_MARKERS = {"ai", "agent", "codex", "claude", "model", "oa"}
ROLLBACK_FIELDS = ("trigger", "method", "owner", "data_compatibility", "configuration_compatibility", "reverify")
CONDITION_FIELDS = ("condition", "owner", "deadline", "reverify")
IGNORED_DIRTY_PREFIXES = ("governance/",)


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
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _validate_task(task_id: str) -> str:
    if not TASK_RE.fullmatch(task_id):
        raise ValueError(f"invalid task id: {task_id!r}")
    return task_id


def _validate_version(version: str) -> str:
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ValueError(f"invalid release version: {version!r}")
    return version


def _project(project_dir: Path | str) -> Path:
    project = Path(project_dir).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"project directory does not exist: {project}")
    return project


def _safe_path(project: Path, raw: Path | str, *, require_file: bool = True) -> Path:
    value = str(raw)
    if not value or value.startswith(("http://", "https://")) or "$(" in value or "`" in value:
        raise ValueError(f"unsafe project path: {value!r}")
    path = Path(value).expanduser()
    resolved = path.resolve() if path.is_absolute() else (project / path).resolve()
    try:
        resolved.relative_to(project)
    except ValueError as exc:
        raise ValueError(f"path outside project: {value!r}") from exc
    if require_file and (not resolved.is_file() or resolved.is_symlink()):
        raise ValueError(f"not a regular project file: {value!r}")
    return resolved


def _relative(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project).as_posix()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_ref(project: Path, path: Path) -> dict[str, Any]:
    return {"path": _relative(project, path), "sha256": _sha(path), "size": path.stat().st_size}


def _git(project: Path, args: list[str]) -> str:
    completed = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise ValueError("Git fact query failed: " + " ".join(args))
    return completed.stdout.strip()


def _head(project: Path) -> str:
    commit = _git(project, ["rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError("Git HEAD is not a full commit SHA")
    return commit.lower()


def _commit_exists(project: Path, commit: str) -> bool:
    completed = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=project, capture_output=True, check=False)
    return completed.returncode == 0


def _dirty_paths(project: Path, bound_paths: set[str]) -> list[str]:
    raw = _git(project, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    records = raw.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise ValueError("unparseable Git status record")
        status, path = record[:2], record[3:]
        paths.append(path)
        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                raise ValueError("unparseable Git rename/copy record")
            paths.append(records[index])
            index += 1
    ignored = lambda item: item in bound_paths or any(item.startswith(prefix) for prefix in IGNORED_DIRTY_PREFIXES)
    return sorted(set(item for item in paths if not ignored(item)))


def manifest_path_for(project_dir: Path | str, version: str) -> Path:
    project = _project(project_dir)
    return project / "governance" / "releases" / f"Release_Manifest_{_validate_version(version)}.yaml"


def _evidence_for_task(project: Path, task_id: str) -> dict[str, Any]:
    contract = _safe_path(project, f"governance/contracts/Intent_Contract_{task_id}.md")
    bundle = _safe_path(project, f"governance/evidence/EB-{task_id}.md")
    telemetry = _safe_path(project, f"governance/telemetry/runs/telemetry-{task_id}.json")
    graph = _safe_path(project, "governance/Intent_Graph.md")
    verification_path = project / "governance" / "verification" / f"Verification_Plan_{task_id}.yaml"
    return {
        "task_id": task_id,
        "contract": _file_ref(project, contract),
        "bundle": _file_ref(project, bundle),
        "telemetry": _file_ref(project, telemetry),
        "graph": _file_ref(project, graph),
        "verification_plan": _file_ref(project, verification_path) if verification_path.is_file() else None,
        "freshness_hours": 168,
    }


def _configuration_ref(project: Path, paths: list[str] | None) -> dict[str, Any]:
    if not paths:
        return {"paths": [], "sha256": None}
    refs = [_file_ref(project, _safe_path(project, path)) for path in paths]
    combined = hashlib.sha256("".join(ref["sha256"] for ref in sorted(refs, key=lambda item: item["path"])).encode()).hexdigest()
    return {"paths": refs, "sha256": combined}


def build_manifest(project_dir: Path | str, task_id: str, version: str, artifact: Path | str, config_paths: list[str] | None = None) -> dict[str, Any]:
    project = _project(project_dir)
    task_id = _validate_task(task_id)
    version = _validate_version(version)
    artifact_path = _safe_path(project, artifact)
    artifact_ref = _file_ref(project, artifact_path)
    commit = _head(project)
    bound_paths = {artifact_ref["path"]}
    if config_paths:
        bound_paths.update(_relative(project, _safe_path(project, path)) for path in config_paths)
    dirty = _dirty_paths(project, bound_paths)
    return {
        "schema_version": "1.0", "release_id": f"REL-{version}", "version": version,
        "status": "DRAFT", "tasks": [task_id],
        "source": {"commit": commit, "dirty": bool(dirty), "dirty_paths": dirty},
        "artifact": artifact_ref,
        "configuration": _configuration_ref(project, config_paths),
        "evidence": [_evidence_for_task(project, task_id)],
        "approvals": [],
        "rollback": {field: "TBD" for field in ROLLBACK_FIELDS},
        "promotions": [{"environment": "release", "artifact_sha256": artifact_ref["sha256"]}],
        "events": [],
    }


def apply_manifest(project_dir: Path | str, manifest: dict[str, Any]) -> Path:
    path = manifest_path_for(project_dir, str(manifest.get("version", "")))
    if path.exists():
        raise FileExistsError(f"manifest already exists; refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(manifest), encoding="utf-8")
    return path


def _human(value: Any) -> bool:
    text = str(value or "").strip().lower()
    tokens = set(re.findall(r"[a-z]+", text))
    return bool(text) and not (tokens & AI_MARKERS)


def _verify_ref(project: Path, ref: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(ref, dict):
        errors.append(f"{label} reference missing")
        return None
    try:
        path = _safe_path(project, ref.get("path", ""))
    except ValueError as exc:
        errors.append(f"{label}: {exc}")
        return None
    if ref.get("sha256") != _sha(path) or ref.get("size", path.stat().st_size) != path.stat().st_size:
        errors.append(f"{label} digest or size drift")
    return path


def _task_semantics(project: Path, entry: Any, errors: list[str]) -> None:
    if not isinstance(entry, dict) or not TASK_RE.fullmatch(str(entry.get("task_id", ""))):
        errors.append("invalid task evidence entry")
        return
    task_id = entry["task_id"]
    contract = _verify_ref(project, entry.get("contract"), f"{task_id} contract", errors)
    bundle = _verify_ref(project, entry.get("bundle"), f"{task_id} bundle", errors)
    telemetry = _verify_ref(project, entry.get("telemetry"), f"{task_id} telemetry", errors)
    graph = _verify_ref(project, entry.get("graph"), f"{task_id} graph", errors)
    observed_paths = [path for path in (contract, bundle, telemetry, graph) if path]
    if contract:
        text = contract.read_text(encoding="utf-8", errors="replace")
        if "SIGNED" not in text or not re.search(r"IO（意图主理人）.*\|\s*(?!Codex|OA|Agent)[^_|\n]+", text, re.IGNORECASE):
            errors.append(f"{task_id} contract is not human-signed")
    if bundle:
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if "APPROVED" not in text or "PASS" not in text:
            errors.append(f"{task_id} Evidence Bundle is not APPROVED")
    if telemetry:
        try:
            data = json.loads(telemetry.read_text(encoding="utf-8"))
            observed = data.get("meta", {}).get("task_id", data.get("task_id"))
            if observed != task_id:
                errors.append(f"{task_id} telemetry task mismatch")
        except (json.JSONDecodeError, AttributeError):
            errors.append(f"{task_id} telemetry is not parseable")
    if graph:
        matching = [line for line in graph.read_text(encoding="utf-8", errors="replace").splitlines() if task_id in line]
        if not matching or not any("已验证完成" in line or "COMPLETED" in line.upper() for line in matching):
            errors.append(f"{task_id} is not completed in Intent Graph")
    verification = entry.get("verification_plan")
    if verification is not None:
        plan = _verify_ref(project, verification, f"{task_id} Verification Plan", errors)
        if plan:
            observed_paths.append(plan)
            try:
                from verification_plan import check_plan
                result = check_plan(project, task_id, plan)
                if result.get("verdict") != "PASS":
                    errors.append(f"{task_id} Verification Plan is {result.get('verdict')}")
            except Exception as exc:
                errors.append(f"{task_id} Verification Plan check failed: {exc}")
    freshness = entry.get("freshness_hours")
    if not isinstance(freshness, (int, float)) or freshness < 0:
        errors.append(f"{task_id} freshness_hours must be non-negative")
    else:
        now = datetime.now(timezone.utc).timestamp()
        stale = [path for path in observed_paths if now - path.stat().st_mtime > freshness * 3600]
        if stale:
            errors.append(f"{task_id} evidence is stale")


def _check_configuration(project: Path, config: Any, errors: list[str]) -> None:
    if not isinstance(config, dict):
        errors.append("configuration must be an object")
        return
    refs = config.get("paths", [])
    if not isinstance(refs, list):
        errors.append("configuration.paths must be a list")
        return
    actual: list[dict[str, Any]] = []
    for index, ref in enumerate(refs):
        path = _verify_ref(project, ref, f"configuration {index + 1}", errors)
        if path:
            actual.append({"path": _relative(project, path), "sha256": _sha(path)})
    expected = None if not actual else hashlib.sha256("".join(item["sha256"] for item in sorted(actual, key=lambda item: item["path"])).encode()).hexdigest()
    if config.get("sha256") != expected:
        errors.append("configuration digest drift")


def check_manifest(project_dir: Path | str, manifest_path: Path | str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        project = _project(project_dir)
        path = _safe_path(project, manifest_path)
        data = _load(path)
        version = _validate_version(str(data.get("version", "")))
        if data.get("release_id") != f"REL-{version}":
            errors.append("release_id does not match version")
        status = data.get("status")
        if status not in {"AUTHORIZED", "CONDITIONAL", "RELEASED", "ROLLED_BACK"}:
            errors.append("manifest status must be AUTHORIZED before readiness check")
        tasks = data.get("tasks")
        if not isinstance(tasks, list) or not tasks or any(not TASK_RE.fullmatch(str(task)) for task in tasks):
            errors.append("tasks must contain valid T-IDs")
            tasks = []
        source = data.get("source")
        artifact = data.get("artifact")
        if not isinstance(source, dict):
            errors.append("source binding missing")
            source = {}
        commit = str(source.get("commit", ""))
        if not re.fullmatch(r"[0-9a-fA-F]{40}", commit) or not _commit_exists(project, commit):
            errors.append("source commit is invalid or unknown")
        elif _head(project) != commit.lower():
            errors.append("current HEAD differs from bound source commit")
        artifact_path = _verify_ref(project, artifact, "artifact", errors)
        if artifact_path:
            artifact_relative = _relative(project, artifact_path)
            config = data.get("configuration")
            config_bound = set()
            if isinstance(config, dict) and isinstance(config.get("paths"), list):
                for ref in config["paths"]:
                    if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                        config_bound.add(ref["path"])
            dirty = _dirty_paths(project, {artifact_relative, *config_bound})
            if dirty:
                errors.append("unbound dirty source paths: " + ", ".join(dirty))
            artifact_digest = _sha(artifact_path)
            promotions = data.get("promotions")
            if not isinstance(promotions, list) or not promotions:
                errors.append("promotions must bind at least one environment")
            elif any(not isinstance(item, dict) or item.get("artifact_sha256") != artifact_digest for item in promotions):
                errors.append("promotion artifact digest drift")
        _check_configuration(project, data.get("configuration"), errors)
        evidence = data.get("evidence")
        if not isinstance(evidence, list) or {entry.get("task_id") for entry in evidence if isinstance(entry, dict)} != set(tasks):
            errors.append("evidence entries must exactly cover tasks")
            evidence = evidence if isinstance(evidence, list) else []
        for entry in evidence:
            _task_semantics(project, entry, errors)
        approvals = data.get("approvals")
        if not isinstance(approvals, list) or not any(isinstance(item, dict) and item.get("decision") == "APPROVED" and _human(item.get("actor")) for item in approvals):
            errors.append("qualified human release approval missing")
        rollback = data.get("rollback")
        if not isinstance(rollback, dict) or any(not rollback.get(field) or rollback.get(field) == "TBD" for field in ROLLBACK_FIELDS):
            errors.append("rollback plan is incomplete")
        if not isinstance(data.get("events"), list):
            errors.append("events must be a list")
        condition = data.get("condition")
        if status == "CONDITIONAL" and (not isinstance(condition, dict) or any(not condition.get(field) for field in CONDITION_FIELDS)):
            errors.append("CONDITIONAL terms are incomplete")
    except ValueError as exc:
        return {"verdict": "BLOCKED", "passed": False, "errors": [str(exc)]}

    if errors:
        verdict = "BLOCKED"
    elif status == "CONDITIONAL":
        verdict = "CONDITIONAL"
    elif status in {"RELEASED", "ROLLED_BACK"}:
        verdict = status
    else:
        verdict = "READY_FOR_HUMAN_RELEASE"
    return {"release_id": data.get("release_id"), "version": data.get("version"), "verdict": verdict, "passed": verdict in {"READY_FOR_HUMAN_RELEASE", "RELEASED", "ROLLED_BACK"}, "errors": errors}


def record_event(project_dir: Path | str, manifest_path: Path | str, event: str, actor: str, evidence_path: Path | str) -> dict[str, Any]:
    project = _project(project_dir)
    manifest_file = _safe_path(project, manifest_path)
    if event not in {"released", "rolled_back"}:
        raise ValueError("event must be released or rolled_back")
    if not _human(actor):
        raise ValueError("record actor must be a qualified human or external accountable identity")
    evidence_file = _safe_path(project, evidence_path)
    evidence = _load(evidence_file)
    data = _load(manifest_file)
    if evidence.get("release_id") != data.get("release_id") or evidence.get("version") != data.get("version") or evidence.get("event") != event or not evidence.get("occurred_at"):
        raise ValueError("event evidence does not match manifest/event")
    evidence_digest = _sha(evidence_file)
    event_id = "EVT-" + hashlib.sha256(f"{event}|{actor}|{evidence_digest}".encode()).hexdigest()[:16]
    events = data.get("events")
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    if any(isinstance(item, dict) and item.get("event_id") == event_id for item in events):
        return data
    if event == "released":
        readiness = check_manifest(project, manifest_file)
        if readiness["verdict"] != "READY_FOR_HUMAN_RELEASE":
            raise ValueError("release cannot be recorded before readiness PASS")
    elif data.get("status") != "RELEASED" or not any(isinstance(item, dict) and item.get("event") == "released" for item in events):
        raise ValueError("rollback requires a prior released event")
    original_binding = {key: data.get(key) for key in ("release_id", "version", "tasks", "source", "artifact", "configuration", "evidence")}
    events.append({"event_id": event_id, "event": event, "actor": actor, "occurred_at": evidence["occurred_at"], "evidence": _file_ref(project, evidence_file)})
    data["status"] = "RELEASED" if event == "released" else "ROLLED_BACK"
    if original_binding != {key: data.get(key) for key in original_binding}:
        raise ValueError("release binding changed while recording event")
    manifest_file.write_text(_dump(data), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-project proof-carrying Release Manifest")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="create a measured DRAFT; dry-run unless --apply")
    plan.add_argument("--task", required=True)
    plan.add_argument("--version", required=True)
    plan.add_argument("--artifact", required=True)
    plan.add_argument("--config", action="append", dest="config_paths")
    plan.add_argument("--project-dir", default=".")
    plan.add_argument("--apply", action="store_true")
    for name in ("check", "status"):
        command = sub.add_parser(name, help=f"{name} a manifest without publishing")
        command.add_argument("--manifest", required=True)
        command.add_argument("--project-dir", default=".")
    record = sub.add_parser("record", help="append an already-executed release/rollback fact")
    record.add_argument("--manifest", required=True)
    record.add_argument("--event", choices=("released", "rolled_back"), required=True)
    record.add_argument("--actor", required=True)
    record.add_argument("--evidence", required=True)
    record.add_argument("--project-dir", default=".")
    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = build_manifest(args.project_dir, args.task, args.version, args.artifact, args.config_paths)
            if args.apply:
                result["path"] = str(apply_manifest(args.project_dir, result))
            print(_dump(result), end="")
            return
        if args.command in {"check", "status"}:
            result = check_manifest(args.project_dir, args.manifest)
            print(_dump(result), end="")
            sys.exit(0 if result["passed"] else 1)
        result = record_event(args.project_dir, args.manifest, args.event, args.actor, args.evidence)
        print(_dump(result), end="")
    except (ValueError, FileExistsError) as exc:
        print(json.dumps({"verdict": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
