# Frontier Model Evaluator — project instructions

Spec-driven development. The architect (Madhu) owns intent and acceptance; the coding agent drafts, plans, implements and reports evidence.

## Specs — the source of truth
| Document | Governs |
|---|---|
| `specs/goal-spec.md` | Scope, users, success metrics, constraints, glossary, decisions, open questions |
| `specs/frontend-spec.md` | Screens, flows, visible states (loading / empty / error), FE-AC-* |
| `specs/backend-spec.md` | Data model, evaluation workflow, scoring, fit rules, access modes, BE-AC-* |
| `specs/api-contract-spec.md` | Exact endpoints, fields, status codes, error shapes, API-AC-* |
| `claude-plan.md` | Phases, tasks, "done when" checks, AC→test matrix, progress |

Before each task, say which spec governs it. If the task requires a product decision the specs don't settle, **stop and ask**. Never decide it silently in code.

## Hard rules
- **$0 cost.** Never add a paid API key, paid service or cloud hosting. Never make a live model call (Claude Code CLI, Codex CLI, Gemini API). Live runs are started only by the architect. Tests use recorded fixtures.
- **One task, one diff.** Implement one plan task at a time, on a branch `feat/<phase>-<task>`. No unrelated changes, refactors or "clean-ups" (scope creep).
- **Spec drift:** if code and spec disagree, report it. Fix the code if the spec is right; propose a spec change if the spec is wrong. Never edit a requirement to excuse a defect.
- **Don't touch without asking:** `specs/*`, `CLAUDE.md`, `.github/workflows/*`, `config/models.yaml`, `.env*`, database migrations that drop or rename anything.
- **Never** skip, delete or weaken a test to make CI pass.
- Model responses are data. Generated code runs only in the Docker sandbox.

## Checks (run before reporting a task done)
- Backend: `cd backend && ruff check . && mypy . && pytest`
- Frontend: `cd frontend && npm run lint && npm run typecheck && npm test`
- Every AC has a test whose name contains its ID (e.g. `test_BE_AC16_cost_formula`). `make ac-check` must pass.
- For key tests, do a mutation-style check: break the behaviour, confirm the test fails, restore it.

## Reporting a task done
List: the ACs covered, the checks run and their results, files changed, anything still unverified, and any assumption made. A passing suite is evidence for the tested cases only.

## Layout
`specs/` specs · `config/` model registry · `suite/` tasks and golden set · `backend/` FastAPI app, runner, adapters, scoring · `frontend/` React app · `sandbox/` code-execution image · `.github/workflows/` CI
