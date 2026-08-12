#!/usr/bin/env python3
"""Agentic Agile 3-4-3 统一 CLI dispatcher.

提供单一入口点路由到各治理脚本，避免 16 个独立入口的记忆负担。

用法:
    python scripts/cli.py <subcommand> [args...]

示例:
    python scripts/cli.py check --all              # harness check
    python scripts/cli.py collect --project myapp  # collect_telemetry
    python scripts/cli.py verify --task T-003      # verify_contract
    python scripts/cli.py audit                    # audit_evidence
    python scripts/cli.py dashboard                # 生成仪表板
    python scripts/cli.py graph plan               # graph_engine plan
    python scripts/cli.py reflect --task T-003     # reflect
    python scripts/cli.py list                     # 列出所有子命令
"""
import sys
import os
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

# 子命令 → (脚本文件, 说明)
COMMANDS = {
    # ── Harness 引擎 ──
    "check":      ("harness.py", "约束检查（harness check --all）"),
    "tests":      ("harness.py", "运行测试套件（harness tests）"),
    "nfr-list":   ("harness.py", "列出可用 NFR 验证器"),
    "recover":    ("harness.py", "自动恢复失败的约束"),

    # ── 遥测与仪表板 ──
    "collect":    ("collect_telemetry.py", "收集遥测数据"),
    "merge":      ("collect_telemetry.py", "合并多模块遥测（--merge）"),
    "dashboard":  ("collect_telemetry.py", "生成/刷新仪表板（--rebuild）"),
    "telemetry-track": ("telemetry_tracker.py", "追加执行事件或查看可信 P0 度量"),
    "telemetry-run": ("telemetry_workflow.py", "跨平台运行遥测主流程"),

    # ── 验证体系 ──
    "verify":     ("verify_contract.py", "契约 AC 验证"),
    "audit":      ("audit_evidence.py", "证据包完整性审计"),
    "triangulate":("verify_triangulation.py", "三方一致性验证"),
    "rollback":   ("verify_rollback_safety.py", "回滚安全性验证"),
    "verification": ("verification_plan.py", "风险驱动多层验证计划与独立证据检查"),
    "evidence":     ("evidence_workflow.py", "Evidence 完成后调用遥测工作流并生成双 Dashboard（指标由 tracker 派生）"),
    "release":      ("release_manifest.py", "单项目携证发布计划、就绪检查与事实记录"),
    "freshness":  ("verify_freshness.py", "工件时效检测"),
    "cross-module":("verify_cross_module.py", "跨模块接口契约验证"),

    # ── 上下文工程 ──
    "discover":   ("discover_context.py", "代码上下文发现"),
    "crop":       ("crop_context.py", "上下文裁剪"),

    # ── LOOP & Graph ──
    "reflect":    ("reflect.py", "生成反思 + 反哺图谱"),
    "consistency":("self_consistency_check.py", "LOOP-1 自洽性检查"),
    "graph":      ("graph_engine.py", "DAG 图谱引擎"),

    # ── 证据聚合 ──
    "aggregate":  ("aggregate_evidence.py", "多模块证据包聚合"),

    # ── 工具审计 ──
    "audit-tools":("audit_tools.py", "工具调用合规性审计"),

    # ── 既有项目 Recon 与风险裁剪 ──
    "recon":      ("recon.py", "既有项目轻量 Recon（默认只读）"),
    "envelope":   ("change_envelope.py", "Change Envelope 实际变更机械门禁"),
    "characterize": ("characterize.py", "既有行为特征基线 plan/capture/verify"),
    "change":      ("change_workflow.py", "既有代码安全变更统一状态入口"),
    "bug":         ("bug_workflow.py", "Bug 分类、复现、验证与回溯入口"),
    "assess-risk":("assess_risk.py", "风险评估与治理模式推荐"),
    "init":       ("init_governance.py", "风险驱动治理入口（默认 dry-run）"),
    "maintain":   ("maintenance.py", "门禁自身治理与低风险维护通道"),
}

# 需要将子命令作为第一个参数传递给目标脚本的命令
# 例如: harness.py check --all → cli.py check --all
#       graph_engine.py plan → cli.py graph plan
SUBCOMMAND_MAP = {
    "check":    "check",
    "tests":    "tests",
    "nfr-list": "nfr-list",
    "recover":  "recover",
    "merge":    "--merge",
    "dashboard":"--rebuild",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "list", "help"):
        print("Agentic Agile 3-4-3 统一 CLI\n")
        print("用法: python scripts/cli.py <subcommand> [args...]\n")
        print("可用子命令:")
        for cmd, (script, desc) in sorted(COMMANDS.items()):
            print(f"  {cmd:16s} {desc}")
        print(f"\n共 {len(COMMANDS)} 个子命令")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"错误: 未知子命令 '{cmd}'。运行 'python scripts/cli.py list' 查看可用命令。", file=sys.stderr)
        sys.exit(1)

    script_name, desc = COMMANDS[cmd]
    extra_args = sys.argv[2:]
    if cmd == "recon" and extra_args[:1] == ["task"]:
        script_name = "task_recon.py"
        extra_args = extra_args[1:]
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"错误: 脚本不存在: {script_path}", file=sys.stderr)
        sys.exit(1)

    # 构建命令
    subcmd = SUBCOMMAND_MAP.get(cmd)
    if subcmd:
        # 对于需要子命令的脚本（如 harness.py check），插入子命令
        py_args = [sys.executable, str(script_path), subcmd] + extra_args
    else:
        py_args = [sys.executable, str(script_path)] + extra_args

    # 转发执行
    result = subprocess.run(py_args, cwd=str(Path.cwd()))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
