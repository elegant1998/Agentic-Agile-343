#!/usr/bin/env python3
"""三层上下文裁剪引擎 v2.0

输入任务 ID，从以下三层组装精简 prompt：
  L2: 全局约束（技术栈、API 规范、安全规则）—— 从架构文档 + 约束矩阵提取
  L3: 任务切片（目标/非目标/规则/AC）—— 从 YAML 契约加载
  Ctx: 代码上下文（已有端点、模型、依赖）—— 从 discover_context.py 提取

v2.0 新增:
  --watch:     监听文件变更，自动重新裁剪
  --verify-isolation: 验证裁剪后上下文不包含禁止信息

用法:
    python scripts/crop_context.py --task T-003 [--format text|json]
    python scripts/crop_context.py --task T-003 --watch       # 动态监听模式
    python scripts/crop_context.py --task T-003 --verify-isolation  # 隔离验证
"""

import argparse
import json
import re
import sys
import time
try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml
from pathlib import Path


def load_global_constraints(project_dir: Path) -> dict:
    """从架构文档和约束矩阵动态提取 L2 全局约束

    优先从 docs/architecture.md 提取真实技术栈信息。
    如果架构文档不存在（简单项目跳过了架构设计阶段），
    降级为基础约束——仅包含项目通用规则，不假设任何技术栈。
    """
    arch_file = project_dir / "docs" / "architecture.md"
    constraint_yaml = project_dir / "governance" / "constraints.yaml"

    # 尝试从架构文档提取技术栈
    arch_info = _parse_architecture_doc(arch_file) if arch_file.exists() else {}

    # 从约束 YAML 提取覆盖率阈值等关键门禁
    threshold_info = _parse_constraint_thresholds(constraint_yaml)

    # 基础约束：适用于所有项目类型（不假设技术栈）
    constraints = {
        "project_type": arch_info.get("project_type", "unknown"),
        "tech_stack": arch_info.get("tech_stack", "未定义 — 请查看 docs/architecture.md"),
        "api_spec": arch_info.get("api_spec", ""),
        "auth": arch_info.get("auth", ""),
        "orm": arch_info.get("orm", ""),
        "cache": arch_info.get("cache", ""),
        "test_framework": arch_info.get("test_framework", "pytest"),
        "coverage_threshold": threshold_info.get("coverage", "80%"),
        "error_codes": arch_info.get("error_codes", ""),
        "money_rule": arch_info.get("money_rule", ""),
    }

    # 移除空值字段（精简上下文）
    constraints = {k: v for k, v in constraints.items() if v}

    # 如果架构文档不存在，只返回最基础的通用约束
    if not arch_info:
        constraints = {
            "project_type": "simple",
            "note": "无架构文档 — 本项目跳过了架构设计阶段，技术栈由 AS 在实现时自行决策",
            "test_framework": threshold_info.get("test_framework", "按需选择"),
        }

    return constraints


