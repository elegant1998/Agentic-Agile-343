# Verified Engineering：六维验证体系

> **核心原则**：在每一个关键决策点之前，用自动化手段预先验证"下一步是正确的"，而非事后发现错误。

## 验证矩阵

```
┌──────────────────────────────────────────────────────────┐
│  P0 — 核心验证（每次 SCOPE-V 必须通过）                    │
│  ├─ verify_contract.py   → AC 逐条自动化验证              │
│  └─ audit_evidence.py    → 证据包门禁完整性审计            │
├──────────────────────────────────────────────────────────┤
│  P1 — 结构验证（跨工件一致性保障）                         │
│  ├─ verify_triangulation.py → 图谱/契约/约束三方一致性    │
│  └─ harness.py NFR 扩展     → 安全/可靠性/可观测性扫描     │
├──────────────────────────────────────────────────────────┤
│  P2 — 时序验证（长期运行保障）                             │
│  ├─ verify_rollback_safety.py → 回滚前 DAG 安全性分析     │
│  └─ verify_freshness.py       → 工件时效检测              │
└──────────────────────────────────────────────────────────┘
```

## P0: 契约一致性验证 (verify_contract.py)

读取 YAML 契约的 `ac` 字段，逐条执行可验证断言。支持四种验证类型：

| 类型 | 前缀 | 示例 |
|------|------|------|
| shell | `type: shell` | 执行 bash 命令，退出码 0 = 通过 |
| http | `type: http` | 发起 HTTP 请求，检查状态码/响应体 |
| db | `type: db` | 执行 SQL 查询，检查行数/值 |
| assert | `type: assert` | 运行 Python 表达式，True = 通过 |

契约 ac 字段示例：
```yaml
ac:
  - id: "AC-01"
    desc: "用户可查询自己的积分余额"
    verify:
      type: http
      method: GET
      url: "/api/member/points"
      headers:
        Authorization: "Bearer {{token}}"
      expect:
        status: 200
        body_contains: "points"
```

```bash
# 验证单个契约
python scripts/verify_contract.py --task T-003

# 验证所有契约
python scripts/verify_contract.py --all

# HTTP 验证指定 base URL
python scripts/verify_contract.py --all --base-url http://localhost:8000
```

## P0: 证据包完整性审计 (audit_evidence.py)

对照 `constraints.yaml` 的 gate 定义，逐门禁检查证据包覆盖度（v1.11+ 按约束 ID 判定）：

- 每个 gate 的 MUST 约束是否都在证据包中被引用（按约束 ID 检索，如 `C-DATA-01`）
- 证据包是否包含测试/检查结果
- HITL 签署区是否完整

> **证据包发现（v1.11+）**：同时支持按任务拆分模式（`governance/evidence/EB-T-XXX.md`，推荐）和单文件模式（`governance/Evidence_Bundle.md`）。
> **覆盖判定（v1.11+）**：不再按"门禁章节名"匹配（与模板 §3 按域组织的结构不兼容），改为检查约束 ID 是否出现在任一证据包中——与 Template_Evidence_Bundle 的 §3 约束符合性表天然对齐。

```bash
# 审计证据包
python scripts/audit_evidence.py

# 仅审计指定门禁
python scripts/audit_evidence.py --gate G4

# JSON 输出（CI 消费）
python scripts/audit_evidence.py --format json
```

## P1: 三方一致性验证 (verify_triangulation.py)

四项交叉检查：
1. 图谱 domain → 约束矩阵 domain（孤儿域检测）
2. 契约任务 ID → 图谱任务节点（可追溯性）
3. MUST 约束 → 契约 AC 覆盖（未追踪约束检测）
4. 契约 domain → 约束 gate 匹配

```bash
python scripts/verify_triangulation.py
```

**契约格式**：同时支持 YAML（`Intent_Contract_*.yaml`）和 Markdown（`Intent_Contract_*.md`）契约，自动识别。

**业务域 ↔ 治理域映射（v1.10.1+）**：意图图谱通常使用业务域（如 BRAND/MEMBER/COURSE），约束矩阵使用治理域（STRUCT/DATA/BEHAVE...）。两者是不同维度的分类，通过 `constraints.yaml` 中的 `domain_mapping` 字段显式声明交叉覆盖关系：

```yaml
# constraints.yaml
domain_mapping:
  BRAND: [STRUCT, BEHAVE, STYLE]    # 业务域 → 覆盖的治理域
  MEMBER: [DATA, BEHAVE, SEC]
  "*": [PROC, REL, OBS]             # "*" = 全局治理域（不隶属特定业务域）
```

声明映射后，检查 1 和检查 4 按映射验证（每个业务域有治理域覆盖、每个治理域被覆盖）；未声明时退回关键词模糊匹配（向后兼容）。

**检查 3 的覆盖判定**：MUST 约束有两种合法覆盖来源——
- 带可执行 `check` 的自动约束 → 由 harness 门禁覆盖，豁免 AC 匹配
- `manual: true` 的人工约束 → 未匹配 AC 时仅输出 MANUAL_REVIEW 提示（不阻断），由 OA 确认已在 HITL 审查中覆盖

**模板约束同步**：`templates/Template_Constraints.yaml` 已附带 `domain_mapping` 示例段，新项目初始化时按需填写。

## P1: NFR 验证扩展 (harness.py) — 跨语言

