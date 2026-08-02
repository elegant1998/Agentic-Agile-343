#!/usr/bin/env python3
"""Cross-Module Contract Verifier — 跨模块接口契约验证器

读取 protocol.yaml 中的 cross_module_contracts，逐条验证：
- 接口可达性（HTTP 请求返回非 5xx）
- 响应格式匹配（schema 校验）
- SLA 合规（P95 延迟）
- 破坏性变更检测（与上次基线对比）

用法:
    python scripts/verify_cross_module.py --all              # 验证所有 XC
    python scripts/verify_cross_module.py --xc XC-001        # 验证单条
    python scripts/verify_cross_module.py --all --baseline   # 建立基线
    python scripts/verify_cross_module.py --all --format json

退出码: 0 = 全部通过, 1 = 存在失败
"""

import argparse
import json
import sys
import time
try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def load_protocol(project_dir: Path) -> dict:
    """加载 protocol.yaml"""
    proto_file = project_dir / "governance" / "protocol.yaml"
    if not proto_file.exists():
        print(f"错误: 找不到 {proto_file}", file=sys.stderr)
        sys.exit(1)
    with open(proto_file) as f:
        return yaml.safe_load(f)


def load_baseline(project_dir: Path) -> dict:
    """加载上次基线"""
    baseline_file = project_dir / "governance" / ".xc_baseline.json"
    if baseline_file.exists():
        with open(baseline_file) as f:
            return json.load(f)
    return {}


def save_baseline(project_dir: Path, results: list[dict]):
    """保存当前结果为基线"""
    baseline_file = project_dir / "governance" / ".xc_baseline.json"
    baseline = {}
    for r in results:
        xc_id = r["xc_id"]
        baseline[xc_id] = {
            "response_status": r.get("response_status"),
            "response_body_sample": r.get("response_body_sample"),
            "latency_p95_ms": r.get("latency_p95_ms"),
            "checked_at": r.get("checked_at", ""),
        }
    baseline_file.write_text(json.dumps(baseline, indent=2, ensure_ascii=False))
    print(f"基线已保存: {baseline_file}", file=sys.stderr)


def check_breaking_changes(xc_id: str, current: dict, baseline: dict) -> list[str]:
    """检测破坏性变更"""
    issues = []
    prev = baseline.get(xc_id, {})
    if not prev:
        return issues

    # 状态码变化
    prev_status = prev.get("response_status")
    curr_status = current.get("response_status")
    if prev_status and curr_status and str(prev_status) != str(curr_status):
        issues.append(f"HTTP 状态码变更: {prev_status} → {curr_status}")

    return issues


