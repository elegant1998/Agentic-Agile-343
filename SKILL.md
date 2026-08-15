---
name: agentic-agile-343
description: "Agentic-Agile-343，让 AI 研发治理进可攻退可守。用户说既有项目先看看、风险评估或初始化治理、门禁误报、分析文件影响范围、本次只允许修改某些文件、没有测试先固定现有行为、修改已有功能、报告 Bug/缺陷/回归并要求修复、设计多层验证、生成证据包并完成任务，或准备发布、生成发布清单、检查制品和证据是否一致、记录已发布/回滚时使用。提供 3-4-3、Recon、安全变更、Verification Plan、Evidence 遥测收口、Release Manifest、TDD、证据与遥测闭环。Use for existing-project governance, safe changes, bug/regression repair, risk-driven verification, evidence-to-telemetry finalization, proof-carrying release readiness, artifact/evidence binding, and release/rollback fact recording."
metadata:
  display_name: "Agentic Agile 343"
  version: "1.50.0"
  author: "王立杰-无敌哥"
  created: "2025-07-20"
---

# Agentic Agile 3-4-3 治理架构

基于《Agentic Agile智能体敏捷：从氛围编程到验证工程的AI研发治理指南》v1.6 的落地 skill。将 3-4-3 治理架构（3 个超级角色、4 个动态工件、3 大自治运行机制）转化为可直接使用的模板和工具。

> **v1.14+ 通用立场（跨项目、跨领域）**：批判性思维是 OA 的**默认职责**，不绑定任何特定产品、课程、证书或仓库。任何新需求在进入实现前，都可质疑、校准、给推荐默认；「用户字面意思 = 实现规格」是反模式。

## 自然语言能力路由矩阵

**用户不需要记忆 CLI、B/T 编号或治理术语。** 先依据用户自然语言选择最小能力入口，再由 Agent 调用内部脚本：

| 用户可能会说 | 路由 | Agent 的第一步 | 不得越过的边界 |
|---|---|---|---|
| “这是已有项目，先看看再改” | `PROJECT_RECON` | 只读建立 Baseline / Preserve / Unknown | 不生成修改、不覆盖文件 |
| “评估风险，看看该用多重治理” | `RISK_INIT` | 风险评估并输出 dry-run 计划 | 未明确 apply 不落盘、不降级 Unknown |
| “这个门禁误报了” | `MAINTENANCE` | 判断是否满足 M-XXX 六项准入 | 规则、签署、权限语义变化必须升级契约 |
| “分析改这个文件会影响什么” | `TASK_RECON` | 围绕目标发现依赖、引用、测试和 Unknown | Candidate 不冒充 Fact |
| “本次只允许修改这些文件” | `CHANGE_ENVELOPE` | 生成或检查 DRAFT 围栏 | Agent 不得自行 AUTHORIZED 或扩围 |
| “没有测试，先固定现在的行为” | `CHARACTERIZE` | 规划 Preserve 特征基线 | Preserve 必须由 IO 或既有测试确认 |
| “安全地修改这个已有功能” | `SAFE_CHANGE` | 编排 plan → prepare → verify → close | 不复制门禁，不自动签署或运行未授权实现；verify 必须自动串起 Prove→Evidence/Telemetry |
| “这是一个 Bug/缺陷/回归，以前正常现在失败……请修复” | `BUG` | 调查父任务、分配 B-ID 并分类 | Bug 标签不代替分类；无真实 RED 不改代码 |
| “不要只跑单测，设计多层验证并检查证据是否同源” | `VERIFICATION_PLAN` | 按风险生成 DRAFT proof obligations | 不自动授权；缺层、同源、过期或 AI 代签不得 PASS |
| “生成证据包并完成任务” | `EVIDENCE_FINALIZE` | `change verify` 在 Prove 通过后自动运行 `evidence finalize` | 无需等待用户提醒；失败不得完成，不自动签署或批准 |
| “准备发布，生成发布清单，检查制品和证据是否一致” | `RELEASE_MANIFEST` | 实测提交、制品摘要并生成 DRAFT | 不自动批准；不执行 Tag、push、部署或生产写入 |

同时出现多个信号时，先处理最具体的事实：门禁自身缺陷走 `MAINTENANCE`；已完成功能异常先走 `BUG` 分类；具体文件优先 `TASK_RECON`；验证充分性走 `VERIFICATION_PLAN`；Evidence 写入完成立即走 `EVIDENCE_FINALIZE`；准备发布、制品绑定或记录已发布/回滚事实走 `RELEASE_MANIFEST`；`CHANGE_ENVELOPE` 与 `CHARACTERIZE` 作为 `SAFE_CHANGE` 的前置保护组合使用。证据仍不足时，先只读调查；只有确实无法唯一选路时才只追问一个信息增益最高的问题。

“3-4-3、Agentic Agile、意图契约、约束矩阵、证据包、SCOPE-V、意图图谱、遥测”等方法词同样触发本 skill。完整话术、冲突消解和 Agent 动作见 **[references/natural_language_routing.md](references/natural_language_routing.md)**。

## 核心资源

本 skill 提供以下资源，按需加载：

