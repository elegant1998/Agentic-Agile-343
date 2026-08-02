# 贡献指南（Contributing）

> 🌐 English version: [CONTRIBUTING.en.md](CONTRIBUTING.en.md)

感谢你愿意为 **Agentic Agile 3-4-3 开源版** 添砖加瓦！

本仓库是完整、可运行的 Agentic AI 研发治理框架——全部开源，无保留。欢迎在任意方向贡献。

---

## 一、什么欢迎

- 🐛 **Bug 修复**：脚本报错、模板字段错误、文档命令写错、示例跑不通等。
- 📝 **文档与示例增强**：补充 `examples/` 场景；扩展 `references/` 读物；修正错别字 / 死链。
- 🌐 **翻译**：中文 ↔ English 双语对照（保持术语一致：意图契约 / Intent Contract、约束矩阵 / Constraint Matrix、SCOPE-V 等）。
- 🧩 **能力增强**：新增门禁规则、NFR 验证器、遥测维度、上下文裁剪策略、图引擎调度策略等。
- ✅ **测试与冒烟**：为 `scripts/` 补单测；让 CI 跑通 `gate_check.py`、`verify_contract.py`、`harness.py`。

## 二、自己先吃狗粮（Dog-food the 3-4-3）

提交前，请让你的改动本身符合 SCOPE-V：

1. **Specify**：在 PR 描述里写清"改了什么 / 不打算改什么 / 非目标"。
2. **Constrain**：遵守本仓库约定——纯标准库 + `pyyaml`（可选，缺失降级 MD-only）；脚本放 `scripts/`；模板放 `templates/`；不新增运行时依赖。
3. **Orchestrate / Prove**：本地跑 `bash scripts/ensure_py_env.sh` 后，确认 `python scripts/gate_check.py --gate pre --task T-001 --project-dir .`、`python scripts/harness.py check --all`、`python scripts/verify_contract.py --task T-001 --project-dir .` 不报错。
4. **Verify**：PR 描述附一句"我验证了 ____"。

## 三、提交流程（GitHub Flow）

```bash
# 1. Fork 后克隆你的副本
git clone <your-fork>
cd agentic-agile-343-community-ed

# 2. 开分支（语义化命名）
git checkout -b fix/gate-check-signed-detection

# 3. 改动 + 本地校验
bash scripts/ensure_py_env.sh
python scripts/gate_check.py --gate pre --task T-001 --project-dir .
python scripts/harness.py check --all

# 4. 提交与推送
git add -p
git commit -m "fix: gate_check 对占位符署名的检测更严格"
git push -u origin fix/gate-check-signed-detection

# 5. 开 PR，填写 PR 模板（见下）
```

### PR 描述建议结构

```markdown
## 改动摘要
<一句话说清改了什么>

## 范围（SCOPE-V · Specify）
- 目标：
- 非目标（明确不做的）：

## 验证（Verify）
- [ ] `bash scripts/ensure_py_env.sh` 通过
- [ ] `python scripts/gate_check.py --gate pre --task T-001 --project-dir .` 通过
- [ ] `python scripts/harness.py check --all` 通过
- [ ] 新增/修改的脚本有最小冒烟
```

## 四、代码与风格约定

- **语言**：脚本用 Python 3.10+；Shell 脚本用 `bash`，首行 `#!/usr/bin/env bash`，`set -uo pipefail`。
- **依赖**：仅标准库 + 可选 `pyyaml`；如确需新依赖，请在 PR 里说明理由与降级策略（保证"开箱即跑"不破功）。
- **路径**：不硬编码绝对路径；可经由环境变量覆盖。
- **中文优先**：注释与文档用简体中文，方法论术语保留英文原词（SCOPE-V、DoD、TDD…）。
- **提交信息**：遵循 Conventional Commits（`fix:` / `docs:` / `feat:` / `chore:` …）。

## 五、许可证

- 代码与模板：**[MIT](LICENSE)**——可自由使用、修改、分发，请保留版权声明。
- 白皮书（`docs/whitepaper/`）：**[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**——转载 / 二次创作需注明来源（王立杰-无敌哥）。
- 提交 PR 即表示你同意在上述许可证下发布你的贡献。

---

有疑问？来社区聊聊：<http://agentic.iloveagile.me/about> · 微信 `iloveagile`（备注「智能体敏捷」）。认同理念可在官网签署《Agentic Agile 宣言》。
