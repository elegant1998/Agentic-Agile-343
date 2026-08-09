---
name: agentic-agile-343
description: "Agentic-Agile-343，让AI研发治理，进可攻退可守 By 无敌哥. Agentic AI governance: 3-4-3, intent contract, constraint matrix, evidence bundle, SCOPE-V, telemetry, Grill-Me, critical thinking."
display_name: "Agentic Agile 343"
version: "1.25.0"
author: "王立杰-无敌哥"
created: "2025-07-20"
---

# Agentic Agile 3-4-3 治理架构

基于《Agentic Agile智能体敏捷：从氛围编程到验证工程的AI研发治理指南》v1.6 的落地 skill。将 3-4-3 治理架构（3 个超级角色、4 个动态工件、3 大自治运行机制）转化为可直接使用的模板和工具。

> **v1.14+ 通用立场（跨项目、跨领域）**：批判性思维是 OA 的**默认职责**，不绑定任何特定产品、课程、证书或仓库。任何新需求在进入实现前，都可质疑、校准、给推荐默认；「用户字面意思 = 实现规格」是反模式。

## 触发场景

当用户提及以下任一关键词时激活本 skill：
- "3-4-3"、"343 架构"、"Agentic Agile"
- "意图契约"、"Intent Contract"
- "约束矩阵"、"Constraint Matrix"
- "证据包"、"Evidence Bundle"
- "SCOPE-V"、"意图图谱"
- "智能体敏捷"、"AI 研发治理"
- "算力遥测"、"价值遥测"、"telemetry dashboard"
- "既有项目"、"遗留系统"、"Recon"、"Change Envelope"
- "风险评估"、"治理模式"、"governance profile"

## 核心资源

本 skill 提供以下资源，按需加载：