| 资源 | 路径 | 用途 |
|------|------|------|
| 意图图谱模板 | `templates/Template_Intent_Graph.md` | 宏观导航地图，含裁剪关系 |
| 意图契约模板 (MD) | `templates/Template_Intent_Contract.md` | 单次任务执行基准（详细版） |
| 意图契约模板 (YAML) | `templates/Template_Intent_Contract.yaml` | 单次任务执行基准（精简版，用于上下文裁剪） |
| 约束矩阵模板 (MD) | `templates/Template_Constraint_Matrix.md` | 六域硬门禁（人类可读文档） |
| 约束定义 (YAML) | `templates/Template_Constraints.yaml` | 结构化约束定义（核心六域 + NFR 域 + 降级/恢复策略） |
| **AI 编码规范** | `templates/Template_AI_Coding_Guide.md` | **硬性红线 ≤5 + 分层约束 + 自检清单（L2 自动注入）** |
| **跨工具治理协议** | `templates/Template_Protocol.yaml` | **模块清单 + 跨模块契约 + 集成 DAG + 多语言 checks** |
| **模块 OA 指南** | `templates/Template_Module_Governance.md` | **多模块场景下模块负责人的快速启动指南** |
| 工具清单 | `templates/Template_Tools_Manifest.yaml` | **AS 可用工具白名单 + 权限边界 + 能力矩阵** |
| 证据包模板 | `templates/Template_Evidence_Bundle.md` | 裁决支撑材料（人类可读版） |
| 证据包模板 (YAML) | `templates/Template_Evidence_Bundle.yaml` | 结构化证据包（脚本消费：五类证据+映射表+遥测+6种裁决） |
| 工作图模板 | `templates/Template_Work_Graph.yaml` | DAG 任务拓扑（含超时 + 重调度策略） |
| **统一命令执行器** | `scripts/command_runner.py` | **Python 原生 argv 执行、显式 shell 方言、结构化失败状态；Windows/macOS/Linux 共用（v1.36）** |
| 遥测汇总器 | `scripts/collect_telemetry.py` | 读取/汇总管道、质量、性能、成本与治理指标 |
| **跨平台遥测主流程** | `scripts/telemetry_workflow.py` | **Python 原生编排可信度量、测试与 Dashboard；Windows 不要求 Bash（v1.35）** |
| **执行事件追踪** | `scripts/telemetry_tracker.py` | **追加式事件账本；从签署契约、合格 Evidence 和事件派生事实（v1.36）** |
| Unix 兼容包装器 | `scripts/quick_telemetry.sh` | 仅转发到 Python 主流程，不承载度量逻辑 |
| **Evidence 遥测收口** | `scripts/evidence_workflow.py` | **Evidence 完成后调用 Python 遥测主流程；指标由 tracker/collector 事实派生（v1.36）** |
| **门禁验证器** | `scripts/gate_check.py` | **SCOPE-V 5 个检查门的机械验证器：前置/编码/验证/收尾/Bug回溯（v1.20）** |
| **Token 实测** | `scripts/token_usage.py` + `scripts/tool_bootstrap.py` | **首次安装到 Skill 私有工具目录，后续直接复用；缺 npm 时明确降级（v1.44.3）** |
| **依赖自举** | `scripts/_bootstrap.py` + `scripts/ensure_py_env.sh` | **Python 原生自包含依赖 bootstrap：首次缺失时自动建 venv + 装 pyyaml；后续探测健康即直接复用，不再执行 pip（v1.44.1）** |
| **Skill 发布** | `scripts/skill_release.py` | **一条命令机械升版并校验；单次 staging 同时驱动本地原子安装与对外 ZIP（v1.44.2）** |
| 代码上下文发现 | `scripts/discover_context.py` | AST 解析自动发现 API 端点、模型、依赖 |
| **轻量 Recon** | `scripts/recon.py` | **既有项目只读侦察；可选消费 IWE Document Map 与 codebase-memory-mcp Code Map，缺失时保持 L0** |
| **Context Provider** | `scripts/context_providers.py` | **统一能力探测、制品归一化、新鲜度检查与需求—代码—测试 Trace Link（v1.37）** |
| **任务级 Recon** | `scripts/task_recon.py` | **围绕具体文件发现依赖与候选，并按 L0-L3 渐进增强、Fact / Candidate / Unknown 分层** |
| **变更围栏门禁** | `scripts/change_envelope.py` | **用正式 Change Envelope 机械检查 staged/unstaged/untracked/delete/rename 实际变更** |
| **特征行为基线** | `scripts/characterize.py` | **plan/capture/verify 既有 Preserve 行为，输出 SAME / CHANGED / UNVERIFIABLE** |
| **安全变更入口** | `scripts/change_workflow.py` | **change plan/status/prepare/verify/close，统一编排既有代码安全变更状态** |
| **Bug 修复入口** | `scripts/bug_workflow.py` | **B-XXX 分类、真实复现 RED、修复验证与历史回溯** |
| **多层验证计划** | `scripts/verification_plan.py` + `templates/Template_Verification_Plan.yaml` | **按风险裁剪验证层，检查证据独立性、时效、责任与无效全绿** |
| **携证发布清单** | `scripts/release_manifest.py` + `templates/Template_Release_Manifest.yaml` | **绑定 Git commit、制品摘要、配置、任务证据、批准、发布与回滚事实** |
| **风险评估** | `scripts/assess_risk.py` | **按事实推荐 explore / delivery / high-risk / legacy / multi-module 治理模式** |
| **风险驱动入口** | `scripts/init_governance.py` | **识别项目类型、执行 Recon、评估七域风险并生成最小治理计划；默认 dry-run** |
| **门禁维护通道** | `scripts/maintenance.py` | **以 M-XXX 管理低风险机械缺陷；Unknown 或规则语义变化自动升级为契约** |
| 上下文裁剪引擎 | `scripts/crop_context.py` | 三层注入模型，自动注入有界 L0-L3 Document/Code Map 上下文 |
| **Harness 引擎** | `scripts/harness.py` | **约束执行引擎（含 7 个 NFR 验证器，支持插件扩展）** |
| 自洽性检查 | `scripts/self_consistency_check.py` | LOOP-1: 校验产出物是否与契约一致 |
| 反思+反哺 | `scripts/reflect.py` | LOOP-2/3: 生成反思日志 + 反哺意图图谱 |
| **Graph 引擎** | `scripts/graph_engine.py` | **DAG 引擎（含 reschedule + timeouts 命令）** |
| **工具审计器** | `scripts/audit_tools.py` | **审计 AS 工具调用合规性（白名单/权限/边界）** |
| **契约验证器** | `scripts/verify_contract.py` | **逐条执行 AC 验收标准（shell/http/db/predicate，支持 MD+YAML+YML 契约）** |
| **证据包审计** | `scripts/audit_evidence.py` | **按约束 ID 检查证据包覆盖度（支持 EB-T-XXX 拆分模式）** |
| **三方一致性** | `scripts/verify_triangulation.py` | **图谱↔契约↔约束交叉一致性验证** |
| **回滚安全验证** | `scripts/verify_rollback_safety.py` | **DAG 回滚前安全性分析（下游/数据/并行组）** |
| **时间窗口验证** | `scripts/verify_freshness.py` | **工件时效检测（已完成任务自动豁免）** |
| **跨模块契约验证** | `scripts/verify_cross_module.py` | **验证跨模块接口契约（XC）可达性 + SLA + 破坏性变更** |
| **证据聚合器** | `scripts/aggregate_evidence.py` | **多模块证据包聚合 + 遥测合并 → 发布证据包** |
| **共享解析库** | `scripts/gov_common.py` | **统一发现与解析 MD/YAML/YML 契约，同任务多格式冲突 fail closed** |
| **Loop Memory 模板** | `templates/Template_Loop_Memory.yaml` | **跨 cycle 统一状态文件（进度 + 教训 + 模式 + 决策）** |
| **Recon 基线模板** | `templates/Template_Recon_Baseline.md` | **既有项目的事实、保留项、未知项与变更围栏** |
| **Change Envelope** | `templates/Template_Change_Envelope.yaml` | **限定本轮允许和禁止修改的范围** |
| **治理模式模板** | `templates/Template_Governance_Profile.yaml` | **风险等级、最小工件、机械门和 HITL 要求** |
| 遥测仪表板 | `assets/dashboard.html` | 网页式实时大屏 |
| **自然语言路由** | `references/natural_language_routing.md` | **v1.25—v1.31 用户话术、路由优先级与边界** |
| **验证计划指南** | `references/verification_planning.md` | **proof obligation、验证层、独立性与非二元裁决** |
| **携证发布指南** | `references/release_manifest.md` | **Release Manifest、Build Once、就绪裁决与追加事件** |
| **参考文档** | `references/*.md` | **按需加载的详细参考（见下文各节链接）** |

## 使用流程

> **统一风险驱动入口（v1.26.0）**：新项目与既有项目统一先规划，默认仅预览、不写文件：
>
> ```bash
> python scripts/cli.py init --project-dir .
> # IO 确认计划后才显式落盘
> python scripts/cli.py init --project-dir . --apply
> ```
>
> 入口识别 new / existing-small / legacy-complex / multi-module；既有项目自动纳入只读 Recon。七域风险中的信息不足会保留 Unknown，禁止自动降级；已有文件不覆盖，生成的契约保持 PENDING，必须由 IO 显式签署。