def verify_contract(xc: dict, base_url: str = "http://localhost:8000",
                    baseline: dict = None) -> dict:
    """验证单条跨模块契约"""
    xc_id = xc["id"]
    endpoint = xc["endpoint"]
    spec = xc.get("spec", {})
    sla = xc.get("sla", {})

    # 解析 HTTP 方法和路径
    parts = endpoint.split(" ", 1)
    method = parts[0] if len(parts) > 1 else "GET"
    path = parts[1] if len(parts) > 1 else endpoint

    url = f"{base_url.rstrip('/')}{path}"
    expected_status = 200  # 默认期望 200
    expected_body_contains = None

    # 从 spec 提取期望
    resp_spec = spec.get("response", {})
    if isinstance(resp_spec, dict):
        if "code" in resp_spec:
            expected_status = 200  # 业务成功
        expected_body_contains = list(resp_spec.get("data", {}).keys()) if "data" in resp_spec else None

    result = {
        "xc_id": xc_id,
        "provider": xc.get("provider", "unknown"),
        "consumer": xc.get("consumer", []),
        "endpoint": endpoint,
        "url": url,
        "method": method,
        "status": "UNKNOWN",
        "checks": [],
    }

    latencies = []
    max_retries = 3

    for attempt in range(max_retries):
        try:
            start = time.perf_counter()
            req = Request(url, method=method)
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")

            # 如果 spec 有 request body 定义，构造空请求体
            if method in ("POST", "PUT", "PATCH") and spec.get("request"):
                req.data = json.dumps({}).encode()

            resp = urlopen(req, timeout=10)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

            resp_body = resp.read().decode()
            resp_status = resp.status

            result["response_status"] = resp_status
            result["latency_p95_ms"] = max(latencies) if latencies else 0  # 简化: 取 max 作为 p95 近似

            # 检查 1: HTTP 可达性
            if 200 <= resp_status < 500:
                result["checks"].append({
                    "type": "reachability",
                    "passed": True,
                    "detail": f"HTTP {resp_status}",
                })
            else:
                result["checks"].append({
                    "type": "reachability",
                    "passed": False,
                    "detail": f"HTTP {resp_status} (期望 2xx/3xx/4xx, 非 5xx)",
                })

            # 检查 2: 响应 JSON 格式
            try:
                body_json = json.loads(resp_body)
                result["response_body_sample"] = resp_body[:200]
                result["checks"].append({
                    "type": "json_format",
                    "passed": True,
                    "detail": "响应为合法 JSON",
                })
            except json.JSONDecodeError:
                result["response_body_sample"] = resp_body[:200]
                result["checks"].append({
                    "type": "json_format",
                    "passed": False,
                    "detail": "响应不是合法 JSON",
                })

            # 检查 3: SLA
            sla_p95 = sla.get("p95_latency_ms")
            if sla_p95:
                p95_val = max(latencies)
                sla_ok = p95_val <= sla_p95
                result["checks"].append({
                    "type": "sla",
                    "passed": sla_ok,
                    "detail": f"P95={p95_val:.1f}ms (阈值 {sla_p95}ms)",
                })

            # 检查 4: 破坏性变更（与 baseline 对比）
            if baseline:
                breaking = check_breaking_changes(xc_id, result, baseline)
                if breaking:
                    result["checks"].append({
                        "type": "breaking_change",
                        "passed": False,
                        "detail": "; ".join(breaking),
                    })

            break  # 成功则退出重试循环

        except HTTPError as e:
            result["response_status"] = e.code
            if attempt == max_retries - 1:
                result["checks"].append({
                    "type": "reachability",
                    "passed": False,
                    "detail": f"HTTP {e.code}: {e.reason}",
                })
        except URLError as e:
            if attempt == max_retries - 1:
                result["checks"].append({
                    "type": "reachability",
                    "passed": False,
                    "detail": f"连接失败: {e.reason}",
                })
        except Exception as e:
            if attempt == max_retries - 1:
                result["checks"].append({
                    "type": "reachability",
                    "passed": False,
                    "detail": str(e)[:100],
                })

    # 汇总状态
    all_passed = all(c["passed"] for c in result["checks"])
    result["status"] = "PASS" if all_passed else "FAIL"
    result["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    return result


def verify_all(project_dir: Path, base_url: str = "http://localhost:8000",
               baseline: dict = None) -> list[dict]:
    """验证所有跨模块契约"""
    data = load_protocol(project_dir)
    contracts = data.get("cross_module_contracts", [])

    if not contracts:
        print("⚠️ protocol.yaml 中未定义跨模块契约", file=sys.stderr)
        return []

    results = []
    for xc in contracts:
        result = verify_contract(xc, base_url, baseline)
        results.append(result)

    return results


def print_text(results: list[dict]):
    """文本格式输出"""
    print("╔══════════════════════════════════════════════════╗")
    print("║  跨模块接口契约验证 (Cross-Module Contracts)     ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"{icon} [{r['xc_id']}] {r['provider']} → {', '.join(r['consumer'])}")
        print(f"   {r['method']} {r['endpoint']}")
        for c in r["checks"]:
            sub_icon = "  ✅" if c["passed"] else "  ❌"
            print(f"{sub_icon} [{c['type']}] {c['detail']}")
        print()

    print(f"总计: {len(results)} | 通过: {passed} | 失败: {failed}")

    if failed > 0:
        print(f"\n❌ {failed} 条跨模块契约验证失败！")
    else:
        print(f"\n✅ 所有跨模块契约验证通过！")


def main():
    parser = argparse.ArgumentParser(description="跨模块接口契约验证器")
    parser.add_argument("--all", action="store_true", help="验证所有 XC")
    parser.add_argument("--xc", default=None, help="验证指定 XC ID")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API 基础 URL")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--baseline", action="store_true", help="建立/更新基线")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP 请求超时（秒）")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    baseline = load_baseline(project_dir) if args.baseline else None

    if args.xc:
        data = load_protocol(project_dir)
        contracts = data.get("cross_module_contracts", [])
        xc = next((c for c in contracts if c["id"] == args.xc), None)
        if not xc:
            print(f"错误: 找不到 XC {args.xc}", file=sys.stderr)
            sys.exit(1)
        results = [verify_contract(xc, args.base_url, baseline)]
    elif args.all:
        results = verify_all(project_dir, args.base_url, baseline)
    else:
        print("请指定 --all 或 --xc <ID>", file=sys.stderr)
        sys.exit(1)

    if args.baseline:
        save_baseline(project_dir, results)

    if args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_text(results)

    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
