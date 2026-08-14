# Release Notes

> 🌐 中文版: [RELEASE_NOTES.md](RELEASE_NOTES.md)

# Agentic Agile 3-4-3 Governance Framework · Open Source Edition v1.46.4

> **Calibrate first, then fight the bosses.** A complete, runnable governance framework for Agentic AI development — fully open source, no reservations. Let AI R&D governance be both offensive and defensive.

- **Version**: `1.46.4`
- **Release date**: 2026-08-12
- **License**: Code/templates MIT · Whitepaper CC BY 4.0
- **Author**: Wang Lijie (无敌哥), AI Governance Architect

## v1.46.4: Verification Gate Fixes (gate_check + change_envelope)

- Fix bytes/str type error in `gate_check.run_python_tests`: `run()` function's `stdout`/`stderr` could be bytes (from `run_command`), causing `join` to fail. Now ensures str is always returned.
- Fix YAML parsing in `change_envelope._load`: support frontmatter format (`---`-wrapped YAML + Markdown content), no longer fails due to Markdown table `|` characters.

## v1.46.3: Telemetry Task-ID Resolution Enhancement (telemetry_tracker)

- `telemetry_tracker`'s task-ID regex `TASK_RE` is relaxed to accept namespace-prefixed task IDs (e.g. `PROJ-T-123`) instead of only `T-XXX`, supporting multi-project / multi-tenant task identifiers.
- New helpers `_artifact_task_id` and `_find_task_artifact` parse the task ID from Evidence Bundle / Intent Contract files, so metrics correctly associate with file-naming conventions or prefixed task IDs rather than failing to merge due to ID shape differences.
- Reuses `runtime_context.load_trusted_verification_context` for a unified trusted-verification entry point.

## v1.46.2: Unified Test Count Semantics (T-146 close-out)

- `total` is now uniformly `passed + failed`, excluding skipped/ignored/Skipped across all four runners (vitest/jest/cargo/dotnet), aligned with backend trust validation. Previously vitest's `numTotalTests` included skipped (e.g. DB-gated tests skipped via `describe.skipIf(!AGENTIC_DB_PATH)`), so `passed < total` rejected the context and degraded single-task dashboard metrics.
- Test status is now derived from the `failed` count instead of the process exit code. A beforeAll failure (e.g. adminMembers seed) that exits 1 while business tests all pass no longer reports a false FAIL.
- Regression: 292 tests green (full suite with `PYTHONPATH=scripts`).

## v1.45.1: Host-tool identity passthrough at closure (T-149)

- Fixes the tail of T-148 AC-004 (cross-tool identity): the host tool identity was not passed through to the token probe at closure, so `cost.token_measurement.host_tool` degraded to `other` and the token client was conflated with the project identity.
- `change verify` now forwards `--host-tool` / `--token-client` end to end: `change_workflow.run_stage` → `evidence_workflow.finalize_evidence` → `telemetry_workflow.py`'s `collect_token_measurement`, so the per-task `host_tool` reflects the real caller (e.g. `codex`).
- `evidence_workflow.finalize_evidence` gains `host_tool` / `token_clients` parameters; `_build_collector_command` injects `--host-tool` / `--token-client` into both the prepare and final-persist commands. Default behavior is unchanged when omitted, preserving backward compatibility.
- 8 TDD tests cover entry passthrough, command injection, default compatibility, and closure chaining. `change verify --host-tool codex` closed with 243/243 tests green, a `VERIFIED` formal-verification chain, and `telemetry-T-149.json` reporting `host_tool=codex`, `source=measured:ocusage:codex` (real probe, not hardcoded).

## v1.45.0: Trustworthy cross-AI-tool telemetry and unavoidable closure

- Telemetry records the host AI tool, token client, and stable project identity separately instead of conflating WorkBuddy, Codex, Claude Code, or other hosts with usage data sources.
- Token usage follows a structured measurement contract. A project daily cumulative snapshot is baseline evidence only; task and project totals accept only same-client, same-project, same-day start/end deltas. Missing, ambiguous, or cross-day data remains `UNKNOWN/N/A`.
- `change prepare` captures the token baseline. `change verify` chains Prove, Evidence, Telemetry, Intent Graph feedback, and the Closing Gate; any failure is `BLOCKED`, while success returns `CLOSED`.
- The first failed formal Prove enters the append-only ledger. Harness recovery with `--task` records constraint failure, resolution, and reverification automatically, removing manual auto-heal counts.

