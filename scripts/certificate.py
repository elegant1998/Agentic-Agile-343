"""Certificate 证书资格判定模块 — 从 collect_telemetry.py 拆分。

负责：根据遥测门槛判定是否可申请 AASC 项目自治成熟度证书（L3/L4）。
"""


def calc_certificate_eligibility(value_layer: dict, capability_layer: dict) -> dict:
    """根据遥测门槛判定是否可申请 AASC 项目自治成熟度证书（仅 L3/L4）。

    与门户 /api/project-autonomy-certificates/eligibility 对齐：
      L4: autonomy≥80, tasks≥15, first_pass≥0.9, must≥0.99, auto_heal≥0.8
      L3: autonomy≥60, tasks≥10, first_pass≥0.7, must≥0.95
    """
    ga = value_layer.get("goal_accuracy") or {}
    fp = value_layer.get("first_pass_rate") or {}
    ah = capability_layer.get("auto_heal_rate") or {}
    mp = capability_layer.get("must_pass_rate") or {}
    au = capability_layer.get("autonomy_score") or {}

    critical = {"goal_accuracy": ga, "first_pass_rate": fp, "auto_heal_rate": ah}
    unavailable = [name for name, metric in critical.items()
                   if metric.get("status") in ("UNKNOWN", "NOT_APPLICABLE")
                   or metric.get("value") is None]
    if unavailable:
        return {
            "eligible": False, "suggested_level": None,
            "label": "INSUFFICIENT_DATA", "cta_enabled": False,
            "cta_text": "关键指标数据不足，暂不可申请证书",
            "apply_url": "http://agentic.iloveagile.me/project-autonomy-certificate/apply",
            "what_is_it": "证书资格必须由有来源、可复验的关键遥测指标支持。",
            "reasons": ["关键指标缺少可信数据: " + ", ".join(unavailable)],
            "metrics": {name: metric.get("value") for name, metric in critical.items()},
        }

    autonomy = float(au.get("value") or 0)
    tasks = int(ga.get("tasks_completed") or 0)
    first_pass = float(fp.get("value") or 0)
    must_pass = float(mp.get("value") or 0)
    auto_heal = float(ah.get("value") or 0)

    apply_url = "http://agentic.iloveagile.me/project-autonomy-certificate/apply"
    what_is_it = (
        "项目自治成熟度证书（AASC Project Autonomy Certificate）是组织在智能体敏捷（Agentic Agile）成熟度模型上达到 L3 受控自治 或 L4 自治超进化 后，可申请的项目级认证。证书针对「项目」而非个人；需在<a href='http://agentic.iloveagile.me/'>Agentic Agile 智能体敏捷体系认证中心网站</a>申请并签发，可下载 PDF。L1/L2 不能申请证书——仅用本仪表盘作成长反馈。"
    )
    metrics = {
        "autonomy_score": autonomy,
        "tasks_completed": tasks,
        "first_pass_rate": first_pass,
        "must_pass_rate": must_pass,
        "auto_heal_rate": auto_heal,
    }

    if (
        autonomy >= 80
        and tasks >= 15
        and first_pass >= 0.9
        and must_pass >= 0.99
        and auto_heal >= 0.8
    ):
        return {
            "eligible": True,
            "suggested_level": "L4",
            "label": "可申请 L4 自治超进化证书",
            "cta_enabled": True,
            "cta_text": "申请 L4 项目自治证书 →",
            "apply_url": apply_url,
            "what_is_it": what_is_it,
            "reasons": [
                "遥测达标：autonomy≥80, tasks≥15, first_pass≥90%, must≥99%, auto_heal≥80%"
            ],
            "metrics": metrics,
        }

    if autonomy >= 60 and tasks >= 10 and first_pass >= 0.7 and must_pass >= 0.95:
        gaps = []
        if autonomy < 80:
            gaps.append(f"autonomy={autonomy:.1f}(需≥80)")
        if tasks < 15:
            gaps.append(f"tasks={tasks}(需≥15)")
        if first_pass < 0.9:
            gaps.append(f"first_pass={first_pass*100:.0f}%(需≥90%)")
        if must_pass < 0.99:
            gaps.append(f"must_pass={must_pass*100:.0f}%(需≥99%)")
        if auto_heal < 0.8:
            gaps.append(f"auto_heal={auto_heal*100:.0f}%(需≥80%)")
        return {
            "eligible": True,
            "suggested_level": "L3",
            "label": "可申请 L3 受控自治证书",
            "cta_enabled": True,
            "cta_text": "申请 L3 项目自治证书 →",
            "apply_url": apply_url,
            "what_is_it": what_is_it,
            "reasons": ["遥测达标（L3）"] + (
                [f"距离 L4 差距: {', '.join(gaps)}"] if gaps else []
            ),
            "metrics": metrics,
        }

    gaps = []
    if autonomy < 60:
        gaps.append(f"autonomy={autonomy:.1f}(需≥60)")
    if tasks < 10:
        gaps.append(f"tasks={tasks}(需≥10)")
    if first_pass < 0.7:
        gaps.append(f"first_pass={first_pass*100:.0f}%(需≥70%)")
    if must_pass < 0.95:
        gaps.append(f"must_pass={must_pass*100:.0f}%(需≥95%)")
    return {
        "eligible": False,
        "suggested_level": None,
        "label": "未达 L3/L4 发证门槛",
        "cta_enabled": False,
        "cta_text": "达到 L3 后可申请证书",
        "apply_url": apply_url,
        "what_is_it": what_is_it,
        "reasons": ["未达到 L3 门槛"] + gaps,
        "metrics": metrics,
    }
