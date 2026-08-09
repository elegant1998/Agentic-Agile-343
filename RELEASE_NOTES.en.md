# Release Notes

> 🌐 中文版: [RELEASE_NOTES.md](RELEASE_NOTES.md)

# Agentic Agile 3-4-3 Governance Framework · Open Source Edition v1.25.0

> **Calibrate first, then fight the bosses.** A complete, runnable governance framework for Agentic AI development — fully open source, no reservations. Let AI R&D governance be both offensive and defensive.

- **Version**: `1.25.0`
- **Release date**: 2026-08-09
- **License**: Code/templates MIT · Whitepaper CC BY 4.0
- **Author**: Wang Lijie (无敌哥), AI Governance Architect
- **Official site**: <http://agentic.iloveagile.me/about> · WeChat `iloveagile`

---

## v1.25.0 Changes

- Added read-only lightweight Recon for existing projects.
- Added explainable risk assessment and five governance profiles.
- Added `recon` and `assess-risk` CLI commands plus three templates.
- Python TDD gates now detect pytest or standard-library unittest RED/GREEN states.
- No tag or external release is created by this update.

---

## 1. TL;DR

Starting from this version, **there is no more Community/Full split** — the strongest edition is open-sourced directly. From Intent Contract to evidence closure, from 5 mechanical gates to 4-layer 9-dimension telemetry, everything works out of the box.

## 2. v1.24.0 Changes (vs. v1.0.0-community)

| Category | Change |
|---|---|
| 🔄 Repositioning | Upgraded from "Community Edition (intentionally missing)" to **complete open-source edition**, no gaps kept |
| ➕ New scripts | `gate_check.py` (5 mechanical gates), `audit_evidence.py`, `collect_telemetry.py`, `fetch_token_usage.sh`, `quick_telemetry.sh`, `crop_context.py`, `graph_engine.py`, `audit_tools.py`, `verify_*.py` (triangulation/rollback/freshness/cross_module), `reflect.py`, `aggregate_evidence.py`, `discover_context.py`, `self_consistency_check.py`, etc. (25 scripts total) |
| ➕ New templates | `Template_Evidence_Bundle.*`, `Template_Tools_Manifest.yaml`, `Template_Protocol.yaml`, `Template_Module_Governance.md`, `Template_Work_Graph.yaml`, `Template_Loop_Memory.yaml`, `Template_AI_Coding_Guide.md` (13 templates total) |
| ➕ New references | `references/` expanded to 9 (incl. harness/loop_graph/telemetry/multi_module/verified/context) |
| ➕ Dashboard | `assets/dashboard.html` telemetry dashboard (pure static, double-click to view) |
| ✂️ Removed | `build_community_ed.sh` (no longer needed) |
| 🐛 Fixes | v1.23 anti-proxy-signing: Grill-Me decision confirmation ≠ contract signing, `gate_check.py` proxy-signing detection; v1.23.1 negative-context fix |
| ✏️ Meta | description condensed to one line; "contact 无敌哥" updated with official-site link |

## 3. What's in This Edition

See [README.md §3](README.md#三本版包含什么全部开源无保留) — 25 scripts / 13 templates / 9 references / dashboard / whitepaper / example.

## 4. Requirements

- Python 3.10+ (`ensure_py_env.sh` auto-creates a venv + installs pyyaml; degrades to MD-only when missing)
- Node ≥ 22.5 (optional, for `fetch_token_usage.sh` token measurement; auto-runs `npm i -g @geeeger/ocusage` when missing)
- No external services, no network dependency, no API key required

## 5. Quick Start

```bash
# 1. Prepare environment
bash scripts/ensure_py_env.sh

# 2. Initialize project governance
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml

# 3. SCOPE-V loop + 5 mechanical gates (hard blocking)
python scripts/gate_check.py --gate pre --task T-001 --project-dir .
python scripts/verify_contract.py --task T-001 --project-dir .
python scripts/harness.py check --all
bash scripts/quick_telemetry.sh T-001 ./governance
```

For fuller instructions, see [`README.md`](README.md).

## 6. Upgrading from the Old Community Edition

- Users on the old Community Edition (v1.0.0-community): just overlay this edition onto `scripts/`, `templates/`, `references/`, `assets/`, `SKILL.md`. Your existing `governance/` contracts and constraint matrices need no rebuild.
- `build_community_ed.sh` has been removed — no longer needed.

## 7. Known Limitations (Honest Caveats)

1. **Single example**: only `T-001` (a neutral example) for now — PRs adding more scenarios welcome.
2. **Token measurement depends on ocusage**: `fetch_token_usage.sh` requires `@geeeger/ocusage` (auto-installed when missing, needs Node ≥ 22.5); falls back to estimation marked `estimated` when unavailable.
3. **Multi-person / multi-module**: `protocol.yaml` and module governance target complex projects; solo projects can ignore them.

## 8. License

- Code & templates: **[MIT](LICENSE)**
- Whitepaper: **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)** (redistribution / derivative works must attribute Wang Lijie-无敌哥)

## 9. Next Steps

- 📘 Read the whitepaper to understand the 3-4-3 theoretical foundation and maturity model (L1–L4)
- 🎓 Enroll in advanced courses / in-house training to turn "can use" into "use well"
- ✍️ Sign the *Agentic Agile Manifesto* on the official site and join the pioneer community
- 🤝 Want to contribute? See [`CONTRIBUTING.md`](CONTRIBUTING.md)

> The toolset is fully open source, but between "can use" and "use well" lies systematic learning and enterprise-scenario coaching — that is exactly where courses and in-house training add value.
