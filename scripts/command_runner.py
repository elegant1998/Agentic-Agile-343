#!/usr/bin/env python3
"""Safe, explicit and cross-platform command execution contract."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PLATFORMS = {"windows", "linux", "macos"}
SHELL_DIALECTS = {"powershell", "cmd", "posix"}


def current_platform():
    if os.name == "nt" or sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _result(status, *, argv=None, stdout="", stderr="", returncode=None, detail=""):
    return {"status": status, "argv": list(argv or []), "stdout": stdout or "",
            "stderr": stderr or "", "returncode": returncode, "detail": detail,
            "shell": False}


def _safe_cwd(project_dir, relative):
    root = Path(project_dir).resolve()
    candidate = (root / (relative or ".")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def run_command(spec, project_dir):
    if not isinstance(spec, dict) or not isinstance(spec.get("argv"), list) or not spec["argv"]:
        return _result("INVALID_COMMAND_SPEC", detail="command spec requires non-empty argv list")
    argv = spec["argv"]
    if not all(isinstance(x, (str, int, float)) and "\x00" not in str(x) for x in argv):
        return _result("INVALID_COMMAND_SPEC", detail="argv contains invalid value")
    platforms = spec.get("platforms")
    if platforms is not None:
        if not isinstance(platforms, list) or not platforms or any(x not in PLATFORMS for x in platforms):
            return _result("INVALID_COMMAND_SPEC", detail="invalid platforms")
        if current_platform() not in platforms:
            return _result("UNSUPPORTED_PLATFORM", detail=f"current platform is {current_platform()}")
    cwd = _safe_cwd(project_dir, spec.get("cwd", "."))
    if cwd is None:
        return _result("INVALID_COMMAND_SPEC", detail="cwd must remain inside project")
    command = [str(x) for x in argv]
    if command[0].lower() in {"python", "python3", "python.exe"}:
        command[0] = sys.executable
    elif not Path(command[0]).is_absolute():
        found = shutil.which(command[0])
        if not found:
            return _result("COMMAND_NOT_FOUND", argv=command, detail=f"not found: {command[0]}")
        command[0] = found
    try:
        completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", shell=False,
                                   timeout=float(spec.get("timeout_seconds", 300)))
    except subprocess.TimeoutExpired as exc:
        return _result("TIMEOUT", argv=command, stdout=exc.stdout or "", stderr=exc.stderr or "",
                       detail="command timed out")
    except (OSError, ValueError) as exc:
        return _result("COMMAND_NOT_FOUND" if isinstance(exc, FileNotFoundError) else "INVALID_COMMAND_SPEC",
                       argv=command, detail=str(exc))
    return _result("PASS" if completed.returncode == 0 else "FAIL", argv=command,
                   stdout=completed.stdout, stderr=completed.stderr,
                   returncode=completed.returncode)


def run_shell(spec, project_dir):
    if not isinstance(spec, dict) or spec.get("dialect") not in SHELL_DIALECTS or not isinstance(spec.get("script"), str):
        return _result("INVALID_COMMAND_SPEC", detail="shell requires dialect and script")
    dialect, script = spec["dialect"], spec["script"]
    if "\x00" in script:
        return _result("INVALID_COMMAND_SPEC", detail="script contains NUL")
    if dialect == "powershell":
        executable = shutil.which("pwsh") or shutil.which("powershell")
        argv = [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script] if executable else None
    elif dialect == "cmd":
        executable = shutil.which("cmd.exe") or shutil.which("cmd")
        argv = [executable, "/d", "/s", "/c", script] if executable else None
    else:
        executable = shutil.which("sh") or shutil.which("bash")
        argv = [executable, "-c", script] if executable else None
    if not argv:
        return _result("UNSUPPORTED_SHELL_DIALECT", detail=f"{dialect} shell is unavailable")
    command = {"argv": argv, "cwd": spec.get("cwd", "."),
               "timeout_seconds": spec.get("timeout_seconds", 300)}
    if "platforms" in spec:
        command["platforms"] = spec["platforms"]
    return run_command(command, project_dir)
