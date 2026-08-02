#!/usr/bin/env python3
"""Tools Auditor — 工具调用审计器

读取 tools_manifest.yaml，审计 AS 的实际工具调用是否在授权范围内。
支持三种审计模式：

  1. 白名单审计：检查调用的工具是否在 tools_manifest 中定义
  2. 权限审计：检查高风险工具调用是否经过审批
  3. 边界审计：检查工具调用是否越界（文件路径/网络地址/数据库操作）

用法:
    # 审计工具调用日志
    python scripts/audit_tools.py --log tool_calls.json

    # 检查特定任务类型的工具权限
    python scripts/audit_tools.py --task-type implement

    # 验证工具清单本身是否完整
    python scripts/audit_tools.py --validate-manifest

    # JSON 输出
    python scripts/audit_tools.py --log tool_calls.json --format json

工具调用日志格式 (tool_calls.json):
    [
      {
        "tool_id": "FILE_WRITE",
        "params": {"path": "src/api/food/router.py"},
        "task_id": "T-004",
        "task_type": "implement",
        "timestamp": "2025-07-21T10:30:00Z"
      }
    ]

退出码: 0 = 全部合规, 1 = 存在违规
"""

import argparse
import json
import re
import sys
from pathlib import Path
from fnmatch import fnmatch

try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml


# ─── 文件发现 ──────────────────────────────────────────────

