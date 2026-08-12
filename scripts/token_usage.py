#!/usr/bin/env python3
"""Cross-platform optional ocusage probe. Missing data stays unavailable."""
import argparse
import json
import shutil
from pathlib import Path

from command_runner import run_command


def collect_token_usage(project, date="today", client="codex"):
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return {"status": "UNAVAILABLE_OPTIONAL_TOOL", "source": "unavailable",
                "total": None, "input": None, "output": None}
    spec = {"argv": [npx, "--yes", "@geeeger/ocusage", "--json", "--project", project,
                     "--date", date, "--client", client], "timeout_seconds": 120}
    result = run_command(spec, Path.cwd())
    if result["status"] != "PASS":
        return {"status": "UNAVAILABLE_OPTIONAL_TOOL", "source": "unavailable",
                "total": None, "input": None, "output": None, "detail": result.get("detail") or result.get("stderr")}
    try:
        payload = json.loads(result["stdout"])
        return {"status": "MEASURED", "source": f"measured:ocusage:{client}",
                "total": int(payload.get("total", 0)), "input": int(payload.get("input", 0)),
                "output": int(payload.get("output", 0))}
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"status": "UNAVAILABLE_OPTIONAL_TOOL", "source": "unavailable",
                "total": None, "input": None, "output": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("date", nargs="?", default="today")
    parser.add_argument("client", nargs="?", default="codex")
    args = parser.parse_args()
    print(json.dumps(collect_token_usage(args.project, args.date, args.client), ensure_ascii=False))


if __name__ == "__main__":
    main()
