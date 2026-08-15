#!/usr/bin/env python3
"""Build and publish Agentic-Agile-343 from one validated staging tree."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from tool_bootstrap import prepare_ocusage


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
VERSION_FILES = ("SKILL.md", "README.md", "README.en.md", "RELEASE_NOTES.md", "RELEASE_NOTES.en.md")
DEFAULT_EXCLUDES = {
    ".git", ".github", ".DS_Store", "__pycache__", "governance", "tests",
    "dist", ".pytest_cache", ".mypy_cache", ".coverage", ".workbuddy",
    ".codebase-memory",
}


def current_version(source: Path) -> str:
    match = re.search(r'^\s*version:\s*"(\d+\.\d+\.\d+)"\s*$',
                      (source / "SKILL.md").read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError("SKILL.md metadata version was not found")
    return match.group(1)


def validate_versions(source: Path, expected: str) -> list[str]:
    errors = []
    for name in VERSION_FILES:
        path = source / name
        if not path.is_file() or expected not in path.read_text(encoding="utf-8"):
            errors.append(f"{name} does not contain version {expected}")
    if current_version(source) != expected:
        errors.append(f"SKILL.md metadata version is not {expected}")
    return errors


def set_version(source: Path | str, version: str) -> dict:
    source = Path(source).resolve()
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"invalid semantic version: {version}")
    old = current_version(source)
    if old == version:
        errors = validate_versions(source, version)
        if errors:
            raise ValueError("; ".join(errors))
        return {"version": version, "updated": []}
    replacements = {
        "SKILL.md": [(rf'(?m)^(\s*version:\s*"){re.escape(old)}("\s*)$', rf'\g<1>{version}\g<2>')],
        "README.md": [(rf'(?m)^(# .* v){re.escape(old)}$', rf'\g<1>{version}')],
        "README.en.md": [(rf'(?m)^(# .* v){re.escape(old)}$', rf'\g<1>{version}')],
        "RELEASE_NOTES.md": [
            (rf'(?m)^(# .* v){re.escape(old)}$', rf'\g<1>{version}'),
            (rf'(?m)^(- \*\*版本\*\*：`){re.escape(old)}(`)$', rf'\g<1>{version}\g<2>'),
        ],
        "RELEASE_NOTES.en.md": [
            (rf'(?m)^(# .* v){re.escape(old)}$', rf'\g<1>{version}'),
            (rf'(?m)^(- \*\*Version\*\*: `){re.escape(old)}(`)$', rf'\g<1>{version}\g<2>'),
        ],
    }
    rendered_files = {}
    for name, rules in replacements.items():
        path = source / name
        rendered = path.read_text(encoding="utf-8")
        substitutions = 0
        for pattern, replacement in rules:
            rendered, count = re.subn(pattern, replacement, rendered)
            substitutions += count
        if substitutions != len(rules):
            raise ValueError(f"{name} normative version fields are inconsistent with {old}")
        rendered_files[path] = rendered
    for path in (source / "tests" / "test_windows_core_migration.py",
                 source / "tests" / "test_scope_v_control_planes.py"):
        if path.is_file():
            rendered_files[path] = path.read_text(encoding="utf-8").replace(old, version)
    originals = {path: path.read_text(encoding="utf-8") for path in rendered_files}
    try:
        for path, rendered in rendered_files.items():
            path.write_text(rendered, encoding="utf-8")
        errors = validate_versions(source, version)
        if errors:
            raise ValueError("; ".join(errors))
    except Exception:
        for path, original in originals.items():
            path.write_text(original, encoding="utf-8")
        raise
    return {"version": version, "updated": [str(path.relative_to(source)) for path in rendered_files]}


def _ignored(_directory: str, names: list[str], excludes: set[str]) -> set[str]:
    return {name for name in names if name in excludes or name.endswith((".pyc", ".zip"))}


def _tracked_files(source: Path) -> list[Path] | None:
    """Use the repository manifest when source is a Git worktree root."""
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=source,
        capture_output=True, text=True, shell=False,
    )
    if root.returncode != 0 or Path(root.stdout.strip()).resolve() != source:
        return None
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=source,
        capture_output=True, shell=False,
    )
    if listed.returncode != 0:
        return None
    return [Path(raw.decode("utf-8")) for raw in listed.stdout.split(b"\0") if raw]


def _excluded_path(path: Path, excludes: set[str]) -> bool:
    return any(part in excludes for part in path.parts) or path.name.endswith((".pyc", ".zip"))


def build_staging(source: Path | str, staging: Path | str,
                  excludes: set[str] | None = None) -> Path:
    source, staging = Path(source).resolve(), Path(staging).resolve()
    excludes = set(DEFAULT_EXCLUDES if excludes is None else excludes)
    staging.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{staging.name}.", dir=staging.parent))
    shutil.rmtree(temporary)
    backup = staging.parent / f".{staging.name}.backup"
    try:
        tracked = _tracked_files(source)
        if tracked is None:
            shutil.copytree(source, temporary, ignore=lambda directory, names: _ignored(directory, names, excludes))
        else:
            temporary.mkdir()
            for relative in tracked:
                if _excluded_path(relative, excludes):
                    continue
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / relative, target)
        if backup.exists():
            shutil.rmtree(backup)
        if staging.exists():
            os.replace(staging, backup)
        os.replace(temporary, staging)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if not staging.exists() and backup.exists():
            os.replace(backup, staging)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return staging


def atomic_install(staging: Path | str, install_dir: Path | str) -> Path:
    staging, install_dir = Path(staging).resolve(), Path(install_dir).expanduser().resolve()
    install_dir.parent.mkdir(parents=True, exist_ok=True)
    incoming = Path(tempfile.mkdtemp(prefix=f".{install_dir.name}.incoming.", dir=install_dir.parent))
    shutil.rmtree(incoming)
    backup = install_dir.parent / f".{install_dir.name}.backup"
    try:
        shutil.copytree(staging, incoming)
        if backup.exists():
            shutil.rmtree(backup)
        if install_dir.exists():
            os.replace(install_dir, backup)
        os.replace(incoming, install_dir)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if not install_dir.exists() and backup.exists():
            os.replace(backup, install_dir)
        raise
    finally:
        if incoming.exists():
            shutil.rmtree(incoming)
    return install_dir


def build_zip(staging: Path | str, archive: Path | str) -> Path:
    staging, archive = Path(staging).resolve(), Path(archive).resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_name(f".{archive.name}.tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                bundle.write(path, Path(staging.name) / path.relative_to(staging))
    with zipfile.ZipFile(temporary) as bundle:
        damaged = bundle.testzip()
        if damaged:
            raise ValueError(f"ZIP integrity check failed at {damaged}")
    os.replace(temporary, archive)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("version", "stage", "publish"))
    parser.add_argument("--source", default=".")
    parser.add_argument("--version")
    parser.add_argument("--staging")
    parser.add_argument("--install-dir")
    parser.add_argument("--zip")
    args = parser.parse_args()
    source = Path(args.source).resolve()
    if args.version:
        set_version(source, args.version)
    version = current_version(source)
    errors = validate_versions(source, version)
    if errors:
        raise SystemExit("; ".join(errors))
    if args.command == "version":
        print(version)
        return 0
    if not args.staging:
        raise SystemExit("--staging is required")
    staging = build_staging(source, args.staging)
    if args.command == "stage":
        print(staging)
        return 0
    if not args.install_dir or not args.zip:
        raise SystemExit("publish requires --install-dir and --zip")
    installed = atomic_install(staging, args.install_dir)
    tool = prepare_ocusage()
    archive = build_zip(staging, args.zip)
    print(f"version={version}\nstaging={staging}\ninstalled={installed}\n"
          f"ocusage={tool['status']}\nzip={archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
