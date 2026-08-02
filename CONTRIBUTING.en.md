# Contributing Guide

> 🌐 中文版: [CONTRIBUTING.md](CONTRIBUTING.md)

Thanks for wanting to help build the **Agentic Agile 3-4-3 Open Source Edition**!

This repository is a complete, runnable governance framework for Agentic AI development — fully open source, no reservations. Contributions in any direction are welcome.

---

## 1. What's Welcome

- 🐛 **Bug fixes**: script errors, wrong template fields, incorrect doc commands, examples that don't run, etc.
- 📝 **Docs & example enhancements**: add scenarios to `examples/`; expand `references/` reading; fix typos / dead links.
- 🌐 **Translations**: Chinese ↔ English bilingual alignment (keep terms consistent: 意图契约 / Intent Contract, 约束矩阵 / Constraint Matrix, SCOPE-V, …).
- 🧩 **Capability enhancements**: new gate rules, NFR validators, telemetry dimensions, context-pruning strategies, graph-engine scheduling strategies, etc.
- ✅ **Tests & smoke**: add unit tests for `scripts/`; let CI run `gate_check.py`, `verify_contract.py`, `harness.py`.

## 2. Eat Your Own Dog Food (Dog-food the 3-4-3)

Before submitting, make your change itself conform to SCOPE-V:

1. **Specify**: in the PR description, state clearly "what changed / what is deliberately not changed / non-goals".
2. **Constrain**: follow this repo's conventions — pure standard library + `pyyaml` (optional; degrades to MD-only when missing); scripts go in `scripts/`; templates go in `templates/`; no new runtime deps.
3. **Orchestrate / Prove**: after `bash scripts/ensure_py_env.sh`, confirm `python scripts/gate_check.py --gate pre --task T-001 --project-dir .`, `python scripts/harness.py check --all`, and `python scripts/verify_contract.py --task T-001 --project-dir .` don't error.
4. **Verify**: include one line in the PR description — "I verified ____".

## 3. Submission Flow (GitHub Flow)

```bash
# 1. Clone your fork
git clone <your-fork>
cd agentic-agile-343-community-ed

# 2. Branch (semantic naming)
git checkout -b fix/gate-check-signed-detection

# 3. Change + local check
bash scripts/ensure_py_env.sh
python scripts/gate_check.py --gate pre --task T-001 --project-dir .
python scripts/harness.py check --all

# 4. Commit & push
git add -p
git commit -m "fix: gate_check stricter on placeholder signatures"
git push -u origin fix/gate-check-signed-detection

# 5. Open a PR using the template below
```

### Suggested PR description structure

```markdown
## Summary
<one line on what changed>

## Scope (SCOPE-V · Specify)
- Goal:
- Non-goals (explicitly not doing):

## Verification (Verify)
- [ ] `bash scripts/ensure_py_env.sh` passes
- [ ] `python scripts/gate_check.py --gate pre --task T-001 --project-dir .` passes
- [ ] `python scripts/harness.py check --all` passes
- [ ] new/changed scripts have minimal smoke
```

## 4. Code & Style Conventions

- **Language**: scripts in Python 3.10+; shell scripts in `bash` with shebang `#!/usr/bin/env bash` and `set -uo pipefail`.
- **Dependencies**: standard library only + optional `pyyaml`; if a new dep is truly needed, explain the rationale and fallback strategy in the PR (preserve "runs out of the box").
- **Paths**: no hardcoded absolute paths; overridable via env vars.
- **Chinese-first**: comments & docs in Simplified Chinese; keep methodology terms in English (SCOPE-V, DoD, TDD…).
- **Commit messages**: follow Conventional Commits (`fix:` / `docs:` / `feat:` / `chore:` …).

## 5. License

- Code & templates: **[MIT](LICENSE)** — free to use, modify, distribute; keep the copyright notice.
- Whitepaper (`docs/whitepaper/`): **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)** — redistribution / derivative works must attribute **Wang Lijie (无敌哥)**.
- Opening a PR means you agree to release your contribution under the above licenses.

---

Questions? Come chat in the community: <http://agentic.iloveagile.me/about> · WeChat `iloveagile` (note "Agentic Agile"). If you resonate with the philosophy, sign the *Agentic Agile Manifesto* on the official site.
