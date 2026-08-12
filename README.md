# Agentic Agile 3-4-3 治理架构 · 开源版 v1.42.0

> **让AI交付可治理、可追溯、可验证。** 这是一套 Agentic AI 研发的**完整、可运行治理框架**——从意图契约到证据闭环、从约束门禁到遥测仪表板，全部开源，开箱即用。让 AI 研发治理，进可攻退可守。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Whitepaper: CC BY 4.0](https://img.shields.io/badge/Whitepaper-CC%20BY%204.0-green.svg)](docs/whitepaper/)

- 📘 方法论白皮书：[`docs/whitepaper/`](docs/whitepaper/)（CC BY 4.0，保留署名可自由传播）
- 🌐 官网：<http://agentic.iloveagile.me/>
- 📦 GitHub 仓库：<https://github.com/elegant1998/Agentic-Agile-343.git>（手动安装：`git clone https://github.com/elegant1998/Agentic-Agile-343.git`）
- ✍️ 作者：王立杰（无敌哥），AI 治理架构师
- 🤝 贡献指南：[`CONTRIBUTING.md`](CONTRIBUTING.md)（[English](CONTRIBUTING.en.md)）· 📦 发布说明：[`RELEASE_NOTES.md`](RELEASE_NOTES.md)（[English](RELEASE_NOTES.en.md)）· 🌐 [English README](README.en.md)

---

## 一、为什么需要它

2024 年以来的自治智能体（Agentic AI）击穿了传统敏捷的生理物理边界，但也带来了新问题：**模糊的规格说明书 + 聪明的模型 = 更高级的逻辑偏离**。正如业界洞察所言——*"这根本不是模型能力的问题，而是流程控制体系的问题。"*

从随性的 **Vibe Coding（氛围编程）** 走向严格的 **Verified Engineering（经过验证的严肃系统工程）**，需要一套以意图为中心、以多智能体高频对抗为引擎、以算力为基础的新治理架构。这就是 **Agentic Agile 3-4-3**。

## 二、3-4-3 治理架构速览

- **3 个超级角色**：意图主理人（IO，定方向）、编排架构师（OA，管机器与边界）、自治蜂群（AS，确定性执行体）。
- **4 个动态工件**：意图图谱、意图契约、约束矩阵、算力与价值遥测。
- **3 大自治机制**：意图注入（对话到契约门）、高频对抗自净化闭环、人类异常裁决（HITL + 证据包验收）。
- **SCOPE-V 六个持续控制面**：`S / C / O / P⇄E / V`；Prove 与 Evolve 构成快内环，`V → Telemetry → S/C/O` 构成慢反馈外环。
- **三大自治机制横切运行**：上下文自治、执行自治、进化自治横跨控制面，不与某一个阶段机械绑定。
- **大仓库与长期历史可扩展**：Map-first Recon 使用有界 Provider 查询；无地图时单次有界回退，事件与项目遥测使用可重建索引和稳定摘要。

更完整的理论基石（认知科学 / 控制论 / 系统论）、Agentic Agile 宣言、成熟度模型（L1–L4）、落地路线图，见 [`docs/whitepaper/`](docs/whitepaper/)。

## 三、本版包含什么（全部开源，无保留）

本仓库即完整版，不再区分社区版/完整版：

| 能力 | 关键资产 |
|---|---|
| 意图契约 / 约束矩阵 / 证据包 / 意图图谱 / Recon / 风险模式 | `templates/` 18 个模板（MD + YAML 双格式） |
| 机械门禁（5 道门，退出码硬拦截） | `scripts/gate_check.py` |
| 约束执行引擎（G0–G8 + 7 个 NFR 验证器） | `scripts/harness.py` |
| 契约 AC 逐条验证 | `scripts/verify_contract.py` |
| 风险驱动多层验证 / 证据独立性 / 无效全绿 | `scripts/verification_plan.py`、`Template_Verification_Plan.yaml` |
| 单项目携证发布 / 制品证据绑定 / 发布回滚事实 | `scripts/release_manifest.py`、`Template_Release_Manifest.yaml` |
| 证据包审计 | `scripts/audit_evidence.py` |
| 三方一致性 / 回滚安全 / 时效 / 跨模块 | `scripts/verify_*.py` |
| 上下文工程三层注入 + L0-L3 双地图渐进增强 | `scripts/crop_context.py`、`scripts/context_providers.py` |
| 工作图 DAG 引擎 | `scripts/graph_engine.py` |
| 工具审计 | `scripts/audit_tools.py` |
| 遥测采集（4 层 9 维） + Token 实测 | `scripts/collect_telemetry.py`、`scripts/token_usage.py`、`fetch_token_usage.sh` |
| 跨平台可信遥测 + 仪表板 | `scripts/telemetry_workflow.py`、`scripts/telemetry_tracker.py`、`assets/dashboard.html` |
| Evidence 完成后自动遥测收口 + 双 Dashboard | `scripts/evidence_workflow.py` |
| 批判性思维 / Grill-Me / LOOP / Graph / 门禁维护 / Recon / 验证 / 发布 | `references/` 15 篇参考 |

### 自然语言入口（v1.36.2）

用户不需要记忆 CLI：已有项目、风险评估、门禁误报、影响分析、变更围栏、Preserve、安全修改、Bug 修复，以及“不要只跑单测、检查证据是否同源”等表达都会路由到最小必要能力。详见 [`references/natural_language_routing.md`](references/natural_language_routing.md)。

“准备发布”“生成发布清单”“检查制品和证据是否一致”“记录已发布/回滚”会进入单项目 Release Manifest；自然语言请求不等于发布授权。

### 单项目携证发布（v1.32.0）

```bash
python scripts/cli.py release plan --task T-001 --version 1.2.3 --artifact dist/app.tar.gz --project-dir .
python scripts/cli.py release check --manifest governance/releases/Release_Manifest_1.2.3.yaml --project-dir .
```

plan 默认 dry-run，实测 Git commit、工作树、制品 SHA-256/大小、配置与任务证据；apply 只创建 DRAFT。AUTHORIZED 清单满足条件时只输出 `READY_FOR_HUMAN_RELEASE`，不会创建 Tag、push、构建或部署。`record` 只追加人类或外部系统已执行的 released/rolled_back 事实。详见 [`references/release_manifest.md`](references/release_manifest.md)。

### 风险驱动多层验证（v1.31.0）

```bash
python scripts/cli.py verification plan --task T-001 --project-dir .
python scripts/cli.py verification plan --task T-001 --project-dir . --risk high --trace AC-001 --apply
python scripts/cli.py verification check --task T-001 --project-dir .
```

计划默认 dry-run，apply 只创建 DRAFT 且不覆盖。IO 授权后的正式计划自动接入 prove 门；缺层、同源伪装、独立性不足、过期/错任务证据、LLM 独证或 AI 代签 HUMAN_ACCEPTANCE 都不能形成 PASS。详见 [`references/verification_planning.md`](references/verification_planning.md)。

### 风险驱动初始化（v1.26.0）

```bash
python scripts/cli.py init --project-dir .          # 默认 dry-run
python scripts/cli.py init --project-dir . --apply  # IO 确认后落盘
```

入口识别四类项目、评估七域风险并选择五种治理模式之一。既有项目自动执行只读 Recon；Unknown 不会触发风险降级，已有文件不覆盖，生成契约保持 PENDING。

### 门禁自身治理（v1.26.1）

```bash
python scripts/cli.py maintain open --id M-001 --task T-128 --project-dir .
python scripts/cli.py maintain check --id M-001 --project-dir .
python scripts/cli.py maintain close --id M-001 --project-dir .
```

确定性的低风险门禁误报使用 `M-XXX` 维护记录，不再反复创建业务补充契约。Unknown、门禁弱化、签署语义或权限边界变化一律升级为 IO 签署的 Amendment；详见 [`references/maintenance_channel.md`](references/maintenance_channel.md)。

### 任务级 Recon（v1.27.0）

```bash
python scripts/cli.py recon task --task T-001 --target src/example.py --project-dir .
```

围绕具体修改目标，只读发现直接依赖、引用/测试/公共入口候选，并将 Fact、Candidate、Unknown 分层输出。覆盖 Python、JavaScript/TypeScript、C/C++、Java/JSP，基础支持 Go、Rust、Shell；建议 Change Envelope 不自动获得授权效力。详见 [`references/task_recon.md`](references/task_recon.md)。

### 双地图增强 Recon（v1.37.0）

IWE 推荐负责 Document Map（需求、规则、AC、ADR、历史决策），codebase-memory-mcp 推荐负责 Code Map（模块、符号、调用、路由、测试），343 用统一 ID 维护 Trace Link。两者均为可选能力：无外部工具时保持 L0；仅 Code Map 为 L1，仅 Document Map 为 L2，双地图为 L3。支持 Agent-native MCP 与项目内显式 JSON/YAML 制品，失败或过期时记录 Unknown 并安全回退；不会自动安装、配置、联网、回写知识库或扩大 Change Envelope。

v1.40.0 补齐原生索引到标准地图工件、再到 Agent Prompt 的链路。`crop_context.py` 默认注入受预算限制的 Map Context；单地图继续增强，无地图使用契约、约束和内建扫描。团队项目建议由 CI 生成 `authority: ci` 的确定性快照，本地使用 `recon.py --map-mode team` 只消费校验，缺失时仅生成 `.local` 回退，避免覆盖共享地图。过期、损坏和查询失败会披露影响与恢复建议，而不是静默 Unknown。

正式围栏经 IO 确认为 `AUTHORIZED` 后，可执行 `python scripts/cli.py envelope check --task T-001 --project-dir .`，机械检查全部 Git 变更；存在正式围栏时 prove 门自动执行，越界或 Unknown 直接阻断。

缺少可靠测试时，使用 `cli.py characterize plan/capture/verify` 固定 IO 确认的 Preserve 行为；CAPTURED 基线会在 prove 门自动复验。

使用 `cli.py change plan/status/prepare/verify/close` 可统一编排上述既有代码安全变更流程，状态始终从当前证据重算。

用户直接说“这是一个 Bug：……请修复”即可触发候选调查，无需提供 B/T 编号或手工运行命令。Agent 自动寻找父任务和分配 B-ID；证据无法唯一关联时只追问一个关键问题，且不会因为用户使用了“Bug”一词就跳过分类。

内部流程使用 `cli.py bug open/classify/reproduce/status/verify/telemetry/close`；实现回归、规格变化、门禁缺陷和无法复现问题使用不同治理路由。父契约不因完成而改写；完成态由证据包、原任务遥测与意图图谱证明。验证通过后以 `bug telemetry --test-total N --test-passed N` 单独记录修正运行，再关闭 Bug；原任务遥测保持历史原貌。
| 证书申请（AASC） | `scripts/certificate.py` |

## 四、快速开始

### 1. 准备 Python 环境

```bash
# Bash 不是必需项；入口命令可直接用当前 Python 启动
python scripts/cli.py list
```

缺少 PyYAML 时，YAML 消费脚本会通过 Python 原生 `_bootstrap.py` 创建/复用
`~/.agentic-agile-343/venv` 并安装依赖；Windows、macOS、Linux 使用同一实现。

### 2. 初始化项目治理（单人）

```bash
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml
```

### 3. 按 SCOPE-V 六控制面执行

```
Specify  → 填意图契约 → Grill-Me 决策确认 → IO 显式签署（OA 不得代签）
Constrain → 填约束矩阵（六域，先列 MUST）
Orchestrate → TDD 红→绿→重构；每任务先写失败测试
Prove ⇄ Evolve → 证据不足就修正并重新证明
Verify  → 依据证据形成裁决
V → Telemetry → S/C/O → 将反馈回流到后续意图、约束或编排
```

### 4. 机械门禁（5 道门，硬拦截）

```bash
# 前置门（编码前：契约已显式签署 + 约束矩阵 + AC shell:grep ≤50%）
python scripts/gate_check.py --gate pre --task T-001 --project-dir .

# 编码门（TDD Red：测试已先写且运行 RED）
python scripts/gate_check.py --gate coding --task T-001 --project-dir .

# 验证门（TDD Green：测试全绿 + AC 通过 + tsc 编译）
python scripts/gate_check.py --gate prove --task T-001 --project-dir .

# 收尾门（证据包 + 单任务遥测 + 图谱回写）
python scripts/gate_check.py --gate closing --task T-001 --project-dir .

# Bug 回溯门（已完成任务发现 bug 时）
python scripts/gate_check.py --gate bug --task T-001 --project-dir .

# 契约 AC 校验
python scripts/verify_contract.py --task T-001 --project-dir .

# 约束检查
python scripts/harness.py check --all

# 推荐完成入口：Prove 通过后自动执行 Evidence/Telemetry/Dashboard 收口
python scripts/cli.py change verify --task T-001 --project-dir .

# 底层诊断/补跑入口
python scripts/cli.py evidence finalize --task T-001 --project-dir .
```

### 5. 一个填好的示例

见 [`examples/Intent_Contract_T-001.example.yaml`](examples/Intent_Contract_T-001.example.yaml)——把模板字段填上了一个最小可运行任务，照着改即可。

## 五、批判性思维（跨项目通用）

AI 默认盲从用户的字面指令（IO）。本框架要求 OA 在 Specify / Constrain 阶段**先校准、再实现**——遇歧义、激励过密、与北极星冲突、不可验证、安全过宽时，先挑战并给推荐默认，确认前不得实现。完整的 7 大可疑信号、Grill-Me 逐条确认协议、四类任务人机分工模型，见 [`references/critical_thinking.md`](references/critical_thinking.md)。

## 六、约束优先级链

```
法律/安全约束 > 约束矩阵 > 已签署意图契约 > 实现便利性
MUST（破坏即失败） > SHOULD（重要但可协商） > MAY（可选）
```

任何例外只能由人类 IO 通过签署的书面批准授予。

## 七、目录结构

```text
agentic-agile-343-community-ed/
├── SKILL.md                      # 技能入口（使用流程 + 全部硬性规则）
├── README.md                     # 本文件
├── LICENSE                       # MIT（代码）；白皮书见 docs/whitepaper，CC BY 4.0
├── requirements.txt              # Python 依赖（pyyaml，可选）
├── .gitignore
├── scripts/                      # 26 个可运行脚本（门禁/引擎/验证/Evidence 收口/遥测/上下文/图谱）
├── templates/                    # 13 个工件模板（MD + YAML 双格式）
├── references/                   # 15 篇参考文档（批判性思维/SCOPE-V/Harness/LOOP/Graph/自然语言路由/验证/发布…）
├── assets/
│   └── dashboard.html            # 遥测仪表板（纯静态，双击即看）
├── examples/
│   └── Intent_Contract_T-001.example.yaml
└── docs/
    └── whitepaper/               # 《Agentic Agile 智能体敏捷白皮书》（CC BY 4.0）
```

## 八、许可证

- **代码与模板**（`scripts/`、`templates/`、`SKILL.md` 等）：[MIT License](LICENSE)，可自由使用、修改、分发。
- **白皮书**（`docs/whitepaper/`）：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，转载、二次创作需注明来源（王立杰-无敌哥）。

## 九、关于作者与社区

**王立杰（无敌哥）**，AI 治理架构师、资深研发效能顾问；畅销书《敏捷无敌》《京东敏捷实践指南》作者。

- 官网：<http://agentic.iloveagile.me/about>
- 微信：`iloveagile` · Email：3433839@qq.com
- 在线课程：《Agentic Agile 3-4-3 快速入门：完成第一个可验证治理闭环》详见 http://agentic.iloveagile.me/
- 进阶线下课程：《Agentic Agile/智能体敏捷：AI 时代研发治理沙盘实战课》等（联系无敌哥）

> 认同理念？欢迎在官网签署《Agentic Agile 宣言》，加入先锋社区。
v1.38.0 起，项目 Recon 默认优先读取项目内标准双地图 artifact；工具已安装但地图缺失时，会在显式项目边界内初始化 IWE，并通过 codebase-memory-mcp 的 `index_repository --repo-path <PROJECT> --persistence true` 建立持久化 Code Map。双地图归一化后自动生成 Trace Link，证据不足时保持 Candidate/Unknown；`--no-auto-context` 可关闭初始化，失败自动回退 L0。
