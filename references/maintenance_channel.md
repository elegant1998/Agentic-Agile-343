# 门禁自身治理与维护通道

## 为什么需要独立维护通道

业务意图变化与治理工具缺陷不是同一类工作。若每次机械误报都创建业务补充契约，契约会被工具维护噪声淹没；若直接修复，又会失去授权边界和审计证据。

v1.26.1 使用独立的 `M-XXX` Maintenance Record：低风险、确定性的治理工具缺陷走维护通道；任何可能改变规则语义或权限边界的事项升级为 IO 签署的 Amendment 或新契约。

## 准入底线

以下六项必须全部明确为 `true`：

1. `deterministic_tool_defect`：确定是工具、解析器、门禁或验证器缺陷。
2. `reproducible`：存在最小可复现样例。
3. `business_scope_unchanged`：业务目标、AC 和 Change Envelope 不变。
4. `gate_strength_preserved`：不降低门禁强度，不新增豁免。
5. `permissions_unchanged`：不扩大文件、工具、网络或环境权限。
6. `approval_boundaries_unchanged`：签署责任、风险等级和不可逆操作批准边界不变。

任一项为 `false` 或 `null`，结果都是 `ESCALATED`。`changes_gate_semantics`、`changes_signing_semantics`、`expands_permissions`、`adds_bypass_or_exception` 任一风险标记为真，也必须升级。

## 使用流程

```bash
python scripts/cli.py maintain open --id M-001 --task T-128 --project-dir .
```

编辑 `governance/maintenance/M-001.yaml`，填写问题现象、六项准入判断和参数数组形式的最小复现命令。记录采用 JSON 语法的 YAML 子集，不需要第三方依赖。

```bash
python scripts/cli.py maintain check --id M-001 --project-dir .
```

`check` 先检查准入边界，再以 `shell=False` 执行复现命令。只有命令正常启动且产生非零退出码，才记录为真实 RED；命令缺失、无法执行或测试已绿均会升级，不得冒充 RED。

修复后补齐以下本地证据：

- `governance/maintenance/evidence/ME-M-001.md`
- `governance/telemetry/runs/telemetry-M-001.json`
- `governance/Intent_Graph.md` 中包含 M-001 教训
- 维护记录中的 focused command 与 full test command

```bash
python scripts/cli.py maintain close --id M-001 --project-dir .
```

只有专项测试和全量回归均为 GREEN，且三类收尾证据齐全，记录才能进入 `CLOSED`。重复执行 open/check/close 均保持幂等，不覆盖人工内容。

## 必须建立契约的情况

- 新增、删除或放宽门禁。
- 改变签署语义或 IO/OA 权责。
- 增加例外、白名单、跳过或默认放行。
- 改变风险 Profile、Unknown 处理或不可逆操作边界。
- 扩大工具、网络、生产或发布权限。
- 无法用回归测试证明兼容性。

维护通道不是免签通道。它是由已签署维护政策约束的工程化缺陷通道，并始终以 fail closed 为默认结果。
