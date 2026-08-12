# Agentic Agile 343 ROADMAP



结论：`agentic-agile-343` 目前已经能很好地支撑“单任务治理闭环”，但最新版图书已经明显扩展为“从任务到交付、知识、组织和风险治理的完整系统”。skill 必须从“模板和门禁工具箱”升级为“风险驱动的治理编排器”。

另外，当前书稿在 Git 中仍是未跟踪文件，所以无法精确还原“最近每一次修改”；以下结论基于最新版书稿快照与 skill v1.24.0 的完整对照。

## P0：必须优先增强

### 1. 增加风险识别与治理模式自动裁剪

书中已经明确：

- 探索型、交付型、安全关键型三类场景
- 低、中、高、安全关键四级风险
- 轻量模式与完整模式
- 治理强度随场景变化而升级

但 skill 当前入口基本是“一旦触发，就按同一套完整流程执行”，容易导致：

- 小任务治理过重
- 高风险任务治理不足
- 用户不知道何时应从轻量模式升级

必须新增：

- `Governance_Profile.yaml`
- `assess_risk.py`
- `init --profile explore|delivery|high-risk|legacy|multi-module`
- 风险变化后的自动升级规则
- 每个模式对应的最小工件、门禁、证据和 HITL 要求

这是最关键的增强，因为它决定 skill 能否真正跨场景使用，而不是只适用于标准功能开发。

------

### 2. 增加既有大型系统的 Change-Driven Governance

书中新增的遗留系统方法是当前 skill 最大能力缺口，包括：

- Recon：进入 Specify 前的认知侦察
- 业务能力、系统结构、变更影响三层地图
- Baseline / Preserve / Unknown
- Characterization Test
- Change Envelope
- 治理岛、邻接保护区、未知遗留区
- 变化覆盖率，而非全量代码覆盖率
- 两级或三级 OA

skill 当前的 `discover_context.py` 只能算代码结构发现，不能完成上述治理判断。

必须新增：

- `recon.py`
- `Template_Change_Envelope.yaml`
- `Template_Legacy_Baseline.md`
- `Template_Governance_Island.yaml`
- Characterization Test 生成与校验支持
- 变化覆盖率验证器
- Evidence Bundle 中的 `changed / preserved / unknown` 证据区
- `init --legacy` 工作流

否则 skill 面对真实企业存量系统时，仍然只能按新项目思路处理。

------

### 3. 把“多层验证”升级为可配置的验证计划

当前 skill 主要围绕：

- 单元测试
- AC 执行
- 编译
- NFR 扫描
- 证据完整性

但书中已经扩展为完整验证组合：

- 单元与组件
- 接口测试
- UI 用户旅程
- SIT
- 性能
- SAST / DAST
- 可靠性与数据验证
- UAT
- 生产验证
- LLM-as-Judge 边界
- 验证者独立性
- 同源误判
- Proof-Carrying Delivery

必须新增：

- `Template_Verification_Plan.yaml`
- 每条 AC 对应“证明责任”和验证层级
- 测试生成者、实现者、裁决者独立性字段
- `evidence_source`、`independence_level`、`freshness`、`confidence`
- `verify_independence.py`
- “无效全绿”检测
- UNKNOWN、CONDITIONAL、ESCALATED 等非二元裁决
- UAT 必须由业务责任人接受，禁止 AI 代签
- 生产验证与发布后证据回流

当前证据包已经开始记录独立性，但还没有形成机械门和完整验证策略。

------

### 4. 将五道门与 SCOPE-V 控制面彻底对齐

当前 skill 文档中仍存在概念滞后：

- 开头描述 SCOPE-V 为“七步循环”
- 书中已经把它定义成“六个持续运行的控制面”
- Telemetry 是 Verify 后进入慢外环的反馈系统，不应与六个控制面混成第七个阶段
- `gate_check.py` 实际已经有五道门，但主流程表述仍容易让人理解成线性瀑布

必须调整为：

```
S / C / O / P⇄E / V
        │       │
        └─ 快内环
V → Telemetry → S/C/O 慢外环
```

并让五道门分别检查“控制状态”，而不只是文件存在：

- 前置门
- 编码门
- 验证门
- 收尾门
- Bug 回溯门

还要明确：三大自治机制横跨 SCOPE-V，不是一种“一机制对应一阶段”的机械映射。

------

### 5. 增加 AI 原生交付流水线与 Release Manifest

