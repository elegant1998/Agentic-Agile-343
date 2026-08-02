#!/usr/bin/env python3
"""Gate Check — SCOPE-V 强制检查门机械验证器

对应 SKILL.md v1.20 的 5 个检查门，逐条机械验证，失败则退出码 1。

用法:
    python scripts/gate_check.py --gate pre       --task T-026  # 前置门
    python scripts/gate_check.py --gate coding    --task T-026  # 编码门（TDD Red）
    python scripts/gate_check.py --gate prove     --task T-026  # 验证门（TDD Green）
    python scripts/gate_check.py --gate closing   --task T-026  # 收尾门
    python scripts/gate_check.py --gate bug       --task T-025  # Bug 回溯门

退出码: 0 = 全部通过, 1 = 有未通过项
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run(cmd, cwd=None, timeout=30):
    """运行 shell 命令，返回 (returncode, stdout, stderr)"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -2, "", str(e)


def check(label, condition, detail=""):
    icon = "✅" if condition else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def check_signed(content):
    """检查契约是否经 IO 真实签署，而非 OA 代签/自动签署。

    返回 (ok, detail)：
    - 反代签：任何"自动签署/代签/OA 代"等标记一律判失败（OA 不得代 IO 盖 SIGNED）
    - 必须有签署区（## 签署 / 签署区 / sign-off）
    - IO 署名字段必须非占位符（非 _____），且状态为 SIGNED
    """
    # 1. 反代签：强拒绝一切自动/代签标记
    # 注意：裸"代签"已从硬标记移除——用户契约可能合法出现"禁止代签"等否定语境。
    # 【v1.23.1 修复】"OA 代"等子串不得裸匹配，须排除【否定语境】：
    #   同一行若含否定词（非/禁止/不得/无/不/未/并非/not/no），说明是反代签的正向
    #   说明（如"非 OA 代签""禁止 OA 代签""不得由 OA 代"），应放行而非误报。
    NEGATION_TOKENS = ["非", "禁止", "不得", "无", "没有", "不", "未", "并非", "请勿", "not ", "no ", "never"]
    autosign_markers = [
        "自动签署", "自动签", "OA 代", "代 OA",
        "auto-sign", "auto sign", "（Grill-Me", "Grill-Me 自动",
        "自动盖章", "默认已签", "自动生效",
    ]
    for m in autosign_markers:
        idx = content.find(m)
        while idx != -1:
            # 取标记所在行，判定是否处于否定语境
            line_start = content.rfind("\n", 0, idx) + 1
            line_end = content.find("\n", idx)
            if line_end == -1:
                line_end = len(content)
            line = content[line_start:line_end]
            if any(neg in line for neg in NEGATION_TOKENS):
                # 否定语境（如"非 OA 代签"），属反代签正向说明，跳过本次匹配
                idx = content.find(m, idx + len(m))
                continue
            return False, f"检测到代签/自动签署标记「{m}」— OA 不得代 IO 签署"
            # 以下 break 不会执行（上方已 return），仅作语法安全占位
            break

    # 2. 必须有签署区
    if not re.search(r"##\s*签署|签署区|sign[- ]?off", content, re.I):
        return False, "未找到签署区（## 签署 / 签署区）"

    # 3. 找 IO 行（无论状态）：署名必须是真实填写，不得为占位符
    io_any = re.search(r"\|\s*IO[^\n|]*\|\s*([^\n|]+?)\s*\|", content)
    if io_any:
        name = io_any.group(1).strip()
        if not name or "___" in name:
            return False, "IO 署名为占位符（未填写真实署名）— 未经 IO 显式签署"
        # 有真实署名，再要求状态为 SIGNED
        if re.search(
            r"\|\s*IO[^\n|]*\|\s*[^\n|]+?\s*\|\s*[^\n|]*\s*\|\s*\*{0,2}SIGNED",
            content,
        ):
            return True, ""
        return False, "契约状态非 SIGNED（IO 未显式确认）"

    # 4. 退化判定：无 IO 表格行，仅按 SIGNED 标记通过（告警，提示补全 §7）
    if "SIGNED" in content:
        return True, "（警告：未解析到 IO 表格署名，仅按 SIGNED 标记通过，建议补全 §7 签署区）"

    return False, "契约状态非 SIGNED 或 IO 未署名"


