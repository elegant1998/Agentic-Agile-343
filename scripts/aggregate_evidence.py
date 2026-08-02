#!/usr/bin/env python3
"""Evidence Aggregator — 多模块证据聚合 + 遥测合并

读取 protocol.yaml 中定义的所有模块，聚合：
- 各模块证据包（Evidence_Bundle.md）→ 聚合发布证据包
- 各模块遥测数据（telemetry.json）→ 合并遥测报告
- 各模块门禁状态 → 全局门禁矩阵

用法:
    python scripts/aggregate_evidence.py --all
    python scripts/aggregate_evidence.py --modules user,order,payment
    python scripts/aggregate_evidence.py --all --output RELEASE_Evidence_Bundle.md
    python scripts/aggregate_evidence.py --all --format json
"""

import argparse
import json
import sys
try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml
from pathlib import Path
from datetime import datetime


def load_protocol(project_dir: Path) -> dict:
    """加载 protocol.yaml"""
    proto_file = project_dir / "governance" / "protocol.yaml"
    if not proto_file.exists():
        print(f"错误: 找不到 {proto_file}", file=sys.stderr)
        sys.exit(1)
    with open(proto_file) as f:
        return yaml.safe_load(f)


def find_telemetry_files(project_dir: Path, modules: list[dict]) -> list[Path]:
    """自动发现各模块的遥测文件

    约定路径:
      WorkBuddy:  governance/telemetry.json
      Codex:      .codex/telemetry.json
      CC:         .claude/telemetry.json
    """
    paths = []
    # 全局遥测
    global_telemetry = project_dir / "governance" / "telemetry.json"
    if global_telemetry.exists():
        paths.append(global_telemetry)

    # 模块级遥测
    for mod in modules:
        mod_dir = project_dir / "modules" / mod["id"]
        candidates = [
            mod_dir / "governance" / "telemetry.json",
            mod_dir / ".codex" / "telemetry.json",
            mod_dir / ".claude" / "telemetry.json",
        ]
        for c in candidates:
            if c.exists():
                paths.append(c)
                break  # 每个模块只取第一个找到的

    return paths


def merge_telemetry(telemetry_files: list[Path]) -> dict:
    """合并多源遥测数据"""
    merged = {
        "merged_at": datetime.now().isoformat(),
        "sources": len(telemetry_files),
        "modules": [],
        "totals": {
            "tasks_total": 0,
            "tasks_completed": 0,
            "hitl_total": 0,
            "token_total": 0,
            "gates_passed_total": 0,
            "gates_total": 0,
        },
    }

    for tf in telemetry_files:
        try:
            data = json.loads(tf.read_text())
        except Exception:
            print(f"⚠️ 无法解析遥测文件: {tf}", file=sys.stderr)
            continue

        # 支持两种格式: 标准 telemetry.json 和简化格式
        module_entry = {
            "source": str(tf),
            "module_id": data.get("project", data.get("module_id", "unknown")),
            "tasks_total": data.get("tasks_assigned", data.get("tasks_total", 0)),
            "tasks_completed": data.get("tasks_completed", 0),
            "first_pass_rate": data.get("first_pass_rate", 0),
            "hitl_count": data.get("hitl_count", 0),
            "token_usage": data.get("token_usage", 0),
            "gates_passed": data.get("gates_passed", 0),
            "gates_total": data.get("gates_total", data.get("total", 0)),
            "coverage_pct": data.get("coverage_pct", data.get("coverage", 0)),
            "benchmark_p95_ms": data.get("benchmark_p95_ms", data.get("bench_p95", 0)),
        }
        merged["modules"].append(module_entry)

        # 累加总计
        merged["totals"]["tasks_total"] += module_entry["tasks_total"]
        merged["totals"]["tasks_completed"] += module_entry["tasks_completed"]
        merged["totals"]["hitl_total"] += module_entry["hitl_count"]
        merged["totals"]["token_total"] += module_entry["token_usage"]
        merged["totals"]["gates_passed_total"] += module_entry["gates_passed"]
        merged["totals"]["gates_total"] += module_entry["gates_total"]

    # 计算聚合指标
    t = merged["totals"]
    t["completion_rate"] = round(t["tasks_completed"] / max(t["tasks_total"], 1) * 100, 1)
    t["gate_pass_rate"] = round(t["gates_passed_total"] / max(t["gates_total"], 1) * 100, 1)

    return merged