## v1.44.9: Governance verifier robustness fixes

- Database contract queries close cursors and connections on both success and failure; a value-only expectation now fails when the query returns no rows.
- Vitest/Jest pending tests are no longer reported as errors, and dotnet `Failed!` summaries retain passed, failed, and total counts.
- Telemetry merging uses the normal module-level import; the Bug gate continues past damaged telemetry files while emitting an explicit diagnostic.

## v1.44.8: Tool-independent local Node/npm discovery

- When explicit configuration and PATH are unavailable, the Token tool bootstrap discovers common local runtimes from AI tools, nvm, fnm, Volta, Homebrew, and similar locations.
- A candidate must provide sibling `node` and `npm` executables, with newer versions preferred; discovery still leads to one private installation that later runs reuse directly.

## v1.44.7: ocusage 3.9 project telemetry protocol

- Adapts to the current CLI by removing the retired `--project` option and selecting exact project Token metrics from JSON `byProject` data.

## v1.44.6: Explicit Node launch for Token CLI

- The Dashboard launches the private `cli.mjs` with a fixed absolute Node path, removing runtime PATH and `.bin` wrapper dependencies.

## v1.44.5: Symlinked npm launcher fix

- Preserves the directory of the configured npm entry point instead of resolving its symlink into npm internals, keeping the sibling Node executable available to `env node`.

## v1.44.4: Private npm bootstrap PATH compatibility

- When npm is provided through `AGENTIC_AGILE_NPM` or a non-standard location, its sibling Node directory is added to the installer subprocess PATH.
- Fixes isolated Node environments where npm is discoverable but its `env node` launcher cannot start.

## v1.44.3: One-time Token telemetry tool bootstrap

- Installs `@geeeger/ocusage` once into `~/.agentic-agile-343/tools/ocusage`; later Dashboard runs reuse it without invoking npm.
- Skill publication and Dashboard runtime share one bootstrap, repairing only a missing or damaged private tool.
- Missing npm does not block publication or other telemetry, but now produces an explicit diagnostic instead of silent blank Token data.

## v1.44.2: Stable runtime and Skill release pipeline

- The Unix bootstrap wrapper no longer clears or deletes the persistent venv or upgrades pip; `_bootstrap.py` is the single lifecycle implementation.
- Token measurement invokes an installed `ocusage` executable and no longer uses `npx --yes` for implicit package resolution or download.
- Adds `skill_release.py` for one-command version updates and validation, atomic local installation from one release staging tree, and a validated public ZIP from that same tree.

## v1.44.1: Persistent venv reuse performance fix

- `_bootstrap.py` re-execs immediately when the target venv can already import PyYAML, without repeating `pip install`.
- The Telemetry Harness shares the same health probe and cross-platform venv path, installing only when the dependency is first missing.
- Regression tests lock down healthy-venv reuse without recreation or pip invocation.

## v1.44.0: Single sources for governance contracts and test results

- `gov_common.py` owns `.yaml/.yml/.md` discovery, task IDs, and normalized parsing; duplicate formats for one task fail closed.
- Triangulation, Freshness, Crop, Verify Contract, and Self Consistency consume the same contract semantics.
- Gate, Harness, and Telemetry use `runtime_context.parse_test_output()` for all eight supported runner families.

## v1.43.0: Secure governance predicate execution

- Replaces dynamic `eval/exec` governance checks with a side-effect-free AST allowlist predicate interpreter.
- Legacy Python/assert/setup checks fail closed, with constraints templates and public guidance migrated.
- Adds T-146 security regression coverage for malicious expressions, path traversal, and default predicates.

## v1.42.0: Map-first Recon and incremental long-history governance

