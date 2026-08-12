#!/usr/bin/env bash
# ensure_py_env.sh — skill 自包含依赖 bootstrap（Python 运行时）
#
# Python 原生 bootstrap 是唯一实现；本文件只保留 Unix 兼容入口。
#
# 退出码: 0 = 成功（stdout 含 python 路径）; 非 0 = 失败（stderr 含原因）
#
# 用法:
#   VENV_PY=$(bash ensure_py_env.sh) || { echo "venv 准备失败"; exit 1; }

set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/_bootstrap.py" --print-python
