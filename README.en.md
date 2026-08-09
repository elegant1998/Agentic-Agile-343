# Agentic Agile 3-4-3 Governance Framework · Open Source Edition v1.25.0

> 🌐 中文版: [README.md](README.md)

> **Calibrate first, then fight the bosses.** This is a **complete, runnable governance framework** for Agentic AI development — from Intent Contract to evidence closure, from constraint gates to telemetry dashboards, fully open source and ready to use out of the box. Let AI R&D governance be both offensive and defensive.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Whitepaper: CC BY 4.0](https://img.shields.io/badge/Whitepaper-CC%20BY%204.0-green.svg)](docs/whitepaper/)

- 📘 Methodology whitepaper: [`docs/whitepaper/`](docs/whitepaper/) (CC BY 4.0 — free to share with attribution)
- 🌐 Official site: <http://agentic.iloveagile.me/about>
- 📦 GitHub repo: <https://github.com/elegant1998/Agentic-Agile-343.git> (manual install: `git clone https://github.com/elegant1998/Agentic-Agile-343.git`)
- ✍️ Author: Wang Lijie (无敌哥), AI Governance Architect
- 🤝 Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) ([English](CONTRIBUTING.en.md)) · 📦 Release Notes: [`RELEASE_NOTES.md`](RELEASE_NOTES.md) ([English](RELEASE_NOTES.en.md))

---

## 1. Why You Need It

Since 2024, autonomous agents (Agentic AI) have blown past the physical and cognitive limits of traditional Agile — but they also introduced a new problem: **vague specifications + a smart model = a more sophisticated form of logic drift**. As the industry insight goes — *"This is not a model-capability problem at all; it is a process-control-system problem."*

Moving from casual **Vibe Coding** to rigorous **Verified Engineering** requires an intent-centric governance architecture powered by multi-agent high-frequency adversarial loops and backed by compute. That is **Agentic Agile 3-4-3**.

## 2. The 3-4-3 Framework at a Glance

- **3 super-roles**: Intent Owner (IO, sets direction), Orchestration Architect (OA, manages machines & boundaries), Autonomous Swarm (AS, deterministic executors).
- **4 dynamic artifacts**: Intent Graph, Intent Contract, Constraint Matrix, Compute & Value Telemetry.
- **3 autonomous mechanisms**: intent injection (dialogue → contract gate), high-frequency adversarial self-purification loop, human exception arbitration (HITL + evidence-bundle acceptance).
- **SCOPE-V engineering control loop**: `Specify → Constrain → Orchestrate → Prove → Evolve → Verify → Telemetry`.

For the full theoretical foundation (cognitive science / cybernetics / systems theory), the Agentic Agile Manifesto, the maturity model (L1–L4), and the adoption roadmap, see [`docs/whitepaper/`](docs/whitepaper/).

## 3. What's in This Edition (Fully Open Source, No Reservations)

This repository **is** the complete edition — no more Community/Full split:

| Capability | Key Asset |
|---|---|
| Intent Contract / Constraint Matrix / Evidence Bundle / Intent Graph | `templates/` — 13 templates (MD + YAML dual format) |
| Mechanical gates (5 gates, hard-blocking exit codes) | `scripts/gate_check.py` |
| Constraint execution engine (G0–G8 + 7 NFR validators) | `scripts/harness.py` |
| Contract AC clause-by-clause verification | `scripts/verify_contract.py` |
| Evidence bundle audit | `scripts/audit_evidence.py` |
| Triangulation / rollback safety / freshness / cross-module | `scripts/verify_*.py` |
| Context engineering 3-layer injection | `scripts/crop_context.py` |
| Work-graph DAG engine | `scripts/graph_engine.py` |
| Tool audit | `scripts/audit_tools.py` |
| Telemetry collection (4 layers, 9 dimensions) + token measurement | `scripts/collect_telemetry.py`, `fetch_token_usage.sh` |
| One-click telemetry + dashboard | `scripts/quick_telemetry.sh`, `assets/dashboard.html` |
| Critical Thinking / Grill-Me / LOOP / Graph engineering | `references/` — 9 references |
| Certificate application (AASC) | `scripts/certificate.py` |

## 4. Quick Start

### 1. Prepare the Python environment

```bash
# On first run, a venv is created automatically and pyyaml is installed
# (falls back to MD-only mode if pyyaml is missing)
bash scripts/ensure_py_env.sh
```

### 2. Initialize project governance (solo)

```bash
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml
```

### 3. Run the SCOPE-V loop

