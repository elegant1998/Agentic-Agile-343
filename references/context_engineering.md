# 上下文工程：三层注入模型

> 本文是 SKILL.md §5 的详细参考，按需加载。

## 三层注入模型

本 skill 内置**三层上下文注入模型**，确保 AS 每次任务只拿到"最小必要上下文"，避免全局信息泄漏：

```
┌──────────────────────────────────┐
│ L1: 意图图谱（全量）              │
│ → 注入对象: OA 会话级             │
│ → 内容: 北极星、五大域、用户画像   │
│ → 频率: 会话开始一次               │
├──────────────────────────────────┤
│ L2: 全局约束（共享）              │
│ → 注入对象: OA + AS 会话级        │
│ → 内容: 技术栈、API 规范、安全规则 │
│ → 频率: 一次注入，全会话复用       │
├──────────────────────────────────┤
│ L2+: AI 编码规范（STYLE 域）      │
│ → 注入对象: AS 任务级             │
│ → 内容: 硬性红线 ≤5 + 分层约束    │
│ → 来源: governance/AI_Coding_Guide.md │
│ → 频率: 每次任务自动加载 §1+§2    │
├──────────────────────────────────┤
│ L3: 任务切片（收敛）              │
│ → 注入对象: AS 任务级             │
│ → 内容: 目标+非目标+规则+AC+代码   │
│ → 频率: 每个 SCOPE-V 任务独立      │
└──────────────────────────────────┘
```

## 裁剪工作流

OA 在给 AS 派任务时，不应手工编写冗长 prompt，而是：

```bash
# 1. 自动发现代码上下文
python scripts/discover_context.py --project-dir /path/to/project --format text

# 2. 三层裁剪，生成精简 prompt
python scripts/crop_context.py --task T-003 --domain membership

# 3. 将输出直接注入给 AS Agent

# 🆕 隔离验证：确保裁剪后上下文不包含禁止信息
python scripts/crop_context.py --task T-003 --verify-isolation

# 🆕 动态监听模式：文件变更自动重新裁剪
python scripts/crop_context.py --task T-003 --watch
```

## 精简契约（YAML 格式）

```yaml
# 契约只保留执行必需的 5 个字段
goal:          # 目标（做什么）
not_goal:      # 非目标（禁止触碰）
rules:         # 业务规则（怎么判定）
ac:            # 验收标准（怎么验证）
db_tables:     # 数据表（可选）
```

篇幅约为原 Markdown 契约的 30%，消除所有叙事性内容。
