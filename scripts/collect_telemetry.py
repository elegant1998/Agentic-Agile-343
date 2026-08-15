#!/usr/bin/env python3
"""Agentic Agile 343 — 算力与价值遥测收集器 v2.0

4 层 9 维遥测模型：
  Layer 1 — 价值层：目标准确率、首次成功率、复合 ROI
  Layer 2 — 能力层：约束自愈率、HITL 升级率
  Layer 3 — 效率层：上下文压缩比、Token 效率
  Layer 4 — 进化层：知识沉淀率

用法:
    python scripts/collect_telemetry.py \
        --project "my-project" \
        --test-total 42 --test-passed 42 \
        --coverage-pct 93.0 --coverage-threshold 90.0 \
        --bench-p95 0.0067 --bench-threshold 2.0 \
        --token-usage 45000 --execution-rounds 6 --hitl-count 2 \
        --gates-passed 5 --must-constraints 20 --must-failed 0 \
        --tasks-assigned 10 --tasks-completed 9 --tasks-first-pass 7 \
        --auto-healed 3 --constraint-failures-total 5 \
        --human-hourly-rate 500 --hours-saved-per-task 2.0 \
        --ai-monthly-cost 50000 \
        --context-input-tokens 8000 --context-output-tokens 1500 \
        --new-patterns 3 --total-patterns 12 \
        --output telemetry.json

退出码: 0 = 成功, 1 = 采集失败
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
# ── 从 dashboard.py / certificate.py 导入（v1.15 拆分）──
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from dashboard import find_dashboard_template as _find_dashboard_template
    from dashboard import write_static_dashboard
    from dashboard import summarize_for_index as _summarize_for_index
    from certificate import calc_certificate_eligibility as _calc_certificate_eligibility
    from telemetry_tracker import derive_measurements as _derive_measurements
except ImportError:
    pass  # 模块不可用时降级为内联定义（见下方）



# ─── 分层遥测模型 ──────────────────────────────────────────

def _is_measured_task_usage(measurement: dict | None) -> bool:
    measurement = measurement or {}
    return (
        measurement.get("status") == "MEASURED"
        and measurement.get("scope") in {"task_snapshot", "task_delta"}
    )

def _get_project_uid(project_root: str = ".") -> str:
    """生成或读取项目唯一标识（project_uid）。
    优先从 git remote URL 派生（SHA256 前 16 位，同仓库永远一致，跨公司不撞）；
    无 git 则生成 UUID 持久化到 .project_uid 文件。
    """
    import hashlib, uuid as _uuid
    # 1. 尝试 git remote
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, cwd=project_root,
        )
        if r.returncode == 0 and r.stdout.strip():
            return hashlib.sha256(r.stdout.strip().encode()).hexdigest()[:16]
    except Exception:
        pass
    # 2. 读取已持久化的 UID
    uid_file = os.path.join(project_root, ".project_uid")
    if os.path.isfile(uid_file):
        try:
            uid = open(uid_file, "r").read().strip()
            if uid:
                return uid
        except Exception:
            pass
    # 3. 生成新 UUID 并持久化
    uid = _uuid.uuid4().hex[:16]
    try:
        with open(uid_file, "w") as f:
            f.write(uid)
    except Exception:
        pass
    return uid


def collect(args):
    """采集全部 4 层遥测指标"""
    now = datetime.now(timezone.utc).isoformat()
    task_id = _normalize_task_id(getattr(args, "task", None) or getattr(args, "module_id", None))
    # contract = 单次意图契约；project = 项目累积（默认：有 --task 则为 contract）
    scope = getattr(args, "scope", None) or ("contract" if task_id else "project")
    token_measurement = getattr(args, "token_measurement", None) or {
        "value": getattr(args, "token_usage", 0),
        "status": "MEASURED" if str(getattr(args, "token_source", "")).startswith("measured") else "UNKNOWN",
        "source": getattr(args, "token_source", "estimated"),
        "evidence": [], "measured_at": now, "scope": "legacy_input", "detail": "",
    }
    task_tokens_measured = _is_measured_task_usage(token_measurement)
    args.token_usage = int(token_measurement.get("value") or 0) if task_tokens_measured else 0
    args.token_source = str(token_measurement.get("source") or "unavailable")
    args._token_measurement = token_measurement

    # P0 Measurement Contract: task collection derives facts from project artifacts/events.
    # Explicit numeric compatibility inputs are accepted only as DECLARED data.
    if task_id:
        out = Path(getattr(args, "output", "governance/telemetry.json")).resolve()
        project_root = out.parent.parent if out.parent.name == "governance" else Path.cwd().resolve()
        measurements = _derive_measurements(project_root, task_id)
        manual = ("tasks_assigned", "tasks_completed", "tasks_first_pass",
                  "auto_healed", "constraint_failures_total")
        supplied = [name for name in manual if getattr(args, name, None) is not None]
        if supplied:
            if getattr(args, "p0_source", None) != "declared":
                raise ValueError("手工 P0 数字必须同时使用 --p0-source declared")
            now_declared = datetime.now(timezone.utc).isoformat()
            for name in supplied:
                measurements[name] = {"value": getattr(args, name), "status": "DECLARED",
                                      "source": "cli_declared", "evidence": [],
                                      "measured_at": now_declared}
        args._p0_measurements = measurements
        for name, metric in measurements.items():
            setattr(args, name, metric.get("value"))

    # 约束矩阵 → 门禁/测试：消费 harness 执行结果（不再手工判定，从源头解决）
    _wire_matrix(args, task_id)

    # ── Layer 1: 价值层 ──
    value_layer = _collect_value_layer(args)

    # ── Layer 2: 能力层 ──
    capability_layer = _collect_capability_layer(args)

    # ── Layer 3: 效率层 ──
    # T-153: 先跑 cost（含 ESTIMATED 降级），回写 token_usage 到 args 供效率层读取
    cost = _collect_cost(args)
    if cost.get("token_usage") is not None and args.token_usage == 0:
        args.token_usage = cost["token_usage"]
    efficiency_layer = _collect_efficiency_layer(args)

    # ── Layer 4: 进化层 ──
    evolution_layer = _collect_evolution_layer(args)

    # ── 兼容旧版字段 ──
    pipeline = _collect_pipeline(args)
    quality = _collect_quality(args)
    # T-153: 性能基准已砍掉；cost 已在 efficiency_layer 之前采集并回写 args.token_usage
    governance = _collect_governance(args)

    # ── 项目自治成熟度证书资格（仅 L3/L4 可申请）──
    certificate_eligibility = _calc_certificate_eligibility(
        value_layer, capability_layer
    )

    return {
        "meta": {
            "collected_at": now,
            "project": args.project or "UNKNOWN",
            "project_uid": _get_project_uid(),
            "version": "2.2",
            "model": "4-layer-9-dim",
            "scope": scope,  # contract | project
            "task_id": task_id,  # e.g. T-018；project 级为 null
            "module_id": getattr(args, "module_id", None),
            "tool": getattr(args, "tool", "other"),
            "host_tool": token_measurement.get("host_tool") or getattr(args, "tool", "other"),
            "token_client": token_measurement.get("token_client"),
            # 双向链接字段（落盘时再补全路径）
            "links": {
                "project_telemetry": "telemetry.json",
                "contract_telemetry": None,
                "dashboard_project": "dashboard.html",
                "dashboard_contract": None,
            },
        },
        # 新分层
        "value": value_layer,
        "capability": capability_layer,
        "efficiency": efficiency_layer,
        "evolution": evolution_layer,
        # 项目自治成熟度证书资格
        "certificate_eligibility": certificate_eligibility,
        # 兼容旧版
        "pipeline": pipeline,
        "quality": quality,
        "cost": cost,
        "governance": governance,
        # 项目累积时保留 runs 索引（单次为空）
        "runs": [],
    }



# _calc_certificate_eligibility → moved to certificate.py



def _normalize_task_id(raw):
    if not raw:
        return None
    s = str(raw).strip().upper()
    if not s:
        return None
    if s.startswith("T-"):
        return s
    if s.startswith("T") and s[1:].isdigit():
        return f"T-{s[1:]}"
    if s.isdigit():
        return f"T-{s}"
    return s


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# _find_dashboard_template → moved to dashboard.py



# write_static_dashboard → moved to dashboard.py



# _summarize_for_index → moved to dashboard.py



def _read_run_file(project_dir: Path, file_rel: str | None) -> dict | None:
    """按 runs 摘要中的相对路径读取单次契约 run 文件。"""
    if not file_rel:
        return None
    p = project_dir / file_rel
    return _load_json(p)


def _raw_summary_from_telemetry(telemetry: dict) -> dict:
    """Extract the small, stable facts needed for project aggregation."""
    value = telemetry.get("value") or {}
    capability = telemetry.get("capability") or {}
    evolution = telemetry.get("evolution") or {}
    goal = value.get("goal_accuracy") or {}
    first_pass = value.get("first_pass_rate") or {}
    auto_heal = capability.get("auto_heal_rate") or {}
    must_pass = capability.get("must_pass_rate") or {}
    hitl = capability.get("hitl_escalation_rate") or {}
    knowledge = evolution.get("knowledge_crystallization") or {}
    measurements = {
        "tasks_assigned": {"value": goal.get("tasks_assigned"), "status": goal.get("status")},
        "tasks_completed": {"value": goal.get("tasks_completed"), "status": goal.get("status")},
        "tasks_first_pass": {"value": first_pass.get("tasks_first_pass"), "status": first_pass.get("status")},
        "auto_healed": {"value": auto_heal.get("auto_healed"), "status": auto_heal.get("status")},
        "constraint_failures_total": {
            "value": auto_heal.get("failures_total"), "status": auto_heal.get("status")
        },
    }
    return {
        "measurements": measurements,
        "must_passed": int(must_pass.get("must_passed", 0) or 0),
        "must_total": int(must_pass.get("must_total", 0) or 0),
        "hitl_count": int(hitl.get("hitl_count", 0) or 0),
        "execution_rounds": int(hitl.get("execution_rounds", 0) or 0),
        "token_measurement": (telemetry.get("cost") or {}).get("token_measurement") or {
            "value": int((telemetry.get("cost") or {}).get("token_usage", 0) or 0),
            "status": "MEASURED" if str((telemetry.get("cost") or {}).get("token_source", "")).startswith("measured") else "UNKNOWN",
            "source": str((telemetry.get("cost") or {}).get("token_source", "estimated")),
            "scope": "legacy_input",
        },
        "context_measurement": ((telemetry.get("efficiency") or {}).get("context_compression") or {}).get("measurement"),
        "new_patterns": int(knowledge.get("new_patterns_this_cycle", 0) or 0),
        "total_patterns": int(knowledge.get("total_patterns_accumulated", 0) or 0),
    }


def _estimate_monthly_tasks(run_summaries: list) -> int:
    """从历史 runs 推导月任务数。取最早和最晚 collected_at 计算跨度天数。
    加上限保护：密集开发期（如 5 天 40 个任务）线性外推会失真，上限 50 任务/月。
    """
    from datetime import datetime as _dt
    dates = []
    for r in run_summaries:
        ca = r.get("collected_at")
        if ca:
            try:
                dates.append(_dt.fromisoformat(ca.replace("Z", "+00:00")))
            except Exception:
                pass
    if len(dates) < 2:
        return max(len(run_summaries), 1)
    span_days = max((max(dates) - min(dates)).days, 1)
    raw_monthly = len(run_summaries) / span_days * 30
    # 上限保护：密集开发期外推失真，上限 50/月；下限 5/月
    return max(5, min(50, round(raw_monthly)))


def _accumulate_runs_raw(project_dir: Path, run_summaries: list, latest_contract: dict) -> dict:
    """跨所有契约 run 文件累加原始计数，用于项目级累计遥测。

    关键修正：旧版把最近一次契约的快照当作项目级分层字段，导致
    tasks=1 / first_pass=0% 这类「单契约快照」被误读为「项目累计」。
    这里改为读取每个 run 文件的原始计数并累加，得到真正的项目累计。
    """
    raw = {
        "tasks_assigned": 0,
        "tasks_completed": 0,
        "tasks_first_pass": 0,
        "auto_healed": 0,
        "constraint_failures_total": 0,
        "must_passed": 0,
        "must_total": 0,
        "hitl_count": 0,
        "execution_rounds": 0,
        "token_usage": 0,
        "new_patterns": 0,
    }
    token_sources = set()
    coverage = {name: {"measured": 0, "eligible": 0} for name in (
        "tasks_assigned", "tasks_completed", "tasks_first_pass",
        "constraint_failures_total", "auto_healed")}
    total_patterns = 0
    for run in run_summaries:
        summary = run.get("raw_summary")
        if not isinstance(summary, dict):
            telemetry = _read_run_file(project_dir, run.get("file"))
            if not telemetry:
                continue
            summary = _raw_summary_from_telemetry(telemetry)
            run["raw_summary"] = summary
        for name, metric in (summary.get("measurements") or {}).items():
            if name not in coverage:
                continue
            coverage[name]["eligible"] += 1
            status = metric.get("status")
            # v1.33 and earlier run files had no Measurement Contract status.
            # Treat absent status as trusted legacy data during --rebuild, while
            # keeping explicit UNKNOWN / NOT_APPLICABLE out of aggregation.
            if (status is None or status in ("MEASURED", "DERIVED", "DECLARED")) and metric.get("value") is not None:
                raw[name] += int(metric["value"])
                coverage[name]["measured"] += 1
        raw["must_passed"] += int(summary.get("must_passed", 0) or 0)
        raw["must_total"] += int(summary.get("must_total", 0) or 0)
        raw["hitl_count"] += int(summary.get("hitl_count", 0) or 0)
        raw["execution_rounds"] += int(summary.get("execution_rounds", 0) or 0)
        token = summary.get("token_measurement") or {
            "value": summary.get("token_usage", 0), "status": "UNKNOWN",
            "source": summary.get("token_source", "estimated"), "scope": "legacy_input",
        }
        if _is_measured_task_usage(token):
            raw["token_usage"] += int(token.get("value", 0) or 0)
            token_sources.add(str(token.get("source", "measured")))
        elif token.get("status") == "CUMULATIVE_SNAPSHOT":
            # 项目日累计快照不能归属到具体任务，不进入任务聚合。
            token_sources.add("cumulative_snapshot_only")
        elif token.get("value"):
            # fallback：旧 run 有 token_usage 但无 token_measurement（status=UNKNOWN）
            raw["token_usage"] += int(token.get("value", 0) or 0)
            token_sources.add(str(token.get("source", "legacy")))
        raw["new_patterns"] += int(summary.get("new_patterns", 0) or 0)
        # total_patterns 为项目累积快照（最新契约已含历史），取最大值
        tp = int(summary.get("total_patterns", 0) or 0)
        if tp > total_patterns:
            total_patterns = tp
    # 以最新契约快照中的 total_patterns 为准（已是累积值）
    latest_tp = int(
        (latest_contract.get("evolution", {}).get("knowledge_crystallization", {}) or {}).get(
            "total_patterns_accumulated", 0
        )
        or 0
    )
    if latest_tp > total_patterns:
        total_patterns = latest_tp
    raw["total_patterns"] = total_patterns
    raw["measurement_coverage"] = coverage
    measured = {s for s in token_sources if s.startswith("measured")}
    if measured and len(measured) == len(token_sources):
        raw["token_source"] = "measured:ocusage"
    elif measured:
        raw["token_source"] = "mixed(measured+estimated)"
    elif token_sources == {"cumulative_snapshot_only"}:
        raw["token_source"] = "cumulative_snapshot_only"
    else:
        raw["token_source"] = "unknown"
    return raw


class _RawArgs:
    """用跨契约累计原始计数构造伪 args，复用现有分层采集函数。"""

    def __init__(self, raw: dict):
        self.tasks_assigned = raw["tasks_assigned"]
        self.tasks_completed = raw["tasks_completed"]
        self.tasks_first_pass = raw["tasks_first_pass"]
        self.auto_healed = raw["auto_healed"]
        self.constraint_failures_total = raw["constraint_failures_total"]
        self.must_constraints = raw["must_total"]
        self.must_failed = max(0, raw["must_total"] - raw["must_passed"])
        self.hitl_count = raw["hitl_count"]
        self.execution_rounds = raw["execution_rounds"]
        self.token_usage = raw["token_usage"]
        self.new_patterns = raw["new_patterns"]
        self.total_patterns = raw["total_patterns"]
        # Cost inputs are resolved from the independent measurement contract.
        self._project_dir = raw.get("_project_dir", Path("."))
        # T-153: 上下文 tokens 从 token_usage 粗估（与 _derive_auto_params 同逻辑）
        self.context_input_tokens = raw.get("context_input_tokens", 0)
        self.context_output_tokens = raw.get("context_output_tokens", 0)
        self._context_measurement = raw.get("context_measurement")
        # T-153: 月任务数（供 ROI 计算）
        self.estimated_monthly_tasks = raw.get("estimated_monthly_tasks")
        now = datetime.now(timezone.utc).isoformat()
        coverage = raw.get("measurement_coverage", {})
        self._p0_measurements = {}
        for name in ("tasks_assigned", "tasks_completed", "tasks_first_pass",
                     "constraint_failures_total", "auto_healed"):
            c = coverage.get(name, {})
            measured = c.get("measured", 0)
            status = "DERIVED" if measured else "UNKNOWN"
            if name in ("constraint_failures_total", "auto_healed") and not measured and c.get("eligible", 0):
                status = "NOT_APPLICABLE"
            self._p0_measurements[name] = {
                "value": raw[name] if measured else None, "status": status,
                "source": "project_run_aggregation" if measured else "insufficient_run_sources",
                "evidence": [], "measured_at": now if measured else None,
            }
            if not measured:
                setattr(self, name, None)


def _aggregate_project_from_runs(
    project: str, run_summaries: list, latest_contract: dict | None, project_dir: Path
) -> dict:
    """从历史 runs 累加原始计数，拼出项目级累计遥测。

    value / capability / efficiency / evolution 分层字段为**所有契约 run 的
    跨契约累计聚合**（修正旧版「取最近一次快照」导致 tasks=1 的偏差）；
    runs 为完整历史索引。
    """
    now = datetime.now(timezone.utc).isoformat()
    latest = latest_contract or {
        "meta": {},
        "value": {},
        "capability": {},
        "efficiency": {},
        "evolution": {},
        "pipeline": {},
        "quality": {},
        "cost": {},
        "governance": {},
    }
    raw = _accumulate_runs_raw(project_dir, run_summaries, latest)
    raw["context_measurement"] = (
        ((latest.get("efficiency") or {}).get("context_compression") or {}).get("measurement")
    )
    # Token usage and Context Pack are independent measurements.
    raw["_project_dir"] = str(project_dir)
    # T-153: 从历史 runs 推导月任务数（供 ROI 计算）
    raw["estimated_monthly_tasks"] = _estimate_monthly_tasks(run_summaries)
    try:
        from token_usage import collect_token_measurement
        tm = collect_token_measurement(project_dir)
        tm_val = int(tm.get("value") or 0)
        if tm_val > 0 and raw["token_usage"] == 0:
            raw["token_usage"] = tm_val
            raw["token_source"] = tm.get("source", "estimated")
    except Exception:
        pass
    fake = _RawArgs(raw)
    value_layer = _collect_value_layer(fake)
    capability_layer = _collect_capability_layer(fake)
    efficiency_layer = _collect_efficiency_layer(fake)
    evolution_layer = _collect_evolution_layer(fake)
    certificate_eligibility = _calc_certificate_eligibility(value_layer, capability_layer)

    n = len(run_summaries)
    agg = {
        "meta": {
            "collected_at": now,
            "project": project or (latest.get("meta") or {}).get("project") or "UNKNOWN",
            "project_uid": (latest.get("meta") or {}).get("project_uid") or _get_project_uid(),
            "version": "2.2",
            "model": "4-layer-9-dim",
            "scope": "project",
            "task_id": None,
            "run_count": n,
            "links": {
                "project_telemetry": "telemetry.json",
                "contract_telemetry": None,
                "dashboard_project": "dashboard.html",
                "dashboard_contract": None,
            },
        },
        "value": value_layer,
        "capability": capability_layer,
        "efficiency": efficiency_layer,
        "evolution": evolution_layer,
        "certificate_eligibility": certificate_eligibility,
        "pipeline": latest.get("pipeline") or {},
        "quality": latest.get("quality") or {},
        "cost": {
            "token_usage": raw["token_usage"] if raw["token_usage"] > 0 else None,
            "token_source": raw.get("token_source", "estimated"),
            "token_status": "ESTIMATED" if raw["token_usage"] > 0 else "UNKNOWN",
            "execution_rounds": raw["execution_rounds"],
            "hitl_count": raw["hitl_count"],
            "hitl_rate": _safe_ratio(raw["hitl_count"], max(raw["execution_rounds"], 1)),
            "estimated_cost_usd": round(raw["token_usage"] * 0.000002, 4) if raw["token_usage"] > 0 else None,
        },
        "governance": latest.get("governance") or {},
        "runs": run_summaries,
        "aggregate": {
            "contracts_recorded": n,
            "task_ids": [r.get("task_id") for r in run_summaries if r.get("task_id")],
            "contracts_completed": sum(1 for r in run_summaries if r.get("task_id")),
            "note": "value/capability/efficiency/evolution 分层字段为所有契约 run 的跨契约累计聚合；runs 为完整历史索引",
            "raw_accumulated": raw,
            "measurement_coverage": raw.get("measurement_coverage", {}),
        },
    }
    return agg


def persist_telemetry(args, telemetry: dict) -> dict:
    """
    双轨落盘：
    - 单次意图契约: governance/telemetry/runs/telemetry-T-XXX.json
    - 项目累积:     governance/telemetry.json（含 runs[] 链接）
    默认 --output 仍写项目累积；有 --task 时额外写单次并回写双方 links。
    """
    out = Path(args.output)
    # 约定：项目累积默认路径
    if out.name == "telemetry.json" or not getattr(args, "task", None):
        project_path = out if out.suffix == ".json" else out / "telemetry.json"
    else:
        project_path = out.parent / "telemetry.json" if out.parent.name != "runs" else out.parent.parent / "telemetry.json"

    # 若用户把 output 指到 runs 下，纠正 project 路径
    if project_path.parent.name == "runs":
        project_path = project_path.parent.parent / "telemetry.json"

    task_id = telemetry["meta"].get("task_id")
    scope = telemetry["meta"].get("scope") or "project"

    contract_path = None
    if task_id and scope == "contract":
        runs_dir = project_path.parent / "telemetry" / "runs"
        contract_path = runs_dir / f"telemetry-{task_id}.json"
        rel_contract = f"telemetry/runs/telemetry-{task_id}.json"
        rel_project = "telemetry.json"
        rel_dash_contract = f"dashboards/dashboard-{task_id}.html"
        telemetry["meta"]["links"] = {
            "project_telemetry": rel_project,
            "contract_telemetry": rel_contract,
            "dashboard_project": "dashboard.html",
            "dashboard_contract": rel_dash_contract,
        }
        telemetry["meta"]["scope"] = "contract"
        telemetry["runs"] = []
        _write_json(contract_path, telemetry)

        # 更新项目累积：合并历史 runs
        existing = _load_json(project_path) or {}
        old_runs = list(existing.get("runs") or [])
        # 去重同 task_id，新的覆盖旧的
        old_runs = [r for r in old_runs if r.get("task_id") != task_id]
        summary = _summarize_for_index(telemetry)
        summary["raw_summary"] = _raw_summary_from_telemetry(telemetry)
        old_runs.append(summary)
        # 按时间排序
        old_runs.sort(key=lambda r: r.get("collected_at") or "")

        project_tel = _aggregate_project_from_runs(
            telemetry["meta"].get("project"),
            old_runs,
            telemetry,
            project_path.parent,
        )
        project_tel["meta"]["links"]["project_telemetry"] = rel_project
        project_tel["meta"]["links"]["latest_contract_telemetry"] = rel_contract
        project_tel["meta"]["links"]["latest_dashboard_contract"] = rel_dash_contract
        project_tel["meta"]["latest_task_id"] = task_id
        _write_json(project_path, project_tel)

        # 纯静态大屏：内嵌 JSON，双击 HTML 即可，无需 serve
        gov_dir = project_path.parent
        tpl = _find_dashboard_template()
        dash_project = write_static_dashboard(gov_dir / "dashboard.html", project_tel, tpl)
        dash_contract = write_static_dashboard(gov_dir / rel_dash_contract, telemetry, tpl)

        # 若 --output 不是项目路径也不是契约路径，额外写一份用户指定文件
        out_resolved = out.resolve()
        if out_resolved != project_path.resolve() and (
            not contract_path or out_resolved != contract_path.resolve()
        ):
            _write_json(out, telemetry)

        return {
            "contract_path": str(contract_path),
            "project_path": str(project_path),
            "dashboard_project": str(dash_project),
            "dashboard_contract": str(dash_contract),
            "telemetry": telemetry,
            "project": project_tel,
        }

    # 纯项目级采集（无 --task）：优先从已有 runs 跨契约累加；无 runs 则保留本次快照
    existing = _load_json(project_path) or {}
    runs = existing.get("runs") or []
    if runs:
        base = existing
        agg = _aggregate_project_from_runs(
            telemetry["meta"].get("project") or (base.get("meta") or {}).get("project"),
            runs,
            base,
            project_path.parent,
        )
        agg["meta"]["links"] = {
            "project_telemetry": "telemetry.json",
            "contract_telemetry": None,
            "dashboard_project": "dashboard.html",
            "dashboard_contract": None,
            "latest_contract_telemetry": (base.get("meta") or {}).get("links", {}).get(
                "latest_contract_telemetry"
            ),
            "latest_dashboard_contract": (base.get("meta") or {}).get("links", {}).get(
                "latest_dashboard_contract"
            ),
        }
        agg["meta"]["run_count"] = len(runs)
        agg["meta"]["latest_task_id"] = (base.get("meta") or {}).get("latest_task_id")
        _write_json(project_path, agg)
        dash_project = write_static_dashboard(
            project_path.parent / "dashboard.html",
            agg,
            _find_dashboard_template(),
        )
        return {
            "contract_path": None,
            "project_path": str(project_path),
            "dashboard_project": str(dash_project),
            "dashboard_contract": None,
            "telemetry": agg,
            "project": agg,
        }
    # 无历史 runs：直接写本次采集快照
    telemetry["meta"]["scope"] = "project"
    telemetry["meta"]["task_id"] = None
    telemetry["meta"]["links"] = {
        "project_telemetry": "telemetry.json",
        "contract_telemetry": None,
        "dashboard_project": "dashboard.html",
        "dashboard_contract": None,
    }
    _write_json(project_path, telemetry)
    dash_project = write_static_dashboard(
        project_path.parent / "dashboard.html",
        telemetry,
        _find_dashboard_template(),
    )
    return {
        "contract_path": None,
        "project_path": str(project_path),
        "dashboard_project": str(dash_project),
        "dashboard_contract": None,
        "telemetry": telemetry,
        "project": telemetry,
    }


# ─── Layer 1: 价值层 — 回答"AI 创造多少价值" ──────────────

def _collect_value_layer(args) -> dict:
    measurements = getattr(args, "_p0_measurements", {})
    assigned_m = measurements.get("tasks_assigned", {})
    completed_m = measurements.get("tasks_completed", {})
    first_m = measurements.get("tasks_first_pass", {})
    tasks_assigned = args.tasks_assigned

    # P0: 目标准确率
    goal_known = tasks_assigned is not None and args.tasks_completed is not None and tasks_assigned > 0
    goal_accuracy = _safe_ratio(args.tasks_completed, tasks_assigned) if goal_known else None

    # P0: 首次成功率
    first_known = args.tasks_first_pass is not None and args.tasks_completed is not None and args.tasks_completed > 0
    first_pass_rate = _safe_ratio(args.tasks_first_pass, args.tasks_completed) if first_known else None

    # P1: 复合 ROI（含失败折现）
    compound_roi = _calc_compound_roi(args)

    # 目标准确率健康度
    if goal_accuracy is None:
        goal_health = "INSUFFICIENT_DATA"
    elif goal_accuracy >= 0.80:
        goal_health = "L3_READY"  # 适合 L3 受监督自主
    elif goal_accuracy >= 0.60:
        goal_health = "L2_COLLAB"  # 仍处于 L2 协作阶段
    else:
        goal_health = "NEEDS_IMPROVEMENT"  # 需优化 Prompt 策略

    return {
        "goal_accuracy": {
            "value": round(goal_accuracy, 4) if goal_accuracy is not None else None,
            "display": f"{goal_accuracy * 100:.1f}%" if goal_accuracy is not None else "N/A",
            "status": completed_m.get("status", "DECLARED" if goal_known else "UNKNOWN"),
            "source": completed_m.get("source", "legacy_input" if goal_known else "missing_source"),
            "evidence": completed_m.get("evidence", []),
            "measured_at": completed_m.get("measured_at"),
            "tasks_assigned": args.tasks_assigned,
            "tasks_completed": args.tasks_completed,
            "health": goal_health,
            "threshold": {
                "l3_ready": 0.80,
                "l2_collab": 0.60,
            },
        },
        "first_pass_rate": {
            "value": round(first_pass_rate, 4) if first_pass_rate is not None else None,
            "display": f"{first_pass_rate * 100:.1f}%" if first_pass_rate is not None else "N/A",
            "status": first_m.get("status", "DECLARED" if first_known else "UNKNOWN"),
            "source": first_m.get("source", "legacy_input" if first_known else "missing_event_history"),
            "evidence": first_m.get("evidence", []),
            "measured_at": first_m.get("measured_at"),
            "tasks_first_pass": args.tasks_first_pass,
            "tasks_assigned": args.tasks_assigned,
            "impact_note": (
                "首次成功率从 60%→80% 可降低约 50% 单任务 Token 成本"
                if first_pass_rate is not None and first_pass_rate < 0.80 else
                "首次成功率处于健康水平" if first_pass_rate is not None else "缺少首次正式验证历史"
            ),
        },
        "compound_roi": compound_roi,
    }


DEFAULT_AI_MONTHLY_COST_PER_PERSON = 500


def _load_cost_model(project_dir: Path) -> dict:
    """Load the independent cost model, with legacy constraints compatibility."""
    canonical = [
        project_dir / "governance" / "measurement-contracts" / "AI_Cost_Model.yaml",
        project_dir / "AI_Cost_Model.yaml",
    ]
    try:
        import yaml
    except ImportError:
        return {}
    for cand in canonical:
        if cand.exists():
            try:
                data = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
                if isinstance(data, dict) and data.get("schema") == "ai-cost-model/v1":
                    return {**data, "_source": str(cand.relative_to(project_dir)), "_source_type": "measurement_contract"}
            except Exception:
                pass
    # Compatibility only: new projects must use AI_Cost_Model.yaml.
    cands = [
        project_dir / "governance" / "constraints.yaml",
        project_dir / "constraints.yaml",
    ]
    for cand in cands:
        if cand.exists():
            try:
                data = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
                cm = data.get("cost_model")
                if cm and isinstance(cm, dict):
                    return {**cm, "_source": str(cand.relative_to(project_dir)), "_source_type": "legacy_constraints"}
            except Exception:
                pass
    return {}


def _calc_compound_roi(args) -> dict:
    """P1: 月度复合 ROI（T-153 改进：时间维度对齐 + 合理默认值）

    公式：月度 ROI = (月度人力节省 - 月度AI成本) / 月度AI成本 × 100%
    月度人力节省 = 每任务人力节省 × 月任务数
    每任务人力节省 = hours_saved_per_task × human_hourly_rate
    月任务数 = 从历史 runs 自动推导（runs总数 / 跨度天数 × 30），默认 10
    """
    project_dir = Path(getattr(args, "_project_dir", None) or ".")
    cost_model = _load_cost_model(project_dir)
    token_measurement = getattr(args, "_token_measurement", {}) or {}
    principal_id = (getattr(args, "principal_id", None) or
                    token_measurement.get("principal_id") or
                    cost_model.get("default_principal_id"))
    people = cost_model.get("people") if isinstance(cost_model.get("people"), dict) else {}
    person = people.get(principal_id, {}) if principal_id else {}
    person = person if isinstance(person, dict) else {}
    human_rate = (getattr(args, "human_hourly_rate", 0) or
                  person.get("human_hourly_rate") or cost_model.get("human_hourly_rate") or 200)
    hours_saved = (getattr(args, "hours_saved_per_task", 0) or
                   person.get("hours_saved_per_task") or cost_model.get("hours_saved_per_task") or 0.5)
    cli_ai_cost = getattr(args, "ai_monthly_cost", 0)
    ai_monthly = (cli_ai_cost or person.get("ai_monthly_cost") or
                  cost_model.get("default_monthly_cost_per_person") or
                  cost_model.get("ai_monthly_cost") or DEFAULT_AI_MONTHLY_COST_PER_PERSON)
    if cli_ai_cost:
        cost_status = "CLI_OVERRIDE"
    elif person.get("ai_monthly_cost"):
        cost_status = "PERSON_CONFIGURED"
    elif cost_model:
        cost_status = "MODEL_DEFAULT"
    else:
        cost_status = "FRAMEWORK_DEFAULT"
    resolved_principal = principal_id or "UNATTRIBUTED"

    if not human_rate or not hours_saved:
        return {"status": "INSUFFICIENT_DATA", "detail": "缺少成本参数，请在 governance/measurement-contracts/AI_Cost_Model.yaml 配置人员成本模型"}

    tasks_completed = max(args.tasks_completed or 0, 0)
    tasks_assigned = max(args.tasks_assigned or 0, 1)
    failure_rate = 1.0 - _safe_ratio(tasks_completed, tasks_assigned)

    # 每任务人力节省
    task_saving = hours_saved * human_rate

    # 月任务数估算：从 runs 历史推导，或用默认值 10
    monthly_tasks = getattr(args, "estimated_monthly_tasks", None)
    if monthly_tasks is None:
        monthly_tasks = 10  # 保守默认：每月 10 个任务

    # 月度人力节省（含失败折现）
    monthly_saving_raw = task_saving * monthly_tasks
    monthly_saving = monthly_saving_raw * (1.0 - failure_rate)

    # 月度 AI 成本
    ai_cost = max(ai_monthly, 1)

    # 月度复合 ROI
    roi_pct = ((monthly_saving - ai_cost) / ai_cost) * 100

    return {
        "value": round(roi_pct, 1),
        "display": f"{roi_pct:.1f}%",
        "breakdown": {
            "task_saving": round(task_saving, 2),
            "monthly_tasks": monthly_tasks,
            "monthly_saving_raw": round(monthly_saving_raw, 2),
            "failure_rate": round(failure_rate, 4),
            "monthly_saving": round(monthly_saving, 2),
            "ai_monthly_cost": ai_cost,
            "principal_id": resolved_principal,
            "cost_status": cost_status,
            "cost_model_source": cost_model.get("_source", "framework-default"),
            "currency": cost_model.get("currency", "CNY"),
        },
        "formula": "((每任务节省 × 月任务数 × (1-失败率)) - 月AI成本) / 月AI成本 × 100%",
        "health": "EXCELLENT" if roi_pct >= 400 else "POSITIVE" if roi_pct >= 100 else "MARGINAL" if roi_pct >= 0 else "NEGATIVE",
        "note": (
            f"每任务节省 ¥{task_saving:.0f} × {monthly_tasks} 任务/月 = ¥{monthly_saving_raw:.0f}/月"
            if roi_pct >= 0 else
            f"月度节省 ¥{monthly_saving:.0f} < 月AI成本 ¥{ai_cost}，需提升任务量或效率"
        ),
    }


# ─── Layer 2: 能力层 — 回答"Agent 有多自主" ──────────────

def _collect_capability_layer(args) -> dict:
    measurements = getattr(args, "_p0_measurements", {})
    failure_m = measurements.get("constraint_failures_total", {})
    healed_m = measurements.get("auto_healed", {})
    # P0: 约束自愈率
    auto_known = (args.auto_healed is not None and args.constraint_failures_total is not None
                  and args.constraint_failures_total > 0)
    auto_heal_rate = _safe_ratio(args.auto_healed, args.constraint_failures_total) if auto_known else None

    # HITL 升级率（已有，归入能力层）
    hitl_rate = _safe_ratio(args.hitl_count, max(args.execution_rounds, 1))

    # MUST 约束通过率
    must_pass_rate = (1.0 - _safe_ratio(args.must_failed, args.must_constraints)) if args.must_constraints > 0 else None

    # 综合自主性评分 (0-100)
    autonomy_score = _calc_autonomy_score(auto_heal_rate, hitl_rate, must_pass_rate) if auto_heal_rate is not None and must_pass_rate is not None else None

    return {
        "auto_heal_rate": {
            "value": round(auto_heal_rate, 4) if auto_heal_rate is not None else None,
            "display": f"{auto_heal_rate * 100:.1f}%" if auto_heal_rate is not None else "N/A",
            "status": failure_m.get("status", "DECLARED" if auto_known else "UNKNOWN"),
            "source": failure_m.get("source", "legacy_input" if auto_known else "missing_event_history"),
            "evidence": failure_m.get("evidence", []),
            "measured_at": failure_m.get("measured_at"),
            "auto_healed": args.auto_healed,
            "failures_total": args.constraint_failures_total,
            "health": ("NOT_APPLICABLE" if failure_m.get("status") == "NOT_APPLICABLE"
                       else "INSUFFICIENT_DATA" if auto_heal_rate is None
                       else "EXCELLENT" if auto_heal_rate >= 0.70
                       else "GOOD" if auto_heal_rate >= 0.40 else "NEEDS_WORK"),
            "note": "Agent 自主修复约束失败的比例，直接反映自治修复能力",
        },
        "hitl_escalation_rate": {
            "value": round(hitl_rate, 4),
            "display": f"{hitl_rate * 100:.1f}%",
            "hitl_count": args.hitl_count,
            "execution_rounds": args.execution_rounds,
            "health": "LOW_TOUCH" if hitl_rate <= 0.10 else "MODERATE" if hitl_rate <= 0.30 else "HIGH_TOUCH",
        },
        "must_pass_rate": {
            "value": round(must_pass_rate, 4) if must_pass_rate is not None else None,
            "display": f"{must_pass_rate * 100:.1f}%" if must_pass_rate is not None else "N/A",
            "status": "MEASURED" if must_pass_rate is not None else "NOT_APPLICABLE",
            "source": "constraint_matrix" if must_pass_rate is not None else "no_applicable_constraints",
            "must_passed": args.must_constraints - args.must_failed,
            "must_total": args.must_constraints,
        },
        "autonomy_score": {
            "value": round(autonomy_score, 1) if autonomy_score is not None else None,
            "display": f"{autonomy_score:.1f}/100" if autonomy_score is not None else "N/A",
            "status": "MEASURED" if autonomy_score is not None else "UNKNOWN",
            "components": {
                "auto_heal_weight": 0.4,
                "must_pass_weight": 0.35,
                "hitl_weight": 0.25,
            },
            "health": (
                "INSUFFICIENT_DATA" if autonomy_score is None
                else "L3_READY" if autonomy_score >= 80
                else "L2_MATURE" if autonomy_score >= 60
                else "L1_BASELINE"
            ),
        },
    }


def _calc_autonomy_score(auto_heal: float, hitl: float, must_pass: float) -> float:
    """综合自主性评分"""
    # 自愈率贡献 (0.4) + MUST 通过率 (0.35) + (1-HITL率) (0.25)
    score = (
        auto_heal * 40 +
        must_pass * 35 +
        (1.0 - min(hitl, 1.0)) * 25
    )
    return min(100.0, max(0.0, score))


# ─── Layer 3: 效率层 — 回答"人机协作效率如何" ──────────────

def _collect_efficiency_layer(args) -> dict:
    context_measurement = getattr(args, "_context_measurement", None)
    context_not_collected = not context_measurement and (
        args.context_input_tokens == 0 and args.context_output_tokens == 0
    )

    # Token 效率：每任务平均 Token
    measurement = getattr(args, "_token_measurement", {})
    token_known = _is_measured_task_usage(measurement)
    # T-153: ESTIMATED 降级 — 有 _token_measurement 且 value > 0，或无 measurement 但 token_usage > 0
    token_estimated = (not token_known and (
        (measurement.get("value") and int(measurement.get("value", 0)) > 0) or
        (not measurement and args.token_usage > 0)
    ))
    tokens_per_task = (
        args.token_usage / max(args.tasks_assigned or 0, 1)
        if (token_known or token_estimated) and args.token_usage > 0 else None
    )

    # 执行效率：每轮次完成任务数
    tasks_per_round = _safe_ratio(args.tasks_completed or 0, max(args.execution_rounds, 1))

    if context_measurement:
        ratio = context_measurement["compression_ratio"].get("value")
        context_compression = {
            "status": context_measurement.get("status", "MEASURED"),
            "ratio": ratio,
            "display": f"{ratio:.1f}:1" if ratio is not None else "N/A",
            "counter": context_measurement.get("counter"),
            "candidate": context_measurement.get("candidate"),
            "injected": context_measurement.get("injected"),
            "required_retention": context_measurement.get("required_retention"),
            "trace_coverage": context_measurement.get("trace_coverage"),
            "budget_utilization": context_measurement.get("budget_utilization"),
            "source": context_measurement.get("source"),
            "measured_at": context_measurement.get("measured_at"),
            "measurement": context_measurement,
            "health": (
                "INCOMPLETE" if (context_measurement.get("required_retention") or {}).get("status") == "INCOMPLETE"
                else "EXCELLENT" if ratio is not None and ratio >= 5.0
                else "GOOD" if ratio is not None and ratio >= 3.0 else "ROOM_FOR_IMPROVEMENT"
            ),
            "note": "压缩率必须与必要上下文保留率和 Trace 覆盖率共同解释",
        }
    elif context_not_collected:
        context_compression = {
            "status": "NOT_COLLECTED",
            "display": "未采集",
            "ratio": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "health": "NOT_COLLECTED",
            "note": "传入 --context-input-tokens 和 --context-output-tokens 以启用",
        }
    else:
        cc_ratio = _safe_ratio(args.context_input_tokens, max(args.context_output_tokens, 1))
        context_compression = {
            "status": "DECLARED",
            "ratio": round(cc_ratio, 1),
            "display": f"{cc_ratio:.1f}:1",
            "input_tokens": args.context_input_tokens,
            "output_tokens": args.context_output_tokens,
            "health": "EXCELLENT" if cc_ratio >= 5.0 else "GOOD" if cc_ratio >= 3.0 else "ROOM_FOR_IMPROVEMENT",
            "source": "legacy_cli_input",
            "note": (
                "上下文压缩比 ≥ 5:1 表示裁剪效果优秀"
                if cc_ratio >= 5.0 else "上下文压缩比偏低"
            ),
        }

    return {
        "context_compression": context_compression,
        "token_efficiency": {
            "tokens_per_task": round(tokens_per_task, 0) if tokens_per_task is not None else None,
            "display": str(round(tokens_per_task)) if tokens_per_task is not None else "N/A",
            "total_tokens": args.token_usage if (token_known or token_estimated) else None,
            "total_tasks": args.tasks_assigned,
            "status": "MEASURED" if token_known else ("ESTIMATED" if token_estimated else "UNKNOWN"),
            "health": ("UNKNOWN" if tokens_per_task is None else
                       "EFFICIENT" if tokens_per_task < 10000 else
                       "NORMAL" if tokens_per_task < 25000 else "HIGH"),
        },
        "execution_efficiency": {
            "tasks_per_round": round(tasks_per_round, 2),
            "tasks_completed": args.tasks_completed,
            "execution_rounds": args.execution_rounds,
            "health": "EFFICIENT" if tasks_per_round >= 1.5 else "NORMAL",
        },
    }


# ─── Layer 4: 进化层 — 回答"系统在变好还是变差" ────────────

def _collect_evolution_layer(args) -> dict:
    # P1: 知识沉淀率
    knowledge_rate = _safe_ratio(args.new_patterns, max(args.total_patterns, 1))

    return {
        "knowledge_crystallization": {
            "rate": round(knowledge_rate, 4),
            "display": f"{knowledge_rate * 100:.1f}%",
            "new_patterns_this_cycle": args.new_patterns,
            "total_patterns_accumulated": args.total_patterns,
            "health": "ACTIVE_LEARNING" if knowledge_rate >= 0.15 else "STEADY" if knowledge_rate >= 0.05 else "STAGNANT",
            "note": (
                "知识持续沉淀中，意图图谱在持续进化"
                if knowledge_rate >= 0.05
                else "建议关注反思 LOOP 产出，增加模式发现"
            ),
        },
        "trend_note": (
            "趋势数据需多周期累积后分析。"
            "建议每次 SCOPE-V 后运行本采集器，对比历史数据观察趋势。"
        ),
    }


# ─── 兼容旧版字段 ──────────────────────────────────────────

def _collect_pipeline(args) -> dict:
    mt = getattr(args, "_matrix_tests", None)
    if mt and not mt.get("skipped"):
        return {"tests": mt["tests"]}
    return {
        "tests": {
            "total": args.test_total,
            "passed": args.test_passed,
            "failed": args.test_failed,
            "errors": args.test_errors,
            "pass_rate": _safe_ratio(args.test_passed, max(args.test_total, 1)),
        }
    }


def _collect_quality(args) -> dict:
    mt = getattr(args, "_matrix_tests", None)
    if mt and not mt.get("skipped"):
        return {"coverage": mt["coverage"]}
    return {
        "coverage": {
            "line_rate": args.coverage_pct,
            "threshold": args.coverage_threshold,
            "status": "PASS" if args.coverage_pct >= args.coverage_threshold else "FAIL",
        }
    }


def _collect_performance(args) -> dict:
    return {
        "benchmark": {
            "warmup": args.bench_warmup,
            "samples": args.bench_samples,
            "p50_ms": args.bench_p50,
            "p95_ms": args.bench_p95,
            "p99_ms": args.bench_p99,
            "max_ms": args.bench_max,
            "threshold_ms": args.bench_threshold,
            "status": "PASS" if args.bench_p95 <= args.bench_threshold else "FAIL",
        }
    }


def _collect_cost(args) -> dict:
    measurement = getattr(args, "_token_measurement", None) or {
        "value": args.token_usage, "status": "UNKNOWN", "source": getattr(args, "token_source", "estimated"),
        "scope": "legacy_input", "evidence": [], "measured_at": None, "detail": "",
    }
    # T-153: 降级处理 — UNKNOWN 但 value > 0 时标 ESTIMATED（而非 None）
    is_measured = _is_measured_task_usage(measurement)
    is_estimated = (not is_measured and measurement.get("value") and int(measurement.get("value", 0)) > 0)
    token_usage_val = None
    if is_measured:
        token_usage_val = args.token_usage
    elif is_estimated:
        token_usage_val = int(measurement.get("value", 0))

    return {
        "token_usage": token_usage_val,
        "token_source": getattr(args, "token_source", "estimated"),
        "token_measurement": measurement,
        "token_status": "MEASURED" if is_measured else ("ESTIMATED" if is_estimated else "UNKNOWN"),
        "execution_rounds": args.execution_rounds,
        "hitl_count": args.hitl_count,
        "hitl_rate": _safe_ratio(args.hitl_count, max(args.execution_rounds, 1)),
        "estimated_cost_usd": (round(token_usage_val * 0.000002, 4)
                               if token_usage_val is not None
                               else None),
    }


def _is_web_or_code_project(project_dir: Path) -> bool:
    """判定是否应进行 NFR(G6-G8) 评估：含 Web/TS/JS/Go/Python 等源码的项目。"""
    markers = ["package.json", "tsconfig.json", "go.mod", "requirements.txt",
               "pyproject.toml", "pom.xml", "Cargo.toml"]
    for m in markers:
        if (project_dir / m).exists():
            return True
    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx", "*.py", "*.go"):
        try:
            if any(project_dir.rglob(ext)):
                return True
        except Exception:
            continue
    return False


# ── 约束矩阵 → 门禁 / 测试 的唯一来源：harness 执行引擎 ──
# 门禁不再由 collect_telemetry 手工判定，而是直接消费 harness 对约束矩阵(check)
# 与测试套件(tests) 的执行结果。门禁 G0-G8 共 9 个，统一由 harness 派生。
_GATE_NAMES = {
    "G0": "意图前置", "G1": "文件结构", "G2": "数据完整性", "G3": "行为正确",
    "G4": "质量达标", "G5": "过程合规", "G6": "安全合规",
    "G7": "可靠性合规", "G8": "可观测性合规",
}
_ALL_GATES = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]


_HARNESS_VENV = Path.home() / ".agentic-agile-343" / "venv"


def _can_import_yaml(python: str) -> bool:
    """检测指定 python 解释器是否能 import yaml"""
    from _bootstrap import can_import_yaml
    return can_import_yaml(python)


def _bootstrap_harness_venv() -> str:
    """创建或复用持久 venv，且仅在 PyYAML 缺失时安装依赖。

    解决可移植性问题：skill 分享到其他机器后，系统 python3 未装 pyyaml，
    harness.py _load_yaml 会 ModuleNotFoundError 导致全部门禁 UNEVALUATED。
    旧版把 venv 放 /tmp（重启即丢）或硬编码作者路径（他机不存在），
    本版改为用户主目录下持久 venv，首次自动创建、后续复用。
    """
    import venv as _venv
    from _bootstrap import venv_python
    venv_py = venv_python(_HARNESS_VENV)
    if venv_py.exists() and _can_import_yaml(str(venv_py)):
        return str(venv_py)
    try:
        _HARNESS_VENV.parent.mkdir(parents=True, exist_ok=True)
        if not venv_py.exists():
            _venv.create(_HARNESS_VENV, with_pip=True)
        if not _can_import_yaml(str(venv_py)):
            completed = subprocess.run(
                [str(venv_py), "-m", "pip", "install", "--quiet", "pyyaml>=6.0"],
                capture_output=True, timeout=120,
            )
            if completed.returncode != 0:
                raise RuntimeError("pyyaml installation failed")
        return str(venv_py)
    except Exception as e:
        print(f"⚠️ 无法自动创建 harness venv: {e}", file=sys.stderr)
        print(f"   请手动执行: python3 -m venv {_HARNESS_VENV} && "
              f"{_HARNESS_VENV}/bin/pip install pyyaml", file=sys.stderr)
        return sys.executable  # 降级，让 harness 自己报 pyyaml 缺失


def _harness_py() -> str:
    """返回可运行 harness 的 python（含 pyyaml）。

    优先级:
    1. HARNESS_PY 环境变量（用户显式指定，最高优先）
    2. sys.executable（当前 python 已能 import yaml 则直接用）
    3. ~/.agentic-agile-343/venv（自动创建的持久 venv，首次自动 bootstrap）
    """
    env_py = os.environ.get("HARNESS_PY")
    if env_py and Path(env_py).exists():
        return env_py
    if _can_import_yaml(sys.executable):
        return sys.executable
    return _bootstrap_harness_venv()


def _run_harness_json(project_dir: Path, sub: str, extra=None) -> dict | None:
    """调用 harness CLI 并返回 JSON；失败返回含 __error__ 的 dict。

    harness 是唯一执行引擎：约束矩阵由 harness check 评估、测试套件由 harness tests 运行。
    collector 只做消费，不再重复实现门禁/测试逻辑（从源头解决）。
    """
    harness = Path(__file__).resolve().parent / "harness.py"
    if not harness.exists():
        return {"__error__": f"未找到 harness.py: {harness}"}
    cmd = [_harness_py(), str(harness), sub, "--project-dir", str(project_dir)] + (extra or [])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=360, cwd=str(project_dir))
        return json.loads(proc.stdout)
    except Exception as e:
        return {"__error__": str(e)}


def _wire_matrix(args, task_id):
    """从约束矩阵派生门禁与测试，挂到 args 上供 _collect_* 消费（源头解决）。"""
    out = getattr(args, "output", None)
    if out and str(out).endswith("telemetry.json"):
        project_dir = Path(out).resolve().parent.parent
    else:
        project_dir = Path.cwd()
    if getattr(args, "auto_nfr", True) and _is_web_or_code_project(project_dir):
        if getattr(args, "skip_matrix_check", False) and task_id:
            previous = _load_json(project_dir / "governance" / "telemetry" / "runs" / f"telemetry-{task_id}.json") or {}
            gov = previous.get("governance") or {}
            args._matrix_gov = {
                "gates": gov.get("gates", []), "gates_passed": gov.get("gates_passed", 0),
                "gates_total": gov.get("gates_total", 0), "passed": gov.get("gates_passed", 0),
                "total": gov.get("gates_total", 0), "must_constraints": gov.get("must_constraints", 0),
                "must_failed": gov.get("must_failed", 0), "skipped": False, "error": "",
                "nfr": {**(gov.get("nfr") or {}), "source": "reused_contract_telemetry"},
            }
        else:
            args._matrix_gov = _auto_run_nfr(
                project_dir, getattr(args, "verification_context", None)
            )
        if getattr(args, "skip_matrix_tests", False):
            total = max(0, int(getattr(args, "test_total", 0) or 0))
            passed = max(0, int(getattr(args, "test_passed", 0) or 0))
            args._matrix_tests = {
                "skipped": False, "error": "", "source": "verification_run_context",
                "tests": {"total": total, "passed": passed, "failed": max(0, total - passed),
                          "errors": 0, "pass_rate": _safe_ratio(passed, max(total, 1)),
                          "status": "PASS" if total and passed == total else "FAIL" if total else "UNKNOWN",
                          "runner": getattr(args, "test_runner", None) or "trusted_context",
                          "detail": "reused trusted Verification Run Context"},
                "coverage": {"line_rate": getattr(args, "coverage_pct", 0.0),
                             "threshold": getattr(args, "coverage_threshold", 90.0),
                             "status": "UNKNOWN"},
            }
        else:
            args._matrix_tests = _derive_tests_from_matrix(project_dir)
    else:
        args._matrix_gov = None
        args._matrix_tests = None


def _auto_run_nfr(project_dir: Path, verification_context: str | None = None) -> dict:
    """从约束矩阵派生门禁（harness check --all）：按 MUST 约束判定每门禁通过。

    返回所有 G0-G8 的逐条状态与 MUST 计数。
    保证 Web/TS/Go 等项目在采集时必然评估全部门禁（含 G6-G8 Web 扩展），
    且判定逻辑完全来自约束矩阵，而非手动传 --gates-total。
    """
    extra = ["--all", "--format", "json"]
    if verification_context:
        extra.extend(["--verification-context", verification_context])
    rep = _run_harness_json(project_dir, "check", extra)
    if not rep or "__error__" in rep:
        return {"gates": [], "passed": 0, "total": 0, "skipped": True,
                "error": (rep or {}).get("__error__", "harness 调用失败"),
                "must_constraints": 0, "must_failed": 0,
                "nfr": {"auto_triggered": True, "applied": False, "skipped": True,
                        "error": (rep or {}).get("__error__", "")}}
    gates_src = rep.get("gates", {})
    failed_by_gate = {}
    for r in rep.get("results", []):
        if r.get("gate") and not r.get("passed"):
            failed_by_gate.setdefault(r["gate"], []).append(
                f"{r['id']}: {r.get('detail', '')[:140]}")
    gates, passed, must_total, must_failed = [], 0, 0, 0
    for gid in _ALL_GATES:
        g = gates_src.get(gid)
        if not g:
            continue
        gp = g.get("gate_passed", False)
        detail = "; ".join(failed_by_gate.get(gid, [])) or (
            "所有 MUST 约束通过" if gp else "存在 MUST 约束失败")
        gates.append({"id": gid, "name": _GATE_NAMES.get(gid, gid),
                      "passed": gp, "detail": detail})
        if gp:
            passed += 1
        must_total += g.get("must_total", 0)
        must_failed += (g.get("must_total", 0) - g.get("must_passed", 0))
    return {"gates": gates, "passed": passed, "total": len(gates),
            "gates_passed": passed, "gates_total": len(gates),
            "skipped": False, "error": "",
            "must_constraints": must_total, "must_failed": must_failed,
            "nfr": {"auto_triggered": True, "applied": True, "skipped": False, "error": ""}}


def _derive_tests_from_matrix(project_dir: Path) -> dict:
    """从约束矩阵运行测试套件：调用 harness tests，返回真实管道吞吐与覆盖率。

    无测试套件 → status=NO_TEST_SUITE（诚实，非零静默）；有则解析 total/passed/failed/errors/coverage。
    """
    res = _run_harness_json(project_dir, "tests", ["--format", "json"])
    if not res or "__error__" in res:
        return {"skipped": True, "error": (res or {}).get("__error__", "harness 不可用"),
                "tests": {"total": 0, "passed": 0, "failed": 0, "errors": 0,
                          "pass_rate": 0.0, "status": "UNKNOWN",
                          "detail": (res or {}).get("__error__", "")},
                "coverage": {"line_rate": 0.0, "threshold": 90.0, "status": "UNKNOWN"}}
    total = res.get("total", 0)
    passed = res.get("passed", 0)
    return {
        "skipped": False, "error": "",
        "tests": {
            "total": total, "passed": passed,
            "failed": res.get("failed", 0), "errors": res.get("errors", 0),
            "pass_rate": _safe_ratio(passed, max(total, 1)),
            "status": res.get("status", "UNKNOWN"),
            "runner": res.get("runner"),
            "detail": res.get("detail", ""),
        },
        "coverage": {
            "line_rate": res.get("coverage", 0.0),
            "threshold": res.get("coverage_threshold", 90.0),
            "status": res.get("coverage_status", "UNKNOWN"),
        },
    }


def _collect_governance(args) -> dict:
    # 优先消费约束矩阵派生的门禁（harness check --all）；不可用时回退手工参数
    mg = getattr(args, "_matrix_gov", None)
    if mg and not mg.get("skipped"):
        return {
            "gates_passed": mg["gates_passed"],
            "gates_total": mg["gates_total"],
            "gates": mg["gates"],
            "must_constraints": mg["must_constraints"],
            "must_failed": mg["must_failed"],
            "contract_pass_rate": _safe_ratio(args.contract_passed, max(args.contract_total, 1)),
            "evidence_status": (
                "READY_FOR_HITL"
                if mg["must_failed"] == 0
                and (mg["gates_total"] == 0
                     or _safe_ratio(mg["gates_passed"], max(mg["gates_total"], 1)) == 1.0)
                else "BLOCKED"
            ),
            "nfr": mg["nfr"],
        }

    # 回退：harness 不可用时，门禁统一标记为「未评估」(passed=null)。
    # 不再从 --gates-passed 伪造逐条 pass/fail；手动参数仅用于计数，不用于判定。
    fallback_gates = [
        {"id": gid, "name": _GATE_NAMES.get(gid, gid), "passed": None,
         "detail": "harness 不可用，未评估（手动计数仅供展示）"}
        for gid in _ALL_GATES
    ]
    return {
        "gates_passed": args.gates_passed,
        "gates_total": args.gates_total,
        "gates": fallback_gates,
        "must_constraints": args.must_constraints,
        "must_failed": args.must_failed,
        "contract_pass_rate": _safe_ratio(args.contract_passed, max(args.contract_total, 1)),
        "evidence_status": "UNEVALUATED",
        "nfr": {
            "auto_triggered": getattr(args, "auto_nfr", True),
            "applied": False,
            "skipped": True,
            "error": "harness 不可用，门禁未评估；手动参数仅作计数降级",
        },
    }


# ─── 工具函数 ──────────────────────────────────────────────

def _safe_ratio(numerator, denominator) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


# ─── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Agentic Agile 343 遥测收集器 v2.1 — 单次契约 + 项目累积双轨"
    )
    parser.add_argument("--project", default=None, help="项目名称")
    parser.add_argument("--_project-dir", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--output",
        default="governance/telemetry.json",
        help="项目累积遥测路径（默认 governance/telemetry.json）",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="意图契约任务 ID，如 T-018；传入则写入单次遥测并更新项目 runs 索引",
    )
    parser.add_argument(
        "--scope",
        choices=["contract", "project", "auto"],
        default="auto",
        help="contract=单次契约, project=仅项目累积, auto=有 --task 则 contract",
    )
    parser.add_argument(
        "--auto-nfr",
        dest="auto_nfr",
        action="store_true",
        default=True,
        help="自动运行 harness 跨语言 NFR 验证器评估 G6-G8（Web/TS/Go 等项目默认开启，保证门禁必然触发）",
    )
    parser.add_argument(
        "--no-auto-nfr",
        dest="auto_nfr",
        action="store_false",
        help="关闭自动 NFR 扫描（G6-G8 不参与评估，门禁逐条状态标记为未评估）",
    )

    # ── 旧版兼容参数 ──
    parser.add_argument("--test-total", type=int, default=0)
    parser.add_argument("--test-passed", type=int, default=0)
    parser.add_argument("--test-failed", type=int, default=0)
    parser.add_argument("--test-errors", type=int, default=0)
    parser.add_argument("--skip-matrix-tests", action="store_true",
                        help="使用显式可信测试快照，不再调用 harness tests")
    parser.add_argument("--skip-matrix-check", action="store_true",
                        help="复用既有单任务门禁快照，不再调用 harness check")
    parser.add_argument("--test-runner", default=None,
                        help="可信测试快照的 runner，仅与 --skip-matrix-tests 一起使用")
    parser.add_argument("--verification-context", default=None,
                        help="传给 Harness 的可信 Verification Run Context 路径")
    parser.add_argument("--coverage-pct", type=float, default=0.0)
    parser.add_argument("--coverage-threshold", type=float, default=90.0)
    parser.add_argument("--bench-warmup", type=int, default=1000)
    parser.add_argument("--bench-samples", type=int, default=10000)
    parser.add_argument("--bench-p50", type=float, default=0.0)
    parser.add_argument("--bench-p95", type=float, default=0.0)
    parser.add_argument("--bench-p99", type=float, default=0.0)
    parser.add_argument("--bench-max", type=float, default=0.0)
    parser.add_argument("--bench-threshold", type=float, default=2.0)
    parser.add_argument("--token-usage", type=int, default=0)
    parser.add_argument("--token-source", type=str, default="estimated",
                        help="token 数据来源: measured:ocusage:project / measured:ocusage:client-total / estimated。"
                             "由 fetch_token_usage.sh (@geeeger/ocusage) 实测时自动填写")
    parser.add_argument("--token-measurement-json", default=None,
                        help="结构化 Token Measurement Contract JSON")
    parser.add_argument("--execution-rounds", type=int, default=0)
    parser.add_argument("--hitl-count", type=int, default=0)
    parser.add_argument("--gates-passed", type=int, default=0,
                        help="【降级】手动门禁通过数（仅 harness 不可用时使用，逐条状态标记为未评估）")
    parser.add_argument("--gates-total", type=int, default=9,
                        help="【降级】手动门禁总数（默认 9 = G0-G8；仅 harness 不可用时使用）")
    parser.add_argument("--must-constraints", type=int, default=0)
    parser.add_argument("--must-failed", type=int, default=0)
    parser.add_argument("--contract-passed", type=int, default=0)
    parser.add_argument("--contract-total", type=int, default=0)

    # ── 价值层参数 ──
    parser.add_argument("--tasks-assigned", type=int, default=None,
                        help="【P0】总分配任务数")
    parser.add_argument("--tasks-completed", type=int, default=None,
                        help="【P0】正确完成的任务数")
    parser.add_argument("--tasks-first-pass", type=int, default=None,
                        help="【P0】一次性正确完成的任务数")

    # ── 能力层参数 ──
    parser.add_argument("--auto-healed", type=int, default=None,
                        help="【P0】Agent 自主修复的约束失败数")
    parser.add_argument("--constraint-failures-total", type=int, default=None,
                        help="【P0】约束失败总数（含人工修复）")
    parser.add_argument("--p0-source", choices=["declared"], default=None,
                        help="显式手工 P0 数字的来源类型；不传则自动从契约/Evidence/事件派生")

    # ── 价值层 ROI 参数 ──
    parser.add_argument("--human-hourly-rate", type=float, default=0.0,
                        help="【P1】人力时薪（元）")
    parser.add_argument("--hours-saved-per-task", type=float, default=0.0,
                        help="【P1】每任务平均节省工时")
    parser.add_argument("--ai-monthly-cost", type=float, default=0.0,
                        help="【P1】AI 工具月成本（元）")
    parser.add_argument("--principal-id", default=None,
                        help="【P1】成本归属人 ID；缺省从 Usage Snapshot principal_id 获取")

    # ── 效率层参数 ──
    parser.add_argument("--context-input-tokens", type=int, default=0,
                        help="【P1】裁剪前上下文 Token 数")
    parser.add_argument("--context-output-tokens", type=int, default=0,
                        help="【P1】裁剪后上下文 Token 数")
    parser.add_argument("--context-measurement-json", default=None,
                        help="Context Pack measurement/v1 JSON")

    # ── 进化层参数 ──
    parser.add_argument("--new-patterns", type=int, default=0,
                        help="【P1】本周期新发现的模式数")
    parser.add_argument("--total-patterns", type=int, default=0,
                        help="【P1】累积模式总数")
    parser.add_argument("--merge", default=None,
                        help="合并多个遥测 JSON 文件（逗号分隔路径，或 'auto' 自动发现）")
    parser.add_argument("--rebuild", action="store_true",
                        help="仅根据已有 runs 重建项目累计遥测（修正聚合口径），不写入任何契约文件")
    parser.add_argument("--module-id", default=None,
                        help="模块 ID（多模块场景下标识遥测来源）")
    parser.add_argument("--tool", default="other",
                        help="宿主 AI 工具标识（如 codex、claude-code 或其他工具）")

    args = parser.parse_args()
    if args.token_measurement_json:
        try:
            args.token_measurement = json.loads(args.token_measurement_json)
        except json.JSONDecodeError as exc:
            parser.error(f"invalid --token-measurement-json: {exc}")
        if not isinstance(args.token_measurement, dict):
            parser.error("--token-measurement-json must be an object")
    if args.context_measurement_json:
        try:
            from context_measurement import validate_context_measurement
            from token_usage import project_identity
            args._context_measurement = json.loads(args.context_measurement_json)
        except json.JSONDecodeError as exc:
            parser.error(f"invalid --context-measurement-json: {exc}")
        output = Path(args.output).resolve()
        expected_project = output.parent.parent if output.parent.name == "governance" else Path.cwd().resolve()
        if not validate_context_measurement(
            args._context_measurement, args.task, project_identity(expected_project)["project_uid"]
        ):
            parser.error("--context-measurement-json does not match schema/task")
    # v1.19: --module-id 作为 --task 的 fallback（兼容旧调用习惯）
    if not args.task and args.module_id:
        args.task = args.module_id
    if args.scope == "auto":
        args.scope = "contract" if (args.task or args.module_id) else "project"

    # 重建模式：仅根据已有 runs 重新累计项目级遥测（不触碰契约文件）
    if args.rebuild:
        project_path = Path(args.output)
        if project_path.name != "telemetry.json":
            project_path = project_path.parent / "telemetry.json" if project_path.suffix == ".json" else project_path / "telemetry.json"
        existing = _load_json(project_path)
        if not existing or not existing.get("runs"):
            print("无可重建的 runs 历史，无法进行 --rebuild", file=sys.stderr)
            return 1
        runs = existing["runs"]
        base = existing
        agg = _aggregate_project_from_runs(
            (base.get("meta") or {}).get("project"),
            runs,
            base,
            project_path.parent,
        )
        agg["meta"]["links"] = {
            "project_telemetry": "telemetry.json",
            "contract_telemetry": None,
            "dashboard_project": "dashboard.html",
            "dashboard_contract": None,
            "latest_contract_telemetry": (base.get("meta") or {}).get("links", {}).get("latest_contract_telemetry"),
            "latest_dashboard_contract": (base.get("meta") or {}).get("links", {}).get("latest_dashboard_contract"),
        }
        agg["meta"]["run_count"] = len(runs)
        agg["meta"]["latest_task_id"] = (base.get("meta") or {}).get("latest_task_id")

        # ── 重建时从约束矩阵重新派生门禁与测试（代码可能已变更，不再沿用历史快照）──
        # project_path = governance/telemetry.json → .parent=governance → .parent.parent=项目根
        project_root = project_path.parent.parent
        if getattr(args, "auto_nfr", True) and _is_web_or_code_project(project_root):
            mg = _auto_run_nfr(project_root)
            tests = None if getattr(args, "skip_matrix_tests", False) else _derive_tests_from_matrix(project_root)
            gov = agg.get("governance", {}) or {}
            if mg.get("skipped"):
                gov["nfr"] = mg["nfr"]
            else:
                gov["gates"] = mg["gates"]
                gov["gates_passed"] = mg["gates_passed"]
                gov["gates_total"] = mg["gates_total"]
                gov["must_constraints"] = mg["must_constraints"]
                gov["must_failed"] = mg["must_failed"]
                gov["nfr"] = mg["nfr"]
            if tests and not tests.get("skipped"):
                agg["pipeline"] = {"tests": tests["tests"]}
                agg["quality"] = {"coverage": tests["coverage"]}
            agg["governance"] = gov

        _write_json(project_path, agg)
        dash = write_static_dashboard(project_path.parent / "dashboard.html", agg, _find_dashboard_template())
        t = agg
        print(f"项目累计遥测已重建（--rebuild）")
        print(f"  项目累积: {project_path}")
        print(f"  范围: project · 契约数: {len(runs)}")
        print(f"  版本: {t['meta']['version']} ({t['meta']['model']})")
        print(f"  价值层 — 目标准确率: {t['value']['goal_accuracy']['display']}")
        print(f"  价值层 — 首次成功率: {t['value']['first_pass_rate']['display']}")
        print(f"  能力层 — 约束自愈率: {t['capability']['auto_heal_rate']['display']}")
        print(f"  能力层 — 自主性评分: {t['capability']['autonomy_score']['display']}")
        print(f"  价值层 — 复合 ROI: {t['value']['compound_roi'].get('display', 'N/A')}")
        print(f"  效率层 — 上下文压缩比: {t['efficiency']['context_compression']['display']}")
        print(f"  进化层 — 知识沉淀率: {t['evolution']['knowledge_crystallization']['display']}")
        print(f"  证书资格: {t['certificate_eligibility']['label']} (CTA={'启用' if t['certificate_eligibility']['cta_enabled'] else '禁用'})")
        print(f"  总览大屏(纯静态双击): {dash}")
        return 0

    # 合并模式
    if args.merge:
        merged = merge_telemetry_files(args)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        print(f"合并完成: {merged['sources']} 个源 → {args.output}", file=sys.stderr)
        return 0

    telemetry = collect(args)
    result = persist_telemetry(args, telemetry)
    t = result["telemetry"]
    print(f"遥测数据已写入")
    if result.get("contract_path"):
        print(f"  单次契约: {result['contract_path']}")
    print(f"  项目累积: {result['project_path']}")
    print(f"  范围: {t['meta'].get('scope')} · 任务: {t['meta'].get('task_id') or '—'}")
    print(f"  版本: {t['meta']['version']} ({t['meta']['model']})")
    print(f"  价值层 — 目标准确率: {t['value']['goal_accuracy']['display']}")
    print(f"  价值层 — 首次成功率: {t['value']['first_pass_rate']['display']}")
    print(f"  能力层 — 约束自愈率: {t['capability']['auto_heal_rate']['display']}")
    print(f"  能力层 — 自主性评分: {t['capability']['autonomy_score']['display']}")
    print(f"  价值层 — 复合 ROI: {t['value']['compound_roi'].get('display', 'N/A')}")
    print(f"  效率层 — 上下文压缩比: {t['efficiency']['context_compression']['display']}")
    print(f"  进化层 — 知识沉淀率: {t['evolution']['knowledge_crystallization']['display']}")
    if result.get("project") and result["project"].get("runs"):
        print(f"  历史契约数: {len(result['project']['runs'])}")
    if result.get("dashboard_project"):
        print(f"  总览大屏(纯静态双击): {result['dashboard_project']}")
    if result.get("dashboard_contract"):
        print(f"  单次大屏(纯静态双击): {result['dashboard_contract']}")
    return 0


def merge_telemetry_files(args) -> dict:
    """合并多个遥测 JSON 文件

    支持:
      --merge auto: 自动发现（governance/telemetry.json + modules/*/governance/telemetry.json）
      --merge file1.json,file2.json: 手动指定文件列表
    """
    import glob as glob_mod
    files = []

    if args.merge == "auto":
        # 自动发现
        patterns = [
            "governance/telemetry.json",
            "modules/*/governance/telemetry.json",
            ".codex/telemetry.json",
            ".claude/telemetry.json",
        ]
        for pat in patterns:
            for f in glob_mod.glob(pat):
                if f not in files:
                    files.append(f)
    else:
        files = [f.strip() for f in args.merge.split(",")]

    if not files:
        return {"error": "未找到任何遥测文件", "sources": 0}

    merged = {
        "merged_at": datetime.now().isoformat(),
        "sources": len(files),
        "source_files": files,
        "modules": [],
        "totals": {
            "tasks_assigned": 0,
            "tasks_completed": 0,
            "tasks_first_pass": 0,
            "hitl_count": 0,
            "token_usage": 0,
            "gates_passed": 0,
            "gates_total": 0,
        },
    }

    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
        except Exception:
            continue

        # 提取模块级数据
        value = data.get("value", {})
        capability = data.get("capability", {})
        module_entry = {
            "source": f,
            "project": data.get("meta", {}).get("project", data.get("project", "unknown")),
            "module_id": data.get("module_id", args.module_id or f.split("/")[0]),
            "tool": data.get("tool", args.tool),
            "tasks_assigned": data.get("tasks_assigned", 0),
            "tasks_completed": data.get("tasks_completed", 0),
            "tasks_first_pass": data.get("tasks_first_pass", 0),
            "hitl_count": data.get("hitl_count", 0),
            "token_usage": data.get("token_usage", 0),
            "gates_passed": data.get("gates_passed", 0),
            "gates_total": data.get("gates_total", 0),
            "coverage_pct": data.get("coverage_pct", 0),
            "benchmark_p95_ms": data.get("bench_p95", data.get("benchmark_p95_ms", 0)),
        }
        merged["modules"].append(module_entry)

        # 累加总计
        for key in ["tasks_assigned", "tasks_completed", "tasks_first_pass",
                     "hitl_count", "token_usage", "gates_passed", "gates_total"]:
            merged["totals"][key] += module_entry.get(key, 0)

    # 计算聚合指标
    t = merged["totals"]
    t["goal_accuracy"] = round(t["tasks_completed"] / max(t["tasks_assigned"], 1) * 100, 1)
    t["first_pass_rate"] = round(t["tasks_first_pass"] / max(t["tasks_completed"], 1) * 100, 1)

    return merged


if __name__ == "__main__":
    sys.exit(main())