def find_evidence_files(project_dir: Path, modules: list[dict]) -> list[Path]:
    """发现各模块证据包"""
    paths = []
    # 全局证据包
    global_evidence = project_dir / "governance" / "evidence" / "Evidence_Bundle.md"
    if global_evidence.exists():
        paths.append(global_evidence)

    # 模块级证据包
    for mod in modules:
        candidates = [
            project_dir / "modules" / mod["id"] / "governance" / "evidence" / "Evidence_Bundle.md",
            project_dir / "modules" / mod["id"] / "governance" / "Evidence_Bundle.md",
        ]
        for c in candidates:
            if c.exists():
                paths.append(c)
                break

    return paths


def check_global_constraints(project_dir: Path, protocol: dict) -> dict:
    """检查全局约束在各模块中的遵守情况

    当前为简化版——只检查 protocol.yaml 中声明的全局约束是否有对应的模块级约束文件。
    完整版需要 harness.py --module 支持。
    """
    global_constraints = protocol.get("global_constraints", [])
    modules = protocol.get("modules", [])

    result = {
        "total": len(global_constraints),
        "modules_checked": len(modules),
        "constraints": [],
    }

    for gc in global_constraints:
        applies_to = gc.get("applies_to", ["all"])
        result["constraints"].append({
            "id": gc["id"],
            "rule": gc["rule"],
            "applies_to": applies_to,
            "status": "PENDING"  # 完整版需要实际检查
        })

    return result


