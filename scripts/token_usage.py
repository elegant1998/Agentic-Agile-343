#!/usr/bin/env python3
"""Cross-platform optional ocusage probe. Missing data stays unavailable."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from command_runner import run_command
from tool_bootstrap import prepare_ocusage


def project_identity(project: Path | str) -> dict:
    supplied = Path(project).expanduser().absolute()
    root = supplied.resolve()
    try:
        repo = subprocess.run(["git", "-C", str(root), "config", "--get", "remote.origin.url"],
                              capture_output=True, text=True, timeout=5, shell=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        repo = ""
    repo_name = re.split(r"[/:]", repo)[-1].removesuffix(".git") if repo else ""
    aliases = list(dict.fromkeys([root.name, str(supplied), str(root), repo_name]))
    aliases = [alias for alias in aliases if alias]
    return {"project_uid": hashlib.sha256(str(root).encode()).hexdigest()[:16],
            "project_root": str(root), "aliases": aliases}


def task_delta_measurement(baseline: dict | None, current: dict | None) -> dict:
    current = current or {}
    common = (baseline and current and
              baseline.get("token_client") == current.get("token_client") and
              baseline.get("project_uid") == current.get("project_uid") and
              baseline.get("date") == current.get("date") and
              baseline.get("value") is not None and current.get("value") is not None)
    if not common or int(current["value"]) < int(baseline["value"]):
        return {**current, "value": None, "status": "UNKNOWN", "scope": "task_delta",
                "detail": "missing_or_incompatible_token_baseline"}
    return {**current, "value": int(current["value"]) - int(baseline["value"]),
            "status": "MEASURED", "scope": "task_delta",
            "detail": "end_snapshot_minus_start_snapshot"}


def _find_metric(payload: dict, client: str, identity: dict) -> dict | None:
    client_data = payload.get(client, {}) if isinstance(payload, dict) else {}
    projects = client_data.get("byProject") or {}
    matches = [projects[name] for name in identity["aliases"] if isinstance(projects.get(name), dict)]
    return matches[0] if len(matches) == 1 else None


def _detect_ocusage_clients(prefix: list[str]) -> list[str]:
    """用 ocusage detect 解析已安装的 AI 客户端列表。"""
    try:
        result = subprocess.run(
            [*prefix, "detect"],
            capture_output=True, text=True, timeout=30, shell=False,
        )
        # 输出格式: "  WorkBuddy (workbuddy): /path\n  Codex (codex): /path\n"
        import re
        return re.findall(r'\((\w+)\)', result.stdout)
    except Exception:
        return []


def _infer_host_tool() -> str:
    """从环境变量特征推断当前运行的 AI Coding 工具（不依赖外部传参）。

    优先级：
    1. AGENTIC_AGILE_HOST_TOOL 环境变量（标准化方式）
    2. 环境变量特征检测（__CFBundleIdentifier / WORKBUDDY_APP_NAME / CURSOR_* 等）
    3. 兜底 "other"
    """
    # 标准化环境变量
    explicit = os.environ.get("AGENTIC_AGILE_HOST_TOOL")
    if explicit:
        return explicit.lower()

    # 特征检测：按已知 AI 工具的环境变量签名匹配
    _ENV_SIGNATURES = {
        "workbuddy": ["WORKBUDDY_APP_NAME", "__CFBundleIdentifier=com.workbuddy"],
        "cursor":    ["CURSOR_TRACE_ID", "CURSOR_SESSION_ID"],
        "copilot":   ["COPILOT_LANGUAGE_SERVER", "GITHUB_COPILOT_TOKEN"],
        "codex":     ["OPENAI_CODEX", "CODEX_HOME"],
        "claude":    ["CLAUDE_CODE_ENTRYPOINT", "CLAUDE_API_KEY"],
        "opencode":  ["OPENCODE_HOME"],
        "mimocode":  ["MIMOCODE_HOME"],
        "zcode":     ["ZCODE_HOME"],
        "qoder":     ["QODER_HOME"],
        "codewhale": ["CODEWHALE_HOME"],
    }

    env_keys = set(os.environ.keys())
    env_str = " ".join(f"{k}={v}" for k, v in os.environ.items())

    for tool_name, signatures in _ENV_SIGNATURES.items():
        for sig in signatures:
            if "=" in sig:
                # 精确匹配 key=value（如 __CFBundleIdentifier=com.workbuddy）
                if sig in env_str:
                    return tool_name
            else:
                # key 存在即匹配
                if sig in env_keys:
                    return tool_name

    return "other"


# ocusage client 名与 host_tool 名的映射（不同时才需要映射）
_HOST_TOOL_TO_OCUSAGE_CLIENT = {
    "workbuddy": "workbuddy",
    "codebuddy": "workbuddy",
    "claude-code": "claude",
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "mimocode": "mimocode",
    "zcode": "zcode",
    "qoder": "qoder",
    "codewhale": "codewhale",
    "cursor": "cursor",
    "copilot": "copilot",
}


def collect_token_measurement(project: Path | str, *, host_tool: str | None = None,
                              token_clients: list[str] | None = None, date_name: str = "today",
                              baseline: dict | None = None) -> dict:
    identity = project_identity(project)
    # 精确推断 host_tool：CLI 参数 > 环境变量 > 特征检测
    if not host_tool or host_tool == "other":
        host_tool = _infer_host_tool()
    configured_client = os.environ.get("AGENTIC_AGILE_TOKEN_CLIENT")
    tool = prepare_ocusage()
    base = {"value": None, "status": "UNAVAILABLE", "source": "unavailable",
            "evidence": [], "measured_at": None, "scope": "task_delta",
            "host_tool": host_tool, "token_client": None, **identity}
    if not tool.get("executable"):
        base["detail"] = tool.get("detail", "ocusage is unavailable")
        return base
    prefix = tool.get("argv_prefix") or [tool["executable"]]

    # 确定要查的 ocusage client 列表
    if token_clients:
        clients = token_clients
    elif configured_client:
        clients = [configured_client]
    else:
        # 从 host_tool 精确映射到 ocusage client
        ocusage_client = _HOST_TOOL_TO_OCUSAGE_CLIENT.get(host_tool)
        if ocusage_client:
            clients = [ocusage_client]
        else:
            # host_tool 未知 → 用 detect 做兜底
            detected = _detect_ocusage_clients(prefix)
            clients = detected if detected else ["workbuddy", "claude", "codex"]

    snapshots = []
    for client in dict.fromkeys(clients):
        # T-153: 自动回退 — today 无数据时试 yesterday（跨天场景）
        for try_date in ([date_name, "yesterday"] if date_name == "today" else [date_name]):
            result = run_command({"argv": [*prefix, "--json", "--date", try_date, "--client", client],
                                  "timeout_seconds": 120}, Path(project))
            if result.get("status") != "PASS":
                continue
            try:
                payload = json.loads(result.get("stdout", ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            metric = _find_metric(payload, client, identity)
            if metric is None or int(metric.get("totalTokens", 0)) == 0:
                continue
            snapshots.append({**base, "value": int(metric.get("totalTokens", 0)),
                              "status": "CUMULATIVE_SNAPSHOT", "source": f"measured:ocusage:{client}",
                              "measured_at": datetime.now(timezone.utc).isoformat(),
                              "scope": "project_daily_snapshot", "token_client": client,
                              "date": try_date, "input": int(metric.get("inputTokens", 0)),
                              "output": int(metric.get("outputTokens", 0))})
            break  # 有数据就停止回退
        # 如果 today 和 yesterday 都无数据，跳过该 client
    if len(snapshots) == 1:
        return task_delta_measurement(baseline, snapshots[0]) if baseline else snapshots[0]
    if len(snapshots) > 1:
        # 多客户端有数据时，取 totalTokens 最大的（主力工具）
        best = max(snapshots, key=lambda s: s.get("value", 0))
        best["detail"] = f"multiple clients matched ({', '.join(s['token_client'] for s in snapshots)}); using {best['token_client']}"
        return task_delta_measurement(baseline, best) if baseline else best
    base["detail"] = "ocusage returned no data for any detected client"
    return base


def collect_token_usage(project, date="today", client="codex"):
    measurement = collect_token_measurement(project, token_clients=[client], date_name=date)
    if measurement.get("status") not in {"CUMULATIVE_SNAPSHOT", "MEASURED"}:
        return {"status": "UNAVAILABLE_OPTIONAL_TOOL", "source": "unavailable",
                "total": None, "input": None, "output": None, "detail": measurement.get("detail")}
    return {"status": "MEASURED", "source": measurement["source"], "total": measurement["value"],
            "input": measurement.get("input"), "output": measurement.get("output"),
            "measurement": measurement}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("date", nargs="?", default="today")
    parser.add_argument("client", nargs="?", default="codex")
    args = parser.parse_args()
    print(json.dumps(collect_token_usage(args.project, args.date, args.client), ensure_ascii=False))


if __name__ == "__main__":
    main()
