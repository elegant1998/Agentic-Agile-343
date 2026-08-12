# 自然语言能力路由

本参考定义 v1.25—v1.34 能力如何从用户日常表达路由到内部治理工具。自然语言是用户入口，CLI 是 Agent 内部执行器。

## 路由总则

1. 先判断用户是在要求只读了解、规划，还是明确要求修改。只读请求不得扩展为写入。
2. 优先使用最具体的路由；必要时组合前置能力，但不得为了“流程完整”制造无关工件。
3. 先从仓库和治理工件发现答案。只有影响选路且无法发现时，才只追问一个信息增益最高的问题。
4. 用户不需要提供 T-ID、B-ID、M-ID 或 CLI 参数；Agent 负责发现或安全分配，且不得覆盖旧记录。
5. 用户使用“Bug、门禁误报、只允许”等标签不构成事实证明，也不授予签署、围栏授权、权限扩张或不可逆操作权。

## 完整路由矩阵

| 路由 | 典型自然语言 | 内部入口 | 完成或转向条件 |
|---|---|---|---|
| `PROJECT_RECON` | “这是已有项目，先了解一下”“先别改代码，看看现状” | `recon.py` 或 `cli.py init` 的只读阶段 | 输出 Baseline / Preserve / Unknown / 建议围栏；不写业务代码 |
| `RISK_INIT` | “帮我评估风险”“这个项目该用什么治理强度”“初始化治理但先给我看计划” | `cli.py init`，默认 dry-run | IO 明确同意 apply 后才能落盘；Unknown 禁止降级 |
| `MAINTENANCE` | “这个门禁误报了”“治理脚本自身有确定性缺陷” | `cli.py maintain open/check/close` | 六项准入全真才走 M；规则、签署、权限、批准边界变化转契约 |
| `TASK_RECON` | “分析改这个文件会影响哪些地方”“先看看这个类被谁调用” | `cli.py recon task` | Fact / Candidate / Unknown 分层；结果仅建议围栏，不自动授权 |
| `CHANGE_ENVELOPE` | “本次只能改这些文件”“不要碰数据库和部署配置” | `cli.py envelope check` 与围栏模板 | 先形成 DRAFT；只有 IO 可改为 AUTHORIZED，protected 优先 |
| `CHARACTERIZE` | “没测试，先锁住现在的行为”“重构但不能改变旧输出” | `cli.py characterize plan/capture/verify` | Preserve 来源必须是 IO 确认或既有测试；SAME 不替代新 AC |
| `SAFE_CHANGE` | “安全地修改这个已有功能”“按完整流程改这段旧代码” | `cli.py change plan/status/prepare/verify/close` | 按当前证据重算状态；签署、围栏、Preserve 和门禁缺一不可 |
| `BUG` | “这是一个 Bug，请修复”“以前正常，现在失败” | `cli.py bug open/classify/reproduce/status/verify/telemetry/close` | 只有实现回归、父任务可追溯、边界不变且真实 RED 才能改代码 |
| `VERIFICATION_PLAN` | “不要只跑单测”“设计多层验证”“检查证据是否同源”“排查无效全绿” | `cli.py verification plan/check/status` | 计划先 DRAFT；缺层、同源、过期、独立性不足或 AI 代签均不得 PASS |
| `EVIDENCE_FINALIZE` | “生成证据包并完成任务”“证据已经整理好了” | `cli.py change verify` 在 Prove 通过后自动调用 `evidence finalize` | Evidence 完成后无需等待用户提醒；生成单任务/项目遥测和双 Dashboard，指标由 tracker/collector 事实读取或派生，失败不得完成 |
| `RELEASE_MANIFEST` | “准备发布”“生成发布清单”“检查制品和证据是否一致”“记录已发布/回滚” | `cli.py release plan/check/status/record` | READY 只交给人类决策；不执行 Tag、push、部署或生产写入 |

## 冲突消解

- “这是 Bug，但预期行为也要改”先走 `BUG` 分类；一旦确认是规格变化，立即转 Amendment 或新契约。
- “门禁误报，顺便改变门禁规则”不能走纯 `MAINTENANCE`，因为规则语义变化需要契约。
- “修改已有功能，但不知道影响范围”先 `TASK_RECON`，再进入 `SAFE_CHANGE`。
- “修改已有功能，而且没有可靠测试”先组合 `TASK_RECON` + `CHARACTERIZE`，再进入 `SAFE_CHANGE`。
- “只允许改两个文件并修 Bug”先建立 `CHANGE_ENVELOPE`，随后 `BUG` 修复仍必须服从围栏。
- “安全修改并且不要只跑单测”先用 `SAFE_CHANGE` 控制变更，再用 `VERIFICATION_PLAN` 证明结果；验证计划不扩大 Change Envelope。
- “生成证据并完成”在 Evidence 内容完成后自动进入 `EVIDENCE_FINALIZE`；这不是新的人工确认点，也不表示 IO 已批准 Evidence。
- “修好这个 Bug 并直接发布”先完成 `BUG` 闭环，再进入 `RELEASE_MANIFEST`；修复授权不包含发布授权。
- 只说“看看、分析、评估”时保持只读；只有“修改、修复、实施”等明确动作才授权可逆的项目内实现步骤，且不包含发布、推送或其他不可逆动作。

## Bug 路由细则

用户最简话术：

> 这是一个 Bug：订单保存后刷新，金额变成了 0；预期保持保存值。请修复。

Agent 应当：

1. 从契约、证据包、遥测、意图图谱和代码关联中寻找唯一父任务；不能唯一确定时只追问一个关键问题。
2. 扫描 `governance/bugs/B-*.yaml`，分配下一个未占用 B-ID，禁止覆盖。
3. 将用户描述映射为 symptom / expected / actual / reproduction，能从仓库发现的内容不重复询问。
4. 完成六类问题分类；无法复现则停止改代码并报告证据缺口。
5. 实现回归取得真实 RED 后执行 TDD，随后 verify、独立 Bug telemetry、证据/图谱回写和 close。

## Evidence 自动收口细则

当 Agent 创建或完成更新 `governance/evidence/EB-T-XXX.md`，且其中已经包含任务归属、AC 验证结果和约束检查结果时，推荐执行：

```bash
python scripts/cli.py change verify --task T-XXX --project-dir .
```

`change verify` 先跑 Prove gate，成功后由工作流代码直接调用底层 `evidence finalize`。用户无需知道或重复底层命令。成功必须同时得到单任务遥测、项目累计遥测、项目 Dashboard 和 `dashboard-T-XXX.html`；任一步失败时 Agent 应报告阻断原因并继续修复，不得跳过、静默降级或声称任务完成。自动收口不修改 Evidence Bundle，不填写 IO 签署，也不执行上传或发布。