def _parse_architecture_doc(arch_file: Path) -> dict:
    """从 architecture.md 解析关键字段"""
    info = {}
    try:
        content = arch_file.read_text()
    except Exception:
        return info

    # 提取模式：## 标题 后面的结构化信息
    patterns = {
        "project_type": r'项目类型[：:]\s*(.+)',
        "tech_stack": r'(?:技术栈|后端)[：:]\s*(.+)',
        "api_spec": r'(?:API\s*规范|响应格式)[：:]\s*(.+)',
        "auth": r'(?:认证|鉴权)[：:]\s*(.+)',
        "orm": r'(?:ORM|数据库\s*ORM)[：:]\s*(.+)',
        "cache": r'(?:缓存|Cache)[：:]\s*(.+)',
        "test_framework": r'(?:测试框架)[：:]\s*(.+)',
        "error_codes": r'(?:错误码|Error\s*Codes?)[：:]\s*(.+)',
        "money_rule": r'(?:金额|货币)[：:]\s*(.+)',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()

    return info


def _parse_constraint_thresholds(constraint_yaml: Path) -> dict:
    """从 constraints.yaml 提取覆盖率等阈值"""
    info = {}
    if not constraint_yaml.exists():
        return info

    try:
        data = yaml.safe_load(constraint_yaml.read_text())
    except Exception:
        return info

    for c in data.get("constraints", []):
        check = c.get("check", "")
        # 提取覆盖率阈值
        if isinstance(check, str) and "cov-fail-under" in check:
            m = re.search(r'cov-fail-under[= ](\d+)', check)
            if m:
                info["coverage"] = f"{m.group(1)}%"
        # 提取测试框架
        if isinstance(check, str) and "pytest" in check:
            info["test_framework"] = "pytest"

    return info


def load_coding_guide(project_dir: Path) -> str | None:
    """加载 AI 编码规范，提取硬性红线和分层约束。

    返回精简版（去掉模板说明和空行），适合注入 AI 上下文。
    如果文件不存在或为空，返回 None。
    """
    guide_file = project_dir / "governance" / "AI_Coding_Guide.md"
    if not guide_file.exists() or guide_file.stat().st_size == 0:
        return None

    try:
        content = guide_file.read_text()
    except Exception:
        return None

    # 只提取 §1（硬性红线）和 §2（分层约束）—— 这两个对 AI 编码最有用
    # §3-5（补充禁止项/自检清单/历史记录）留给自检脚本处理
    lines = content.split('\n')
    result = []
    in_section = False
    sections_found = set()

    for line in lines:
        stripped = line.strip()
        # 检测目标章节
        if stripped.startswith('## 1. 硬性红线'):
            in_section = True
            sections_found.add('redlines')
            result.append(stripped)
            continue
        elif stripped.startswith('## 2. 分层约束'):
            in_section = True
            sections_found.add('layers')
            result.append(stripped)
            continue
        elif stripped.startswith('## ') and in_section:
            # 遇到下一个 ## 章节，停止（除非还在 §2 的子章节）
            if stripped.startswith('## 3.') or stripped.startswith('## 4.') or stripped.startswith('## 5.'):
                in_section = False
                continue
            else:
                result.append(stripped)
                continue

        if in_section and stripped:
            # 跳过模板说明行（以 > 开头的引用块）
            if stripped.startswith('>'):
                continue
            result.append(stripped)

    if not result:
        return None

    # 加注来源
    result.insert(0, '> 以下内容来自 governance/AI_Coding_Guide.md')
    return '\n'.join(result)


def load_loop_memory(project_dir: Path, task_id: str) -> str | None:
    """加载跨 cycle 记忆（Lance Martin "Rules Load" 零件）

    从 .loop_memory.yaml 提取对当前任务有用的上下文:
      - 上一 cycle 的教训和可复用模式（未衰减的）
      - 当前进度（哪些节点已完成）
      - 相关决策

    只注入最近 3 个 cycle 的条目，避免上下文膨胀。
    """
    memory_file = project_dir / "governance" / ".loop_memory.yaml"
    if not memory_file.exists():
        return None

    try:
        memory = yaml.safe_load(memory_file.read_text())
    except Exception:
        return None

    if not memory:
        return None

    lines = ["> 以下内容来自 .loop_memory.yaml（跨 cycle 累积记忆）", ""]

    # 进度摘要
    progress = memory.get("progress", {})
    if progress.get("cycles_completed", 0) > 0:
        lines.append(f"**进度**: {progress['cycles_completed']} 个 cycle 已完成")
        completed = progress.get("completed_nodes", [])
        if completed:
            lines.append(f"  已完成节点: {', '.join(completed[-5:])}")
        lines.append("")

    # 最近 3 个 cycle 的教训（跳过已衰减的）
    carry_over = memory.get("carry_over", [])
    recent = [c for c in carry_over[-3:] if not c.get("decayed")]
    if recent:
        lines.append("**最近教训**:")
        for entry in recent:
            for lesson in entry.get("lessons", [])[:2]:  # 每个 cycle 最多 2 条
                lines.append(f"  - [{entry.get('task', '?')}] {lesson}")
        lines.append("")

    # 可复用模式
    all_patterns = []
    for entry in carry_over[-5:]:
        all_patterns.extend(entry.get("patterns", []))
    if all_patterns:
        unique_patterns = list(set(all_patterns))[:5]
        lines.append("**可复用模式**:")
        for p in unique_patterns:
            lines.append(f"  - {p}")
        lines.append("")

    # 相关决策
    decisions = memory.get("decisions", [])
    if decisions:
        lines.append("**关键决策**:")
        for d in decisions[-3:]:
            lines.append(f"  - [{d.get('date', '?')}] {d.get('decision', '')}: {d.get('reason', '')}")
        lines.append("")

    if len(lines) <= 2:  # 只有 header 没有实际内容
        return None

    return '\n'.join(lines)


sys.path.insert(0, str(Path(__file__).parent))
from gov_common import ContractConflictError, find_contract as _gc_find_contract, parse_contract as _gc_parse_contract
from context_providers import build_context


def _to_bullet_list(text) -> list:
    """把 MD 契约的多行文本字段拆成条目列表（兼容已是 list 的 YAML 字段）"""
    if isinstance(text, list):
        return [str(t) for t in text]
    if not text:
        return []
    items = []
    for line in str(text).split('\n'):
        s = line.strip()
        if not s:
            continue
        # 去掉 "1. " / "- " / "❌ " 等前导符号（可组合出现，如 "- ❌ xxx"）
        s = re.sub(r'^(?:(?:\d+[.、)]|[-*])\s*)?(?:❌\s*)?', '', s).strip()
        if s:
            items.append(s)
    return items


def load_yaml_contract(project_dir: Path, task_id: str) -> dict:
    """加载契约（L3 任务切片）— 支持 YAML 和 Markdown 双格式

    统一归一化为：goal/not_goal/rules 列表、ac 字典 {AC-ID: 描述}。
    """
    contract_file = _gc_find_contract(project_dir, task_id)
    if contract_file is None:
        return {}
    if contract_file.suffix in ('.yaml', '.yml'):
        with open(contract_file) as f:
            return yaml.safe_load(f)
    # Markdown 契约：解析后归一化为与 YAML 同形的结构
    parsed = _gc_parse_contract(contract_file)
    return {
        "goal": _to_bullet_list(parsed["goal"]),
        "not_goal": _to_bullet_list(parsed["not_goal"]),
        "rules": {},
        "ac": {a["id"]: a["desc"] for a in parsed["ac"]},
    }


def load_code_context(project_dir: Path) -> dict:
    """进程内获取代码上下文，避免重复 Python 启动。"""
    try:
        from discover_context import discover
        return discover(project_dir)
    except (ImportError, OSError, ValueError):
        return {}


def format_code_context(code_ctx: dict, target_domain: str = None) -> str:
    """格式化代码上下文为文本"""
    lines = []
    if target_domain and target_domain in code_ctx.get("endpoints", {}):
        eps = code_ctx["endpoints"][target_domain]
        lines.append(f"**{target_domain} 域已有端点 ({len(eps)} 个):**")
        for ep in eps:
            lines.append(f"  - {ep['method']} {ep['path']}")
    else:
        for domain, eps in code_ctx.get("endpoints", {}).items():
            lines.append(f"**{domain} 域 ({len(eps)} 个端点):**")
            for ep in eps[:5]:  # 每个域最多展示 5 个
                lines.append(f"  - {ep['method']} {ep['path']}")
            if len(eps) > 5:
                lines.append(f"  - ... 及其他 {len(eps)-5} 个端点")

    if code_ctx.get("models"):
        lines.append(f"\n**已有数据模型 ({len(code_ctx['models'])} 个):**")
        lines.append(f"  {', '.join(code_ctx['models'])}")

    if code_ctx.get("domains"):
        lines.append(f"\n**业务域:** {', '.join(code_ctx['domains'])}")

    return '\n'.join(lines)


def _map_item_text(item: dict) -> str:
    label = item.get("title") or item.get("name") or item.get("path") or ""
    return f"{item.get('id', '?')}" + (f" — {label}" if label else "")


def format_map_context(map_context: dict) -> str:
    lines = ["## 项目知识上下文（渐进增强）", f"- Context Level: {map_context['level']}"]
    providers = map_context.get("providers", [])
    lines.append("- Providers: " + (", ".join(f"{p['name']}={p['status']}" for p in providers) or "unavailable"))
    for title, key in (("需求上下文", "documents"), ("代码地图", "code")):
        items = map_context.get(key, [])
        if items:
            lines.append(f"\n### {title}")
            lines.extend(f"- [{item.get('classification', 'CANDIDATE')}] {_map_item_text(item)}" for item in items)
    links = map_context.get("trace_links", [])
    if links:
        lines.append("\n### Trace Links")
        for link in links:
            tests = ", ".join(link.get("tests", []))
            suffix = f" -> {tests}" if tests else ""
            lines.append(f"- [{link.get('classification', 'CANDIDATE')}] {link['requirement_id']} -> {link['symbol_id']}{suffix}")
    if map_context.get("unknown"):
        lines.append("\n### Unknown / 降级")
        lines.extend(f"- {item}" for item in map_context["unknown"])
    if map_context.get("recovery_actions"):
        lines.append("\n### 建议操作")
        for action in map_context["recovery_actions"]:
            lines.append(f"- {action['reason']}: `{action['command']}`（不自动执行）")
    if map_context["level"] == "L0":
        lines.append("- Fallback: 使用契约、约束和内建代码扫描")
    lines.append(f"- Authority: {map_context['authority']}")
    return "\n".join(lines)


def crop(project_dir: Path, task_id: str, target_domain: str = None, map_max_items: int = 10,
         include_map_context: bool = True, map_context: dict | None = None) -> str:
    """裁剪：组装 L2 + L3 + Ctx → 精简 prompt"""
    l2 = load_global_constraints(project_dir)
    l3 = load_yaml_contract(project_dir, task_id)
    ctx = load_code_context(project_dir)
    if map_context is None:
        map_context = build_context(project_dir, max_items=map_max_items, include_recommendations=False)

    parts = []

    # L2 全局约束（动态 — 简单项目可能只有 1-2 行）
    parts.append("## L2: 全局约束（全会话复用）")
    if l2.get("project_type") == "simple":
        parts.append(f"- ⚠️ 无架构文档 — 技术栈由 AS 按需决定")
    else:
        for key, label in [
            ("tech_stack", "技术栈"), ("api_spec", "API 规范"), ("auth", "认证"),
            ("orm", "ORM"), ("cache", "缓存"), ("test_framework", "测试框架"),
            ("coverage_threshold", "覆盖率阈值"), ("error_codes", "错误码"),
            ("money_rule", "金额规则"),
        ]:
            if l2.get(key):
                parts.append(f"- {label}: {l2[key]}")
    if l2.get("note"):
        parts.append(f"- 💡 {l2['note']}")
    parts.append("")

    # L2.5: AI 编码规范（从 AI_Coding_Guide.md 自动加载）
    coding_guide = load_coding_guide(project_dir)
    if coding_guide:
        parts.append("## L2+: AI 编码规范（本项目特定）")
        parts.append(coding_guide)
        parts.append("")

    # L2.8: Loop Memory（跨 cycle 累积记忆 — Lance Martin "Rules Load" 零件）
    loop_memory = load_loop_memory(project_dir, task_id)
    if loop_memory:
        parts.append("## L2.8: 跨 Cycle 记忆（Loop Memory）")
        parts.append(loop_memory)
        parts.append("")

    # L3 任务切片
    parts.append(f"## L3: 任务切片 — {task_id}")

    if l3:
        if l3.get("goal"):
            parts.append("\n### 目标")
            for g in l3["goal"]:
                parts.append(f"- {g}")

        if l3.get("not_goal"):
            parts.append("\n### 非目标（禁止触碰）")
            for ng in l3["not_goal"]:
                parts.append(f"- ❌ {ng}")

        if l3.get("rules"):
            parts.append("\n### 业务规则")
            for rid, rule in l3["rules"].items():
                parts.append(f"- [{rid}] {rule}")

        if l3.get("ac"):
            parts.append("\n### 验收标准")
            for aid, check in l3["ac"].items():
                parts.append(f"- [{aid}] `{check}`")
    else:
        parts.append(f"\n⚠️ 契约文件不存在: governance/contracts/Intent_Contract_{task_id}（.yaml/.yml/.md）")
        parts.append("请先创建契约后再裁剪。")

    # 代码上下文
    parts.append(f"\n## 代码上下文（自动发现）")
    parts.append(format_code_context(ctx, target_domain))

    if include_map_context:
        parts.append("\n" + format_map_context(map_context))

    # 关键约束提示（按项目类型动态调整）
    parts.append(f"\n## ⚠️ 关键约束")
    if l2.get("project_type") == "simple":
        parts.append("- 本项目为简单项目，无预定义架构约束")
        parts.append("- AS 自行决定代码组织方式和技术选型")
        parts.append("- 测试写入 tests/ 目录")
    else:
        parts.append("- 不要修改已有端点的路径和签名，只能新增")
        parts.append("- 新增代码写入 src/api/{domain}/ 和 src/models/{domain}.py")
        parts.append("- 测试写入 tests/test_{domain}.py")
        if (project_dir / "src" / "main.py").exists():
            parts.append("- 在 src/main.py 注册新 router")

    return '\n'.join(parts)


# ─── 隔离验证 ──────────────────────────────────────────────

def verify_isolation(prompt: str, task_id: str, project_dir: Path) -> dict:
    """验证裁剪后的上下文不包含禁止信息"""
    issues = []

    # 规则1: 不得包含其他任务的 not_goal 域
    other_domains = _find_other_domains(project_dir, task_id)
    for domain in other_domains:
        if re.search(rf'\b{domain}\b', prompt, re.IGNORECASE):
            issues.append({
                "rule": "domain_isolation",
                "severity": "MEDIUM",
                "detail": f"上下文包含其他域 '{domain}'，可能泄漏跨域信息",
            })

    # 规则2: 不得包含绝对路径
    abs_paths = re.findall(r'(?:/[a-zA-Z0-9_./-]+){2,}', prompt)
    project_root = str(project_dir)
    leaked = [p for p in abs_paths if project_root not in p and not p.startswith('/api/')]
    if leaked:
        issues.append({
            "rule": "path_isolation",
            "severity": "LOW",
            "detail": f"上下文包含外部绝对路径: {leaked[:3]}",
        })

    # 规则3: 不得包含敏感关键词
    sensitive_patterns = [
        (r'(?:password|passwd|secret|token|key)\s*[:=]\s*["\'][^"\']+["\']', "硬编码凭证"),
        (r'(?:AKIA|ASIA)[A-Z0-9]{16}', "AWS 密钥"),
        (r'-----BEGIN\s+(?:RSA|DSA|EC)\s+PRIVATE\s+KEY-----', "私钥"),
    ]
    for pattern, label in sensitive_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            issues.append({
                "rule": "sensitive_data",
                "severity": "CRITICAL",
                "detail": f"上下文包含敏感信息: {label}",
            })

    # 规则4: Token 预算检查（Karpathy 规则6 — 预算不是建议）
    estimated_tokens = len(prompt.split()) * 1.3  # 粗略估算

    # 分级预算阈值
    budgets = {
        "simple": 8000,     # 简单任务上限
        "standard": 20000,  # 标准编码/分析任务
        "complex": 40000,   # 复杂多文件任务
    }

    # 根据 prompt 大小自动判断任务复杂度
    if estimated_tokens <= budgets["simple"]:
        budget_level = "simple"
    elif estimated_tokens <= budgets["standard"]:
        budget_level = "standard"
    else:
        budget_level = "complex"

    over_budget = estimated_tokens > budgets[budget_level]

    if over_budget:
        issues.append({
            "rule": "token_budget",
            "severity": "CRITICAL",  # 升级为 CRITICAL — 超预算即失败
            "detail": (
                f"上下文约 {int(estimated_tokens)} tokens，"
                f"超过 {budget_level} 级预算 {budgets[budget_level]} tokens。"
                f"请拆分任务或使用 --domain 缩小裁剪范围。"
            ),
        })
    elif estimated_tokens > budgets["simple"]:
        issues.append({
            "rule": "token_budget",
            "severity": "MEDIUM" if estimated_tokens > budgets["standard"] else "LOW",
            "detail": f"上下文约 {int(estimated_tokens)} tokens（{budget_level} 级，上限 {budgets[budget_level]}）",
        })

    all_pass = not any(i["severity"] == "CRITICAL" for i in issues)
    return {
        "status": "PASS" if all_pass else "FAIL",
        "estimated_tokens": int(estimated_tokens),
        "budget_level": budget_level,
        "budget_limit": budgets[budget_level],
        "over_budget": over_budget,
        "issues": issues,
    }


def _find_other_domains(project_dir: Path, current_task: str) -> list[str]:
    """找出当前任务不应看到的其他域"""
    # 从图谱中提取所有域，排除当前任务所属域（YAML + MD 契约均可）
    from gov_common import find_contracts as _gc_find_contracts, parse_contract as _gc_parse
    all_contracts = _gc_find_contracts(project_dir)
    domains = set()
    current_domain = None

    for cf in all_contracts:
        try:
            parsed = _gc_parse(cf)
            domain = parsed.get("domain", "")
            # 多域契约（"MEMBER, BRAND"）拆分
            domain_list = [d.strip() for d in re.split(r'[,，、]', domain) if d.strip()]
            if cf.stem.endswith(f"_{current_task}"):
                current_domain = domain_list[0] if domain_list else None
            else:
                domains.update(domain_list)
        except Exception:
            pass

    # 返回非当前域的其他域
    if current_domain and current_domain in domains:
        domains.remove(current_domain)
    return list(domains)


# ─── Watch 模式 ────────────────────────────────────────────

def watch_mode(project_dir: Path, task_id: str, domain: str = None,
               interval: float = 5.0):
    """监听文件变更，自动重新裁剪"""
    # 需要监听的文件
    from gov_common import find_contract as _gc_find
    contract_file = _gc_find(project_dir, task_id)
    watch_paths = [
        project_dir / "governance" / "constraints.yaml",
        project_dir / "governance" / "Intent_Graph.md",
    ]
    if contract_file:
        watch_paths.insert(0, contract_file)
    # 过滤掉不存在的文件
    watch_paths = [p for p in watch_paths if p.exists()]

    if not watch_paths:
        print("⚠️ 无文件可监听", file=sys.stderr)
        return

    print(f"👁️ Watch 模式启动 — 每 {interval}s 检查变更")
    print(f"   监听文件: {', '.join(str(p.relative_to(project_dir)) for p in watch_paths)}")
    print(f"   按 Ctrl+C 退出")
    print()

    # 记录初始 mtime
    last_mtimes = {p: p.stat().st_mtime for p in watch_paths}

    # 首次裁剪
    prompt = crop(project_dir, task_id, domain)
    _print_watch_output(prompt, project_dir, task_id, "初始")

    try:
        while True:
            time.sleep(interval)
            changed = False
            for p in watch_paths:
                if p.exists():
                    current_mtime = p.stat().st_mtime
                    if current_mtime != last_mtimes.get(p, 0):
                        changed = True
                        last_mtimes[p] = current_mtime
                        print(f"\n📝 检测到变更: {p.relative_to(project_dir)}")

            if changed:
                prompt = crop(project_dir, task_id, domain)
                _print_watch_output(prompt, project_dir, task_id, "更新")
    except KeyboardInterrupt:
        print("\n👋 Watch 模式已退出")


def _print_watch_output(prompt: str, project_dir: Path, task_id: str, tag: str):
    """打印 watch 模式输出摘要"""
    token_est = len(prompt.split()) * 1.3
    print(f"[{tag}] 任务 {task_id} — 约 {int(token_est)} tokens")
    # 打印前 3 行作为摘要
    first_lines = prompt.split('\n')[:3]
    for line in first_lines:
        if line.strip():
            print(f"  {line.strip()[:80]}")
    print(f"  ...")


def main():
    parser = argparse.ArgumentParser(description="三层上下文裁剪引擎 v2.0")
    parser.add_argument("--task", required=True, help="任务 ID，如 T-003")
    parser.add_argument("--domain", default=None, help="目标业务域，如 membership")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output", default=None, help="输出文件路径")
    parser.add_argument("--verify-isolation", action="store_true",
                        help="验证裁剪后上下文不包含禁止信息")
    parser.add_argument("--watch", action="store_true",
                        help="监听文件变更，自动重新裁剪")
    parser.add_argument("--watch-interval", type=float, default=5.0,
                        help="Watch 模式检查间隔（秒）")
    parser.add_argument("--enforce-budget", action="store_true",
                        help="Token 预算硬拦��：超预算时拒绝裁剪（退出码 1），强制 OA 拆分任务")
    parser.add_argument("--map-max-items", type=int, default=10, help="每类地图上下文最多注入的条目数")
    parser.add_argument("--no-map-context", action="store_true", help="关闭地图上下文注入，不删除地图")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()

    # Watch 模式
    if args.watch:
        watch_mode(project_dir, args.task, args.domain, args.watch_interval)
        return

    map_context = build_context(project_dir, max_items=args.map_max_items, include_recommendations=False)
    try:
        prompt = crop(project_dir, args.task, args.domain, args.map_max_items,
                      not args.no_map_context, map_context=map_context)
    except ContractConflictError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)

    # Token 预算硬拦截（Karpathy 规则6 — 在裁剪阶段就拦截，不等到 AS 执行时才发现）
    if args.enforce_budget:
        iso_result = verify_isolation(prompt, args.task, project_dir)
        budget_issue = next((i for i in iso_result["issues"] if i["rule"] == "token_budget"), None)
        if budget_issue and budget_issue["severity"] == "CRITICAL":
            print(f"❌ Token 预算硬拦截: {budget_issue['detail']}", file=sys.stderr)
            print(f"   预算等级: {iso_result['budget_level']} (上限 {iso_result['budget_limit']} tokens)", file=sys.stderr)
            print(f"   实际估算: {iso_result['estimated_tokens']} tokens", file=sys.stderr)
            print(f"   建议: 使用 --domain 缩小范围，或拆分任务为多个子任务", file=sys.stderr)
            sys.exit(1)

    # 隔离验证
    if args.verify_isolation:
        iso_result = verify_isolation(prompt, args.task, project_dir)
        if args.format == "json":
            output = {"prompt": prompt, "isolation_check": iso_result}
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(prompt)
            print("\n" + "=" * 60)
            print("🔒 上下文隔离验证")
            print("=" * 60)
            for issue in iso_result["issues"]:
                sev = {"CRITICAL": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(issue["severity"], "?")
                print(f"  {sev} [{issue['rule']}] {issue['detail']}")
            status_icon = "✅" if iso_result["status"] == "PASS" else "❌"
            print(f"\n  {status_icon} 隔离验证: {iso_result['status']} "
                  f"(约 {iso_result['estimated_tokens']} tokens, "
                  f"{iso_result.get('budget_level', '?')} 级预算 {iso_result.get('budget_limit', '?')})")
        sys.exit(0 if iso_result["status"] == "PASS" else 1)

    # 常规输出
    if args.output:
        rendered = json.dumps({"prompt": prompt, "map_context": map_context}, ensure_ascii=False, indent=2) if args.format == "json" else prompt
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"裁剪后的 prompt 已写入: {args.output}", file=sys.stderr)
    if args.format == "json":
        print(json.dumps({"prompt": prompt, "map_context": map_context}, ensure_ascii=False, indent=2))
    else:
        print(prompt)


if __name__ == "__main__":
    main()
