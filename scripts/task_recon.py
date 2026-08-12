#!/usr/bin/env python3
"""Task-scoped, read-only Recon for existing codebases.

The implementation intentionally prefers explainable lightweight discovery over
pretending to build a complete call graph. JSON output is YAML 1.2 compatible.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import shutil
from pathlib import Path
from typing import Iterable

from context_providers import build_context


IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".iwe", ".codebase-memory"}
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".c": "C", ".h": "C/C++",
    ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++",
    ".java": "Java", ".jsp": "JSP", ".jspx": "JSP", ".go": "Go",
    ".rs": "Rust", ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
}
TEXT_SUFFIXES = set(LANGUAGES) | {".md", ".xml", ".yaml", ".yml", ".json", ".gradle"}
TEST_MARKERS = ("/tests/", "/test/", "/src/test/", "test_", "_test.", ".test.", ".spec.", "tests.")
PUBLIC_MARKERS = ("api", "route", "controller", "servlet", "handler", "public", "include/")
GENERIC_SYMBOLS = {"main", "run", "get", "set", "test", "init", "start", "stop", "build", "create"}


def _files(project: Path) -> list[Path]:
    return sorted(
        path for path in project.rglob("*")
        if path.is_file() and not any(part in IGNORED_PARTS for part in path.relative_to(project).parts)
    )


def _relative(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def _validate_targets(project: Path, targets: Iterable[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in targets:
        candidate = Path(raw).expanduser()
        candidate = candidate.resolve() if candidate.is_absolute() else (project / candidate).resolve()
        try:
            candidate.relative_to(project)
        except ValueError as exc:
            raise ValueError(f"target escapes project directory: {raw}") from exc
        if not candidate.exists():
            raise ValueError(f"target does not exist: {raw}")
        if not candidate.is_file():
            raise ValueError(f"target must be a file: {raw}")
        resolved.append(candidate)
    if not resolved:
        raise ValueError("at least one --target is required")
    return list(dict.fromkeys(resolved))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def _resolve_file(project: Path, base: Path, reference: str, extensions: tuple[str, ...] = ()) -> Path | None:
    raw = Path(reference)
    starts = [base / raw, project / raw]
    for start in starts:
        options = [start]
        options.extend(Path(str(start) + ext) for ext in extensions)
        options.extend(start / f"index{ext}" for ext in extensions)
        for option in options:
            try:
                resolved = option.resolve()
                resolved.relative_to(project)
            except (OSError, ValueError):
                continue
            if resolved.is_file():
                return resolved
    return None


def _python_deps(project: Path, target: Path, text: str) -> tuple[list[str], list[str]]:
    declarations, dependencies = [], []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return declarations, dependencies
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    for module in modules:
        declarations.append(module)
        dependency = _resolve_file(project, project, module.replace(".", "/"), (".py",))
        if dependency:
            dependencies.append(_relative(project, dependency))
    return declarations, dependencies


def _dependency_info(project: Path, target: Path, language: str, text: str) -> tuple[list[str], list[str], list[str]]:
    declarations: list[str] = []
    dependencies: list[str] = []
    unknown: list[str] = []
    if language == "Python":
        declarations, dependencies = _python_deps(project, target, text)
        if re.search(r"\b(importlib|__import__|getattr)\b", text):
            unknown.append(f"{_relative(project, target)}: dynamic Python import/reflection may hide dependencies")
    elif language in {"JavaScript", "TypeScript"}:
        refs = re.findall(r"(?:from\s+|require\s*\(\s*)['\"]([^'\"]+)['\"]", text)
        declarations.extend(refs)
        for ref in refs:
            if ref.startswith("."):
                dep = _resolve_file(project, target.parent, ref, (".js", ".jsx", ".ts", ".tsx"))
                if dep:
                    dependencies.append(_relative(project, dep))
        if re.search(r"\bimport\s*\(", text):
            unknown.append(f"{_relative(project, target)}: dynamic import may hide runtime dependencies")
    elif language in {"C", "C++", "C/C++"}:
        refs = re.findall(r'^\s*#\s*include\s*["<]([^">]+)[">]', text, re.MULTILINE)
        declarations.extend(refs)
        for ref in refs:
            dep = _resolve_file(project, target.parent, ref) or _resolve_file(project, project / "include", ref)
            if dep:
                dependencies.append(_relative(project, dep))
        if re.search(r"^\s*#\s*(if|ifdef|ifndef)\b", text, re.MULTILINE):
            unknown.append(f"{_relative(project, target)}: conditional compilation may change dependencies")
    elif language == "Java":
        refs = re.findall(r"^\s*import\s+([\w.]+)\s*;", text, re.MULTILINE)
        declarations.extend(refs)
        for ref in refs:
            suffix = ref.replace(".", "/") + ".java"
            matches = [path for path in _files(project) if path.as_posix().endswith(suffix)]
            if matches:
                dependencies.append(_relative(project, matches[0]))
        if re.search(r"Class\.forName|@(?:Autowired|Inject|ComponentScan)\b", text):
            unknown.append(f"{_relative(project, target)}: Java reflection/IoC may add runtime bindings")
    elif language == "JSP":
        includes = re.findall(r'<%@\s*include\s+file=["\']([^"\']+)', text)
        imports = re.findall(r'<%@\s*page[^%]*import=["\']([^"\']+)', text)
        taglibs = re.findall(r'<%@\s*taglib[^%]*uri=["\']([^"\']+)', text)
        declarations.extend(includes + imports + taglibs)
        for ref in includes:
            dep = _resolve_file(project, target.parent, ref)
            if dep:
                dependencies.append(_relative(project, dep))
        unknown.append(f"{_relative(project, target)}: JSP EL, container mappings and runtime bindings require runtime confirmation")
    elif language == "Go":
        refs = re.findall(r'^\s*import\s+(?:\w+\s+)?["`]([^"`]+)["`]', text, re.MULTILINE)
        if "import (" in text:
            refs.extend(re.findall(r'^\s*["`]([^"`]+)["`]', text, re.MULTILINE))
        declarations.extend(refs)
    elif language == "Rust":
        refs = re.findall(r"^\s*(?:pub\s+)?(?:mod|use)\s+([^;]+);", text, re.MULTILINE)
        declarations.extend(refs)
        for ref in refs:
            name = ref.split("::", 1)[0].strip()
            dep = _resolve_file(project, target.parent, name, (".rs",))
            if dep:
                dependencies.append(_relative(project, dep))
    elif language == "Shell":
        refs = re.findall(r'^\s*(?:source|\.)\s+["\']?([^\s"\']+)', text, re.MULTILINE)
        declarations.extend(refs)
        for ref in refs:
            dep = _resolve_file(project, target.parent, ref)
            if dep:
                dependencies.append(_relative(project, dep))
    else:
        unknown.append(f"{_relative(project, target)}: unsupported language; dependency and call analysis not performed")
    return declarations, dependencies, unknown


def _symbols(target: Path, text: str, language: str) -> set[str]:
    result = {target.stem}
    patterns = [r"\bclass\s+(\w+)", r"\b(?:def|function|func|fn)\s+(\w+)"]
    if language in {"C", "C++", "C/C++", "Java"}:
        patterns.append(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")
    for pattern in patterns:
        result.update(re.findall(pattern, text))
    return {item for item in result if len(item) >= 3 and item.lower() not in GENERIC_SYMBOLS}


def _is_test(path: str) -> bool:
    lowered = "/" + path.lower()
    return any(marker in lowered for marker in TEST_MARKERS)


def _git_untracked(project: Path) -> list[str]:
    result = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=project, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    return [line[3:] for line in result.stdout.splitlines() if line.startswith("?? ")]


def _map_candidate_paths(project: Path, context: dict, search_tokens: set[str]) -> list[Path]:
    candidates = []
    lowered = {token.lower() for token in search_tokens}
    for item in context.get("code", []):
        searchable = " ".join(str(item.get(key, "")) for key in ("id", "name", "qualified_name", "title")).lower()
        if lowered and not any(token in searchable for token in lowered):
            continue
        values = [item.get("path"), item.get("file")]
        values.extend(item.get("tested_by", []) if isinstance(item.get("tested_by"), list) else [])
        for value in values:
            if not isinstance(value, str):
                continue
            path = (project / value).resolve()
            try:
                path.relative_to(project)
            except ValueError:
                continue
            if path.is_file() and path.suffix.lower() in LANGUAGES:
                candidates.append(path)
    return list(dict.fromkeys(candidates))


def _rg_candidate_paths(project: Path, search_tokens: set[str], limit: int = 500) -> list[Path]:
    executable = shutil.which("rg")
    if not executable or not search_tokens:
        return []
    argv = [executable, "-l", "-i", "--hidden"]
    for ignored in sorted(IGNORED_PARTS):
        argv.extend(["--glob", f"!{ignored}/**"])
    for suffix in sorted(LANGUAGES):
        argv.extend(["--glob", f"*{suffix}"])
    for token in sorted(search_tokens):
        argv.extend(["-e", re.escape(token)])
    argv.append(".")
    try:
        result = subprocess.run(argv, cwd=project, capture_output=True, text=True,
                                check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    paths = []
    for raw in result.stdout.splitlines()[:limit]:
        path = (project / raw).resolve()
        try:
            path.relative_to(project)
        except ValueError:
            continue
        if path.is_file():
            paths.append(path)
    return list(dict.fromkeys(paths))


def scan_task(
    project_dir: Path | str,
    task_id: str,
    targets: Iterable[str],
    provider_inputs: Iterable[Path | str] = (),
    agent_providers: Iterable[str] = (),
    context_max_items: int | None = None,
    context_recommendations: bool = True,
) -> dict:
    project = Path(project_dir).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"project directory does not exist: {project}")
    target_paths = _validate_targets(project, targets)
    target_set = set(target_paths)
    languages: dict[str, str] = {}
    declarations: list[dict] = []
    dependencies: set[str] = set()
    unknown: list[str] = []
    search_tokens: set[str] = set()
    for target in target_paths:
        relative = _relative(project, target)
        language = LANGUAGES.get(target.suffix.lower(), "Unsupported")
        languages[relative] = language
        text = _read(target)
        refs, deps, gaps = _dependency_info(project, target, language, text)
        declarations.extend({"path": relative, "language": language, "value": ref} for ref in refs)
        dependencies.update(deps)
        unknown.extend(gaps)
        search_tokens.update(_symbols(target, text, language))

    context = build_context(
        project, provider_inputs, agent_providers,
        context_max_items if context_max_items is not None else 100,
        context_recommendations,
    )
    candidate_files = _map_candidate_paths(project, context, search_tokens)
    if candidate_files:
        strategy = "map_first"
    else:
        candidate_files = _rg_candidate_paths(project, search_tokens)
        if candidate_files:
            strategy = "rg_fallback"
        else:
            candidate_files = _files(project)
            strategy = "builtin_scan_fallback"

    candidates: dict[tuple[str, str], dict] = {}
    for path in candidate_files:
        if path in target_set or path.suffix.lower() not in LANGUAGES:
            continue
        relative = _relative(project, path)
        content = _read(path)
        matched = sorted(token for token in search_tokens if re.search(rf"\b{re.escape(token)}\b", content, re.IGNORECASE))
        header_pair = any(path.stem == target.stem and path.suffix.lower() in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"} for target in target_paths)
        test_name_match = _is_test(relative) and any(target.stem.lower() in path.stem.lower() for target in target_paths)
        if not matched and not header_pair and not test_name_match:
            continue
        category = "test" if _is_test(relative) else "reference"
        reason = "test path/name and target symbol match" if category == "test" else "target symbol/name reference"
        if header_pair:
            reason = "C/C++ header/implementation basename pair"
        candidates[(relative, category)] = {"path": relative, "category": category, "reason": reason, "matched": matched}

    public_entries = sorted({
        item[0] for item in candidates
        if any(marker in item[0].lower() for marker in PUBLIC_MARKERS)
    } | {
        _relative(project, target) for target in target_paths if target.suffix.lower() in {".h", ".hpp", ".jsp", ".jspx"}
    })
    untracked = _git_untracked(project)
    target_rel = [_relative(project, path) for path in target_paths]
    if not unknown:
        unknown.append("Runtime dispatch and behavior remain unverified; static Recon is not execution evidence")
    return {
        "task": {"id": task_id, "project": str(project), "targets": target_rel},
        "facts": {
            "targets": target_rel,
            "languages": languages,
            "dependency_declarations": declarations,
            "dependencies": sorted(dependencies),
        },
        "candidates": sorted(candidates.values(), key=lambda item: (item["path"], item["category"])),
        "preserve": sorted(set(public_entries + untracked)),
        "unknown": unknown,
        "context": context,
        "discovery": {
            "strategy": strategy,
            "candidate_file_count": len(candidate_files),
            "search_token_count": len(search_tokens),
        },
        "suggested_change_envelope": {
            "status": "DRAFT_NOT_AUTHORIZED",
            "allowed": target_rel,
            "protected": sorted(set(untracked + public_entries)),
            "expansion_rule": "Update the signed contract before expanding the Change Envelope",
        },
    }


def render_task_recon(result: dict, output_format: str = "markdown") -> str:
    normalized = output_format.lower()
    if normalized in {"yaml", "yml", "json"}:
        return json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if normalized not in {"markdown", "md"}:
        raise ValueError(f"unsupported format: {output_format}")
    facts = result["facts"]
    context = result["context"]
    candidate_lines = "\n".join(f"- `{item['path']}` [{item['category']}]: {item['reason']}" for item in result["candidates"]) or "- None discovered"
    return f"""# Task Recon: {result['task']['id']}

