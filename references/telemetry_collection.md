# 遥测采集与大屏（4 层 9 维模型）

> 本文是 SKILL.md §3+§4 的详细参考，按需加载。

## 📅 采集时机（v1.12 硬性）

| 时机 | 必采 | 说明 |
|------|------|------|
| **每个意图契约 Verify 完成后** | 🔴 必采 | 见 SCOPE-V「Verify 后强制遥测」——逐任务形成时间序列 |
| 每个 SCOPE-V 周期结束 | ✅ 必采 | 周期级汇总 |
| 跨模块集成测试通过后 | ✅ 必采 | 用 `--merge` 合并各模块 |
| 发布裁决前 | ✅ 必采 | 作为 RELEASE_Evidence_Bundle 的输入 |
| 每周/每两周固定节奏 | ✅ 推荐 | 周期性 dashboard 刷新 |

> 跳过逐任务遥测的任务，不得标记为"已完成"（见禁止事项）。

## 完整采集命令

```bash
python scripts/collect_telemetry.py \
    --project "my-project" \
    # ── 兼容性参数（v1.15+：项目采集时门禁/测试由 harness 自动派生，可不填；
    #     harness 不可用时逐条门禁标记为「未评估」，手动计数仅作展示降级）──
    --test-total 42 --test-passed 42 \
    --coverage-pct 93.0 --coverage-threshold 90.0 \
    --bench-p95 0.0067 --bench-threshold 2.0 \
    --token-usage 45000 --execution-rounds 6 --hitl-count 2 \
    --gates-passed 5 --must-constraints 20 --must-failed 0 \
    # ── 价值层（P0）──
    --tasks-assigned 10 --tasks-completed 9 --tasks-first-pass 7 \
    # ── 能力层（P0）──
    --auto-healed 3 --constraint-failures-total 5 \
    # ── ROI 参数（P1）──
    --human-hourly-rate 500 --hours-saved-per-task 2.0 \
    --ai-monthly-cost 50000 \
    # ── 效率层（P1）──
    --context-input-tokens 8000 --context-output-tokens 1500 \
    # ── 进化层（P1）──
    --new-patterns 3 --total-patterns 12 \
    --output telemetry.json
```

## 遥测 2.0：4 层 9 维指标体系

```
Layer 1 — 价值层（回答"AI 创造多少价值"）
  ├─ 🎯 目标准确率（Goal Accuracy）         ← P0
  ├─ ✨ 首次成功率（First-Pass Rate）       ← P0
  └─ 💵 复合 ROI（含失败折现）              ← P1

Layer 2 — 能力层（回答"Agent 有多自主"）
  ├─ 🔧 约束自愈率（Auto-Heal Rate）        ← P0
  ├─ 🤖 自主性综合评分（Autonomy Score）    ← P0
  ├─ 🔔 HITL 升级率                        ← 已有
  └─ 🛡️ MUST 约束通过率                    ← 已有

Layer 3 — 效率层（回答"人机协作效率如何"）
  ├─ 📐 上下文压缩比                        ← P1
  ├─ 📊 Token 效率（每任务 Token）          ← P1
  └─ 🔄 执行效率（每轮完成任务数）          ← P1

Layer 4 — 进化层（回答"系统在变好还是变差"）
  └─ 🧠 知识沉淀率                          ← P1
```

## 核心指标详解

**目标准确率（P0）**：Agent 正确完成预定任务的比率。

> 公式：目标准确率 = 正确完成的任务数 ÷ 总分配任务数 × 100%
>
> ≥80%：L3 就绪（受监督自主）| 60-80%：L2 协作 | <60%：需优化

**首次成功率（P0）**：Agent 一次性正确完成任务的比率。直接影响成本——从 60% 提升到 80% 可将单任务 Token 成本降低约 50%。

**约束自愈率（P0）**：Agent 自主修复约束失败的比例。

> 公式：自愈率 = 自主修复的约束失败数 ÷ 约束失败总数 × 100%
>
> ≥70%：优秀 | 40-70%：良好 | <40%：需改进

**自主性综合评分（P0）**：加权综合评分（0-100）。
> 权重：自愈率 40% + MUST 通过率 35% + (1-HITL率) 25%
>
> ≥80：L3 就绪 | 60-80：L2 成熟 | <60：L1 基线

**复合 ROI（P1）**：引入失败折现系数的真实 ROI。
> 公式：((节省人力 × (1-失败率)) - AI成本) ÷ AI成本 × 100%
>
> 优秀团队通常 3 年内实现 200%-400% 复合 ROI

**上下文压缩比（P1）**：裁剪前后 Token 比。
> 公式：输入 Token ÷ 输出 Token
>
> ≥5:1：优秀（crop_context.py 效果显著）| 3-5:1：良好 | <3:1：需优化

**知识沉淀率（P1）**：本周期新模式占累积模式的比例。
> ≥15%：活跃学习 | 5-15%：稳步积累 | <5%：停滞

## 遥测大屏（v1.13.1 纯静态 · 无需 Server）

`collect_telemetry.py` 每次采集后会**自动生成内嵌数据的 HTML**，双击即可：

```text
governance/dashboard.html              ← 项目总遥测（内嵌 telemetry.json）
governance/dashboard-T-018.html        ← 单次契约（内嵌该次 JSON）
```

- **总 → 单**：总览页 `runs` 表点链接 → `dashboard-T-XXX.html`
- **单 → 总**：单次页顶栏「返回项目总遥测」→ `dashboard.html`
- **不需要** `npx serve` / 任何本地 HTTP 服务

```bash
# 采集即刷新大屏
python3 scripts/collect_telemetry.py --project my-proj --task T-018 ... --output governance/telemetry.json
open governance/dashboard.html          # macOS
# 或双击 dashboard-T-018.html
```