def gate_pre(task_id, project_dir):
    """前置门: SDD 完成（契约+约束+Grill-Me+AC设计）"""
    print(f"━━━ 前置门（{task_id}）━━━")
    gov = project_dir / "governance"
    contract = gov / "contracts" / f"Intent_Contract_{task_id}.md"
    constraints = gov / "constraints.yaml"
    all_pass = True

    # 1. 契约文件存在
    all_pass &= check("意图契约已创建", contract.exists(),
                      f"找不到 {contract}")

    # 2. 契约已签署（IO 真实签署，禁止 OA 代签/自动签署）
    if contract.exists():
        content = contract.read_text()
        signed_ok, signed_detail = check_signed(content)
        all_pass &= check("契约已显式签署（IO 真实署名，非 OA 代签）",
                          signed_ok, signed_detail)
    else:
        all_pass &= check("契约已签署", False, "契约文件不存在")

    # 3. 约束矩阵存在
    all_pass &= check("约束矩阵已建立", constraints.exists(),
                      f"找不到 {constraints}")

    # 4. AC 验证方式设计（shell:grep 不超过 50%）
    if contract.exists():
        content = contract.read_text()
        ac_lines = re.findall(r'\|[^|]*\|[^|]*\|[^|]*\|', content)
        shell_count = sum(1 for l in ac_lines if 'shell:' in l.lower() or 'grep' in l.lower())
        assert_count = sum(1 for l in ac_lines if any(k in l.lower() for k in ['assert:', 'http:', 'db:']))
        total = shell_count + assert_count
        if total > 0:
            shell_ratio = shell_count / total
            all_pass &= check(f"AC 验证方式合理（shell:grep {shell_count}/{total} = {shell_ratio:.0%}）",
                              shell_ratio <= 0.5,
                              f"shell:grep 占比 {shell_ratio:.0%}，超过 50% 限制")
        else:
            all_pass &= check("AC 验证方式已设计", False, "未找到 AC 表格或验证方式标注")
    else:
        all_pass &= check("AC 验证方式已设计", False, "契约不存在")

    return all_pass


def gate_coding(task_id, project_dir):
    """编码门: TDD Red（测试已先写且运行失败）"""
    print(f"━━━ 编码门（{task_id}）━━━")
    all_pass = True

    # 1. 测试文件存在
    test_files = []
    for pattern in ["**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts",
                    "**/test_*.py", "**/*_test.py"]:
        test_files.extend(project_dir.glob(pattern))
    test_files = [f for f in test_files if "node_modules" not in str(f) and "__pycache__" not in str(f)]

    all_pass &= check(f"测试文件已创建（{len(test_files)} 个）",
                      len(test_files) > 0,
                      "未找到任何测试文件 — TDD Red 要求先写测试")

    # 2. 测试运行（检查是否有 RED 测试 = 测试存在但实现未完成）
    if test_files:
        pkg = project_dir / "package.json"
        if pkg.exists():
            rc, out, err = run("npx vitest run --reporter=json 2>/dev/null || true",
                               cwd=str(project_dir), timeout=60)
            try:
                data = json.loads(out)
                total = data.get("numTotalTests", 0)
                failed = data.get("numFailedTests", 0)
                passed = data.get("numPassedTests", 0)
                if total == 0:
                    all_pass &= check("测试运行确认 RED", False, "测试文件存在但无测试用例")
                elif failed > 0:
                    all_pass &= check(f"测试运行确认 RED（{failed}/{total} 失败）", True)
                elif passed > 0 and total > 0:
                    # 全绿可能意味着实现已写完（Green 阶段），编码门应该在此前通过
                    print(f"  ⚠️ 测试已全绿（{passed}/{total}）— 可能已跳过 Red 阶段直接到 Green")
                    all_pass &= check("测试运行确认 RED", False, "测试已全绿，Red 阶段可能已跳过")
            except json.JSONDecodeError:
                all_pass &= check("测试运行确认 RED", False, "无法解析 vitest 输出")
        else:
            # Python 项目
            rc, out, err = run("python3 -m pytest --tb=no -q 2>/dev/null || true",
                               cwd=str(project_dir), timeout=60)
            all_pass &= check("测试运行", "error" in out.lower() or "failed" in out.lower() or "no tests" in out.lower(),
                              "需要人工确认测试处于 RED 状态")

    return all_pass


