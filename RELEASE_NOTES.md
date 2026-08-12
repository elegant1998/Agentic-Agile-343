# 发布说明 · Release Notes

> 🌐 English version: [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

# Agentic Agile 3-4-3 治理架构 · 开源版 v1.42.0

> **先校准、再打怪。** 这是完整、可运行的 Agentic AI 研发治理框架——全部开源，无保留。让 AI 研发治理，进可攻退可守。

- **版本**：`1.42.0`
- **发布日期**：2026-08-12
- **许可证**：代码/模板 MIT · 白皮书 CC BY 4.0
- **作者**：王立杰（无敌哥），AI 治理架构师

## v1.42.0：Map-first Recon 与长期治理数据增量化

- IWE 与 codebase-memory-mcp 查询增加条目、Token、字节和阶段超时预算，禁止完整地图导出。
- Task Recon 优先读取地图候选；无地图时只执行一次有界 `rg` 回退，并排除 Provider 数据库与缓存。
- 地图 shared/local、fresh/stale/damaged 状态具备明确消费、重建、降级和恢复建议。
- JSONL 事件账本增加可重建 SQLite 侧索引；项目遥测把聚合事实写入稳定 run 摘要，不再反复打开历史 run 文件。
- Evidence finalize 改为 prepare 后一次最终持久化，不再生成中间项目 Dashboard。
- 12,000 文件 Map-first、10,000 事件和 10,000 run 摘要规模回归纳入自动化预算。

## v1.41.0：治理运行时去重与共享项目快照

- Gate、Harness、Telemetry 统一消费 `TestExecutionPlan`，Verification Context 记录实际 argv 并校验完整性。
- `nfr:test_run` 复用可信 Verification Run Context，不再经 Harness 隐性重跑测试。
- 新增工作流级 `ProjectSnapshot`，复用文件清单、Git revision 和源码摘要。
- Harness 多项 NFR 共用源码清单与内容缓存；12,000 文件五项扫描基准由约 2.96 秒降至约 0.59 秒。
- Crop Context 只构建一次地图上下文，并在进程内调用代码发现器；当前项目基准由约 0.81 秒降至约 0.04 秒。

## v1.40.1：Evidence 收口性能治理

- 消除 collector 内部 `harness tests` 隐性重复执行，可信 Verification Run Context 成为唯一测试快照。
- formal_verification 后改为 metrics-only refresh，不再执行完整遥测工作流。
- 增加写权限预检、阶段进度和 elapsed_ms，避免失败后整条重跑与长时间静默。
- 调度披露外层、内部及总测试执行/复用次数。

## v1.40.0：原生双地图适配与 Agent 上下文自动注入

- Recon 将 IWE 和 codebase-memory-mcp 的结构化查询结果归一化为确定性标准地图工件。
- `crop_context.py` 默认注入有界的 L0-L3 Document Map、Code Map、Candidate Trace Link 与 Unknown。
- 团队模式优先消费 `authority: ci` 快照，本地缺图时仅生成 `.local` 回退，不覆盖共享地图。
- Provider 过期、损坏或查询失败时披露影响与人工恢复建议，继续安全降级。
- **官网**：<http://agentic.iloveagile.me/about> · 微信 `iloveagile`

---

## v1.38.0 变更

- T-139：项目 Recon 默认发现并消费项目内双地图；工具可用而地图缺失时，按项目边界初始化 IWE，并使用 codebase-memory-mcp 的持久化项目索引。
- 双地图归一化后自动生成需求—代码—测试 Trace Link；语义猜测保持 Candidate/Unknown，不冒充 VERIFIED。
- 增加 `--no-auto-context` 与 `--persistence true|false`；任何 Provider 失败继续回退 L0，不自动安装、修改全局配置或写入项目外目录。

## v1.39.0 变更

- T-140：新增 `formal_verification` 追加式事实事件，区分 `VERIFIED`、`CONDITIONAL` 与 `BLOCKED`。
- 首次正式验证结果不可被后续验证覆盖；首次 `CONDITIONAL` 后续转 `VERIFIED` 时，首次成功率保持 0。
- `must_total=0` 时通过率改为 `NOT_APPLICABLE/N/A`，不再把 0/0 显示为 100%。

## v1.39.1 变更

- T-141：引入 Verification Run Context，复用同一项目/revision/argv 的可信测试结果，避免 Prove、Evidence 和二阶段遥测重复执行全量测试。
- context 缺失、源码或命令变化、项目不匹配、过期或摘要不可信时自动重跑，并在遥测中披露执行/复用次数和原因。

## v1.37.0 变更

- T-138：Recon 新增可选 Context Provider，推荐 IWE 负责 Document Map、codebase-memory-mcp 负责 Code Map，由 343 归一化 Trace Link。
- 支持 L0-L3 渐进增强、Agent 宿主能力披露与项目内 JSON/YAML 制品；无工具、格式异常、越界、冲突或 revision 过期时 fail closed 并回退 L0。
- 外部关系保留 provider、查询时间、revision、classification 与 evidence，默认不升级为运行事实；不自动安装、配置、联网、回写或扩大 Change Envelope。

## v1.36.2 变更

- 将 SCOPE-V 后半段从“Agent 记得调用”升级为工作流代码保证：`change verify` 在 Prove gate 通过后自动执行 `evidence finalize`，生成单任务遥测、项目遥测与双 Dashboard。
- `evidence finalize` 失败时 `change verify` 返回 BLOCKED，不再只输出推荐命令或声称 VERIFIED；新增回归测试覆盖自动收口与失败阻断。

## v1.36.1 变更

- 修复 `collect_telemetry.py --rebuild` 对 v1.33 及更早旧 run 的兼容断点：缺少 `status` 字段时按历史可信输入聚合，显式 `UNKNOWN/NOT_APPLICABLE` 仍跳过。
- 增加回归测试覆盖旧格式 run 聚合，T-137 完整回归 156/156 通过；`--rebuild` 实测不再返回 `INSUFFICIENT_DATA`。

## v1.36.0 变更

- T-137：新增 `scripts/command_runner.py` 统一命令执行契约，默认 argv + `shell=False`，Shell 必须显式声明 `powershell` / `cmd` / `posix` 方言。
- `_bootstrap.py` 改为 Python 原生 venv/pip 自举，正确区分 Windows `Scripts/python.exe` 与 Unix `bin/python`；Bash 不再是依赖安装前置条件。
- 新增 `scripts/token_usage.py` 作为 Token 探测主实现；`.sh` 仅保留 Unix 包装，不可用时返回 UNKNOWN/UNAVAILABLE，不伪造估算。
- `gate_check.py`、`harness.py`、`verify_contract.py`、`self_consistency_check.py` 和默认模板迁移到结构化命令或 Python 检查，Windows 无 Bash 时 fail closed。
- 新增真实 `windows-latest` CI，覆盖 Python 3.10/3.11/3.12 专项与全量回归；`requirements.txt` 无增量。

## v1.35.0 变更

- T-136：新增 Measurement Contract 和追加式任务事件账本，五个 P0 原始计数统一携带 value/status/source/evidence/measured_at。
- UNKNOWN 不再计算为 0%，无约束失败使用 NOT_APPLICABLE；项目聚合排除未知并披露覆盖率，证书关键指标未知时返回 INSUFFICIENT_DATA。
- assigned/completed 从签署契约和合格 Evidence 派生；首次成功和自愈只接受正式验证事件及完整的失败—Agent 修复—复验链。
- 新增 Python 原生 telemetry_workflow.py；Evidence finalize 不再依赖 Bash，quick_telemetry.sh 仅保留 Unix 转发包装。
- 手工 P0 数字必须显式声明 --p0-source declared；不再硬编码 1/1/1/0/0，也不再用估算 Token 冒充测量值。

## v1.34.0 变更

- T-135：新增 `cli.py evidence finalize`，将单任务 Evidence Bundle 的完成收口与遥测采集建立为一个原子入口。
- Agent 完成 `EB-T-XXX.md` 后无需等待用户提醒，自动复用 `quick_telemetry.sh` 运行真实测试、Harness、Token 实测与 `collect_telemetry.py`。
- 成功必须同时生成单任务遥测、项目累计遥测、项目 Dashboard 与 `dashboard-T-XXX.html`；缺失、重复 task、脚本失败或 Evidence 被改写均 fail closed。
- 同一任务重复 finalize 保持幂等，项目 `runs[]` 不产生重复索引；Evidence 的签署与批准保持人类边界。
- closing gate 继续保持只读，不在检查阶段隐式产生测试、遥测或文件写入。
- 新增 9 项专项测试；完整回归 121/121 通过，`requirements.txt` 无增量。

## v1.33.0 变更

- T-134：SCOPE-V 统一为六控制面 `S / C / O / P⇄E / V`，不再把 Telemetry 与六个控制面并列。
- Prove 与 Evolve 形成证据驱动的快内环；`V → Telemetry → S/C/O` 形成反馈到意图、约束和编排的慢外环。
- `gate_check.py` 为 pre/coding/prove/closing/bug 提供唯一控制状态映射和解释性输出，保持五道门现有检查强度、CLI 与退出码。
- 三大自治运行机制明确为横跨六控制面的治理机制，不与单一阶段机械绑定。
- 新增 6 项概念与接口专项测试；完整回归 112/112 通过，`requirements.txt` 无增量。

## v1.32.0 变更

- T-127：新增 `release plan/check/status/record` 与 Release Manifest 模板，绑定任务契约、Git commit、制品 SHA-256/大小、配置、Evidence Bundle、Telemetry、Verification Plan、批准与回滚。
- 实现 Build Once, Verify Once, Promote Many 最小语义；制品、提交、配置、任务证据或 promotion 摘要漂移会使旧 READY 失效。
- 就绪裁决固定为 `READY_FOR_HUMAN_RELEASE`，不自动标记 RELEASED；Agent 不执行 commit、Tag、push、构建、上传、部署或生产写入。
- released / rolled_back 仅通过项目内外部证据和合格 actor 追加记录；重复事件幂等，旧事件及源码制品绑定不可覆写。
- 新增 `RELEASE_MANIFEST` 自然语言路由和携证发布指南；专项测试 16/16，新增模块标准库实测行覆盖率 90%。
- 完整回归 106/106 通过；requirements.txt 无增量。

## v1.31.0 变更

- T-126：新增 `verification plan/check/status` 和 Verification Plan 模板，按 low / medium / high / safety-critical 风险选择必要验证层与最低证据独立性，不默认堆满测试。
- 机械识别缺层、缺证据、同源复制、独立性不足、过期/错任务证据、路径攻击、LLM 独证以及 AI 代签 HUMAN_ACCEPTANCE 等“无效全绿”。
- 保留 PASS / FAIL / UNKNOWN / CONDITIONAL / ESCALATED；CONDITIONAL 必须声明条件、责任人、截止时间和复验动作。
- 正式计划存在时自动接入 prove 门；无计划项目保持兼容。计划默认 dry-run，apply 只创建 DRAFT 且不覆盖，不执行任意命令。
- 新增自然语言 `VERIFICATION_PLAN` 路由、参考指南和 12 项专项测试；完整回归 90/90 通过。

## v1.30.3 变更

- M-007：统一补齐 v1.25—v1.30 的自然语言能力路由矩阵。
- frontmatter 覆盖项目 Recon、风险入口、门禁维护、任务 Recon、Change Envelope、Preserve、安全变更和 Bug 八类用户表达。
- 新增冲突消解规则：最具体路由优先，缺证据先只读调查，只在无法唯一选路时追问一个问题。
- 将版本、作者等扩展字段迁入合法的 `metadata`，通过 Codex skill schema 校验。
- 新增路由 reference 与机械测试；完整回归 78/78 通过。

## v1.30.2 变更

- M-006：skill frontmatter 和触发场景加入 Bug、缺陷、回归、修复等自然语言触发词。
- 用户只需描述问题并说“请修复”，无需提供 B/T 编号或运行 CLI；Agent 自动发现父任务和分配 B-ID。
- 关联证据不唯一时只追问一个高信息问题；用户的 Bug 标签不能替代六类问题分类与真实 RED。
- 新增自然语言触发协议机械测试；完整回归 77/77 通过。

## v1.30.1 变更

- M-003：父任务完成态改由证据包、任务遥测与意图图谱共同证明，不再要求改写已签署契约。
- M-004：`bug verify` 仅接受具备真实 RED 证据的 RED 记录，`bug close` 仅接受 VERIFIED 记录。
- M-005：新增 `bug telemetry`，把修正运行独立写入 `telemetry-B-XXX.json`；Bug 门兼容旧数据但不再要求覆写原任务遥测。
- 三项均经真实 RED→GREEN、维护证据和完整回归验证；全量 76/76 通过。

## v1.30.0 变更

- 新增 B-XXX Bug Record 与 bug open/classify/reproduce/status/verify/close。
- 六类问题分别路由 BUG_FIX、契约、M 维护、环境调查或 IO 升级。
- 仅已完成父契约、AC/Preserve 可追溯、边界不变且真实 RED 的实现回归可直接修复。
- verify/close 复用 change verify 和既有 bug gate；新增 5 项专项测试，全量 73/73 通过。

## v1.29.0 变更

- 新增 `change plan/status/prepare/verify/close` 统一安全变更入口。
- plan 复用任务 Recon，默认 dry-run；apply 创建本地计划且不覆盖。
- 状态从契约、Unknown、围栏、Preserve 和机械门实时重算，每次只给一个下一步。
- prepare/verify/close 分别复用 pre/prove/closing，不复制或弱化门禁。
- 新增 5 项专项测试，全量 68/68 通过。

## v1.28.1 变更

- M-001：`quick_telemetry.sh` 现在识别纯 unittest 项目，并传递真实 test-total/test-passed；兼容 tests 包与普通目录。
- M-002：`change_envelope.py`、`characterize.py` 在缺少 PyYAML 时统一调用共享 bootstrap 后重试。
- 两项均通过维护通道准入、真实 RED→GREEN、Maintenance Evidence、遥测和关闭检查。
- 新增 2 项专项测试，全量回归 63/63 通过。

## v1.28.0 变更

- 新增 `characterize plan/capture/verify`，建立既有 Preserve 行为基线。
- Preserve 必须由 IO 或现有测试确认；禁止 Agent 自动发明断言。
- argv 数组、shell=False、超时上限、敏感输出拒绝和配置指纹共同约束安全执行。
- 输出 SAME / CHANGED / UNVERIFIABLE；CAPTURED 基线自动接入 prove 门。
- 新增 7 项专项测试，全量 61/61 通过。

## v1.27.1 变更

- 新增 `cli.py envelope check`，机械比较正式 Change Envelope 与 Git 实际变更。
- 覆盖 staged、unstaged、untracked、删除和 rename 新旧路径。
- protected 优先于 allowed；Unknown、DRAFT、任务不匹配、路径攻击和 Git 故障均 fail closed。
- 存在正式围栏时自动接入 prove 门；无围栏项目保持兼容。
- 不提供 force/skip/自动扩围；新增 9 项专项测试，全量 54/54 通过。

## v1.27.0 变更

- 新增 `python scripts/cli.py recon task`，将既有项目 Recon 从项目级清点推进到具体任务影响侦察。
- 发现目标、直接本地依赖、引用/测试/公共入口候选，并严格区分 Fact / Candidate / Unknown。
- 轻量覆盖 Python、JavaScript/TypeScript、C/C++、Java/JSP，基础支持 Go、Rust、Shell；未支持语言安全降级。
- 路径缺失、目录目标和项目外目标一律 fail closed；默认只读且仅输出 stdout。
- 建议 Change Envelope 固定标记 `DRAFT_NOT_AUTHORIZED`，不得替代 IO 签署或自动扩大权限。
- 新增 8 项跨语言与边界专项测试，全量回归 45 项通过，不新增第三方依赖。

## v1.26.1 变更

- 新增 `cli.py maintain open/check/close` 门禁自身治理通道。
- 低风险机械缺陷使用 `M-XXX`，不再反复创建业务补充契约。
- 六项准入必须全部明确通过；Unknown、门禁弱化、签署语义和权限变化一律升级为契约。
- 强制真实 RED→GREEN、全量回归、Maintenance Evidence、遥测与图谱教训。
- 命令以参数数组且 `shell=False` 执行；命令缺失或不可执行不得冒充 RED。
- 新增 12 项本地专项测试；治理记录和测试继续排除在公开包之外。

## v1.26.0 变更

- 新增统一风险驱动入口 `python scripts/cli.py init`，默认 dry-run，只有 `--apply` 写入。
- 自动识别 new / existing-small / legacy-complex / multi-module；既有项目自动执行只读 Recon。
- 评估 intent / context / data_privacy / tools / execution / verification / organization 七域风险，Unknown 禁止降级。
- 按 explore / delivery / high-risk / legacy / multi-module 生成最小治理计划；不覆盖已有文件，契约保持 PENDING。
- 修复签署门的否定语境识别：非目标和禁止事项中的“自动签署”不再误报，真实代签仍被阻断。
- 新增本地 TDD 回归测试；`governance/` 与 `tests/` 均不进入公开包。

## v1.25.0 变更

- 新增既有项目轻量 Recon：Baseline / Preserve / Unknown / Change Envelope。
- 新增风险评估与五种治理模式推荐，信息不足时禁止自动降级。
- 新增 `recon`、`assess-risk` 两个统一 CLI 子命令。
- 新增 3 个模板，当前共 27 个脚本、16 个模板、10 篇参考。
- Python TDD 机械门可自动识别 pytest 或标准库 unittest 的 RED/GREEN。
- Skill 绑定《Agentic Agile智能体敏捷：从氛围编程到验证工程的AI研发治理指南》v1.6。
- 本版本不创建 Tag、不执行发布。

---

## 一、TL;DR

本版起**不再区分社区版/完整版**——直接开源最强版。从意图契约到证据闭环、从 5 道机械门禁到 4 层 9 维遥测，全部开箱即用。

## 二、v1.24.0 变更（相对 v1.0.0-community）

| 类别 | 变更 |
|---|---|
| 🔄 定位 | 从"社区版（有意缺失）"升级为**完整开源版**，不再保留缺口 |
| ➕ 新增脚本 | `gate_check.py`（5 道机械门）、`audit_evidence.py`、`collect_telemetry.py`、`fetch_token_usage.sh`、`quick_telemetry.sh`、`crop_context.py`、`graph_engine.py`、`audit_tools.py`、`verify_*.py`（triangulation/rollback/freshness/cross_module）、`reflect.py`、`aggregate_evidence.py`、`discover_context.py`、`self_consistency_check.py` 等（共 25 个脚本） |
| ➕ 新增模板 | `Template_Evidence_Bundle.*`、`Template_Tools_Manifest.yaml`、`Template_Protocol.yaml`、`Template_Module_Governance.md`、`Template_Work_Graph.yaml`、`Template_Loop_Memory.yaml`、`Template_AI_Coding_Guide.md`（共 13 个模板） |
| ➕ 新增参考 | `references/` 扩到 9 篇（含 harness/loop_graph/telemetry/multi_module/verified/context 等） |
| ➕ 仪表板 | `assets/dashboard.html` 遥测大屏（纯静态，双击即看） |
| ✂️ 删除 | `build_community_ed.sh`（不再需要剥离） |
| 🐛 修复 | v1.23 禁代签：Grill-Me 决策确认 ≠ 契约签署，`gate_check.py` 反代签检测；v1.23.1 否定语境修复 |
| ✏️ 元信息 | description 精简为一句话；"联系无敌哥"加官网 |

## 三、本版包含

见 [README.md §三](README.md#三本版包含什么全部开源无保留)——25 脚本 / 13 模板 / 9 参考 / 仪表板 / 白皮书 / 示例。

## 四、环境要求

- Python 3.10+（缺 PyYAML 时由 `_bootstrap.py` 用 Python 原生 venv/pip 自举）
- Node / npx 可选（用于 `token_usage.py` 调用 `@geeeger/ocusage` 实测 Token；缺失则指标 UNKNOWN）
- 无外部服务、无联网依赖、无需 API Key

## 五、快速开始

```bash
# 1. 准备环境（Bash 不是必需项）
python scripts/cli.py list

# 2. 初始化项目治理
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml

# 3. SCOPE-V 循环 + 5 道机械门禁（硬拦截）
python scripts/gate_check.py --gate pre --task T-001 --project-dir .
python scripts/verify_contract.py --task T-001 --project-dir .
python scripts/harness.py check --all
python scripts/cli.py evidence finalize --task T-001 --project-dir .
```

更完整说明见 [`README.md`](README.md)。

## 六、从旧社区版升级

- 旧社区版（v1.0.0-community）用户：直接用本版覆盖 `scripts/`、`templates/`、`references/`、`assets/`、`SKILL.md` 即可，你已有的 `governance/` 契约与约束矩阵无需重建。
- `build_community_ed.sh` 已移除，不再需要。

## 七、已知限制（Honest Caveats）

1. **示例单一**：目前仅 `T-001` 一个中性示例，欢迎 PR 补充更多场景。
2. **Token 实测依赖 ocusage**：`token_usage.py` 会通过 npx 调用 `@geeeger/ocusage`；不可用时返回 UNKNOWN/UNAVAILABLE，不回退伪造估算。
3. **多人多模块**：`protocol.yaml` 与模块治理面向复杂项目，单人项目可忽略。

## 八、许可证

- 代码与模板：**[MIT](LICENSE)**
- 白皮书：**[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**（转载/二次创作请署名 王立杰-无敌哥）

## 九、下一步

- 📘 读白皮书，理解 3-4-3 的理论基石与成熟度模型（L1–L4）
- 🎓 报名进阶课程 / 内训，把"会用"变成"用好"
- ✍️ 在官网签署《Agentic Agile 宣言》，加入先锋社区
- 🤝 想贡献？看 [`CONTRIBUTING.md`](CONTRIBUTING.md)

> 工具全开源，但"会用"与"用好"之间隔着体系化学习与企业场景陪跑——这正是课程与内训的价值所在。