```
Specify  → fill the Intent Contract → Grill-Me decision confirmation → IO signs explicitly (OA must not sign on IO's behalf)
Constrain → fill the Constraint Matrix (6 domains; list MUST first)
Orchestrate → TDD red→green→refactor; write the failing test first per task
Prove    → run tests until all green + AC clause-by-clause verification
Evolve / Verify / Telemetry → evidence bundle + telemetry + graph writeback
```

### 4. Mechanical gates (5 gates, hard blocking)

```bash
# Pre-gate (before coding: contract explicitly signed + constraint matrix + AC shell:grep ≤50%)
python scripts/gate_check.py --gate pre --task T-001 --project-dir .

# Coding gate (TDD Red: tests written first and running RED)
python scripts/gate_check.py --gate coding --task T-001 --project-dir .

# Prove gate (TDD Green: all tests green + AC pass + tsc compile)
python scripts/gate_check.py --gate prove --task T-001 --project-dir .

# Closing gate (evidence bundle + per-task telemetry + graph writeback)
python scripts/gate_check.py --gate closing --task T-001 --project-dir .

# Bug regression gate (when a bug is found in an already-completed task)
python scripts/gate_check.py --gate bug --task T-001 --project-dir .

# Contract AC verification
python scripts/verify_contract.py --task T-001 --project-dir .

# Constraint check
python scripts/harness.py check --all

# One-click telemetry
bash scripts/quick_telemetry.sh T-001 ./governance
```

### 5. A filled-in example

See [`examples/Intent_Contract_T-001.example.yaml`](examples/Intent_Contract_T-001.example.yaml) — a minimal runnable task with all template fields filled. Edit to fit your own.

## 5. Critical Thinking (Cross-Project Universal)

AI by default blindly obeys the user's literal instructions (the IO). This framework requires OA to **calibrate before implementing** during the Specify / Constrain stages — whenever there is ambiguity, over-dense incentives, conflict with the north-star, unverifiable claims, or overly permissive safety, challenge first and provide a recommended default; do not implement until confirmed. The full 7 suspicious signals, the Grill-Me clause-by-clause confirmation protocol, and the four-type human-agent division of labor are in [`references/critical_thinking.md`](references/critical_thinking.md).

## 6. Constraint Priority Chain

```
Legal / safety constraints > Constraint Matrix > signed Intent Contract > implementation convenience
MUST (break = failure) > SHOULD (important but negotiable) > MAY (optional)
```

Any exception may only be granted by the human IO through a signed written approval.

## 7. Directory Structure

```text
agentic-agile-343-community-ed/
├── SKILL.md                      # skill entry (usage flow + all hard rules)
├── README.md                     # Chinese readme
├── LICENSE                       # MIT (code); whitepaper CC BY 4.0, see docs/whitepaper
├── requirements.txt              # Python deps (pyyaml, optional)
├── .gitignore
├── scripts/                      # 25 runnable scripts (gates / engine / verification / telemetry / context / graph)
├── templates/                    # 13 artifact templates (MD + YAML dual format)
├── references/                   # 9 reference docs (critical thinking / SCOPE-V / Harness / LOOP / Graph / telemetry…)
├── assets/
│   └── dashboard.html            # telemetry dashboard (pure static, double-click to view)
├── examples/
│   └── Intent_Contract_T-001.example.yaml
└── docs/
    └── whitepaper/               # "Agentic Agile" whitepaper (CC BY 4.0)
```

## 8. License

- **Code & templates** (`scripts/`, `templates/`, `SKILL.md`, etc.): [MIT License](LICENSE) — free to use, modify, and distribute.
- **Whitepaper** (`docs/whitepaper/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — redistribution and derivative works require attribution to **Wang Lijie (无敌哥)**.

## 9. About the Author & Community

**Wang Lijie (无敌哥)**, AI Governance Architect and veteran R&D effectiveness consultant. MIIT Certified R&D Effectiveness Engineer expert instructor, PMI-ACP authorized instructor, SAFe SPC6, Huawei Cloud MVP; author of the bestsellers *Agile Invincible* and *JD Agile Practice Guide*.

- Official site: <http://agentic.iloveagile.me/about>
- WeChat: `iloveagile` · Email: 3433839@qq.com
- Advanced courses: *Agentic Agile / 智能体敏捷: AI-Era R&D Governance Sandbox Bootcamp* and others (contact 无敌哥)

>  Resonate with the philosophy? Sign the *Agentic Agile Manifesto* on the official site and join the pioneer community.