def gate_prove(task_id, project_dir):
    """验证门: TDD Green（测试全通过 + AC 验证 + test-total > 0）"""
    print(f"━━━ 验证门（{task_id}）━━━")
    all_pass = True

    # 1. 测试运行全绿
    pkg = project_dir / "package.json"
    test_total = 0
    test_passed = 0
    if pkg.exists():
        rc, out, err = run("npx vitest run --reporter=json 2>/dev/null || true",
                           cwd=str(project_dir), timeout=120)
        try:
            data = json.loads(out)
            test_total = data.get("numTotalTests", 0)
            test_passed = data.get("numPassedTests", 0)
            test_failed = data.get("numFailedTests", 0)
            all_pass &= check(f"测试全部通过（{test_passed}/{test_total}）",
                              test_failed == 0 and test_passed > 0,
                              f"{test_failed} 个测试失败")
        except json.JSONDecodeError:
            all_pass &= check("测试运行", False, "无法解析 vitest 输出")
    else:
        all_pass &= check("测试运行", False, "未找到 package.json 或 pytest")

    # 2. test-total > 0
    all_pass &= check(f"test-total > 0（当前 {test_total}）", test_total > 0,
                      "测试套件为空 — TDD 未执行")

    # 3. AC 逐条验证（检查证据包是否含 AC 结果表）
    gov = project_dir / "governance"
    evidence = gov / "evidence" / f"EB-{task_id}.md"
    if evidence.exists():
        content = evidence.read_text()
        has_ac_table = "AC" in content and ("PASS" in content or "FAIL" in content)
        all_pass &= check("AC 逐条验证有记录", has_ac_table,
                          "证据包中未找到 AC 验证结果表")
    else:
        all_pass &= check("AC 逐条验证", False, f"证据包 {evidence} 不存在")

    # 4. tsc / build 通过
    if pkg.exists():
        rc, out, err = run("npx tsc --noEmit 2>&1 | head -1", cwd=str(project_dir), timeout=60)
        all_pass &= check("TypeScript 编译通过", rc == 0,
                          out[:80] if out else "有类型错误")

    return all_pass


def gate_closing(task_id, project_dir):
    """收尾门: 证据 + 遥测 + 图谱回写"""
    print(f"━━━ 收尾门（{task_id}）━━━")
    gov = project_dir / "governance"
    all_pass = True

    # 1. 证据包存在
    evidence = gov / "evidence" / f"EB-{task_id}.md"
    all_pass &= check("证据包已生成", evidence.exists(),
                      f"找不到 {evidence}")

    # 2. 单任务遥测文件存在
    tel_file = gov / "telemetry" / "runs" / f"telemetry-{task_id}.json"
    all_pass &= check("单任务遥测文件存在", tel_file.exists(),
                      f"找不到 {tel_file}")

    # 3. telemetry.json 的 run_count 包含本任务
    proj_tel = gov / "telemetry.json"
    if proj_tel.exists():
        try:
            data = json.loads(proj_tel.read_text())
            runs = data.get("runs", [])
            task_in_runs = any(r.get("task_id") == task_id for r in runs)
            all_pass &= check(f"telemetry.json runs 含 {task_id}（共 {len(runs)} 条）",
                              task_in_runs, "本任务不在 runs 数组中")
        except Exception:
            all_pass &= check("telemetry.json 解析", False, "JSON 格式错误")
    else:
        all_pass &= check("telemetry.json 存在", False, "文件不存在")

    # 4. dashboard.html 修改时间在 1 小时内
    dashboard = gov / "dashboard.html"
    if dashboard.exists():
        mtime = datetime.fromtimestamp(dashboard.stat().st_mtime)
        age = (datetime.now() - mtime).total_seconds()
        all_pass &= check(f"dashboard.html 已更新（{int(age/60)} 分钟前）",
                          age < 3600, "dashboard 超过 1 小时未更新")
    else:
        all_pass &= check("dashboard.html 存在", False, "文件不存在")

    # 5. 意图图谱已回写（检查文件是否包含本任务 ID）
    graph = gov / "Intent_Graph.md"
    if graph.exists():
        content = graph.read_text()
        has_task = task_id in content
        all_pass &= check(f"意图图谱含 {task_id}", has_task,
                          "图谱中未找到本任务 ID")
    else:
        all_pass &= check("意图图谱存在", False, "文件不存在")

    return all_pass


