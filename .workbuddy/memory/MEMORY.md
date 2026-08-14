# Agentic-Agile-343 项目长期记忆

## ocusage 智能客户端检测（跨任务持久）
- **精确检测**（优先）：`_infer_host_tool()` 从环境变量特征推断当前工具（4 级：CLI 参数 > `AGENTIC_AGILE_HOST_TOOL` > 环境变量特征检测 > 兜底 "other"）
- **环境变量特征签名**：WorkBuddy=`WORKBUDDY_APP_NAME`/`__CFBundleIdentifier=com.workbuddy`、Cursor=`CURSOR_TRACE_ID`、Copilot=`COPILOT_LANGUAGE_SERVER`、Codex=`OPENAI_CODEX`、Claude=`CLAUDE_CODE_ENTRYPOINT` 等
- **映射**：`_HOST_TOOL_TO_OCUSAGE_CLIENT` 把 host_tool 映射到 ocusage client 名
- **兜底**：host_tool 未知时用 `ocusage detect` 获取已安装客户端列表
- 无 baseline 时 scope=project_daily_snapshot（非 task_delta），_collect_cost 用 ESTIMATED 降级
- ocusage 安装位置：`~/.agentic-agile-343/tools/ocusage/`

## dashboard 子目录（T-153）
- 单次任务 dashboard → `governance/dashboards/dashboard-T-XXX.html`
- 汇总大屏 → `governance/dashboard.html`（原位不动）
- evidence_workflow / collect_telemetry / dashboard.py 路径已同步

## 覆盖率门禁抽象层（T-152）
- 框架只认报告格式（json-summary/lcov/jacoco-xml/cobertura-xml），不认语言工具
- 用户声明 `coverage_policies` → 自己配工具 → 框架收口
- 内置 Python 默认 policy 向下兼容
- 阈值 28%（过渡值，≈基线 27%+1pp）
