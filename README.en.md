# Agentic Agile 3-4-3 Governance Framework · Open Source Edition v1.51.2

> 🌐 中文版: [README.md](README.md)

Telemetry is independent of the host AI tool. `AGENTIC_AGILE_HOST_TOOL` identifies the host while `AGENTIC_AGILE_TOKEN_CLIENT` selects the usage client. Project daily cumulative tokens are baseline evidence only; task totals require a same-client, same-project, same-day delta, otherwise they remain `N/A`.

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
- **Six continuous control planes in SCOPE-V**: `S / C / O / Prove ⇄ Evolve / V`; the fast proof-evolution loop is complemented by the slow `Verify → Telemetry → Specify/Constrain/Orchestrate` feedback loop.
- **Cross-cutting autonomy**: context, execution, and evolution mechanisms operate across the control planes instead of mapping one-to-one to stages.
- **Scales to large repositories and long histories**: Map-first Recon uses bounded provider queries, L0 performs one bounded fallback, and event/project telemetry uses rebuildable indexes and stable summaries.

For the full theoretical foundation (cognitive science / cybernetics / systems theory), the Agentic Agile Manifesto, the maturity model (L1–L4), and the adoption roadmap, see [`docs/whitepaper/`](docs/whitepaper/).

## 3. What's in This Edition (Fully Open Source, No Reservations)

This repository **is** the complete edition — no more Community/Full split:

| Capability | Key Asset |
|---|---|
| Intent Contract / Constraint Matrix / Evidence Bundle / Intent Graph / Recon / risk profiles | `templates/` — 18 templates (MD + YAML dual format) |
| Mechanical gates (5 gates, hard-blocking exit codes) | `scripts/gate_check.py` |
| Constraint execution engine (G0–G8 + 7 NFR validators) | `scripts/harness.py` |
| Contract AC clause-by-clause verification | `scripts/verify_contract.py` |
| Risk-driven multi-layer verification / evidence independence / invalid-green detection | `scripts/verification_plan.py`, `Template_Verification_Plan.yaml` |
| Single-project proof-carrying release / artifact-evidence binding / release facts | `scripts/release_manifest.py`, `Template_Release_Manifest.yaml` |
| Evidence bundle audit | `scripts/audit_evidence.py` |
| Triangulation / rollback safety / freshness / cross-module | `scripts/verify_*.py` |
| Context engineering + real Context Pack measurement + L0-L3 dual maps | `scripts/crop_context.py`, `scripts/context_measurement.py`, `scripts/context_providers.py` |
| Work-graph DAG engine | `scripts/graph_engine.py` |
| Tool audit | `scripts/audit_tools.py` |
| Telemetry collection (4 layers, 9 dimensions) + cross-tool Usage Providers | `scripts/collect_telemetry.py`, `scripts/usage_providers.py`, `scripts/token_usage.py` |
| Cross-platform telemetry + dashboard | `scripts/telemetry_workflow.py`, `scripts/telemetry_tracker.py`, `assets/dashboard.html` |
| Automatic evidence-to-telemetry finalization + dual dashboards | `scripts/evidence_workflow.py` |
| Critical Thinking / Grill-Me / LOOP / Graph / maintenance / Recon / verification / release | `references/` — 15 references |
| Certificate application (AASC) | `scripts/certificate.py` |

### Natural-language routing (v1.36.2)

Users do not need CLI knowledge. Requests such as “do not rely only on unit tests,” “design multi-layer verification,” “check whether evidence has the same source,” or “detect invalid green” route to Verification Plan alongside the existing workflows. See [`references/natural_language_routing.md`](references/natural_language_routing.md).

“Prepare a release,” “generate a release manifest,” “check artifact/evidence consistency,” and “record released/rolled back” route to the single-project Release Manifest. Natural language never grants release approval.

### Single-project proof-carrying release (v1.32.0)

```bash
python scripts/cli.py release plan --task T-001 --version 1.2.3 --artifact dist/app.tar.gz --project-dir .
python scripts/cli.py release check --manifest governance/releases/Release_Manifest_1.2.3.yaml --project-dir .
```

Planning is dry-run by default and measures Git commit/worktree state, artifact SHA-256/size, configuration, and task evidence. Apply creates only a DRAFT. A valid authorized manifest yields `READY_FOR_HUMAN_RELEASE`, never a tag, push, build, or deployment. `record` only appends already-executed released/rolled_back facts. See [`references/release_manifest.md`](references/release_manifest.md).

### Risk-driven multi-layer verification (v1.31.0)

```bash
python scripts/cli.py verification plan --task T-001 --project-dir .
python scripts/cli.py verification plan --task T-001 --project-dir . --risk high --trace AC-001 --apply
python scripts/cli.py verification check --task T-001 --project-dir .
```

Planning is dry-run by default; apply only creates a DRAFT and never overwrites. Once explicitly authorized, the plan joins the prove gate. Missing layers, copied same-source evidence, insufficient independence, stale or mismatched evidence, LLM-only key proof, and AI-signed human acceptance cannot become PASS. See [`references/verification_planning.md`](references/verification_planning.md).

### Risk-driven initialization (v1.26.0)

```bash
python scripts/cli.py init --project-dir .          # dry-run by default
python scripts/cli.py init --project-dir . --apply  # write only after IO review
```

The entry point classifies the project, evaluates seven risk domains, and selects one of five governance profiles. Existing projects include read-only Recon; Unknown never lowers risk, existing files are never overwritten, and generated contracts remain PENDING.

