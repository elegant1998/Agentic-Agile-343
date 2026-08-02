#!/usr/bin/env python3
"""代码上下文自动发现 v1.1

解析项目目录，自动提取：
- API 端点签名（FastAPI / Flask 自适应）
- 数据模型列表（SQLAlchemy / Pydantic / dataclass）
- 已有域模块
- 关键依赖
- 项目类型检测（web_fastapi / web_flask / cli / lib / unknown）

用法:
    python scripts/discover_context.py [--project-dir /path/to/project]
"""

import ast
import json
import sys
import re
from pathlib import Path


# ─── 项目类型检测 ──────────────────────────────────────────

def detect_project_type(project_dir: Path) -> str:
    """自动检测项目类型，决定后续解析策略"""
    src = project_dir / "src"
    req_file = project_dir / "requirements.txt"

    if not src.exists():
        return "unknown"

    # 检测 FastAPI
    api_dir = src / "api"
    if api_dir.exists():
        for d in api_dir.iterdir():
            if d.is_dir():
                router = d / "router.py"
                if router.exists():
                    try:
                        content = router.read_text()
                        if "from fastapi" in content or "APIRouter" in content:
                            return "web_fastapi"
                    except Exception:
                        pass
    # 检测 Flask
    app_file = src / "app.py"
    main_file = src / "main.py"
    for check_file in [app_file, main_file]:
        if check_file.exists():
            try:
                content = check_file.read_text()
                if "from flask" in content or "Flask(__name__)" in content:
                    return "web_flask"
            except Exception:
                pass

    # 检测 CLI
    for check_file in [main_file, src / "cli.py", src / "__main__.py"]:
        if check_file.exists():
            try:
                content = check_file.read_text()
                if "argparse" in content or "click" in content or "if __name__" in content:
                    return "cli"
            except Exception:
                pass

    # 检测纯库（无入口文件，只有模块）
    py_files = list(src.rglob("*.py"))
    if py_files and not any(f.name in ("main.py", "app.py", "cli.py") for f in py_files):
        return "lib"

    return "unknown"


def extract_endpoints(router_file: Path, project_type: str = "web_fastapi") -> list[dict]:
    """从路由文件提取端点签名（按项目类型自适应）"""
    if project_type == "web_fastapi":
        return _extract_fastapi_endpoints(router_file)
    elif project_type == "web_flask":
        return _extract_flask_endpoints(router_file)
    else:
        # CLI / lib / unknown — 不提取端点
        return []


def _extract_fastapi_endpoints(router_file: Path) -> list[dict]:
    """从 FastAPI router.py 提取 @router 装饰的端点"""
    endpoints = []
    try:
        tree = ast.parse(router_file.read_text())
    except SyntaxError:
        return endpoints

    # 找路由前缀
    prefix = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and hasattr(node.target, 'id') and node.target.id == 'router':
            if isinstance(node.value, ast.Call):
                for kw in getattr(node.value, 'keywords', []):
                    if kw.arg == 'prefix':
                        prefix = kw.value.value if isinstance(kw.value, ast.Constant) else ""

    # 找 @router.method(...) 装饰器
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                method, path = _parse_fastapi_decorator(deco)
                if method:
                    full_path = f"{prefix.rstrip('/')}/{path.lstrip('/')}"
                    endpoints.append({
                        "method": method.upper(),
                        "path": full_path,
                        "function": node.name,
                        "summary": _extract_summary(node)
                    })
    return endpoints


def _extract_flask_endpoints(router_file: Path) -> list[dict]:
    """从 Flask app.py 提取 @app.route 装饰的端点"""
    endpoints = []
    try:
        tree = ast.parse(router_file.read_text())
    except SyntaxError:
        return endpoints

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
                    if deco.func.attr == 'route':
                        path = deco.args[0].value if deco.args and isinstance(deco.args[0], ast.Constant) else ""
                        # 提取 methods 参数
                        methods = ["GET"]
                        for kw in getattr(deco, 'keywords', []):
                            if kw.arg == 'methods' and isinstance(kw.value, ast.List):
                                methods = [e.value.upper() if isinstance(e, ast.Constant) else "GET"
                                          for e in kw.value.elts]
                        for method in methods:
                            endpoints.append({
                                "method": method,
                                "path": path,
                                "function": node.name,
                                "summary": _extract_summary(node),
                            })
    return endpoints


def _parse_fastapi_decorator(deco) -> tuple:
    """解析 @router.get('/path') 或 @router.post('/path')"""
    if isinstance(deco, ast.Attribute):
        method = deco.attr
        return (method, "") if method in ('get', 'post', 'put', 'delete', 'patch') else ("", "")

    if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
        method = deco.func.attr
        if method in ('get', 'post', 'put', 'delete', 'patch') and deco.args:
            arg = deco.args[0]
            path = arg.value if isinstance(arg, ast.Constant) else ""
            return (method, path)
    return ("", "")