书中已经从代码验证推进到了携证发布，而 skill 目前基本止于任务完成和证据包。

必须新增：

- `Template_Release_Manifest.yaml`
- 交付谱系：意图契约 → Commit → Build → Evidence Bundle → Release → Telemetry
- 分支、Worktree、Merge Queue 的隔离检查
- 文件所有权与语义冲突检测
- Build Once, Verify Once, Promote Many
- Tag、版本、配置、制品摘要的绑定
- 灰度、Feature Flag、条件批准
- 发布权限边界
- 回滚后的数据和配置兼容性验证
- 发布版本到任务契约的反向追踪
- CI 五道门示例

`aggregate_evidence.py` 可以继续复用，但输出应升级为“发布级 Evidence Bundle + Release Manifest”。

------

### 6. 增加 Knowledge Engineering 和 Memory Governance

当前只有 `Template_Loop_Memory.yaml` 和 `reflect.py`，距离书中新建立的知识与记忆体系差距很大。

必须覆盖：

- 五层知识体系：L0–L4
- 知识身份证：来源、版本、所有者、权限、时效、状态
- 知识状态机
- 知识晋升必须由外部证据支持
- 五类检索协同
- Knowledge Release
- 五类记忆与六级作用域
- Memory Write Gate
- 记忆状态机
- 记忆衰减、冲突、删除传播
- 防止上下文污染和未经验证记忆回灌

建议新增：

- `Template_Knowledge_Record.yaml`
- `Template_Memory_Record.yaml`
- `knowledge_ingest.py`
- `memory_gate.py`
- `verify_knowledge_provenance.py`
- `verify_memory_scope.py`
- `promote_knowledge.py`

其中最重要的规则是：

> Agent 不能因为“自己总结过”就把内容晋升为组织知识或长期记忆。

------

### 7. 建立真正的度量治理，而不只是遥测采集

当前 skill 擅长“采数并展示”，最新版图书进一步解决了“数字能不能相信、应如何解释”。

必须新增：

- Measurement Contract
- 主指标与反指标
- 领先、滞后、护栏指标组合
- 基线、分群、分布和样本量
- 指标所有者、计算方式、数据源、刷新周期
- 指标变更版本
- 数据质量门禁
- Goodhart 风险检查
- “信号 → 责任人 → 动作 → 截止时间 → 复验”的闭环
- 遥测系统自身的遥测

建议新增：

- `Template_Measurement_Contract.yaml`
- `validate_measurement.py`
- Dashboard 展示样本数、分母、时间窗、风险等级和估算/实测状态
- 禁止仅凭单一自治率、Token 数或 HITL 数量评价项目

尤其需要重新审视当前“成熟度证书资格”的总分逻辑：书中已经强调成熟度应按能力维度呈现，不能用一个平均分掩盖高风险短板。

------

### 8. 增强安全、隐私和 Agentic 风险治理

当前有 Tools Manifest、沙箱和部分 NFR，但最新版书中的风险体系已经更完整：

- 意图风险
- 上下文风险
- 数据与隐私风险
- 工具风险
- 执行风险
- 验证风险
- 组织风险
- Prompt Injection / Context Poisoning
- 模型、MCP、Memory、向量库和第三方工具的数据边界
- 供应链风险
- Agentic 事故响应

必须新增：

- `Template_Threat_Model.yaml`
- `Template_Data_Routing_Policy.yaml`
- `Template_Incident_Record.md`
- `threat_model_check.py`
- 第三方 Skill / MCP / 脚本来源、许可证、版本、权限、联网和敏感信息访问审计
- 数据生命周期：采集、注入、缓存、日志、遥测、证据、记忆、删除
- 事故时停止 Work Graph、撤权、隔离制品、保存证据、通知责任人和回溯的自动清单

尤其值得注意：当前 `fetch_token_usage.sh` 可以自动全局安装外部 npm 包，这与书中新强调的供应链治理存在冲突。自动安装前至少应校验来源、锁定版本、记录授权，并允许离线降级。

## P1：紧随其后的增强

### 9. 增强 Specify：Example Mapping、规格漂移和 AC 质量

必须增加：

- Example Mapping 模板：规则、示例、问题、范围
- AC 六要素质量检查
- Happy Path、边界、异常、权限、并发和恢复覆盖组合
- 自然语言 AC 的可执行等级
- 规格漂移识别
- “实现中发现事实”与“未经批准改变需求”的区分
- 漂移后的暂停、回流、重新签署和版本关联

