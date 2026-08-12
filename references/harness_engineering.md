# Harness Engineering：可执行约束护栏

> 本文是 SKILL.md §6 的详细参考，按需加载。

## 核心原则

约束不应该是"检查清单文档"，而应该是**可自动执行的护栏（Harness）**——在违规发生的瞬间阻止，而不是事后检查。

> **统一 CLI（v1.15+）**：所有脚本可通过 `python scripts/cli.py <子命令>` 统一调用。运行 `python scripts/cli.py list` 查看全部 20 个子命令。

## 从声明式到可执行

```
优化前: Constraint_Matrix.md → 人工逐条 grep/test -f/diff
优化后: constraints.yaml → harness.py check --all（一条命令）
```

## Harness 引擎用法

```bash
# 全量门禁检查（门禁 G0-G8 直接从 constraints.yaml 的 gate: 标签聚合）
python scripts/harness.py check --all

# 按域检查
python scripts/harness.py check --domain QUAL

# 按门禁检查
python scripts/harness.py check --gate G4

# 仅 NFR 检查
python scripts/harness.py check --nfr-only

# JSON 输出（供 CI/CD 与 collect_telemetry.py 消费）
python scripts/harness.py check --all --format json

# 跨语言运行测试套件（Node/vitest/jest 或 Python/pytest），返回结构化 JSON
python scripts/harness.py tests

# 列出所有约束
python scripts/harness.py list

# 列出可用 NFR 验证器
python scripts/harness.py nfr-list
```

> **门禁直接源自约束矩阵（v1.14+）**：`harness check --all` 读取 `constraints.yaml` 中每条约束的 `gate:` 标签，按 MUST 约束聚合出 G0-G8 的通过/失败——判定逻辑 `gate_passed = (must_passed == must_total)`。门禁不再由人工判定后通过 `--gates-passed` 传入；遥测采集时 `collect_telemetry.py` 直接消费此结果。

```bash
# 🆕 自动恢复失败的约束
python scripts/harness.py recover --dry-run    # 预览
python scripts/harness.py recover              # 执行恢复
python scripts/harness.py recover --domain STRUCT
```

## 结构化约束格式 (constraints.yaml)

```yaml
constraints:
  - id: C-STRUCT-01
    domain: STRUCT
    level: MUST
    description: "治理文档目录 governance/ 存在"
    check: "test -d governance/"
    watch_paths: ["governance/"]
    gate: G1
```

每条约束包含：
- `check`: 可执行检查。推荐 `check_type: command` 的 argv 数组或 `check_type: predicate`；Shell 检查必须显式声明 `posix` / `powershell` / `cmd` 方言，缺失时 fail closed。
- `check_type`: 设为 `predicate` 时只允许无副作用白名单函数，如 `is_file`、`is_dir`、`contains`、`all_files` 和 `python_syntax`。旧 `python` 类型会被安全阻断。
- `watch_paths`: 关联文件列表（变更时触发检查），兼作约束生效范围（Scope）
- `gate`: 所属门禁
- `on_failure`: 执行策略 — `block`(阻断) / `warn`(告警) / `escalate`(暂停并提交 IO/OA 裁决) / `log`(仅记录)
- `level`: 约束等级 — `MUST` / `SHOULD` / `MAY`（影响默认 on_failure 行为）
- `owner`: **谁能解释规则或批准例外**（IO / OA / Tech Lead），v1.5 新增
- `evidence`: **通过后保留什么证据**（日志/截图/测试输出），v1.5 新增，供 `audit_evidence.py` 校验证据包覆盖度
- `manual: true`: 标记为人工检查（自动跳过）

## 例外管理

```yaml
exceptions:
  - id: EX-001
    constraint_id: C-QUAL-03
    reason: "MVP 阶段暂不执行 benchmark"
    approved_by: "IO"
    valid_until: "2025-08-21"  # 到期自动恢复检查
```

## CI/CD 集成

```bash
# pre-commit hook
python scripts/harness.py check --domain STRUCT,DATA --format json
# 退出码非 0 → 阻止提交

# GitHub Actions
- name: 约束检查
  run: python scripts/harness.py check --all --format json
```

## 可移植性与常见陷阱（v1.17 新增）

> 以下问题来自 skill 分发到其他机器后的真实反馈。本节帮助你在新环境中快速排障。

### 陷阱 1: HARNESS_PY 路径或 pyyaml 缺失 → 门禁全 UNEVALUATED

**症状**: `collect_telemetry.py` 产出的遥测中 G0-G8 全是 `passed: null`、`evidence_status: UNEVALUATED`，must_constraints 为手动填的数字而非自动校验。

**根因**: harness.py 的 `_load_yaml` 需要 pyyaml，而系统 python3 未预装。旧版 `collect_telemetry.py` 的 `_harness_py()` 默认指向作者机器路径（`/Users/wanglijie/...`），他机不存在。

**修复（v1.17 已内置）**: `_harness_py()` 现在按优先级自动解析:
1. `HARNESS_PY` 环境变量（用户显式指定）
2. `sys.executable`（当前 python 已能 import yaml 则直接用）
3. `~/.agentic-agile-343/venv`（自动创建的持久 venv，首次自动 bootstrap pyyaml）

手动修复（若自动引导失败）:
```bash
python -m venv ~/.agentic-agile-343/venv
python -m pip install pyyaml
# 之后直接使用统一入口；Windows/macOS/Linux 均由 _bootstrap.py 解析正确解释器
python scripts/cli.py check --all
```

### 陷阱 2: npx 类 check 超时

**症状**: 约束 `check` 字段使用 `npx <tool>`（如 `npx secretlint`），首次执行因现场下载包超过 30s 超时。

**修复**: 把工具预装到 devDependencies，check 改为直接调用二进制:
```bash
npm i -D secretlint @secretlint/secretlint-rule-preset-recommend
# constraints.yaml 中 check 改为:
check: "node_modules/.bin/secretlint '**/*' --secretlintrc .secretlintrc.json"
```

### 陷阱 3: git 类 check 在非 git 项目中失败

**症状**: `git check-ignore .env.local` 等命令在未 `git init` 的项目中返回非 0，约束误判失败。

**修复**: check 前加 git 仓库判定，或在 auto_recover 中执行 `git init`:
```yaml
check: "git rev-parse --git-dir && git check-ignore .env.local"
auto_recover:
  command: "git init"
  description: "初始化 git 仓库使 check-ignore 可用"
```

### 陷阱 4: 覆盖率读取为 0

**症状**: C-QUAL-01 误判失败，harness 报 coverage=0.0，但实际测试通过。

**根因**: harness 的 `_parse_coverage` 只读 `coverage/coverage-summary.json`。vitest 默认不生成此文件。

**修复**: vitest.config.ts 中配置 json-summary reporter:
```typescript
export default defineConfig({
  test: {
    coverage: {
      reporter: ['text', 'json-summary'],  // json-summary 是 harness 读取的格式
    },
  },
});
```
然后运行 `npx vitest run --coverage`，确认 `coverage/coverage-summary.json` 生成。

### 仍需手动录入的指标

以下两项 harness 无法自动采集，需从平台面板手动录入:
- **Token 消耗**: 从 AI 平台用量面板读取，通过 `--token-usage` 参数传入
- **上下文压缩比**: 用 `crop_context.py` 估算，通过 `--context-input-tokens` / `--context-output-tokens` 传入
