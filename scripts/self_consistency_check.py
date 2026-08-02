#!/usr/bin/env python3
"""Self-Consistency LOOP — 自洽性校验

读取契约 YAML 中声明的 self_consistency 字段，逐项校验：
- 产出物文件是否存在且非空
- API 端点数量是否达标 [仅 Web 项目]
- 测试文件是否可执行
- 前端页面是否已在 app.json 注册 [仅含前端的项目]

用法:
    python scripts/self_consistency_check.py --task T-005 [--max-retries 3]

退出码: 0 = 全部一致, 1 = 存在缺口
"""

import argparse
import json
import re
import subprocess
import sys
try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml
from pathlib import Path


def check_expected_files(project_dir: Path, expected: list) -> tuple[int, int, list]:
    """检查产出物文件是否存在且非空"""
    passed, failed = 0, 0
    missing = []
    for f in expected:
        fp = project_dir / f
        if fp.exists() and fp.stat().st_size > 0:
            passed += 1
        else:
            failed += 1
            missing.append(f)
    return passed, failed, missing


def check_endpoint_count(project_dir: Path, expected_count: int, router_path: str) -> tuple[bool, int]:
    """检查 API 端点数量"""
    fp = project_dir / router_path
    if not fp.exists():
        return False, 0
    try:
        result = subprocess.run(
            ["grep", "-c", "@router", str(fp)],
            capture_output=True, text=True
        )
        actual = int(result.stdout.strip() or 0)
        return actual >= expected_count, actual
    except Exception:
        return False, 0


def check_tests_runnable(project_dir: Path, test_file: str) -> tuple[bool, str]:
    """检查测试文件是否可执行"""
    fp = project_dir / test_file
    if not fp.exists():
        return False, "文件不存在"
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", str(fp), "--collect-only", "-q"],
            capture_output=True, text=True,
            timeout=60,
            cwd=str(project_dir)
        )
        if result.returncode == 0:
            # 提取测试数量
            for line in result.stderr.split('\n') + result.stdout.split('\n'):
                if 'collected' in line or 'test' in line.lower():
                    return True, line.strip()
            return True, "可执行"
        return False, result.stderr.strip()[-100:]
    except subprocess.TimeoutExpired:
        return False, "超时"
    except Exception as e:
        return False, str(e)


def check_frontend_routes(project_dir: Path, expected_pages: list) -> tuple[bool, list]:
    """检查前端页面是否已在 app.json 注册"""
    app_json = project_dir / "frontend" / "app.json"
    if not app_json.exists():
        return True, []  # 无前端项目则跳过

    try:
        config = json.loads(app_json.read_text())
        registered = set(config.get("pages", []))
        missing = [p for p in expected_pages if p not in registered]
        return len(missing) == 0, missing
    except Exception:
        return False, ["app.json 解析失败"]


sys.path.insert(0, str(Path(__file__).parent))
from gov_common import find_contract as _gc_find_contract


def _load_self_consistency_config(contract_file: Path) -> dict:
    """从契约中提取 self_consistency 配置

    - YAML 契约：直接读取顶层 self_consistency 字段
    - MD 契约：查找 ```yaml 围栏块中的 self_consistency 字段，如：
        ```yaml
        self_consistency:
          expected_files: [src/App.tsx]
          expected_endpoints: 5
          router_path: server/routes.ts
        ```
    """
    if contract_file.suffix in (".yaml", ".yml"):
        with open(contract_file) as f:
            contract = yaml.safe_load(f)
        return (contract or {}).get("self_consistency", {}) or {}

    # Markdown：扫描围栏 YAML 块
    text = contract_file.read_text()
    for m in re.finditer(r"```ya?ml\s*\n(.*?)```", text, re.DOTALL):
        try:
            block = yaml.safe_load(m.group(1))
        except Exception:
            continue
        if isinstance(block, dict) and "self_consistency" in block:
            return block["self_consistency"] or {}
    return {}


