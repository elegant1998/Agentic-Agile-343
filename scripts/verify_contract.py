#!/usr/bin/env python3
"""Contract Compliance Verifier — 契约一致性验证器

读取 YAML 契约的 ac（验收标准）字段，逐条执行可验证断言，
输出 PASS/FAIL 矩阵。支持四种验证类型：

  - shell:   执行 shell 命令，退出码 0 = 通过
  - http:    发起 HTTP 请求，检查状态码/响应体
  - db:      执行数据库查询，检查返回行数/值
  - predicate: 运行无副作用的 AST 白名单谓词，True = 通过

用法:
    # 验证单个契约
    python scripts/verify_contract.py --task T-003

    # 验证所有契约
    python scripts/verify_contract.py --all

    # JSON 输出
    python scripts/verify_contract.py --task T-003 --format json

    # TDD Red 阶段：从 AC 自动生成测试骨架
    python scripts/verify_contract.py --task T-003 --generate-tests

契约 ac 字段格式:
    ac:
      - id: "AC-01"
        desc: "用户可查询自己的积分余额"
        verify:
          type: http
          method: GET
          url: "http://localhost:8000/api/member/points"
          headers:
            Authorization: "Bearer {{token}}"
          expect:
            status: 200
            body_contains: "points"

      - id: "AC-02"
        desc: "积分表包含 user_id 字段"
        verify:
          type: shell
          command: "grep -q 'user_id' src/models/point.py"

      - id: "AC-03"
        desc: "治理目录存在"
        verify:
          type: predicate
          expression: "is_dir('governance')"

      - id: "AC-04"
        desc: "数据库中有初始会员等级配置"
        verify:
          type: db
          engine: "sqlite:///test.db"
          query: "SELECT COUNT(*) FROM member_levels"
          expect:
            min_rows: 1

退出码: 0 = 全部 AC 通过, 1 = 存在失败
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from textwrap import dedent
from command_runner import run_command, run_shell
from safe_predicate import run_predicate

try:
    import yaml
except ImportError:
    from _bootstrap import ensure_yaml_available
    ensure_yaml_available()
    import yaml


# ─── 验证执行器 ───────────────────────────────────────────

def verify_shell(command: str, project_dir: Path, timeout: int = 30, dialect: str = None) -> tuple[bool, str]:
    """执行 shell 命令验证"""
    if not dialect:
        return False, "Shell AC 必须显式声明方言（posix/powershell/cmd）"
    result = run_shell({"dialect": dialect, "script": command,
                        "timeout_seconds": timeout}, project_dir)
    detail = result.get("stdout") or result.get("stderr") or result.get("detail") or result["status"]
    return result["status"] == "PASS", detail[:300]


def verify_command(command: dict, project_dir: Path) -> tuple[bool, str]:
    result = run_command(command, project_dir)
    detail = result.get("stdout") or result.get("stderr") or result.get("detail") or result["status"]
    return result["status"] == "PASS", detail[:300]


def verify_http(method: str, url: str, headers: dict, expect: dict,
                timeout: int = 10) -> tuple[bool, str]:
    """发起 HTTP 请求验证"""
    try:
        data = None
        body = expect.get("body")
        if body:
            data = json.dumps(body).encode() if isinstance(body, dict) else str(body).encode()

        req = urllib.request.Request(url, data=data, method=method.upper())
        for k, v in (headers or {}).items():
            req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            resp_body = resp.read().decode(errors="replace")

        failures = []
        if "status" in expect and status != expect["status"]:
            failures.append(f"期望状态 {expect['status']}, 实际 {status}")
        if "body_contains" in expect and expect["body_contains"] not in resp_body:
            failures.append(f"响应体不包含 '{expect['body_contains']}'")
        if "body_regex" in expect and not re.search(expect["body_regex"], resp_body):
            failures.append(f"响应体不匹配正则 '{expect['body_regex']}'")

        if failures:
            return False, "; ".join(failures)
        return True, f"HTTP {status}"
    except urllib.error.HTTPError as e:
        if "status" in expect and e.code == expect["status"]:
            return True, f"HTTP {e.code}（符合预期）"
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)


def verify_db(engine: str, query: str, expect: dict) -> tuple[bool, str]:
    """执行数据库查询验证"""
    conn = None
    cursor = None
    try:
        # 动态导入，避免强制依赖
        if "sqlite" in engine:
            import sqlite3
            db_path = engine.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
        elif "postgresql" in engine or "postgres" in engine:
            # 尝试 psycopg2
            try:
                import psycopg2
            except ImportError:
                return False, "需要安装 psycopg2: pip install psycopg2-binary"
            conn = psycopg2.connect(engine)
        else:
            return False, f"不支持的数据库引擎: {engine}"

        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        row_count = len(rows)
        failures = []
        if "min_rows" in expect and row_count < expect["min_rows"]:
            failures.append(f"期望 ≥{expect['min_rows']} 行, 实际 {row_count}")
        if "max_rows" in expect and row_count > expect["max_rows"]:
            failures.append(f"期望 ≤{expect['max_rows']} 行, 实际 {row_count}")
        if "exact_rows" in expect and row_count != expect["exact_rows"]:
            failures.append(f"期望 {expect['exact_rows']} 行, 实际 {row_count}")
        if "value" in expect:
            if not rows:
                failures.append(f"期望值 {expect['value']}, 但查询返回 0 行")
            else:
                actual = rows[0][0]
                expected = expect["value"]
                if actual != expected:
                    failures.append(f"期望值 {expected}, 实际 {actual}")

        if failures:
            return False, "; ".join(failures)
        return True, f"查询返回 {row_count} 行"
    except Exception as e:
        return False, str(e)
    finally:
        for resource in (cursor, conn):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass


def verify_assert(expression: str, setup: str = "") -> tuple[bool, str]:
    """Legacy arbitrary Python assertions are blocked by default."""
    return False, "UNSAFE_LEGACY_CHECK: assert/setup is blocked; migrate to predicate or command"


def verify_predicate(expression: str, project_dir: Path) -> tuple[bool, str]:
    return run_predicate(expression, project_dir)


# ─── TDD: AC → 测试骨架生成 ───────────────────────────────

def _detect_project_language(project_dir: Path) -> str:
    """检测项目主语言，返回 python/node/go/rust/java/dotnet 之一"""
    if (project_dir / "go.mod").exists():
        return "go"
    if (project_dir / "Cargo.toml").exists():
        return "rust"
    if (project_dir / "pom.xml").exists():
        return "java"
    if list(project_dir.glob("*.csproj")) or list(project_dir.glob("*.sln")):
        return "dotnet"
    if (project_dir / "package.json").exists():
        return "node"
    return "python"  # 默认


def generate_tests(contract_path: Path, project_dir: Path) -> str:
    """从契约 AC 自动生成测试骨架（Red 阶段）

    根据项目主语言生成对应框架的测试骨架：
    - Python → pytest
    - Node/TS → vitest
    - Go → go test
    - Rust → cargo test (#[test])
    - Java → JUnit 5
    - C# → xUnit

    生成策略（Python 示例）：
    - shell AC  → def test_ac_N_*(): subprocess.run(...)
    - http AC   → def test_ac_N_*(): TestClient.get/post(...)
    - db AC     → def test_ac_N_*(): db_session.execute(...)
    - assert AC → def test_ac_N_*(): import + call function
    """
    with open(contract_path) as f:
        contract = yaml.safe_load(f)

    task_id = extract_task_id(contract_path)
    ac_list = contract.get("ac", [])
    domain = contract.get("domain", task_id.lower().replace('-', '_'))
    lang = _detect_project_language(project_dir)

    if not ac_list:
        return "# 契约中未定义 AC，无法生成测试骨架\n"

    # 按语言分发
    if lang == "go":
        return _generate_go_tests(task_id, domain, ac_list)
    if lang == "rust":
        return _generate_rust_tests(task_id, domain, ac_list)
    if lang == "java":
        return _generate_java_tests(task_id, domain, ac_list)
    if lang == "dotnet":
        return _generate_dotnet_tests(task_id, domain, ac_list)
    if lang == "node":
        return _generate_node_tests(task_id, domain, ac_list)
    return _generate_python_tests(task_id, domain, ac_list, contract, contract_path)


def _generate_python_tests(task_id, domain, ac_list, contract, contract_path):
    """Python/pytest 测试骨架（原有逻辑）"""
    tdd_flow = contract.get("tdd_flow", {})
    test_file_name = tdd_flow.get("red", {}).get("test_file", f"tests/test_{domain}.py")

    if not ac_list:
        return "# 契约中未定义 AC，无法生成测试骨架\n"

    lines = [
        f'"""TDD Red 阶段 — {task_id} 测试骨架',
        f'',
        f'从契约 AC 自动生成（verify_contract.py --generate-tests）',
        f'运行: python3 -m pytest {test_file_name} -v',
        f'预期: 全部 FAIL（证明测试可捕获缺陷）',
        f'"""',
        f'',
        f'import pytest',
        f'from fastapi.testclient import TestClient',
    ]

    # 检测需要的 import
    needs_db = any(ac.get("verify", {}).get("type") == "db" for ac in ac_list)
    needs_http = any(ac.get("verify", {}).get("type") == "http" for ac in ac_list)
    needs_shell = any(ac.get("verify", {}).get("type") in {"shell", "command"} for ac in ac_list)
    needs_path = needs_shell or any(ac.get("verify", {}).get("type") == "predicate" for ac in ac_list)

    if needs_db:
        lines.append('from sqlalchemy import create_engine, text')
    if needs_http:
        lines.append(f'from src.main import app  # 根据实际项目调整')
    if needs_path:
        lines.append('from pathlib import Path')
    if needs_shell:
        lines.append('from command_runner import run_command, run_shell')

    lines.extend([
        '',
        '',
        f'# ═══════════════════════════════════════════════',
        f'# {task_id}: {domain}',
        f'# AC 数量: {len(ac_list)}',
        f'# ═══════════════════════════════════════════════',
        '',
    ])

    # Fixture
    if needs_http:
        lines.extend([
            '',
            '@pytest.fixture',
            'def client():',
            '    """测试客户端 fixture"""',
            '    return TestClient(app)',
            '',
        ])

    if needs_db:
        lines.extend([
            '@pytest.fixture',
            'def db_session():',
            '    """数据库会话 fixture（使用测试库）"""',
            '    engine = create_engine("sqlite:///test.db")',
            '    with engine.connect() as conn:',
            '        yield conn',
            '',
        ])

    # 为每个 AC 生成测试函数
    for ac in ac_list:
        ac_id = ac.get("id", "AC-??").replace("-", "_").replace(".", "_")
        ac_desc = ac.get("desc", "验证验收标准")
        verify_cfg = ac.get("verify", {})
        vtype = verify_cfg.get("type", "shell")

        lines.append(f'')
        lines.append(f'def test_{ac_id.lower()}():')
        lines.append(f'    """{ac_desc}"""')

        if vtype == "http":
            method = verify_cfg.get("method", "GET").lower()
            url = verify_cfg.get("url", "/")
            expect_status = verify_cfg.get("expect", {}).get("status", 200)
            expect_contains = verify_cfg.get("expect", {}).get("body_contains", "")

            lines.append(f'    response = client.{method}("{url}")')
            lines.append(f'    assert response.status_code == {expect_status}')
            if expect_contains:
                lines.append(f'    assert "{expect_contains}" in response.text')

        elif vtype == "db":
            query = verify_cfg.get("query", "SELECT 1")
            expect_min = verify_cfg.get("expect", {}).get("min_rows")
            expect_exact = verify_cfg.get("expect", {}).get("exact_rows")

            lines.append(f'    result = db_session.execute(text("""{query}"""))')
            lines.append(f'    rows = result.fetchall()')
            if expect_min is not None:
                lines.append(f'    assert len(rows) >= {expect_min}, f"期望 ≥{expect_min} 行，实际 {{len(rows)}}"')
            if expect_exact is not None:
                lines.append(f'    assert len(rows) == {expect_exact}')

        elif vtype == "shell":
            command = verify_cfg.get("command", "true")
            dialect = verify_cfg.get("dialect")
            lines.append(f'    result = run_shell({{"dialect": {dialect!r}, "script": {command!r}}}, Path.cwd())')
            lines.append(f'    assert result["status"] == "PASS", result')

        elif vtype == "command":
            command = verify_cfg.get("command", {})
            lines.append(f'    result = run_command({command!r}, Path.cwd())')
            lines.append(f'    assert result["status"] == "PASS", result')

        elif vtype == "predicate":
            expression = verify_cfg.get("expression", "False")
            lines.append('    from safe_predicate import evaluate_predicate')
            lines.append(f'    assert evaluate_predicate({expression!r}, Path.cwd()), "安全谓词失败"')
        elif vtype == "assert":
            lines.append('    pytest.fail("UNSAFE_LEGACY_CHECK: migrate assert/setup to predicate or command")')

        else:
            lines.append(f'    # TODO: 未知验证类型 {vtype}，请手动编写')
            lines.append(f'    pytest.skip("验证类型 {vtype} 暂不支持自动生成")')

    # TDD 提示
    lines.extend([
        '',
        '',
        '# ═══════════════════════════════════════════════',
        '# TDD Red-Green-Refactor 流程',
        '# ═══════════════════════════════════════════════',
        '#',
        '# 🔴 Red:   python3 -m pytest ' + test_file_name + ' -v  → 全部 FAIL',
        '# 🟢 Green: 编写 src/ 下的最小实现，使测试通过',
        '# 🔵 Refactor: python3 scripts/reflect.py --task ' + task_id + ' --feedback-to-graph',
        '#',
        '# ⚡ 快速运行:',
        '#    python3 -m pytest ' + test_file_name + ' -v --tb=short',
        '#    python3 -m pytest ' + test_file_name + ' --cov=src --cov-report=term',
    ])

    return '\n'.join(lines)


