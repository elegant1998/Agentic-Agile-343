"""One-command project snapshot for shared inventory, revision, and source digest."""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXCLUDES = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".next", "out", "coverage", ".turbo", ".iwe", ".codebase-memory",
})


@dataclass(frozen=True)
class ProjectSnapshot:
    project: Path
    revision: str
    files: tuple[Path, ...]

    @classmethod
    def capture(cls, project_dir: Path | str, excludes=DEFAULT_EXCLUDES) -> "ProjectSnapshot":
        project = Path(project_dir).resolve()
        files = tuple(sorted(
            path for path in project.rglob("*")
            if path.is_file() and not any(part in excludes for part in path.relative_to(project).parts)
        ))
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True,
            text=True, check=False, timeout=10,
        )
        revision = result.stdout.strip() if result.returncode == 0 else "UNKNOWN"
        return cls(project=project, revision=revision, files=files)

    def source_digest(self, roots=("tests", "scripts", "src")) -> str:
        allowed = tuple((self.project / root).resolve() for root in roots)
        digest = hashlib.sha256()
        for path in self.files:
            resolved = path.resolve()
            if not any(resolved == root or root in resolved.parents for root in allowed):
                continue
            digest.update(path.relative_to(self.project).as_posix().encode())
            digest.update(path.read_bytes())
        return "sha256:" + digest.hexdigest()
