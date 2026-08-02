#!/usr/bin/env bash
# ensure_py_env.sh — skill 自包含依赖 bootstrap（Python 运行时）
#
# 功能:
#   1. 动态查找可用 python3（managed 优先: ~/.workbuddy/binaries/python/versions/*/bin/python3，
#      回退系统 python3；不硬编码任何个人路径，保证跨机器可移植）
#   2. 创建持久 venv: ~/.agentic-agile-343/venv
#   3. 安装 pyyaml（若缺失）
#   4. 将 venv 的 python3 绝对路径输出到 stdout，供调用方使用
#
# 退出码: 0 = 成功（stdout 含 python 路径）; 非 0 = 失败（stderr 含原因）
#
# 用法:
#   VENV_PY=$(bash ensure_py_env.sh) || { echo "venv 准备失败"; exit 1; }

set -uo pipefail

VENV="$HOME/.agentic-agile-343/venv"
VENV_PY="$VENV/bin/python3"

# 已就绪则直接返回（幂等，避免重复建 venv）
if [ -x "$VENV_PY" ] && "$VENV_PY" -c "import yaml" 2>/dev/null; then
  echo "$VENV_PY"
  exit 0
fi

# --- 动态查找 python3（managed 优先，避免硬编码个人路径）---
PY=""
for cand in \
  "$HOME/.workbuddy/binaries/python/versions/"*/bin/python3 \
  "$(command -v python3 2>/dev/null || true)" \
  "$(command -v python 2>/dev/null || true)"; do
  [ -x "$cand" ] || continue
  PY="$cand"; break
done
if [ -z "$PY" ]; then
  echo "错误: 找不到 python3，无法创建 skill venv" >&2
  exit 1
fi

# --- 创建 venv（--clear 保证干净；失败回退不带 --clear）---
if ! "$PY" -m venv "$VENV" --clear 2>/dev/null; then
  rm -rf "$VENV" 2>/dev/null || true
  "$PY" -m venv "$VENV" 2>/dev/null || {
    echo "错误: 创建 venv 失败 ($VENV)" >&2
    exit 2
  }
fi

# --- 安装 pyyaml ---
"$VENV/bin/pip" install --quiet --upgrade pip 2>/dev/null || true
if ! "$VENV_PY" -c "import yaml" 2>/dev/null; then
  "$VENV/bin/pip" install --quiet "pyyaml>=6.0" 2>/dev/null || {
    echo "错误: 安装 pyyaml 失败（可能离线，请手动: $VENV/bin/pip install pyyaml）" >&2
    exit 3
  }
fi

# --- 最终校验 ---
if "$VENV_PY" -c "import yaml" 2>/dev/null; then
  echo "$VENV_PY"
  exit 0
else
  echo "错误: venv 就绪但 pyyaml 仍不可用" >&2
  exit 4
fi