# ── 多语言测试骨架生成器 ──────────────────────────────────

def _generate_node_tests(task_id, domain, ac_list):
    """Node/TS (vitest) 测试骨架"""
    lines = [
        f"// TDD Red 阶段 — {task_id} 测试骨架 (vitest)",
        f"// 从契约 AC 自动生成（verify_contract.py --generate-tests）",
        f"// 运行: npx vitest run --reporter=verbose",
        f"// 预期: 全部 FAIL（证明测试可捕获缺陷）",
        f"",
        f"import {{ describe, it, expect }} from 'vitest';",
        f"",
        f"describe('{task_id}: {domain}', () => {{",
    ]
    for ac in ac_list:
        ac_id = ac.get("id", "AC-??")
        ac_desc = ac.get("desc", "验证验收标准")
        lines.append(f"  it('{ac_id}: {ac_desc}', () => {{")
        lines.append(f"    // TODO: 实现验证逻辑")
        lines.append(f"    expect(true).toBe(false); // Red: 必须失败")
        lines.append(f"  }});")
    lines.extend([
        f"}});",
        f"",
        f"// ═══ TDD Red-Green-Refactor ═══",
        f"// 🔴 Red:   npx vitest run --reporter=verbose  → 全部 FAIL",
        f"// 🟢 Green: 编写 src/ 下的最小实现，使测试通过",
        f"// 🔵 Refactor: python3 scripts/reflect.py --task {task_id} --feedback-to-graph",
    ])
    return '\n'.join(lines)