def generate_aggregate_report(project_dir: Path, modules: list[dict],
                               telemetry: dict, global_gates: dict,
                               cross_module_results: list = None) -> str:
    """生成聚合证据包 Markdown"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# 聚合发布证据包",
        f"",
        f"**项目**: {protocol.get('project', 'UNKNOWN')}",
        f"**聚合时间**: {now}",
        f"**聚合模块数**: {len(modules)}",
        f"**状态**: ⬜ PENDING",
        f"",
        f"---",
        f"",
        f"## 1. 模块概览",
        f"",
        f"| 模块 | 负责人 | 工具 | 状态 |",
        f"|------|--------|------|------|",
    ]

    for mod in modules:
        mod_telemetry = next((m for m in telemetry["modules"] if m["module_id"] == mod["id"]), None)
        status = "✅" if mod_telemetry else "⬜"
        lines.append(f"| {mod['name']} | {mod['owner']} | {mod['tool']} | {status} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 2. 全局约束符合性",
        f"",
        f"| 约束 ID | 规则 | 适用模块 | 状态 |",
        f"|---------|------|----------|------|",
    ])

    for gc in global_gates.get("constraints", []):
        lines.append(f"| {gc['id']} | {gc['rule']} | {', '.join(gc['applies_to'])} | ⬜ {gc['status']} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. 遥测聚合",
        f"",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 总任务数 | {telemetry['totals']['tasks_total']} |",
        f"| 完成任务数 | {telemetry['totals']['tasks_completed']} |",
        f"| 完成率 | {telemetry['totals']['completion_rate']}% |",
        f"| HITL 总次数 | {telemetry['totals']['hitl_total']} |",
        f"| Token 总消耗 | {telemetry['totals']['token_total']} |",
        f"| 门禁通过率 | {telemetry['totals']['gate_pass_rate']}% ({telemetry['totals']['gates_passed_total']}/{telemetry['totals']['gates_total']}) |",
        f"",
        f"### 模块明细",
        f"",
        f"| 模块 | 任务完成 | 首次成功率 | HITL | Token | 门禁 |",
        f"|------|----------|-----------|------|-------|------|",
    ])

    for mod in telemetry["modules"]:
        lines.append(
            f"| {mod['module_id']} | {mod['tasks_completed']}/{mod['tasks_total']} | "
            f"{mod['first_pass_rate']}% | {mod['hitl_count']} | {mod['token_usage']} | "
            f"{mod['gates_passed']}/{mod['gates_total']} |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 4. 跨模块契约验证",
        f"",
    ])

    if cross_module_results:
        passed = sum(1 for r in cross_module_results if r["status"] == "PASS")
        failed = sum(1 for r in cross_module_results if r["status"] == "FAIL")
        lines.append(f"| 契约 ID | 提供方 | 消费方 | 状态 |")
        lines.append(f"|---------|--------|--------|------|")
        for r in cross_module_results:
            icon = "✅" if r["status"] == "PASS" else "❌"
            lines.append(f"| {r['xc_id']} | {r['provider']} | {', '.join(r['consumer'])} | {icon} {r['status']} |")
        lines.append(f"")
        lines.append(f"通过: {passed} / 失败: {failed}")
    else:
        lines.append("未执行跨模块契约验证。运行 `verify_cross_module.py --all` 后更新。")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 5. 人类最终裁决区",
        f"",
        f"| 角色 | 裁决 | 签署人 | 日期 | 备注 |",
        f"|------|------|--------|------|------|",
        f"| 全局 IO | _________ | _________ | ________ | |",
        f"| 全局 OA | _________ | _________ | ________ | |",
        f"",
        f"---",
        f"",
        f"> **聚合说明**: 本证据包由 `aggregate_evidence.py` 自动生成。",
        f"> 各模块详细证据见各自 `governance/evidence/Evidence_Bundle.md`。",
        f"> 任一模块门禁未通过，聚合证据包不得标记为 READY_FOR_RELEASE。",
    ])

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="多模块证据聚合器")
    parser.add_argument("--all", action="store_true", help="聚合所有模块")
    parser.add_argument("--modules", default=None, help="逗号分隔的模块 ID 列表")
    parser.add_argument("--output", default=None, help="输出文件路径")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="markdown")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()

    global protocol
    protocol = load_protocol(project_dir)
    all_modules = protocol.get("modules", [])

    # 筛选模块
    if args.modules:
        module_ids = [m.strip() for m in args.modules.split(",")]
        modules = [m for m in all_modules if m["id"] in module_ids]
    elif args.all:
        modules = all_modules
    else:
        print("请指定 --all 或 --modules <id1,id2>", file=sys.stderr)
        sys.exit(1)

    # 聚合遥测
    telemetry_files = find_telemetry_files(project_dir, modules)
    telemetry = merge_telemetry(telemetry_files)

    # 聚合证据
    evidence_files = find_evidence_files(project_dir, modules)

    # 全局约束检查
    global_gates = check_global_constraints(project_dir, protocol)

    # 生成报告
    report = generate_aggregate_report(project_dir, modules, telemetry, global_gates)

    if args.format == "json":
        output = {
            "project": protocol.get("project"),
            "aggregated_at": datetime.now().isoformat(),
            "modules": len(modules),
            "telemetry": telemetry,
            "global_constraints": global_gates,
            "evidence_files": [str(f) for f in evidence_files],
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(report)
        if args.output:
            Path(args.output).write_text(report)
            print(f"\n聚合证据包已写入: {args.output}", file=sys.stderr)

    # 统计摘要
    print(f"\n📊 聚合完成: {len(modules)} 个模块, "
          f"{len(telemetry_files)} 个遥测源, "
          f"{len(evidence_files)} 个证据包",
          file=sys.stderr)


if __name__ == "__main__":
    main()
