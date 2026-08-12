#!/usr/bin/env python3
"""gov_common — 3-4-3 治理工件共享解析库

为 scripts/ 下所有验证脚本提供统一的工件发现与解析能力，
消除各脚本重复实现导致的格式支持不一致问题。

核心能力：
  1. 契约发现与解析（YAML / Markdown 双格式）
  2. 证据包发现（单文件 / 按任务拆分 EB-T-XXX 双模式）
  3. 意图图谱 / 约束矩阵定位
  4. 任务完成状态判定（用于 freshness 等场景豁免已完成任务）

用法（在 scripts/ 同目录脚本中）：
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent))
  from gov_common import find_contracts, parse_contract, find_evidence_bundles
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import yaml
except ImportError:  # 允许仅使用 MD 解析能力的环境
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml


# ─── 契约发现 ──────────────────────────────────────────────

class ContractConflictError(ValueError):
    """同一任务存在多个契约格式，无法确定唯一事实源。"""


def _reject_contract_conflicts(paths: list[Path]) -> None:
    by_task: dict[str, list[Path]] = {}
    for path in paths:
        by_task.setdefault(extract_task_id(path), []).append(path)
    conflicts = {task: files for task, files in by_task.items() if len(files) > 1}
    if conflicts:
        detail = "; ".join(
            f"{task}: {', '.join(path.name for path in files)}"
            for task, files in sorted(conflicts.items())
        )
        raise ContractConflictError(f"CONTRACT_FORMAT_CONFLICT: {detail}")

def find_contracts(project_dir: Path) -> list[Path]:
    """发现所有契约文件（YAML + Markdown 双格式，去重排序）"""
    patterns = ["Intent_Contract_*.yaml", "Intent_Contract_*.yml", "Intent_Contract_*.md"]
    found: list[Path] = []
    contracts_dir = project_dir / "governance" / "contracts"
    search_root = contracts_dir if contracts_dir.exists() else project_dir / "governance" / "contracts"
    for p in patterns:
        found.extend(search_root.glob(p))
    result = sorted(set(found))
    _reject_contract_conflicts(result)
    return result


def find_contract(project_dir: Path, task_id: str) -> Path | None:
    """按任务 ID 定位唯一契约；多格式并存时 fail closed。"""
    contracts_dir = project_dir / "governance" / "contracts"
    found = [
        contracts_dir / f"Intent_Contract_{task_id}{ext}"
        for ext in (".yaml", ".yml", ".md")
        if (contracts_dir / f"Intent_Contract_{task_id}{ext}").exists()
    ]
    _reject_contract_conflicts(found)
    return found[0] if found else None


def extract_task_id(filepath: Path) -> str:
    """从契约/证据包文件名提取任务 ID（T-001 / T-001a 等）"""
    m = re.search(r"(?:Intent_Contract|EB)_(.+?)\.(?:yaml|yml|md)$", filepath.name)
    return m.group(1) if m else filepath.stem


# ─── 契约解析 ──────────────────────────────────────────────

def parse_contract(contract_path: Path) -> dict:
    """统一解析契约为标准结构（自动识别格式）

    返回:
        task:      任务 ID
        goal:      目标（多行合并为单文本）
        not_goal:  非目标
        domain:    关联业务域（可能为逗号分隔多域）
        ac:        AC 列表 [{id, desc, verify}]
        ac_texts:  AC 描述文本列表（便捷字段）
        format:    "yaml" | "md"
        raw:       原始数据（YAML dict 或 MD 全文）

    MD 契约的 AC 验证方式列支持 verify 前缀语法：
        | AC-01 | 描述 | shell: npm run build |
        | AC-02 | 描述 | http: GET /api/x expect 200 |
        | AC-03 | 描述 | assert: python 表达式 |
        | AC-04 | 描述 | manual / 人工验证 |（无前缀 → verify=None）
    """
    if contract_path.suffix in (".yaml", ".yml"):
        return _parse_yaml_contract(contract_path)
    return _parse_md_contract(contract_path)


def _parse_yaml_contract(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("解析 YAML 契约需要 pyyaml: pip install pyyaml")
    data = yaml.safe_load(path.read_text()) or {}
    ac_list = data.get("ac", []) or []
    return {
        "task": extract_task_id(path),
        "goal": data.get("goal", "") or "",
        "not_goal": data.get("not_goal", "") or "",
        "domain": data.get("domain", "") or "",
        "ac": ac_list,
        "ac_texts": [a.get("desc", "") for a in ac_list if isinstance(a, dict)],
        "format": "yaml",
        "raw": data,
    }


def _split_table_row(line: str) -> list[str]:
    """拆分 Markdown 表格行，忽略反引号代码段内的 | 字符

    契约 AC 表格的验证命令常含管道符（如 `cmd 2>&1 | head -5`），
    朴素 split('|') 会把它切成多列。本函数按反引号配对跳过代码段。
    """
    cols: list[str] = []
    buf: list[str] = []
    in_code = False
    for ch in line.strip().strip("|"):
        if ch == "`":
            in_code = not in_code
            buf.append(ch)
        elif ch == "|" and not in_code:
            cols.append("".join(buf).strip().strip("`").strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        cols.append("".join(buf).strip().strip("`").strip())
    return [c for c in cols if c]


def _extract_section(text: str, heading_keywords: tuple[str, ...]) -> str:
    """提取 MD 契约中某个章节标题下的全部文本（直到下一个同级或更高级标题）"""
    lines = text.split("\n")
    capturing = False
    captured: list[str] = []
    capture_level = 99
    for line in lines:
        m = re.match(r"^(#{1,4})\s*(.+)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2)
            if capturing and level <= capture_level:
                break
            if any(kw in title for kw in heading_keywords):
                capturing = True
                capture_level = level
                continue
        if capturing:
            captured.append(line)
    return "\n".join(captured).strip()


def _parse_md_contract(path: Path) -> dict:
    text = path.read_text()

    metadata: dict[str, str] = {}
    for line in text.splitlines():
        cols = _split_table_row(line) if line.strip().startswith("|") else []
        if len(cols) >= 2 and cols[0] in {"创建日期", "签署日期", "日期", "Date", "Signed Date"}:
            metadata[cols[0]] = cols[1]

    # goal：优先 "**目标**: xxx"，其次 "### 目标" / "## §1 目标" 章节首段
    goal = ""
    m = re.search(r"\*\*目标\*\*[：:]\s*(.+)", text)
    if m:
        goal = m.group(1).strip()
    else:
        # 优先找"纯目标"章节（含"目标"、不含"非目标"和"背景"）——避免把背景叙述混入
        for m2 in re.finditer(r"^#{1,4}\s*(.+)$", text, re.MULTILINE):
            title = m2.group(1)
            if "目标" in title and "非目标" not in title and "背景" not in title:
                goal = _extract_section(text, (title,))
                break
        # 回退：只有"背景与目标"联合章节时，整段提取（调用方可接受背景前缀）
        if not goal:
            goal = _extract_section(text, ("背景与目标",))

    # not_goal："非目标" 章节整段
    not_goal = _extract_section(text, ("非目标",))

    # domain："**关联域**: xxx" 或 "**关联图谱**: ... BRAND 域 + MEMBER 域"
    domain = ""
    m = re.search(r"\*\*关联域\*\*[：:]\s*(.+)", text)
    if m:
        domain = m.group(1).strip()
    else:
        m = re.search(r"关联图谱[^\n]*", text)
        if m:
            ids = re.findall(r"\b([A-Z][A-Z_]{2,})\b(?=\s*域)", m.group(0))
            domain = ", ".join(ids)

    # AC 表格：| AC-01 | 描述 | 验证方式 |（反引号内 | 不算分隔符）
    ac_list: list[dict] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("|") or "---" in s:
            continue
        cols = _split_table_row(s)
        if len(cols) >= 2 and re.match(r"^AC-\d+", cols[0]):
            entry = {"id": cols[0], "desc": cols[1], "verify": None}
            if len(cols) >= 3:
                entry["verify"] = _parse_verify_column(cols[2])
            ac_list.append(entry)

    return {
        "task": extract_task_id(path),
        "goal": goal,
        "not_goal": not_goal,
        "domain": domain,
        "ac": ac_list,
        "ac_texts": [a["desc"] for a in ac_list],
        "format": "md",
        "raw": text,
        "metadata": metadata,
    }


def _parse_verify_column(cell: str) -> dict | None:
    """解析 MD 契约 AC 表格的验证方式列

    支持前缀：
      shell: <命令>                    → {type: shell, command}
      http: <METHOD> <url> [expect N]  → {type: http, method, url, expect}
      predicate: <安全谓词>           → {type: predicate, expression}
      db: <sql> [expect rows>=N]       → {type: db, sql, expect}
      manual / 其他                    → None（人工验证）
    """
    s = cell.strip().strip("`").strip()
    m = re.match(r"^shell:\s*(.+)$", s, re.IGNORECASE)
    if m:
        return {"type": "shell", "command": m.group(1).strip().strip("`").strip()}
    m = re.match(r"^http:\s*(\w+)?\s*(\S+)(?:\s+expect\s+(?:status\s+)?(\d+))?", s, re.IGNORECASE)
    if m:
        expect = {"status": int(m.group(3))} if m.group(3) else {"status": 200}
        return {"type": "http", "method": (m.group(1) or "GET").upper(),
                "url": m.group(2).strip("`"), "expect": expect}
    m = re.match(r"^predicate:\s*(.+)$", s, re.IGNORECASE)
    if m:
        return {"type": "predicate", "expression": m.group(1).strip()}
    m = re.match(r"^assert:\s*(.+)$", s, re.IGNORECASE)
    if m:
        return {"type": "assert", "expr": m.group(1).strip(), "legacy_unsafe": True}
    m = re.match(r"^db:\s*(.+)$", s, re.IGNORECASE)
    if m:
        return {"type": "db", "sql": m.group(1).strip()}
    return None


# ─── 证据包发现 ────────────────────────────────────────────

def find_evidence_bundles(project_dir: Path) -> list[Path]:
    """发现所有证据包（两种模式兼容）

    模式 A（按任务拆分，推荐）: governance/evidence/EB-T-001.md ...
    模式 B（单文件）:           governance/Evidence_Bundle.md
    """
    found: list[Path] = []
    # 模式 A：按任务拆分
    ev_dir = project_dir / "governance" / "evidence"
    if ev_dir.exists():
        found.extend(sorted(ev_dir.glob("EB-*.md")))
        found.extend(sorted(ev_dir.glob("Evidence_Bundle_*.md")))
    # 模式 B：单文件
    for c in (
        project_dir / "governance" / "Evidence_Bundle.md",
        project_dir / "docs" / "Evidence_Bundle.md",
        project_dir / "Evidence_Bundle.md",
    ):
        if c.exists():
            found.append(c)
    # 兼容 governance/ 下的 Evidence_Bundle_T-XXX.md
    gov = project_dir / "governance"
    if gov.exists():
        found.extend(sorted(gov.glob("Evidence_Bundle_*.md")))
    return sorted(set(found))


def find_evidence_bundle(project_dir: Path, task_id: str) -> Path | None:
    """按任务 ID 定位证据包"""
    ev_dir = project_dir / "governance" / "evidence"
    for name in (f"EB-{task_id}.md", f"Evidence_Bundle_{task_id}.md"):
        c = ev_dir / name
        if c.exists():
            return c
    return None


def is_task_completed(project_dir: Path, task_id: str) -> bool:
    """判定任务是否已完成（用于豁免时效检查等场景）

    SIGNED 只表示 IO 已授权执行，不能作为完成态；契约也不会从
    SIGNED 迁移为 COMPLETED。完成必须由 Evidence 的技术裁决或明确
    最终裁决派生，避免 Evidence 中引用 Contract (SIGNED) 被误判。
    """
    eb = find_evidence_bundle(project_dir, task_id)
    if eb is None:
        return False
    try:
        text = eb.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    verdict_rows = (
        r"^\s*\|?\s*(?:技术裁决|Technical\s+Verdict|technical_verdict)\s*\|\s*(?:PASS|APPROVED)\b",
        r"^\s*\|?\s*(?:最终裁决|Final\s+Verdict|final_verdict)\s*\|\s*(?:PASS|APPROVED)\b",
        r"^\s*\|?\s*(?:状态|Status|status)\s*\|\s*(?:APPROVED|COMPLETED)\b",
    )
    return any(re.search(pattern, text, re.IGNORECASE | re.MULTILINE) for pattern in verdict_rows)


# ─── 图谱 / 约束定位 ───────────────────────────────────────

def find_graph(project_dir: Path) -> Path | None:
    for c in (
        project_dir / "governance" / "Intent_Graph.md",
        project_dir / "docs" / "Intent_Graph.md",
        project_dir / "Intent_Graph.md",
    ):
        if c.exists():
            return c
    return None


def find_constraints(project_dir: Path) -> Path | None:
    for c in (
        project_dir / "governance" / "constraints.yaml",
        project_dir / "constraints.yaml",
    ):
        if c.exists():
            return c
    return None