def _generate_go_tests(task_id, domain, ac_list):
    """Go 测试骨架"""
    lines = [
        f"// TDD Red 阶段 — {task_id} 测试骨架 (go test)",
        f"// 从契约 AC 自动生成（verify_contract.py --generate-tests）",
        f"// 运行: go test -v ./...",
        f"// 预期: 全部 FAIL（证明测试可捕获缺陷）",
        f"",
        f"package {domain}_test",
        f"",
        f"import (",
        f"\t\"testing\"",
        f")",
        f"",
    ]
    for ac in ac_list:
        ac_id = ac.get("id", "AC-??").replace("-", "").replace(".", "")
        ac_desc = ac.get("desc", "验证验收标准")
        lines.append(f"func Test{ac_id}(t *testing.T) {{")
        lines.append(f"\t// {ac_desc}")
        lines.append(f"\t// TODO: 实现验证逻辑")
        lines.append(f"\tt.Errorf(\"Not implemented: {ac_id}\") // Red: 必须失败")
        lines.append(f"}}")
        lines.append("")
    lines.extend([
        f"// ═══ TDD Red-Green-Refactor ═══",
        f"// 🔴 Red:   go test -v ./...  → 全部 FAIL",
        f"// 🟢 Green: 编写 src/ 下的最小实现，使测试通过",
        f"// 🔵 Refactor: python3 scripts/reflect.py --task {task_id} --feedback-to-graph",
    ])
    return '\n'.join(lines)


