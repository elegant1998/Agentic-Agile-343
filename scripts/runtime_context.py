"""Shared runtime plans and trusted verification context helpers."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


def resolve_test_plan(project_dir: Path | str, timeout: int = 300) -> dict:
    project = Path(project_dir).resolve()
    package = project / "package.json"
    if package.is_file():
        try:
            script = (json.loads(package.read_text(encoding="utf-8")).get("scripts") or {}).get("test", "")
        except (OSError, json.JSONDecodeError):
            script = ""
        if script:
            if "vitest" in script:
                return {"runner": "vitest", "argv": ["npx", "vitest", "run", "--reporter=json"], "kind": "node", "cwd": ".", "timeout": timeout}
            if "jest" in script:
                return {"runner": "jest", "argv": ["npx", "jest", "--json"], "kind": "node", "cwd": ".", "timeout": timeout}
            return {"runner": "npm", "argv": ["npm", "test"], "kind": "node", "cwd": ".", "timeout": timeout}
    tests = project / "tests"
    if tests.is_dir() or list(project.glob("test_*.py")):
        argv = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
        if (tests / "__init__.py").is_file():
            argv.extend(["-t", "."])
        argv.append("-v")
        return {"runner": "unittest", "argv": argv, "kind": "python", "cwd": ".", "timeout": timeout}
    if (project / "pyproject.toml").is_file() or (project / "pytest.ini").is_file():
        return {"runner": "pytest", "argv": [sys.executable, "-m", "pytest", "--tb=no", "-q"], "kind": "python", "cwd": ".", "timeout": timeout}
    candidates = [
        (project / "go.mod", "go", ["go", "test", "-v", "./..."], "go"),
        (project / "Cargo.toml", "cargo", ["cargo", "test"], "rust"),
        (project / "pom.xml", "mvn", ["mvn", "test", "-q"], "java"),
    ]
    for marker, runner, argv, kind in candidates:
        if marker.is_file():
            return {"runner": runner, "argv": argv, "kind": kind, "cwd": ".", "timeout": timeout}
    if list(project.glob("*.csproj")) or list(project.glob("*.sln")):
        return {"runner": "dotnet", "argv": ["dotnet", "test"], "kind": "dotnet", "cwd": ".", "timeout": timeout}
    return {"runner": None, "argv": [], "kind": None, "cwd": ".", "timeout": timeout}


def parse_test_output(runner: str | None, output: str) -> dict:
    result = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
    if runner == "unittest":
        matches = list(re.finditer(r"Ran (\d+) tests?", output))
        match = matches[-1] if matches else None
        result["total"] = int(match.group(1)) if match else 0
        summary = None
        if match:
            trailing = output[match.end():]
            summaries = list(re.finditer(r"FAILED \(([^)]+)\)", trailing))
            summary = summaries[-1] if summaries else None
        if summary:
            failures = re.search(r"failures=(\d+)", summary.group(1))
            errors = re.search(r"errors=(\d+)", summary.group(1))
            result["failed"] = int(failures.group(1)) if failures else 0
            result["errors"] = int(errors.group(1)) if errors else 0
        result["passed"] = max(0, result["total"] - result["failed"] - result["errors"])
        return result
    if runner in {"pytest", "npm"}:
        result["passed"] = sum(int(value) for value in re.findall(r"(\d+) passed", output))
        result["failed"] = sum(int(value) for value in re.findall(r"(\d+) failed", output))
        result["errors"] = sum(int(value) for value in re.findall(r"(\d+) errors?", output))
        result["total"] = result["passed"] + result["failed"] + result["errors"]
        return result
    if runner in {"vitest", "jest"}:
        try:
            start, end = output.find("{"), output.rfind("}")
            payload = json.loads(output[start:end + 1]) if start >= 0 and end >= start else {}
        except json.JSONDecodeError:
            payload = {}
        result["total"] = int(payload.get("numTotalTests", 0) or 0)
        result["passed"] = int(payload.get("numPassedTests", 0) or 0)
        result["failed"] = int(payload.get("numFailedTests", 0) or 0)
        result["skipped"] = int(payload.get("numSkippedTests", 0) or 0)
        # T-146 fix: total 应为 passed + failed（不含 skipped），与后端校验逻辑一致
        result["total"] = result["passed"] + result["failed"]
        return result
    if runner == "go":
        result["passed"] = len(re.findall(r"^--- PASS:", output, re.MULTILINE))
        result["failed"] = len(re.findall(r"^--- FAIL:", output, re.MULTILINE))
        result["errors"] = 1 if re.search(r"FAIL\t.*\[build failed\]", output) else 0
        result["total"] = result["passed"] + result["failed"]
        return result
    if runner == "cargo":
        match = re.search(r"test result:.*?(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored", output)
        if match:
            result["passed"], result["failed"] = int(match.group(1)), int(match.group(2))
            # T-146 fix: total = passed + failed（不含 ignored），与后端校验及 vitest/jest 一致
            result["total"] = result["passed"] + result["failed"]
        return result
    if runner == "mvn":
        for match in re.finditer(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", output):
            result["total"] += int(match.group(1))
            result["failed"] += int(match.group(2))
            result["errors"] += int(match.group(3))
        result["passed"] = max(0, result["total"] - result["failed"] - result["errors"])
        return result
    if runner == "dotnet":
        match = re.search(r"(?:Passed|Failed)!\s+-\s+Failed:\s*(\d+),\s+Passed:\s*(\d+),\s+Skipped:\s*(\d+),\s+Total:\s*(\d+)", output)
        if match:
            result["failed"], result["passed"] = int(match.group(1)), int(match.group(2))
            # T-146 fix: total = passed + failed（不含 Skipped），与后端校验及 vitest/jest 一致
            result["total"] = result["passed"] + result["failed"]
        return result
    return result


def verification_context_checksum(context: dict) -> str:
    payload = {key: value for key, value in context.items() if key != "context_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def load_trusted_verification_context(path: Path | str, project_dir: Path | str) -> tuple[dict | None, str]:
    try:
        context = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "missing_or_invalid_context"
    if context.get("schema") != "verification-run-context/v1":
        return None, "schema_changed"
    if context.get("project_root") != str(Path(project_dir).resolve()):
        return None, "project_changed"
    if context.get("context_sha256") != verification_context_checksum(context):
        return None, "checksum_changed"
    # T-146 fix: 允许 skipped 测试（passed + failed + skipped = total）。
    # 旧逻辑 passed != total 会拒绝有 skipped 的 context（如 vitest describe.skipIf）。
    # 新逻辑：status == PASS 且 failed == 0 即可（skipped 不阻断）。
    if context.get("status") != "PASS" or not context.get("total"):
        return None, "tests_not_passing"
    failed = context.get("failed", 0)
    if failed and int(failed) > 0:
        return None, "tests_not_passing"
    return context, "trusted_context"
