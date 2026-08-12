#!/usr/bin/env python3
"""One-time bootstrap for optional tools used by recurring governance workflows."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


OCUSAGE_PACKAGE = "@geeeger/ocusage"
DEFAULT_TOOLS_ROOT = Path.home() / ".agentic-agile-343" / "tools"


def ocusage_executable(tools_root: Path | str = DEFAULT_TOOLS_ROOT) -> Path:
    root = Path(tools_root).expanduser()
    suffix = ".cmd" if os.name == "nt" else ""
    return root / "ocusage" / "node_modules" / ".bin" / f"ocusage{suffix}"


def ocusage_cli(tools_root: Path | str = DEFAULT_TOOLS_ROOT) -> Path:
    return Path(tools_root).expanduser() / "ocusage" / "node_modules" / "@geeeger" / "ocusage" / "cli.mjs"


def _runtime_bin_is_usable(directory: Path) -> Path | None:
    node_names = ("node.exe", "node") if os.name == "nt" else ("node", "node.exe")
    npm_names = ("npm.cmd", "npm") if os.name == "nt" else ("npm", "npm.cmd")
    if not any((directory / name).is_file() for name in node_names):
        return None
    return next((directory / name for name in npm_names if (directory / name).is_file()), None)


def _version_key(path: Path) -> tuple:
    return tuple(int(part) if part.isdigit() else part.lower()
                 for part in re.split(r"([0-9]+)", path.as_posix()))


def _local_node_bins(home: Path) -> list[Path]:
    """Return bounded, common user-local Node runtime directories."""
    version_patterns = (
        ".*/binaries/node/versions/*/bin",
        ".cache/*/dependencies/node/bin",
        ".cache/*/*/dependencies/node/bin",
        ".nvm/versions/node/*/bin",
        ".local/share/fnm/node-versions/*/installation/bin",
        "Library/Application Support/fnm/node-versions/*/installation/bin",
    )
    bins: list[Path] = []
    for pattern in version_patterns:
        bins.extend(sorted(home.glob(pattern), key=_version_key, reverse=True))
    bins.extend((
        home / ".volta/bin",
        home / ".local/bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ))
    if os.name == "nt":
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "ProgramFiles"):
            base = os.environ.get(variable)
            if base:
                bins.append(Path(base) / "nodejs")
    return bins


def find_npm() -> str | None:
    configured = os.environ.get("AGENTIC_AGILE_NPM")
    if configured and Path(configured).is_file():
        return configured
    on_path = shutil.which("npm") or shutil.which("npm.cmd")
    if on_path:
        return on_path
    for directory in _local_node_bins(Path.home()):
        npm = _runtime_bin_is_usable(directory)
        if npm:
            return str(npm)
    return None


def prepare_ocusage(tools_root: Path | str = DEFAULT_TOOLS_ROOT) -> dict:
    """Return a private ocusage executable, installing it only when absent."""
    root = Path(tools_root).expanduser()
    prefix = root / "ocusage"
    executable = ocusage_executable(root)
    npm = find_npm()
    cli = ocusage_cli(root)
    node = str(Path(npm).expanduser().absolute().parent / ("node.exe" if os.name == "nt" else "node")) if npm else shutil.which("node")
    if cli.is_file() and node and Path(node).is_file():
        return {"status": "READY", "executable": str(executable), "argv_prefix": [node, str(cli)], "installed": False}
    if not npm:
        return {
            "status": "UNAVAILABLE",
            "executable": None,
            "installed": False,
            "detail": "npm is unavailable; install Node.js/npm or set AGENTIC_AGILE_NPM",
        }
    prefix.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    npm_dir = str(Path(npm).expanduser().absolute().parent)
    environment["PATH"] = npm_dir + os.pathsep + environment.get("PATH", "")
    completed = subprocess.run(
        [npm, "install", "--prefix", str(prefix), "--no-audit", "--no-fund", OCUSAGE_PACKAGE],
        capture_output=True,
        text=True,
        timeout=300,
        shell=False,
        env=environment,
    )
    if completed.returncode != 0 or not cli.is_file():
        return {
            "status": "UNAVAILABLE",
            "executable": None,
            "installed": False,
            "detail": (completed.stderr or "ocusage installation did not create its executable").strip(),
        }
    node = str(Path(npm).expanduser().absolute().parent / ("node.exe" if os.name == "nt" else "node"))
    return {"status": "INSTALLED", "executable": str(executable), "argv_prefix": [node, str(cli)], "installed": True}
