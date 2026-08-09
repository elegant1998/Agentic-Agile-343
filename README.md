# Agentic Agile 3-4-3 治理架构 · 开源版 v1.25.0

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
- **SCOPE-V 工程控制循环**：`Specify → Constrain → Orchestrate → Prove → Evolve → Verify → Telemetry`。

更完整的理论基石（认知科学 / 控制论 / 系统论）、Agentic Agile 宣言、成熟度模型（L1–L4）、落地路线图，见 [`docs/whitepaper/`](docs/whitepaper/)。

## 三、本版包含什么（全部开源，无保留）

本仓库即完整版，不再区分社区版/完整版：

| 能力 | 关键资产 |
|---|---|
| 意图契约 / 约束矩阵 / 证据包 / 意图图谱 / Recon / 风险模式 | `templates/` 16 个模板（MD + YAML 双格式） |
| 机械门禁（5 道门，退出码硬拦截） | `scripts/gate_check.py` |
| 约束执行引擎（G0–G8 + 7 个 NFR 验证器） | `scripts/harness.py` |
| 契约 AC 逐条验证 | `scripts/verify_contract.py` |
| 证据包审计 | `scripts/audit_evidence.py` |
| 三方一致性 / 回滚安全 / 时效 / 跨模块 | `scripts/verify_*.py` |
| 上下文工程三层注入 | `scripts/crop_context.py` |
| 工作图 DAG 引擎 | `scripts/graph_engine.py` |
| 工具审计 | `scripts/audit_tools.py` |
| 遥测采集（4 层 9 维） + Token 实测 | `scripts/collect_telemetry.py`、`fetch_token_usage.sh` |
| 一键遥测 + 仪表板 | `scripts/quick_telemetry.sh`、`assets/dashboard.html` |
| 批判性思维 / Grill-Me / LOOP / Graph 工程 | `references/` 10 篇参考 |

### 既有项目先 Recon（v1.25.0）

```bash
python scripts/cli.py recon --project-dir .
python scripts/cli.py assess-risk --project-dir .
```

Recon 默认只读，先输出 Baseline、Preserve、Unknown 与 Change Envelope，再生成最小治理工件。风险信息不足时不会自动降级为探索模式。
| 证书申请（AASC） | `scripts/certificate.py` |

## 四、快速开始

### 1. 准备 Python 环境

```bash
# 首次运行自动建 venv 并安装 pyyaml（缺失时降级为 MD-only 模式）
bash scripts/ensure_py_env.sh
```

### 2. 初始化项目治理（单人）

```bash
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml
```

### 3. 按 SCOPE-V 循环执行

```
Specify  → 填意图契约 → Grill-Me 决策确认 → IO 显式签署（OA 不得代签）
Constrain → 填约束矩阵（六域，先列 MUST）
Orchestrate → TDD 红→绿→重构；每任务先写失败测试
Prove    → 跑测试至全绿 + AC 逐条验证
Evolve / Verify / Telemetry → 证据包 + 遥测 + 图谱回写
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

# 一键遥测
bash scripts/quick_telemetry.sh T-001 ./governance
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
├── scripts/                      # 25 个可运行脚本（门禁/引擎/验证/遥测/上下文/图谱）
├── templates/                    # 13 个工件模板（MD + YAML 双格式）
├── references/                   # 10 篇参考文档（批判性思维/SCOPE-V/Harness/LOOP/Graph/遥测…）
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
