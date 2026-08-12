# SCOPE-V 六控制面运行模型（SDD + TDD 内嵌）

> 本文是 SKILL.md §2 的详细参考，按需加载。

## 六个持续控制面

```
S / C / O / P⇄E / V
        │       │
        └─ 证据驱动快内环

V → Telemetry → S/C/O
        运行反馈慢外环
```

SCOPE-V 不是要求任务只向前走一次的流程，而是六个持续控制面：

| 控制面 | 控制问题 | 主要证据 |
|---|---|---|
| Specify | 要实现什么、为什么、怎样验收？ | 意图、目标、非目标、AC、责任边界 |
| Constrain | 哪些边界不可越过？ | 约束、权限、风险、围栏与人工决策点 |
| Orchestrate | 怎样组织上下文、任务、工具和执行顺序？ | 工作路径、工具权限、真实 TDD Red |
| Prove | 当前结果由什么证据支持？ | 测试、AC、约束和必要验证层 |
| Evolve | 失败和偏差怎样被修正？ | 最小修正、重跑、反思和规则债处理 |
| Verify | 证据是否足以形成当前裁决？ | 完整性、独立性、时效、责任与 Unknown |

**SDD（规约驱动）**：Specify 产出的意图契约就是 Spec。AC 不是事后检查清单，而是驱动实现的**可执行规约**。`verify_contract.py --generate-tests` 从 AC 自动生成测试骨架，AS 的工作是让这些测试通过。

**TDD（测试驱动）**：Orchestrate 与 `P⇄E` 快内环承载 Red-Green-Refactor：
- **Red**：从契约 AC 生成测试 → 运行 → 全部失败（证明测试有效）
- **Green**：AS 编写最小实现使测试通过
- **Refactor**：Evolve 根据证据重构代码、测试或规则，然后回到 Prove；证据不足不得进入 Verify

三大自治运行机制横跨六个控制面：上下文自治控制每个控制面的可信输入，执行自治负责编排、恢复和停止，进化自治在证据与责任边界内将教训回流。它们不是与 S、C、O、P、E、V 一一对应的流程阶段。

## 🔵 微检查点（Karpathy 规则10）

Orchestrate 完成后、Prove 开始前，AS 必须向 OA 报告：
1. 我理解的目标是什么（用自己的话复述）
2. 我会修改哪些文件
3. 我不会碰哪些文件/模块
4. 我识别到哪些潜在风险

OA 确认无误后 AS 才能开始写代码。这个检查点只需 30 秒，但能避免 80% 的方向性错误。

> ⚠️ **为什么不做更多**：不引入 BDD/Gherkin 层、不自动生成 Mock/Fixture、不做测试优先级排序。当前模型已经足够理解 AC 语义，过度框架化反而降低效率（superpowers 教训）。

## 🔴 Evidence 完成后进入 Telemetry 慢外环（v1.36.2）

> **每个意图契约（Intent_Contract_T-XXX）形成完整 Evidence Bundle 后，推荐完成入口是 `cli.py change verify`。它先执行 Prove gate；通过后由工作流代码自动调用 `cli.py evidence finalize`，从契约、Evidence 与事件账本派生可信指标并生成双 Dashboard。任一步失败都必须 BLOCKED，成功后才能标记该任务为“已完成”。**

Telemetry 是 Verify 后的强制反馈证据，但不属于六控制面。它通过慢外环把运行事实送回后续控制：

```
V → Telemetry → S/C/O
       │          ├─ 修订后续意图或 AC
       │          ├─ 升级约束、风险与权限边界
       │          └─ 调整上下文、工作图、工具和验证编排
       └─ change verify → prove gate → evidence finalize → telemetry_workflow.py → collect_telemetry.py + 结果摘要给 IO
```

**为什么强制**：
- 遥测不是"可选的运营动作"，而是**判断 AI 是否真的在变好的唯一证据**
- 跳过遥测 = 价值层/能力层指标停在基线 = 无法回答"这套治理架构到底有没有用"
- 逐任务采集才能形成时间序列，发现退化趋势（如首次成功率连续下降）
- 强制采集只证明反馈已捕获，不表示 Agent 可以自行改写已签署意图、约束或发布决定

### 自动收口入口（推荐）

```bash
python scripts/cli.py change verify --task T-0XX --project-dir .
```

入口先确认 Prove gate 通过；随后自动确认契约、Evidence 任务归属、AC 结果和约束结果，再复用现有一键遥测。它不修改 Evidence、不代签或批准；失败时返回非零，任务保持未完成。以下直接采集命令保留为底层接口和故障诊断手段。

```bash
python scripts/cli.py evidence finalize --task T-0XX --project-dir .
```

### 底层最小采集参数

每任务必填，**必须带 `--task`**：

```bash
# v1.13 双轨遥测：单次契约 + 项目累积
# v1.14+：传入 --project 后，G0-G8 门禁与测试计数由 harness 从 constraints.yaml 自动派生；
#       --gates-passed / --must-* / --test-* 仅作 harness 不可用时的降级覆盖（可不填）。
python3 scripts/collect_telemetry.py \
    --project "<项目名>" \
    --task T-0XX \
    --tasks-assigned 1 --tasks-completed 1 --tasks-first-pass 1 \
    --hitl-count <HITL 次数> \
    --token-usage <本任务 token> \
    --execution-rounds <执行轮次> \
    --new-patterns <新模式数> \
    --total-patterns <累积模式数> \
    --auto-healed <自愈次数> \
    --constraint-failures-total <约束失败总数> \
    --output governance/telemetry.json
```

### 落盘结果（v1.13）

| 文件 | 含义 |
|------|------|
| `governance/telemetry/runs/telemetry-T-0XX.json` | **单次意图契约**遥测（scope=contract） |
| `governance/telemetry.json` | **项目累积** + `runs[]` 历史索引（scope=project） |
| `governance/dashboard.html` | 大屏：总览 ⇄ 单次 双向跳转 |
| `governance/dashboard-T-0XX.html` | **单次意图契约** Dashboard |

- 总遥测 → 单次：`dashboard.html` 索引表，或 `dashboard.html?task=T-0XX`
- 单次 → 总遥测：单次页导航「返回项目总遥测」

### 结果摘要必须包含

OA 在对话中向 IO 汇报：

| 指标 | 健康阈值 | 本次 |
|------|----------|------|
| 目标准确率 | ≥80% L3 | XX% |
| 首次成功率 | 影响 50% 成本 | XX% |
| 自主性评分 | ≥60 L2 | XX |
| MUST 通过率 | 100% | XX% |
| 知识沉淀率 | ≥5% 稳步 | XX% |

### 跳过遥测的后果

任务不得标记为"已完成"；证据包裁决不得为 APPROVED；下一任务的契约不得签署。这条规则由 `verify_freshness.py` 在下次检查时强制（已完成任务需有对应 telemetry 记录）。
