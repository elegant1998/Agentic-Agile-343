# Harness Engineering 六大支柱总览

> 本文是 SKILL.md 六大支柱章节的详细参考，按需加载。

## 总览

本 skill 的能力体系围绕六大支柱构建，每个支柱回答一个治理核心问题：

| # | 支柱 | 核心问题 | 覆盖率 | 关键资产 |
|---|------|----------|--------|----------|
| 1 | **上下文管理** | AI 应该看到什么？ | 6/6 ✅ | crop_context.py（三层注入 + 隔离验证 + watch） |
| 2 | **工具系统** | AI 能触达和操作什么？ | 4/4 ✅ | tools_manifest.yaml + audit_tools.py |
| 3 | **执行编排** | AI 应按什么顺序完成任务？ | 7/7 ✅ | work_graph.yaml + graph_engine.py（含 reschedule + timeouts） |
| 4 | **状态与记忆** | AI 应该记住什么？ | 7/7 ✅ | reflect.py（反思 + 反哺 + carry-over + 记忆衰减） |
| 5 | **评估与观测** | 怎样判断 AI 做得对不对？ | 11/11 ✅ | collect_telemetry.py v2.0 + dashboard.html v2.0 + verify_* |
| 6 | **约束与恢复** | AI 不能做什么，失败后怎样恢复？ | 10/10 ✅ | harness.py（check + recover + NFR）+ constraints.yaml |

## 支柱 1: 上下文管理

```
三层注入模型 → crop_context.py
  ├─ L1: 意图图谱（OA 会话级）
  ├─ L2: 全局约束（共享复用）
  ├─ L3: 任务切片（AS 任务级，YAML 精简契约）
  ├─ Ctx: 代码上下文（discover_context.py 自动发现）
  ├─ 🆕 隔离验证: --verify-isolation（跨域泄漏/敏感信息/Token 预算）
  └─ 🆕 动态切换: --watch（文件变更自动重裁剪）
```

## 支柱 2: 工具系统

```
tools_manifest.yaml → audit_tools.py
  ├─ 工具白名单（18 个工具，6 个分类）
  ├─ 权限边界（文件/网络/数据库/部署）
  ├─ 任务-工具能力矩阵
  ├─ 白名单审计
  ├─ 权限审计（高风险操作需 IO 审批）
  ├─ 边界审计（路径/域名/SQL/环境）
  └─ 清单自验证（引用完整性检查）
```

## 支柱 3: 执行编排

```
work_graph.yaml → graph_engine.py
  ├─ 拓扑排序 + 并行组 + 关键路径
  ├─ 分支/回滚规则
  ├─ 🆕 超时控制（全局 + 每节点）
  ├─ 🆕 重调度: reschedule 命令
  └─ 🆕 timeouts 命令（超时配置总览）
```

## 支柱 4: 状态与记忆

```
reflect.py
  ├─ 反思日志（what_worked/failed/improve/patterns）
  ├─ 图谱反哺（--feedback-to-graph）
  ├─ 🆕 跨任务传递（--carry-over + --next-task）
  └─ 🆕 记忆衰减（--decay-memory --decay-days 90）
```

## 支柱 5: 评估与观测

```
collect_telemetry.py v2.0（4 层 9 维）
  ├─ 价值层: 目标准确率 + 首次成功率 + 复合 ROI
  ├─ 能力层: 约束自愈率 + 自主性评分 + HITL 升级率
  ├─ 效率层: 上下文压缩比 + Token 效率 + 执行效率
  └─ 进化层: 知识沉淀率

验证器矩阵
  ├─ verify_contract.py（AC 自动化验证）
  ├─ audit_evidence.py（证据包完整性）
  ├─ verify_triangulation.py（三方一致性）
  └─ self_consistency_check.py（自洽性）

dashboard.html v2.0（4 层展示 + 传统指标兼容）
```

## 支柱 6: 约束与恢复

```
constraints.yaml → harness.py
  ├─ 核心六域（所有项目必须）: STRUCT/DATA/BEHAVE/QUAL/PROC/STYLE
  ├─ AI 编码规范: STYLE 域 → AI_Coding_Guide.md → L2 自动注入
  ├─ 7 个 NFR 验证器（bandit/secrets/health/retry/log/monitoring/test_run）+ 插件扩展
  ├─ MUST/SHOULD/MAY 分级 + 门禁体系 G0（意图前置）+ G1-G5（核心）+ G6-G8（Web 扩展）
  ├─ 🆕 on_failure 降级策略（block/warn/log）
  ├─ 🆕 自动恢复: recover 子命令
  ├─ 🆕 约束冲突优先级链（SEC 100 > DATA 90 > ...）
  └─ 例外管理（valid_until 自动过期）
```

## 约束域分层说明

| 分层 | 域 | 适用范围 | 说明 |
|------|-----|---------|------|
| **核心六域** | STRUCT / DATA / BEHAVE / QUAL / PROC / **STYLE** | 所有项目 | 文件结构、数据完整性、行为正确、质量门禁、过程合规、**AI 编码规范** |
| **Web 扩展域** | SEC / REL / OBS | Web 服务项目 | 安全扫描、可靠性、可观测性 |
| **NFR 验证器** | bandit / secrets / health / retry / log / monitoring / test_run | 代码项目 | 自动安全扫描、密钥检测、健康检查、测试执行等（可插件扩展） |

> **STYLE 域**承载 `AI_Coding_Guide.md` 中的硬性红线（≤5 条），由 `crop_context.py` 自动注入到每次 AS 任务的 L2 上下文。OA 在项目初始化时从模板填充。
>
> **CLI 工具、离线脚本、纯库项目应删除 SEC/REL/OBS 域的所有约束。** 扩展域约束默认设为 `SHOULD`（不阻断），上线前 OA 可按需升级为 `MUST`。
