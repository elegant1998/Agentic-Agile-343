#!/usr/bin/env python3
"""既有项目轻量 Recon：只读采集事实并生成治理起点。"""

import argparse
import json
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
LANGUAGE_SUFFIXES = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".go": "Go", ".rs": "Rust", ".cpp": "C++", ".c": "C"}


def _git(project: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout.strip()


def _files(project: Path) -> list[Path]:
    return sorted(path for path in project.rglob("*") if path.is_file() and not any(part in IGNORED_PARTS for part in path.parts))


def scan_project(project_dir: Path | str) -> dict:
    """只读扫描既有项目，明确区分事实、保留项和未知项。"""
    project = Path(project_dir).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"project directory does not exist: {project}")
    files = _files(project)
    relative = [path.relative_to(project).as_posix() for path in files]
    languages = Counter(LANGUAGE_SUFFIXES[p.suffix] for p in files if p.suffix in LANGUAGE_SUFFIXES)
    git_rc, branch = _git(project, "branch", "--show-current")
    status_rc, status = _git(project, "status", "--porcelain", "--untracked-files=all")
    untracked = [line[3:] for line in status.splitlines() if line.startswith("?? ")] if status_rc == 0 else []
    test_files = [item for item in relative if item.startswith("tests/") or "/test_" in item or item.endswith(".test.ts")]
    governance = [item for item in relative if item.startswith("governance/")]
    existing = bool(files or git_rc == 0)
    baseline = [
        f"Existing project: {existing}",
        f"Files scanned: {len(files)}",
        "Languages: " + (", ".join(f"{k}={v}" for k, v in sorted(languages.items())) or "unknown"),
        f"Tests discovered: {len(test_files)}",
        f"Governance artifacts discovered: {len(governance)}",
    ]
    if git_rc == 0:
        baseline.append(f"Git branch: {branch or '(detached)'}")
    preserve = [
        "Preserve tracked files and public entry points until characterized",
        "Preserve untracked user files; Recon is read-only",
        "Preserve existing test and governance semantics",
    ]
    unknown = []
    if not test_files:
        unknown.append("Behavioral regression baseline is unknown because no tests were discovered")
    if not governance:
        unknown.append("Signed intent, executable constraints, and evidence history were not discovered")
    if git_rc != 0:
        unknown.append("Change history and tracked/untracked ownership are unknown because Git is unavailable")
    if not languages:
        unknown.append("Implementation language and executable entry points require human confirmation")
    return {
        "recon": {"version": "1.0", "date": date.today().isoformat(), "mode": "lightweight-existing"},
        "project": {"name": project.name, "path": str(project), "existing": existing},
        "git": {"available": git_rc == 0, "branch": branch, "untracked": untracked},
        "inventory": {"file_count": len(files), "languages": dict(sorted(languages.items())), "test_files": test_files, "governance_files": governance},
        "baseline": baseline,
        "preserve": preserve,
        "unknown": unknown or ["No blocking unknowns detected; IO review is still required"],
        "change_envelope": {
            "allowed": ["governance/", "tests/", "files explicitly named by a signed contract"],
            "protected": untracked + ["existing public entry points", "signed contracts", "MUST constraints"],
        },
    }


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_recon(result: dict, output_format: str = "markdown") -> str:
    """渲染 Markdown 或 YAML（JSON 是 YAML 1.2 的合法子集）。"""
    normalized = output_format.lower()
    if normalized in {"yaml", "yml"}:
        return json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if normalized not in {"markdown", "md"}:
        raise ValueError(f"unsupported format: {output_format}")
    project = result["project"]
    envelope = result["change_envelope"]
    return f"""# Recon Baseline: {project['name']}

**Mode**: lightweight-existing
**Project**: `{project['path']}`

## Baseline

{_bullets(result['baseline'])}

## Preserve

{_bullets(result['preserve'])}

## Unknown

{_bullets(result['unknown'])}

## Change Envelope

### Allowed

{_bullets(envelope['allowed'])}

### Protected

{_bullets(envelope['protected'])}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="既有项目轻量 Recon（默认只读）")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--format", choices=["markdown", "md", "yaml", "yml"], default="markdown")
    parser.add_argument("--output", help="显式指定时才写文件；否则输出到 stdout")
    args = parser.parse_args()
    rendered = render_recon(scan_project(args.project_dir), args.format)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
