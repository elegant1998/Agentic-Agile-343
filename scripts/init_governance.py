#!/usr/bin/env python3
"""风险驱动治理入口：识别项目、评估风险并初始化最小工件。"""

import argparse
import json
from pathlib import Path

from assess_risk import PROFILES, assess_risk
from recon import render_recon, scan_project
from project_snapshot import ProjectSnapshot


IGNORED = {".git", ".venv", "venv", "node_modules", "__pycache__", "governance", "tests"}
PROFILE_RANK = {"explore": 0, "delivery": 1, "legacy": 1, "multi-module": 1, "high-risk": 2}


def _project_files(project: Path) -> list[Path]:
    return [
        path
        for path in project.rglob("*")
        if path.is_file() and not any(part in IGNORED for part in path.relative_to(project).parts)
    ]


def classify_project(project_dir: Path | str, snapshot: ProjectSnapshot | None = None) -> str:
    """区分新项目、既有小项目、复杂遗留和多模块项目。"""
    project = Path(project_dir).resolve()
    files = list(snapshot.files) if snapshot is not None else _project_files(project)
    files = [path for path in files if not any(part in IGNORED for part in path.relative_to(project).parts)]
    if not files:
        return "new"
    module_roots = []
    for container in ("services", "modules", "packages", "apps"):
        root = project / container
        if root.is_dir():
            module_roots.extend(path for path in root.iterdir() if path.is_dir())
    if len(module_roots) >= 2:
        return "multi-module"
    if len(files) >= 50:
        return "legacy-complex"
    return "existing-small"


def _risk_domains(project_type: str, recon: dict | None, facts: dict) -> dict:
    tests_found = bool(recon and recon["inventory"]["test_files"])
    governance_found = bool(recon and recon["inventory"]["governance_files"])
    return {
        "intent": {
            "status": "controlled" if facts.get("goal_defined") else "unknown",
            "reason": "Goal and success criteria require IO confirmation" if not facts.get("goal_defined") else "Goal supplied",
        },
        "context": {
            "status": "medium" if project_type != "new" else "unknown",
            "reason": "Existing context requires source and freshness checks" if project_type != "new" else "No established context source",
        },
        "data_privacy": {
            "status": "high" if facts.get("sensitive_data") else "unknown",
            "reason": "Sensitive data declared" if facts.get("sensitive_data") else "Data classification not supplied",
        },
        "tools": {
            "status": "high" if facts.get("production_access") else "unknown",
            "reason": "Production access declared" if facts.get("production_access") else "Tool permissions not supplied",
        },
        "execution": {
            "status": "high" if facts.get("irreversible_action") else "medium",
            "reason": "Irreversible action declared" if facts.get("irreversible_action") else "Rollback and stop conditions require confirmation",
        },
        "verification": {
            "status": "controlled" if tests_found else "unknown",
            "reason": "Tests discovered" if tests_found else "No behavioral test evidence discovered",
        },
        "organization": {
            "status": "medium" if project_type == "multi-module" else "unknown",
            "reason": "Multiple modules require ownership" if project_type == "multi-module" else "Owners and approval roles not supplied",
        },
    }


def _intent_graph() -> str:
    return """# Intent Graph

**状态**: DRAFT

## 战略北极星

[由 IO 填写目标、价值和成功标准]

## 当前任务

| 任务 | 状态 |
|---|---|
| T-001 | PENDING |
"""


def _pending_contract() -> str:
    return """# Intent Contract: T-001

| 属性 | 值 |
|---|---|
| 状态 | PENDING |
| IO | _________ |

## 目标

[待 IO 确认]

## 非目标

[待 IO 确认]

## 验收标准

[待补充可执行 AC]

## 签署区

| 角色 | 签署人 | 日期 | 状态 |
|---|---|---|---|
| IO（意图主理人） | _________ | ________ | **PENDING** |
"""


def _constraints(profile: str) -> str:
    return f"""project: YOUR_PROJECT_NAME
version: "1.0"
profile: {profile}
status: DRAFT
constraints:
  - id: C-PROC-01
    domain: PROC
    level: MUST
    description: "契约签署前不得开始功能编码"
    check: "test -d governance/contracts"
    on_failure: block
    owner: IO
"""


def _ai_cost_model() -> str:
    return """schema: ai-cost-model/v1
currency: CNY
default_monthly_cost_per_person: 500
default_principal_id: null
people: {}
"""