def _generate_rust_tests(task_id, domain, ac_list):
    """Rust (cargo test) 测试骨架"""
    lines = [
        f"// TDD Red 阶段 — {task_id} 测试骨架 (cargo test)",
        f"// 从契约 AC 自动生成（verify_contract.py --generate-tests）",
        f"// 运行: cargo test",
        f"// 预期: 全部 FAIL（证明测试可捕获缺陷）",
        f"",
        f"#[cfg(test)]",
        f"mod tests {{",
        f"    use super::*;",
        f"",
    ]
    for ac in ac_list:
        ac_id = ac.get("id", "AC-??").replace("-", "_").replace(".", "_").lower()
        ac_desc = ac.get("desc", "验证验收标准")
        lines.append(f"    #[test]")
        lines.append(f"    fn test_{ac_id}() {{")
        lines.append(f"        // {ac_desc}")
        lines.append(f"        // TODO: 实现验证逻辑")
        lines.append(f"        panic!(\"Not implemented: {ac_id}\"); // Red: 必须失败")
        lines.append(f"    }}")
        lines.append(f"")
    lines.extend([
        f"    // ═══ TDD Red-Green-Refactor ═══",
        f"    // 🔴 Red:   cargo test  → 全部 FAIL",
        f"    // 🟢 Green: 编写 src/ 下的最小实现，使测试通过",
        f"    // 🔵 Refactor: python3 scripts/reflect.py --task {task_id} --feedback-to-graph",
        f"}}",
    ])
    return '\n'.join(lines)


