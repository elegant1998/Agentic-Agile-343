# 跨人、跨工具、跨模块协作

> **核心原则**: 3-4-3 不仅适用于单人单工具单项目，也适用于多人多工具多模块的大型项目。

## 核心机制

| 机制 | 工件 | 解决什么问题 |
|------|------|-------------|
| **治理协议** | `protocol.yaml` | 工具无关的治理中枢——不依赖 Python 运行时 |
| **两级 OA** | 全局 OA + 模块 OA | 治理去中心化——全局 OA 管跨模块，模块 OA 管本模块 |
| **全局约束** | `protocol.yaml` §2 | 所有模块必须遵守的硬性红线 |
| **跨模块接口契约（XC）** | `protocol.yaml` §3 | 模块间 API 依赖的正式定义 |
| **集成 DAG** | `protocol.yaml` §4 | 模块间集成顺序编排 |
| **多语言 checks** | `protocol.yaml` §5 | 同一检查提供 shell/python/node/manual 多版本 |
| **遥测合并** | `collect_telemetry.py --merge` | 自动合并多工具遥测 |
| **证据聚合** | `aggregate_evidence.py` | 聚合各模块证据包 → 发布证据包 |

## 工具适配

| AI 工具 | 如何接入 3-4-3 |
|---------|---------------|
| **WorkBuddy** | 原生支持，所有脚本直接运行 |
| **Codex (Copilot)** | 全局约束 → `.github/copilot-instructions.md`；遥测 → `.codex/telemetry.json` |
| **Claude Code** | 全局约束 → `CLAUDE.md`；遥测 → `.claude/telemetry.json` |
| **其他** | 读取 `protocol.yaml`，使用 §5 中的 shell/manual 版本检查 |

> **关键设计**: `protocol.yaml` 是纯 YAML 文本，任何 AI 工具都能读取。不开发工具专用插件——文本即协议。

## 角色分工

| 角色 | 前身 | 核心职责 |
|------|------|----------|
| **IO** (意图主理人) | PO / 业务发起人 | 签署意图契约，最终审批证据包 |
| **OA** (编排架构师) | Scrum Master / 架构师 | 维护约束矩阵，设计契约，治理运行，汇总证据 |
| **AS** (自治蜂群) | 开发/测试/运维团队 | 执行 SCOPE-V 循环，产出代码 + 测试 + 证据 |

### 多模块场景：两级 OA 治理

当项目包含多个模块（5 人 × 5 模块 × 多种 AI 工具）时，引入两级 OA：

```
全局 IO ──签署──→ 全局 OA（Tech Lead）
                     │
                     ├── 维护 protocol.yaml（模块清单 + 跨模块契约 + 集成 DAG）
                     ├── 维护全局 constraints.yaml
                     ├── 聚合各模块证据包 → 发布证据包
                     └── 最终 HITL 签署
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   模块 OA₁           模块 OA₂          模块 OA₃
   (WorkBuddy)        (Codex)         (Claude Code)
        │                 │                 │
      AS₁               AS₂               AS₃
```

| 角色 | 职责 |
|------|------|
| **全局 OA** | 维护 `protocol.yaml`；下发全局约束；协调跨模块集成 DAG；聚合遥测和证据包；最终发布裁决 |
| **模块 OA** | 维护本模块 governance/；遵守全局约束和跨模块接口契约（XC）；运行 harness/verify；上报遥测 |

> 模块 OA 快速启动指南: `templates/Template_Module_Governance.md`

---

## 多人多模块协作：端到端使用流程

> **何时需要**: 项目 ≥2 个模块、或 ≥2 个人、或 ≥2 种 AI 工具。
> **何时不需要**: 单人单模块 — 忽略此章节，直接按 §1-10 操作。

### 角色速查

| 你是谁 | 你的模板 | 你的任务 |
|--------|---------|---------|
| 全局 OA（Tech Lead） | `Template_Protocol.yaml` | 初始化 protocol.yaml，协调集成，聚合发布 |
| 模块 OA（模块负责人） | `Template_Module_Governance.md` | 建立本模块治理，遵守全局约束，上报遥测 |
| 全局 IO（业务发起人） | 无模板 | 签署全局约束，最终发布裁决 |

### 第一步：全局 OA 初始化跨模块治理

**时机**: 项目启动，模块划分确定后。

```bash
# 1. 如果还没有治理目录，先初始化
mkdir -p governance/contracts governance/evidence

# 2. 复制并填写跨工具治理协议
cp templates/Template_Protocol.yaml governance/protocol.yaml
```

**编辑 `governance/protocol.yaml`**:

