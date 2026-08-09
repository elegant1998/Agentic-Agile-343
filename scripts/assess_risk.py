#!/usr/bin/env python3
"""风险驱动治理模式评估器。"""

import argparse
import json
from pathlib import Path

PROFILES = {
    "explore": {"artifacts": ["lightweight intent", "core constraints"], "gates": ["pre", "prove"], "hitl": ["external release"]},
    "delivery": {"artifacts": ["Intent Contract", "constraints", "Evidence Bundle"], "gates": ["pre", "coding", "prove", "closing"], "hitl": ["value decisions", "release decision"]},
    "high-risk": {"artifacts": ["Intent Graph", "signed contract", "threat model", "Evidence Bundle"], "gates": ["pre", "coding", "prove", "closing", "bug"], "hitl": ["irreversible actions", "sensitive data", "release decision"]},
    "legacy": {"artifacts": ["Recon", "Baseline/Preserve/Unknown", "Change Envelope", "contract"], "gates": ["pre", "coding", "prove", "closing"], "hitl": ["unknown behavior", "change envelope expansion"]},
    "multi-module": {"artifacts": ["Protocol", "cross-module contracts", "integration graph", "aggregate evidence"], "gates": ["pre", "coding", "prove", "closing"], "hitl": ["ownership conflicts", "integration release"]},
}


def assess_risk(facts: dict) -> dict:
    reasons = []
    unknown = not facts or not facts.get("scenario")
    if facts.get("safety_critical") or facts.get("regulated"):
        level, profile = "safety-critical", "high-risk"
        reasons.append("Safety-critical or regulated responsibility requires formal expert governance")
    elif facts.get("irreversible_action") or facts.get("sensitive_data"):
        level, profile = "high", "high-risk"
        reasons.append("Irreversible action or sensitive data prevents lightweight autonomy")
    elif unknown or facts.get("reversible") is None and not facts.get("rollback"):
        level, profile = "medium", "delivery"
        reasons.append("Insufficient evidence is retained as Unknown; risk is not downgraded")
    elif facts.get("scenario") == "explore" and facts.get("reversible") and facts.get("internal_only"):
        level, profile = "low", "explore"
        reasons.append("Internal, reversible exploration has limited blast radius")
    else:
        level, profile = "medium", "delivery"
        reasons.append("User-facing or delivery work requires complete evidence and release judgment")
    if facts.get("legacy") and level not in {"high", "safety-critical"}:
        profile = "legacy"
        reasons.append("Existing behavior requires Recon and a protected change envelope")
    if (facts.get("modules", 1) >= 2 or facts.get("contributors", 1) >= 2) and level not in {"high", "safety-critical"}:
        profile = "multi-module"
        reasons.append("Multiple modules or contributors require ownership and integration governance")
    config = PROFILES[profile]
    return {
        "risk_level": level,
        "recommended_profile": profile,
        "reasons": reasons,
        "unknown": [key for key in ("scenario", "reversible") if key not in facts or facts.get(key) is None],
        "minimum_artifacts": config["artifacts"],
        "required_gates": config["gates"],
        "hitl_requirements": config["hitl"],
        "rule": "Governance may escalate automatically; high-risk governance requires IO approval to downgrade",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="风险驱动治理模式评估")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--facts", help="JSON 对象或 JSON 文件")
    parser.add_argument("--scenario", choices=["explore", "delivery"])
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--sensitive-data", action="store_true")
    parser.add_argument("--irreversible-action", action="store_true")
    parser.add_argument("--modules", type=int, default=1)
    args = parser.parse_args()
    facts = {}
    if args.facts:
        candidate = Path(args.facts)
        facts = json.loads(candidate.read_text(encoding="utf-8") if candidate.exists() else args.facts)
    supplied = {"scenario": args.scenario, "legacy": args.legacy, "sensitive_data": args.sensitive_data, "irreversible_action": args.irreversible_action, "modules": args.modules}
    facts.update({key: value for key, value in supplied.items() if value not in (None, False, 1)})
    facts.setdefault("legacy", (Path(args.project_dir).resolve() / ".git").exists())
    print(json.dumps(assess_risk(facts), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