def _generate_java_tests(task_id, domain, ac_list):
    """Java (JUnit 5) 测试骨架"""
    class_name = domain.title().replace("_", "") + "Test"
    lines = [
        f"// TDD Red 阶段 — {task_id} 测试骨架 (JUnit 5)",
        f"// 从契约 AC 自动生成（verify_contract.py --generate-tests）",
        f"// 运行: mvn test",
        f"// 预期: 全部 FAIL（证明测试可捕获缺陷）",
        f"",
        f"import org.junit.jupiter.api.Test;",
        f"import static org.junit.jupiter.api.Assertions.*;",
        f"",
        f"public class {class_name} {{",
        f"",
    ]
    for ac in ac_list:
        ac_id = ac.get("id", "AC-??").replace("-", "").replace(".", "")
        ac_desc = ac.get("desc", "验证验收标准")
        lines.append(f"    @Test")
        lines.append(f"    void test{ac_id}() {{")
        lines.append(f"        // {ac_desc}")
        lines.append(f"        // TODO: 实现验证逻辑")
        lines.append(f"        fail(\"Not implemented: {ac_id}\"); // Red: 必须失败")
        lines.append(f"    }}")
        lines.append(f"")
    lines.extend([
        f"    // ═══ TDD Red-Green-Refactor ═══",
        f"    // 🔴 Red:   mvn test  → 全部 FAIL",
        f"    // 🟢 Green: 编写 src/ 下的最小实现，使测试通过",
        f"    // 🔵 Refactor: python3 scripts/reflect.py --task {task_id} --feedback-to-graph",
        f"}}",
    ])
    return '\n'.join(lines)


def _generate_dotnet_tests(task_id, domain, ac_list):
    """C# (xUnit) 测试骨架"""
    class_name = domain.title().replace("_", "") + "Test"
    namespace = domain.title().replace("_", "") + "Tests"
    lines = [
        f"// TDD Red 阶段 — {task_id} 测试骨架 (xUnit)",
        f"// 从契约 AC 自动生成（verify_contract.py --generate-tests）",
        f"// 运行: dotnet test",
        f"// 预期: 全部 FAIL（证明测试可捕获缺陷）",
        f"",
        f"using Xunit;",
        f"",
        f"namespace {namespace}",
        f"{{",
        f"    public class {class_name}",
        f"    {{",
    ]
    for ac in ac_list:
        ac_id = ac.get("id", "AC-??").replace("-", "").replace(".", "")
        ac_desc = ac.get("desc", "验证验收标准")
        lines.append(f"        [Fact]")
        lines.append(f"        public void Test{ac_id}()")
        lines.append(f"        {{")
        lines.append(f"            // {ac_desc}")
        lines.append(f"            // TODO: 实现验证逻辑")
        lines.append(f"            Assert.Fail(\"Not implemented: {ac_id}\"); // Red: 必须失败")
        lines.append(f"        }}")
        lines.append(f"")
    lines.extend([
        f"        // ═══ TDD Red-Green-Refactor ═══",
        f"        // 🔴 Red:   dotnet test  → 全部 FAIL",
        f"        // 🟢 Green: 编写 src/ 下的最小实现，使测试通过",
        f"        // 🔵 Refactor: python3 scripts/reflect.py --task {task_id} --feedback-to-graph",
        f"    }}",
        f"}}",
    ])
    return '\n'.join(lines)