### Gate self-governance (v1.26.1)

```bash
python scripts/cli.py maintain open --id M-001 --task T-128 --project-dir .
python scripts/cli.py maintain check --id M-001 --project-dir .
python scripts/cli.py maintain close --id M-001 --project-dir .
```

Deterministic low-risk gate defects use `M-XXX` maintenance records instead of repeated business-contract addenda. Unknown, weaker gates, changed signing semantics, or expanded permissions fail closed and require an IO-signed Amendment. See [`references/maintenance_channel.md`](references/maintenance_channel.md).

### Task-scoped Recon (v1.27.0)

```bash
python scripts/cli.py recon task --task T-001 --target src/example.py --project-dir .
```

Read-only discovery around concrete change targets, separating facts from reference/test/public-entry candidates and unknown runtime relationships. Lightweight adapters cover Python, JavaScript/TypeScript, C/C++, Java/JSP, with basic Go, Rust, and Shell support. The suggested Change Envelope remains `DRAFT_NOT_AUTHORIZED`.

### Dual-map enhanced Recon (v1.37.0)

IWE is the recommended Document Map for requirements, rules, ACs, ADRs, and historical decisions. codebase-memory-mcp is the recommended Code Map for modules, symbols, calls, routes, and tests. 343 owns stable-ID Trace Links. Both are optional: built-in Recon remains L0, Code Map alone is L1, Document Map alone is L2, and both maps form L3. Agent-native MCP and explicit project-local JSON/YAML artifacts are supported; unavailable, stale, conflicting, or incompatible providers record Unknown and safely fall back. 343 never auto-installs, configures, contacts, or writes back to these tools, and map results cannot authorize a Change Envelope.

After IO authorizes a formal envelope, run `python scripts/cli.py envelope check --task T-001 --project-dir .`. It checks all Git changes and automatically joins the prove gate when the formal envelope exists; outside or unknown changes fail closed.

For code without reliable tests, use `cli.py characterize plan/capture/verify` to preserve IO-confirmed observable behavior. A captured baseline is automatically re-verified by the prove gate.

Use `cli.py change plan/status/prepare/verify/close` to orchestrate the complete safe-change flow; state is always recomputed from current evidence.

Users can simply say “This is a bug: … please fix it.” They do not need B/T identifiers or CLI commands. The agent discovers the evidence-backed parent task, allocates the next B-ID, and asks only one high-information question when the association is ambiguous. Calling something a bug never bypasses classification.

Internally, use `cli.py bug open/classify/reproduce/status/verify/telemetry/close`. Completion is proven by immutable closing evidence instead of mutating the signed parent contract. After verification, record a separate correction run with `bug telemetry --test-total N --test-passed N`; the original task telemetry remains unchanged.

## 4. Quick Start

### 1. Prepare the Python environment

```bash
# Bash is not required; the public entry point starts with the current Python.
python scripts/cli.py list
```

When PyYAML is missing, YAML-consuming scripts use the Python-native
`_bootstrap.py` path to create or reuse `~/.agentic-agile-343/venv`. The
dependency is installed only when absent; subsequent healthy runs reuse the
environment without invoking pip. Windows, macOS, and Linux share the same implementation.

The Dashboard's `ocusage` dependency is installed once into
`~/.agentic-agile-343/tools/ocusage` during Skill publication and then reused.
When npm is not on PATH, common local Node/npm runtimes are discovered automatically;
you can also install Node.js/npm or set `AGENTIC_AGILE_NPM` explicitly.

Telemetry is independent of the AI host. Any host bridge can write the standard task
snapshot to `governance/telemetry/usage-snapshots/<TASK>.json`, where the workflow
discovers it automatically; `AGENTIC_AGILE_USAGE_SNAPSHOT` remains an explicit override.
Only trustworthy direct task measurements or start/end deltas with matching provider,
counter, project, and task bindings enter task totals. Missing or ambiguous data remains `N/A`.

### 2. Initialize project governance (solo)

```bash
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml
```

### 3. Run the six SCOPE-V control planes

```
Specify  → fill the Intent Contract → Grill-Me decision confirmation → IO signs explicitly (OA must not sign on IO's behalf)
Constrain → fill the Constraint Matrix (6 domains; list MUST first)
Orchestrate → TDD red→green→refactor; write the failing test first per task
Prove ⇄ Evolve → repair insufficient proof and prove again
Verify  → reach a verdict from qualified evidence
Verify → Telemetry → Specify/Constrain/Orchestrate → feed facts into later intent, constraints, or orchestration
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

# Recommended completion entry: after Prove passes, Evidence/Telemetry/Dashboard closure runs automatically
python scripts/cli.py change verify --task T-001 --project-dir .

# Low-level diagnostic / rerun entry
python scripts/cli.py evidence finalize --task T-001 --project-dir .
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
├── scripts/                      # 26 runnable scripts (gates / engine / verification / evidence finalization / telemetry / context / graph)
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
Starting with v1.38.0, project Recon first consumes canonical project-local map artifacts. When a visible CLI is available but its map is missing, Recon initializes IWE within the explicit project boundary and invokes codebase-memory-mcp with `index_repository --repo-path <PROJECT> --persistence true`. Normalized dual maps produce Trace Links automatically; unsupported links remain Candidate/Unknown. `--no-auto-context` disables initialization, and failures fall back to L0.
