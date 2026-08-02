#!/usr/bin/env python3
"""Rollback Safety Verifier — 回滚安全性验证器

在执行 DAG 回退操作前，模拟验证回滚是否安全：
  1. 下游依赖检查：目标节点的下游是否已开始执行
  2. 数据迁移检查：是否有需要反转的数据变更
  3. 图谱一致性：回滚后图谱状态是否一致
  4. 并行组影响：回滚是否影响同组其他节点

与 graph_engine.py 共享 work_graph.yaml 的 DAG 定义。

用法:
    # 验证回滚 T-004 是否安全
    python scripts/verify_rollback_safety.py --target T-004

    # 模拟回滚（不执行，仅分析）
    python scripts/verify_rollback_safety.py --target T-004 --dry-run

    # JSON 输出
    python scripts/verify_rollback_safety.py --target T-004 --format json

退出码: 0 = 回滚安全, 1 = 存在风险, 2 = 回滚不可行
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml


# ─── 文件发现 ──────────────────────────────────────────────

def find_work_graph(project_dir: Path) -> Path | None:
    candidates = [
        project_dir / "governance" / "work_graph.yaml",
        project_dir / "work_graph.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_contract(project_dir: Path, task_id: str) -> Path | None:
    candidates = [
        project_dir / "governance" / "contracts" / f"Intent_Contract_{task_id}.yaml",
        project_dir / "governance" / "contracts" / f"Intent_Contract_{task_id}.md",
        project_dir / "governance" / "contracts" / f"Intent_Contract_{task_id}.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ─── DAG 分析 ──────────────────────────────────────────────

def topological_sort(nodes: dict) -> list:
    """拓扑排序"""
    in_degree = {nid: len(n.get("depends_on", [])) for nid, n in nodes.items()}
    dependents = defaultdict(list)
    for nid, n in nodes.items():
        for dep in n.get("depends_on", []):
            if dep in dependents:
                dependents[dep].append(nid)

    queue = [nid for nid, d in in_degree.items() if d == 0]
    result = []
    while queue:
        nid = queue.pop(0)
        result.append(nid)
        for dep in dependents.get(nid, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    return result


def find_downstream(nodes: dict, target: str) -> list[str]:
    """查找目标节点的所有下游依赖（直接+间接）"""
    # 构建邻接表
    downstream = defaultdict(set)
    for nid, n in nodes.items():
        for dep in n.get("depends_on", []):
            downstream[dep].add(nid)

    # BFS
    visited = set()
    queue = [target]
    while queue:
        current = queue.pop(0)
        for child in downstream.get(current, []):
            if child not in visited:
                visited.add(child)
                queue.append(child)

    return sorted(visited)


def find_upstream(nodes: dict, target: str) -> list[str]:
    """查找目标节点的所有上游依赖"""
    upstream = set()
    for nid, n in nodes.items():
        if target in n.get("depends_on", []):
            upstream.add(nid)
            upstream.update(find_upstream(nodes, nid))
    return sorted(upstream)


def find_parallel_siblings(nodes: dict, target: str) -> list[str]:
    """查找目标节点的并行组兄弟节点"""
    target_node = nodes.get(target, {})
    pg = target_node.get("parallel_group")
    if not pg:
        return []

    siblings = []
    for nid, n in nodes.items():
        if nid != target and n.get("parallel_group") == pg:
            siblings.append(nid)
    return siblings


# ─── 回滚安全性检查 ────────────────────────────────────────

def check_downstream_safety(nodes: dict, target: str, project_dir: Path) -> list[dict]:
    """检查1: 下游依赖节点是否已开始执行"""
    issues = []
    downstream = find_downstream(nodes, target)

    if not downstream:
        return [{"check": "downstream", "status": "OK",
                 "detail": f"节点 {target} 无下游依赖，回滚无传播风险"}]

    for ds in downstream:
        ds_node = nodes.get(ds, {})
        produces = ds_node.get("produces", [])

        # 检查产出物是否已存在
        existing = []
        for p in produces:
            fp = project_dir / p
            if fp.exists():
                existing.append(p)

        if existing:
            issues.append({
                "check": "downstream",
                "node": ds,
                "status": "RISK",
                "severity": "HIGH",
                "detail": f"下游节点 {ds} 已产生文件: {', '.join(existing)}，回滚可能导致不一致",
            })
        else:
            issues.append({
                "check": "downstream",
                "node": ds,
                "status": "OK",
                "severity": "LOW",
                "detail": f"下游节点 {ds} 尚未产生文件，回滚安全",
            })

    return issues


def check_data_migration(project_dir: Path, target: str) -> list[dict]:
    """检查2: 是否有需要反转的数据变更"""
    issues = []

    # 查找 Alembic 迁移文件
    migrations_dir = project_dir / "migrations" / "versions"
    if not migrations_dir.exists():
        migrations_dir = project_dir / "alembic" / "versions"

    if migrations_dir.exists():
        migration_files = sorted(migrations_dir.glob("*.py"), reverse=True)
        if migration_files:
            # 检查最近的迁移是否与此任务相关
            latest = migration_files[0]
            content = latest.read_text()
            if target.lower() in content.lower() or target.replace('-', '_').lower() in content.lower():
                issues.append({
                    "check": "data_migration",
                    "status": "RISK",
                    "severity": "MEDIUM",
                    "detail": f"发现与 {target} 相关的数据库迁移: {latest.name}，回滚可能需要 alembic downgrade",
                })

    # 检查是否有 seed/fixture 数据
    seed_files = list(project_dir.glob("**/seed*.py")) + list(project_dir.glob("**/fixture*.py"))
    for sf in seed_files:
        content = sf.read_text()
        if target.lower() in content.lower():
            issues.append({
                "check": "data_migration",
                "status": "RISK",
                "severity": "LOW",
                "detail": f"发现与 {target} 相关的种子数据: {sf.relative_to(project_dir)}",
            })

    if not issues:
        issues.append({
            "check": "data_migration",
            "status": "OK",
            "detail": "未发现需要反转的数据变更",
        })

    return issues


def check_graph_consistency(nodes: dict, target: str, graph: dict) -> list[dict]:
    """检查3: 回滚后图谱状态是否一致"""
    issues = []

    # 如果目标节点在关键路径上，回滚会导致阻塞
    order = topological_sort(nodes)
    critical_path = find_critical_path(nodes, order)
    if target in critical_path:
        issues.append({
            "check": "graph_consistency",
            "status": "RISK",
            "severity": "HIGH",
            "detail": f"节点 {target} 在关键路径上（{' → '.join(critical_path)}），回滚会阻塞整体进度",
        })

    # 检查是否有分支规则定义了此节点的回滚路径
    branch_rules = graph.get("branch_rules", [])
    has_rollback_rule = any(
        target in str(rule.get("on_failure", "")) or target in str(rule.get("rollback", ""))
        for rule in branch_rules
    )
    if has_rollback_rule:
        issues.append({
            "check": "graph_consistency",
            "status": "OK",
            "detail": f"work_graph.yaml 已为 {target} 定义分支回滚规则",
        })
    else:
        issues.append({
            "check": "graph_consistency",
            "status": "WARN",
            "severity": "LOW",
            "detail": f"work_graph.yaml 中未为 {target} 定义回滚规则（将使用默认行为）",
        })

    return issues


def check_parallel_impact(nodes: dict, target: str) -> list[dict]:
    """检查4: 回滚是否影响同组并行节点"""
    issues = []
    siblings = find_parallel_siblings(nodes, target)

    if not siblings:
        return [{"check": "parallel_impact", "status": "OK",
                 "detail": "无并行组兄弟节点，回滚不影响其他任务"}]

    # 检查兄弟节点状态
    for sib in siblings:
        sib_node = nodes.get(sib, {})
        produces = sib_node.get("produces", [])

        # 如果兄弟节点依赖目标节点的产出，则是风险
        if target in sib_node.get("depends_on", []):
            issues.append({
                "check": "parallel_impact",
                "node": sib,
                "status": "RISK",
                "severity": "HIGH",
                "detail": f"并行组兄弟节点 {sib} 直接依赖 {target}，回滚会导致 {sib} 失效",
            })

    if not issues:
        issues.append({
            "check": "parallel_impact",
            "status": "OK",
            "detail": f"并行组兄弟节点 ({', '.join(siblings)}) 不依赖 {target}，回滚安全",
        })

    return issues


def find_critical_path(nodes: dict, order: list) -> list:
    """找关键路径"""
    distances = {nid: 0 for nid in nodes}
    for nid in order:
        for dep in nodes[nid].get("depends_on", []):
            if dep in distances:
                distances[nid] = max(distances[nid], distances[dep] + 1)

    end_node = max(distances, key=distances.get)
    path = [end_node]
    current = end_node
    while nodes[current].get("depends_on"):
        deps = [(d, distances.get(d, 0)) for d in nodes[current]["depends_on"]]
        current = max(deps, key=lambda x: x[1])[0]
        path.insert(0, current)

    return path


# ─── 主流程 ────────────────────────────────────────────────

def verify_rollback(project_dir: Path, target: str) -> dict:
    """执行回滚安全性验证"""
    result = {
        "target": target,
        "project": project_dir.name,
        "status": "SAFE",
        "risk_level": "NONE",
        "checks": [],
        "recommendations": [],
    }

    # 加载 DAG
    graph_file = find_work_graph(project_dir)
    if not graph_file:
        result["status"] = "UNKNOWN"
        result["risk_level"] = "UNKNOWN"
        result["checks"].append({
            "check": "dag",
            "status": "ERROR",
            "detail": "未找到 work_graph.yaml，无法分析 DAG 结构",
        })
        return result

    with open(graph_file) as f:
        graph = yaml.safe_load(f)

    nodes = graph.get("nodes", {})
    if target not in nodes:
        result["status"] = "UNKNOWN"
        result["risk_level"] = "UNKNOWN"
        result["checks"].append({
            "check": "dag",
            "status": "ERROR",
            "detail": f"节点 {target} 不在 work_graph.yaml 中",
        })
        return result

    # 加载契约（如果存在）
    contract_file = find_contract(project_dir, target)

    # 执行四项检查
    all_issues = []

    # 1. 下游安全
    downstream_issues = check_downstream_safety(nodes, target, project_dir)
    all_issues.extend(downstream_issues)
    result["checks"].append({
        "id": "downstream_safety",
        "name": "下游依赖安全",
        "status": "PASS" if all(i["status"] == "OK" for i in downstream_issues) else "FAIL",
        "items": downstream_issues,
    })

    # 2. 数据迁移
    migration_issues = check_data_migration(project_dir, target)
    all_issues.extend(migration_issues)
    result["checks"].append({
        "id": "data_migration",
        "name": "数据迁移检查",
        "status": "PASS" if all(i["status"] == "OK" for i in migration_issues) else "FAIL",
        "items": migration_issues,
    })

    # 3. 图谱一致性
    consistency_issues = check_graph_consistency(nodes, target, graph)
    all_issues.extend(consistency_issues)
    result["checks"].append({
        "id": "graph_consistency",
        "name": "图谱一致性",
        "status": "PASS" if all(i["status"] == "OK" for i in consistency_issues) else "FAIL",
        "items": consistency_issues,
    })

    # 4. 并行组影响
    parallel_issues = check_parallel_impact(nodes, target)
    all_issues.extend(parallel_issues)
    result["checks"].append({
        "id": "parallel_impact",
        "name": "并行组影响",
        "status": "PASS" if all(i["status"] == "OK" for i in parallel_issues) else "FAIL",
        "items": parallel_issues,
    })

    # 汇总风险等级
    high_risks = [i for i in all_issues if i.get("severity") == "HIGH"]
    medium_risks = [i for i in all_issues if i.get("severity") == "MEDIUM"]

    if high_risks:
        result["risk_level"] = "HIGH"
        result["status"] = "UNSAFE"
        result["recommendations"].append(
            f"存在 {len(high_risks)} 个高风险项，建议先回滚下游节点再回滚 {target}"
        )
    elif medium_risks:
        result["risk_level"] = "MEDIUM"
        result["status"] = "CAUTION"
        result["recommendations"].append(
            f"存在 {len(medium_risks)} 个中风险项，建议人工确认后执行"
        )
    else:
        result["risk_level"] = "LOW"
        result["status"] = "SAFE"
        result["recommendations"].append(f"回滚 {target} 是安全的，可以执行")

    # 具体建议
    if contract_file:
        result["recommendations"].append(
            f"回滚前请确认契约 {contract_file.name} 是否需要同时作废"
        )

    return result


# ─── 输出 ──────────────────────────────────────────────────

def print_text(result: dict):
    print("╔══════════════════════════════════════════════╗")
    print("║  Rollback Safety Verifier — 回滚安全性验证   ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"项目: {result['project']}")
    print(f"回滚目标: {result['target']}")
    print()

    risk_icons = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "✅", "UNKNOWN": "⬜"}
    print(f"风险等级: {risk_icons.get(result['risk_level'], '?')} {result['risk_level']}")
    print(f"回滚判定: {result['status']}")
    print()

    for check in result["checks"]:
        icon = "✅" if check["status"] == "PASS" else "❌"
        print(f"━━━ {icon} {check['name']} ━━━")
        for item in check.get("items", []):
            item_icon = {"OK": "  ✅", "RISK": "  ⚠️", "WARN": "  💡", "ERROR": "  ❌"}.get(item.get("status", ""), "  ?")
            print(f"{item_icon} {item['detail']}")
        print()

    if result["recommendations"]:
        print("📋 建议操作:")
        for i, rec in enumerate(result["recommendations"], 1):
            print(f"  {i}. {rec}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Rollback Safety Verifier — 回滚安全性验证器"
    )
    parser.add_argument("--target", required=True, help="回滚目标节点 ID（如 T-004）")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅分析，不提示实际执行")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = verify_rollback(project_dir, args.target)

    if args.dry_run:
        result["dry_run"] = True

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)

    exit_map = {"SAFE": 0, "CAUTION": 1, "UNSAFE": 2, "UNKNOWN": 2}
    sys.exit(exit_map.get(result["status"], 2))


if __name__ == "__main__":
    main()
