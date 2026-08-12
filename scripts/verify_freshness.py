#!/usr/bin/env python3
"""Freshness Verifier — 时间窗口验证器

验证治理工件的时效性，防止 AS 使用过期工件执行任务：

  1. 契约时效：契约签署时间是否超过 N 小时
  2. 图谱变更检测：契约依赖的图谱节点自签署后是否被修改
  3. 约束变更检测：约束矩阵自上次 harness check 以来是否有变更
  4. 依赖工件版本：契约引用的外部工件是否过期

自动通过文件时间戳比较实现，不依赖外部服务。

用法:
    # 检查所有工件时效
    python scripts/verify_freshness.py --all

    # 检查指定契约
    python scripts/verify_freshness.py --task T-003

    # 设置阈值（默认 72 小时）
    python scripts/verify_freshness.py --all --max-age-hours 48

    # JSON 输出
    python scripts/verify_freshness.py --all --format json

退出码: 0 = 全部新鲜, 1 = 存在过期工件
"""

import argparse
import json
import os
import re
import sys
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

from gov_common import (
    ContractConflictError,
    extract_task_id,
    find_constraints,
    find_contract,
    find_contracts,
    find_graph,
    is_task_completed,
    parse_contract,
)

try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml


def find_evidence(project_dir: Path) -> list[Path]:
    candidates = [
        project_dir / "governance" / "Evidence_Bundle.md",
        project_dir / "docs" / "Evidence_Bundle.md",
        project_dir / "Evidence_Bundle.md",
    ]
    return [c for c in candidates if c.exists()]


# ─── 时间戳工具 ────────────────────────────────────────────

def get_mtime(path: Path) -> datetime:
    """获取文件修改时间（UTC）"""
    ts = os.path.getmtime(str(path))
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def get_age_hours(path: Path, reference: datetime = None) -> float:
    """计算文件距今的小时数"""
    if reference is None:
        reference = datetime.now(timezone.utc)
    mtime = get_mtime(path)
    return (reference - mtime).total_seconds() / 3600


def get_checksum(path: Path) -> str:
    """计算文件 SHA256"""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def extract_signed_date(contract_path: Path) -> datetime | None:
    """从契约文件中提取签署日期"""
    content = contract_path.read_text()

    if contract_path.suffix in (".yaml", ".yml"):
        try:
            data = parse_contract(contract_path)["raw"]
            signed = data.get("signed_date") or data.get("date")
            if signed:
                return _parse_date(str(signed))
        except Exception:
            pass
    else:
        metadata = parse_contract(contract_path).get("metadata", {})
        for key in ("签署日期", "创建日期", "日期", "Signed Date", "Date"):
            if metadata.get(key):
                return _parse_date(metadata[key])

    # Markdown 契约：查找签署日期
    patterns = [
        r'(?:签署|Signed|签名).*?[:：]\s*(\d{4}-\d{2}-\d{2})',
        r'(?:Date|日期).*?[:：]\s*(\d{4}-\d{2}-\d{2})',
        r'(\d{4}-\d{2}-\d{2})\s*$',
    ]
    for pat in patterns:
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            return _parse_date(m.group(1))

    return None


def _parse_date(date_str: str) -> datetime | None:
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ─── 验证逻辑 ──────────────────────────────────────────────

def check_contract_age(contract_path: Path, max_age_hours: float) -> dict:
    """检查1: 契约签署时效"""
    task_id = extract_task_id(contract_path)
    signed = extract_signed_date(contract_path)

    if not signed:
        # 如果未找到签署日期，用文件修改时间作为近似
        signed = get_mtime(contract_path)
        return {
            "task": task_id,
            "check": "contract_age",
            "status": "WARN",
            "detail": "契约未检测到签署日期（使用文件修改时间作为近似）",
            "age_hours": round(get_age_hours(contract_path), 1),
            "max_age_hours": max_age_hours,
            "expired": get_age_hours(contract_path) > max_age_hours,
        }

    age = (datetime.now(timezone.utc) - signed).total_seconds() / 3600
    expired = age > max_age_hours

    return {
        "task": task_id,
        "check": "contract_age",
        "status": "FAIL" if expired else "PASS",
        "detail": (f"契约已签署 {age:.1f} 小时（阈值 {max_age_hours}h）"
                   if expired else f"契约签署于 {age:.1f} 小时前，仍在有效期内"),
        "age_hours": round(age, 1),
        "max_age_hours": max_age_hours,
        "expired": expired,
        "signed_date": signed.isoformat(),
    }