建议新增 `check_spec_quality.py` 与 `detect_spec_drift.py`。

------

### 10. 强化 Work Graph，而不只把它实现成 DAG

书中已经明确：经常使用 DAG，但 Work Graph 不能只理解为 DAG。

节点还应包含：

- Agent 能力和权限
- 输入可信来源
- 输出契约
- 文件所有权
- 时间、Token、并发和重试预算
- Handoff 验证
- 互斥写入
- 失败分支
- 熔断和人工升级
- 停止条件

还应增加 Org Graph，让调度同时回答：

- 谁有能力做？
- 谁有权限做？
- 谁承担责任？
- 谁能批准？

------

### 11. 将 Evolve 从“反思记录”升级为受控演进

必须增加：

- 失败分类与回流路由
- 修复后必须重跑原始判据
- Failure Mining
- 规则债务和约束疲劳检测
- Champion–Challenger
- 演进预算
- 停止条件
- 记忆衰减
- 只有经过验证的变化才能写回图谱、约束、Skill 和知识库
- Agent Chaos Engineering

不能再把“写了一段 reflection”视为完成 Evolve。

------

### 12. 增加组织级落地与成熟度工作流

当前虽然有成熟度展示，但缺少真正的组织采纳流程。

必须补充：

- 分维度 L1–L4 成熟度画像
- 90 天试点契约
- 0–30、31–60、61–90 天三阶段门
- 基线与对照组
- 3–5 个、8–15 个任务的样本规划
- 扩大、受限继续、先补基础、停止四类裁决
- 治理委员会章程
- 团队运行节奏
- 治理资产的所有者、版本、迁移和淘汰机制
- 激励反模式
- 角色成长路径

建议增加：

- `Template_Pilot_Contract.md`
- `Template_Maturity_Profile.yaml`
- `Template_Governance_Committee.md`
- `assess_maturity.py`

## P2：体验与产品化增强

### 13. 建立统一 CLI 和场景化向导

目前脚本很多，但用户必须知道该调用哪一个。建议统一为：

```
agentic-agile init
agentic-agile assess-risk
agentic-agile recon
agentic-agile specify
agentic-agile gate pre
agentic-agile prove
agentic-agile evidence
agentic-agile release
agentic-agile telemetry
agentic-agile incident
agentic-agile maturity
```

入口先判断任务类型，再推荐流程，而不是让用户直接面对二十多个脚本。

### 14. 更新 skill 的触发词和资源路由

当前触发词仍偏向早期的 3-4-3 工件与遥测。至少应加入：

- 验证工程、多层验证、Proof-Carrying Delivery
- 既有系统、遗留系统、治理岛、Change Envelope、Recon
- 知识工程、记忆治理、Memory Write Gate
- 携证发布、Release Manifest、交付谱系
- 度量契约、反指标
- 风险分层、威胁建模、Agentic 事故
- 成熟度、90 天试点、治理委员会

同时，skill 头部仍写着“基于白皮书 v1.5”，已经不能准确描述当前这本书的范围，应改为绑定当前书名、版本或 commit/hash。

## 推荐升级顺序

不要一次把所有章节都搬进 skill。建议分四个版本：

1. **v1.25：风险驱动入口**
   - 风险评估
   - 轻量/完整/高风险/遗留模式
   - SCOPE-V 控制面表述修正
   - Example Mapping 与规格漂移
2. **v1.26：验证与交付**
   - 多层验证计划
   - 验证独立性
   - 无效全绿检测
   - Release Manifest
   - 携证发布
3. **v1.27：遗留系统与知识记忆**
   - Recon
   - Change Envelope
   - 治理岛
   - Characterization Test
   - Knowledge/Memory Write Gate
4. **v1.28：组织治理**
   - Measurement Contract
   - 分维度成熟度
   - 90 天试点
   - 治理委员会
   - 风险与事故响应

一句话概括这次升级方向：

> 旧 skill 主要保证“一个 AI 任务按规则做完”；新版必须进一步保证“它在正确风险等级下，由正确主体，使用可信知识和受控权限，产生独立证据，经携证发布后还能被组织持续治理”。

对照来源：[最新版图书](/Users/wanglijie/HappyLife/18-AI/Agentic-Agile/whitepaper/Agentic Agile智能体敏捷：从氛围编程到验证工程的AI研发治理指南.md)；当前实现：[SKILL.md (line 1)](/Users/wanglijie/.codex/skills/agentic-agile-343/SKILL.md:1)。