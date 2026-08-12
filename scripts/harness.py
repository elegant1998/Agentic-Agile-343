#!/usr/bin/env python3
"""Harness Engine — 约束执行引擎

读取 constraints.yaml，逐条执行约束检查，输出 text/json 格式。
支持按域/门禁筛选，支持例外管理，退出码反映通过/失败。

内置 NFR（非功能需求）验证器（跨语言：支持 Python / TypeScript / JavaScript / Go 等）：
  - SEC:  bandit 安全扫描(仅 Python) / 敏感信息检测(跨语言)
  - REL:  熔断/重试模式检测(跨语言) / 健康检查端点检测(跨语言)
  - OBS:  日志语句检测(跨语言) / 结构化日志格式检测(跨语言)
  - QUAL: 测试覆盖率 / 性能基准（原有）

NFR 验证器在约束的 check 字段为特殊前缀时自动触发：
  - check: "nfr:bandit"          → bandit 安全扫描(仅 Python 项目；TS/JS 项目自动跳过)
  - check: "nfr:secrets"         → 扫描硬编码密钥(跨语言)
  - check: "nfr:health_endpoint" → 检测健康检查端点(跨语言)
  - check: "nfr:retry_pattern"   → 检测重试/熔断模式(跨语言)
  - check: "nfr:log_structured"  → 检测结构化日志(跨语言)

用法:
    python scripts/harness.py check --all                # 全量检查（含 NFR）
    python scripts/harness.py check --domain QUAL        # 按域
    python scripts/harness.py check --gate G4            # 按门禁
    python scripts/harness.py check --all --format json  # JSON 输出
    python scripts/harness.py check --nfr-only           # 仅运行 NFR 检查
    python scripts/harness.py list                       # 列出所有约束
    python scripts/harness.py nfr-list                   # 列出可用 NFR 验证器
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path
from command_runner import run_command, run_shell
from runtime_context import load_trusted_verification_context, parse_test_output, resolve_test_plan


_RUNTIME_FILE_CACHE = {}
_RUNTIME_INVENTORY_CACHE = {}


def reset_runtime_caches():
    """Reset per-command source caches before a new Harness lifecycle."""
    _RUNTIME_FILE_CACHE.clear()
    _RUNTIME_INVENTORY_CACHE.clear()


def _read_source(path: Path) -> str:
    # rglob yields stable absolute paths for the absolute project roots used by
    # Harness. Avoid Path.resolve() on every cache hit in multi-validator scans.
    key = path if path.is_absolute() else path.absolute()
    if key not in _RUNTIME_FILE_CACHE:
        _RUNTIME_FILE_CACHE[key] = path.read_text(encoding="utf-8", errors="ignore")
    return _RUNTIME_FILE_CACHE[key]


def _load_yaml(path: Path) -> dict:
    """惰性加载 YAML，避免 NFR-only 场景强制依赖 pyyaml（采集器可直接调用验证器）"""
    try:
        import yaml
    except ImportError:
        from _bootstrap import ensure_yaml_available
        ensure_yaml_available()  # 成功则自动建 venv 装 pyyaml 后重启整个 harness
        import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def load_constraints(project_dir: Path, module: str = None) -> dict:
    """加载 constraints.yaml，可选叠加模块级约束"""
    yaml_file = project_dir / "governance" / "constraints.yaml"
    if not yaml_file.exists():
        print(f"错误: 找不到 {yaml_file}", file=sys.stderr)
        sys.exit(1)
    data = _load_yaml(yaml_file)

    # 加载模块级约束并叠加
    if module:
        module_file = project_dir / "modules" / module / "constraints.yaml"
        if module_file.exists():
            with open(module_file) as f:
                module_data = _load_yaml(module_file)
            # 叠加约束列表
            module_constraints = module_data.get("constraints", [])
            if module_constraints:
                # 避免 ID 冲突：模块级约束加前缀
                for c in module_constraints:
                    if not c["id"].startswith(f"M-{module}-"):
                        c["id"] = f"M-{module}-{c['id']}"
                data.setdefault("constraints", []).extend(module_constraints)
            # 叠加例外
            module_exceptions = module_data.get("exceptions", [])
            if module_exceptions:
                data.setdefault("exceptions", []).extend(module_exceptions)

    return data


def is_exception_active(constraint_id: str, exceptions: list) -> dict | None:
    """检查约束是否在有效例外中"""
    for ex in exceptions:
        if ex.get("constraint_id") == constraint_id:
            valid_until = ex.get("valid_until")
            if valid_until:
                try:
                    expiry = datetime.strptime(valid_until, "%Y-%m-%d").date()
                    if date.today() <= expiry:
                        return ex
                except ValueError:
                    pass
    return None


def _run_shell_check(check_cmd: str, project_dir: Path, timeout: int = 30) -> tuple[bool, str]:
    """Legacy POSIX check. Windows callers must migrate to an explicit dialect."""
    dialect = "posix" if sys.platform != "win32" else None
    if not dialect:
        return False, "UNSUPPORTED_SHELL_DIALECT: legacy shell check 未声明方言"
    result = run_shell({"dialect": dialect, "script": check_cmd,
                        "timeout_seconds": timeout}, project_dir)
    detail = result.get("stderr") or result.get("stdout") or result.get("detail") or result["status"]
    return result["status"] == "PASS", detail[:200]


def _run_python_check(expr: str, project_dir: Path) -> tuple[bool, str]:
    """执行 Python 表达式作为 check（跨平台备选方案）。

    约束中 check_type: python + check: "expression" 时使用。
    expression 可以是任意 Python 表达式，返回 True/False。
    """
    try:
        result = eval(expr, {"__builtins__": __builtins__}, {"Path": Path, "project_dir": project_dir})
        passed = bool(result)
        return passed, "通过" if passed else "失败"
    except Exception as e:
        return False, f"Python check 异常: {e}"


def run_check(constraint: dict, project_dir: Path) -> tuple[bool, str]:
    """执行单条约束检查（跨平台）"""
    check_cmd = constraint.get("check", "true")
    if constraint.get("manual"):
        return True, "人工检查（跳过自动验证）"

    # NFR 验证器路由
    if isinstance(check_cmd, str) and check_cmd.startswith("nfr:"):
        nfr_name = check_cmd[4:]
        nfr_params = constraint.get("nfr_params", {})
        return run_nfr_check(nfr_name, project_dir, nfr_params)

    # Python 表达式 check（跨平台，check_type: python）
    if constraint.get("check_type") == "python":
        return _run_python_check(check_cmd, project_dir)

    if constraint.get("check_type") == "command":
        result = run_command(check_cmd, project_dir)
        detail = result.get("stderr") or result.get("stdout") or result.get("detail") or result["status"]
        return result["status"] == "PASS", detail[:200]

    if constraint.get("check_type") == "shell":
        spec = check_cmd if isinstance(check_cmd, dict) else {
            "dialect": constraint.get("shell_dialect"), "script": check_cmd}
        result = run_shell(spec, project_dir)
        detail = result.get("stderr") or result.get("stdout") or result.get("detail") or result["status"]
        return result["status"] == "PASS", detail[:200]

    # Shell check（跨平台：bash 优先，无 bash 时降级）
    return _run_shell_check(check_cmd, project_dir)


# ─── NFR 验证器注册表 ─────────────────────────────────────

NFR_REGISTRY = {}


def nfr_register(name: str, description: str):
    """装饰器：注册 NFR 验证器"""
    def decorator(func):
        NFR_REGISTRY[name] = {"func": func, "description": description}
        return func
    return decorator


def run_nfr_check(name: str, project_dir: Path, params: dict) -> tuple[bool, str]:
    """执行 NFR 验证器"""
    if name not in NFR_REGISTRY:
        return False, f"未知 NFR 验证器: {name}（可用: {', '.join(NFR_REGISTRY.keys())}）"
    try:
        return NFR_REGISTRY[name]["func"](project_dir, params)
    except Exception as e:
        return False, f"NFR 验证器异常: {e}"


def load_nfr_plugins(plugins_dir: Path = None):
    """从 plugins/ 目录加载外部 NFR 验证器插件。

    插件为 Python 文件（nfr_*.py），在模块级使用 nfr_register 装饰器注册验证器。
    签名: func(project_dir: Path, params: dict) -> tuple[bool, str]
    示例:
        from harness import nfr_register
        @nfr_register("custom_check", "自定义检查说明")
        def my_check(project_dir, params):
            return True, "通过"
    """
    if plugins_dir is None:
        plugins_dir = Path(__file__).resolve().parent / "plugins"
    if not plugins_dir.is_dir():
        return
    import importlib.util
    for pf in sorted(plugins_dir.glob("nfr_*.py")):
        try:
            spec = importlib.util.spec_from_file_location(pf.stem, pf)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"⚠️ 加载 NFR 插件 {pf.name} 失败: {e}", file=sys.stderr)


# NFR 源文件扩展名：覆盖 Python 与主流 Web 栈（TS/JS），使 G6-G8 Web 扩展门禁
# 能正确评估 TypeScript/Node 项目（而非只扫 *.py 导致大面积误判）
# 可被外部插件扩展：from harness import _NFR_SOURCE_EXTS; _NFR_SOURCE_EXTS.extend(["*.go"])
_NFR_SOURCE_EXTS = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx",
                     "*.go", "*.rs", "*.java", "*.cs", "*.rb"]


def _iter_nfr_files(target: Path):
    """遍历目录下所有受支持源码文件（Python + TS/JS），忽略权限/编码错误"""
    resolved = target.resolve()
    if resolved not in _RUNTIME_INVENTORY_CACHE:
        files = []
        for ext in _NFR_SOURCE_EXTS:
            try:
                files.extend(target.rglob(ext))
            except Exception:
                continue
        _RUNTIME_INVENTORY_CACHE[resolved] = tuple(sorted(set(files)))
    yield from _RUNTIME_INVENTORY_CACHE[resolved]


# 源码根目录（用于语言判定），排除构建产物与依赖
_SRC_ROOTS = ("src", "server", "lib", "app", "api", "backend", "pkg", "cmd")
_EXCLUDE_DIRS = (".git", "__pycache__", "node_modules", "venv", ".venv",
                 "dist", "build", ".next", "out", "coverage", ".turbo")


def _has_source_language(project_dir: Path, ext: str) -> bool:
    """跨语言判定：项目是否在真实源码目录中含某扩展名文件（排除依赖/构建目录）。
    避免把 scripts/ 下的辅助 .py 或 node_modules 误判为项目主语言。"""
    # 源码根目录优先
    for root in _SRC_ROOTS:
        d = project_dir / root
        if d.is_dir():
            if any(True for _ in d.rglob(ext)):
                return True
    # 根目录下的一级 .py/.ts（排除已知非源码目录）
    for fp in project_dir.iterdir():
        if fp.is_file() and fp.name.endswith(ext) and fp.name not in _EXCLUDE_DIRS:
            return True
    return False


# ─── SEC 域：安全验证器 ────────────────────────────────────

@nfr_register("bandit", "Python 代码安全扫描（仅 Python 项目；TS/JS/Go 等自动跳过）")
def nfr_bandit(project_dir: Path, params: dict) -> tuple[bool, str]:
    """运行 bandit 安全扫描（仅当项目含 Python 源文件时生效，跨语言项目自动跳过）"""
    # 跨语言：仅对含 Python 源文件的项目运行 bandit，否则跳过（不误判 TS/JS/Go）
    if not _has_source_language(project_dir, ".py"):
        return True, "非 Python 项目（源码目录无 *.py），bandit 不适用，跳过"
    target = params.get("target", "src/")
    severity = params.get("severity", "medium")
    try:
        result = subprocess.run(
            ["bandit", "-r", target, "-ll", "-s", "B101", "-q"],
            capture_output=True, text=True, timeout=120,
            cwd=str(project_dir)
        )
        # bandit 返回 0 = 无问题, 1 = 有问题
        if result.returncode == 0:
            return True, "bandit 安全扫描通过"
        else:
            issues = result.stdout.strip().split('\n')
            high_issues = [l for l in issues if 'HIGH' in l or 'MEDIUM' in l]
            return False, f"bandit 发现 {len(issues)} 个安全问题（高/中: {len(high_issues)}）"
    except FileNotFoundError:
        return True, "bandit 未安装（跳过，安装: pip install bandit）"
    except Exception as e:
        return False, str(e)


@nfr_register("secrets", "硬编码密钥/令牌扫描")
def nfr_secrets(project_dir: Path, params: dict) -> tuple[bool, str]:
    """扫描源代码中的硬编码密钥"""
    patterns = params.get("patterns", [
        (r'(?:password|passwd|pwd|secret|token|api_key|apikey)\s*[:=]\s*["\'](?:(?!your_|example_|test_|changeme|xxx|TODO).)+["\']', "疑似硬编码凭证"),
        (r'-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----', "私钥"),
        (r'(?:AKIA|ASIA)[A-Z0-9]{16}', "AWS Access Key"),
        (r'ghp_[A-Za-z0-9]{36}', "GitHub Personal Access Token"),
    ])
    exclude_dirs = params.get("exclude_dirs", [".git", "__pycache__", "node_modules", "venv", ".venv"])
    scan_dirs = params.get("scan_dirs", ["src", "server", "scripts", "tests"])

    findings = []
    for scan_dir in scan_dirs:
        target = project_dir / scan_dir
        if not target.exists():
            continue
        for fp in _iter_nfr_files(target):
            if any(ex in str(fp) for ex in exclude_dirs):
                continue
            try:
                content = _read_source(fp)
                for pattern, label in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for m in matches:
                        # 截断敏感内容
                        masked = str(m)[:30] + "..." if len(str(m)) > 30 else str(m)
                        findings.append(f"{fp.relative_to(project_dir)}: {label} ({masked})")
            except Exception:
                continue

    if findings:
        return False, f"发现 {len(findings)} 处疑似敏感信息: {'; '.join(findings[:5])}"
    return True, "未发现硬编码敏感信息"


# ─── REL 域：可靠性验证器 ──────────────────────────────────

@nfr_register("health_endpoint", "检测健康检查端点是否存在")
def nfr_health_endpoint(project_dir: Path, params: dict) -> tuple[bool, str]:
    """检测 API 是否有健康检查端点"""
    patterns = params.get("patterns", [
        r'(?:/health|/healthz|/ping|/status|/ready|/livez)',
        r'@router\.(?:get|post).*?["\']/(?:health|ping|status)',
    ])
    scan_dirs = params.get("scan_dirs", ["src", "server", "src/api", "src/routes", "src/app"])

    found = False
    for scan_dir in scan_dirs:
        target = project_dir / scan_dir
        if not target.exists():
            continue
        for fp in _iter_nfr_files(target):
            try:
                content = _read_source(fp)
                for pat in patterns:
                    if re.search(pat, content, re.IGNORECASE):
                        found = True
                        break
            except Exception:
                continue
        if found:
            break

    if found:
        return True, "健康检查端点已定义"
    return False, "未检测到健康检查端点（建议添加 /health 端点）"


@nfr_register("retry_pattern", "检测重试/熔断/超时模式")
def nfr_retry_pattern(project_dir: Path, params: dict) -> tuple[bool, str]:
    """检测代码中是否有重试/熔断/超时模式"""
    retry_keywords = params.get("retry_keywords", [
        # 通用 / Python
        "retry", "Retry", "backoff", "circuit_breaker", "CircuitBreaker",
        "tenacity", "HTTPAdapter", "max_retries",
        "Timeout", "timeout", "connect_timeout",
        # TypeScript / JavaScript / Node
        "axios-retry", "p-retry", "retry-axios", "@nestjs/terminus",
        "RetryPolicy", "withRetry", "useRetry", "resilience4j",
        # Go
        "retry.Do", "backoff.Retry",
    ])
    scan_dirs = params.get("scan_dirs", ["src", "server", "scripts"])

    found_keywords = set()
    for scan_dir in scan_dirs:
        target = project_dir / scan_dir
        if not target.exists():
            continue
        for fp in _iter_nfr_files(target):
            try:
                content = _read_source(fp)
                for kw in retry_keywords:
                    if kw in content:
                        found_keywords.add(kw)
            except Exception:
                continue

    if found_keywords:
        return True, f"检测到可靠性模式: {', '.join(sorted(found_keywords))}"
    return True, "未检测到重试/熔断模式（如不需要外部调用则无影响）"


# ─── OBS 域：可观测性验证器 ─────────────────────────────────

@nfr_register("log_structured", "检测结构化日志使用情况")
def nfr_log_structured(project_dir: Path, params: dict) -> tuple[bool, str]:
    """检测是否使用结构化日志"""
    structured_indicators = params.get("indicators", [
        # Python
        "structlog", "python-json-logger",
        "logging.basicConfig", "logger.info(", "logger.error(",
        "logger.debug(", "logger.warning(",
        # TypeScript / JavaScript / Node
        "winston", "pino", "bunyan", "morgan",
        "console.log", "logger.", "log.info", "createLogger",
    ])
    scan_dirs = params.get("scan_dirs", ["src", "server"])

    found = set()
    for scan_dir in scan_dirs:
        target = project_dir / scan_dir
        if not target.exists():
            continue
        for fp in _iter_nfr_files(target):
            try:
                content = _read_source(fp)
                for ind in structured_indicators:
                    if ind in content:
                        found.add(ind)
            except Exception:
                continue

    # found 为集合，元素是被命中的指示符字符串；跨语言判定是否有任意日志迹象
    if "structlog" in found or "python-json-logger" in found:
        return True, "使用结构化日志库（最佳实践）"
    if ("logging.basicConfig" in found or "logger." in found or "logger.info(" in found
            or "winston" in found or "pino" in found or "bunyan" in found
            or "morgan" in found or "console.log" in found or "log.info" in found
            or "createLogger" in found):
        return True, "已使用日志输出（建议升级为结构化日志库如 winston/pino/structlog）"
    return True, "未检测到日志语句（如为纯库项目则无影响）"


@nfr_register("monitoring_endpoint", "检测指标暴露端点")
def nfr_monitoring_endpoint(project_dir: Path, params: dict) -> tuple[bool, str]:
    """检测是否有 metrics/Prometheus 端点"""
    indicators = params.get("indicators", [
        # 通用
        "/metrics", "prometheus", "PrometheusMetrics",
        # Python
        "prometheus_client",
        # TypeScript / JavaScript / Node
        "prom-client", "express-prometheus-middleware", "prometheusMiddleware",
        # Go
        "promhttp", "prometheus.NewGauge",
    ])
    scan_dirs = params.get("scan_dirs", ["src", "server"])

    for scan_dir in scan_dirs:
        target = project_dir / scan_dir
        if not target.exists():
            continue
        for fp in _iter_nfr_files(target):
            try:
                content = _read_source(fp)
                if any(ind in content for ind in indicators):
                    return True, "检测到指标暴露端点"
            except Exception:
                continue

    return True, "未检测到 /metrics 端点（建议在生产环境添加）"


# ─── 自动恢复引擎 ──────────────────────────────────────────

# ─── 测试执行器（跨语言） ─────────────────────────────────
@nfr_register("test_run", "运行项目测试套件并采集结构化结果（Node/vitest/jest、Python/pytest、Go/go test、Rust/cargo test、Java/mvn test、C#/dotnet test）")
def nfr_test_run(project_dir: Path, params: dict) -> tuple[bool, str]:
    """运行测试套件；返回 (是否通过, 详情)。详情含结构化计数。"""
    context_path = params.get("verification_context")
    if context_path:
        context, reason = load_trusted_verification_context(context_path, project_dir)
        if context is not None:
            return True, (
                "reused trusted Verification Run Context: "
                f"{context.get('passed', 0)}/{context.get('total', 0)} "
                f"runner={context.get('runner', 'unknown')}"
            )
        return False, f"Verification Run Context rejected: {reason}"
    res = run_tests(project_dir, params)
    return (res.get("passed", 0) > 0 and res.get("failed", 0) == 0), res.get("detail", "")


# 加载外部 NFR 插件（plugins/nfr_*.py）
load_nfr_plugins()


def _detect_test_command(project_dir: Path) -> dict:
    """探测项目测试命令，返回 {runner, cmd, kind} 或 {runner: None}"""
    plan = resolve_test_plan(project_dir)
    return {"runner": plan["runner"], "cmd": plan["argv"], "kind": plan["kind"]}


def run_tests(project_dir: Path, params: dict | None = None) -> dict:
    """跨语言运行测试套件，返回结构化结果。

    返回: {ran, runner, total, passed, failed, errors, coverage, status, detail, coverage_threshold, coverage_status}
    """
    params = params or {}
    cov_threshold = params.get("coverage_threshold", 80)
    info = _detect_test_command(project_dir)
    if not info.get("runner"):
        return {
            "ran": False, "runner": None,
            "total": 0, "passed": 0, "failed": 0, "errors": 0,
            "coverage": 0.0, "status": "NO_TEST_SUITE",
            "detail": "未检测到测试套件（无 package.json / pytest / go.mod / Cargo.toml / pom.xml / *.csproj）；SCOPE-V 未运行测试",
        }
    execution = run_command({"argv": info["cmd"], "timeout_seconds": params.get("timeout", 300)}, project_dir)
    if execution["status"] == "TIMEOUT":
        return {"ran": True, "runner": info["runner"], "total": 0, "passed": 0,
                "failed": 0, "errors": 1, "coverage": 0.0, "status": "TIMEOUT",
                "detail": f"测试执行超时（>{params.get('timeout', 300)}s）"}
    if execution["status"] in {"COMMAND_NOT_FOUND", "INVALID_COMMAND_SPEC"}:
        return {"ran": True, "runner": info["runner"], "total": 0, "passed": 0,
                "failed": 0, "errors": 1, "coverage": 0.0, "status": "ERROR",
                "detail": f"测试执行异常: {execution.get('detail')}"}

    out = execution.get("stdout", "") + execution.get("stderr", "")
    result = _parse_test_output(info["runner"], out)
    result["ran"] = True
    result["runner"] = info["runner"]
    result["status"] = "PASS" if (result["failed"] == 0 and result["passed"] > 0) else (
        "FAIL" if result["passed"] == 0 else "PARTIAL")
    # 覆盖率（best-effort）
    cov = _parse_coverage(project_dir)
    result["coverage"] = cov
    result["coverage_threshold"] = cov_threshold
    result["coverage_status"] = "PASS" if cov >= cov_threshold else ("FAIL" if cov > 0 else "UNKNOWN")
    bits = [f"runner={info['runner']}",
            f"total={result['total']} passed={result['passed']} failed={result['failed']} errors={result['errors']}"]
    if cov > 0:
        bits.append(f"coverage={cov:.1f}% (阈值 {cov_threshold}%)")
    result["detail"] = "; ".join(bits)
    return result


def _parse_test_output(runner: str, out: str) -> dict:
    shared = parse_test_output(runner, out)
    if shared["total"] or runner in {"unittest", "pytest", "vitest", "jest", "npm", "go", "cargo", "mvn", "dotnet"}:
        return shared
    base = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
    # Go / Rust / Java / C# 专用解析器
    if runner == "go":
        return _parse_go_test_output(out)
    if runner == "cargo":
        return _parse_cargo_test_output(out)
    if runner == "mvn":
        return _parse_mvn_test_output(out)
    if runner == "dotnet":
        return _parse_dotnet_test_output(out)
    if runner == "unittest":
        m = re.search(r"Ran (\d+) tests?", out)
        if m:
            base["total"] = int(m.group(1))
        failed = 0
        errors = 0
        summary = re.search(r"FAILED \(([^)]+)\)", out)
        if summary:
            fm = re.search(r"failures=(\d+)", summary.group(1))
            em = re.search(r"errors=(\d+)", summary.group(1))
            failed = int(fm.group(1)) if fm else 0
            errors = int(em.group(1)) if em else 0
        base["failed"] = failed
        base["errors"] = errors
        base["passed"] = max(base["total"] - failed - errors, 0) if base["total"] else 0
        return base
    if runner in ("vitest", "jest"):
        try:
            start = out.find("{")
            end = out.rfind("}")
            if start != -1 and end != -1:
                obj = json.loads(out[start:end + 1])
                if runner == "jest":
                    base["total"] = obj.get("numTotalTests", 0)
                    base["passed"] = obj.get("numPassedTests", 0)
                    base["failed"] = obj.get("numFailedTests", 0)
                    base["errors"] = obj.get("numPendingTests", 0)
                else:  # vitest
                    base["total"] = obj.get("numTotalTests", 0)
                    base["passed"] = obj.get("numPassedTests", 0)
                    base["failed"] = obj.get("numFailedTests", 0)
                    base["errors"] = obj.get("numPendingTests", 0)
                return base
        except Exception:
            pass
    # 文本回退：Vitest/Jest 摘要行 "Tests  X failed | Y passed | Z total"
    m = re.search(r"Tests\s+(\d+)\s+failed[^|]*\|\s*(\d+)\s+passed[^|]*\|\s*(\d+)\s+total", out)
    if m:
        base["failed"] = int(m.group(1))
        base["passed"] = int(m.group(2))
        base["total"] = int(m.group(3))
        return base
    m2 = re.search(r"(\d+)\s+passed", out)
    if m2:
        base["passed"] = int(m2.group(1))
        fm = re.search(r"(\d+)\s+failed", out)
        base["failed"] = int(fm.group(1)) if fm else 0
        base["total"] = base["passed"] + base["failed"]
    return base


def _parse_go_test_output(out: str) -> dict:
    """解析 go test -v 输出"""
    base = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
    # go test -v 输出 "--- PASS: TestX" / "--- FAIL: TestX"
    base["passed"] = len(re.findall(r"^--- PASS:", out, re.MULTILINE))
    base["failed"] = len(re.findall(r"^--- FAIL:", out, re.MULTILINE))
    base["total"] = base["passed"] + base["failed"]
    # 编译错误也算失败
    if re.search(r"FAIL\t.*\[build failed\]", out):
        base["errors"] = 1
    return base


def _parse_cargo_test_output(out: str) -> dict:
    """解析 cargo test 输出"""
    base = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
    # cargo test: "test result: ok. 5 passed; 0 failed; 0 ignored;"
    m = re.search(r"test result:.*?(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored", out)
    if m:
        base["passed"] = int(m.group(1))
        base["failed"] = int(m.group(2))
        base["total"] = base["passed"] + base["failed"] + int(m.group(3))
    return base


def _parse_mvn_test_output(out: str) -> dict:
    """解析 mvn test 输出"""
    base = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
    # mvn test: "Tests run: 5, Failures: 0, Errors: 0, Skipped: 0"
    total_run = 0
    total_fail = 0
    total_err = 0
    for m in re.finditer(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", out):
        total_run += int(m.group(1))
        total_fail += int(m.group(2))
        total_err += int(m.group(3))
    base["total"] = total_run
    base["passed"] = total_run - total_fail - total_err
    base["failed"] = total_fail
    base["errors"] = total_err
    return base


def _parse_dotnet_test_output(out: str) -> dict:
    """解析 dotnet test 输出"""
    base = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
    # dotnet test: "Passed: 5", "Failed: 1", "Skipped: 0", "Total: 6"
    pm = re.search(r"Passed:\s*(\d+)", out)
    fm = re.search(r"Failed:\s*(\d+)", out)
    tm = re.search(r"Total:\s*(\d+)", out)
    base["passed"] = int(pm.group(1)) if pm else 0
    base["failed"] = int(fm.group(1)) if fm else 0
    base["total"] = int(tm.group(1)) if tm else (base["passed"] + base["failed"])
    return base


def _parse_coverage(project_dir: Path) -> float:
    """best-effort: 读取 coverage/coverage-summary.json (vitest/jest json-summary 报告)"""
    cand = project_dir / "coverage" / "coverage-summary.json"
    if cand.exists():
        try:
            obj = json.loads(cand.read_text())
            tot = obj.get("total", {})
            line = tot.get("lines", {})
            if isinstance(line, dict) and "pct" in line:
                return float(line["pct"])
        except Exception:
            pass
    return 0.0


def resolve_constraint_conflicts(constraints: list[dict], data: dict) -> list[dict]:
    """解决约束冲突：两条 MUST 冲突时按优先级链仲裁"""
    priority = data.get("constraint_priority", {})
    if not priority:
        return constraints

    # 按优先级排序，高优先级覆盖低优先级
    def sort_key(c):
        domain = c.get("domain", "")
        return -priority.get(domain, 0)

    return sorted(constraints, key=sort_key)


def attempt_recovery(constraint: dict, project_dir: Path) -> tuple[bool, str]:
    """尝试自动恢复单条约束"""
    auto_recover = constraint.get("auto_recover")
    if not auto_recover:
        return False, "未定义自动恢复策略"

    recover_cmd = auto_recover.get("command", "")
    if not recover_cmd:
        return False, "恢复策略缺少 command"

    command_type = auto_recover.get("command_type", "shell")
    if command_type == "command":
        result = run_command(recover_cmd, project_dir)
    elif command_type == "shell":
        spec = recover_cmd if isinstance(recover_cmd, dict) else {
            "dialect": auto_recover.get("shell_dialect"), "script": recover_cmd}
        result = run_shell(spec, project_dir)
    else:
        return False, "INVALID_COMMAND_SPEC: unknown recovery command_type"
    if result["status"] == "PASS":
        return True, f"自动恢复成功: {auto_recover.get('description', 'structured command')}"
    return False, f"恢复命令失败[{result['status']}]: {(result.get('stderr') or result.get('detail') or '')[:100]}"


def recover_constraints(project_dir: Path, domain: str = None,
                        module: str = None,
                        dry_run: bool = False) -> dict:
    """recover 子命令：自动修复失败的约束"""
    data = load_constraints(project_dir, module)
    constraints = data.get("constraints", [])
    exceptions = data.get("exceptions", [])

    if domain:
        constraints = [c for c in constraints if c["domain"] == domain]

    recovery_config = data.get("auto_recovery", {})
    max_retries = recovery_config.get("max_retries", 3)

    results = []
    recovered = 0
    failed_recovery = 0
    skipped = 0

    for c in constraints:
        # 跳过已设例外的
        exc = is_exception_active(c["id"], exceptions)
        if exc:
            results.append({
                "id": c["id"],
                "description": c["description"],
                "status": "SKIPPED",
                "detail": f"例外中: {exc['reason']}",
            })
            skipped += 1
            continue

        # 跳过人工检查的
        if c.get("manual"):
            results.append({
                "id": c["id"],
                "description": c["description"],
                "status": "SKIPPED",
                "detail": "人工检查，不可自动恢复",
            })
            skipped += 1
            continue

        # 先检查是否真的失败了
        ok, detail = run_check(c, project_dir)
        if ok:
            results.append({
                "id": c["id"],
                "description": c["description"],
                "status": "ALREADY_OK",
                "detail": "约束已通过，无需恢复",
            })
            continue

        # 尝试恢复
        if not dry_run:
            for attempt in range(max_retries):
                recovered_ok, rec_detail = attempt_recovery(c, project_dir)
                if recovered_ok:
                    # 恢复后验证
                    verify_ok, verify_detail = run_check(c, project_dir)
                    if verify_ok:
                        results.append({
                            "id": c["id"],
                            "description": c["description"],
                            "status": "RECOVERED",
                            "detail": f"恢复成功（第 {attempt + 1} 次尝试）: {rec_detail}",
                        })
                        recovered += 1
                        break
                    else:
                        results.append({
                            "id": c["id"],
                            "description": c["description"],
                            "status": "RECOVERY_UNVERIFIED",
                            "detail": f"恢复命令已执行但约束仍未通过: {verify_detail}",
                        })
                        failed_recovery += 1
                        break
                else:
                    if attempt == max_retries - 1:
                        results.append({
                            "id": c["id"],
                            "description": c["description"],
                            "status": "RECOVERY_FAILED",
                            "detail": f"恢复失败（{max_retries} 次尝试后）: {rec_detail}",
                        })
                        failed_recovery += 1
        else:
            # dry-run 模式
            has_recovery = bool(c.get("auto_recover"))
            results.append({
                "id": c["id"],
                "description": c["description"],
                "status": "WOULD_RECOVER" if has_recovery else "NO_RECOVERY_DEFINED",
                "detail": ("将执行恢复命令" if has_recovery else "无恢复策略定义，需人工处理"),
            })

    return {
        "project": data.get("project", "UNKNOWN"),
        "dry_run": dry_run,
        "total_checked": len(constraints),
        "recovered": recovered,
        "failed_recovery": failed_recovery,
        "skipped": skipped,
        "results": results,
    }


def get_failure_policy(constraint: dict, data: dict) -> str:
    """获取约束失败时的处理策略"""
    # 单条约束可覆盖全局策略
    if "on_failure" in constraint:
        return constraint["on_failure"]

    level = constraint.get("level", "MUST")
    default_policy = data.get("default_failure_policy", {})
    return default_policy.get(level, "warn")


def check_constraints(project_dir: Path, domain: str = None, gate: str = None,
                      format: str = "text", nfr_only: bool = False,
                      module: str = None, data: dict | None = None) -> dict:
    """执行约束检查"""
    data = data or load_constraints(project_dir, module)
    constraints = data.get("constraints", [])
    exceptions = data.get("exceptions", [])

    # 冲突解决：按优先级链排序
    constraints = resolve_constraint_conflicts(constraints, data)

    # 筛选
    if nfr_only:
        constraints = [c for c in constraints
                       if isinstance(c.get("check", ""), str) and c["check"].startswith("nfr:")]
    if domain:
        constraints = [c for c in constraints if c["domain"] == domain]
    if gate:
        constraints = [c for c in constraints if c.get("gate") == gate]

    results = []
    passed = 0
    failed = 0
    manual = 0

    for c in constraints:
        exc = is_exception_active(c["id"], exceptions)
        if exc:
            results.append({
                "id": c["id"],
                "domain": c["domain"],
                "level": c["level"],
                "description": c["description"],
                "passed": True,
                "status": "EXCEPTION",
                "detail": f"例外: {exc['reason']} (至 {exc['valid_until']})",
                "gate": c.get("gate", ""),
            })
            passed += 1
            continue

        ok, detail = run_check(c, project_dir)
        policy = get_failure_policy(c, data)
        if c.get("manual"):
            status = "MANUAL"
            manual += 1
        elif ok:
            status = "PASS"
            passed += 1
        elif policy == "escalate":
            status = "ESCALATE"
            failed += 1
        else:
            status = "FAIL"
            failed += 1

        results.append({
            "id": c["id"],
            "domain": c["domain"],
            "level": c["level"],
            "description": c["description"],
            "passed": ok,
            "status": status,
            "detail": detail,
            "gate": c.get("gate", ""),
            "failure_policy": get_failure_policy(c, data),
            "recoverable": bool(c.get("auto_recover")),
        })

    # 门禁汇总（从约束矩阵派生）：门禁通过 = 该门下所有 MUST 约束通过；
    # SHOULD 约束失败计入缺口但不阻断门禁。G0 为意图前置门禁，单独统计。
    gates = {}
    for r in results:
        g = r.get("gate", "")
        if not g:
            continue
        gates.setdefault(g, {"total": 0, "passed": 0, "must_total": 0, "must_passed": 0})
        gates[g]["total"] += 1
        if r.get("level") == "MUST":
            gates[g]["must_total"] += 1
            if r["passed"]:
                gates[g]["must_passed"] += 1
        if r["passed"]:
            gates[g]["passed"] += 1
    for g in gates:
        gates[g]["gate_passed"] = (gates[g]["must_total"] == 0) or (
            gates[g]["must_passed"] == gates[g]["must_total"]
        )

    return {
        "project": data.get("project", "UNKNOWN"),
        "total": len(constraints),
        "passed": passed,
        "failed": failed,
        "manual": manual,
        "gates": gates,
        "results": results,
    }


def print_text(report: dict):
    """文本格式输出"""
    print(f"╔══════════════════════════════════════════╗")
    print(f"║  Harness 约束检查 — {report['project']:20s} ║")
    print(f"╚══════════════════════════════════════════╝")
    print()

    by_domain = {}
    for r in report["results"]:
        by_domain.setdefault(r["domain"], []).append(r)

    for domain, items in by_domain.items():
        print(f"━━━ {domain} ━━━")
        for r in items:
            icon = {"PASS": "✅", "FAIL": "❌", "MANUAL": "👤", "EXCEPTION": "⚠️", "ESCALATE": "🚨"}.get(r["status"], "?")
            print(f"  {icon} [{r['id']}] {r['description']}")
            if r["status"] in ("FAIL", "EXCEPTION"):
                print(f"     → {r['detail']}")
            elif r["status"] == "ESCALATE":
                print(f"     → {r['detail']}")
                print(f"     → 🚨 需提交 IO/OA 裁决（on_failure: escalate）")
        print()

    # 门禁汇总
    print("━━━ 门禁汇总 ━━━")
    gates = {}
    for r in report["results"]:
        g = r.get("gate", "")
        if g:
            gates.setdefault(g, {"total": 0, "passed": 0})
            gates[g]["total"] += 1
            if r["passed"]:
                gates[g]["passed"] += 1

    for gid in sorted(gates.keys()):
        g = gates[gid]
        icon = "✅" if g["passed"] == g["total"] else "❌"
        print(f"  {icon} {gid}: {g['passed']}/{g['total']}")

    print()
    print(f"总计: {report['total']} | 通过: {report['passed']} | 失败: {report['failed']} | 人工: {report['manual']}")

    # 统计 escalate 数量
    escalated = sum(1 for r in report["results"] if r.get("status") == "ESCALATE")

    if report["failed"] > 0 and escalated > 0:
        print(f"\n❌ {report['failed']} 条约束失败（其中 🚨 {escalated} 条需人工裁决）！")
    elif report["failed"] > 0:
        print(f"\n❌ {report['failed']} 条约束失败！")
    elif escalated > 0:
        print(f"\n🚨 {escalated} 条约束需人工裁决！")
    else:
        print(f"\n✅ 全部自动约束通过！")


def main():
    reset_runtime_caches()
    parser = argparse.ArgumentParser(description="Harness Engine — 约束执行引擎")
    sub = parser.add_subparsers(dest="command")

    # check 子命令
    check_parser = sub.add_parser("check", help="执行约束检查")
    check_parser.add_argument("--all", action="store_true", help="全量检查")
    check_parser.add_argument("--nfr-only", action="store_true", help="仅运行 NFR 验证器")
    check_parser.add_argument("--domain", default=None, help="按域筛选")
    check_parser.add_argument("--gate", default=None, help="按门禁筛选")
    check_parser.add_argument("--format", choices=["text", "json"], default="text")
    check_parser.add_argument("--project-dir", default=".", help="项目根目录")
    check_parser.add_argument("--module", default=None, help="模块 ID（加载 modules/<id>/constraints.yaml 叠加检查）")
    check_parser.add_argument("--verification-context", default=None,
                              help="可信 Verification Run Context，供 nfr:test_run 复用")

    # list 子命令
    list_parser = sub.add_parser("list", help="列出所有约束")
    list_parser.add_argument("--domain", default=None)
    list_parser.add_argument("--project-dir", default=".")
    list_parser.add_argument("--module", default=None, help="同时列出模块级约束")

    # nfr-list 子命令
    nfr_list_parser = sub.add_parser("nfr-list", help="列出所有可用 NFR 验证器")

    # tests 子命令
    tests_parser = sub.add_parser("tests", help="运行测试套件并返回结构化 JSON")
    tests_parser.add_argument("--project-dir", default=".")
    tests_parser.add_argument("--format", choices=["json", "text"], default="json")
    tests_parser.add_argument("--timeout", type=int, default=300)

    # recover 子命令
    recover_parser = sub.add_parser("recover", help="自动恢复失败的约束")
    recover_parser.add_argument("--domain", default=None, help="按域筛选")
    recover_parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行恢复")
    recover_parser.add_argument("--format", choices=["text", "json"], default="text")
    recover_parser.add_argument("--project-dir", default=".", help="项目根目录")
    recover_parser.add_argument("--module", default=None, help="恢复模块级约束")

    args = parser.parse_args()
    project_dir = Path(args.project_dir).resolve() if hasattr(args, 'project_dir') else Path(".")

    if args.command == "nfr-list":
        print("可用 NFR 验证器:")
        for name, info in NFR_REGISTRY.items():
            print(f"  nfr:{name:20s} — {info['description']}")
        return

    if args.command == "list":
        data = load_constraints(project_dir, getattr(args, "module", None))
        constraints = data.get("constraints", [])
        if args.domain:
            constraints = [c for c in constraints if c["domain"] == args.domain]
        for c in constraints:
            manual = " [人工]" if c.get("manual") else ""
            nfr = " [NFR]" if isinstance(c.get("check", ""), str) and c["check"].startswith("nfr:") else ""
            print(f"[{c['id']}] {c['domain']:6s} {c['level']:4s} {c['description']}{manual}{nfr}")
        return

    if args.command == "check":
        if not args.all and not args.domain and not args.gate:
            print("请���定 --all / --domain / --gate", file=sys.stderr)
            sys.exit(1)

        if args.verification_context:
            data = load_constraints(project_dir, getattr(args, "module", None))
            for constraint in data.get("constraints", []):
                if constraint.get("check") == "nfr:test_run":
                    constraint.setdefault("nfr_params", {})["verification_context"] = args.verification_context
            report = check_constraints(project_dir, args.domain, args.gate, args.format,
                                       nfr_only=args.nfr_only, module=getattr(args, "module", None), data=data)
        else:
            report = check_constraints(project_dir, args.domain, args.gate, args.format,
                                       nfr_only=args.nfr_only, module=getattr(args, "module", None))

        if args.format == "json":
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print_text(report)

        sys.exit(0 if report["failed"] == 0 else 1)

    if args.command == "recover":
        report = recover_constraints(project_dir, args.domain, getattr(args, "module", None), args.dry_run)

        if args.format == "json":
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_recovery(report)

        sys.exit(0 if report["failed_recovery"] == 0 else 1)

    if args.command == "tests":
        res = run_tests(project_dir, {"timeout": args.timeout})
        if args.format == "json":
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"status={res['status']} total={res['total']} passed={res['passed']} "
                  f"failed={res['failed']} errors={res['errors']} coverage={res['coverage']}")
        sys.exit(0)


def _print_recovery(report: dict):
    """恢复报告文本输出"""
    mode = "🔍 预览模式" if report["dry_run"] else "🔧 执行恢复"
    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  Harness Recovery — 约束自动恢复 {mode:8s} ║")
    print(f"╚══════════════════════════════════════════════╝")
    print()
    print(f"检查约束: {report['total_checked']} | 已恢复: {report['recovered']} | 失败: {report['failed_recovery']} | 跳过: {report['skipped']}")
    print()

    status_icons = {
        "RECOVERED": "✅", "ALREADY_OK": "✅", "SKIPPED": "⬜",
        "WOULD_RECOVER": "🔧", "NO_RECOVERY_DEFINED": "❌",
        "RECOVERY_FAILED": "❌", "RECOVERY_UNVERIFIED": "⚠️",
    }
    for r in report["results"]:
        icon = status_icons.get(r["status"], "?")
        print(f"  {icon} [{r['id']}] {r['description']}")
        print(f"     → {r['detail']}")
    print()

    if report["failed_recovery"] == 0 and not report["dry_run"]:
        print("✅ 所有可恢复约束已自动修复")
    elif report["dry_run"]:
        print("💡 使用 --no-dry-run 执行实际恢复")


if __name__ == "__main__":
    main()
