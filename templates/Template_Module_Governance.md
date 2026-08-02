# 模块 OA 快速启动指南

> **适用场景**: 你是多模块项目中的模块负责人（模块 OA）。
> 本文档帮你快速建立本模块的 3-4-3 治理体系。

---

## 你的角色

```
全局 IO ──签署──→ 全局 OA（Tech Lead，维护 protocol.yaml）
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   模块 OA₁       模块 OA₂       模块 OA₃ (= 你)
   (WorkBuddy)    (Codex)      (你的工具)
        │             │             │
      AS₁           AS₂           AS₃
```

你的职责：
- 维护本模块的 governance/ 工件
- 遵守 protocol.yaml 中的全局约束
- 遵守你作为 consumer 的跨模块接口契约
- 如果你是本模块的 provider，确保接口符合 XC 定义
- 每个 SCOPE-V 周期结束后向全局 OA 上报遥测数据

---

## 启动清单（一次性）

### 1. 创建本模块治理目录

```bash
mkdir -p governance/contracts governance/evidence
```

### 2. 复制并填充编码规范

```bash
cp templates/Template_AI_Coding_Guide.md governance/AI_Coding_Guide.md
# 编辑: 填写本模块特有的硬性红线（≤5 条）
```

### 3. 从全局 protocol.yaml 提取本模块上下文

全局 OA 会给你一份 protocol.yaml。你只需要关注：

- `modules[你的模块]` — 你的模块信息
- `global_constraints` — 所有模块必须遵守的约束
- `cross_module_contracts[你的模块是 provider 或 consumer]` — 你需要遵守的接口契约
- `integration_dag` — 你的模块在哪个阶段、依赖谁

### 4. 创建本模块级约束（如有特殊需求）

```bash
# 仅当你的模块有全局约束未覆盖的特殊需求时
cp templates/Template_Constraints.yaml modules/<你的模块>/constraints.yaml
# 编辑: 删除不相关的域，保留本模块特有的约束
```

---

## 每个 SCOPE-V 周期的例行操作

### 开始前

1. 从全局 OA 获取最新 protocol.yaml（检查是否有新的全局约束或 XC 变更）
2. 裁剪本任务上下文:
   ```bash
   python3 scripts/crop_context.py --task T-XXX --domain <你的域>
   ```
   裁剪结果自动注入全局约束 + 本模块 AI_Coding_Guide

### 执行中

1. 遵守全局约束中的硬性红线
2. 如果本模块是 XC provider，确保接口签名不偏离 XC 定义
3. 如果本模块是 XC consumer，按 XC spec 构造请求

### 完成后

1. 运行本模块约束检查:
   ```bash
   python3 scripts/harness.py check --all
   ```
2. 收集遥测数据:
   ```bash
   python3 scripts/collect_telemetry.py --project <模块名> --output governance/telemetry.json
   ```
3. 更新证据包:
   - 记录测试结果、覆盖率、性能基准
   - 标记本模块门禁状态
4. 向全局 OA 上报:
   - 提交 governance/telemetry.json
   - 提交 governance/evidence/Evidence_Bundle.md

---

## 与其他模块 OA 的协作

### 当你是 XC consumer（调用方）

- 如果 provider 接口行为与 XC spec 不符 → 先检查自己请求格式 → 再联系 provider 模块 OA
- 如果 XC spec 不满足你的需求 → 向全局 OA 提 XC 变更请求

### 当你是 XC provider（提供方）

- 修改 XC 接口前必须通知所有 consumer 模块 OA
- 破坏性变更需要全局 OA 批准
- 非破坏性变更（新增字段、新增端点）可自行决定

### 集成测试阶段

全局 OA 会协调所有模块进行集成测试。你需要：
1. 确保本模块服务可被其他模块访问（测试环境）
2. 配合运行 `verify_cross_module.py`
3. 修复本模块导致的集成测试失败

---

## 工具适配说明

### 如果你用 WorkBuddy
所有脚本直接可用。按标准 SCOPE-V 流程执行。

### 如果你用 Codex (Copilot)
- 将 protocol.yaml 中的全局约束复制到 `.github/copilot-instructions.md`
- 治理脚本（harness.py 等）需要本地安装 Python 3.11+ 才能运行
- 如果无法运行 Python，使用 protocol.yaml §5 中的 `shell` 或 `manual` 替代命令

### 如果你用 Claude Code
- 将 protocol.yaml 中的全局约束 + 本模块 AI_Coding_Guide 追加到 `CLAUDE.md`
- 治理脚本可以通过 Bash 运行（CC 支持 Bash 工具）
- 遥测数据手动记录到 `.claude/telemetry.json`

---

## 常见问题

**Q: 我不同意某条全局约束怎么办？**
A: 先遵守，同时向全局 OA 提例外申请。在例外被批准前，约束仍然生效。

**Q: 我的模块不需要某些门禁（如 G6 安全扫描）怎么办？**
A: 在模块级 constraints.yaml 中为该门禁添加 exception，经全局 OA 批准后生效。

**Q: 跨模块 XC 接口变更了但我不知道？**
A: 全局 OA 应在 protocol.yaml 变更时通知所有受影响的模块 OA。如果未收到通知，在集成测试阶段 `verify_cross_module.py` 会发现不匹配。
