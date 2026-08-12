# 既有代码任务级 Recon

项目级 Recon 回答“这是一个什么项目”；任务级 Recon 回答“为了这次修改，哪些代码与风险值得先看”。它面向单人使用 Agent 修改既有代码的场景，默认只读，不运行项目代码。

## Document Map / Code Map 渐进增强（v1.37.0）

343 的内建扫描始终是 L0 基线。外部地图是可选增强：IWE 负责需求、规则、AC、ADR 和历史决策等 Document Map；codebase-memory-mcp 负责模块、符号、调用、路由和测试关系等 Code Map；343 负责用稳定 ID 归一化 Trace Link。

能力层级为：仅内建扫描 `L0`、Code Map `L1`、Document Map `L2`、双地图与 Trace Link `L3`。Agent 宿主已暴露 MCP 时可先查询，再把结构化结果交给 Recon；CLI 也可只读消费项目内显式 JSON/YAML 制品：

```bash
python scripts/cli.py recon task --task T-001 --target src/example.py \
  --context-provider governance/context/document-map.json \
  --context-provider governance/context/code-map.json \
  --project-dir . --format json
```

`--agent-provider IWE` 或 `--agent-provider codebase-memory-mcp` 只披露宿主可见能力，Python CLI 不伪装能够枚举或调用宿主 MCP。Provider 缺失、越界、格式不兼容或 Code Map revision 过期时，Recon 记录 Unknown 并回退；不会安装软件、修改 MCP 配置、联网或回写第三方知识库。

`--context-max-items N` 可限制每个 Context Slice 分区的条目数；`--no-context-recommendations` 可关闭可选安装建议。

Document Map 的 `DEPRECATED/EXPIRED/REVOKED` 条目默认排除，`CONFLICTED` 进入 Unknown。地图关系默认是 `CANDIDATE`，不能冒充运行事实、签署、Evidence、Change Envelope 授权或发布批准。L3 提高关系召回和上下文质量，但正确性仍由契约、测试、运行 Trace 与 Evidence 证明。

## 使用

```bash
python scripts/cli.py recon task \
  --task T-130 \
  --target scripts/recon.py \
  --project-dir .
```

可重复传入 `--target`。默认输出 Markdown 到标准输出；结构化输出使用 `--format yaml`（JSON-compatible YAML）。只有显式传入 `--output` 才写文件。

## 结果可信度

- **Fact**：文件存在、语言、直接 import/include/source 等可复核事实。
- **Candidate**：通过符号、名称、路径和测试约定发现的调用者、相关测试或公共入口候选。
- **Unknown**：动态导入、反射、IoC、宏、条件编译、JSP EL、容器映射和运行时行为。

Candidate 不是调用图事实。任务级 Recon 用于缩小阅读与验证范围，不能替代运行时测试、契约签署或 Change Envelope 门禁。

## 语言适配

| 语言 | 轻量发现 |
|---|---|
| Python | AST import、本地模块、符号引用、测试候选 |
| JavaScript / TypeScript | 相对 import/require、引用和 test/spec 候选 |
| C / C++ | include、头文件/实现文件配对、符号和测试候选 |
| Java | package/import、类引用、Maven/Gradle 测试候选 |
| JSP | include、taglib、Java 引用、Servlet/Controller 候选 |
| Go / Rust / Shell | 基础依赖声明、名称引用和常见测试候选 |
| 其他 | 文件级事实 + 明确 Unknown |

## 安全边界

- 目标必须存在、必须是文件且必须位于项目目录内。
- Recon 不修改源码、Git 索引或未跟踪文件。
- 输出的建议 Change Envelope 固定为 `DRAFT_NOT_AUTHORIZED`。
- 扩大允许范围必须更新契约并由 IO 重新签署。
- 未支持或无法确认的关系必须保留 Unknown，禁止用猜测补全。

## Change Envelope 机械门禁

T-130 的建议围栏没有授权效力。IO 审阅并建立正式 `governance/Change_Envelope.yaml` 后，将状态改为 `AUTHORIZED`，再运行：

```bash
python scripts/cli.py envelope check --task T-XXX --project-dir .
```

检查覆盖 staged、unstaged、untracked、删除和 rename 新旧路径。路径规则只支持精确文件和以 `/` 结尾的目录前缀，不执行 shell glob。

判定优先级：

```text
protected > allowed > outside
```

Unknown、DRAFT/PENDING、任务不匹配、空 allowed、路径穿越或 Git 不可用一律 fail closed。只有 Evidence、Telemetry 和 Dashboard 等固定本地治理输出被忽略；contracts、constraints 和源码绝不会被隐式排除。

## 既有行为特征基线

当目标代码缺少可靠相关测试时：

```bash
python scripts/cli.py characterize plan --task T-XXX --target src/example.py --project-dir .
# IO 填写 Preserve、argv 并将计划标为 AUTHORIZED
python scripts/cli.py characterize capture --task T-XXX --project-dir .
# 修改代码后
python scripts/cli.py characterize verify --task T-XXX --project-dir .
```

Capture 只保存规范化摘要、SHA-256、退出码和环境指纹，不保存完整敏感输出。命令、cwd、规范化规则改变，或执行超时、敏感信息命中时返回 UNVERIFIABLE。CAPTURED 基线存在时 prove 门自动复验；SAME 只表示 Preserve 行为未变化。

## 统一安全变更入口

```bash
python scripts/cli.py change plan --task T-XXX --target src/example.py --project-dir .
python scripts/cli.py change status --task T-XXX --project-dir .
python scripts/cli.py change prepare --task T-XXX --project-dir .
python scripts/cli.py change verify --task T-XXX --project-dir .
python scripts/cli.py change close --task T-XXX --project-dir .
```

plan 默认只输出；`--apply` 才创建本地 Change Plan，且绝不覆盖。status 根据契约、Recon Unknown、正式围栏和 Preserve 基线重新计算，只推荐一个下一步。prepare/verify/close 分别复用 pre/prove/closing 门，不复制裁决规则。自 v1.36.2 起，`change verify` 在 prove 门通过后会自动调用 `evidence finalize`，把 Evidence、Telemetry 与双 Dashboard 串成代码保证的 SCOPE-V 收口；收口失败时 verify 返回 BLOCKED。