## Facts

- Targets: {', '.join(facts['targets'])}
- Languages: {', '.join(f'{path}={lang}' for path, lang in facts['languages'].items())}
- Direct local dependencies: {', '.join(facts['dependencies']) or 'none discovered'}

## Candidates

{candidate_lines}

## Preserve

{chr(10).join(f'- {item}' for item in result['preserve']) or '- None discovered'}

## Unknown

{chr(10).join(f'- {item}' for item in result['unknown'])}

## Context Enhancement

- Level: {context['level']}
- Providers: {', '.join(item['name'] for item in context['providers']) or 'none'}
- Trace links: {len(context['trace_links'])}
{chr(10).join(f'- {item}' for item in context['unknown'] + context['recommendations'])}

## Suggested Change Envelope

- Status: DRAFT_NOT_AUTHORIZED
- Allowed: {', '.join(result['suggested_change_envelope']['allowed'])}
- Protected: {', '.join(result['suggested_change_envelope']['protected']) or 'none discovered'}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="任务级只读 Recon")
    parser.add_argument("--task", required=True)
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--context-provider", action="append", default=[], help="Explicit JSON/YAML Document Map or Code Map artifact")
    parser.add_argument("--agent-provider", action="append", default=[], help="Provider exposed by the Agent host; capability disclosure only")
    parser.add_argument("--context-max-items", type=int, help="Maximum items retained in each context section")
    parser.add_argument("--no-context-recommendations", action="store_true", help="Suppress optional provider suggestions")
    parser.add_argument("--format", choices=("markdown", "md", "yaml", "yml", "json"), default="markdown")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        rendered = render_task_recon(
            scan_task(
                args.project_dir, args.task, args.target, args.context_provider, args.agent_provider,
                args.context_max_items, not args.no_context_recommendations,
            ),
            args.format,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