| 资源 | 路径 | 用途 |
|------|------|------|
| 意图图谱模板 | `templates/Template_Intent_Graph.md` | 宏观导航地图，含裁剪关系 |
| 意图契约模板 (MD) | `templates/Template_Intent_Contract.md` | 单次任务执行基准（详细版） |
| 意图契约模板 (YAML) | `templates/Template_Intent_Contract.yaml` | 单次任务执行基准（精简版，用于上下文裁剪） |
| 约束矩阵模板 (MD) | `templates/Template_Constraint_Matrix.md` | 六域硬门禁（人类可读文档） |
| 约束定义 (YAML) | `templates/Template_Constraints.yaml` | 结构化约束定义（核心六域 + NFR 域 + 降级/恢复策略） |
| **AI 编码规范** | `templates/Template_AI_Coding_Guide.md` | **硬性红线 ≤5 + 分层约束 + 自检清单（L2 自动注入）** |
| **跨工具治理协议** | `templates/Template_Protocol.yaml` | **模块清单 + 跨模块契约 + 集成 DAG + 多语言 checks** |
| **模块 OA 指南** | `templates/Template_Module_Governance.md` | **多模块场景下模块负责人的快速启动指南** |
| 工具清单 | `templates/Template_Tools_Manifest.yaml` | **AS 可用工具白名单 + 权限边界 + 能力矩阵** |
| 证据包模板 | `templates/Template_Evidence_Bundle.md` | 裁决支撑材料（人类可读版） |
| 证据包模板 (YAML) | `templates/Template_Evidence_Bundle.yaml` | 结构化证据包（脚本消费：五类证据+映射表+遥测+6种裁决） |
| 工作图模板 | `templates/Template_Work_Graph.yaml` | DAG 任务拓扑（含超时 + 重调度策略） |
| 遥测收集器 | `scripts/collect_telemetry.py` | 自动收集管道/质量/性能/成本/治理指标 |
| **一键遥测** | `scripts/quick_telemetry.sh` | **简化版：只需 task_id，自动运行 harness + 采集遥测 + 生成 dashboard（v1.19）** |
| **门禁验证器** | `scripts/gate_check.py` | **SCOPE-V 5 个检查门的机械验证器：前置/编码/验证/收尾/Bug回溯（v1.20）** |
| **Token 实测** | `scripts/fetch_token_usage.sh` | **调用 @geeeger/ocusage 实测 AI 客户端真实 Token 用量，替代人工估算（v1.21）；缺失时自动 `npm i -g` 安装（v1.22）** |
| **依赖自举** | `scripts/ensure_py_env.sh` + `scripts/_bootstrap.py` | **自包含依赖 bootstrap：首次运行自动建 venv + 装 pyyaml，缺 ocusage 自动全局安装（v1.22）** |
| 代码上下文发现 | `scripts/discover_context.py` | AST 解析自动发现 API 端点、模型、依赖 |
| **轻量 Recon** | `scripts/recon.py` | **既有项目只读侦察，输出 Baseline / Preserve / Unknown / Change Envelope** |
| **风险评估** | `scripts/assess_risk.py` | **按事实推荐 explore / delivery / high-risk / legacy / multi-module 治理模式** |
| 上下文裁剪引擎 | `scripts/crop_context.py` | 三层注入模型，从图谱裁剪出给 AS 的精简 prompt |
| **Harness 引擎** | `scripts/harness.py` | **约束执行引擎（含 7 个 NFR 验证器，支持插件扩展）** |
| 自洽性检查 | `scripts/self_consistency_check.py` | LOOP-1: 校验产出物是否与契约一致 |
| 反思+反哺 | `scripts/reflect.py` | LOOP-2/3: 生成反思日志 + 反哺意图图谱 |
| **Graph 引擎** | `scripts/graph_engine.py` | **DAG 引擎（含 reschedule + timeouts 命令）** |
| **工具审计器** | `scripts/audit_tools.py` | **审计 AS 工具调用合规性（白名单/权限/边界）** |
| **契约验证器** | `scripts/verify_contract.py` | **逐条执行 AC 验收标准（shell/http/db/assert，支持 MD+YAML 契约）** |
| **证据包审计** | `scripts/audit_evidence.py` | **按约束 ID 检查证据包覆盖度（支持 EB-T-XXX 拆分模式）** |
| **三方一致性** | `scripts/verify_triangulation.py` | **图谱↔契约↔约束交叉一致性验证** |
| **回滚安全验证** | `scripts/verify_rollback_safety.py` | **DAG 回滚前安全性分析（下游/数据/并行组）** |
| **时间窗口验证** | `scripts/verify_freshness.py` | **工件时效检测（已完成任务自动豁免）** |
| **跨模块契约验证** | `scripts/verify_cross_module.py` | **验证跨模块接口契约（XC）可达性 + SLA + 破坏性变更** |
| **证据聚合器** | `scripts/aggregate_evidence.py` | **多模块证据包聚合 + 遥测合并 → 发布证据包** |
| **共享解析库** | `scripts/gov_common.py` | **契约/证据包/图谱统一发现与解析（MD+YAML 双格式），被各验证脚本复用** |
| **Loop Memory 模板** | `templates/Template_Loop_Memory.yaml` | **跨 cycle 统一状态文件（进度 + 教训 + 模式 + 决策）** |
| **Recon 基线模板** | `templates/Template_Recon_Baseline.md` | **既有项目的事实、保留项、未知项与变更围栏** |
| **Change Envelope** | `templates/Template_Change_Envelope.yaml` | **限定本轮允许和禁止修改的范围** |
| **治理模式模板** | `templates/Template_Governance_Profile.yaml` | **风险等级、最小工件、机械门和 HITL 要求** |
| 遥测仪表板 | `assets/dashboard.html` | 网页式实时大屏 |
| **参考文档** | `references/*.md` | **按需加载的详细参考（10 个文件，见下文各节链接）** |

## 使用流程

> **既有项目（v1.25.0）**：不要先机械复制全部治理模板。先运行只读 Recon，再根据风险评估建立最小治理底座：
>
> ```bash
> python scripts/cli.py recon --project-dir .
> python scripts/cli.py assess-risk --project-dir .
> ```
>
> Recon 产出 Baseline / Preserve / Unknown / Change Envelope；Intent Graph 和首份契约应由这些事实生成。信息不足时保留 Unknown，禁止自动降级为低风险模式。