- IWE and codebase-memory-mcp queries now enforce item, token, byte, and stage-timeout budgets; full-map exports are prohibited.
- Task Recon reads bounded map candidates first; without a usable map, L0 performs one bounded `rg` fallback and excludes provider databases and caches.
- Shared/local and fresh/stale/damaged map states have deterministic consume, rebuild, degrade, and recovery paths.
- The JSONL event ledger gains a rebuildable SQLite side index; project telemetry stores aggregation facts in stable run summaries instead of reopening historical run files.
- Evidence finalize prepares verification and then performs one final persistence, eliminating the intermediate project dashboard.
- Automated scale budgets cover 12,000-file Map-first Recon, 10,000 events, and 10,000 run summaries.

## v1.41.0: Runtime deduplication and shared project snapshots

- Gate, Harness, and Telemetry consume one `TestExecutionPlan`; Verification Context records the actual argv and verifies its checksum.
- `nfr:test_run` reuses a trusted Verification Run Context instead of rerunning tests through Harness.
- A workflow-scoped `ProjectSnapshot` shares file inventory, Git revision, and source digest work.
- Harness NFR validators share source inventory and content caching; the 12,000-file five-check benchmark drops from about 2.96s to about 0.59s.
- Crop Context builds map context once and calls code discovery in-process; the current-project benchmark drops from about 0.81s to about 0.04s.

## v1.40.1: Evidence finalization performance governance

- Removes hidden `harness tests` reruns; the trusted Verification Run Context is the sole test snapshot.
- Uses metrics-only refresh after the formal verification event.
- Adds write preflight, stage progress, and elapsed timing.
- Discloses external, internal, and total test execution/reuse counts.

## v1.40.0: Native dual-map adapters and automatic Agent context injection

- Recon normalizes structured IWE and codebase-memory-mcp results into deterministic standard map artifacts.
- `crop_context.py` injects bounded L0-L3 Document Map, Code Map, candidate Trace Links, and Unknown state by default.
- Team mode consumes `authority: ci` snapshots first and writes missing-map fallback only under `.local`.
- Stale, damaged, or failed providers disclose impact and manual recovery actions while safely degrading.
- **Official site**: <http://agentic.iloveagile.me/about> · WeChat `iloveagile`

---

## v1.38.0 Changes

- T-139 makes project Recon discover and consume project-local dual maps by default. If a visible tool has no project map, Recon initializes IWE within the project and requests a persisted codebase-memory-mcp project index.
- Normalized dual maps automatically produce requirement-to-code-to-test Trace Links; semantic guesses remain Candidate/Unknown rather than VERIFIED.
- Adds `--no-auto-context` and `--persistence true|false`. Provider failures still fall back to L0, with no automatic installation, global configuration mutation, or project-external writes.

## v1.39.0 Changes

- T-140 adds append-only `formal_verification` facts with `VERIFIED`, `CONDITIONAL`, and `BLOCKED` results.
- The first formal result is immutable for first-pass metrics; a later VERIFIED result cannot turn an initial CONDITIONAL attempt into first-pass success.
- `must_total=0` now renders `NOT_APPLICABLE/N/A` instead of the misleading 100%.

## v1.39.1 Changes

- T-141 adds a Verification Run Context so trusted test results for the same project, revision, and argv are reused across Prove, Evidence, and the second telemetry pass.
- Missing, stale, changed, mismatched, or unverifiable contexts trigger a fresh test run, with execution/reuse counts and reasons exposed in telemetry.

## v1.37.0 Changes

- T-138 adds optional Context Providers to Recon: IWE is recommended for the Document Map, codebase-memory-mcp for the Code Map, and 343 normalizes stable-ID Trace Links.
- Supports L0-L3 progressive enhancement, Agent-host capability disclosure, and project-local JSON/YAML artifacts. Missing, invalid, out-of-boundary, conflicting, or stale providers fail closed and fall back.
- External relations retain provider, query time, revision, classification, and evidence. They never become runtime facts or authorize installation, configuration, network access, write-back, or Change Envelope expansion.

## v1.36.2 Changes

- Upgraded the second half of SCOPE-V from “the agent should remember to call it” to workflow-enforced closure: after the Prove gate passes, `change verify` now automatically runs `evidence finalize` and generates task telemetry, project telemetry, and dual dashboards.
- If `evidence finalize` fails, `change verify` returns BLOCKED instead of only printing a recommended command or claiming VERIFIED. Regression tests cover both automatic closure and failure blocking.