def check_graph_changes(contract_path: Path, graph_file: Path) -> dict | None:
    """检查2: 图谱自契约签署后是否变更"""
    if not graph_file or not graph_file.exists():
        return None

    task_id = extract_task_id(contract_path)
    signed = extract_signed_date(contract_path) or get_mtime(contract_path)
    graph_mtime = get_mtime(graph_file)

    changed = _changed_after_signed(graph_mtime, signed)
    return {
        "task": task_id,
        "check": "graph_changes",
        "status": "FAIL" if changed else "PASS",
        "detail": ("图谱在契约签署后有更新，契约可能基于过时图谱"
                   if changed else "图谱自契约签署后未变更"),
        "graph_mtime": graph_mtime.isoformat(),
        "contract_signed": signed.isoformat(),
        "changed": changed,
    }


def check_constraints_changes(contract_path: Path,
                               constraints_file: Path) -> dict | None:
    """检查3: 约束矩阵自契约签署后是否变更"""
    if not constraints_file or not constraints_file.exists():
        return None

    task_id = extract_task_id(contract_path)
    signed = extract_signed_date(contract_path) or get_mtime(contract_path)
    constraints_mtime = get_mtime(constraints_file)

    changed = _changed_after_signed(constraints_mtime, signed)
    return {
        "task": task_id,
        "check": "constraints_changes",
        "status": "FAIL" if changed else "PASS",
        "detail": ("约束矩阵在契约签署后有变更，契约可能违反新约束"
                   if changed else "约束矩阵自契约签署后未变更"),
        "constraints_mtime": constraints_mtime.isoformat(),
        "contract_signed": signed.isoformat(),
        "changed": changed,
    }


def check_dependency_freshness(contract_path: Path) -> list[dict]:
    """检查4: 契约引用的依赖工件是否过期"""
    task_id = extract_task_id(contract_path)

    if contract_path.suffix in (".yaml", ".yml"):
        try:
            data = parse_contract(contract_path)["raw"]
        except Exception:
            return []

        deps = data.get("depends_on", [])
        if not deps:
            return []

        issues = []
        for dep in deps:
            # 如果是任务 ID，检查对应契约
            project_dir = contract_path.parents[2]
            dep_contract = find_contract(project_dir, str(dep))
            if dep_contract is not None:
                dep_age = get_age_hours(dep_contract)
                if dep_age > 168:  # 一周
                    issues.append({
                        "task": task_id,
                        "check": "dependency_freshness",
                        "status": "WARN",
                        "detail": f"依赖契约 {dep} 已创建 {dep_age:.0f} 小时（> 7 天），可能过期",
                    })

        return issues

    return []


def _changed_after_signed(artifact_mtime: datetime, signed: datetime) -> bool:
    """日期级签署不伪造时分；同日变更视为同一签署窗口。"""
    if signed.hour == signed.minute == signed.second == signed.microsecond == 0:
        return artifact_mtime.date() > signed.date()
    return artifact_mtime > signed


# ─── 主流程 ────────────────────────────────────────────────

