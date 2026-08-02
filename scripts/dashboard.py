"""Dashboard 渲染模块 — 从 collect_telemetry.py 拆分。

负责：模板发现、HTML 生成、单次契约摘要。
"""
import json
import re
from pathlib import Path


def find_dashboard_template() -> Path | None:
    """skill assets 模板；也接受项目 governance 已有的 dashboard.html"""
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "assets" / "dashboard.html",
        Path("governance/dashboard.html"),
        here.parent.parent / "assets" / "dashboard.html",
    ]
    for p in candidates:
        if p.is_file() and "TELEMETRY_EMBED_START" in p.read_text(encoding="utf-8", errors="ignore"):
            return p
    return None


def write_static_dashboard(html_path: Path, telemetry: dict, template: Path | None = None) -> Path:
    """把遥测 JSON 内嵌进 HTML，双击即可用浏览器打开（无需 Server）。"""
    tpl = template or find_dashboard_template()
    if not tpl or not tpl.is_file():
        # 无模板时仍写一个最小 HTML
        payload = json.dumps(telemetry, ensure_ascii=False)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(
            f"""<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8">
<title>Telemetry</title>
<pre id="raw"></pre>
<script type="application/json" id="telemetry-data">{payload}</script>
<script>
const d=JSON.parse(document.getElementById('telemetry-data').textContent);
document.getElementById('raw').textContent=JSON.stringify(d,null,2);
</script></html>""",
            encoding="utf-8",
        )
        return html_path

    text = tpl.read_text(encoding="utf-8")
    # 避免 </script> 打断页面
    payload = json.dumps(telemetry, ensure_ascii=False).replace("</", "<\\/")
    embed = (
        "<!-- TELEMETRY_EMBED_START -->\n"
        f'<script type="application/json" id="telemetry-data">{payload}</script>\n'
        "<!-- TELEMETRY_EMBED_END -->"
    )

    new_text, n = re.subn(
        r"<!-- TELEMETRY_EMBED_START -->.*?<!-- TELEMETRY_EMBED_END -->",
        lambda _m: embed,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        # 旧模板无占位：插到第一个 <script> 前
        new_text = text.replace("<script>", embed + "\n<script>", 1)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(new_text, encoding="utf-8")
    return html_path


def summarize_for_index(telemetry: dict) -> dict:
    """单次契约 → 项目 runs 列表中的摘要条目"""
    m = telemetry.get("meta", {})
    v = telemetry.get("value", {})
    c = telemetry.get("capability", {})
    e = telemetry.get("efficiency", {})
    ev = telemetry.get("evolution", {})
    tid = m.get("task_id")
    return {
        "task_id": tid,
        "collected_at": m.get("collected_at"),
        "file": m.get("links", {}).get("contract_telemetry"),
        "dashboard": f"dashboard-{tid}.html" if tid else m.get("links", {}).get("dashboard_contract"),
        "goal_accuracy": (v.get("goal_accuracy") or {}).get("display"),
        "first_pass_rate": (v.get("first_pass_rate") or {}).get("display"),
        "autonomy_score": (c.get("autonomy_score") or {}).get("display"),
        "auto_heal_rate": (c.get("auto_heal_rate") or {}).get("display"),
        "context_compression": (e.get("context_compression") or {}).get("display"),
        "knowledge_rate": (ev.get("knowledge_crystallization") or {}).get("display"),
        "token_usage": (telemetry.get("cost") or {}).get("token_usage", 0),
    }