def find_manifest(project_dir: Path) -> Path | None:
    candidates = [
        project_dir / "governance" / "tools_manifest.yaml",
        project_dir / "tools_manifest.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ─── 白名单审计 ────────────────────────────────────────────

def audit_whitelist(call: dict, manifest: dict) -> dict | None:
    """检查工具是否在白名单中"""
    tool_id = call.get("tool_id", "")
    tools = {t["id"]: t for t in manifest.get("tools", [])}

    if tool_id not in tools:
        return {
            "check": "whitelist",
            "status": "VIOLATION",
            "severity": "HIGH",
            "detail": f"工具 '{tool_id}' 不在白名单中",
        }
    return None


# ─── 权限审计 ──────────────────────────────────────────────

def audit_permissions(call: dict, manifest: dict) -> dict | None:
    """检查高风险工具调用是否经过审批"""
    tool_id = call.get("tool_id", "")
    tools = {t["id"]: t for t in manifest.get("tools", [])}
    tool = tools.get(tool_id)

    if not tool:
        return None

    # 需要人工审批的工具
    if tool.get("requires_human"):
        if not call.get("approved_by"):
            return {
                "check": "permissions",
                "status": "VIOLATION",
                "severity": "CRITICAL",
                "detail": f"工具 '{tool_id}' 需要人工审批但缺少 approved_by",
            }

    # 需要 IO 审批的操作
    requires_approval = tool.get("requires_approval_for", [])
    if requires_approval:
        params = call.get("params", {})
        command = params.get("command", "")
        for pattern in requires_approval:
            if pattern in command:
                if not call.get("approved_by"):
                    return {
                        "check": "permissions",
                        "status": "VIOLATION",
                        "severity": "CRITICAL",
                        "detail": f"命令 '{command[:60]}' 匹配禁止模式 '{pattern}'，需 IO 审批",
                    }

    return None


# ─── 边界审计 ──────────────────────────────────────────────

def audit_boundaries(call: dict, manifest: dict) -> list[dict]:
    """检查工具调用是否越界"""
    issues = []
    tool_id = call.get("tool_id", "")
    tools = {t["id"]: t for t in manifest.get("tools", [])}
    tool = tools.get(tool_id)
    params = call.get("params", {})

    if not tool:
        return issues

    # 文件路径边界
    if tool.get("category") == "file_ops":
        path = params.get("path") or params.get("file_path") or ""
        if path:
            # 检查 forbidden 模式
            for pattern in tool.get("forbidden", []):
                if fnmatch(path, pattern) or pattern in path:
                    issues.append({
                        "check": "boundary",
                        "status": "VIOLATION",
                        "severity": "CRITICAL",
                        "detail": f"文件路径 '{path}' 匹配禁止模式 '{pattern}'",
                    })

            # 检查 scope 限制
            scopes = tool.get("scope", [])
            if scopes and not any(fnmatch(path, s) for s in scopes):
                issues.append({
                    "check": "boundary",
                    "status": "VIOLATION",
                    "severity": "HIGH",
                    "detail": f"文件路径 '{path}' 超出授权范围 {scopes[:3]}...",
                })

    # 网络边界
    if tool.get("category") == "network_io":
        url = params.get("url") or params.get("domain") or ""
        if url:
            for domain in tool.get("forbidden_domains", []):
                if domain in url:
                    issues.append({
                        "check": "boundary",
                        "status": "VIOLATION",
                        "severity": "HIGH",
                        "detail": f"URL '{url}' 匹配禁止域名 '{domain}'",
                    })

    # Shell 命令边界
    if tool.get("category") == "shell_exec":
        command = params.get("command") or ""
        for pattern in tool.get("forbidden_patterns", []):
            if pattern in command or re.search(pattern, command):
                issues.append({
                    "check": "boundary",
                    "status": "VIOLATION",
                    "severity": "CRITICAL",
                    "detail": f"命令包含禁止模式 '{pattern}'",
                })

    # 数据库边界
    if tool.get("category") == "db_ops":
        query = params.get("query") or ""
        if query and tool_id == "DB_QUERY":
            # 检查是否只读
            if not any(query.strip().upper().startswith(p) for p in ["SELECT", "EXPLAIN", "PRAGMA"]):
                issues.append({
                    "check": "boundary",
                    "status": "VIOLATION",
                    "severity": "CRITICAL",
                    "detail": f"数据库查询不是只读操作: '{query[:80]}'",
                })

    # 部署环境边界
    if tool_id == "ARTIFACT_DEPLOY":
        env = params.get("environment") or params.get("env") or ""
        forbidden = tool.get("forbidden_environments", [])
        if env in forbidden:
            issues.append({
                "check": "boundary",
                "status": "VIOLATION",
                "severity": "CRITICAL",
                "detail": f"禁止部署到 '{env}' 环境",
            })

    return issues


# ─── 任务-工具匹配审计 ────────────────────────────────────

def audit_task_tool_match(call: dict, manifest: dict) -> dict | None:
    """检查任务类型是否使用了正确的工具集"""
    task_type = call.get("task_type", "")
    tool_id = call.get("tool_id", "")
    matrix = manifest.get("task_tool_matrix", {})

    if not task_type or task_type not in matrix:
        return None

    allowed = matrix[task_type].get("required_tools", []) + matrix[task_type].get("optional_tools", [])

    if tool_id not in allowed:
        return {
            "check": "task_match",
            "status": "WARN",
            "severity": "LOW",
            "detail": f"任务类型 '{task_type}' 通常不使用 '{tool_id}'，请确认是否需要",
        }
    return None


# ─── 清单验证 ──────────────────────────────────────────────

def validate_manifest(manifest: dict) -> list[dict]:
    """验证 tools_manifest.yaml 自身的完整性"""
    issues = []
    tools = manifest.get("tools", [])
    categories = set(manifest.get("tool_categories", {}).keys())
    tool_ids = set()

    for t in tools:
        tid = t.get("id", "")
        if not tid:
            issues.append({"check": "manifest", "status": "ERROR", "detail": "工具缺少 id"})
            continue
        if tid in tool_ids:
            issues.append({"check": "manifest", "status": "ERROR", "detail": f"工具 ID '{tid}' 重复"})
        tool_ids.add(tid)

        # 检查 category 引用
        cat = t.get("category", "")
        if cat and cat not in categories:
            issues.append({"check": "manifest", "status": "WARN", "detail": f"工具 '{tid}' 引用未定义的分类 '{cat}'"})

    # 检查 task_tool_matrix 引用的工具
    matrix = manifest.get("task_tool_matrix", {})
    for task_type, config in matrix.items():
        for req in config.get("required_tools", []):
            if req not in tool_ids:
                issues.append({"check": "manifest", "status": "ERROR", "detail": f"任务类型 '{task_type}' 引用了不存在的工具 '{req}'"})
        for opt in config.get("optional_tools", []):
            if opt not in tool_ids:
                issues.append({"check": "manifest", "status": "WARN", "detail": f"任务类型 '{task_type}' 引用了不存在的可选工具 '{opt}'"})

    return issues


# ─── 主流程 ────────────────────────────────────────────────

def audit_calls(calls: list[dict], manifest: dict) -> dict:
    """审计所有工具调用"""
    results = {
        "total_calls": len(calls),
        "violations": 0,
        "warnings": 0,
        "by_tool": {},
        "by_task": {},
        "issues": [],
    }

    for call in calls:
        tool_id = call.get("tool_id", "UNKNOWN")
        task_id = call.get("task_id", "UNKNOWN")

        # 初始化统计
        if tool_id not in results["by_tool"]:
            results["by_tool"][tool_id] = {"count": 0, "violations": 0}
        results["by_tool"][tool_id]["count"] += 1

        # 执行各项审计
        checks = [
            audit_whitelist(call, manifest),
            audit_permissions(call, manifest),
            *audit_boundaries(call, manifest),
            audit_task_tool_match(call, manifest),
        ]

        call_issues = [c for c in checks if c is not None]
        for issue in call_issues:
            issue["tool_id"] = tool_id
            issue["task_id"] = task_id
            results["issues"].append(issue)

            if issue["status"] == "VIOLATION":
                results["violations"] += 1
                results["by_tool"][tool_id]["violations"] += 1
            elif issue["status"] == "WARN":
                results["warnings"] += 1

    results["status"] = "PASS" if results["violations"] == 0 else "FAIL"
    return results


# ─── 输出 ──────────────────────────────────────────────────

def print_text(result: dict):
    print("╔══════════════════════════════════════════════╗")
    print("║  Tools Auditor — 工具调用审计               ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"审计调用数: {result['total_calls']}")
    print(f"违规: {result['violations']} | 警告: {result['warnings']}")
    print()

    if result["by_tool"]:
        print("━━━ 工具调用统计 ━━━")
        for tool_id, stats in sorted(result["by_tool"].items()):
            vflag = f" ⚠️{stats['violations']}违规" if stats["violations"] > 0 else ""
            print(f"  {tool_id}: {stats['count']} 次{vflag}")

    if result["issues"]:
        print(f"\n❌ 发现 {len(result['issues'])} 个问题:")
        for i, issue in enumerate(result["issues"], 1):
            sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(issue.get("severity", ""), "?")
            print(f"  {sev_icon} [{issue.get('tool_id', '?')}] [{issue.get('task_id', '?')}] {issue['detail']}")
        print()

    if result["status"] == "PASS":
        print("✅ 所有工具调用合规")
    else:
        print(f"❌ 发现 {result['violations']} 个违规，需人工审查")


def print_manifest_issues(issues: list[dict]):
    print("╔══════════════════════════════════════════════╗")
    print("║  Tools Manifest Validator — 清单完整性验证   ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    if not issues:
        print("✅ 工具清单完整，无结构性问题")
        return

    for issue in issues:
        icon = "❌" if issue["status"] == "ERROR" else "⚠️"
        print(f"  {icon} {issue['detail']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Tools Auditor — 工具调用审计器")
    parser.add_argument("--log", default=None, help="工具调用日志 JSON 文件")
    parser.add_argument("--task-type", default=None, help="按任务类型筛选")
    parser.add_argument("--validate-manifest", action="store_true", help="验证工具清单完整性")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    manifest_file = find_manifest(project_dir)

    if not manifest_file:
        print("错误: 未找到 tools_manifest.yaml", file=sys.stderr)
        print("提示: 从 templates/Template_Tools_Manifest.yaml 复制到 governance/tools_manifest.yaml", file=sys.stderr)
        sys.exit(2)

    with open(manifest_file) as f:
        manifest = yaml.safe_load(f)

    # 清单验证模式
    if args.validate_manifest:
        issues = validate_manifest(manifest)
        print_manifest_issues(issues)
        sys.exit(1 if any(i["status"] == "ERROR" for i in issues) else 0)

    # 审计模式
    if not args.log:
        print("请指定 --log <工具调用日志.json> 或 --validate-manifest", file=sys.stderr)
        sys.exit(2)

    with open(args.log) as f:
        calls = json.load(f)

    # 按任务类型筛选
    if args.task_type:
        calls = [c for c in calls if c.get("task_type") == args.task_type]
        if not calls:
            print(f"未找到任务类型 '{args.task_type}' 的工具调用记录")
            sys.exit(0)

    result = audit_calls(calls, manifest)

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
