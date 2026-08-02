"""skill 自包含依赖 bootstrap（Python 侧）

当脚本运行环境缺少 pyyaml 时，调用同目录的 ensure_py_env.sh 自动创建
持久 venv 并安装 pyyaml，然后用 venv 的 python 重新执行当前脚本
（os.execv，不会返回）。

调用方只需在 import yaml 失败时：

    try:
        import yaml
    except ImportError:
        from _bootstrap import ensure_yaml_available
        ensure_yaml_available()
        import yaml

注意：本模块本身不依赖任何第三方包，仅用标准库，确保 bootstrap 链路不中断。
"""
import os
import subprocess
import sys


def ensure_yaml_available() -> None:
    """确保当前进程能 import yaml；否则自动 bootstrap 后重启本脚本。

    成功时通过 os.execv 替换当前进程（不返回）；
    失败时向 stderr 输出指引并以退出码 1 终止。
    """
    # 已能 import 则直接返回，避免无谓的 re-exec（venv 已就绪的常态路径）
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    ensure_sh = os.path.join(here, "ensure_py_env.sh")
    if not os.path.exists(ensure_sh):
        sys.stderr.write(
            "错误: 找不到 ensure_py_env.sh（skill 安装不完整），无法自动修复依赖。\n"
        )
        sys.exit(1)

    try:
        r = subprocess.run(
            ["bash", ensure_sh],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"错误: 运行 ensure_py_env.sh 失败: {e}\n")
        sys.exit(1)

    venv_py = (r.stdout or "").strip()
    if venv_py and os.path.exists(venv_py):
        # 用 venv 的 python 重启当前脚本，保留原始 argv
        os.execv(venv_py, [venv_py, *sys.argv])

    # bootstrap 失败：输出原因 + 手动指引
    detail = (r.stderr or "").strip()
    sys.stderr.write(
        "错误: 无法自动安装 pyyaml，skill 的 YAML 相关功能不可用。\n"
        f"  {detail}\n"
        "手动修复（任选其一）:\n"
        f"  bash {ensure_sh}\n"
        "  pip install pyyaml\n"
    )
    sys.exit(1)