def check_consistency(project_dir: Path, task_id: str) -> dict:
    """执行自洽性检查"""
    contract_file = _gc_find_contract(project_dir, task_id)
    if contract_file is None:
        return {"error": f"契约文件不存在: Intent_Contract_{task_id}（.yaml/.md）"}

    sc = _load_self_consistency_config(contract_file)
    if not sc:
        return {
            "error": "契约中未定义 self_consistency 字段"
                     "（MD 契约可在 ```yaml 围栏块中声明 self_consistency）",
            "status": "SKIPPED",
        }

    results = {"task": task_id, "checks": [], "all_pass": True}

    # 1. 文件存在检查
    if sc.get("expected_files"):
        passed, failed, missing = check_expected_files(project_dir, sc["expected_files"])
        results["checks"].append({
            "type": "files",
            "passed": passed,
            "failed": failed,
            "missing": missing,
        })
        if failed > 0:
            results["all_pass"] = False

    # 2. 端点数量检查
    if sc.get("expected_endpoints") and sc.get("router_path"):
        ok, actual = check_endpoint_count(project_dir, sc["expected_endpoints"], sc["router_path"])
        results["checks"].append({
            "type": "endpoints",
            "expected": sc["expected_endpoints"],
            "actual": actual,
            "passed": ok,
        })
        if not ok:
            results["all_pass"] = False

    # 3. 测试可执行
    if sc.get("test_file"):
        ok, detail = check_tests_runnable(project_dir, sc["test_file"])
        results["checks"].append({
            "type": "tests",
            "passed": ok,
            "detail": detail,
        })
        if not ok:
            results["all_pass"] = False

    # 4. 前端路由 [可选 — 仅含前端的项目定义 frontend_pages]
    if sc.get("frontend_pages"):
        ok, missing = check_frontend_routes(project_dir, sc["frontend_pages"])
        results["checks"].append({
            "type": "frontend",
            "passed": ok,
            "missing": missing,
        })
        if not ok:
            results["all_pass"] = False

    results["status"] = "PASS" if results["all_pass"] else "FAIL"
    return results


def main():
    parser = argparse.ArgumentParser(description="Self-Consistency LOOP")
    parser.add_argument("--task", required=True, help="任务 ID")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--max-retries", type=int, default=0, help="失败后自动重试次数")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()

    for attempt in range(args.max_retries + 1):
        if attempt > 0:
            print(f"\n🔄 自洽性检查第 {attempt + 1} 次重试...")

        result = check_consistency(project_dir, args.task)

        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            _print_text(result)

        if result.get("all_pass"):
            sys.exit(0)
        elif result.get("status") == "SKIPPED":
            # 契约未声明自洽性配置 — 跳过不算失败，退出码 0 不阻断流程
            print("\n⏭️ 跳过（未声明 self_consistency 配置）")
            sys.exit(0)
        elif attempt < args.max_retries:
            continue
        else:
            print(f"\n❌ 自洽性检查失败（已重试 {args.max_retries} 次）")
            sys.exit(1)


def _print_text(result):
    if result.get("error"):
        print(f"⚠️ {result['error']}")
        return

    print(f"🔍 Self-Consistency Check — {result['task']}")
    print()

    for c in result.get("checks", []):
        icon = "✅" if c["passed"] else "❌"
        if c["type"] == "files":
            print(f"  {icon} 文件检查: {c['passed']}/{c['passed'] + c['failed']}")
            for m in c.get("missing", []):
                print(f"     缺失: {m}")
        elif c["type"] == "endpoints":
            print(f"  {icon} 端点检查: 期望 ≥{c['expected']}, 实际 {c['actual']}")
        elif c["type"] == "tests":
            print(f"  {icon} 测试检查: {c['detail']}")
        elif c["type"] == "frontend":
            missing_str = str(c.get("missing", []))
            print(f"  {icon} 前端路由: {'全部注册' if c['passed'] else '缺失: ' + missing_str}")

    print()
    status = result.get("status", "UNKNOWN")
    if status == "PASS":
        print("✅ 自洽性检查全部通过")
    else:
        print("❌ 自洽性检查存在缺口")


if __name__ == "__main__":
    main()