> **单人项目**: 直接按 §1-10 操作，`protocol.yaml` 和模块治理完全不需要——
> 就像它们不存在一样。3-4-3 的默认行为不依赖它们。
>
> **多人多模块项目**: 先按下面 §11 初始化跨模块治理，再按 §1-10 各自开发。

### 1. 初始化项目治理（单人）

```bash
# 复制模板到新项目
cp templates/Template_Intent_Graph.md /path/to/project/governance/Intent_Graph.md
cp templates/Template_Constraint_Matrix.md /path/to/project/governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml /path/to/project/governance/constraints.yaml

# 可选但推荐：AI 编码规范（STYLE 域 + L2 自动注入的基础）
cp templates/Template_AI_Coding_Guide.md /path/to/project/governance/AI_Coding_Guide.md

# 可选：架构文档（crop_context.py L2 全局约束的信息源，
# 描述技术栈/API 规范/认证/ORM 等，没有则 L2 退化为通用提示）
cp docs/architecture.md /path/to/project/docs/architecture.md  # 如有模板
```

**工件命名约定**（所有验证脚本均按此发现工件，务必遵守）：

| 工件 | 路径 | 说明 |
|------|------|------|
| 意图图谱 | `governance/Intent_Graph.md` | 单文件，会话级 |
| 意图契约 | `governance/contracts/Intent_Contract_T-XXX.md`（或 `.yaml`） | **每任务一份**，MD/YAML 双格式均可 |
| 证据包 | `governance/evidence/EB-T-XXX.md` | **每任务一份**，与契约任务 ID 对应 |
| 约束矩阵 | `governance/constraints.yaml`（可执行版）+ `Constraint_Matrix.md`（人类可读版） | YAML 供 harness 引擎，MD 供 IO 审阅 |

**契约格式选择指引**：
- **MD 契约（推荐起步）**：人类可读性好，Grill-Me 决策确认 + **IO 显式签署**流程自然；AC 表格的"验证方式"列支持 `shell:`/`http:`/`assert:`/`db:` 前缀实现自动化验证（写自然语言则视为人工验证项）
- **YAML 契约（精简进阶）**：体积约为 MD 的 30%，适合上下文敏感的 AS 任务注入；支持 `self_consistency`、`depends_on` 等结构化字段
- 两种格式可混用，所有脚本（verify_contract / crop_context / verify_triangulation / self_consistency_check / verify_freshness）自动识别

**MD 契约的自洽性配置**：MD 契约如需启用 `self_consistency_check.py`，在契约中加一个围栏块：
````markdown
```yaml
self_consistency:
  expected_files: [src/App.tsx, server/index.ts]
  expected_endpoints: 5
  router_path: server/routes.ts
```
````

### 2. 按 SCOPE-V 循环执行（SDD + TDD 内嵌）

Specify → Constrain → Orchestrate → Prove → Evolve → Verify → 🔴 **Telemetry**（七步循环）。

- SDD：契约 AC = 可执行规约，`verify_contract.py --generate-tests` 自动生成测试骨架
- TDD：Red（写失败测试）→ Green（最小实现）→ Refactor（重构+反思）
- 🔵 微检查点：Orchestrate 后、Prove 前 AS 必须向 OA 复述目标+影响范围
- 🔴 Verify 后强制遥测：每任务 Verify 完成后必须运行 `collect_telemetry.py` 并给出结果摘要，否则不得标记"已完成"

> 📖 完整流程图、SDD/TDD 详解、微检查点规则、遥测最小参数、落盘结果、跳过后果详见 **[references/scope_v_execution.md](references/scope_v_execution.md)**。

### 3. 收集遥测数据（4 层 9 维模型）

`collect_telemetry.py` 自动采集价值层（目标准确率/首次成功率/ROI）、能力层（自愈率/自主性评分/HITL）、效率层（压缩比/Token效率/执行效率）、进化层（知识沉淀率）。

