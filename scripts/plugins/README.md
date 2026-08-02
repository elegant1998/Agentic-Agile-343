# NFR 插件扩展

本目录用于存放外部 NFR 验证器插件。harness.py 在启动时自动加载 `nfr_*.py` 文件。

## 扩展 API

### 注册验证器

```python
# plugins/nfr_my_check.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import nfr_register
from pathlib import Path

@nfr_register("my_check", "自定义检查说明（显示在 nfr-list 中）")
def my_check(project_dir: Path, params: dict) -> tuple[bool, str]:
    """
    参数:
        project_dir: 项目根目录 Path
        params: constraints.yaml 中 nfr_params 字段的 dict

    返回:
        (passed: bool, detail: str)
        - passed=True 表示通过
        - detail 是人类可读的详情（显示在检查报告中）
    """
    target = params.get("target", "src/")
    # ... 你的检查逻辑 ...
    return True, "检查通过"
```

### 在 constraints.yaml 中使用

```yaml
- id: C-CUSTOM-01
  domain: QUAL
  level: MUST
  description: "自定义质量检查"
  check: "nfr:my_check"
  nfr_params:
    target: "src/"
    threshold: 0.9
  gate: G4
```

### 源码文件扩展名扩展

默认扫描 `*.py *.ts *.tsx *.js *.jsx`。如需扩展，在插件中追加：

```python
from harness import _NFR_SOURCE_EXTS
_NFR_SOURCE_EXTS = list(_NFR_SOURCE_EXTS) + ["*.go", "*.rs", "*.java"]
```

## 内置验证器

| 名称 | 域 | 说明 |
|------|-----|------|
| `nfr:bandit` | SEC | Python 安全扫描 |
| `nfr:secrets` | SEC | 硬编码密钥扫描 |
| `nfr:health_endpoint` | REL | 健康检查端点检测 |
| `nfr:retry_pattern` | REL | 重试/熔断模式检测 |
| `nfr:log_structured` | OBS | 结构化日志检测 |
| `nfr:monitoring_endpoint` | OBS | 指标端点检测 |
| `nfr:test_run` | QUAL | 测试套件执行 |