> **既有代码任务级 Recon（v1.27.0）**：项目级 Recon 后，编码前可围绕本次目标文件继续缩小影响范围：
>
> ```bash
> python scripts/cli.py recon task --task T-XXX --target src/example.py --project-dir .
> ```
>
> 内置轻量适配 Python、JavaScript/TypeScript、C/C++、Java/JSP，并为 Go、Rust、Shell 提供基础发现。结果严格区分 Fact / Candidate / Unknown；建议 Change Envelope 状态固定为 `DRAFT_NOT_AUTHORIZED`，不得替代 IO 签署。详见 **[references/task_recon.md](references/task_recon.md)**。

> **双地图渐进增强 Recon（v1.37.0）**：IWE 推荐作为 Document Map，codebase-memory-mcp 推荐作为 Code Map，343 用统一 ID 维护 Trace Link。Agent-native MCP、显式 JSON/YAML Map 制品和内建扫描是三种兼容入口；没有外部工具时 L0 继续完整工作并给出非阻断建议。CLI 不伪装发现宿主 MCP，不自动安装、配置、联网或回写地图。外部静态/语义关系默认保持 Candidate，过期、冲突、越界或不兼容数据进入 Unknown 并 fail closed。详见 **[references/task_recon.md](references/task_recon.md#document-map--code-map-渐进增强v1370)**。

> **项目级地图默认增强（v1.38.0）**：项目 Recon 默认发现 `governance/recon/*_map_artifact.json`；工具可用但项目地图缺失时，以显式项目根初始化 IWE `.iwe` 并调用 codebase-memory-mcp `index_repository --repo-path <PROJECT> --persistence true`。双地图归一化后自动生成 Trace Link；无充分证据的关系保持 Candidate/Unknown。可用 `--no-auto-context` 关闭初始化；工具失败继续回退 L0。该能力只允许项目内持久化，不自动安装、联网、修改全局 MCP 配置或扩大 Change Envelope。

> **原生地图适配与 Prompt 注入（v1.40.0）**：Recon 可将 IWE 与 codebase-memory-mcp 的结构化结果原子归一化为标准 Map 工件，`crop_context.py` 默认把有界的 Document Map、Code Map、Candidate Trace Link、Provider 状态和 Unknown 注入 Agent Prompt。L0/L1/L2/L3 均可工作；`--no-map-context` 可关闭注入。团队模式使用 `recon.py --map-mode team`：匹配 revision 的 `authority: ci` 快照只消费不覆盖，缺失时仅生成 `governance/recon/.local/` 本地回退。地图异常必须披露影响和人工恢复建议，地图上下文不构成执行授权或验证证据。

> **Evidence 收口性能治理（v1.40.1）**：可信 Verification Run Context 会作为 collector 的唯一测试快照，禁止 `collect_telemetry.py` 再通过 `harness tests` 隐性重跑；正式验证事件后的第二阶段只执行 metrics/dashboard refresh。收口启动前预检写权限，并输出 preflight、collector、formal_event、metrics_refresh 阶段及耗时。调度披露 external/internal/total execution 与 reuse count，context 失效时仍真实执行一次完整测试。

> **治理运行时统一计划（v1.41.0）**：Gate、Harness、Telemetry 共用唯一 `TestExecutionPlan`，Verification Run Context 绑定实际 argv、源码摘要与校验和；`nfr:test_run` 收到可信 context 时只验证快照，不再重跑测试。单次工作流通过 `ProjectSnapshot` 复用 revision、文件清单和源码摘要；Harness NFR 共用源码清单与内容缓存，Crop Context 只构建一次地图并在进程内发现代码上下文。调度输出 test/scan/digest/map/harness/collector/persist 的执行或复用事实，失效数据仍 fail closed。

> **安全执行与共享解析（v1.44.0）**：Provider 查询与 Task Recon 保持有界。治理检查只接受无副作用 AST 白名单谓词，旧任意 Python 断言 fail closed。`.yaml/.yml/.md` 契约由 `gov_common.py` 统一发现与解析，同任务多格式冲突显式阻断；Gate、Harness 与 Telemetry 共用 `runtime_context.py` 的测试输出计数。

> **跨工具可信遥测与不可旁路收口（v1.45.0）**：宿主 AI 工具、Token 客户端与项目身份分别记录，不依赖 WorkBuddy 或任何单一 AI 工具。项目日累计 Token 只可作为任务起止基线；仅同客户端、同项目、同自然日差值进入任务聚合，缺测或歧义保持 `UNKNOWN/N/A`。`change prepare` 自动捕获基线；`change verify` 必须连续执行 Prove、Evidence、Telemetry、Intent Graph 反馈与 Closing Gate，成功直接返回 `CLOSED`。Harness `recover --task T-XXX` 自动追加失败、恢复、复验事件链。

> **正式验证事实链（v1.39.0）**：Evidence/Telemetry 收口后由工作流代码追加 `formal_verification` 事件，结果严格为 `VERIFIED`、`CONDITIONAL` 或 `BLOCKED`。首次 `CONDITIONAL` 后续转 `VERIFIED` 不计首次成功；无正式事件时 `first_pass_rate` 为 UNKNOWN。`must_total=0` 输出 `NOT_APPLICABLE/N/A`，不显示虚假的 100%。

> **验证结果复用（v1.39.1）**：Prove gate 产生的测试结果写入 `governance/telemetry/verification-runs/T-XXX.json`；同一项目、源码摘要、argv 和任务的后续遥测收口复用该 context，不重复执行测试。context 缺失、过期、源码/命令/项目不匹配或摘要校验失败时自动重跑，并披露 execution/reuse count 与原因。

> **Change Envelope 机械门禁（v1.27.1）**：正式围栏经 IO 确认为 `AUTHORIZED` 后，可检查全部 Git 工作树变更，并自动接入 prove 门：
>
> ```bash
> python scripts/cli.py envelope check --task T-XXX --project-dir .
> ```
>
> protected 优先于 allowed；Unknown、DRAFT、任务不匹配、路径穿越或 Git 不可用均 fail closed。没有正式围栏的项目保持既有 prove 行为。详见 **[references/task_recon.md](references/task_recon.md#change-envelope-机械门禁)**。

> **既有行为特征基线（v1.28.0）**：缺少可靠测试时，先规划并由 IO 确认 Preserve，再捕获修改前可重复行为，修改后复验：
>
> ```bash
> python scripts/cli.py characterize plan --task T-XXX --target src/example.py --project-dir .
> python scripts/cli.py characterize capture --task T-XXX --project-dir .
> python scripts/cli.py characterize verify --task T-XXX --project-dir .
> ```
>
> 只执行已授权计划中的 argv 数组（`shell=False`）；敏感、超时或配置变化返回 UNVERIFIABLE。SAME 只证明 Preserve 未变，不替代 AC。详见 **[references/task_recon.md](references/task_recon.md#既有行为特征基线)**。

> **既有代码安全变更统一入口（v1.29.0，v1.36.2 收口串联）**：
>
> ```bash
> python scripts/cli.py change plan --task T-XXX --target src/example.py --project-dir .
> python scripts/cli.py change status --task T-XXX --project-dir .
> python scripts/cli.py change prepare|verify|close --task T-XXX --project-dir .
> ```
>
> 入口只编排已有 Recon、契约、围栏、Preserve 与门禁；计划默认 dry-run，状态从当前证据重算，每个非终态只给一个下一步。`change verify` 不再只给建议命令：Prove gate 通过后必须由工作流代码直接执行 `evidence finalize`，生成单任务遥测、项目遥测与双 Dashboard；收口失败则 `change verify` 返回 BLOCKED。详见 **[references/task_recon.md](references/task_recon.md#统一安全变更入口)**。

> **Bug 修复专用入口（v1.30.3）**：用户直接说“这是一个 Bug：……请修复”即可。Agent 自动寻找唯一且有证据的父任务、分配 B-ID 并执行 `bug open/classify/reproduce/status/verify/telemetry/close`；父契约与原任务遥测保持历史不变。详见 **[references/natural_language_routing.md](references/natural_language_routing.md#bug-路由细则)**。

> **风险驱动多层验证（v1.31.0）**：用户说“不要只跑单测”“设计多层验证”“检查证据是否同源”或“排查无效全绿”时，先用 `verification plan` 形成 DRAFT，再由 IO 授权。`verification check/status` 只读取项目内证据；缺层、同源伪装、证据过期、独立性不足、LLM 独证或 AI 代签均不得折算为 PASS。详见 **[references/verification_planning.md](references/verification_planning.md)**。

> **单项目携证发布（v1.32.0）**：用户说“准备发布”“生成发布清单”“检查制品和证据是否一致”时，`release plan` 实测 Git commit、制品 SHA-256 和任务证据并生成 DRAFT；IO 授权后 `check/status` 只给 `READY_FOR_HUMAN_RELEASE`，绝不自动发布。`record` 仅追加人类或外部系统已经执行的发布/回滚事实。详见 **[references/release_manifest.md](references/release_manifest.md)**。

> **SCOPE-V 自动收口（v1.36.2）**：`python scripts/cli.py change verify --task T-XXX --project-dir .` 是推荐完成入口。它先执行 Prove gate；通过后由工作流代码直接调用 `evidence finalize`，生成 `telemetry-T-XXX.json`、项目 `telemetry.json`、`dashboard.html` 与 `dashboard-T-XXX.html`。任一步失败都返回 BLOCKED，不得标记任务完成。底层 `python scripts/cli.py evidence finalize --task T-XXX --project-dir .` 保留为诊断/补跑入口。`SIGNED` 是契约不可变的 IO 授权状态；完成态由合格 Evidence、遥测与图谱/事件事实派生，不把契约改写为 `COMPLETED`。该动作不修改 Evidence，也不代替 IO 签署或批准；`--rebuild` 对缺少 `status` 的旧 run 按可信历史数据聚合，显式 UNKNOWN/NOT_APPLICABLE 仍排除。

> **Windows 原生全兼容（v1.36.0）**：公开核心能力必须可在 Windows 10/11 + CPython 3.10+ 原生运行，不要求 WSL、Git Bash 或 Cygwin。进程执行默认使用 `scripts/command_runner.py` 的 argv 数组与 `shell=False`；确需 Shell 时必须声明 `powershell` / `cmd` / `posix` 方言和适用平台。旧 POSIX-only 配置在无对应 Shell 时返回 `UNSUPPORTED_SHELL_DIALECT` 并 fail closed。

> **单人项目**: 直接按 §1-10 操作，`protocol.yaml` 和模块治理完全不需要——
> 就像它们不存在一样。3-4-3 的默认行为不依赖它们。
>
> **多人多模块项目**: 先按下面 §11 初始化跨模块治理，再按 §1-10 各自开发。

### 1. 初始化项目治理（单人）

```bash
# 复制模板到新项目
cp templates/Template_Intent_Graph.md /path/to/project/governance/Intent_Graph.md
cp templates/Template_Constraint_Matrix.md /path/to/project/governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml /path/to/project/governance/constraints.yaml

# 可选但推荐：AI 编码规范（STYLE 域 + L2 自动注入的基础）
cp templates/Template_AI_Coding_Guide.md /path/to/project/governance/AI_Coding_Guide.md

# 可选：架构文档（crop_context.py L2 全局约束的信息源，
# 描述技术栈/API 规范/认证/ORM 等，没有则 L2 退化为通用提示）
cp docs/architecture.md /path/to/project/docs/architecture.md  # 如有模板
```

**工件命名约定**（所有验证脚本均按此发现工件，务必遵守）：

| 工件 | 路径 | 说明 |
|------|------|------|
| 意图图谱 | `governance/Intent_Graph.md` | 单文件，会话级 |
| 意图契约 | `governance/contracts/Intent_Contract_T-XXX.md`（或 `.yaml/.yml`） | **每任务一份**；同一任务不得多格式并存 |
| 证据包 | `governance/evidence/EB-T-XXX.md` | **每任务一份**，与契约任务 ID 对应 |
| 约束矩阵 | `governance/constraints.yaml`（可执行版）+ `Constraint_Matrix.md`（人类可读版） | YAML 供 harness 引擎，MD 供 IO 审阅 |

**契约格式选择指引**：
- **MD 契约（推荐起步）**：人类可读性好，Grill-Me 决策确认 + **IO 显式签署**流程自然；AC 表格的"验证方式"列支持 `shell:`/`http:`/`predicate:`/`db:` 前缀实现自动化验证（写自然语言则视为人工验证项）
- **YAML 契约（精简进阶）**：体积约为 MD 的 30%，适合上下文敏感的 AS 任务注入；支持 `self_consistency`、`depends_on` 等结构化字段
- 项目可按任务选择任一格式；所有公开入口统一识别 `.md/.yaml/.yml`，同任务多格式冲突时明确阻断

**MD 契约的自洽性配置**：MD 契约如需启用 `self_consistency_check.py`，在契约中加一个围栏块：
````markdown
```yaml
self_consistency:
  expected_files: [src/App.tsx, server/index.ts]
  expected_endpoints: 5
  router_path: server/routes.ts
```
````

### 2. 按 SCOPE-V 六控制面运行（SDD + TDD 内嵌）

SCOPE-V 是六个持续控制面，而不是一次性线性阶段：`S / C / O / P⇄E / V`，即 Specify、Constrain、Orchestrate、Prove、Evolve、Verify。`P⇄E` 构成证明—演化快内环；Verify 后由 `V → Telemetry → S/C/O` 形成慢外环，把运行事实反馈到下一轮意图、约束或编排。

三大自治运行机制横跨六个控制面：上下文自治持续控制可信输入，执行自治负责编排、恢复与停止，进化自治只在证据与责任边界内回写规则和知识。Telemetry 是强制反馈证据，但不是额外控制面。

- SDD：契约 AC = 可执行规约，`verify_contract.py --generate-tests` 自动生成测试骨架
- TDD：Red（写失败测试）→ Green（最小实现）→ Refactor（重构+反思）
- 🔵 微检查点：Orchestrate 后、Prove 前 AS 必须向 OA 复述目标+影响范围
- 🔴 Evidence 完成后遥测收口：每任务 Verify 形成 Evidence 后，`change verify` 必须在 Prove 通过后自动调用 `evidence finalize`，生成结果摘要，否则不得标记“已完成”；指标事实由 tracker/collector 读取或派生，不由入口臆造

> 📖 完整流程图、SDD/TDD 详解、微检查点规则、遥测最小参数、落盘结果、跳过后果详见 **[references/scope_v_execution.md](references/scope_v_execution.md)**。

### 3. 收集遥测数据（4 层 9 维模型）

`collect_telemetry.py` 读取并汇总可直接测量的数据；`telemetry_tracker.py` 从 `SIGNED` 契约、合格 Evidence 与追加式事件账本派生关键 P0 指标。`SIGNED` 仅代表 IO 授权，不是完成态，也不会迁移成 `COMPLETED`；完成由 Evidence、遥测和图谱/事件事实独立派生。无法证明的数据保持 `UNKNOWN/null/N/A`；无约束失败为 `NOT_APPLICABLE`，不会伪装成 0%。显式手工数字仅以 `DECLARED` 来源进入统计。`--rebuild` 重建项目累计遥测时，缺少 `status` 字段的 v1.33 及更早 run 按历史可信输入兼容聚合；显式 `UNKNOWN/NOT_APPLICABLE` 仍不得计入关键指标。

> 📖 完整采集命令、4 层 9 维指标体系、核心指标公式与健康阈值详见 **[references/telemetry_collection.md](references/telemetry_collection.md)**。

### 4. 查看遥测大屏

`collect_telemetry.py` 自动生成内嵌数据的 HTML，双击即可（无需 server）。总览页 ⇄ 单次契约页双向跳转。

> 📖 详见 **[references/telemetry_collection.md](references/telemetry_collection.md#遥测大屏v1131-纯静态--无需-server)**。

### 5. 上下文工程：三层注入模型

L1 意图图谱（OA 会话级）→ L2 全局约束（共享）→ L2+ AI 编码规范（AS 任务级）→ L3 任务切片（收敛）→ Map Context（L0-L3 渐进增强）。`crop_context.py` 自动裁剪并注入双地图或单地图上下文，支持隔离验证、预算限制和 watch 模式。

> 📖 三层注入模型图、裁剪工作流、YAML 精简契约格式详见 **[references/context_engineering.md](references/context_engineering.md)**。

### 6. Harness Engineering：可执行约束护栏

`constraints.yaml` → `harness.py check --all` 一条命令完成全量门禁检查。门禁 G0-G8 直接从约束 `gate:` 标签聚合。支持按域/按门禁/NFR 检查、自动恢复、CI/CD 集成。

> 📖 引擎用法、constraints.yaml 格式、例外管理、CI/CD 集成详见 **[references/harness_engineering.md](references/harness_engineering.md)**。

### 7. LOOP Engineering：自我纠错与持续进化

> SCOPE-V 的 Evolve 是完整的**自我纠错→反思→进化**闭环。三层 LOOP 模型详见 **[references/loop_graph_engineering.md](references/loop_graph_engineering.md)**。

### 8. Graph Engineering：可编程的 Agent 组织架构

> 复杂任务应**显式定义为有向无环图（DAG）**。两层图模型、DAG 定义、Graph Engine 用法详见 **[references/loop_graph_engineering.md](references/loop_graph_engineering.md#graph-engineering可编程的-agent-组织架构)**。

> Graph × LOOP × Harness × Context 四维度形成完整的 Agent 治理闭环。

### 9. Verified Engineering：六维验证体系

| 优先级 | 验证工具 | 说明 |
|--------|---------|------|
| P0 | `verify_contract.py` | AC 逐条自动化验证（shell/http/db/assert） |
| P0 | `audit_evidence.py` | 证据包门禁完整性审计 |
| P1 | `verify_triangulation.py` | 图谱/契约/约束三方一致性 |
| P1 | `harness.py` NFR 扩展 | 安全/可靠性/可观测性扫描（7 个验证器） |
| P2 | `verify_rollback_safety.py` | 回滚前 DAG 安全性分析 |
| P2 | `verify_freshness.py` | 工件时效检测 |

> 📖 验证矩阵详解、NFR 验证器列表、SCOPE-V 验证集成点详见 **[references/verified_engineering.md](references/verified_engineering.md)**。

### 10. 遥测扩展框架（P2 — 待自动化）

> 4 个 P2 指标的度量框架、公式、健康阈值详见 **[references/telemetry_framework.md](references/telemetry_framework.md)**。

## 跨人、跨工具、跨模块协作（v1.8 新增）

> 3-4-3 不仅适用于单人单工具单项目，也适用于多人多工具多模块的大型项目。详见 **[references/multi_module.md](references/multi_module.md)**。

## Harness Engineering 六大支柱总览

| # | 支柱 | 核心问题 | 关键资产 |
|---|------|----------|----------|
| 1 | **上下文管理** | AI 应该看到什么？ | crop_context.py |
| 2 | **工具系统** | AI 能触达和操作什么？ | tools_manifest.yaml + audit_tools.py |
| 3 | **执行编排** | AI 应按什么顺序完成任务？ | work_graph.yaml + graph_engine.py |
| 4 | **状态与记忆** | AI 应该记住什么？ | reflect.py |
| 5 | **评估与观测** | 怎样判断 AI 做得对不对？ | collect_telemetry.py + verify_* |
| 6 | **约束与恢复** | AI 不能做什么，失败后怎样恢复？ | harness.py + constraints.yaml |

> 📖 六大支柱详细树状图、约束域分层说明详见 **[references/six_pillars.md](references/six_pillars.md)**。

## 🔴 批判性思维（Critical Thinking · v1.15 硬性 · 跨项目通用）

> **适用范围**：**所有**使用本 skill 的项目。OA 在 Specify / Constrain 阶段的**默认工作方式**——把模糊意图校准为可验证、可运营、成本合理的契约。
> **禁止**：「用户说了 → 我照做 → 完成」而跳过批判性思维。

核心原则、7 大可疑信号、挑战话术模板、反哺教训写法详见 **[references/critical_thinking.md](references/critical_thinking.md)**。

## Grill-Me 交互协议（HITL 提示词工程）

> HITL 不应是"甩一份完整文档让 IO 通读"，而应是**逐条引导 IO 决策，每次只问一个问题，并给出推荐的默认答案**。
> **叠加 v1.14**：先运用**批判性思维**校准可疑规则，再 Grill-Me 逐条确认——对所有项目一律生效。

详细协议格式、示例、关键规则、对话流状态机、HITL 触发条件见 **[references/critical_thinking.md](references/critical_thinking.md#grill-me-交互协议hitl-提示词工程)**。

## 人机分工：四类任务模型

> 不是按"介入程度"分（人工决策/审核/全自动），而是按**任务性质**分——每一类任务放到最擅长的执行者手上。

| 任务性质 | 谁做 | 典型场景 | 3-4-3 机制 |
|---------|------|---------|-----------|
| **1. 不可逆操作** | 人批 | 删除生产数据、修改生产配置、对外发布、大额资金操作 | HITL 触发 + Tools Manifest `requires_approval` + `BOUNDARY_DEPLOY` |
| **2. 价值判断** | 人决策 | 方案选型、风险偏好、内容风格取舍 | Grill-Me 协议（逐条确认 + 推荐默认值）+ IO 签署契约 |
| **3. 不确定验证** | 人审 | 逻辑审查、边界情况、上下文敏感检查 | 🆕 Evidence_Bundle §11.5 人工审查清单 |
| **4. 可自动化** | AI 做 | 测试执行、Git 操作、通知发送、数据预处理 | SCOPE-V 执行循环 + harness.py + verify_contract.py |

> **判定标准**: 每一类任务是否都被放到了最擅长的执行者手上？
> 不可逆的不自动、价值判断不推给 AI、不确定的不盲信测试、可自动化的不浪费人力。

## 约束优先级链

```
法律/安全约束 > 约束矩阵 > 已签署意图契约 > 实现便利性
```

任何例外只能由人类 IO 通过签署的书面批准授予。

## 禁止事项

- 不得修改已签署的 Intent_Contract.md
- 不得降低 Constraint_Matrix.md 中的门禁
- 不得通过删除、跳过或弱化测试获得通过
- 不得用 pytest 总耗时替代专用性能基准
- 任一 MUST 失败时，不得生成可上线结论
- **P0 验证未通过时，不得进入 HITL 签署**
- **证据包门禁覆盖不完整时，不得标记 Verify 完成**
- **契约过期（超过时效阈值）时，必须先重新签署再执行**
- **🔴 意图契约 Verify 完成后未运行 collect_telemetry.py 并给出结果摘要的，不得标记任务为"已完成"，证据包不得裁决 APPROVED**（v1.12）
- **🔴 批判性思维（跨项目）**：不得盲从 IO 第一句字面需求；遇歧义、激励过密、与北极星冲突、不可验证、安全过宽时须先挑战并给推荐默认，确认前不得实现（v1.15）
- **🔴 可移植性（v1.17）**：collect_telemetry.py 不得依赖作者机器路径；harness 调用前须自动检测 pyyaml 并引导持久 venv（`~/.agentic-agile-343/venv`），确保 skill 分发到任意机器后门禁可自动评估而非降级为 UNEVALUATED
- **🔴 契约前置（v1.18）**：不得在意图契约签署前开始编码实现。任何功能开发任务必须先完成 Specify（意图契约草稿）→ Constrain（约束矩阵）→ Grill-Me 决策确认 → **IO 显式签署（sign-off，OA 不得代签）**，然后才能进入 Orchestrate（编码）。注意：**Grill-Me 逐条确认 ≠ 契约签署**，签署是 IO 审阅完整契约后的独立显式动作。仅以下任务可豁免：纯查询/阅读/规划类任务、bug 修复（但需补 AC）、配置变更（但需补约束检查）
- **🔴 证据包强制（v1.18）**：任一功能任务 Verify 完成后，必须生成 Evidence_Bundle（至少包含 AC 验证结果 + 约束检查结果 + 遥测摘要），不得跳过。未生成证据包时任务不得标记为"已完成"，与 v1.12 遥测规则共同构成 Verify 收尾双门
- **🔴 意图图谱回写（v1.18）**：任务完成后必须回写意图图谱：(a) 新增模块/能力节点 (b) 遇到的教训 (c) 下一步迭代方向。跳过回写视为 Evolve 阶段未完成，任务不得关闭
- **🔴 遥测结果验证（v1.19）**：收尾门的遥测检查不只是"是否运行了脚本"，必须验证三件事：(a) `telemetry/runs/telemetry-T-XXX.json` 单任务文件存在 (b) `telemetry.json` 的 `meta.run_count` 比运行前增加 (c) `dashboard.html` 修改时间已更新。推荐使用 `quick_telemetry.sh` 一键完成
- **🔴 TDD 强制（v1.20）**：Orchestrate 阶段必须先写测试（Red），再写实现（Green），再重构（Refactor）。编码门检查"测试已先写且运行 RED"；验证门检查"测试 GREEN + AC 逐条验证通过 + test-total > 0"。AC 验证方式为 `shell:grep` 的条目不得超过总 AC 的 50%，至少一半必须用 `predicate:`/`http:`/`db:` 运行时验证
- **🔴 遥测数据真实性（v1.20）**：collect_telemetry.py 的 `--test-total`/`--test-passed` 参数不得手工编造。必须先运行 `npx vitest run`（Node 项目）或 `pytest`（Python 项目）获取真实测试数，再将结果传入。若项目无测试套件，`--test-total` 传 0 并在证据包中标注"TDD 缺口"
- **🔴 Bug 回溯（v1.20）**：任一任务标记"已完成"后发现的 bug，必须：(a) 归属到对应契约 T-XXX（b）重新采集该任务遥测（`--tasks-first-pass 0 --auto-healed 1`）（c）在证据包追加"事后 bug 记录"段（d）回写意图图谱教训。跳过回溯视为该任务首次成功率数据虚假
- **🔴 Token 用量实测（v1.21，v1.45.0 更新）**：`--token-usage` 不得人工估算。Skill 发布安装与 Dashboard 运行时共用 `tool_bootstrap.py`：首次将 `@geeeger/ocusage` 安装到 `~/.agentic-agile-343/tools/ocusage`，后续检测到私有可执行文件即直接复用，不再调用 npm。宿主工具通过 `AGENTIC_AGILE_HOST_TOOL`/`--host-tool` 标识，Token 客户端通过 `AGENTIC_AGILE_TOKEN_CLIENT`/`--token-client` 独立选择；累计快照不得冒充任务用量。禁止全局安装和 `npx --yes`；npm 不可用、项目匹配歧义或基线不兼容时保持 UNKNOWN/N/A。
- **🔴 依赖自包含（v1.22，v1.44.2 更新）**：skill 所有必需运行时依赖必须自包含。Python 侧仅当持久 venv 无法 `import yaml` 时执行一次安装；健康环境禁止重建、清空、升级 pip 或重复安装。`ensure_py_env.sh` 只能转发到 Python 原生 bootstrap，不得维护第二套生命周期逻辑。可选工具不得在正式工作流中隐式下载。
- **🔴 Skill 发布单一流水线（v1.44.2）**：版本字段必须由 `skill_release.py version` 单命令更新并校验，禁止手工逐文件补丁。发布只构建一次已排除私有目录的 staging；本地 Skill 从该 staging 原子替换，对外 ZIP 从同一 staging 生成并执行完整性校验，本地安装不得解压 ZIP。
- **🔴 显式签署·禁代签（v1.23）**：Grill-Me 决策确认**不等于**契约签署（sign-off）。OA 不得自行在契约中写入 `SIGNED`、IO 署名或"自动签署"标记；签署区 `IO（意图主理人）` 一行必须由 IO 本人填写并明确确认（回复「签署」或署名）。签署前不得创建业务代码（与 v1.18 契约前置一致）。`gate_check.py --gate pre` 会扫描"自动签署 / 代签 / OA 代"等标记并直接判失败，签署区缺失或 IO 未署名同样失败。
- **🔴 签署检测否定语境修复（v1.23.1）**：`gate_check.py` 的代签扫描不得裸匹配子串。当"OA 代 / 代 OA / 自动签署"等标记出现在**否定语境**（同一行含 非/禁止/不得/无/不/未/并非/not/no）时——如"**非 OA 代签**""**禁止 OA 代签**"——属反代签的正向说明，必须**放行**而非误报失败。避免 IA 为规避误报而被迫改写合法签署措辞。
- **🔴 C-QUAL-01 模板修正（v1.23.1）**：`Template_Constraints.yaml` 中 Node/vitest 项目的 check 不再写 `--coverage-reporter=json-summary`（vitest v2 不识别连字符写法）。正确写法为 `npx vitest run --coverage`，覆盖率阈值与 json-summary 在 `vitest.config` 的 `test.coverage` 配置；点号写法 `--coverage.reporter=json-summary` 亦可。否则命令报错会导致 C-QUAL-01 门禁**误判失败**。
- **🔴 既有项目 Recon（v1.25.0）**：既有项目应先只读 Recon，再生成 Intent Graph、约束和契约。Recon 必须区分 Baseline / Preserve / Unknown / Change Envelope，不得把推测伪装成事实或覆盖未跟踪用户文件。
- **🔴 风险驱动入口（v1.26.0）**：`cli.py init` 统一完成项目分类、既有项目 Recon、七域风险判断与最小工件规划；默认 dry-run，只有 `--apply` 写入，且绝不覆盖已有文件或自动签署契约。
- **🔴 门禁自身治理（v1.26.1）**：确定性的低风险门禁误报使用 `cli.py maintain` 和 `M-XXX` 维护记录闭环，不再建立业务补充契约。仅当业务范围、门禁强度、签署语义、权限和批准边界均明确不变时准入；任一项 Unknown 或发生变化必须 fail closed，升级为 IO 签署的 Amendment 或新契约。维护仍强制真实 RED→GREEN、全量回归、Maintenance Evidence、遥测和图谱教训。
- **🔴 风险驱动裁剪（v1.25.0）**：治理可依据证据自动升级；信息不足不得推荐低风险模式，高风险治理不得由 Agent 自动降级。Python TDD 门支持自动识别 pytest 或标准库 unittest 的真实 RED/GREEN。
- **🔴 任务级 Recon（v1.27.0）**：单人修改既有代码时，可通过 `cli.py recon task` 从目标文件发现直接依赖、引用/测试/公共入口候选并形成建议围栏。静态名称匹配不得冒充确定调用关系；动态导入、宏、条件编译、反射、IoC、JSP EL 与容器绑定必须保留 Candidate 或 Unknown。任务 Recon 默认只读，建议围栏不得自动获得授权效力。
- **🔴 双地图 Context Provider（v1.37.0）**：Recon 可选使用 IWE Document Map、codebase-memory-mcp Code Map 与 343 Trace Link，按 L0/L1/L2/L3 披露实际能力。任何 Provider 缺失、未授权、过期、冲突或不兼容都必须回退并保留 Unknown；不得自动安装、联网、回写地图、升级静态关系为运行事实或扩大正式 Change Envelope。
- **🔴 项目级地图默认增强（v1.38.0）**：Recon 默认优先消费项目内标准 Map artifact；缺失时仅对 CLI 可用 Provider 执行项目边界明确的持久化初始化。IWE 用项目内 `.iwe`，codebase-memory-mcp 使用 `index_repository --repo-path <PROJECT> --persistence true`。构建成功不等于已归一化或已形成 L3；Trace Link 必须有稳定 ID 和来源，语义猜测不得晋升 VERIFIED。失败回退 L0，禁止自动安装、全局配置写入、项目外持久化或权限升级。
- **🔴 正式验证事实链（v1.39.0）**：`formal_verification` 是追加式事实源；`VERIFIED` 才计入完整完成，`CONDITIONAL` 必须有条件且不计完整完成，`BLOCKED` 不计完成。首次成功率只读取每个任务的首次正式验证结果，禁止用后续 VERIFIED 覆盖历史首次结果；`0/0` MUST 通过率为 NOT_APPLICABLE。
- **🔴 Change Envelope 门禁（v1.27.1）**：存在正式 `governance/Change_Envelope.yaml` 时，prove 门必须检查 staged、unstaged、untracked、删除与 rename 的新旧路径。只有 task 匹配、状态 AUTHORIZED、allowed 非空且 Unknown 为空的围栏有效；protected 优先，任何越界或解析失败均阻断。禁止自动授权、自动扩围或提供跳过参数。
- **🔴 Preserve 特征基线（v1.28.0）**：Agent 不得自动发明既有行为。只有 IO confirmed 或 existing test 来源、AUTHORIZED、Unknown 为空的基线可 capture；命令必须为参数数组且 shell=False。CAPTURED 基线存在时 prove 门强制复验，CHANGED/UNVERIFIABLE 均阻断；SAME 不替代新需求 AC。
- **🔴 维护兼容修复（v1.28.1）**：`quick_telemetry.sh` 必须识别纯 unittest 项目的真实测试总数与通过数；新增 YAML 消费工具必须复用 `_bootstrap.ensure_yaml_available()`，不得在首次缺少 PyYAML 时破坏自包含承诺。
- **🔴 安全变更统一入口（v1.29.0，v1.45.0 收口串联）**：`cli.py change` 仅负责编排现有能力，不得复制或弱化下层门禁。计划默认 dry-run、apply 不覆盖；状态必须从当前工件重算，不信任自报；禁止自动签署、自动授权围栏、自动决定 Preserve 或运行实现命令。`change verify` 在 Prove gate 通过后必须连续完成 `evidence finalize`、Intent Graph 反馈和 Closing Gate；若任一步失败必须 BLOCKED，全部成功才返回 CLOSED。
- **🔴 自然语言能力路由（v1.32.0）**：v1.25—v1.32 能力统一增加 `RELEASE_MANIFEST` 路由。用户不需要治理编号或 CLI；准备发布、制品证据绑定、记录已发布和回滚事实必须进入发布清单，且不得把自然语言请求当成发布授权。
- **🔴 Bug 修复入口（v1.30.3）**：自然语言“这是一个 Bug……请修复”即可触发候选调查；用户无需提供 B/T 编号或运行 CLI。Agent 自动发现父任务与下一个 B-ID，但证据不唯一时必须只追问一个关键问题，禁止猜测。B-XXX 必须关联已签署父契约及其不可变收尾证据；只有 implementation_regression 可进入 BUG_FIX。状态严格按 REPORTED→CLASSIFIED→RED→VERIFIED→CLOSED 推进；修复验证后先用 `bug telemetry` 独立记录 first_pass=0，再由 bug gate 关闭，原任务遥测不得覆写。
- **🔴 多层验证与无效全绿（v1.31.0）**：Verification Plan 按 proof obligation 与风险选择必要层级，不默认堆满测试。DRAFT 不得自动授权；正式计划存在时 prove 门强制检查项目内、可解析、任务匹配且未过期的证据。缺少 required layer、实际独立性不足、同一来源复制改名、关键结论仅靠 LLM-as-Judge、HUMAN_ACCEPTANCE 由 AI/OA 代签，或 UNKNOWN/CONDITIONAL/ESCALATED 被压成绿色，均禁止 PASS。
- **🔴 携证发布（v1.32.0）**：Release Manifest 将任务契约、Git commit、制品 SHA-256、配置、Evidence Bundle、Telemetry、Verification Plan、批准与回滚绑定为可复验谱系。READY 只表示可交给人类发布决策，不等于 RELEASED。Agent 不得执行 Tag、push、上传、部署或生产写入；发布和回滚只能用追加事件记录已经发生的外部事实。
- **🔴 SCOPE-V 控制面（v1.33.0）**：SCOPE-V 固定为六个持续控制面 `S / C / O / P⇄E / V`。Prove 与 Evolve 形成快内环；Telemetry 是 `V → Telemetry → S/C/O` 慢外环的反馈证据。五道门只裁决控制状态转换，不增加线性阶段，也不得因概念对齐削弱既有检查。
- **🔴 Evidence 遥测收口（v1.34.0，v1.36.2 更新）**：单任务 Evidence Bundle 完成后，推荐入口 `cli.py change verify` 必须在 Prove gate 通过后自动运行 `evidence finalize`。入口先验证契约/任务归属、AC 结果和约束结果，再调用 Python 原生 `telemetry_workflow.py` 生成单任务遥测、项目累计遥测、项目 Dashboard 与 `dashboard-T-XXX.html`；P0 指标由 `telemetry_tracker.py` 和 `collect_telemetry.py` 基于事实读取/派生，入口不得自动填写事实、代签或批准 Evidence；closing gate 继续只读。
- **🔴 遥测测量契约（v1.35.0，v1.36.1 兼容修复）**：目标准确率、首次成功率和约束自愈率必须绑定 `value/status/source/evidence/measured_at`。签署契约与合格 Evidence 提供 assigned/completed；首次正式验证及约束失败—Agent 修复—复验链来自追加式事件账本。UNKNOWN 不等于 0，NOT_APPLICABLE 不等于失败；项目聚合排除未知并披露覆盖率，证书关键指标未知时返回 INSUFFICIENT_DATA。`--rebuild` 对缺少 `status` 字段的 v1.33 及更早 run 保持兼容并按旧格式可信计数；显式 UNKNOWN/NOT_APPLICABLE 仍不聚合。`evidence finalize` 调用 Python 原生遥测主流程，`.sh` 仅为 Unix 包装器。
- **🔴 Windows 原生命令契约（v1.36.0）**：核心 Python 路径不得使用 `shell=True`、固定 `bash -c`、固定 Unix venv 路径或默认 POSIX 工具链制造绿色。默认约束、恢复动作、Intent Contract AC、测试生成、self-consistency、Telemetry/Token 入口和门禁内部命令必须优先使用结构化 argv 或 Python 内建检查；用户自定义 Shell 必须显式声明方言和平台，未知或缺失时 fail closed。

## 🔴 强制检查门（v1.18 新增，v1.20 重构）

> 以下五道门是控制状态转换的机械裁决点，不是五个额外阶段。**每个门由 `gate_check.py` 验证当前证据是否足以进入目标状态，不可自报通过。**

```
SCOPE-V:  S / C / O / P⇄E / V
快内环:              P ⇄ E
慢外环:  V → Telemetry → S/C/O

pre:      S+C READY → O ELIGIBLE
coding:   O PLANNED → O RED_CONFIRMED
prove:    P⇄E EVIDENCING → V ELIGIBLE
closing:  V VERIFIED → FEEDBACK CAPTURED
bug:      CLOSED FACT → S/C/O/P⇄E REENTRY
```

### 前置门（Orchestrate 前 — SDD 完成，编码开始前必须通过）

```bash
python scripts/gate_check.py --gate pre --task T-XXX --project-dir .
# 机械检查: 契约文件存在 + 已显式签署（IO 真实署名，非 OA 代签） + 约束矩阵存在 + AC shell:grep ≤50%
```

### 编码门（Orchestrate 开始时 — TDD Red，写实现前必须通过）

```bash
python scripts/gate_check.py --gate coding --task T-XXX --project-dir .
# 机械检查: 测试文件存在 + vitest 运行有 RED（测试存在但未全绿 = 实现未写完）
```

### 验证门（Prove 阶段 — TDD Green，标记 Verify 前必须通过）

```bash
python scripts/gate_check.py --gate prove --task T-XXX --project-dir .
# 机械检查: vitest 全绿 + test-total>0 + 证据包含 AC 结果 + tsc 编译通过
```

### 收尾门（标记"已完成"前必须通过 — 证据与度量）

```bash
python scripts/gate_check.py --gate closing --task T-XXX --project-dir .
# 机械检查: 证据包存在 + 单任务遥测文件存在 + runs 含本任务 + dashboard 1小时内更新 + 图谱含本任务
# 推荐完成入口：Prove 通过后自动执行 evidence finalize 并生成双 Dashboard
python scripts/cli.py change verify --task T-XXX --project-dir .
# 底层诊断/补跑入口:
python scripts/cli.py evidence finalize --task T-XXX --project-dir .
```

### Bug 回溯门（v1.20 — 任务"已完成"后发现 bug 时触发）

```bash
python scripts/gate_check.py --gate bug --task T-XXX --project-dir .
# 机械检查: 证据包含 bug 记录 + 遥测 first_pass=0 + 图谱含 bug 教训
```

## 多人多模块协作：端到端使用流程

> **何时需要**: 项目 ≥2 个模块、或 ≥2 个人、或 ≥2 种 AI 工具。
> **何时不需要**: 单人单模块 — 忽略此章节，直接按 §1-10 操作。

详细流程（全局 OA 初始化 → 模块 OA 启动 → 并行开发 → 集成测试 → 证据聚合与发布裁决）见 **[references/multi_module.md](references/multi_module.md)**。

## 参考资料

- 门禁自身治理与维护通道：**[references/maintenance_channel.md](references/maintenance_channel.md)**
- 既有代码任务级 Recon：**[references/task_recon.md](references/task_recon.md)**
- 自然语言能力路由：**[references/natural_language_routing.md](references/natural_language_routing.md)**
- 风险驱动多层验证：**[references/verification_planning.md](references/verification_planning.md)**
- 单项目携证发布：**[references/release_manifest.md](references/release_manifest.md)**

- 《Agentic Agile智能体敏捷：从氛围编程到验证工程的AI研发治理指南》v1.6，王立杰 (c) 2026 CC BY 4.0
- 实战验证项目：费用报销规则引擎（Intent_Contract.md + Constraint_Matrix.md + Evidence_Bundle.md）

## 关于作者

**王立杰，AI治理架构师，资深研发效能顾问**，工信部研发效能工程师认证专家讲师、PMI-ACP授权讲师、企业级规模化敏捷SAFe认证咨询师(SPC6)，曾任京东首席敏捷创新教练、IBM客户技术专家、DNV高级咨询师等，帮助小米IT信息部、OPPO内容产品中心、海康威视、京东方CTIO、吉利亿咖通、晓羊教育集团、中远海运租赁、京东购物APP、京东到家、招商银行、工商银行等组织实现研发效能提效。畅销书《敏捷无敌》、《京东敏捷实践指南》作者，江湖人称"**无敌哥**"。

### 教授经典课程

- **《Agentic Agile/智能体敏捷：AI时代研发治理沙盘实战课》**
- **《Agentic AI 项目管理：企业项目管理的人机协同新范式》**
- **《AI时代研发治理与领导力：从"驭人"到"驭智"高管研修班》**
- 《OpenClaw 创想家：从创意到产品的沉浸式工作坊》
- 《乌托邦计划沙盘：跨部门协同与高效项目管理特训营》
- 《敏捷项目管理实战沙盘演练》
- 《DevOps黑客马拉松》
- 《创新设计思维Design Thinking》
- 北大光华管理学院/新华都商学院《创业机会分析与识别》
- 京东大学《京东创新之路》、《从0到1商业模式快速探索》

曾经提供培训与咨询的企业包括宝马、博世、吉利、上汽、广汽传祺等车企，百度、京东、小米、Oppo、微博、360、58同城、美团等互联网企业，中国移动、联通、Agilent、IBM、阿朗、爱立信、诺基亚、东软、华为等传统电信/IT/软件企业，招商银行、工商银行、中信银行、中国银行、山东城商行等金融企业，E人E本、长虹、海尔、美的等白电企业，海天建筑、同方威视、中大医疗等传统行业；曾经在"AgileChina敏捷中国、RSG、51CTO、MPD、质量竞争力大会/TiD"等大会做过多次演讲，被评为质量竞争力大会/TiD 2014最受欢迎10大讲师；**目前专注于企业AI组织转型、研发效能提升、企业产品创新。**

### 联系无敌哥

- 官网：http://agentic.iloveagile.me/about
- 微信：iloveagile
- Email：3433839@qq.com
