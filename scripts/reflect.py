#!/usr/bin/env python3
"""Reflection LOOP — 反思日志生成 + 证据反哺图谱

从测试结果、约束检查、HITL 记录中自动生成反思日志，
并将关键教训反哺到意图图谱的历史上下文。

用法:
    # 生成反思
    python scripts/reflect.py --task T-003 --test-passed 51 --coverage 94.01

    # 反哺图谱
    python scripts/reflect.py --task T-003 --feedback-to-graph
"""

import argparse
import sys
try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml
from datetime import datetime, date
from pathlib import Path


def generate_reflection(task_id: str, test_passed: int, coverage: float,
                        hitl_count: int, issues: list, patterns: list) -> dict:
    """生成反思日志"""
    return {
        "task": task_id,
        "date": date.today().isoformat(),
        "metrics": {
            "tests_passed": test_passed,
            "coverage_pct": coverage,
            "hitl_interventions": hitl_count,
        },
        "what_worked": _infer_positives(task_id, test_passed, coverage),
        "what_failed": issues if issues else ["无明显问题"],
        "what_to_improve": _infer_improvements(task_id, issues, hitl_count),
        "patterns_discovered": patterns if patterns else _infer_patterns(task_id),
    }


def _infer_positives(task_id: str, tests: int, coverage: float) -> list:
    positives = []
    if tests > 0:
        positives.append(f"{tests} 个测试全部通过")
    if coverage >= 90:
        positives.append(f"覆盖率 {coverage}% 达标")
    positives.append("SCOPE-V 流程完整执行")
    return positives


def _infer_improvements(task_id: str, issues: list, hitl_count: int) -> list:
    improvements = []
    if hitl_count > 1:
        improvements.append("减少 HITL 干预次数：使用 Grill-Me 协议逐条确认，避免一次性抛出完整文档")
    if any("prompt" in str(i).lower() or "上下文" in str(i) for i in issues):
        improvements.append("使用 crop_context.py 裁剪后给 AS，避免全局上下文泄漏")
    if any("文件未落地" in str(i) or "声称创建" in str(i) for i in issues):
        improvements.append("启用 self_consistency_check.py 自动校验产出物")
    if not improvements:
        improvements.append("保持当前流程，下次任务继续复用三层架构模式")
    return improvements


def _infer_patterns(task_id: str) -> list:
    return [
        "router/schemas/service 三层架构模式",
        "TestClient 无需启动服务器即可测试",
        "金额统一 int（分）避免浮点精度",
        "API 统一响应 {code, data, message}",
    ]


def feedback_to_graph(project_dir: Path, reflection: dict, task_desc: str):
    """将反思反哺到意图图谱 §5 历史上下文"""
    graph_file = project_dir / "governance" / "Intent_Graph.md"
    if not graph_file.exists():
        print("⚠️ 意图图谱不存在，跳过反哺")
        return

    content = graph_file.read_text()

    # 构建历史上下文条目
    task_id = reflection["task"]
    lessons = "; ".join(reflection.get("what_to_improve", [])[:2])
    risks = "; ".join(str(i) for i in reflection.get("what_failed", [])[:2])
    patterns = "; ".join(reflection.get("patterns_discovered", [])[:2])

    entry = (
        f"| HX-{task_id} | {task_desc} | {reflection['date']} | "
        f"教训: {lessons} | 风险: {risks} | 模式: {patterns} |\n"
    )

    # 查找已有表格或"活"的提示行，在前面插入
    lines = content.split('\n')
    insert_idx = None

    # 策略1: 查找已有的 HX- 行
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("| HX-"):
            insert_idx = i + 1
            break

    # 策略2: 在 "意图图谱是活的" 之前插入完整表格
    if insert_idx is None:
        for i, line in enumerate(lines):
            if "意图图谱是活的" in line:
                # 插入表格头和第一行
                table_header = [
                    "",
                    "## 5. 历史上下文（自动反哺）",
                    "",
                    "| ID | 事件 | 日期 | 教训/影响 |",
                    "|----|------|------|----------|",
                ]
                for j, header_line in enumerate(table_header):
                    lines.insert(i + j, header_line)
                insert_idx = i + len(table_header)
                break

    if insert_idx:
        lines.insert(insert_idx, entry.rstrip())
        graph_file.write_text('\n'.join(lines))
        print(f"✅ 已反哺到图谱: HX-{task_id}")
    else:
        print("⚠️ 未找到合适的插入位置，请手动添加")


