#!/usr/bin/env python3
"""Graph Engine — 工作图 DAG 引擎 v1.2

读取 work_graph.yaml，自动推导：
- 可执行计划（拓扑排序 + 并行度分析）
- 当前瓶颈节点
- 关键路径
- 回退路径
- 🆕 auto-loop: 安全的自调度循环（Karpathy 规则10 + Lance Martin Trigger）

用法:
    python scripts/graph_engine.py plan           # 输出执行计划
    python scripts/graph_engine.py status         # 当前进度
    python scripts/graph_engine.py bottlenecks    # 当前瓶颈
    python scripts/graph_engine.py parallel       # 可并行节点
    python scripts/graph_engine.py critical-path  # 关键路径
    python scripts/graph_engine.py auto-loop      # 🆕 安全自调度循环
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
from collections import deque
from datetime import datetime
from pathlib import Path


def load_graph(project_dir: Path) -> dict:
    graph_file = project_dir / "governance" / "work_graph.yaml"
    if not graph_file.exists():
        print(f"❌ 未找到 {graph_file}", file=sys.stderr)
        print(f"   请先创建工作图: cp templates/Template_Work_Graph.yaml governance/work_graph.yaml", file=sys.stderr)
        sys.exit(2)
    with open(graph_file) as f:
        return yaml.safe_load(f)


def topological_sort(nodes: dict) -> list:
    """拓扑排序，返回按依赖顺序排列的节点 ID 列表"""
    in_degree = {nid: len(n.get("depends_on", [])) for nid, n in nodes.items()}
    dependents = {nid: [] for nid in nodes}
    for nid, n in nodes.items():
        for dep in n.get("depends_on", []):
            if dep in dependents:
                dependents[dep].append(nid)

    queue = deque([nid for nid, d in in_degree.items() if d == 0])
    result = []

    while queue:
        nid = queue.popleft()
        result.append(nid)
        for dep in dependents.get(nid, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(result) != len(nodes):
        # 存在环
        remaining = set(nodes.keys()) - set(result)
        print(f"⚠️ DAG 中存在环: {remaining}", file=sys.stderr)
        result.extend(remaining)

    return result


def find_parallel_groups(nodes: dict, order: list) -> list[list]:
    """找出可并行执行的节点组"""
    completed = set()
    groups = []
    remaining = list(order)

    while remaining:
        group = []
        next_remaining = []
        for nid in remaining:
            node = nodes[nid]
            deps = set(node.get("depends_on", []))
            if deps.issubset(completed):
                group.append(nid)
                completed.add(nid)
            else:
                next_remaining.append(nid)
        if group:
            groups.append(group)
        else:
            # 死锁——把剩余的全放进一组
            groups.append(list(next_remaining))
            break
        remaining = next_remaining

    return groups


def find_critical_path(nodes: dict, order: list) -> list:
    """找关键路径（依赖链最长的路径）"""
    # 简化版：找从入口到出口的最长依赖链
    distances = {nid: 0 for nid in nodes}
    for nid in order:
        for dep in nodes[nid].get("depends_on", []):
            if dep in distances:
                distances[nid] = max(distances[nid], distances[dep] + 1)

    # 回溯
    end_node = max(distances, key=distances.get)
    path = [end_node]
    current = end_node
    while nodes[current].get("depends_on"):
        deps = [(d, distances.get(d, 0)) for d in nodes[current]["depends_on"]]
        current = max(deps, key=lambda x: x[1])[0]
        path.insert(0, current)

    return path


def cmd_plan(graph: dict):
    """输出完整执行计划"""
    nodes = graph["nodes"]
    order = topological_sort(nodes)
    groups = find_parallel_groups(nodes, order)
    critical = find_critical_path(nodes, order)
    parallel_strategy = graph.get("parallel_strategy", {})

    print("╔══════════════════════════════════════════╗")
    print(f"║  Work Graph 执行计划 — {graph['project']:20s} ║")
    print("╚══════════════════════════════════════════╝")
    print()

    print("📋 组织图:")
    for role, info in graph["org"]["roles"].items():
        print(f"  {role}: {info['name']} — {', '.join(info['powers'][:2])}...")
    print()

    print("🗺️ 工作图执行顺序:")
    for i, group in enumerate(groups):
        is_parallel = len(group) > 1
        marker = "⚡ 并行组" if is_parallel else "→ 串行"
        print(f"\n  阶段 {i}: {marker}")
        for nid in group:
            node = nodes[nid]
            gate = f" [门禁: {node['gate']}]" if node.get("gate") else ""
            critical_mark = " 🔥关键路径" if nid in critical else ""
            print(f"    [{nid}] {node['label']} ({node['type']}){gate}{critical_mark}")
            if node.get("depends_on"):
                print(f"         依赖: {', '.join(node['depends_on'])}")
            if node.get("parallel_group"):
                pg = node["parallel_group"]
                strategy = parallel_strategy.get(pg, {})
                print(f"         并行组: {pg} (最多 {strategy.get('max_parallel', 'N/A')} 并发)")

    print(f"\n📐 关键路径: {' → '.join(critical)}")
    print(f"   总阶段数: {len(groups)} | 总节点数: {len(nodes)} | 并行机会: {sum(1 for g in groups if len(g)>1)}")


def cmd_status(graph: dict):
    """当前进度（检查 produces 文件是否存在）"""
    nodes = graph["nodes"]
    project_dir = Path(".")
    order = topological_sort(nodes)

    done, in_progress, pending = [], [], []
    found_in_progress = False

    for nid in order:
        node = nodes[nid]
        produces = node.get("produces", [])
        all_exist = True
        any_exist = False
        for p in produces:
            # 通配符展开
            import glob
            matches = glob.glob(str(project_dir / p))
            if matches:
                any_exist = True
            else:
                all_exist = False

        if all_exist and produces:
            done.append(nid)
        elif any_exist and not found_in_progress:
            in_progress.append(nid)
            found_in_progress = True
        elif not found_in_progress:
            pending.append(nid)

    print("📊 Work Graph 状态")
    print()
    for nid in done:
        print(f"  ✅ [{nid}] {nodes[nid]['label']}")
    for nid in in_progress:
        print(f"  🔄 [{nid}] {nodes[nid]['label']}")
    for nid in pending:
        print(f"  ⬜ [{nid}] {nodes[nid]['label']}")


def cmd_bottlenecks(graph: dict):
    """找出瓶颈节点（被多个节点依赖的节点）"""
    nodes = graph["nodes"]
    dep_counts = {}
    for nid, node in nodes.items():
        for dep in node.get("depends_on", []):
            dep_counts[dep] = dep_counts.get(dep, 0) + 1

    bottlenecks = sorted(dep_counts.items(), key=lambda x: -x[1])
    print("🔍 瓶颈分析（被依赖次数）")
    for nid, count in bottlenecks:
        node = nodes.get(nid, {})
        print(f"  [{nid}] {node.get('label', '?')}: 被 {count} 个节点依赖")


def cmd_parallel(graph: dict):
    """列出可并行执行的节点组"""
    nodes = graph["nodes"]
    groups = {}
    for nid, node in nodes.items():
        pg = node.get("parallel_group")
        if pg:
            groups.setdefault(pg, []).append(nid)

    print("⚡ 并行机会")
    for pg, members in groups.items():
        strategy = graph.get("parallel_strategy", {}).get(pg, {})
        print(f"  {pg}: {len(members)} 节点 (最多 {strategy.get('max_parallel', 'N/A')} 并发)")
        for m in members:
            node = nodes[m]
            print(f"    [{m}] {node['label']} — 依赖: {node.get('depends_on', [])}")
    if not groups:
        print("  无并行组定义")


def cmd_reschedule(graph: dict, failed_node: str):
    """P2: 节点失败后重新规划后续节点"""
    nodes = graph["nodes"]
    policy = graph.get("execution_policy", {})

    if failed_node not in nodes:
        print(f"❌ 节点 {failed_node} 不在工作图中")
        return

    print("╔══════════════════════════════════════════════╗")
    print(f"║  DAG Reschedule — 节点 {failed_node} 失败重规划 ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # 1. 找出受影响的下游节点
    affected = []
    for nid, node in nodes.items():
        if failed_node in node.get("depends_on", []):
            affected.append(nid)

    print(f"🔴 失败节点: {failed_node} ({nodes[failed_node]['label']})")
    print(f"📋 受影响下游: {', '.join(affected) if affected else '无（叶节点）'}")
    print()

    # 2. 检查重调度策略
    failed = nodes[failed_node]
    on_timeout = failed.get("on_timeout", policy.get("reschedule_on_timeout", "fail"))
    max_attempts = policy.get("max_reschedule_attempts", 2)

    print(f"⚙️ 重调度策略: {on_timeout}")
    print(f"   最大重试: {max_attempts} 次")

    # 3. 分析替代路径
    if affected:
        print(f"\n🔄 建议重规划方案:")
        # 策略A: 跳过失败节点，直接执行下游（如果下游可以独立运行）
        can_skip = True
        for dep in affected:
            dep_deps = nodes[dep].get("depends_on", [])
            other_deps = [d for d in dep_deps if d != failed_node]
            if not other_deps:
                can_skip = False

        if can_skip:
            print(f"  A) 跳过 {failed_node}，下游节点仍有其他依赖满足 → 继续执行")
        else:
            print(f"  B) {failed_node} 是关键依赖，下游无法独立运行 → 需修复后重试")

        # 策略C: 找替代节点
        parallel_siblings = []
        pg = failed.get("parallel_group")
        if pg:
            for nid, node in nodes.items():
                if node.get("parallel_group") == pg and nid != failed_node:
                    parallel_siblings.append(nid)
        if parallel_siblings:
            print(f"  C) 并行组兄弟节点可继续: {', '.join(parallel_siblings)}")

    # 4. 通知列表
    notify = policy.get("notify_on_timeout", ["OA"])
    print(f"\n📢 通知: {', '.join(notify)}")

    print(f"\n💡 使用 verify_rollback_safety.py --target {failed_node} 分析回滚安全性")


def cmd_timeouts(graph: dict):
    """P2: 显示所有节点的超时配置"""
    nodes = graph["nodes"]
    policy = graph.get("execution_policy", {})

    print("⏱️ 超时配置")
    print(f"  全局默认: {policy.get('default_timeout_minutes', 60)} 分钟/节点")
    print(f"  总超时: {policy.get('max_total_timeout_minutes', 480)} 分钟")
    print()

    print(f"  {'节点':8s} {'标签':20s} {'超时(分)':10s} {'策略':12s}")
    print(f"  {'-'*8} {'-'*20} {'-'*10} {'-'*12}")
    for nid in topological_sort(nodes):
        node = nodes[nid]
        timeout = node.get("timeout_minutes", policy.get("default_timeout_minutes", 60))
        strategy = node.get("on_timeout", "reschedule" if policy.get("reschedule_on_timeout") else "fail")
        print(f"  {nid:8s} {node['label'][:20]:20s} {timeout:>8d}   {strategy:12s}")


# ═══════════════════════════════════════════════════════════
# 🆕 Auto-Loop: 安全的自调度循环
# ═══════════════════════════════════════════════════════════

def _node_status(node_id: str, nodes: dict, project_dir: Path) -> str:
    """判断节点状态: done / in_progress / blocked / ready"""
    node = nodes.get(node_id)
    if not node:
        return "unknown"
    produces = node.get("produces", [])
    if produces:
        all_exist = all((project_dir / p).exists() for p in produces)
        any_exist = any((project_dir / p).exists() for p in produces)
        if all_exist:
            return "done"
        elif any_exist:
            return "in_progress"
    deps = node.get("depends_on", [])
    for dep in deps:
        if _node_status(dep, nodes, project_dir) != "done":
            return "blocked"
    return "ready"


def _find_next_ready(nodes: dict, project_dir: Path, completed: set) -> str | None:
    """找下一个就绪节点"""
    for nid in topological_sort(nodes):
        if nid in completed:
            continue
        status = _node_status(nid, nodes, project_dir)
        if status == "ready":
            return nid
        elif status == "done":
            completed.add(nid)
    return None


def _check_stop_conditions(graph: dict, cycle_count: int, max_cycles: int,
                           completed: set, project_dir: Path) -> tuple:
    """检查终止条件。返回 (should_stop, reason)"""
    nodes = graph["nodes"]
    all_done = all(_node_status(nid, nodes, project_dir) == "done" for nid in nodes)
    if all_done:
        return True, "所有节点已完成"
    if cycle_count >= max_cycles:
        return True, f"达到最大循环次数 ({max_cycles})"
    next_node = _find_next_ready(nodes, project_dir, completed)
    if not next_node:
        blocked = [nid for nid in nodes
                   if _node_status(nid, nodes, project_dir) == "blocked"]
        if blocked:
            return True, f"所有未完成节点均被阻塞: {', '.join(blocked)} — 需 HITL"
        return True, "无更多可执行节点"
    return False, ""


def cmd_auto_loop(graph: dict, project_dir: Path, max_cycles: int = 20,
                  dry_run: bool = False):
    """安全的自调度循环

    安全边界:
      - max_cycles: 硬上限（默认 20），防止无限循环
      - HITL 拦截: 遇到 gate=HITL 的节点自动停止
      - 确定性触发: 只在 depends_on 全部满足时才派发下一节点
      - 不跳过签署: 需要 IO/OA 签署的节点必须人工确认
    """
    nodes = graph["nodes"]

    print("╔══════════════════════════════════════════════╗")
    print("║  🔄 Auto-Loop — 安全自调度循环               ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  最大循环: {max_cycles} 次（硬上限）")
    print(f"  模式: {'🔍 预览（不执行）' if dry_run else '▶️ 执行'}")
    print()

    completed = set()
    cycle = 0
    loop_log = []
    stop_reason = ""

    while cycle < max_cycles:
        cycle += 1

        should_stop, reason = _check_stop_conditions(
            graph, cycle, max_cycles, completed, project_dir)
        if should_stop:
            stop_reason = reason
            print(f"⏹️ 循环终止 (第 {cycle} 次): {reason}")
            break

        next_node = _find_next_ready(nodes, project_dir, completed)
        if not next_node:
            stop_reason = "无可执行节点"
            print(f"⏸️ 暂停 (第 {cycle} 次): 无可执行节点，等待人工介入")
            break

        node = nodes[next_node]
        gate = node.get("gate")

        # HITL 拦截
        if gate == "HITL":
            stop_reason = f"[{next_node}] 需要 IO 签署，自动循环不跳过 HITL"
            print(f"🛑 HITL 拦截 (第 {cycle} 次): [{next_node}] {node['label']} 需要 IO 签署")
            break

        print(f"▶️ 循环 #{cycle}: [{next_node}] {node['label']}")
        print(f"   类型: {node.get('type', '?')} | 域: {node.get('domain', 'N/A')}")
        deps = node.get("depends_on", [])
        if deps:
            print(f"   依赖: {', '.join(deps)} (均已满足)")

        entry = {
            "cycle": cycle, "node": next_node, "label": node["label"],
            "timestamp": datetime.now().isoformat(),
            "action": "DRY_RUN" if dry_run else "DISPATCHED",
        }

        if dry_run:
            print(f"   ⏭️ 预览模式 — 跳过实际执行")
            completed.add(next_node)
            entry["status"] = "SIMULATED"
        else:
            task_id = next_node
            domain = node.get("domain", "")
            print(f"   📋 派发命令:")
            print(f"      crop_context.py --task {task_id} --domain {domain} --enforce-budget")
            if gate:
                print(f"      # 完成后验证: harness.py check --all")
            entry["status"] = "DISPATCHED"

        loop_log.append(entry)
        completed.add(next_node)
        print()

    # 汇总
    print("═" * 50)
    print(f"📊 Auto-Loop 汇总: {cycle} 次循环, {len(completed)} 个节点完成")
    remaining = [nid for nid in nodes if nid not in completed]
    if remaining:
        print(f"   剩余: {', '.join(remaining)}")
    if stop_reason:
        print(f"   终止原因: {stop_reason}")

    # 保存日志
    log_file = project_dir / "governance" / ".auto_loop_log.json"
    log_file.write_text(json.dumps(loop_log, indent=2, ensure_ascii=False))
    print(f"   日志: {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Graph Engine — DAG 引擎")
    parser.add_argument("command", choices=[
        "plan", "status", "bottlenecks", "parallel", "critical-path",
        "reschedule", "timeouts", "auto-loop"
    ])
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--failed-node", default=None, help="失败节点 ID（reschedule 命令使用）")
    parser.add_argument("--max-cycles", type=int, default=20, help="auto-loop 最大循环次数（硬上限）")
    parser.add_argument("--dry-run", action="store_true", help="auto-loop 预览模式，不实际执行")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    graph = load_graph(project_dir)

    if args.command == "plan":
        cmd_plan(graph)
    elif args.command == "status":
        cmd_status(graph)
    elif args.command == "bottlenecks":
        cmd_bottlenecks(graph)
    elif args.command == "parallel":
        cmd_parallel(graph)
    elif args.command == "critical-path":
        critical = find_critical_path(graph["nodes"], topological_sort(graph["nodes"]))
        print("📐 关键路径:", " → ".join(critical))
    elif args.command == "reschedule":
        if not args.failed_node:
            print("请指定 --failed-node <节点ID>", file=sys.stderr)
            sys.exit(2)
        cmd_reschedule(graph, args.failed_node)
    elif args.command == "timeouts":
        cmd_timeouts(graph)
    elif args.command == "auto-loop":
        cmd_auto_loop(graph, project_dir, args.max_cycles, args.dry_run)


if __name__ == "__main__":
    main()
