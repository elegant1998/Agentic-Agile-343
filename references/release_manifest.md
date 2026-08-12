# 单项目携证发布与 Release Manifest

Release Manifest 把被验证的 Git commit、构建制品摘要、配置、任务契约、Evidence Bundle、Telemetry、Verification Plan、批准和回滚方案绑定成一个可复验发布谱系。它解决“测试的是 A、发布的是 B”，但不替人执行发布。

## 最小用法

```bash
python scripts/cli.py release plan --task T-001 --version 1.2.3 --artifact dist/app.tar.gz --project-dir .
python scripts/cli.py release plan --task T-001 --version 1.2.3 --artifact dist/app.tar.gz --project-dir . --apply
# IO 审阅 Manifest 后才可把 DRAFT 改为 AUTHORIZED 并填写批准与回滚方案
python scripts/cli.py release check --manifest governance/releases/Release_Manifest_1.2.3.yaml --project-dir .
```

`plan` 默认 dry-run，实测当前 commit、工作树状态、制品 SHA-256/大小及任务证据摘要；apply 只创建 DRAFT，已有 Manifest 绝不覆盖。

## READY 不等于 RELEASED

`READY_FOR_HUMAN_RELEASE` 只表示证据足以交给发布责任人决策。检查器不会创建 commit、Tag、push、构建、上传、部署、灰度、切流或生产写入，也不会把 Agent 自己列为批准人。

只有外部发布已经发生后，才能用 `record` 追加事实：

```bash
python scripts/cli.py release record \
  --manifest governance/releases/Release_Manifest_1.2.3.yaml \
  --event released --actor "Human Name" \
  --evidence governance/evidence/release-1.2.3.json --project-dir .
```

事件证据必须位于项目内，且 release_id、version、event 和 occurred_at 与 Manifest 匹配。重复的同一事件幂等；源码、制品和旧事件不可覆写。`rolled_back` 必须在已有 released 事件后追加。

## Build Once, Verify Once, Promote Many

所有 promotion 必须引用同一个 artifact SHA-256。制品内容、大小、当前 HEAD、任务证据或配置摘要发生漂移时，旧 READY 自动失效。重新构建意味着产生新的制品绑定和重新验证，而不是沿用旧证据。

## 就绪边界

以下任一情况返回 BLOCKED：工作树存在未绑定业务源码变化；制品或证据摘要漂移；契约未签署；Evidence Bundle 未 APPROVED；缺少任务遥测或图谱完成态；正式 Verification Plan 非 PASS；回滚方案缺代码、数据、配置或复验动作；发布批准来自 AI/OA/Agent。

CONDITIONAL 必须声明 condition、owner、deadline 和 reverify，而且只允许可逆下一步，不能据此自动生产发布。
