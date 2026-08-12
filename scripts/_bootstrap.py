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


def ensure_yaml_available():
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass
    venv_root = Path.home() / ".agentic-agile-343" / "venv"
    target = venv_python(venv_root)
    try:
        if not target.is_file():
            venv_root.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "venv", str(venv_root)], check=True,
                           capture_output=True, text=True, timeout=300, shell=False)
        subprocess.run([str(target), "-m", "pip", "install", "--disable-pip-version-check",
                        "pyyaml>=6.0"], check=True, capture_output=True, text=True,
                       timeout=300, shell=False)
        os.execv(str(target), [str(target), *sys.argv])
    except Exception as exc:
        sys.stderr.write("错误: 无法自动安装 pyyaml。请运行 python -m pip install pyyaml。\n")
        sys.stderr.write(f"  {exc}\n")
        raise SystemExit(1)
