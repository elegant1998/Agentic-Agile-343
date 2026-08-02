#!/usr/bin/env python3
"""Triangulation Verifier — 图谱-契约-约束三方一致性验证器

验证三个核心治理工件之间的交叉一致性：

  1. 图谱 → 约束：图谱中每个 domain 在约束矩阵中是否有对应域的约束
  2. 契约 → 图谱：每个契约的目标是否可追溯到图谱中的任务节点
  3. 约束 → 契约：每条 MUST 约束是否在至少一个契约的 AC 中被引用
  4. 契约 → 约束：每个契约的 domain 是否匹配约束矩阵中对应域的 gate

自动发现工件文件，不依赖特定项目结构。

用法:
    python scripts/verify_triangulation.py [--project-dir .] [--format json]

退出码: 0 = 三方一致, 1 = 存在不一致
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

def find_graph(project_dir: Path) -> Path | None:
    candidates = [
        project_dir / "governance" / "Intent_Graph.md",
        project_dir / "docs" / "Intent_Graph.md",
        project_dir / "Intent_Graph.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_constraints(project_dir: Path) -> Path | None:
    candidates = [
        project_dir / "governance" / "constraints.yaml",
        project_dir / "constraints.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_contracts(project_dir: Path) -> list[Path]:
    """查找契约文件（支持 YAML 和 Markdown 两种格式）"""
    patterns = ["Intent_Contract_*.yaml", "Intent_Contract_*.md"]
    found: list[Path] = []
    contracts_dir = project_dir / "governance" / "contracts"
    if contracts_dir.exists():
        for p in patterns:
            found.extend(contracts_dir.glob(p))
    else:
        for p in patterns:
            found.extend(project_dir.glob(f"governance/contracts/{p}"))
    return sorted(set(found))


# ─── 解析 ──────────────────────────────────────────────────

def extract_domains_from_graph(graph_text: str) -> dict[str, list[str]]:
    """从图谱中提取 domain → 子域/能力 映射"""
    domains = defaultdict(list)

    # 策略1: 查找 "## N. Domain名称" 或 "### Domain名称"
    current_domain = None
    for line in graph_text.split('\n'):
        # 匹配 ## 3. 会员域 或 ### 会员域
        m = re.match(r'^#{2,4}\s*(?:\d+\.?\s*)?(.+?)$', line)
        if m:
            title = m.group(1).strip()
            # 检查是否包含域关键词
            domain_keywords = ['域', 'domain', '模块', '系统', '中心']
            if any(kw in title for kw in domain_keywords):
                # 清理
                clean = re.sub(r'^[\d\.\s]+', '', title)
                current_domain = clean
                continue

        # 收集域下的子项（列表项或子标题）
        if current_domain:
            sub = re.match(r'^[-*]\s+(.+)$', line)
            if sub:
                domains[current_domain].append(sub.group(1).strip())

    # 策略2: 从表格中提取（如 | 域 ID | 域名称 |）
    # 注意：必须正确识别表格边界，遇到非表格行立即重置，
    # 否则后续所有表格的第一列都会被误提取为"域"
    in_table = False
    header_checked = False
    table_is_domain_table = False
    for line in graph_text.split('\n'):
        is_table_row = line.strip().startswith('|')
        if not is_table_row:
            in_table = False
            header_checked = False
            table_is_domain_table = False
            continue
        if '---' in line:
            continue
        cols = [c.strip() for c in line.split('|') if c.strip()]
        if not header_checked:
            header_checked = True
            in_table = True
            # 仅当表头包含域相关关键词时才视为域定义表格
            table_is_domain_table = any(
                kw in c for c in cols for kw in ['域 ID', '域名称', '业务域', 'Domain']
            )
            continue
        if in_table and table_is_domain_table and cols:
            domain_name = cols[0]
            if _is_likely_domain(domain_name):
                if domain_name not in domains:
                    domains[domain_name] = []
                if len(cols) > 1:
                    domains[domain_name].append(cols[1])

    # 策略3: 如果以上都没找到，从任何标题中提取带"域"字的
    if not domains:
        for line in graph_text.split('\n'):
            m = re.match(r'^#{1,3}\s+(.+域.+)$', line)
            if m:
                domains[m.group(1).strip()] = []

    return dict(domains)


def extract_constraint_domains(constraints_data: dict) -> set[str]:
    """从约束矩阵提取所有域"""
    domains = set()
    for c in constraints_data.get("constraints", []):
        d = c.get("domain", "")
        if d:
            domains.add(d)
    return domains


def extract_must_constraints(constraints_data: dict) -> list[dict]:
    """提取所有 MUST 级约束"""
    return [c for c in constraints_data.get("constraints", [])
            if c.get("level") == "MUST"]


def extract_contract_goals(contract_path: Path) -> dict:
    """从契约提取 goal + domain（自动识别 YAML / Markdown 格式）"""
    if contract_path.suffix in (".yaml", ".yml"):
        with open(contract_path) as f:
            data = yaml.safe_load(f)

        return {
            "task": _extract_task_id(contract_path),
            "goal": data.get("goal", ""),
            "not_goal": data.get("not_goal", ""),
            "domain": data.get("domain", ""),
            "ac_count": len(data.get("ac", [])),
            "ac_texts": [ac.get("desc", "") for ac in data.get("ac", [])],
            "db_tables": data.get("db_tables", []),
        }

    # Markdown 契约：从文本结构中提取
    return _extract_from_markdown_contract(contract_path)


def _extract_from_markdown_contract(path: Path) -> dict:
    """从 Markdown 契约中提取 goal / domain / AC 描述列表

    支持的格式（Template_Intent_Contract.md 及其变体）：
    - goal:    `### 目标` 或 `## §1 目标` 或 `**目标**: xxx`
    - domain:  `**关联图谱**: ... §2.4 BRAND 域` 中的大写域 ID
    - ac:      `| AC-01 | 描述 |` 或 `| AC-01 | 描述 | 验证 |` 表格行
    """
    text = path.read_text()

    # ── goal ──
    goal = ""
    m = re.search(r'\*\*目标\*\*[：:]\s*(.+)', text)
    if m:
        goal = m.group(1).strip()
    else:
        # 匹配 "### 目标" / "## §1 目标" / "## 1. 目标" 等标题下的首段
        m = re.search(
            r'#{2,3}\s*(?:§\d+\s*)?(?:\d+\.?\s*)?(?:背景与)?目标[^\n]*\n+([^#\n].+)',
            text,
        )
        if m:
            goal = m.group(1).strip()

    # ── domain ──
    domain = ""
    m = re.search(r'\*\*关联域\*\*[：:]\s*(.+)', text)
    if m:
        domain = m.group(1).strip()
    else:
        # 从 "§2.4 BRAND 域" / "MEMBER, BRAND" 等引用中提取大写域 ID
        m = re.search(r'关联图谱[^\n]*?((?:[A-Z][A-Z_]{2,})(?:\s*[,，、]\s*[A-Z][A-Z_]{2,})*)\s*域', text)
        if m:
            domain = m.group(1).strip()

    # ── AC 描述 ──
    ac_texts: list[str] = []
    for line in text.split('\n'):
        s = line.strip()
        if not s.startswith('|') or '---' in s:
            continue
        cols = [c.strip() for c in s.split('|') if c.strip()]
        if len(cols) >= 2 and re.match(r'^AC-\d+', cols[0]):
            ac_texts.append(cols[1])

    return {
        "task": _extract_task_id(path),
        "goal": goal,
        "not_goal": "",
        "domain": domain,
        "ac_count": len(ac_texts),
        "ac_texts": ac_texts,
        "db_tables": [],
    }


def _extract_task_id(filepath: Path) -> str:
    m = re.search(r"Intent_Contract_(.+?)\.(?:yaml|yml|md)$", filepath.name)
    return m.group(1) if m else filepath.stem


def find_task_nodes_in_graph(graph_text: str) -> dict[str, str]:
    """从图谱中提取任务节点 (T-XXX → 描述)

    支持两种格式：
    - 表格行：  | T-001 | 任务描述 | 域 | 状态 |       （任务队列表）
    - 行内文本：T-001：任务描述  或  T-001 完成：描述   （历史上下文行）
    """
    tasks = {}
    for line in graph_text.split('\n'):
        # 表格格式：| T-001 | 描述 | ...
        m = re.match(r'^\s*\|\s*(T-\d{3})\s*\|\s*([^|]+?)\s*\|', line)
        if m:
            tasks[m.group(1)] = m.group(2).strip()
            continue
        # 行内格式：T-001：描述
        m = re.search(r'\b(T-\d{3})\b.*?[：:]\s*(.+?)(?:\||$)', line)
        if m:
            tasks[m.group(1)] = m.group(2).strip()
    return tasks


# ─── 一致性检查 ────────────────────────────────────────────

def check_graph_to_constraints(graph_domains: dict[str, list[str]],
                                constraint_domains: set[str],
                                domain_mapping: dict[str, list[str]] | None = None) -> list[dict]:
    """检查1: 图谱业务域与约束治理域的覆盖关系

    两种模式：
    A. 显式映射模式（推荐）：constraints.yaml 中声明了 domain_mapping 字段时，
       验证映射双方的完整性 —— 每个业务域至少映射一个治理域，
       每个治理域至少被一个业务域覆盖，且映射引用的域均已定义。
    B. 模糊匹配模式（向后兼容）：未声明映射时，按关键词重叠做 1:1 匹配，
       适用于图谱域与约束域本就是同一套分类的简单项目。
    """
    issues = []

    if domain_mapping is not None:
        covered_constraint_domains: set[str] = set()

        for biz_domain, gov_domains in domain_mapping.items():
            # "*" 通配符：表示全局治理域（不隶属于特定业务域，
            # 如 PROC 过程合规 / REL 可靠性 / OBS 可观测性）
            if biz_domain == "*":
                for gd in gov_domains:
                    if gd not in constraint_domains:
                        issues.append({
                            "check": "mapping->constraints",
                            "domain": gd,
                            "status": "ORPHAN",
                            "detail": f"全局映射引用的治理域「{gd}」在约束矩阵中未定义",
                        })
                    covered_constraint_domains.add(gd)
                continue
            if biz_domain not in graph_domains:
                issues.append({
                    "check": "mapping->graph",
                    "domain": biz_domain,
                    "status": "ORPHAN",
                    "detail": f"映射表业务域「{biz_domain}」在意图图谱中未定义",
                })
            for gd in gov_domains:
                if gd not in constraint_domains:
                    issues.append({
                        "check": "mapping->constraints",
                        "domain": gd,
                        "status": "ORPHAN",
                        "detail": f"映射表引用的治理域「{gd}」在约束矩阵中未定义",
                    })
                covered_constraint_domains.add(gd)

        # 图谱中定义的业务域是否都有映射
        for d in graph_domains:
            if d not in domain_mapping:
                issues.append({
                    "check": "graph->mapping",
                    "domain": d,
                    "status": "UNMAPPED",
                    "detail": f"图谱业务域「{d}」未在 domain_mapping 中声明治理域覆盖",
                })

        # 治理域是否都被业务域覆盖
        for cd in constraint_domains:
            if cd not in covered_constraint_domains:
                issues.append({
                    "check": "constraints->mapping",
                    "domain": cd,
                    "status": "UNCOVERED",
                    "detail": f"治理域「{cd}」未被任何业务域映射覆盖",
                })

        return issues

    # 模糊匹配模式（无显式映射时的向后兼容逻辑）
    for domain, capabilities in graph_domains.items():
        # 尝试模糊匹配
        matched = False
        for cd in constraint_domains:
            # 检查关键词重叠
            domain_words = set(re.findall(r'[\u4e00-\u9fff\w]+', domain.lower()))
            cd_words = set(re.findall(r'[\u4e00-\u9fff\w]+', cd.lower()))
            if domain_words & cd_words:
                matched = True
                break

        if not matched:
            # 进一步：尝试缩写匹配（会员 → MEMBER, 美食 → FOOD）
            if not _fuzzy_domain_match(domain, constraint_domains):
                issues.append({
                    "check": "graph→constraints",
                    "domain": domain,
                    "status": "ORPHAN",
                    "detail": f"图谱域「{domain}」在约束矩阵中无对应约束域",
                })

    # 反向：约束域是否都在图谱中有对应
    for cd in constraint_domains:
        matched = False
        for domain in graph_domains:
            domain_words = set(re.findall(r'[\u4e00-\u9fff\w]+', domain.lower()))
            cd_words = set(re.findall(r'[\u4e00-\u9fff\w]+', cd.lower()))
            if domain_words & cd_words:
                matched = True
                break
        if not matched and not _fuzzy_domain_match(cd, set(graph_domains.keys())):
            issues.append({
                "check": "constraints→graph",
                "domain": cd,
                "status": "ORPHAN",
                "detail": f"约束域「{cd}」在图谱中无对应域",
            })

    return issues


def check_contracts_to_graph(contracts: list[dict],
                              graph_tasks: dict[str, str]) -> list[dict]:
    """检查2: 每个契约的任务 ID 是否可在图谱中追溯"""
    issues = []
    for ct in contracts:
        task_id = ct["task"]
        if task_id not in graph_tasks:
            issues.append({
                "check": "contract→graph",
                "task": task_id,
                "status": "ORPHAN",
                "detail": f"契约任务 {task_id} 在图谱中无对应节点",
            })
    return issues


def check_must_to_contracts(must_constraints: list[dict],
                             all_contracts: list[dict]) -> list[dict]:
    """检查3: 每条 MUST 约束是否被验证覆盖

    覆盖来源有两种，任一即可：
    - harness 自动检查：约束带可执行 check（非 manual）→ 由门禁覆盖，
      不属于任何业务契约的 AC 职责（如"治理目录存在"、"Grill-Me 协议"）
    - 契约 AC 引用：业务型 MUST 约束（如密码哈希、JWT 过期）应被
      至少一个契约的验收标准覆盖
    因此仅对 manual 约束或关键词完全无匹配的约束报告 UNTRACED。
    """
    issues = []
    # 汇总所有契约的 AC 文本
    all_ac_text = ' '.join(
        ac for ct in all_contracts for ac in ct["ac_texts"]
    )

    for mc in must_constraints:
        cid = mc["id"]
        desc = mc.get("description", "")
        keywords = _extract_keywords(desc)

        # 已有可执行自动检查的约束由 harness 门禁覆盖，豁免契约 AC 检查
        check_cmd = mc.get("check", "")
        if check_cmd and not mc.get("manual", False):
            continue

        # 检查是否有契约 AC 引用了类似描述
        found = False
        for kw in keywords:
            if kw in all_ac_text:
                found = True
                break

        # 也检查契约 goal 字段
        if not found:
            for ct in all_contracts:
                if any(kw in ct["goal"] for kw in keywords):
                    found = True
                    break

        if not found:
            if mc.get("manual", False):
                # manual 约束由 HITL 人工审查覆盖，AC 未匹配不阻断，
                # 降级为提示，由 OA 确认已在审查中包含
                issues.append({
                    "check": "must→contracts",
                    "constraint_id": cid,
                    "status": "MANUAL_REVIEW",
                    "detail": f"人工审查约束 [{cid}]「{desc[:50]}」未匹配到契约 AC，请确认已在 HITL 审查中覆盖",
                })
            else:
                issues.append({
                    "check": "must→contracts",
                    "constraint_id": cid,
                    "status": "UNTRACED",
                    "detail": f"MUST 约束 [{cid}]「{desc[:50]}」未被任何契约 AC 覆盖",
                })

    return issues


def check_contract_domain_gates(contracts: list[dict],
                                 constraints_data: dict) -> list[dict]:
    """检查4: 契约 domain 是否匹配约束矩阵中对应域的 gate

    契约的 domain 通常是业务域（BRAND/MEMBER），而约束矩阵使用
    治理域（STRUCT/DATA）。当 constraints.yaml 声明了 domain_mapping 时，
    先把业务域翻译成治理域再检查；否则按关键词模糊匹配。
    """
    issues = []

    # 构建 domain → gate 映射
    domain_gates = defaultdict(set)
    for c in constraints_data.get("constraints", []):
        d = c.get("domain", "")
        g = c.get("gate", "")
        if d and g:
            domain_gates[d].add(g)

    domain_mapping = constraints_data.get("domain_mapping") or {}

    for ct in contracts:
        ct_domain = ct.get("domain", "")
        if not ct_domain:
            continue
        # 契约可能声明多个业务域（如 "MEMBER, BRAND"）
        ct_domains = [d.strip() for d in re.split(r'[,，、]', ct_domain) if d.strip()]

        matched = False
        for ctd in ct_domains:
            # 优先：通过 domain_mapping 把业务域翻译成治理域
            mapped = domain_mapping.get(ctd, [])
            if any(gd in domain_gates for gd in mapped):
                matched = True
                break
            # 向后兼容：模糊匹配
            for cd, gates in domain_gates.items():
                if _fuzzy_domain_match_single(ctd, cd):
                    matched = True
                    break
            if matched:
                break

        if not matched and domain_gates:
            issues.append({
                "check": "contract-domain→gates",
                "task": ct["task"],
                "status": "MISMATCH",
                "detail": f"契约 {ct['task']} 的 domain「{ct_domain}」与约束矩阵中任何域都不匹配",
            })

    return issues


# ─── 辅助 ──────────────────────────────────────────────────

# 明显不是"业务域"的表格单元格模式
_NON_DOMAIN_PATTERNS = [
    r'^[A-Z]{1,3}-\d+$',      # H-01, T-001, HX-05, EX-001, AC-01
    r'^\d+$',                 # 纯数字
    r'^\d+\.\d+$',            # 版本号
]

_NON_DOMAIN_WORDS = {
    'id', '步骤', '角色', '画像维度', '任务 id', '任务id', '目标用户',
    '核心场景', '痛点', '扩展场景', '签署人', '日期', '状态', '操作',
    '实体', '属性', '关系', '画像', '事件', '教训', '影响', '说明',
}


def _is_likely_domain(value: str) -> bool:
    """判断表格单元格值是否可能是业务域 ID

    合法域的形式：
    - 全大写英文 ID（BRAND / MEMBER / COURSE / SHOP）
    - 含"域/中心/模块"的中文名（会员域 / 课程中心）
    排除：ID 列、编号、数字、表头词等。
    """
    v = value.strip()
    if not v or len(v) > 30:
        return False
    for pat in _NON_DOMAIN_PATTERNS:
        if re.match(pat, v):
            return False
    if v.lower() in _NON_DOMAIN_WORDS:
        return False
    # 全大写英文 ID（BRAND, MEMBER, COURSE, SHOP, ASSESS...）
    if re.match(r'^[A-Z][A-Z_]{1,20}$', v):
        return True
    # 中文含"域/中心/模块"
    if re.search(r'[一-鿿]', v) and any(k in v for k in ('域', '中心', '模块')):
        return True
    return False


def _fuzzy_domain_match(domain: str, candidates: set[str]) -> bool:
    """模糊匹配域名称"""
    for c in candidates:
        if _fuzzy_domain_match_single(domain, c):
            return True
    return False


def _fuzzy_domain_match_single(a: str, b: str) -> bool:
    """两个域名称是否模糊匹配"""
    # 通用域映射（中英文 + 缩写）
    # 注意：此处只放"治理域 ↔ 通用别名"的映射，
    # 业务域（项目自定义的 BRAND/COURSE/SHOP 等）请通过
    # constraints.yaml 的 domain_mapping 字段显式声明，不要硬编码到这里。
    domain_aliases = {
        'STRUCT': ['结构', 'structure', '项目结构', '代码结构'],
        'DATA': ['数据', 'data', '数据库', 'database'],
        'BEHAVE': ['行为', 'behave', 'behavior', '业务逻辑', '接口'],
        'QUAL': ['质量', 'quality', '测试', '覆盖', '性能'],
        'PROC': ['流程', 'process', '治理', '签署', '审批'],
        'STYLE': ['规范', 'style', '编码规范', '红线'],
        'SEC': ['安全', 'security', '权限', '认证'],
        'REL': ['可靠', 'reliability', '容错', '熔断'],
        'OBS': ['可观测', 'observability', '日志', '监控'],
        'MEMBER': ['会员', 'membership', '用户'],
        'BRAND': ['品牌', 'brand', '首页', '宣言'],
        'COURSE': ['课程', 'course', '学习'],
        'SHOP': ['商城', 'shop', '商品', '书籍'],
        'ASSESS': ['评估', 'assessment', '成熟度'],
        'RESOURCE': ['资源', 'resource', '下载'],
    }

    a_lower = a.lower().replace('_', '').replace('-', '')
    b_lower = b.lower().replace('_', '').replace('-', '')

    if a_lower == b_lower:
        return True

    # 检查别名表
    for key, aliases in domain_aliases.items():
        a_match = a_lower == key.lower() or any(al in a for al in aliases)
        b_match = b_lower == key.lower() or any(al in b for al in aliases)
        if a_match and b_match:
            return True

    # 中文字符交集
    a_chars = set(re.findall(r'[\u4e00-\u9fff]+', a))
    b_chars = set(re.findall(r'[\u4e00-\u9fff]+', b))
    if a_chars and b_chars and (a_chars & b_chars):
        return True

    return False


def _extract_keywords(text: str) -> list[str]:
    """从约束描述中提取关键词

    中文部分用 3-4 字滑动窗口（而非非重叠 findall），避免
    "响应式布局" 被切成 "响应式布"+"局在" 导致语义碎片化；
    英文部分提取 ≥3 字符的词。
    """
    kws: list[str] = []
    for seg in re.findall(r'[\u4e00-\u9fff]+', text):
        if len(seg) <= 4:
            kws.append(seg)
        else:
            for w in (4, 3):
                kws.extend(seg[i:i + w] for i in range(len(seg) - w + 1))
    kws.extend(re.findall(r'[a-zA-Z_]{3,}', text))
    seen: set[str] = set()
    return [k for k in kws if not (k in seen or seen.add(k))]


# ─── 主流程 ────────────────────────────────────────────────

def triangulate(project_dir: Path) -> dict:
    """执行三方一致性验证"""
    result = {
        "project": project_dir.name,
        "status": "PASS",
        "checks": [],
        "issues": [],
    }

    # 加载工件
    graph_file = find_graph(project_dir)
    constraints_file = find_constraints(project_dir)
    contract_files = find_contracts(project_dir)

    if not graph_file:
        result["issues"].append({"severity": "WARN", "detail": "未找到意图图谱"})
    if not constraints_file:
        result["issues"].append({"severity": "ERROR", "detail": "未找到约束矩阵"})
        result["status"] = "FAIL"
        return result
    if not contract_files:
        result["issues"].append({"severity": "WARN", "detail": "未找到意图契约"})

    # 解析
    graph_text = graph_file.read_text() if graph_file else ""
    graph_domains = extract_domains_from_graph(graph_text)
    graph_tasks = find_task_nodes_in_graph(graph_text)

    with open(constraints_file) as f:
        constraints_data = yaml.safe_load(f)
    constraint_domains = extract_constraint_domains(constraints_data)
    must_constraints = extract_must_constraints(constraints_data)

    # 可选：显式业务域 → 治理域映射（处理两种域分类体系不同的情况）
    domain_mapping = constraints_data.get("domain_mapping")

    contracts = [extract_contract_goals(cf) for cf in contract_files]

    # 执行四项检查
    all_issues = []

    # 1. 图谱 ↔ 约束
    issues1 = check_graph_to_constraints(graph_domains, constraint_domains, domain_mapping)
    all_issues.extend(issues1)
    result["checks"].append({
        "id": "graph↔constraints",
        "name": "图谱域 ↔ 约束域 覆盖",
        "total": len(graph_domains) + len(constraint_domains),
        "issues": len(issues1),
        "status": "PASS" if not issues1 else "FAIL",
    })

    # 2. 契约 → 图谱
    if contract_files:
        issues2 = check_contracts_to_graph(contracts, graph_tasks)
        all_issues.extend(issues2)
        result["checks"].append({
            "id": "contract→graph",
            "name": "契约任务 → 图谱节点 追溯",
            "total": len(contracts),
            "issues": len(issues2),
            "status": "PASS" if not issues2 else "FAIL",
        })

    # 3. MUST 约束 → 契约 AC
    if contract_files:
        issues3 = check_must_to_contracts(must_constraints, contracts)
        all_issues.extend(issues3)
        untraced3 = [i for i in issues3 if i["status"] == "UNTRACED"]
        result["checks"].append({
            "id": "must→contracts",
            "name": "MUST 约束 → 契约 AC 覆盖",
            "total": len(must_constraints),
            "issues": len(untraced3),
            "status": "PASS" if not untraced3 else "FAIL",
        })

    # 4. 契约 domain → 约束 gate
    if contract_files:
        issues4 = check_contract_domain_gates(contracts, constraints_data)
        all_issues.extend(issues4)
        result["checks"].append({
            "id": "contract-domain→gates",
            "name": "契约 domain → 约束 gate 匹配",
            "total": len(contracts),
            "issues": len(issues4),
            "status": "PASS" if not issues4 else "FAIL",
        })

    result["issues"] = all_issues
    if any(c["status"] == "FAIL" for c in result["checks"]):
        result["status"] = "FAIL"

    return result


# ─── 输出 ──────────────────────────────────────────────────

def print_text(result: dict):
    print("╔══════════════════════════════════════════════╗")
    print("║  Triangulation Verifier — 三方一致性验证     ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"项目: {result['project']}")
    print()

    print("━━━ 一致性检查矩阵 ━━━")
    for c in result.get("checks", []):
        icon = "✅" if c["status"] == "PASS" else "❌"
        print(f"  {icon} {c['name']}: {c['total'] - c['issues']}/{c['total']} 一致")

    print()

    if result["issues"]:
        # 按检查分组
        by_check = defaultdict(list)
        for issue in result["issues"]:
            key = issue.get("check", issue.get("severity", "other"))
            by_check[key].append(issue)

        print(f"❌ 发现 {len(result['issues'])} 个不一致项:")
        for check_name, items in by_check.items():
            print(f"\n  [{check_name}]")
            for item in items:
                icon = "🔴" if item.get("status") in ("ORPHAN", "UNTRACED") else "🟡"
                print(f"    {icon} {item['detail']}")
        print()

    if result["status"] == "PASS":
        print("✅ 三方一致性验证通过 — 图谱/契约/约束矩阵保持一致")
    else:
        print("❌ 三方存在不一致 — 请修复上述问题后重新验证")


def main():
    parser = argparse.ArgumentParser(
        description="Triangulation Verifier — 三方一致性验证器"
    )
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = triangulate(project_dir)

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
