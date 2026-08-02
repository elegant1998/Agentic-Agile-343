#!/usr/bin/env bash
# fetch_token_usage.sh — 通过 @geeeger/ocusage 获取真实 Token 用量（替代人工估算）
#
# 用法:
#   ./fetch_token_usage.sh <project_name> [date] [client]
#
#   project_name  项目目录名（ocusage byProject 的 key），如 agentic-agile-portal
#   date          日期或别名: today / yesterday / week / month / YYYY-MM-DD（默认 today）
#   client        AI 客户端: workbuddy / claude / codex / opencode ...（默认 workbuddy）
#
# 输出（stdout，单行 JSON）:
#   {"source":"measured:ocusage","total":123,"input":100,"output":23,"requests":5,"tool_calls":50}
#   取不到数据时: {"source":"unavailable","total":0,...}（exit 0，由调用方决定回退策略）
#
# 依赖: node >= 22.5（ocusage 用 node:sqlite）。查找/自安装顺序:
#   1. 项目 node_modules/@geeeger/ocusage
#   2. 全局 ocusage 命令
#   3. npx --yes @geeeger/ocusage（需网络，首次临时下载）
#   4. npm install -g @geeeger/ocusage 后重试（自包含依赖 bootstrap）

set -uo pipefail

PROJECT_NAME="${1:?用法: $0 <project_name> [date] [client]}"
DATE_ARG="${2:-today}"
CLIENT="${3:-workbuddy}"

fail_json() {
  echo '{"source":"unavailable","total":0,"input":0,"output":0,"requests":0,"tool_calls":0}'
  exit 0
}

# --- 找 node (>=22.5) ---
NODE_BIN=""
for cand in \
  "$HOME/.workbuddy/binaries/node/versions/"*/bin/node \
  "$(command -v node 2>/dev/null || true)"; do
  [ -x "$cand" ] || continue
  MAJOR=$("$cand" -e 'console.log(process.versions.node.split(".")[0])' 2>/dev/null || echo 0)
  MINOR=$("$cand" -e 'console.log(process.versions.node.split(".")[1])' 2>/dev/null || echo 0)
  if [ "$MAJOR" -gt 22 ] || { [ "$MAJOR" -eq 22 ] && [ "$MINOR" -ge 5 ]; }; then
    NODE_BIN="$cand"; break
  fi
done
[ -z "$NODE_BIN" ] && fail_json

# --- 找 ocusage ---
run_ocusage() {
  local cli
  # 1) 当前目录向上找项目本地安装
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    cli="$dir/node_modules/@geeeger/ocusage/cli.mjs"
    if [ -f "$cli" ]; then "$NODE_BIN" "$cli" "$@" 2>/dev/null; return $?; fi
    dir="$(dirname "$dir")"
  done
  # 2) 全局命令
  if command -v ocusage >/dev/null 2>&1; then ocusage "$@" 2>/dev/null; return $?; fi
  # 3) npx 兜底（需网络，首次会临时下载）
  if npx --yes @geeeger/ocusage "$@" 2>/dev/null; then return 0; fi
  # 4) 自包含依赖 bootstrap：全局安装后重试
  echo "⚠️ ocusage 未找到，尝试全局安装 @geeeger/ocusage ..." >&2
  if npm install -g @geeeger/ocusage >/dev/null 2>&1; then
    if command -v ocusage >/dev/null 2>&1; then
      ocusage "$@" 2>/dev/null; return $?
    fi
    npx --yes @geeeger/ocusage "$@" 2>/dev/null; return $?
  fi
  return 1
}

RAW=$(run_ocusage -c "$CLIENT" -j -d "$DATE_ARG") || fail_json
[ -z "$RAW" ] && fail_json

# --- 解析 byProject[PROJECT_NAME]，无则回退 total ---
echo "$RAW" | "$NODE_BIN" -e '
const chunks = [];
process.stdin.on("data", c => chunks.push(c));
process.stdin.on("end", () => {
  try {
    const data = JSON.parse(chunks.join(""));
    const client = data[Object.keys(data)[0]] || {};
    const proj = (client.byProject || {})[process.argv[1]];
    const s = proj || client.total || {};
    const out = {
      source: proj ? "measured:ocusage:project" : (client.total ? "measured:ocusage:client-total" : "unavailable"),
      total: s.totalTokens || 0,
      input: s.inputTokens || 0,
      output: s.outputTokens || 0,
      requests: s.requests || 0,
      tool_calls: s.toolCalls || 0
    };
    console.log(JSON.stringify(out));
  } catch (e) {
    console.log(JSON.stringify({source:"unavailable",total:0,input:0,output:0,requests:0,tool_calls:0}));
  }
});
' "$PROJECT_NAME" || fail_json