def main():
    parser = argparse.ArgumentParser(description="Reflection LOOP")
    parser.add_argument("--task", required=True, help="任务 ID")
    parser.add_argument("--task-desc", default="", help="任务描述（用于反哺）")
    parser.add_argument("--test-passed", type=int, default=0)
    parser.add_argument("--coverage", type=float, default=0.0)
    parser.add_argument("--hitl-count", type=int, default=0)
    parser.add_argument("--issues", nargs="*", default=[], help="遇到的问题列表")
    parser.add_argument("--patterns", nargs="*", default=[], help="发现的模式")
    parser.add_argument("--feedback-to-graph", action="store_true", help="反哺到意图图谱")
    parser.add_argument("--carry-over", action="store_true",
                        help="[P2] 提取 TODO/注意事项保存为跨任务状态")
    parser.add_argument("--next-task", default=None,
                        help="[P2] 下一任务 ID，自动注入 carry-over 上下文")
    parser.add_argument("--decay-memory", action="store_true",
                        help="[P2] 清理意图图谱中过期的历史上下文")
    parser.add_argument("--decay-days", type=int, default=90,
                        help="[P2] 记忆衰减阈值（天），默认 90")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--output", default=None, help="输出 YAML 文件路径")
    parser.add_argument("--format", choices=["yaml", "text"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    reflection = generate_reflection(
        args.task, args.test_passed, args.coverage,
        args.hitl_count, args.issues, args.patterns
    )

    if args.format == "yaml" or args.output:
        output = yaml.dump(reflection, allow_unicode=True, sort_keys=False)
        if args.output:
            Path(args.output).write_text(output)
            print(f"反思日志已写入: {args.output}")
        else:
            print(output)
    else:
        _print_reflection(reflection)

    if args.feedback_to_graph:
        feedback_to_graph(project_dir, reflection, args.task_desc or f"{args.task} 完成")

    # ── P2: carry-over 模式 ──
    if args.carry_over:
        carry_over_todos(project_dir, args.task, reflection)

    # ── P2: 记忆衰减 ──
    if args.decay_memory:
        decay_graph_memory(project_dir, args.decay_days)

    # ── P2: 跨任务状态传递 ──
    if args.next_task:
        inject_carryover_to_next(project_dir, args.task, args.next_task, reflection)


# ─── P2: 跨任务状态传递（Carry-Over）────────────────────────

def carry_over_todos(project_dir: Path, task_id: str, reflection: dict):
    """从反思中提取 TODO/注意事项，写入统一的 .loop_memory.yaml

    Lance Martin "Memory Write" 零件 — 一个文件串起所有 cycle。
    """
    memory_file = project_dir / "governance" / ".loop_memory.yaml"

    # 加载或初始化
    if memory_file.exists():
        memory = yaml.safe_load(memory_file.read_text()) or {}
    else:
        memory = {
            "project": project_dir.name,
            "last_updated": "",
            "progress": {"completed_nodes": [], "current_node": None,
                         "cycles_completed": 0, "last_cycle_at": ""},
            "carry_over": [],
            "decay_config": {"enabled": True, "max_age_days": 90},
            "decisions": [],
        }

    # 更新进度
    memory["progress"]["cycles_completed"] += 1
    memory["progress"]["last_cycle_at"] = reflection.get("date", "")
    if task_id not in memory["progress"]["completed_nodes"]:
        memory["progress"]["completed_nodes"].append(task_id)

    # 提取 carry-over 条目
    lessons = [str(i) for i in reflection.get("what_failed", []) if i and i != "无明显问题"]
    improvements = [str(i) for i in reflection.get("what_to_improve", [])]
    patterns = reflection.get("patterns_discovered", [])
    open_issues = []

    # 合并到统一的 carry_over 列表
    entry = {
        "from_cycle": memory["progress"]["cycles_completed"],
        "task": task_id,
        "date": reflection.get("date", ""),
        "lessons": lessons,
        "improvements": improvements,
        "patterns": patterns,
        "open_issues": open_issues,
    }
    memory["carry_over"].append(entry)

    # 记忆衰减：标记超过 max_age_days 的条目
    max_age = memory.get("decay_config", {}).get("max_age_days", 90)
    if memory.get("decay_config", {}).get("enabled", True):
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=max_age)
        for item in memory["carry_over"]:
            try:
                item_date = datetime.strptime(item.get("date", "2000-01-01"), "%Y-%m-%d")
                if item_date < cutoff:
                    item["decayed"] = True
            except ValueError:
                pass

    memory["last_updated"] = datetime.now().isoformat()
    memory_file.write_text(yaml.dump(memory, allow_unicode=True, sort_keys=False))
    print(f"📋 Loop Memory 已更新: {memory_file} "
          f"(cycle #{memory['progress']['cycles_completed']}, "
          f"{len(lessons)} 条教训, {len(patterns)} 个模式)")


def inject_carryover_to_next(project_dir: Path, from_task: str, next_task: str, reflection: dict):
    """从 .loop_memory.yaml 提取上一任务的上下文，注入到下一任务的 L3

    同时保留旧版 .carry_over_inject.md 兼容。
    """
    memory_file = project_dir / "governance" / ".loop_memory.yaml"
    if not memory_file.exists():
        print(f"⚠️ 无 Loop Memory 文件，先运行 --carry-over")
        return

    memory = yaml.safe_load(memory_file.read_text()) or {}
    carry_over = memory.get("carry_over", [])

    # 找最近一个 cycle 的条目
    recent = [c for c in carry_over if c.get("task") == from_task]
    if not recent:
        recent = carry_over[-1:] if carry_over else []

    # 生成注入内容
    inject_path = project_dir / "governance" / ".carry_over_inject.md"
    lines = [
        f"# 跨任务上下文传递",
        f"",
        f"> 从 {from_task} 自动传递到 {next_task}",
        f"> 来源: .loop_memory.yaml (cycle {memory['progress']['cycles_completed']})",
        f"",
    ]

    for entry in recent:
        if entry.get("decayed"):
            lines.append(f"## ⚠️ 历史教训（已衰减，仅供参考）")
        else:
            lines.append(f"## ⚠️ 上一任务遗留 ({entry.get('date', '')})")

        for lesson in entry.get("lessons", []):
            lines.append(f"- [教训] {lesson}")
        for imp in entry.get("improvements", []):
            lines.append(f"- [改进] {imp}")

        lines.append(f"\n## 📐 可复用模式")
        for pattern in entry.get("patterns", []):
            lines.append(f"- {pattern}")

    inject_path.write_text('\n'.join(lines))
    print(f"📩 跨任务上下文已注入: {inject_path}")
    print(f"   OA 可将此文件内容追加到 {next_task} 的 L3 上下文中")


# ─── P2: 记忆衰减 ──────────────────────────────────────────

def decay_graph_memory(project_dir: Path, max_days: int = 90):
    """清理意图图谱中过期的历史上下文条目"""
    graph_file = project_dir / "governance" / "Intent_Graph.md"
    if not graph_file.exists():
        print("⚠️ 意图图谱不存在")
        return

    content = graph_file.read_text()
    lines = content.split('\n')

    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=max_days)

    removed = 0
    new_lines = []
    for line in lines:
        # 检查是否是 HX 历史行
        if line.strip().startswith("| HX-"):
            # 提取日期
            m = re.search(r'(\d{4}-\d{2}-\d{2})', line)
            if m:
                try:
                    entry_date = date.fromisoformat(m.group(1))
                    if entry_date < cutoff:
                        # 标记为衰减而非删除
                        decayed = line.replace("| HX-", "| ~~HX-") + "~~"
                        new_lines.append(decayed)
                        removed += 1
                        continue
                except ValueError:
                    pass
        new_lines.append(line)

    if removed > 0:
        graph_file.write_text('\n'.join(new_lines))
        print(f"🧹 记忆衰减: {removed} 条超过 {max_days} 天的历史记录已标记")
    else:
        print(f"✅ 无需衰减，所有记录在 {max_days} 天内")


def _print_reflection(reflection: dict):
    print(f"📝 Reflection — {reflection['task']}")
    print(f"   日期: {reflection['date']}")
    print(f"   指标: {reflection['metrics']['tests_passed']} 测试, "
          f"{reflection['metrics']['coverage_pct']}% 覆盖, "
          f"{reflection['metrics']['hitl_interventions']} 次 HITL")
    print()
    print("✅ 做得好:")
    for w in reflection["what_worked"]:
        print(f"   + {w}")
    print()
    print("❌ 问题:")
    for f in reflection["what_failed"]:
        print(f"   - {f}")
    print()
    print("🔧 改进建议:")
    for i in reflection["what_to_improve"]:
        print(f"   → {i}")
    print()
    print("📐 发现模式:")
    for p in reflection["patterns_discovered"]:
        print(f"   ◈ {p}")


if __name__ == "__main__":
    main()
