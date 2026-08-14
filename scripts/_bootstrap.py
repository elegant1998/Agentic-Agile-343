"""Python-native self-contained dependency bootstrap for every platform."""
import os
import subprocess
import sys
from pathlib import Path


def _platform_name():
    return "windows" if os.name == "nt" or sys.platform.startswith("win") else "unix"


def venv_python(root, platform=None):
    platform = platform or _platform_name()
    root = Path(root)
    return root / "Scripts" / "python.exe" if platform == "windows" else root / "bin" / "python"


def can_import_yaml(python: str | Path) -> bool:
    """Return whether an interpreter already has the persistent YAML dependency."""
    try:
        completed = subprocess.run(
            [str(python), "-c", "import yaml"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def can_import_coverage(python: str | Path) -> bool:
    """Return whether an interpreter already has the coverage dependency."""
    try:
        completed = subprocess.run(
            [str(python), "-c", "import coverage"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def prepare_yaml_environment() -> Path:
    """Return a persistent interpreter with PyYAML, installing only when absent."""
    venv_root = Path.home() / ".agentic-agile-343" / "venv"
    target = venv_python(venv_root)
    if not target.is_file():
        venv_root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv_root)], check=True,
                       capture_output=True, text=True, timeout=300, shell=False)
    if not can_import_yaml(target):
        subprocess.run([str(target), "-m", "pip", "install", "--disable-pip-version-check",
                        "pyyaml>=6.0"], check=True, capture_output=True, text=True,
                       timeout=300, shell=False)
    if not can_import_coverage(target):
        subprocess.run([str(target), "-m", "pip", "install", "--disable-pip-version-check",
                        "coverage>=7.0"], check=True, capture_output=True, text=True,
                       timeout=300, shell=False)
    return target


def ensure_yaml_available():
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass
    try:
        target = prepare_yaml_environment()
        os.execv(str(target), [str(target), *sys.argv])
    except Exception as exc:
        sys.stderr.write("错误: 无法自动安装 pyyaml。请运行 python -m pip install pyyaml。\n")
        sys.stderr.write(f"  {exc}\n")
        raise SystemExit(1)


if __name__ == "__main__" and sys.argv[1:] == ["--print-python"]:
    try:
        print(prepare_yaml_environment())
    except Exception as exc:
        sys.stderr.write(f"错误: 无法准备持久 Python 环境: {exc}\n")
        raise SystemExit(1)