## v1.36.1 Changes

- `collect_telemetry.py --rebuild` now remains compatible with v1.33 and earlier run files: absent `status` means trusted legacy input, while explicit `UNKNOWN/NOT_APPLICABLE` is still excluded.
- Added a regression test for legacy run aggregation. T-137 full regression passes 156/156, and `--rebuild` no longer returns `INSUFFICIENT_DATA`.

## v1.36.0 Changes

- T-137 adds `scripts/command_runner.py` as the unified command execution contract: argv + `shell=False` by default, with explicit `powershell` / `cmd` / `posix` dialects when shell is necessary.
- `_bootstrap.py` now uses Python-native venv/pip bootstrapping, including Windows `Scripts/python.exe` and Unix `bin/python`; Bash is no longer a prerequisite for dependency setup.
- `scripts/token_usage.py` becomes the main token probe; shell scripts are Unix wrappers only, and unavailable tools produce UNKNOWN/UNAVAILABLE instead of fabricated estimates.
- `gate_check.py`, `harness.py`, `verify_contract.py`, `self_consistency_check.py`, and default templates now use structured commands or Python checks and fail closed on unsupported shells.
- A real `windows-latest` CI matrix covers Python 3.10/3.11/3.12 focused tests and full regression; no requirements.txt change.

## v1.35.0 Changes

- T-136 adds a Measurement Contract and append-only execution event ledger for trustworthy P0 metrics.
- UNKNOWN is no longer rendered as 0%; no constraint failures is NOT_APPLICABLE, project aggregation reports coverage, and certificate eligibility fails closed with INSUFFICIENT_DATA.
- Assigned/completed are derived from signed contracts and passing Evidence; first pass and auto-heal require formal event history.
- The main telemetry workflow is now Python-native and works without Bash on Windows; the shell script is only a Unix wrapper.

## v1.34.0 Changes

- T-135 adds `cli.py evidence finalize`, making completion of a task Evidence Bundle and telemetry collection one atomic handoff.
- After completing `EB-T-XXX.md`, the agent acts without another user reminder and reuses `quick_telemetry.sh` for real tests, Harness checks, measured tokens, and `collect_telemetry.py`.
- Success requires task telemetry, project telemetry, the project dashboard, and `dashboard-T-XXX.html`; missing output, duplicate task entries, collector failure, or Evidence mutation fails closed.
- Repeated finalization is idempotent and does not duplicate the task in project `runs[]`; Evidence approval remains a human boundary.
- The closing gate remains read-only and never hides test, telemetry, or file-writing side effects inside a checker.
- Added nine focused tests; the full 121/121 regression suite passes and `requirements.txt` is unchanged.

## v1.33.0 Changes

- T-134 aligns SCOPE-V to six control planes, `S / C / O / P⇄E / V`, rather than placing Telemetry beside them.
- Prove and Evolve form the fast evidence loop; `V → Telemetry → S/C/O` is the slow feedback loop into intent, constraints, and orchestration.
- `gate_check.py` now exposes one control-state mapping for pre/coding/prove/closing/bug while preserving all five gates, their enforcement strength, CLI, and exit codes.
- The three autonomous mechanisms are explicitly cross-cutting governance mechanisms, not one-to-one stage assignments.
- Added six focused model/interface tests; the full 112/112 regression suite passes and `requirements.txt` is unchanged.

## v1.32.0 Changes

- T-127 adds `release plan/check/status/record` and a Release Manifest binding task contracts, Git commit, artifact SHA-256/size, configuration, Evidence Bundle, Telemetry, Verification Plan, approval, and rollback.
- Implements the minimum Build Once, Verify Once, Promote Many invariant; artifact, commit, configuration, task-evidence, or promotion drift invalidates old readiness.
- Readiness is always `READY_FOR_HUMAN_RELEASE`, never automatic RELEASED. The agent performs no commit, tag, push, build, upload, deployment, or production write.
- released / rolled_back facts are append-only and require project-local external evidence plus a qualified actor. Duplicate events are idempotent and existing bindings remain immutable.
- Added `RELEASE_MANIFEST` natural-language routing and a proof-carrying release guide; 16/16 focused tests pass with 90% standard-library measured line coverage for the new module.
- The full 106/106 regression suite passes; requirements.txt is unchanged.

