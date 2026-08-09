# 发布说明 · Release Notes

> 🌐 English version: [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

# Agentic Agile 3-4-3 治理架构 · 开源版 v1.25.0

> **先校准、再打怪。** 这是完整、可运行的 Agentic AI 研发治理框架——全部开源，无保留。让 AI 研发治理，进可攻退可守。

- **版本**：`1.25.0`
- **发布日期**：2026-08-09
- **许可证**：代码/模板 MIT · 白皮书 CC BY 4.0
- **作者**：王立杰（无敌哥），AI 治理架构师
- **官网**：<http://agentic.iloveagile.me/about> · 微信 `iloveagile`

---

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

- Python 3.10+（`ensure_py_env.sh` 自动建 venv + 装 pyyaml；缺失降级 MD-only）
- Node ≥ 22.5（可选，用于 `fetch_token_usage.sh` 实测 Token；缺失时自动 `npm i -g @geeeger/ocusage`）
- 无外部服务、无联网依赖、无需 API Key

## 五、快速开始

```bash
# 1. 准备环境
bash scripts/ensure_py_env.sh

# 2. 初始化项目治理
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml

# 3. SCOPE-V 循环 + 5 道机械门禁（硬拦截）
python scripts/gate_check.py --gate pre --task T-001 --project-dir .
python scripts/verify_contract.py --task T-001 --project-dir .
python scripts/harness.py check --all
bash scripts/quick_telemetry.sh T-001 ./governance
```

更完整说明见 [`README.md`](README.md)。

## 六、从旧社区版升级

- 旧社区版（v1.0.0-community）用户：直接用本版覆盖 `scripts/`、`templates/`、`references/`、`assets/`、`SKILL.md` 即可，你已有的 `governance/` 契约与约束矩阵无需重建。
- `build_community_ed.sh` 已移除，不再需要。

## 七、已知限制（Honest Caveats）

1. **示例单一**：目前仅 `T-001` 一个中性示例，欢迎 PR 补充更多场景。
2. **Token 实测依赖 ocusage**：`fetch_token_usage.sh` 需 `@geeeger/ocusage`（缺失时自动安装，需 Node ≥ 22.5）；不可用时回退估算并标记 `estimated`。
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
