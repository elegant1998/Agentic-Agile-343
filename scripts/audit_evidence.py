#!/usr/bin/env python3
"""Evidence Bundle Auditor — 证据包完整性审计器

对照 constraints.yaml 中定义的 gate（门禁），逐门禁检查
Evidence_Bundle.md 中是否有对应的证据条目。自动发现证据包和约束定义。

审计维度：
  - 门禁覆盖：每个 gate 在证据包中是否有对应的 § 章节
  - 证据条目：每个 MUST 约束是否有对应的测试/检查结果引用
  - 签署状态：HITL 签署区是否完整（IO 签名/日期/裁决）

用法:
    # 审计当前项目的证据包
    python scripts/audit_evidence.py

    # 指定路径
    python scripts/audit_evidence.py --project-dir /path/to/project

    # JSON 输出（供 CI 消费）
    python scripts/audit_evidence.py --format json

退出码: 0 = 证据包完整, 1 = 存在缺口
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml


# ─── 文件发现（项目通用）────────────────────────────────────

def find_constraints_file(project_dir: Path) -> Path | None:
    """自动发现 constraints.yaml"""
    candidates = [
        project_dir / "governance" / "constraints.yaml",
        project_dir / "constraints.yaml",
        project_dir / ".github" / "constraints.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


sys.path.insert(0, str(Path(__file__).parent))
from gov_common import find_evidence_bundles as _gc_find_ebs


def find_evidence_bundle(project_dir: Path) -> Path | None:
    """自动发现单个证据包（兼容单文件模式）"""
    ebs = _gc_find_ebs(project_dir)
    return ebs[0] if ebs else None


def find_all_evidence_bundles(project_dir: Path) -> list[Path]:
    """发现所有证据包（EB-T-XXX 拆分模式 + 单文件模式）"""
    return _gc_find_ebs(project_dir)


# ─── 解析 ──────────────────────────────────────────────────

def parse_gates(constraints_data: dict) -> dict[str, dict]:
    """从 constraints.yaml 提取所有门禁定义"""
    gates = {}
    for c in constraints_data.get("constraints", []):
        gate_id = c.get("gate", "")
        if not gate_id:
            continue
        if gate_id not in gates:
            gates[gate_id] = {
                "id": gate_id,
                "constraints": [],
                "must_count": 0,
                "total_count": 0,
            }
        gates[gate_id]["constraints"].append(c)
        gates[gate_id]["total_count"] += 1
        if c.get("level") == "MUST":
            gates[gate_id]["must_count"] += 1
    return gates


def parse_evidence_sections(evidence_text: str) -> dict[str, dict]:
    """解析 Evidence_Bundle.md 的章节结构"""
    sections = {}

    # 查找所有 ## 二级标题（或 # 一级标题对应的门禁章节）
    current_section = None
    current_content = []

    for line in evidence_text.split('\n'):
        # 匹配 ## 或 # 开头的标题
        m = re.match(r'^#{1,3}\s+(.+?)(?:\s*\{.*?\})?\s*$', line)
        if m:
            if current_section:
                sections[current_section] = {
                    "title": current_section_title,
                    "content": '\n'.join(current_content),
                    "has_test_results": _has_test_results('\n'.join(current_content)),
                    "has_bench_results": _has_bench_results('\n'.join(current_content)),
                    "has_signature": _has_signature('\n'.join(current_content)),
                    "line_count": len(current_content),
                }
            current_section_title = m.group(1).strip()
            # 尝试匹配门禁 ID (G1-G5, GATE-1, 等)
            gate_match = re.search(r'(G\d+|GATE[_-]?\d+)', current_section_title, re.IGNORECASE)
            current_section = gate_match.group(1).upper() if gate_match else current_section_title
            current_content = []
        elif current_section is not None:
            current_content.append(line)

    # 最后一节
    if current_section:
        sections[current_section] = {
            "title": current_section_title,
            "content": '\n'.join(current_content),
            "has_test_results": _has_test_results('\n'.join(current_content)),
            "has_bench_results": _has_bench_results('\n'.join(current_content)),
            "has_signature": _has_signature('\n'.join(current_content)),
            "line_count": len(current_content),
        }

    return sections


def _has_test_results(content: str) -> bool:
    """检测是否包含测试结果"""
    indicators = [
        r'passed', r'PASSED', r'PASS',
        r'测试通过', r'通过率',
        r'\d+/\d+\s*(passed|通过)',
        r'pytest', r'coverage',
        r'```.*\n.*PASSED',
    ]
    return any(re.search(p, content, re.IGNORECASE) for p in indicators)


def _has_bench_results(content: str) -> bool:
    """检测是否包含性能基准结果"""
    indicators = [
        r'benchmark', r'Benchmark', r'BENCHMARK',
        r'p\d{2}', r'p95', r'p99',
        r'latency', r'throughput',
        r'性能', r'基准',
        r'ms', r'rps',
    ]
    return any(re.search(p, content, re.IGNORECASE) for p in indicators)


def _has_signature(content: str) -> bool:
    """检测是否包含签署"""
    indicators = [
        r'IO.*签', r'签署', r'签名',
        r'Sign\s*[:：]', r'Approved\s*[:：]',
        r'Date\s*[:：]', r'日期\s*[:：]',
    ]
    return any(re.search(p, content, re.IGNORECASE) for p in indicators)


# ─── 审计逻辑 ──────────────────────────────────────────────

def audit(project_dir: Path) -> dict:
    """执行完整审计"""
    audit_result = {
        "project": project_dir.name,
        "date": date.today().isoformat(),
        "status": "PASS",
        "gates": {},
        "issues": [],
        "warnings": [],
    }

    # Step 1: 加载约束定义
    constraints_file = find_constraints_file(project_dir)
    if not constraints_file:
        audit_result["status"] = "FAIL"
        audit_result["issues"].append("未找到 constraints.yaml，无法执��门禁审计")
        return audit_result

    with open(constraints_file) as f:
        constraints_data = yaml.safe_load(f)

    expected_gates = parse_gates(constraints_data)
    if not expected_gates:
        audit_result["status"] = "FAIL"
        audit_result["issues"].append("constraints.yaml 中未定义任何 gate")
        return audit_result

    # Step 2: 加载证据包
    evidence_files = find_all_evidence_bundles(project_dir)
    if not evidence_files:
        audit_result["status"] = "FAIL"
        audit_result["issues"].append("未找到 Evidence_Bundle.md")
        # 列出期望的门禁
        for gid, ginfo in expected_gates.items():
            audit_result["gates"][gid] = {
                "covered": False,
                "must_constraints": ginfo["must_count"],
                "total_constraints": ginfo["total_count"],
                "issues": ["证据包不存在"],
            }
        return audit_result

    # 合并所有证据包全文（用于约束 ID 覆盖检索）
    all_evidence_text = "\n".join(ef.read_text() for ef in evidence_files)
    # 同时保留章节解析结果（用于测试/性能证据检测）
    all_sections = {}
    for ef in evidence_files:
        all_sections.update(parse_evidence_sections(ef.read_text()))

    has_any_test_results = any(s["has_test_results"] for s in all_sections.values())

    # Step 3: 逐门禁对照 —— 按"约束 ID 是否在证据包中被引用"判定覆盖
    # （适配 Template_Evidence_Bundle §3 约束符合性表按域组织 + EB-T-XXX 按任务拆分的实践）
    for gid, ginfo in expected_gates.items():
        gate_audit = {
            "covered": False,
            "must_constraints": ginfo["must_count"],
            "total_constraints": ginfo["total_count"],
            "issues": [],
        }

        must_constraints = [c for c in ginfo["constraints"] if c.get("level") == "MUST"]
        uncovered = [
            c["id"] for c in must_constraints
            if c.get("id") and c["id"] not in all_evidence_text
        ]

        if not uncovered:
            gate_audit["covered"] = True
        else:
            gate_audit["issues"].append(
                f"{len(uncovered)} 条 MUST 约束未在证据包中引用: {', '.join(uncovered[:5])}"
                + (" ..." if len(uncovered) > 5 else "")
            )
            audit_result["status"] = "FAIL"

        # 有 MUST 约束但全局无任何测试结果引用 → 提示证据充实度不足
        if ginfo["must_count"] > 0 and not has_any_test_results:
            gate_audit["issues"].append("证据包缺少测试结果引用")

        if gate_audit["issues"]:
            audit_result["issues"].extend(
                f"[{gid}] {issue}" for issue in gate_audit["issues"]
            )

        audit_result["gates"][gid] = gate_audit

    # Step 4: 检查 HITL 签署区
    htil_signed = False
    for ef in evidence_files:
        text = ef.read_text()
        if _has_signature(text):
            htil_signed = True
            break

    if not htil_signed:
        audit_result["warnings"].append("证据包缺少 IO 签署（HITL 未完成）")

    # Step 5: 检查是否有门禁在证据包中存在但约束矩阵未定义（多余证据）
    extra_sections = set(all_sections.keys()) - set(expected_gates.keys())
    # 过滤掉非门禁章节（如 "概述"、"总结" 等）
    real_extra = [s for s in extra_sections if re.match(r'^(G\d+|GATE[_-]?\d+)', s, re.IGNORECASE)]
    if real_extra:
        audit_result["warnings"].append(f"证据包包含约束矩阵未定义的额外门禁: {', '.join(real_extra)}")

    return audit_result


# ─── 输出 ──────────────────────────────────────────────────

def print_text(result: dict):
    """文本格式输出"""
    print("╔══════════════════════════════════════════════╗")
    print("║   Evidence Bundle Auditor — 证据包完整性审计  ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"项目: {result['project']}")
    print(f"审计日期: {result['date']}")
    print()

    # 门禁覆盖矩阵
    print("━━━ 门禁覆盖矩阵 ━━━")
    print(f"  {'门禁':8s} {'覆盖':6s} {'约束数':6s} {'状态'}")
    print(f"  {'-'*8} {'-'*6} {'-'*6} {'-'*10}")

    for gid in sorted(result["gates"].keys()):
        g = result["gates"][gid]
        cov = "✅" if g["covered"] else "❌"
        status = "完整" if not g["issues"] else f"{len(g['issues'])} 个问题"
        print(f"  {gid:8s} {cov:6s} {g['total_constraints']:>4d}   {status}")

    print()

    # 问题清单
    if result["issues"]:
        print(f"❌ 发现 {len(result['issues'])} 个问题:")
        for i, issue in enumerate(result["issues"], 1):
            print(f"  {i}. {issue}")
        print()

    if result.get("warnings"):
        print(f"⚠️  {len(result['warnings'])} 个警告:")
        for w in result["warnings"]:
            print(f"  - {w}")
        print()

    if result["status"] == "PASS":
        print("✅ 证据包完整性审计通过 — 所有门禁已覆盖")
    else:
        print("❌ 证据包不完整 — 请补充缺失门禁章节后重新审计")


def main():
    parser = argparse.ArgumentParser(
        description="Evidence Bundle Auditor — 证据包完整性���计器"
    )
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--gate", default=None, help="仅审计指定门禁")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = audit(project_dir)

    # 如果指定了 --gate，过滤结果
    if args.gate:
        gate_id = args.gate.upper()
        if gate_id in result["gates"]:
            result["gates"] = {gate_id: result["gates"][gate_id]}
            result["issues"] = [i for i in result["issues"] if i.startswith(f"[{gate_id}]")]
            result["status"] = "PASS" if not result["issues"] else "FAIL"

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
