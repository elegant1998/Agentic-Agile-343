#!/usr/bin/env python3
"""Optional Document Map and Code Map adapters for progressive Recon."""

from __future__ import annotations

import json
import shutil
import subprocess
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_revision(project: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=False
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
    fresh = kind != "code_map" or not revision or not current_revision or revision in {current_revision, f"git:{current_revision}"}
    return {
        "kind": kind,
        "name": str(name),
        "access_mode": "artifact_available",
        "status": "available" if fresh else "stale",
        "queried_at": payload.get("queried_at", queried_at) or _utc_now(),
        "source_revision": revision,
        "artifact": str(path),
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


def discover_project_maps(project_dir: Path | str) -> list[Path]:
    """Find only the project's canonical, persisted map artifacts."""
    project = Path(project_dir).expanduser().resolve()
    return [project / relative for relative in PROJECT_ARTIFACTS.values() if (project / relative).is_file()]


def build_project_maps(project_dir: Path | str, persistence: bool = True) -> dict:
    """Run CLI-visible providers with explicit project and persistence boundaries."""
    project = Path(project_dir).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"project directory does not exist: {project}")
    commands: list[dict] = []
    unavailable: list[str] = []
    existing_artifacts = {path.name for path in discover_project_maps(project)}
    for kind, provider in PROVIDER_DEFAULTS.items():
        artifact_name = Path(PROJECT_ARTIFACTS[kind]).name
        if artifact_name in existing_artifacts:
            commands.append({"provider": provider, "kind": kind, "argv": [], "returncode": 0, "status": "existing"})
            continue
        executable = "iwe" if kind == "document_map" else "codebase-memory-mcp"
        path = shutil.which(executable)
        if not path:
            unavailable.append(provider)
            continue
        if kind == "document_map":
            if (project / ".iwe" / "config.toml").is_file():
                commands.append({"provider": provider, "kind": kind, "argv": [], "returncode": 0, "status": "existing"})
                continue
            argv = [path, "init", "--auto"]
        else:
            argv = [
                path, "cli", "--json", "index_repository", "--repo-path", str(project),
                "--persistence", "true" if persistence else "false",
            ]
        result = subprocess.run(argv, cwd=project, capture_output=True, text=True, check=False)
        commands.append({
            "provider": provider, "kind": kind, "argv": argv, "returncode": result.returncode,
            "status": "built" if result.returncode in ({0, 2} if kind == "document_map" else {0}) else "failed",
        })
        if result.returncode != 0:
            unavailable.append(f"{provider}:BUILD_FAILED")
    return {
        "project_root": str(project),
        "persistence": persistence,
        "commands": commands,
        "unavailable": unavailable,
        "artifacts": [str(path) for path in discover_project_maps(project)],
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
        paths = discover_project_maps(project)
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
    if include_recommendations and not has_document:
        recommendations.append("Optional: install/configure IWE for requirement and decision context; no tool was installed or contacted automatically.")
    if include_recommendations and not has_code:
        recommendations.append("Optional: install/configure codebase-memory-mcp for deeper code-graph analysis; no tool was installed or contacted automatically.")
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
        "slice": {"max_items_per_section": max_items, "truncated": max_items is not None},
        "authority": "Map output is context, not execution evidence or Change Envelope authorization",
    }
