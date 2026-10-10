# Implementation Plan — Frontier Model Evaluator

> Status: **DRAFT — not approved.** No implementation starts until the four specs are approved (G1) and this plan is reviewed and approved (G2).
> Strategy: **local-first, live-last.** Everything is built and tested against recorded fixtures. Live model calls come only in Phase 7, started by the architect.

## 1. How we work (control surfaces)
The coding agent (Claude Code, or Codex later) is a Level 3 autonomous agent: it chooses its own next steps. We bound it with the four control surfaces:

| Surface | Our control |
|---|---|
| Prompt | One plan task per request, naming its phase, task ID and governing spec |
| Context | The four specs + `CLAUDE.md` + this plan. Decisions go into the specs, not the chat. |
| Loop | Plan mode before each phase; checks from §4; the "done when" checks below; architect review of each diff |
| Graph | A single agent, working sequentially. No parallel workers in v1 (small project; shared files). |

**Gates:** G1 specs approved → G2 plan approved → G3 each phase's "done when" checks reviewed → G4 first live run (architect only) → G5 v1 release.

## 2. Phases
| Phase | Work | Done when (observable) |
|---|---|---|
| **0 Repo and environment** | Tooling (ruff, mypy, ESLint, pre-commit, gitleaks), `backend/` FastAPI with `GET /api/v1/health`, `frontend/` Vite React placeholder, `Makefile` (`dev`, `test`, `ac-check`), CI on push/PR running lint + tests | Both servers run locally and respond; `make test` passes; CI is green on a real PR; `make ac-check` lists every AC as uncovered |
| **1 Backend foundation** | Model registry + validation + paid-key guard; SQLite schema + Alembic migration; task schema, hashing and suite validator; preflight endpoint with stubbed checks | BE-AC-01..04 and API-AC-03 pass; deleting the paid-key guard makes BE-AC-03 fail (mutation check) |
| **2 Evaluation engine (fixtures only)** | Adapter interface + fake and recorded-fixture adapters; runner with retries, quota pause/resume, call cap and one-active-run rule; deterministic checkers; Docker sandbox; judge assignment and combining; scoring; defects; token/cost calculation | BE-AC-05..17 pass on fixtures; a fixture run of 3 models × 6 tasks produces the expected scores and defects; mutation checks on BE-AC-07, 11, 13 |
| **3 Task suite and golden set** | Author 36 tasks (2 per category × tier) with checkers and rubrics; golden-set and seeded-defect files (sizes per OQ-1) | The suite validator passes (BE-AC-04); **the architect has reviewed every task** and found no confidential data; golden labels are recorded by the architect |
| **4 Read API + frontend core** | All read endpoints per contract; S1 Leaderboard, S2 Model detail, S3 Compare, S7 History, on a seeded database | API-AC-01/02 contract tests pass for read endpoints; FE-AC-01..06 pass; the architect clicks through the main journey on the seeded DB |
| **5 Runs, review, fit and export** | Run endpoints + S5 (preflight, progress, manual queue); review endpoints + S6; profiles, templates and fit engine + S4; export | BE-AC-18..20, FE-AC-07..13, 15 and 16, API-AC-05 pass; a fixture run started from the UI completes, pauses on a simulated quota, and resumes |
| **6 Local hardening** | Accessibility, keyboard navigation, all loading/empty/error states, secret scan, AC traceability gate in CI | FE-AC-14, API-AC-04 and BE-AC-23 pass; `make ac-check` shows **every AC covered**; deferred items are listed explicitly |
| **7 Live adapters and first live run (G4)** | Real `claude_code_cli`, `codex_cli` and `gemini_free_api` adapters with recorded-fixture tests; `make smoke` (1 task per category per model). **Architect runs it.** Then the full run. | Preflight shows every mode ready; the smoke run's results appear in the UI with reported tokens; the full run completes (possibly across quota windows); exact models (OQ-2) are recorded in the goal spec |
| **8 Evaluate the evaluator** | Judge calibration (golden set), seeded-defect check, reproducibility run; write `docs/evaluation-report.md`; feed findings back into the specs | SM-2, SM-3 and SM-4 measured and reported (pass or fail, with numbers); any spec changes are recorded as decisions |

Deferred (post-MVP, goal-spec §5): paid-API modes, user-uploaded tasks, login, hosting.

## 3. Task breakdown
Each phase is broken into tasks of about one reviewable diff each, written into this section at the start of that phase (in plan mode) and approved before coding.

### Phase 0 tasks (proposed)
- 0.1 Repo tooling: pre-commit, ruff, mypy, ESLint, Prettier, gitleaks config
- 0.2 Backend skeleton: FastAPI app, `/api/v1/health`, pytest setup, one health test
- 0.3 Frontend skeleton: Vite React TS, Tailwind, Vitest, placeholder page that calls `/health`
- 0.4 Makefile: `dev`, `test`, `lint`, `ac-check` (the script scans test names for AC IDs listed in the specs)
- 0.5 CI workflow: lint + test for backend and frontend on push and PR (**needs architect approval**: workflow file)

## 4. Acceptance criteria → test matrix
Test types: **U** unit · **I** integration (fixture adapters, real DB) · **C** contract · **E** end-to-end (Playwright) · **M** manual / measured.

| AC | Type | AC | Type | AC | Type |
|---|---|---|---|---|---|
| BE-AC-01 | I | BE-AC-11 | U | FE-AC-01 | E |
| BE-AC-02 | U | BE-AC-12 | U | FE-AC-02 | E |
| BE-AC-03 | U | BE-AC-13 | U | FE-AC-03 | E |
| BE-AC-04 | U | BE-AC-14 | U | FE-AC-04 | U (component) |
| BE-AC-05 | I | BE-AC-15 | I | FE-AC-05 | U (component) |
| BE-AC-06 | I | BE-AC-16 | U | FE-AC-06 | E |
| BE-AC-07 | I | BE-AC-17 | U | FE-AC-07 | E |
| BE-AC-08 | I | BE-AC-18 | U | FE-AC-08 | U (component) |
| BE-AC-09 | I (Docker) | BE-AC-19 | U | FE-AC-09 | E |
| BE-AC-10 | I (Docker) | BE-AC-20 | U | FE-AC-10 | E |
| BE-AC-21 | M (live, Phase 8) | API-AC-01 | C | FE-AC-11 | E |
| BE-AC-22 | M (live, Phase 8) | API-AC-02 | C | FE-AC-12 | E |
| BE-AC-23 | I (CI scan) | API-AC-03 | C | FE-AC-13 | E |
|  |  | API-AC-04 | I (scan) | FE-AC-14 | E (axe) |
|  |  | API-AC-05 | I | FE-AC-15 | E |
|  |  |  |  | FE-AC-16 | E |

BE-AC-21/22 also get a fixture-based unit test of the *calculation* (agreement rate, catch rate). The pass/fail measurement itself needs live judges.

**Architect action:** review this table. Each row should state the evidence you will accept.

## 5. Progress log
| Date | Phase/task | Result | Evidence |
|---|---|---|---|
| 2026-10-09 | Repo created; SPEC.md v0.1 | done | commit 420dc49 |
| 2026-10-10 | SPEC v0.2 zero-cost model; restructured into four specs (v0.3) | awaiting G1 | PR #1 |
