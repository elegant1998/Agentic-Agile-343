#!/usr/bin/env python3
"""Optional Document Map and Code Map adapters for progressive Recon."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TRUSTED_DOCUMENT_STATUSES = {"ACTIVE", "APPROVED", "SIGNED", "VALID", "CURRENT"}
EXCLUDED_DOCUMENT_STATUSES = {"DEPRECATED", "EXPIRED", "REVOKED"}
PROVIDER_DEFAULTS = {
    "document_map": "IWE",
    "code_map": "codebase-memory-mcp",
}
PROJECT_ARTIFACTS = {
    "document_map": "governance/recon/document_map_artifact.json",
    "code_map": "governance/recon/code_map_artifact.json",
}
LOCAL_ARTIFACTS = {
    kind: f"governance/recon/.local/{Path(relative).name}" for kind, relative in PROJECT_ARTIFACTS.items()
}
MAP_SCHEMA = "agentic-agile-map/v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_revision(project: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True,
        check=False, timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def detect_capabilities(agent_providers: Iterable[str] = ()) -> dict:
    """Report visible capability without pretending CLI can enumerate host MCPs."""
    exposed = {item.strip().lower() for item in agent_providers if item.strip()}
    document_agent = bool(exposed & {"iwe", "document_map", "document-map"})
    code_agent = bool(exposed & {"codebase-memory-mcp", "code_map", "code-map"})
    return {
        "document_map": {
            "provider": "IWE",
            "status": "available" if document_agent or shutil.which("iwe") else "unavailable",
            "access_mode": "agent_exposed" if document_agent else ("cli_available" if shutil.which("iwe") else "unavailable"),
        },
        "code_map": {
            "provider": "codebase-memory-mcp",
            "status": "available" if code_agent else "unavailable",
            "access_mode": "agent_exposed" if code_agent else "unavailable",
        },
    }


def _load_artifact(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError("artifact is not JSON and optional PyYAML is unavailable") from exc
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError("provider artifact root must be an object")
    return value


def _provider_meta(payload: dict, path: Path, kind: str, current_revision: str | None) -> dict:
    provider = payload.get("provider", PROVIDER_DEFAULTS[kind])
    if isinstance(provider, dict):
        name = provider.get("name", PROVIDER_DEFAULTS[kind])
        queried_at = provider.get("queried_at")
        revision = provider.get("source_revision")
    else:
        name, queried_at, revision = provider, None, None
    revision = payload.get("revision", revision)
    fresh = not revision or not current_revision or revision in {current_revision, f"git:{current_revision}"}
    return {
        "kind": kind,
        "name": str(name),
        "access_mode": "artifact_available",
        "status": "available" if fresh else "stale",
        "queried_at": payload.get("queried_at", queried_at) or _utc_now(),
        "source_revision": revision,
        "artifact": str(path),
        "authority": payload.get("authority", "shared"),
        "fresh": fresh,
    }


def _normalize_item(item: dict, meta: dict) -> dict:
    normalized = dict(item)
    normalized["classification"] = str(item.get("classification", "CANDIDATE")).upper()
    normalized["provider"] = meta["name"]
    normalized["provider_kind"] = meta["kind"]
    normalized["queried_at"] = meta["queried_at"]
    normalized["source_revision"] = meta["source_revision"]
    normalized["evidence"] = list(item.get("evidence", [f"artifact:{meta['artifact']}"]))
    return normalized


def discover_project_maps(project_dir: Path | str, current_revision: str | None = None) -> list[Path]:
    """Prefer shared artifacts, then project-local fallback artifacts per kind."""
    project = Path(project_dir).expanduser().resolve()
    found = []
    for kind, relative in PROJECT_ARTIFACTS.items():
        shared = project / relative
        local = project / LOCAL_ARTIFACTS[kind]
        if shared.is_file():
            try:
                payload = _load_artifact(shared)
                meta = _provider_meta(payload, shared, kind, current_revision if current_revision is not None else _git_revision(project))
            except (OSError, ValueError):
                meta = {"fresh": False}
            if meta["fresh"] or not local.is_file():
                found.append(shared)
            else:
                found.append(local)
        elif local.is_file():
            found.append(local)
    return found


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _json_output(result: subprocess.CompletedProcess, max_output_bytes: int = 2_000_000) -> object:
    if result.returncode != 0:
        raise ValueError((result.stderr or "provider query failed").strip())
    if len((result.stdout or "").encode("utf-8")) > max_output_bytes:
        raise ValueError(f"provider output exceeded {max_output_bytes} bytes")
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("provider returned invalid JSON") from exc


def _run_bounded_json(argv: list[str], project: Path, timeout_seconds: int,
                      max_output_bytes: int) -> tuple[subprocess.CompletedProcess, object]:
    """Keep provider stdout off the Python heap until its byte budget is verified."""
    with tempfile.TemporaryFile(mode="w+b") as output:
        result = subprocess.run(
            argv, cwd=project, stdout=output, stderr=subprocess.PIPE, text=True,
            check=False, timeout=timeout_seconds,
        )
        # Test doubles may return stdout directly; real subprocesses write to output.
        if isinstance(getattr(result, "stdout", None), str):
            return result, _json_output(result, max_output_bytes=max_output_bytes)
        if result.returncode != 0:
            raise ValueError((result.stderr or "provider query failed").strip())
        size = output.tell()
        if size > max_output_bytes:
            raise ValueError(f"provider output exceeded {max_output_bytes} bytes")
        output.seek(0)
        try:
            return result, json.loads(output.read().decode("utf-8") or "[]")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("provider returned invalid JSON") from exc


def _as_rows(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("items", "results", "nodes", "data", "rows"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _normalize_native_rows(rows: list[dict], kind: str) -> list[dict]:
    normalized = []
    for row in rows:
        identifier = row.get("id") or row.get("key") or row.get("symbol_id") or row.get("qualified_name")
        if not identifier:
            continue
        item = {key: value for key, value in row.items() if key not in {"absolute_path", "project_root"}}
        item["id"] = str(identifier)
        item["classification"] = "CANDIDATE"
        if kind == "document_map":
            item["status"] = str(item.get("status", "ACTIVE")).upper()
        normalized.append(item)
    return sorted(normalized, key=lambda item: item["id"])


def _diagnostic(provider: str, status: str, reason: str, impact: str, command: str = "") -> dict:
    return {
        "provider": provider, "status": status, "reason": reason, "impact": impact,
        "blocking": False, "last_known_good": False,
        "recommended_action": {"command": command, "automatic": False},
    }


def build_project_maps(project_dir: Path | str, persistence: bool = True, mode: str = "single",
                       max_items: int = 100, max_tokens: int = 12000,
                       timeout_seconds: int = 60, max_output_bytes: int = 2_000_000) -> dict:
    """Run CLI-visible providers with explicit project and persistence boundaries."""
    project = Path(project_dir).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"project directory does not exist: {project}")
    commands: list[dict] = []
    unavailable: list[str] = []
    diagnostics: list[dict] = []
    if mode not in {"single", "team"}:
        raise ValueError("mode must be single or team")
    if max_items <= 0 or max_tokens <= 0 or timeout_seconds <= 0 or max_output_bytes <= 0:
        raise ValueError("max_items, max_tokens, timeout_seconds, and max_output_bytes must be positive")
    current_revision = _git_revision(project)
    for kind, provider in PROVIDER_DEFAULTS.items():
        shared = project / PROJECT_ARTIFACTS[kind]
        if shared.is_file():
            try:
                shared_payload = _load_artifact(shared)
                authority = str(shared_payload.get("authority", "shared"))
                fresh = _provider_meta(shared_payload, shared, kind, current_revision)["fresh"]
            except (OSError, ValueError):
                authority = "damaged"
                fresh = False
            if authority == "ci" and mode == "team" and fresh:
                commands.append({"provider": provider, "kind": kind, "argv": [], "returncode": 0, "status": "authoritative"})
                continue
            if authority == "ci" and mode == "team" and not fresh:
                diagnostics.append(_diagnostic(provider, "stale", "SOURCE_REVISION_MISMATCH", f"{kind} CI snapshot was not injected", "git pull --ff-only"))
            if authority != "damaged":
                if fresh:
                    commands.append({"provider": provider, "kind": kind, "argv": [], "returncode": 0, "status": "existing"})
                    continue
                diagnostics.append(_diagnostic(provider, "stale", "SOURCE_REVISION_MISMATCH", f"{kind} snapshot is stale", "rebuild map for current revision"))
            diagnostics.append(_diagnostic(provider, "damaged", "DAMAGED", f"{kind} unavailable", "rebuild map in CI"))
        target = project / (LOCAL_ARTIFACTS[kind] if mode == "team" else PROJECT_ARTIFACTS[kind])
        if target.is_file():
            try:
                local_payload = _load_artifact(target)
                local_fresh = _provider_meta(local_payload, target, kind, current_revision)["fresh"]
            except (OSError, ValueError):
                local_fresh = False
            if local_fresh:
                commands.append({"provider": provider, "kind": kind, "argv": [], "returncode": 0, "status": "existing_local"})
                continue
            diagnostics.append(_diagnostic(provider, "stale", "SOURCE_REVISION_MISMATCH", f"{kind} local snapshot is stale", "rebuild local map"))
        executable = "iwe" if kind == "document_map" else "codebase-memory-mcp"
        path = shutil.which(executable)
        if not path:
            unavailable.append(provider)
            diagnostics.append(_diagnostic(provider, "unavailable", "PROVIDER_NOT_FOUND", f"{kind} unavailable", f"install {provider}"))
            continue
        if kind == "document_map":
            argv = [path, "init", "--auto"] if not (project / ".iwe" / "config.toml").is_file() else []
        else:
            argv = [
                path, "cli", "--json", "index_repository", "--repo-path", str(project),
                "--persistence", "true" if persistence else "false",
            ]
        try:
            result = subprocess.run(argv, cwd=project, capture_output=True, text=True,
                                    check=False, timeout=timeout_seconds) if argv else None
        except subprocess.TimeoutExpired:
            unavailable.append(f"{provider}:BUILD_TIMEOUT")
            diagnostics.append(_diagnostic(provider, "query_failed", "BUILD_TIMEOUT", f"{kind} build timed out", "check provider index status"))
            continue
        build_returncode = result.returncode if result is not None else 0
        commands.append({
            "provider": provider, "kind": kind, "argv": argv, "returncode": build_returncode,
            "status": "built" if build_returncode in ({0, 2} if kind == "document_map" else {0}) else "failed",
        })
        if build_returncode not in ({0, 2} if kind == "document_map" else {0}):
            unavailable.append(f"{provider}:BUILD_FAILED")
            diagnostics.append(_diagnostic(provider, "query_failed", "BUILD_FAILED", f"{kind} unavailable", "check provider index status"))
            continue
        query_argv = (
            [path, "find", "--format", "json", "--limit", str(max_items),
             "--max-tokens", str(max_tokens), "--max-document-tokens", str(max(1, max_tokens // max_items))]
            if kind == "document_map" else
            [path, "cli", "--json", "query_graph", json.dumps({
                "query": f"MATCH (n) RETURN n LIMIT {max_items}", "limit": max_items,
            })]
        )
        try:
            query, native_output = _run_bounded_json(
                query_argv, project, timeout_seconds, max_output_bytes
            )
        except subprocess.TimeoutExpired:
            unavailable.append(f"{provider}:QUERY_TIMEOUT")
            diagnostics.append(_diagnostic(provider, "query_failed", "QUERY_TIMEOUT", f"{kind} query timed out", "reduce query scope or inspect provider"))
            continue
        except ValueError as exc:
            unavailable.append(f"{provider}:QUERY_FAILED")
            diagnostics.append(_diagnostic(
                provider, "query_failed", "QUERY_FAILED",
                f"{kind} unavailable: {exc}", "reduce query scope or inspect provider output",
            ))
            continue
        try:
            items = _normalize_native_rows(_as_rows(native_output), kind)[:max_items]
            payload = {
                "schema": MAP_SCHEMA, "kind": kind, "provider": provider,
                "authority": "local", "project_root": ".", "revision": current_revision,
                "queried_at": _utc_now(), "items": items,
                "adapter": {"version": "1.0", "argv": query_argv[1:]},
            }
            _atomic_json(target, payload)
        except ValueError as exc:
            unavailable.append(f"{provider}:QUERY_FAILED")
            diagnostics.append(_diagnostic(provider, "query_failed", "QUERY_FAILED", f"{kind} unavailable: {exc}", "check provider query output"))
    return {
        "project_root": str(project),
        "persistence": persistence,
        "mode": mode,
        "commands": commands,
        "unavailable": unavailable,
        "diagnostics": diagnostics,
        "artifacts": [str(path) for path in discover_project_maps(project, current_revision)],
    }


def build_context(
    project_dir: Path | str,
    provider_inputs: Iterable[Path | str] = (),
    agent_providers: Iterable[str] = (),
    max_items: int | None = None,
    include_recommendations: bool = True,
) -> dict:
    """Merge optional map artifacts; failures become Unknown and preserve L0."""
    project = Path(project_dir).expanduser().resolve()
    current_revision = _git_revision(project)
    capabilities = detect_capabilities(agent_providers)
    providers: list[dict] = []
    documents: list[dict] = []
    code_items: list[dict] = []
    relations: list[dict] = []
    unknown: list[str] = []

    paths = [Path(raw) for raw in provider_inputs]
    if not paths:
        paths = discover_project_maps(project, current_revision)
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        path = path.resolve() if path.is_absolute() else (project / path).resolve()
        try:
            try:
                path.relative_to(project)
            except ValueError as exc:
                raise ValueError("provider artifact escapes project directory") from exc
            payload = _load_artifact(path)
            kind = str(payload.get("kind") or (payload.get("provider") or {}).get("kind", "")).lower()
            if kind not in PROVIDER_DEFAULTS:
                raise ValueError("kind must be document_map or code_map")
            meta = _provider_meta(payload, path, kind, current_revision)
            providers.append(meta)
            if not meta["fresh"]:
                unknown.append(f"STALE_PROVIDER_DATA: {meta['name']} revision does not match current Git revision")
                continue
            items = payload.get("items", payload.get("results", []))
            if not isinstance(items, list):
                raise ValueError("items/results must be a list")
            for raw_item in items:
                if not isinstance(raw_item, dict) or not raw_item.get("id"):
                    unknown.append(f"INCOMPATIBLE_PROVIDER_DATA: {meta['name']} item lacks stable id")
                    continue
                item = _normalize_item(raw_item, meta)
                if kind == "document_map":
                    status = str(item.get("status", "ACTIVE")).upper()
                    if status in EXCLUDED_DOCUMENT_STATUSES:
                        continue
                    if status == "CONFLICTED":
                        unknown.append(f"CONFLICTED_DOCUMENT: {item['id']}")
                        continue
                    if status not in TRUSTED_DOCUMENT_STATUSES:
                        item["classification"] = "CANDIDATE"
                    documents.append(item)
                else:
                    code_items.append(item)
                for relation in item.get("relations", []):
                    if isinstance(relation, dict):
                        relations.append({**relation, "source": item["id"], "provider": meta["name"], "classification": "CANDIDATE"})
        except (OSError, ValueError) as exc:
            providers.append({
                "kind": "unknown", "name": path.name, "access_mode": "artifact_available",
                "status": "incompatible", "artifact": str(path), "fresh": False,
            })
            unknown.append(f"INCOMPATIBLE_PROVIDER_DATA: {path}: {exc}")

    code_by_id = {item["id"]: item for item in code_items}
    trace_links: list[dict] = []
    for document in documents:
        for symbol_id in document.get("implemented_by", []):
            code = code_by_id.get(symbol_id)
            if not code:
                relations.append({
                    "source": document["id"], "relation": "implemented_by", "target": symbol_id,
                    "provider": document["provider"], "classification": "CANDIDATE",
                })
                continue
            trace_links.append({
                "requirement_id": document["id"],
                "symbol_id": symbol_id,
                "tests": list(code.get("tested_by", [])),
                "classification": "CANDIDATE",
                "providers": [document["provider"], code["provider"]],
                "source_revision": code.get("source_revision"),
                "evidence": document["evidence"] + code["evidence"],
            })

    has_document = bool(documents)
    has_code = bool(code_items)
    level = "L3" if has_document and has_code else "L2" if has_document else "L1" if has_code else "L0"
    recommendations = []
    recovery_actions = []
    if include_recommendations and not has_document:
        recommendations.append("Optional: install/configure IWE for requirement and decision context; no tool was installed or contacted automatically.")
    if include_recommendations and not has_code:
        recommendations.append("Optional: install/configure codebase-memory-mcp for deeper code-graph analysis; no tool was installed or contacted automatically.")
    for item in unknown:
        if item.startswith("STALE_PROVIDER_DATA"):
            recovery_actions.append({"reason": "SOURCE_REVISION_MISMATCH", "command": "git pull --ff-only", "automatic": False})
        elif item.startswith("INCOMPATIBLE_PROVIDER_DATA"):
            recovery_actions.append({"reason": "SCHEMA_INCOMPATIBLE_OR_DAMAGED", "command": "python scripts/recon.py --project-dir . --map-mode team", "automatic": False})
        elif item.startswith("CONFLICTED_DOCUMENT"):
            recovery_actions.append({"reason": "CONFLICTED", "command": "resolve the source document conflict and rerun Recon", "automatic": False})
    if max_items is not None:
        if max_items < 0:
            raise ValueError("max_items must be zero or greater")
        documents = documents[:max_items]
        code_items = code_items[:max_items]
        relations = relations[:max_items]
        trace_links = trace_links[:max_items]
    return {
        "level": level,
        "capabilities": capabilities,
        "providers": providers,
        "documents": documents,
        "code": code_items,
        "relations": relations,
        "trace_links": trace_links,
        "unknown": unknown,
        "recommendations": recommendations,
        "recovery_actions": recovery_actions,
        "slice": {"max_items_per_section": max_items, "truncated": max_items is not None},
        "authority": "Map output is context, not execution evidence or Change Envelope authorization",
    }