```yaml
# §1: 填模块清单
modules:
  - id: user
    name: "用户模块"
    owner: "张三"
    tool: workbuddy
    repo: "git@github.com:team/user-service.git"
    constraints_ref: "modules/user/constraints.yaml"
    description: "用户注册/登录/认证/会员信息"

  - id: order
    name: "订单模块"
    owner: "李四"
    tool: codex
    repo: "git@github.com:team/order-service.git"
    constraints_ref: "modules/order/constraints.yaml"
    description: "订单创建/查询/状态管理"
  # ... 按需追加

# §2: 填全局约束（所有模块必须遵守）
global_constraints:
  - id: GC-01
    domain: STYLE
    level: MUST
    rule: "API 响应统一格式 {\"code\":0,\"data\":T,\"message\":\"\"}"
    reason: "前端拦截器依赖此格式"
    applies_to: [all]
  # ... 按需追加

# §3: 填跨模块接口契约
cross_module_contracts:
  - id: XC-001
    provider: user
    consumer: [order]
    endpoint: "POST /api/user/verify"
    description: "订单模块调用用户模块验证用户身份"
    spec:
      request: { "user_id": "int", "token": "str" }
      response: { "code": 0, "data": { "valid": true } }
    sla:
      p95_latency_ms: 50
  # ... 每个 provider→consumer 关系一条

# §4: 填集成 DAG
integration_dag:
  phases:
    - id: phase-1
      name: "独立开发"
      parallel: [user, product]     # 无相互依赖，可并行
    - id: phase-2
      name: "依赖开发"
      depends_on: [user]
      parallel: [order, payment]    # 需要用户模块先完成
    - id: phase-3
      name: "集成测试"
      depends_on: [user, product, order, payment]
      gate: integration
    - id: phase-4
      name: "发布"
      depends_on: [phase-3]
      gate: release
```

```bash
# 3. 提交 protocol.yaml，通知所有模块 OA
git add governance/protocol.yaml
git commit -m "feat(governance): 初始化跨模块治理协议"
```

### 第二步：模块 OA 各自启动

**时机**: 收到全局 OA 的 protocol.yaml 后。

```bash
# 1. 建立本模块治理目录
mkdir -p governance/contracts governance/evidence

# 2. 从 protocol.yaml 复制全局约束 → 本模块 AI_Coding_Guide
cp templates/Template_AI_Coding_Guide.md governance/AI_Coding_Guide.md
# 编辑: 把全局约束中的硬性红线填入 §1

# 3. 如果本模块有特殊约束（如支付模块的 PCI-DSS）
mkdir -p modules/<你的模块>
cp templates/Template_Constraints.yaml modules/<你的模块>/constraints.yaml
# 编辑: 只保留本模块特有的约束，全局已有的不要重复

# 4. 如果本模块是 XC provider，确认接口签名
# 5. 初始化本模块意图图谱和首份契约（标准 SCOPE-V 流程）
cp templates/Template_Intent_Graph.md governance/Intent_Graph.md
```

**工具特定操作**:

| 如果你的工具是 | 额外操作 |
|--------------|---------|
| WorkBuddy | 无需额外操作。`crop_context.py` 自动加载 `AI_Coding_Guide.md` |
| Codex | 将全局约束复制到 `.github/copilot-instructions.md` |
| Claude Code | 将全局约束 + 本模块 AI_Coding_Guide 追加到 `CLAUDE.md` |

### 第三步：并行开发（日常）

```bash
# 裁剪上下文（自动注入全局约束 + 本模块 AI_Coding_Guide）
python3 scripts/crop_context.py --task T-XXX --domain <你的域>

# 检查本模块约束
python3 scripts/harness.py check --all --module <你的模块>

# 周期结束后收集遥测
python3 scripts/collect_telemetry.py \
    --project <模块名> \
    --module-id <你的模块> \
    --tool <workbuddy|codex|claude-code> \
    ... \
    --output governance/telemetry.json
```

### 第四步：集成测试（全局 OA 协调）

```bash
# 验证跨模块接口契约
python3 scripts/verify_cross_module.py --all --base-url http://localhost:8000

# 建立/更新 XC 基线
python3 scripts/verify_cross_module.py --all --baseline
```

### 第五步：证据聚合与发布裁决

```bash
# 合并所有模块遥测
python3 scripts/collect_telemetry.py --merge auto --output telemetry_merged.json

# 聚合所有模块证据包 → 发布证据包
python3 scripts/aggregate_evidence.py --all --output governance/evidence/RELEASE_Evidence_Bundle.md

# 全局 IO 审阅 RELEASE_Evidence_Bundle.md，签署发布裁决
```

### 常见问题

**Q: 模块 OA 说"全局约束不适用于我的模块"怎么办？**

模块 OA 向全局 OA 提例外申请。全局 OA 在 `protocol.yaml` 中修改该约束的 `applies_to` 列表，排除该模块。或模块 OA 在模块级 `constraints.yaml` 中添加 exception。

**Q: 跨模块 XC 接口需要变更怎么办？**

Provider 模块 OA 向全局 OA 提 XC 变更请求。全局 OA 评估影响范围（哪些 consumer 受影响），更新 `protocol.yaml §3`，通知所有 consumer 模块 OA。破坏性变更需要所有 consumer 确认后才能合并。

**Q: 某模块用了非 Python 技术栈（Go/Java/Node），治理脚本怎么办？**

`protocol.yaml §5` 提供了多语言等效命令。模块 OA 使用 `shell` 或 `manual` 版本。遥测数据按 `§6 telemetry_spec` 格式手动上报 JSON。

**Q: 5 个模块不在同一个 git 仓库怎么办？**

`protocol.yaml` 放在全局 OA 指定的"治理仓库"中。每个模块 OA 在自己的仓库中建立 `governance/` 目录。集成测试时全局 OA clone 所有仓库到同一台机器。
