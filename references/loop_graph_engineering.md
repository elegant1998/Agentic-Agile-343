# LOOP & Graph Engineering

## LOOP Engineering：自我纠错与持续进化

> **核心原则**：SCOPE-V 的 Evolve 不只是"修复失败的测试"，而是一个完整的**自我纠错→反思→进化**闭环。

### 三层 LOOP 模型

```
┌─────────────────────────────────────────────┐
│ LOOP-1: Self-Consistency（自洽性）           │
│ 触发: Orchestrate 完成后                     │
│ 检查: 产出物是否存在、端点数量是否达标、      │
│       测试是否可执行、前端路由是否注册        │
│ 动作: 不通过 → 自动重试（最多 3 次）          │
│ 工具: self_consistency_check.py              │
├─────────────────────────────────────────────┤
│ LOOP-2: Reflection（反思）                   │
│ 触发: Prove 完成后                           │
│ 内容: 什么做得好/什么问题/怎么改进/发现模式   │
│ 动作: 生成反思日志 → 指导下一次任务           │
│ 工具: reflect.py                             │
├─────────────────────────────────────────────┤
│ LOOP-3: Feedback→Graph（反哺）               │
│ 触发: HITL 签署后                            │
│ 内容: 教训、风险、模式 → 写入图谱历史上下文   │
│ 动作: 图谱持续进化，后续任务受益              │
│ 工具: reflect.py --feedback-to-graph         │
└─────────────────────────────────────────────┘
```

### LOOP 集成到 SCOPE-V

```
Orchestrate → [Self-Consistency] → Prove → [Test LOOP]
    │              │ 失败则重试                    │ 失败则修复
    │              └───────────────                │
    ▼                                              ▼
Evolve ←──────────────────────── [Reflection LOOP]
    │
    ▼
Verify → [Gate LOOP] → HITL → [Feedback→Graph LOOP]
```

### 用法

```bash
# 自洽性检查（任务完成后自动运行）
python scripts/self_consistency_check.py --task T-005 --max-retries 3

# 生成反思
python scripts/reflect.py --task T-003 \
    --test-passed 51 --coverage 94.01 --hitl-count 1 \
    --issues "prompt 过长" \
    --patterns "router/schemas/service 三层结构"

# 反哺图谱
python scripts/reflect.py --task T-003 --task-desc "会员中心 MVP" \
    --feedback-to-graph
```

### 图谱反哺效果

任务完成后，意图图谱 §5 自动追加：

```
| HX-T-003 | 会员中心 MVP | 2025-07-21 | 教训: 使用 crop_context.py | 风险: prompt过长 | 模式: 三层架构 |
| HX-T-004 | 美食域 MVP   | 2025-07-21 | 教训: 保持当前流程 | 风险: HTTP调用失败 | 模式: 溯源保护 |
| HX-T-005 | 居住域 MVP   | 2025-07-21 | 教训: 启用自洽性检查 | 风险: 文件未落地 | 模式: 场景联动 |
```

> **HX 编号约定**：`reflect.py` 自动生成 `HX-T-XXX` 格式（与任务 ID 对齐）；手工维护时也可用顺序编号（HX-01、HX-02）。两种格式可共存，解析工具均按 `| HX-` 前缀识别。同一任务的反哺条目建议只保留一条（最新覆盖最旧）。

**意图图谱真正"活"了**——每次任务的经验教训自动沉淀为下一次任务的知识。

---

## Graph Engineering：可编程的 Agent 组织架构

> **核心原则**：复杂任务不应靠 OA 在脑子里管理依赖关系，而应**显式定义为有向无环图（DAG）**——让多 Agent 协作变得可编程。

### 两层图模型

```
┌─────────────────────────────────────────┐
│ 组织图（Org Graph）— 长期稳定             │
│ IO ──签署──→ OA ──裁剪──→ AS             │
│ AS ──HITL──→ IO（越权/失败/异常）         │
├─────────────────────────────────────────┤
│ 工作图（Work Graph）— 动态生成             │
│ T-002 → T-003 ──┬──→ T-004 ──┐          │
│                  │            │          │
│                  └──→ T-005 ──┤          │
│                               ▼          │
│                           Evolve → Verify│
└─────────────────────────────────────────┘
```

### DAG 定义 (work_graph.yaml)

```yaml
nodes:
  T-003:
    depends_on: [T-002]
    parallel_group: domain_mvp  # ← 关键：标记可并行

  T-004:
    depends_on: [T-003]
    parallel_group: domain_mvp  # ← 与 T-005 无相互依赖，可并行

  T-005:
    depends_on: [T-003]
    parallel_group: domain_mvp

parallel_strategy:
  domain_mvp:
    max_parallel: 2  # 资源限制
```

### Graph Engine 用法

```bash
# 查看执行计划（拓扑排序 + 并行度分析）
python scripts/graph_engine.py plan

# 当前进度
python scripts/graph_engine.py status

# 瓶颈分析（被依赖最多的节点）
python scripts/graph_engine.py bottlenecks

# 可并行节点
python scripts/graph_engine.py parallel

# 关键路径
python scripts/graph_engine.py critical-path
```

### 实际输出

```
🗺️ 工作图执行顺序:
  阶段 0: ⚡ 并行组
    [T-003] 会员中心 MVP 🔥关键路径
    [T-004] 美食域 MVP   🔥关键路径  ← 与 T-005 可并行
    [T-005] 居住域 MVP               ← 与 T-004 可并行

🔍 瓶颈: T-003 被 3 个节点依赖（会员中心是整个系统的枢纽）
📐 关键路径: T-001 → T-002 → T-003 → T-004 → Evolve → Verify
```

### Graph × LOOP 协作

```
Graph: 定义"谁在什么时候做什么"
LOOP:  保证"做错了能自我纠正"
Harness: 保证"不做不该做的事"
Context: 保证"只看到该看到的信息"
```

四个工程维度形成完整的 Agent 治理闭环。