def gate_bug(task_id, project_dir):
    """Bug 回溯门: 归因 + 遥测修正 + 证据追加 + 图谱回写"""
    print(f"━━━ Bug 回溯门（{task_id}）━━━")
    gov = project_dir / "governance"
    all_pass = True

    # 1. 证据包含"事后 bug 记录"
    evidence = gov / "evidence" / f"EB-{task_id}.md"
    if evidence.exists():
        content = evidence.read_text()
        has_bug = "bug" in content.lower() and ("事后" in content or "回溯" in content)
        all_pass &= check("证据包含事后 bug 记录", has_bug,
                          "证据包中未找到 bug 回溯记录")
    else:
        all_pass &= check("证据包存在", False, "文件不存在")

    # 2. 遥测 first_pass=0（被修正过）
    tel_file = gov / "telemetry" / "runs" / f"telemetry-{task_id}.json"
    if tel_file.exists():
        try:
            data = json.loads(tel_file.read_text())
            first_pass = data.get("value", {}).get("first_pass_rate", {})
            fp_value = first_pass.get("value", 1.0)
            all_pass &= check(f"遥测 first_pass 已修正（{fp_value}）",
                              fp_value == 0, "first_pass_rate 仍为 1.0 — 未修正")
        except Exception:
            all_pass &= check("遥测文件解析", False, "JSON 格式错误")
    else:
        all_pass &= check("遥测文件存在", False, "文件不存在")

    # 3. 意图图谱含 bug 教训
    graph = gov / "Intent_Graph.md"
    if graph.exists():
        content = graph.read_text()
        has_lesson = task_id in content and ("bug" in content.lower() or "教训" in content)
        all_pass &= check(f"图谱含 {task_id} bug 教训", has_lesson,
                          "图谱中未找到 bug 教训")
    else:
        all_pass &= check("图谱存在", False, "文件不存在")

    return all_pass


GATES = {
    "pre": ("前置门", gate_pre),
    "coding": ("编码门", gate_coding),
    "prove": ("验证门", gate_prove),
    "closing": ("收尾门", gate_closing),
    "bug": ("Bug 回溯门", gate_bug),
}


def main():
    parser = argparse.ArgumentParser(description="SCOPE-V 强制检查门机械验证器")
    parser.add_argument("--gate", required=True, choices=list(GATES.keys()),
                        help="检查门: pre(前置) coding(编码) prove(验证) closing(收尾) bug(回溯)")
    parser.add_argument("--task", required=True, help="任务 ID，如 T-026")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    gate_name, gate_func = GATES[args.gate]

    print(f"\n{'='*50}")
    print(f"  Gate Check — {gate_name}")
    print(f"  任务: {args.task}  项目: {project_dir.name}")
    print(f"{'='*50}\n")

    all_pass = gate_func(args.task, project_dir)

    print(f"\n{'─'*50}")
    if all_pass:
        print(f"✅ {gate_name} 全部通过 — 可进入下一阶段")
        sys.exit(0)
    else:
        print(f"❌ {gate_name} 有未通过项 — 必须补齐后才能继续")
        sys.exit(1)


if __name__ == "__main__":
    main()
