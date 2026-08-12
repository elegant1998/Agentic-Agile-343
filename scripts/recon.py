#!/usr/bin/env python3
"""既有项目轻量 Recon：只读采集事实并生成治理起点。"""

import argparse
import json
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

from context_providers import build_context, build_project_maps

IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
LANGUAGE_SUFFIXES = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".go": "Go", ".rs": "Rust", ".cpp": "C++", ".c": "C"}


def _git(project: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout.strip()


def _files(project: Path) -> list[Path]:
    return sorted(path for path in project.rglob("*") if path.is_file() and not any(part in IGNORED_PARTS for part in path.parts))


def scan_project(
    project_dir: Path | str, provider_inputs=(), agent_providers=(), context_max_items=None,
    context_recommendations=True, auto_context=True, persistence=True,
) -> dict:
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
    map_build = None
    if auto_context and not provider_inputs:
        map_build = build_project_maps(project, persistence=persistence)
    context = build_context(project, provider_inputs, agent_providers, context_max_items, context_recommendations)
    context["map_build"] = map_build
    context["project_root"] = str(project)
    context["source_revision"] = _git(project, "rev-parse", "HEAD")[1] or None
    return {
        "recon": {"version": "1.0", "date": date.today().isoformat(), "mode": "lightweight-existing"},
        "project": {"name": project.name, "path": str(project), "existing": existing},
        "git": {"available": git_rc == 0, "branch": branch, "untracked": untracked},
        "inventory": {"file_count": len(files), "languages": dict(sorted(languages.items())), "test_files": test_files, "governance_files": governance},
        "baseline": baseline,
        "preserve": preserve,
        "unknown": unknown or ["No blocking unknowns detected; IO review is still required"],
        "context": context,
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
    context = result["context"]
    return f"""# Recon Baseline: {project['name']}

**Mode**: lightweight-existing
**Project**: `{project['path']}`

## Baseline

{_bullets(result['baseline'])}

## Preserve

{_bullets(result['preserve'])}

## Unknown

{_bullets(result['unknown'])}

## Context Enhancement

- Level: {context['level']}
- Providers: {', '.join(item['name'] for item in context['providers']) or 'none'}
- Trace links: {len(context['trace_links'])}
{_bullets(context['unknown'] + context['recommendations'])}

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
    parser.add_argument("--context-provider", action="append", default=[], help="Explicit JSON/YAML Document Map or Code Map artifact")
    parser.add_argument("--agent-provider", action="append", default=[], help="Provider exposed by the Agent host; capability disclosure only")
    parser.add_argument("--context-max-items", type=int, help="Maximum items retained in each context section")
    parser.add_argument("--no-context-recommendations", action="store_true", help="Suppress optional provider suggestions")
    parser.add_argument("--no-auto-context", action="store_true", help="Do not initialize project maps when providers are available")
    parser.add_argument("--persistence", choices=["true", "false"], default="true", help="Persist provider indexes at project scope")
    parser.add_argument("--output", help="显式指定时才写文件；否则输出到 stdout")
    args = parser.parse_args()
    rendered = render_recon(scan_project(
        args.project_dir, args.context_provider, args.agent_provider,
        args.context_max_items, not args.no_context_recommendations,
        not args.no_auto_context, args.persistence == "true",
    ), args.format)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