def _extract_summary(node) -> str:
    """提取 docstring 或 summary 参数"""
    # 从装饰器 keyword 中提取 summary
    for deco in node.decorator_list:
        if isinstance(deco, ast.Call):
            for kw in getattr(deco, 'keywords', []):
                if kw.arg == 'summary':
                    return kw.value.value if isinstance(kw.value, ast.Constant) else ""
    return ""


def extract_models(models_dir: Path, project_type: str = "web_fastapi") -> list[str]:
    """提取所有模型类名（SQLAlchemy / Pydantic / dataclass 自适应）"""
    models = []
    for f in models_dir.glob("*.py"):
        if f.name == "__init__.py":
            continue
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr

                    # SQLAlchemy Base
                    if base_name == 'Base':
                        models.append(node.name)
                        break
                    # Pydantic BaseModel
                    elif base_name == 'BaseModel':
                        models.append(node.name)
                        break
    return sorted(models)


def extract_domains(api_dir: Path, project_type: str = "web_fastapi") -> list[str]:
    """提取所有业务域

    - FastAPI: src/api/ 下每个子目录是一个域
    - Flask: src/ 下每个子目录（有 __init__.py）是一个模块
    - CLI/Lib: src/ 下每个 .py 文件是一个模块
    """
    domains = []
    if project_type in ("web_fastapi",):
        if api_dir.exists():
            for d in api_dir.iterdir():
                if d.is_dir() and (d / "__init__.py").exists():
                    domains.append(d.name)
    elif project_type in ("web_flask", "cli", "lib"):
        # 通用：扫描 src/ 下所有 Python 子包
        src = api_dir.parent  # api_dir is src/api, go up to src/
        for d in src.iterdir():
            if d.is_dir() and d.name not in ("__pycache__", "api", "models", "migrations"):
                if (d / "__init__.py").exists():
                    domains.append(d.name)
            elif d.suffix == ".py" and d.stem != "__init__":
                domains.append(d.stem)
    return sorted(domains)


def extract_dependencies(req_file: Path) -> list[str]:
    """从 requirements.txt 提取核心依赖"""
    if not req_file.exists():
        return []
    deps = []
    for line in req_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            deps.append(line.split("==")[0].split(">=")[0].split("<")[0].strip())
    return deps


def discover(project_dir: Path) -> dict:
    """自动发现代码上下文（按项目类型自适应）"""
    project_type = detect_project_type(project_dir)
    src = project_dir / "src"
    api_dir = src / "api" if (src / "api").exists() else src
    models_dir = src / "models"
    req_file = project_dir / "requirements.txt"

    context = {
        "project_type": project_type,
        "domains": extract_domains(api_dir, project_type),
        "models": extract_models(models_dir, project_type) if models_dir.exists() else [],
        "dependencies": extract_dependencies(req_file),
        "endpoints": {},
    }

    # 按项目类型发现端点
    if project_type == "web_fastapi":
        api_dir_fastapi = src / "api"
        if api_dir_fastapi.exists():
            for domain in context["domains"]:
                router = api_dir_fastapi / domain / "router.py"
                if router.exists():
                    context["endpoints"][domain] = extract_endpoints(router, project_type)
    elif project_type == "web_flask":
        # Flask: 从 src/app.py 或 src/main.py 提取
        for candidate in [src / "app.py", src / "main.py"]:
            if candidate.exists():
                context["endpoints"]["main"] = extract_endpoints(candidate, project_type)
                break

    return context


def main():
    import argparse
    parser = argparse.ArgumentParser(description="代码上下文自动发现")
    parser.add_argument("--project-dir", default=".", help="项目根目录")
    parser.add_argument("--output", default=None, help="输出 JSON 文件")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="输出格式")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    context = discover(project_dir)

    if args.format == "text":
        _print_text(context)
    else:
        output = json.dumps(context, indent=2, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(output)
            print(f"代码上下文已写入: {args.output}")
        else:
            print(output)

    # 统计
    total_endpoints = sum(len(v) for v in context["endpoints"].values())
    print(f"类型: {context['project_type']} | "
          f"发现: {len(context['domains'])} 个域/模块, "
          f"{len(context['models'])} 个模型, "
          f"{total_endpoints} 个端点", file=sys.stderr)


def _print_text(context):
    print(f"=== 项目类型: {context.get('project_type', 'unknown')} ===")
    print()
    print("=== 业务域/模块 ===")
    for d in context["domains"]:
        print(f"  - {d}")
    print(f"\n=== 模型 ({len(context['models'])}) ===")
    for m in context["models"]:
        print(f"  - {m}")
    print(f"\n=== 端点 ({sum(len(v) for v in context['endpoints'].values())}) ===")
    for domain, eps in context["endpoints"].items():
        print(f"\n  [{domain}]")
        for ep in eps:
            print(f"    {ep['method']:6s} {ep['path']:40s} # {ep['summary']}")


if __name__ == "__main__":
    main()
