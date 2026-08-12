#!/usr/bin/env python3
"""Cross-platform optional ocusage probe. Missing data stays unavailable."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from command_runner import run_command
from tool_bootstrap import prepare_ocusage


def project_identity(project: Path | str) -> dict:
    supplied = Path(project).expanduser().absolute()
    root = supplied.resolve()
    try:
        repo = subprocess.run(["git", "-C", str(root), "config", "--get", "remote.origin.url"],
                              capture_output=True, text=True, timeout=5, shell=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        repo = ""
    repo_name = re.split(r"[/:]", repo)[-1].removesuffix(".git") if repo else ""
    aliases = list(dict.fromkeys([root.name, str(supplied), str(root), repo_name]))
    aliases = [alias for alias in aliases if alias]
    return {"project_uid": hashlib.sha256(str(root).encode()).hexdigest()[:16],
            "project_root": str(root), "aliases": aliases}


def task_delta_measurement(baseline: dict | None, current: dict | None) -> dict:
    current = current or {}
    common = (baseline and current and
              baseline.get("token_client") == current.get("token_client") and
              baseline.get("project_uid") == current.get("project_uid") and
              baseline.get("date") == current.get("date") and
              baseline.get("value") is not None and current.get("value") is not None)
    if not common or int(current["value"]) < int(baseline["value"]):
        return {**current, "value": None, "status": "UNKNOWN", "scope": "task_delta",
                "detail": "missing_or_incompatible_token_baseline"}
    return {**current, "value": int(current["value"]) - int(baseline["value"]),
            "status": "MEASURED", "scope": "task_delta",
            "detail": "end_snapshot_minus_start_snapshot"}


def _find_metric(payload: dict, client: str, identity: dict) -> dict | None:
    client_data = payload.get(client, {}) if isinstance(payload, dict) else {}
    projects = client_data.get("byProject") or {}
    matches = [projects[name] for name in identity["aliases"] if isinstance(projects.get(name), dict)]
    return matches[0] if len(matches) == 1 else None


def collect_token_measurement(project: Path | str, *, host_tool: str | None = None,
                              token_clients: list[str] | None = None, date_name: str = "today",
                              baseline: dict | None = None) -> dict:
    identity = project_identity(project)
    host_tool = host_tool or os.environ.get("AGENTIC_AGILE_HOST_TOOL", "other")
    configured_client = os.environ.get("AGENTIC_AGILE_TOKEN_CLIENT")
    clients = token_clients or ([configured_client] if configured_client else ["codex", "claude"])
    tool = prepare_ocusage()
    base = {"value": None, "status": "UNAVAILABLE", "source": "unavailable",
            "evidence": [], "measured_at": None, "scope": "task_delta",
            "host_tool": host_tool, "token_client": None, **identity}
    if not tool.get("executable"):
        base["detail"] = tool.get("detail", "ocusage is unavailable")
        return base
    prefix = tool.get("argv_prefix") or [tool["executable"]]
    snapshots = []
    for client in dict.fromkeys(clients):
        result = run_command({"argv": [*prefix, "--json", "--date", date_name, "--client", client],
                              "timeout_seconds": 120}, Path(project))
        if result.get("status") != "PASS":
            continue
        try:
            payload = json.loads(result.get("stdout", ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        metric = _find_metric(payload, client, identity)
        if metric is None:
            continue
        snapshots.append({**base, "value": int(metric.get("totalTokens", 0)),
                          "status": "CUMULATIVE_SNAPSHOT", "source": f"measured:ocusage:{client}",
                          "measured_at": datetime.now(timezone.utc).isoformat(),
                          "scope": "project_daily_snapshot", "token_client": client,
                          "date": date.today().isoformat(), "input": int(metric.get("inputTokens", 0)),
                          "output": int(metric.get("outputTokens", 0))})
    if len(snapshots) == 1:
        return task_delta_measurement(baseline, snapshots[0]) if baseline else snapshots[0]
    if len(snapshots) > 1:
        base["detail"] = "multiple token clients matched; select AGENTIC_AGILE_TOKEN_CLIENT"
        return base
    base["detail"] = "ocusage returned no unambiguous project data"
    return base


def collect_token_usage(project, date="today", client="codex"):
    measurement = collect_token_measurement(project, token_clients=[client], date_name=date)
    if measurement.get("status") not in {"CUMULATIVE_SNAPSHOT", "MEASURED"}:
        return {"status": "UNAVAILABLE_OPTIONAL_TOOL", "source": "unavailable",
                "total": None, "input": None, "output": None, "detail": measurement.get("detail")}
    return {"status": "MEASURED", "source": measurement["source"], "total": measurement["value"],
            "input": measurement.get("input"), "output": measurement.get("output"),
            "measurement": measurement}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("date", nargs="?", default="today")
    parser.add_argument("client", nargs="?", default="codex")
    args = parser.parse_args()
    print(json.dumps(collect_token_usage(args.project, args.date, args.client), ensure_ascii=False))


if __name__ == "__main__":
    main()