def write_generated_tests(contract_path: Path, project_dir: Path):
    """生成测试文件并写入磁盘"""
    with open(contract_path) as f:
        contract = yaml.safe_load(f)

    tdd_flow = contract.get("tdd_flow", {})
    domain = contract.get("domain", extract_task_id(contract_path).lower().replace('-', '_'))
    # 按语言选择测试文件扩展名
    lang = _detect_project_language(project_dir)
    ext_map = {"python": ".py", "node": ".test.ts", "go": "_test.go",
               "rust": ".rs", "java": "Test.java", "dotnet": "Test.cs"}
    ext = ext_map.get(lang, ".py")
    test_file_name = tdd_flow.get("red", {}).get("test_file", f"tests/test_{domain}{ext}")
    test_path = project_dir / test_file_name

    content = generate_tests(contract_path, project_dir)

    # 确保 tests 目录存在
    test_path.parent.mkdir(parents=True, exist_ok=True)

    # 如果文件已存在，追加而非覆盖（保护已有测试）
    if test_path.exists():
        existing = test_path.read_text()
        # 简单策略：如果已有 TDD 标记则替换，否则追加
        if "TDD Red 阶段" in existing:
            test_path.write_text(content)
            print(f"🔄 已更新测试骨架: {test_path}")
        else:
            print(f"⚠️ {test_path} 已存在且非自动生成，跳过覆盖")
            print(f"   生成的测试骨架已输出到 stdout，可手动合并")
            print()
            print(content)
            return
    else:
        test_path.write_text(content)

    print(f"🔴 TDD Red 阶段: 测试骨架已生成 → {test_path}")
    print(f"   运行: python3 -m pytest {test_path} -v")
    print(f"   预期: 全部 FAIL（证明测试可捕获缺陷）")
    print(f"   下一步: 编写 src/ 下的最小实现 → Green 阶段")


# ─── 主流程 ───────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent))
from gov_common import (
    ContractConflictError,
    extract_task_id as _gc_extract_task_id,
    find_contract as _gc_find_contract,
    find_contracts as _gc_find_contracts,
    parse_contract,
)


def find_contract_files(project_dir: Path) -> list[Path]:
    """自动发现所有契约文件（YAML + Markdown 双格式）"""
    return _gc_find_contracts(project_dir)


def extract_task_id(filepath: Path) -> str:
    """兼容既有调用；任务 ID 规则由 gov_common 统一维护。"""
    return _gc_extract_task_id(filepath)