> 📖 完整采集命令、4 层 9 维指标体系、核心指标公式与健康阈值详见 **[references/telemetry_collection.md](references/telemetry_collection.md)**。

### 4. 查看遥测大屏

`collect_telemetry.py` 自动生成内嵌数据的 HTML，双击即可（无需 server）。总览页 ⇄ 单次契约页双向跳转。

> 📖 详见 **[references/telemetry_collection.md](references/telemetry_collection.md#遥测大屏v1131-纯静态--无需-server)**。

### 5. 上下文工程：三层注入模型

L1 意图图谱（OA 会话级）→ L2 全局约束（共享）→ L2+ AI 编码规范（AS 任务级）→ L3 任务切片（收敛）。`crop_context.py` 自动裁剪，支持隔离验证和 watch 模式。

> 📖 三层注入模型图、裁剪工作流、YAML 精简契约格式详见 **[references/context_engineering.md](references/context_engineering.md)**。

### 6. Harness Engineering：可执行约束护栏

`constraints.yaml` → `harness.py check --all` 一条命令完成全量门禁检查。门禁 G0-G8 直接从约束 `gate:` 标签聚合。支持按域/按门禁/NFR 检查、自动恢复、CI/CD 集成。

> 📖 引擎用法、constraints.yaml 格式、例外管理、CI/CD 集成详见 **[references/harness_engineering.md](references/harness_engineering.md)**。

### 7. LOOP Engineering：自我纠错与持续进化

> SCOPE-V 的 Evolve 是完整的**自我纠错→反思→进化**闭环。三层 LOOP 模型详见 **[references/loop_graph_engineering.md](references/loop_graph_engineering.md)**。

### 8. Graph Engineering：可编程的 Agent 组织架构

> 复杂任务应**显式定义为有向无环图（DAG）**。两层图模型、DAG 定义、Graph Engine 用法详见 **[references/loop_graph_engineering.md](references/loop_graph_engineering.md#graph-engineering可编程的-agent-组织架构)**。

> Graph × LOOP × Harness × Context 四维度形成完整的 Agent 治理闭环。

### 9. Verified Engineering：六维验证体系

| 优先级 | 验证工具 | 说明 |
|--------|---------|------|
| P0 | `verify_contract.py` | AC 逐条自动化验证（shell/http/db/assert） |
| P0 | `audit_evidence.py` | 证据包门禁完整性审计 |
| P1 | `verify_triangulation.py` | 图谱/契约/约束三方一致性 |
| P1 | `harness.py` NFR 扩展 | 安全/可靠性/可观测性扫描（7 个验证器） |
| P2 | `verify_rollback_safety.py` | 回滚前 DAG 安全性分析 |
| P2 | `verify_freshness.py` | 工件时效检测 |

> 📖 验证矩阵详解、NFR 验证器列表、SCOPE-V 验证集成点详见 **[references/verified_engineering.md](references/verified_engineering.md)**。

### 10. 遥测扩展框架（P2 — 待自动化）

> 4 个 P2 指标的度量框架、公式、健康阈值详见 **[references/telemetry_framework.md](references/telemetry_framework.md)**。

## 跨人、跨工具、跨模块协作（v1.8 新增）

> 3-4-3 不仅适用于单人单工具单项目，也适用于多人多工具多模块的大型项目。详见 **[references/multi_module.md](references/multi_module.md)**。

## Harness Engineering 六大支柱总览

| # | 支柱 | 核心问题 | 关键资产 |
|---|------|----------|----------|
| 1 | **上下文管理** | AI 应该看到什么？ | crop_context.py |
| 2 | **工具系统** | AI 能触达和操作什么？ | tools_manifest.yaml + audit_tools.py |
| 3 | **执行编排** | AI 应按什么顺序完成任务？ | work_graph.yaml + graph_engine.py |
| 4 | **状态与记忆** | AI 应该记住什么？ | reflect.py |
| 5 | **评估与观测** | 怎样判断 AI 做得对不对？ | collect_telemetry.py + verify_* |
| 6 | **约束与恢复** | AI 不能做什么，失败后怎样恢复？ | harness.py + constraints.yaml |

> 📖 六大支柱详细树状图、约束域分层说明详见 **[references/six_pillars.md](references/six_pillars.md)**。

## 🔴 批判性思维（Critical Thinking · v1.15 硬性 · 跨项目通用）

> **适用范围**：**所有**使用本 skill 的项目。OA 在 Specify / Constrain 阶段的**默认工作方式**——把模糊意图校准为可验证、可运营、成本合理的契约。
> **禁止**：「用户说了 → 我照做 → 完成」而跳过批判性思维。

核心原则、7 大可疑信号、挑战话术模板、反哺教训写法详见 **[references/critical_thinking.md](references/critical_thinking.md)**。

## Grill-Me 交互协议（HITL 提示词工程）

> HITL 不应是"甩一份完整文档让 IO 通读"，而应是**逐条引导 IO 决策，每次只问一个问题，并给出推荐的默认答案**。
> **叠加 v1.14**：先运用**批判性思维**校准可疑规则，再 Grill-Me 逐条确认——对所有项目一律生效。

详细协议格式、示例、关键规则、对话流状态机、HITL 触发条件见 **[references/critical_thinking.md](references/critical_thinking.md#grill-me-交互协议hitl-提示词工程)**。

## 人机分工：四类任务模型

> 不是按"介入程度"分（人工决策/审核/全自动），而是按**任务性质**分——每一类任务放到最擅长的执行者手上。

| 任务性质 | 谁做 | 典型场景 | 3-4-3 机制 |
|---------|------|---------|-----------|
| **1. 不可逆操作** | 人批 | 删除生产数据、修改生产配置、对外发布、大额资金操作 | HITL 触发 + Tools Manifest `requires_approval` + `BOUNDARY_DEPLOY` |
| **2. 价值判断** | 人决策 | 方案选型、风险偏好、内容风格取舍 | Grill-Me 协议（逐条确认 + 推荐默认值）+ IO 签署契约 |
| **3. 不确定验证** | 人审 | 逻辑审查、边界情况、上下文敏感检查 | 🆕 Evidence_Bundle §11.5 人工审查清单 |
| **4. 可自动化** | AI 做 | 测试执行、Git 操作、通知发送、数据预处理 | SCOPE-V 执行循环 + harness.py + verify_contract.py |

> **判定标准**: 每一类任务是否都被放到了最擅长的执行者手上？
> 不可逆的不自动、价值判断不推给 AI、不确定的不盲信测试、可自动化的不浪费人力。

## 约束优先级链

```
法律/安全约束 > 约束矩阵 > 已签署意图契约 > 实现便利性
```

任何例外只能由人类 IO 通过签署的书面批准授予。

## 禁止事项

- 不得修改已签署的 Intent_Contract.md
- 不得降低 Constraint_Matrix.md 中的门禁
- 不得通过删除、跳过或弱化测试获得通过
- 不得用 pytest 总耗时替代专用性能基准
- 任一 MUST 失败时，不得生成可上线结论
- **P0 验证未通过时，不得进入 HITL 签署**
- **证据包门禁覆盖不完整时，不得标记 Verify 完成**
- **契约过期（超过时效阈值）时，必须先重新签署再执行**
- **🔴 意图契约 Verify 完成后未运行 collect_telemetry.py 并给出结果摘要的，不得标记任务为"已完成"，证据包不得裁决 APPROVED**（v1.12）
- **🔴 批判性思维（跨项目）**：不得盲从 IO 第一句字面需求；遇歧义、激励过密、与北极星冲突、不可验证、安全过宽时须先挑战并给推荐默认，确认前不得实现（v1.15）
- **🔴 可移植性（v1.17）**：collect_telemetry.py 不得依赖作者机器路径；harness 调用前须自动检测 pyyaml 并引导持久 venv（`~/.agentic-agile-343/venv`），确保 skill 分发到任意机器后门禁可自动评估而非降级为 UNEVALUATED
- **🔴 契约前置（v1.18）**：不得在意图契约签署前开始编码实现。任何功能开发任务必须先完成 Specify（意图契约草稿）→ Constrain（约束矩阵）→ Grill-Me 决策确认 → **IO 显式签署（sign-off，OA 不得代签）**，然后才能进入 Orchestrate（编码）。注意：**Grill-Me 逐条确认 ≠ 契约签署**，签署是 IO 审阅完整契约后的独立显式动作。仅以下任务可豁免：纯查询/阅读/规划类任务、bug 修复（但需补 AC）、配置变更（但需补约束检查）
- **🔴 证据包强制（v1.18）**：任一功能任务 Verify 完成后，必须生成 Evidence_Bundle（至少包含 AC 验证结果 + 约束检查结果 + 遥测摘要），不得跳过。未生成证据包时任务不得标记为"已完成"，与 v1.12 遥测规则共同构成 Verify 收尾双门
- **🔴 意图图谱回写（v1.18）**：任务完成后必须回写意图图谱：(a) 新增模块/能力节点 (b) 遇到的教训 (c) 下一步迭代方向。跳过回写视为 Evolve 阶段未完成，任务不得关闭
- **🔴 遥测结果验证（v1.19）**：收尾门的遥测检查不只是"是否运行了脚本"，必须验证三件事：(a) `telemetry/runs/telemetry-T-XXX.json` 单任务文件存在 (b) `telemetry.json` 的 `meta.run_count` 比运行前增加 (c) `dashboard.html` 修改时间已更新。推荐使用 `quick_telemetry.sh` 一键完成
- **🔴 TDD 强制（v1.20）**：Orchestrate 阶段必须先写测试（Red），再写实现（Green），再重构（Refactor）。编码门检查"测试已先写且运行 RED"；验证门检查"测试 GREEN + AC 逐条验证通过 + test-total > 0"。AC 验证方式为 `shell:grep` 的条目不得超过总 AC 的 50%，至少一半必须用 `assert:`/`http:`/`db:` 运行时验证
- **🔴 遥测数据真实性（v1.20）**：collect_telemetry.py 的 `--test-total`/`--test-passed` 参数不得手工编造。必须先运行 `npx vitest run`（Node 项目）或 `pytest`（Python 项目）获取真实测试数，再将结果传入。若项目无测试套件，`--test-total` 传 0 并在证据包中标注"TDD 缺口"
- **🔴 Bug 回溯（v1.20）**：任一任务标记"已完成"后发现的 bug，必须：(a) 归属到对应契约 T-XXX（b）重新采集该任务遥测（`--tasks-first-pass 0 --auto-healed 1`）（c）在证据包追加"事后 bug 记录"段（d）回写意图图谱教训。跳过回溯视为该任务首次成功率数据虚假
- **🔴 Token 用量实测（v1.21）**：`--token-usage` 不得人工估算。优先通过 `scripts/fetch_token_usage.sh <项目名> [日期] [客户端]` 调用 `@geeeger/ocusage` 从 AI 客户端（workbuddy/claude/codex/opencode 等）本地数据实测；`quick_telemetry.sh` 已自动集成（环境变量 `OCUSAGE_CLIENT`/`OCUSAGE_DATE` 可覆盖）。实测成功时 `cost.token_source` 标记为 `measured:ocusage:*`，dashboard 显示"● 实测"绿色徽标；仅当 ocusage 不可用（未安装/无数据）时才允许回退估算并标记 `estimated`。前置条件：`@geeeger/ocusage` 由 `fetch_token_usage.sh` 自动检测，缺失时自动 `npm i -g` 安装（需 node ≥ 22.5），无需用户手动安装
- **🔴 依赖自包含（v1.22）**：skill 所有运行时依赖必须自包含、开箱即用——新用户安装 skill 后**无需手动装依赖**即可运行全部脚本。Python 侧：所有脚本的 `import yaml` 失败会自动触发 `_bootstrap.ensure_yaml_available()` → 调用 `ensure_py_env.sh` 建持久 venv（`~/.agentic-agile-343/venv`）并装 pyyaml，再用 venv 的 python `os.execv` 重启脚本（仅首次，之后直连 venv 不再重建）。Node 侧：`fetch_token_usage.sh` 在 本地 node_modules → 全局 ocusage → npx → `npm i -g @geeeger/ocusage` 四级查找，最终兜底自动安装。`quick_telemetry.sh` 已统一通过 `ensure_py_env.sh` 获取运行时，不再硬编码任何个人机器路径。`ensure_py_env.sh` 动态查找 managed python（`~/.workbuddy/binaries/python/versions/*/bin/python3`）并回退系统 `python3`，保证跨机器可移植
- **🔴 显式签署·禁代签（v1.23）**：Grill-Me 决策确认**不等于**契约签署（sign-off）。OA 不得自行在契约中写入 `SIGNED`、IO 署名或"自动签署"标记；签署区 `IO（意图主理人）` 一行必须由 IO 本人填写并明确确认（回复「签署」或署名）。签署前不得创建业务代码（与 v1.18 契约前置一致）。`gate_check.py --gate pre` 会扫描"自动签署 / 代签 / OA 代"等标记并直接判失败，签署区缺失或 IO 未署名同样失败。
- **🔴 签署检测否定语境修复（v1.23.1）**：`gate_check.py` 的代签扫描不得裸匹配子串。当"OA 代 / 代 OA / 自动签署"等标记出现在**否定语境**（同一行含 非/禁止/不得/无/不/未/并非/not/no）时——如"**非 OA 代签**""**禁止 OA 代签**"——属反代签的正向说明，必须**放行**而非误报失败。避免 IA 为规避误报而被迫改写合法签署措辞。
- **🔴 C-QUAL-01 模板修正（v1.23.1）**：`Template_Constraints.yaml` 中 Node/vitest 项目的 check 不再写 `--coverage-reporter=json-summary`（vitest v2 不识别连字符写法）。正确写法为 `npx vitest run --coverage`，覆盖率阈值与 json-summary 在 `vitest.config` 的 `test.coverage` 配置；点号写法 `--coverage.reporter=json-summary` 亦可。否则命令报错会导致 C-QUAL-01 门禁**误判失败**。
- **🔴 既有项目 Recon（v1.25.0）**：既有项目应先只读 Recon，再生成 Intent Graph、约束和契约。Recon 必须区分 Baseline / Preserve / Unknown / Change Envelope，不得把推测伪装成事实或覆盖未跟踪用户文件。
- **🔴 风险驱动裁剪（v1.25.0）**：治理可依据证据自动升级；信息不足不得推荐低风险模式，高风险治理不得由 Agent 自动降级。Python TDD 门支持自动识别 pytest 或标准库 unittest 的真实 RED/GREEN。

## 🔴 强制检查门（v1.18 新增，v1.20 重构）

> 以下检查门是硬性流程节点，对应 SCOPE-V 的不同阶段。**每个门由 `gate_check.py` 机械验证，不可自报通过。**

```
SCOPE-V:  Specify → Constrain → Orchestrate → Prove → Evolve → Verify → Telemetry
检查门:                        前置门        编码门    验证门              收尾门
         gate_check.py --gate pre  --gate coding  --gate prove     --gate closing
```

### 前置门（Orchestrate 前 — SDD 完成，编码开始前必须通过）

```bash
python scripts/gate_check.py --gate pre --task T-XXX --project-dir .
# 机械检查: 契约文件存在 + 已显式签署（IO 真实署名，非 OA 代签） + 约束矩阵存在 + AC shell:grep ≤50%
```

### 编码门（Orchestrate 开始时 — TDD Red，写实现前必须通过）

```bash
python scripts/gate_check.py --gate coding --task T-XXX --project-dir .
# 机械检查: 测试文件存在 + vitest 运行有 RED（测试存在但未全绿 = 实现未写完）
```

### 验证门（Prove 阶段 — TDD Green，标记 Verify 前必须通过）

```bash
python scripts/gate_check.py --gate prove --task T-XXX --project-dir .
# 机械检查: vitest 全绿 + test-total>0 + 证据包含 AC 结果 + tsc 编译通过
```

### 收尾门（标记"已完成"前必须通过 — 证据与度量）

```bash
python scripts/gate_check.py --gate closing --task T-XXX --project-dir .
# 机械检查: 证据包存在 + 单任务遥测文件存在 + runs 含本任务 + dashboard 1小时内更新 + 图谱含本任务
# 遥测采集: bash scripts/quick_telemetry.sh T-XXX ./governance
```

### Bug 回溯门（v1.20 — 任务"已完成"后发现 bug 时触发）

```bash
python scripts/gate_check.py --gate bug --task T-XXX --project-dir .
# 机械检查: 证据包含 bug 记录 + 遥测 first_pass=0 + 图谱含 bug 教训
```

## 多人多模块协作：端到端使用流程

> **何时需要**: 项目 ≥2 个模块、或 ≥2 个人、或 ≥2 种 AI 工具。
> **何时不需要**: 单人单模块 — 忽略此章节，直接按 §1-10 操作。

详细流程（全局 OA 初始化 → 模块 OA 启动 → 并行开发 → 集成测试 → 证据聚合与发布裁决）见 **[references/multi_module.md](references/multi_module.md)**。

## 参考资料

- 《Agentic Agile智能体敏捷：从氛围编程到验证工程的AI研发治理指南》v1.6，王立杰 (c) 2026 CC BY 4.0
- 实战验证项目：费用报销规则引擎（Intent_Contract.md + Constraint_Matrix.md + Evidence_Bundle.md）

## 关于作者

**王立杰，AI治理架构师，资深研发效能顾问**，工信部研发效能工程师认证专家讲师、PMI-ACP授权讲师、企业级规模化敏捷SAFe认证咨询师(SPC6)，曾任京东首席敏捷创新教练、IBM客户技术专家、DNV高级咨询师等，帮助小米IT信息部、OPPO内容产品中心、海康威视、京东方CTIO、吉利亿咖通、晓羊教育集团、中远海运租赁、京东购物APP、京东到家、招商银行、工商银行等组织实现研发效能提效。畅销书《敏捷无敌》、《京东敏捷实践指南》作者，江湖人称"**无敌哥**"。

### 教授经典课程

- **《Agentic Agile/智能体敏捷：AI时代研发治理沙盘实战课》**
- **《Agentic AI 项目管理：企业项目管理的人机协同新范式》**
- **《AI时代研发治理与领导力：从"驭人"到"驭智"高管研修班》**
- 《OpenClaw 创想家：从创意到产品的沉浸式工作坊》
- 《乌托邦计划沙盘：跨部门协同与高效项目管理特训营》
- 《敏捷项目管理实战沙盘演练》
- 《DevOps黑客马拉松》
- 《创新设计思维Design Thinking》
- 北大光华管理学院/新华都商学院《创业机会分析与识别》
- 京东大学《京东创新之路》、《从0到1商业模式快速探索》

曾经提供培训与咨询的企业包括宝马、博世、吉利、上汽、广汽传祺等车企，百度、京东、小米、Oppo、微博、360、58同城、美团等互联网企业，中国移动、联通、Agilent、IBM、阿朗、爱立信、诺基亚、东软、华为等传统电信/IT/软件企业，招商银行、工商银行、中信银行、中国银行、山东城商行等金融企业，E人E本、长虹、海尔、美的等白电企业，海天建筑、同方威视、中大医疗等传统行业；曾经在"AgileChina敏捷中国、RSG、51CTO、MPD、质量竞争力大会/TiD"等大会做过多次演讲，被评为质量竞争力大会/TiD 2014最受欢迎10大讲师；**目前专注于企业AI组织转型、研发效能提升、企业产品创新。**

### 联系无敌哥

- 官网：http://agentic.iloveagile.me/about
- 微信：iloveagile
- Email：3433839@qq.com