## v1.31.0 Changes

- T-126 adds `verification plan/check/status` and a Verification Plan template, selecting minimum layers and independence by low / medium / high / safety-critical risk without blindly enabling every layer.
- Mechanically detects missing layers or evidence, copied same-source reports, insufficient independence, stale/task-mismatched evidence, path attacks, LLM-only key proof, and AI-signed human acceptance.
- Preserves PASS / FAIL / UNKNOWN / CONDITIONAL / ESCALATED; CONDITIONAL requires a condition, owner, deadline, and re-verification action.
- Authorized plans automatically join the prove gate while projects without a plan remain compatible. Planning is dry-run by default, apply creates a non-overwriting DRAFT, and no arbitrary commands are executed.
- Added natural-language `VERIFICATION_PLAN` routing, a reference guide, and 12 focused tests; the full 90/90 regression suite passes.

## v1.30.3 Changes

- M-007 adds one natural-language capability-routing matrix for v1.25—v1.30.
- Frontmatter now covers project Recon, risk initialization, gate maintenance, task Recon, Change Envelope, Preserve, safe change, and Bug requests.
- Added conflict resolution: prefer the most specific route, investigate read-only when evidence is missing, and ask one question only when routing remains ambiguous.
- Moved version and author extension fields into schema-valid `metadata`; Codex skill validation now passes.
- Added a routing reference and mechanical test; the full 78/78 regression suite passes.

## v1.30.2 Changes

- M-006 adds natural-language bug, defect, regression, and repair triggers to the skill frontmatter and trigger section.
- Users only describe the issue and request a fix; the agent discovers the parent task and allocates the next B-ID.
- Ambiguous evidence causes one high-information question, while a user-supplied bug label never bypasses classification or real RED.
- Added a mechanical natural-language trigger test; the full 77/77 regression suite passes.

## v1.30.1 Changes

- M-003: parent completion now comes from the evidence bundle, task telemetry, and Intent Graph instead of mutating a signed contract.
- M-004: `bug verify` requires a RED record with real RED evidence; `bug close` requires VERIFIED.
- M-005: added `bug telemetry`, writing a separate `telemetry-B-XXX.json` correction run while preserving original task telemetry.
- All three fixes passed real RED-to-GREEN maintenance evidence and the full 76/76 regression suite.

## v1.30.0 Changes

- Added B-XXX Bug Records and bug open/classify/reproduce/status/verify/close.
- Six issue classes route to bug repair, contracts, maintenance, environment investigation, or IO escalation.
- Only traceable implementation regressions with unchanged boundaries and a real RED enter direct repair.
- Verify/close reuse change verify and the existing bug gate; five focused tests added and all 73 pass.

## v1.29.0 Changes

- Added `change plan/status/prepare/verify/close` as the unified safe-change entry point.
- Planning reuses task Recon, defaults to dry-run, and never overwrites an applied plan.
- State is recomputed from contracts, Unknowns, envelopes, Preserve baselines, and mechanical gates, with one next action.
- Prepare/verify/close delegate to pre/prove/closing without duplicating gate semantics.
- Five focused tests added; all 68 regressions pass.

## v1.28.1 Changes

- M-001: `quick_telemetry.sh` now discovers real unittest totals and passed counts for both package and plain test directories.
- M-002: `change_envelope.py` and `characterize.py` now invoke the shared bootstrap and retry when PyYAML is initially unavailable.
- Both fixes passed maintenance eligibility, real RED-to-GREEN, evidence, telemetry, and closure checks.
- Two focused tests added; all 63 regressions pass.

## v1.28.0 Changes

- Added `characterize plan/capture/verify` for Preserve behavior baselines in existing code.
- Preserve behavior must come from IO confirmation or existing tests; agents cannot invent assertions.
- Array commands, shell=False, timeouts, sensitive-output rejection, and configuration fingerprints constrain execution.
- Reports SAME / CHANGED / UNVERIFIABLE and automatically joins the prove gate when captured.
- Seven focused tests added; all 61 regressions pass.