def verify_contract(contract_path: Path, project_dir: Path,
                    base_url: str = None) -> dict:
    """验证单个契约的所有 AC（YAML / Markdown 契约均可）"""
    parsed = parse_contract(contract_path)

    task_id = parsed["task"]
    ac_list = parsed["ac"]
    if not ac_list:
        return {
            "task": task_id,
            "status": "SKIPPED",
            "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            "results": [],
            "error": "契约中未定义 ac 字段",
        }

    results = []
    passed = failed = skipped = 0

    for ac in ac_list:
        ac_id = ac.get("id", "?")
        ac_desc = ac.get("desc", "")
        verify_cfg = ac.get("verify")

        if not verify_cfg:
            results.append({
                "id": ac_id,
                "desc": ac_desc,
                "status": "SKIPPED",
                "detail": "未定义 verify 配置（纯文档型 AC，需人工确认）",
            })
            skipped += 1
            continue

        vtype = verify_cfg.get("type", "shell")

        try:
            if vtype == "shell":
                ok, detail = verify_shell(verify_cfg.get("command", "true"), project_dir,
                                          dialect=verify_cfg.get("dialect"))
            elif vtype == "command":
                ok, detail = verify_command(verify_cfg.get("command", {}), project_dir)
            elif vtype == "http":
                url = verify_cfg.get("url", "")
                if base_url and url.startswith("/"):
                    url = base_url.rstrip("/") + url
                ok, detail = verify_http(
                    verify_cfg.get("method", "GET"),
                    url,
                    verify_cfg.get("headers", {}),
                    verify_cfg.get("expect", {}),
                )
            elif vtype == "db":
                ok, detail = verify_db(
                    verify_cfg.get("engine", ""),
                    verify_cfg.get("query", "") or verify_cfg.get("sql", ""),
                    verify_cfg.get("expect", {}),
                )
            elif vtype == "assert":
                ok, detail = verify_assert(
                    verify_cfg.get("expression", "") or verify_cfg.get("expr", "True"),
                    verify_cfg.get("setup", ""),
                )
            elif vtype == "predicate":
                ok, detail = verify_predicate(
                    verify_cfg.get("expression", "") or verify_cfg.get("expr", "False"),
                    project_dir,
                )
            else:
                ok, detail = False, f"未知验证类型: {vtype}"
        except Exception as e:
            ok, detail = False, f"验证异常: {e}"

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        results.append({
            "id": ac_id,
            "desc": ac_desc,
            "type": vtype,
            "status": status,
            "detail": detail,
        })

    all_pass = failed == 0
    return {
        "task": task_id,
        "status": "PASS" if all_pass else "FAIL",
        "summary": {
            "total": len(ac_list),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "results": results,
    }


# ─── 输出 ──────────────────────────────────────────────────

def print_text(reports: list[dict]):
    """文本格式输出"""
    print("╔══════════════════════════════════════════════╗")
    print("║   Contract Compliance Verifier — 契约一致性  ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    grand_total = grand_pass = grand_fail = grand_skip = 0

    for report in reports:
        s = report["summary"]
        icon = "✅" if report["status"] == "PASS" else "❌"
        print(f"━━━ {icon} {report['task']} — {s['passed']}/{s['total']} 通过 ━━━")

        if report.get("error"):
            print(f"  ⚠️ {report['error']}")
            print()
            continue

        for r in report["results"]:
            icon2 = {"PASS": "��", "FAIL": "❌", "SKIPPED": "⬜"}.get(r["status"], "?")
            type_tag = f"[{r.get('type', '?')}]"
            print(f"  {icon2} {type_tag} {r['id']}: {r['desc']}")
            if r["status"] == "FAIL":
                print(f"     → {r['detail']}")
            elif r["status"] == "SKIPPED":
                print(f"     → {r['detail']}")

        grand_total += s["total"]
        grand_pass += s["passed"]
        grand_fail += s["failed"]
        grand_skip += s["skipped"]
        print()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"总计: {grand_total} | 通过: {grand_pass} | 失败: {grand_fail} | 跳过: {grand_skip}")
    if grand_fail > 0:
        print(f"\n❌ {grand_fail} 条验收标准未满足！")
    else:
        print(f"\n✅ 所有可验证验收标准通过！")


def main():
    parser = argparse.ArgumentParser(
        description="Contract Compliance Verifier — 契约一致性验证器"
    )
    parser.add_argument("--task", default=None, help="验证指定任务（如 T-003）")
    parser.add_argument("--all", action="store_true", help="验证所有契约")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--base-url", default=None,
                        help="HTTP 验证的基础 URL（如 http://localhost:8000）")
    parser.add_argument("--generate-tests", action="store_true",
                        help="TDD Red 阶段：从契约 AC 生成 pytest 测试���架")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()

    try:
        _main_with_args(args, project_dir)
    except ContractConflictError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)


def _main_with_args(args, project_dir: Path):
    # TDD 模式：生成测试骨架
    if args.generate_tests:
        if not args.task:
            print("--generate-tests 需要指定 --task <ID>", file=sys.stderr)
            sys.exit(2)
        contract_path = _gc_find_contract(project_dir, args.task)
        if not contract_path:
            print(f"错误: 找不到契约文件 Intent_Contract_{args.task}（.yaml/.yml/.md）", file=sys.stderr)
            sys.exit(2)
        write_generated_tests(contract_path, project_dir)
        return

    if args.task:
        contract_path = _gc_find_contract(project_dir, args.task)
        if not contract_path:
            print(f"错误: 找不到契约文件 Intent_Contract_{args.task}（.yaml/.yml/.md）", file=sys.stderr)
            sys.exit(2)
        reports = [verify_contract(contract_path, project_dir, args.base_url)]
    elif args.all:
        files = find_contract_files(project_dir)
        if not files:
            print("错误: 未找到任何契约文件", file=sys.stderr)
            sys.exit(2)
        reports = [verify_contract(f, project_dir, args.base_url) for f in files]
    else:
        print("请指定 --task <ID> 或 --all", file=sys.stderr)
        sys.exit(2)

    if args.format == "json":
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        print_text(reports)

    # 退出码
    has_failure = any(r["status"] == "FAIL" for r in reports)
    sys.exit(1 if has_failure else 0)


if __name__ == "__main__":
    main()