def verify_freshness(project_dir: Path, max_age_hours: float,
                     task_id: str = None) -> dict:
    """执行时间窗口验证"""
    result = {
        "project": project_dir.name,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "max_age_hours": max_age_hours,
        "status": "PASS",
        "contracts": [],
        "summary": {"total": 0, "fresh": 0, "expired": 0, "warn": 0},
    }

    # 发现文件
    try:
        contract_files = ([find_contract(project_dir, task_id)] if task_id
                          else find_contracts(project_dir))
    except ContractConflictError as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
        return result
    if task_id:
        if contract_files[0] is None:
            result["status"] = "FAIL"
            result["error"] = f"未找到契约文件: Intent_Contract_{task_id}"
            return result
        contract_files = [contract_files[0]]

    # 豁免已完成任务：任务已有签署证据包（HITL 裁决）时，
    # 时效检查失去意义——契约已履行完毕，不存在"用过期契约执行"的风险
    skipped_completed = []
    active_files = []
    for cf in contract_files:
        tid = extract_task_id(cf)
        if is_task_completed(project_dir, tid):
            skipped_completed.append(tid)
        else:
            active_files.append(cf)
    if skipped_completed:
        result["skipped_completed"] = skipped_completed
    contract_files = active_files
    if not contract_files:
        # 全部任务均已完成 — 无时效风险
        result["status"] = "PASS"
        return result

    graph_file = find_graph(project_dir)
    constraints_file = find_constraints(project_dir)

    for cf in contract_files:
        task = extract_task_id(cf)
        contract_result = {
            "task": task,
            "file": str(cf.relative_to(project_dir)),
            "status": "FRESH",
            "checks": [],
        }

        # 1. 契约时效
        age_check = check_contract_age(cf, max_age_hours)
        contract_result["checks"].append(age_check)

        # 2. 图谱变更
        if graph_file:
            gc = check_graph_changes(cf, graph_file)
            if gc:
                contract_result["checks"].append(gc)

        # 3. 约束变更
        if constraints_file:
            cc = check_constraints_changes(cf, constraints_file)
            if cc:
                contract_result["checks"].append(cc)

        # 4. 依赖工件
        dep_checks = check_dependency_freshness(cf)
        contract_result["checks"].extend(dep_checks)

        # 汇总状态
        has_expired = any(c.get("expired") or c.get("changed") for c in contract_result["checks"])
        has_warn = any(c["status"] == "WARN" for c in contract_result["checks"])
        if has_expired:
            contract_result["status"] = "EXPIRED"
            result["summary"]["expired"] += 1
            result["status"] = "FAIL"
        elif has_warn:
            contract_result["status"] = "WARN"
            result["summary"]["warn"] += 1
            if result["status"] == "PASS":
                result["status"] = "WARN"
        else:
            contract_result["status"] = "FRESH"
            result["summary"]["fresh"] += 1

        result["summary"]["total"] += 1
        result["contracts"].append(contract_result)

    # 全局检查：约束矩阵 vs 上次 harness 检查
    if constraints_file and not task_id:
        harness_cache = project_dir / ".harness_last_check"
        if harness_cache.exists():
            last_check = get_mtime(harness_cache)
            constraints_mtime = get_mtime(constraints_file)
            if constraints_mtime > last_check:
                result.setdefault("global_issues", []).append({
                    "check": "harness_staleness",
                    "status": "FAIL",
                    "detail": "约束矩阵自上次 harness check 后有变更，建议重新执行 harness.py check --all",
                })
                result["status"] = "FAIL"

    return result


# ─── 输出 ──────────────────────────────────────────────────

def print_text(result: dict):
    print("╔══════════════════════════════════════════════╗")
    print("║  Freshness Verifier — 时间窗口验证          ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"项目: {result['project']}")
    print(f"检查时间: {result['checked_at'][:19]}")
    print(f"时效阈值: {result['max_age_hours']} 小时")
    print()

    if result.get("error"):
        print(f"❌ {result['error']}")
        return

    for ct in result.get("contracts", []):
        status_icons = {"FRESH": "✅", "EXPIRED": "❌", "WARN": "⚠️"}
        icon = status_icons.get(ct["status"], "?")
        print(f"━━━ {icon} {ct['task']} ({ct['file']}) — {ct['status']} ━━━")

        for check in ct.get("checks", []):
            c_icons = {"PASS": "  ✅", "FAIL": "  ❌", "WARN": "  ⚠️"}
            c_icon = c_icons.get(check["status"], "  ?")
            print(f"{c_icon} [{check['check']}] {check['detail']}")
        print()

    # 全局问题
    for gi in result.get("global_issues", []):
        print(f"⚠️ [{gi['check']}] {gi['detail']}")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    s = result["summary"]
    print(f"总计: {s['total']} 契约 | 新鲜: {s['fresh']} | 过期: {s['expired']} | 警告: {s['warn']}")

    if result["status"] == "PASS":
        print(f"\n✅ 所有工件在时效窗口内")
    elif result["status"] == "WARN":
        print(f"\n⚠️ 存在需关注的工件，建议尽快处理")
    else:
        print(f"\n❌ 存在过期工件，必须重新签署/审查后才能继续")


def main():
    parser = argparse.ArgumentParser(
        description="Freshness Verifier — 时间窗口验证器"
    )
    parser.add_argument("--all", action="store_true", help="检查所有契约")
    parser.add_argument("--task", default=None, help="检查指定契约")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--max-age-hours", type=float, default=72.0,
                        help="最大有效期（小时），默认 72")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    if not args.all and not args.task:
        print("请指定 --all 或 --task <ID>", file=sys.stderr)
        sys.exit(2)

    project_dir = Path(args.project_dir).resolve()
    result = verify_freshness(project_dir, args.max_age_hours, args.task)

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)

    exit_map = {"PASS": 0, "WARN": 1, "FAIL": 2}
    sys.exit(exit_map.get(result["status"], 2))


if __name__ == "__main__":
    main()