`harness.py` 内置 7 个 NFR 验证器（含质量类 `test_run`），通过 `nfr:` 前缀自动路由。**全部验证器均为跨语言设计**（支持 Python / TypeScript / JavaScript / Go / Rust / Java / C# / Ruby 等主流栈），源码扫描覆盖 `*.py *.ts *.tsx *.js *.jsx *.go *.rs *.java *.cs *.rb`：

| 验证器 | 域 | 说明 | 语言适用性 |
|--------|-----|------|-----------|
| `nfr:bandit` | SEC | bandit 安全扫描 | **仅 Python 项目**（TS/JS/Go 等项目自动跳过，不误判） |
| `nfr:secrets` | SEC | 硬编码密钥/令牌扫描（正则） | 跨语言 |
| `nfr:health_endpoint` | REL | 健康检查端点检测（路由/路径正则） | 跨语言 |
| `nfr:retry_pattern` | REL | 重试/熔断/超时模式检测（含 axios-retry、resilience4j、backoff 等） | 跨语言 |
| `nfr:log_structured` | OBS | 日志使用检测（含 winston/pino/console.log/structlog 等） | 跨语言 |
| `nfr:monitoring_endpoint` | OBS | 指标端点检测（含 /metrics、prom-client 等） | 跨语言 |
| `nfr:test_run` | QUAL | 运行测试套件并采集结构化计数/覆盖率（vitest/jest/pytest/go test/cargo test/mvn test/dotnet test） | 跨语言 |

> **门禁与测试全部源自约束矩阵（v1.14+）**：`collect_telemetry.py` 在采集项目级遥测时（Web/代码项目）会**自动调用 `harness check --all` 与 `harness tests`**，从 `constraints.yaml` 派生 G0-G8 全部门禁**与**测试计数（默认开启，可用 `--no-auto-nfr` 关闭自动 NFR/测试派生）。无需再手动以 `--gates-passed` / `--test-total` 传入——gates_total 自动为 9（1 意图前置 + 5 核心 + 3 Web 扩展），G0-G8 与测试数据必然基于真实约束与真实执行。harness 不可用时回退到手动参数并显式标记为「未评估」而非隐藏。

```bash
# 仅运行 NFR 检查（手动）
python scripts/harness.py check --nfr-only

# 列出可用 NFR 验证器
python scripts/harness.py nfr-list
```

约束定义示例（constraints.yaml）：
```yaml
- id: C-SEC-01
  domain: SEC
  level: SHOULD
  description: "Python 代码无高危安全问题"
  check: "nfr:bandit"
  nfr_params:
    target: "src/"
    severity: "medium"
  gate: G6
```

### 跨平台 check 原语（v1.15+）

约束的 `check` 字段默认使用 shell 命令（bash 优先，Windows 无 bash 时降级到 cmd.exe）。对于需要跨平台兼容的约束，可使用 `check_type: python` 指定 Python 表达式：

```yaml
- id: C-STRUCT-01
  domain: STRUCT
  level: MUST
  description: "governance 目录存在"
  check: "project_dir.joinpath('governance').is_dir()"
  check_type: python
  gate: G1
```

Python check 表达式可访问 `Path` 和 `project_dir` 变量。

## P2: 回滚安全性验证 (verify_rollback_safety.py)

在执行 DAG 回退前进行四维安全性分析：
1. **下游依赖**：目标节点的下游是否已开始执行
2. **数据迁移**：是否有需要反转的数据库变更
3. **图谱一致性**：回滚后是否破坏关键路径
4. **并行组影响**：回滚是否影响同组兄弟节点

```bash
# 验证回滚安全性
python scripts/verify_rollback_safety.py --target T-004

# 模拟分析
python scripts/verify_rollback_safety.py --target T-004 --dry-run
```

## P2: 时间窗口验证 (verify_freshness.py)

防止 AS 使用过期工件执行任务：
1. **契约时效**：签署是否超过 N 小时（默认 72h）
2. **图谱变更检测**：图谱自签署后是否被修改
3. **约束变更检测**：约束矩阵是否有新变更
4. **依赖工件版本**：契约引用的外部工件是否过期

> **已完成任务豁免（v1.11+）**：已有签署证据包（含 APPROVED 裁决）的任务自动豁免时效检查——契约已履行完毕，不存在"用过期契约执行"的风险。freshness 只对进行中的任务报警。

```bash
# 检查所有契约时效
python scripts/verify_freshness.py --all

# 自定义阈值
python scripts/verify_freshness.py --all --max-age-hours 48

# 检查指定任务
python scripts/verify_freshness.py --task T-003
```

## SCOPE-V 中的验证集成点

```
Specify → Constrain → Orchestrate → Prove → Verify
   │          │            │           │         │
   │          │            │           │         ├─ verify_contract.py
   │          │            │           │         ├─ audit_evidence.py
   │          │            │           │         └─ verify_freshness.py
   │          │            │           │
   │          │            └─ self_consistency_check.py
   │          │
   │          └─ verify_triangulation.py
   │
   └─ harness.py check --all（含 NFR）
```

每次 SCOPE-V 周期的 Verify 阶段，必须通过 P0 验证（契约一致性 + 证据包完整性），建议通过 P1 验证（三方一致性 + NFR），P2 验证在以下场景触发：
- 有并行任务执行时：`verify_rollback_safety.py`
- 距上次 HITL 签署超过阈值：`verify_freshness.py`
