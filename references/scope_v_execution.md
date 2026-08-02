# SCOPE-V 执行循环（SDD + TDD 内嵌）

> 本文是 SKILL.md §2 的详细参考，按需加载。

## SCOPE-V 循环图

```
         SDD 规约驱动                     TDD 测试驱动
    ┌─────────────────────┐    ┌──────────────────────────┐
    │                     │    │                          │
Specify → Constrain → Orchestrate → Prove → Evolve → Verify
   │          │            │           │         │         │
   ▼          ▼            ▼           ▼         ▼         ▼
意图契约   约束矩阵   Red:写失败测试  Green:最小实现  Refactor  全部门禁
(IO签署)  (OA维护)   → AC→测试骨架  → 代码使测试通过 → 重构+反思  (Verify)
   │                     │           │         │         │
   │                     │           │         └─ 修复+重跑│
   │                     └─ SDD ────→│            Evidence_Bundle.md
   │                                │              (呼叫 HITL)
   └─ Spec 定义 AC ────────────────→│
                        verify_contract.py 事后验证
```

**SDD（规约驱动）**：Specify 阶段产出的意图契约就是 Spec。AC（验收标准）不是事后检查清单，而是驱动实现的**可执行规约**。`verify_contract.py --generate-tests` 从 AC 自动生成测试骨架，AS 的工作是让这些测试通过。

**TDD（测试驱动）**：Orchestrate→Prove→Evolve 三步构成完整的 Red-Green-Refactor 循环：
- **Red**：从契约 AC 生成测试 → 运行 → 全部失败（证明测试有效）
- **Green**：AS 编写最小实现使测试通过
- **Refactor**：Evolve 阶段重构代码 + 反思 + 反哺图谱

## 🔵 微检查点（Karpathy 规则10）

Orchestrate 完成后、Prove 开始前，AS 必须向 OA 报告：
1. 我理解的目标是什么（用自己的话复述）
2. 我会修改哪些文件
3. 我不会碰哪些文件/模块
4. 我识别到哪些潜在风险

OA 确认无误后 AS 才能开始写代码。这个检查点只需 30 秒，但能避免 80% 的方向性错误。

> ⚠️ **为什么不做更多**：不引入 BDD/Gherkin 层、不自动生成 Mock/Fixture、不做测试优先级排序。当前模型已经足够理解 AC 语义，过度框架化反而降低效率（superpowers 教训）。

## 🔴 Verify 后强制遥测（v1.12 硬性规则）

> **每个意图契约（Intent_Contract_T-XXX）完成 Verify 阶段后，OA/AS 必须立即主动运行一次 `collect_telemetry.py` 采集遥测，并在对话中给出结果摘要，才能标记该任务为"已完成"。**

这是 SCOPE-V 的**第六步**——从五步循环扩展为「Specify → Constrain → Orchestrate → Prove → Evolve → Verify → **Telemetry**」：

```
Specify → Constrain → Orchestrate → Prove → Evolve → Verify → 🔴 Telemetry
                                                          │         │
                                                          │         └─ collect_telemetry.py
                                                          │            + 结果摘要给 IO
                                                          └─ verify_contract.py
```

**为什么强制**：
- 遥测不是"可选的运营动作"，而是**判断 AI 是否真的在变好的唯一证据**
- 跳过遥测 = 价值层/能力层指标停在基线 = 无法回答"这套治理架构到底有没有用"
- 逐任务采集才能形成时间序列，发现退化趋势（如首次成功率连续下降）

### 最小采集参数

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