def _profile_files(profile: str, recon: dict | None, risk: dict) -> dict[str, str]:
    common_contract = {"governance/contracts/Intent_Contract_T-001.md": _pending_contract()}
    if profile == "explore":
        return {
            "governance/Intent.md": "# Lightweight Intent\n\n**状态**: DRAFT\n\n[目标、非目标、成功标准]\n",
            "governance/constraints.yaml": _constraints(profile),
            "governance/measurement-contracts/AI_Cost_Model.yaml": _ai_cost_model(),
        }
    base = {
        "governance/Intent_Graph.md": _intent_graph(),
        "governance/constraints.yaml": _constraints(profile),
        "governance/measurement-contracts/AI_Cost_Model.yaml": _ai_cost_model(),
        **common_contract,
    }
    if profile == "high-risk":
        base.update(
            {
                "governance/Risk_Assessment.json": json.dumps(risk, ensure_ascii=False, indent=2) + "\n",
                "governance/HITL_Policy.md": "# HITL Policy\n\n不可逆操作、敏感数据和发布必须由责任人批准。\n",
            }
        )
    elif profile == "legacy":
        base.update(
            {
                "governance/recon/Recon_Baseline.md": render_recon(recon, "markdown") if recon else "# Recon Baseline\n",
                "governance/Change_Envelope.yaml": "version: \"1.0\"\nallowed: []\nprotected: []\nunknown: []\n",
            }
        )
    elif profile == "multi-module":
        base.update(
            {
                "governance/Protocol.yaml": "version: \"1.0\"\nmodules: []\nintegration: {edges: []}\n",
                "governance/Module_Governance.md": "# Module Governance\n\n[模块所有者、接口与证据责任]\n",
            }
        )
    return base


def build_init_plan(
    project_dir: Path | str,
    requested_profile: str | None = None,
    facts: dict | None = None,
    allow_upgrade: bool = False,
) -> dict:
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise ValueError(f"project directory does not exist: {project}")
    facts = dict(facts or {})
    snapshot = ProjectSnapshot.capture(project)
    project_type = classify_project(project, snapshot)
    # Governance planning must remain a zero-write dry run; map initialization
    # belongs to an explicit project Recon, not risk-plan discovery.
    recon = None if project_type == "new" else scan_project(project, auto_context=False, snapshot=snapshot)
    if project_type == "legacy-complex":
        facts.setdefault("legacy", True)
    if project_type == "multi-module":
        facts.setdefault("modules", 2)
    risk = assess_risk(facts)
    recommended = risk["recommended_profile"]
    profile = requested_profile or recommended
    if requested_profile and PROFILE_RANK[requested_profile] < PROFILE_RANK[recommended] and not allow_upgrade:
        raise ValueError(f"governance downgrade rejected: {recommended} -> {requested_profile}")
    domains = _risk_domains(project_type, recon, facts)
    unknown = [name for name, value in domains.items() if value["status"] == "unknown"]
    file_contents = _profile_files(profile, recon, {**risk, "domains": domains})
    return {
        "project": str(project),
        "project_type": project_type,
        "recon": recon,
        "risk_domains": domains,
        "unknown": unknown,
        "recommended_profile": recommended,
        "selected_profile": profile,
        "reasons": risk["reasons"],
        "minimum_artifacts": PROFILES[profile]["artifacts"],
        "required_gates": PROFILES[profile]["gates"],
        "hitl_requirements": PROFILES[profile]["hitl"],
        "planned_files": sorted(file_contents),
        "file_contents": file_contents,
    }


def apply_plan(plan: dict, project_dir: Path | str, apply: bool = False) -> dict:
    project = Path(project_dir).resolve()
    result = {"mode": "apply" if apply else "dry-run", "created": [], "skipped": [], "conflicts": []}
    if not apply:
        return result
    for relative, content in plan["file_contents"].items():
        target = project / relative
        if target.exists():
            if target.is_file() and target.read_text(encoding="utf-8") == content:
                result["skipped"].append(relative)
            else:
                result["conflicts"].append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        result["created"].append(relative)
    return result


def _public_plan(plan: dict) -> dict:
    return {key: value for key, value in plan.items() if key != "file_contents"}


def _markdown(plan: dict, result: dict) -> str:
    risks = "\n".join(f"- {name}: {value['status']} — {value['reason']}" for name, value in plan["risk_domains"].items())
    files = "\n".join(f"- {item}" for item in plan["planned_files"])
    return f"""# Governance Init Plan

- Project type: {plan['project_type']}
- Recommended profile: {plan['recommended_profile']}
- Selected profile: {plan['selected_profile']}
- Mode: {result['mode']}
- Unknown: {', '.join(plan['unknown']) or 'none'}

## Seven Risk Domains

{risks}

## Planned Files

{files}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="风险驱动治理初始化（默认 dry-run）")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--profile", choices=list(PROFILES))
    parser.add_argument("--facts", help="JSON 对象或 JSON 文件")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    facts = {}
    if args.facts:
        candidate = Path(args.facts)
        facts = json.loads(candidate.read_text(encoding="utf-8") if candidate.exists() else args.facts)
    plan = build_init_plan(args.project_dir, requested_profile=args.profile, facts=facts)
    result = apply_plan(plan, args.project_dir, apply=args.apply)
    payload = {"plan": _public_plan(plan), "result": result}
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else _markdown(plan, result))


if __name__ == "__main__":
    main()
