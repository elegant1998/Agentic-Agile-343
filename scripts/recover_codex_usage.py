#!/usr/bin/env python3
"""Recover a task-bound Codex usage snapshot from a signed historical time window."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from token_usage import project_identity
from usage_providers import CodexRolloutUsageProvider, canonical_task_id


def recover(project_dir: Path | str, task_id: str, start: str, end: str,
            output: Path | str | None = None, codex_home: Path | str | None = None,
            thread_id: str | None = None) -> dict:
    project = Path(project_dir).resolve()
    task_id = canonical_task_id(task_id)
    provider = CodexRolloutUsageProvider(codex_home, thread_id)
    result = provider.task_delta_between(project_identity(project), task_id, start, end)
    if result.get("status") != "MEASURED":
        return result
    destination = Path(output) if output else (
        project / "governance/telemetry/usage-snapshots" / f"{task_id}.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return {**result, "snapshot_path": str(destination)}


def main() -> int:
    parser = argparse.ArgumentParser(description="恢复 Codex 历史任务 Token 差值")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--start", required=True, help="ISO-8601 task baseline time")
    parser.add_argument("--end", required=True, help="ISO-8601 formal verification time")
    parser.add_argument("--output")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME"))
    parser.add_argument("--thread-id", default=os.environ.get("CODEX_THREAD_ID"))
    args = parser.parse_args()
    result = recover(args.project_dir, args.task, args.start, args.end, args.output,
                     args.codex_home, args.thread_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "MEASURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