## v1.27.1 Changes

- Added `cli.py envelope check` to compare an authorized Change Envelope with actual Git changes.
- Covers staged, unstaged, untracked, deleted, and both sides of renamed paths.
- Protected paths win over allowed paths; Unknown, drafts, task mismatch, unsafe paths, and Git failures fail closed.
- Automatically joins the prove gate when a formal envelope exists while preserving compatibility otherwise.
- No force, skip, or automatic expansion; nine focused tests and all 54 regressions pass.

## v1.27.0 Changes

- Added `python scripts/cli.py recon task` for task-scoped, read-only impact discovery in existing codebases.
- Separates facts from reference/test/public-entry candidates and unknown runtime relationships.
- Lightweight adapters cover Python, JavaScript/TypeScript, C/C++, Java/JSP, with basic Go, Rust, and Shell support.
- Missing, directory, and out-of-project targets fail closed; output defaults to stdout.
- Suggested Change Envelopes remain `DRAFT_NOT_AUTHORIZED` and never grant modification authority.
- Added eight cross-language and boundary tests; all 45 local regression tests pass with no new dependency.

## v1.26.1 Changes

- Added `cli.py maintain open/check/close` for gate self-governance.
- Low-risk deterministic defects use `M-XXX` records instead of repeated business-contract addenda.
- All six eligibility checks must explicitly pass; Unknown, weaker gates, changed signing semantics, or expanded permissions require a signed contract.
- Enforces real RED→GREEN, full regression, Maintenance Evidence, telemetry, and Intent Graph lessons.
- Executes command arrays with `shell=False`; missing or unexecutable commands cannot impersonate RED.
- Added 12 local focused tests; governance records and tests remain excluded from the public package.

## v1.26.0 Changes

- Added the unified risk-driven entry point `python scripts/cli.py init`; dry-run is the default and only `--apply` writes.
- Classifies new / existing-small / legacy-complex / multi-module projects; existing projects automatically include read-only Recon.
- Evaluates seven risk domains and retains Unknown without downgrading governance.
- Plans the minimum artifacts for five profiles, never overwrites existing files, and keeps generated contracts PENDING.
- Fixed negative-context handling in the signing gate while preserving rejection of real proxy signing.
- Added local TDD regression tests; `governance/` and `tests/` remain excluded from the public package.

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

- Python 3.10+ (`_bootstrap.py` uses Python-native venv/pip setup when PyYAML is missing)
- Node / npx optional (for `token_usage.py` to call `@geeeger/ocusage`; missing tools leave the metric UNKNOWN)
- No external services, no network dependency, no API key required

## 5. Quick Start

```bash
# 1. Prepare environment (Bash is not required)
python scripts/cli.py list

# 2. Initialize project governance
mkdir -p governance/contracts governance/evidence governance/telemetry/runs
cp templates/Template_Intent_Contract.yaml governance/contracts/Intent_Contract_T-001.yaml
cp templates/Template_Constraint_Matrix.md   governance/Constraint_Matrix.md
cp templates/Template_Constraints.yaml        governance/constraints.yaml

# 3. SCOPE-V loop + 5 mechanical gates (hard blocking)
python scripts/gate_check.py --gate pre --task T-001 --project-dir .
python scripts/verify_contract.py --task T-001 --project-dir .
python scripts/harness.py check --all
python scripts/cli.py evidence finalize --task T-001 --project-dir .
```

For fuller instructions, see [`README.md`](README.md).

## 6. Upgrading from the Old Community Edition

- Users on the old Community Edition (v1.0.0-community): just overlay this edition onto `scripts/`, `templates/`, `references/`, `assets/`, `SKILL.md`. Your existing `governance/` contracts and constraint matrices need no rebuild.
- `build_community_ed.sh` has been removed — no longer needed.

## 7. Known Limitations (Honest Caveats)

1. **Single example**: only `T-001` (a neutral example) for now — PRs adding more scenarios welcome.
2. **Token measurement depends on ocusage**: `token_usage.py` calls `@geeeger/ocusage` through npx; unavailable tools return UNKNOWN/UNAVAILABLE instead of fabricated estimates.
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
