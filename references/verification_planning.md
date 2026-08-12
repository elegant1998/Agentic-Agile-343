# 风险驱动多层验证计划

Verification Plan 回答的不是“测试跑没跑”，而是“每个关键结论由哪些不同层级、哪些来源、在什么时效和责任边界下被证明”。它是任务级执行计划，不增加第五大核心工件。

## 最小用法

```bash
python scripts/cli.py verification plan --task T-001 --project-dir .
python scripts/cli.py verification plan --task T-001 --project-dir . --risk high --trace AC-001 --apply
# IO 审阅后才可把 DRAFT 改为 AUTHORIZED
python scripts/cli.py verification check --task T-001 --project-dir .
python scripts/cli.py verification status --task T-001 --project-dir .
```

`plan` 默认 dry-run；`--apply` 只创建 DRAFT，已有文件绝不覆盖。`check/status` 只读取项目内计划与证据，不执行自定义 shell、发布或生产写操作。

## 如何裁剪

- low 可用单层 SELF 证据证明局部 AC。
- medium 至少 CROSS_CHECK，通常组合单元/组件与接口或行为观察。
- high 至少 INDEPENDENT，并选择安全、数据、性能或恢复中与真实风险相关的层。
- safety_critical 必须 HUMAN_ACCEPTANCE；AI 只能整理证据，不能代签。

验证层包括 unit、component、interface、UI journey、SIT、performance、security、data、UAT 和 production。风险决定最低充分组合，不代表机械选择全部层级。

## 证据与裁决

每条 proof obligation 追溯 `AC-*`、`PRESERVE-*` 或 `CONSTRAINT-*`，声明 required layers、evidence sources、producer、verifier、最低独立性、freshness 和 verdict。证据文件至少应包含任务 ID、ISO-8601 生成时间与 PASS/FAIL 结果。

同一 `source_id` 或相同内容的复制报告只算一个来源；改文件名、换 Agent 名称或让同一过程自称“独立”不会提升证据独立性。缺失、不可解析、任务不匹配或过期返回 UNKNOWN/FAIL。HUMAN_ACCEPTANCE 由 AI、OA、Codex 或模型签署时返回 ESCALATED。

最终裁决保留 PASS、FAIL、UNKNOWN、CONDITIONAL、ESCALATED。CONDITIONAL 必须同时写明 condition、owner、deadline 与 reverify；任何非 PASS 都会在正式计划存在时阻断 prove 门。
