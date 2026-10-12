# Implementation Plan — Frontier Model Evaluator

> Status: **APPROVED (G2, 2026-10-10); re-scoped to the demo on 2026-10-12 (D-12..D-14); two providers, Claude and ChatGPT (D-17).** Changes to phases or done-when checks need architect approval.
> Strategy: **local-first, live-last, then deploy read-only.** Everything is built and tested against recorded fixtures. Live model calls happen only in Phase 4, started by the architect on her Mac. The public demo serves those results read-only (D-13).
> Dates: working demo **14 Oct**, course submission **18 Oct**.

## 1. How we work (control surfaces)
The coding agent (Claude Code, or Codex later) is a Level 3 autonomous agent: it chooses its own next steps. We bound it with the four control surfaces:

| Surface | Our control |
|---|---|
| Prompt | One phase per request, naming its tasks and governing spec |
| Context | The four specs + `CLAUDE.md` + this plan. Decisions go into the specs, not the chat. |
| Loop | Checks from §4; the "done when" checks below; mutation checks on key tests; architect review of each phase PR |
| Graph | A single agent, working sequentially. No parallel workers (small project; shared files). |

**Gates:** G1 specs ✔ → G2 plan ✔ → G3 each phase PR reviewed and merged → **G4 live run (architect only)** → **G5 deploy approved** → G6 submission.
**Process (D-14):** one PR per phase; each task is its own commit inside that PR.

## 2. Phases (demo scope)
| Phase | Work | Done when (observable) | Target |
|---|---|---|---|
| **0 Repo and environment** | ✔ 0.1 tooling · ✔ 0.2 backend skeleton · ✔ 0.3 frontend skeleton · 0.4 Makefile (`dev`, `test`, `lint`, `ac-check`) · 0.5 CI (**workflow file needs approval**) · ESLint upgrade | `make test` passes; CI green on a real PR; `make ac-check` lists demo ACs as uncovered | 12 Oct |
| **1 Evaluation engine (fixtures only)** | Model registry + paid-key guard; SQLite schema; task schema + hashing + validator; **18 tasks** (1 per category × tier); adapter interface + recorded-fixture adapters; runner (retries, quota stop/resume, call cap, one active run); checkers + Docker sandbox; single cross-provider judge; scoring; defects; tokens/cost; `make eval` CLI | BE-AC-01..11, 13..17, 23 pass on fixtures; a fixture run of 3 models × 18 tasks gives the expected scores and defects; mutation checks on BE-AC-03, 07, 11, 13; **architect reviews the 18 tasks** | 13 Oct |
| **2 Read API + fit engine** | Demo endpoints (health, models, leaderboard, model detail, defects, results, result, profile-templates, fit); 3 template profiles; read-only mode flag; CORS allow-list | API-AC-01..04 pass for demo endpoints; BE-AC-18..20 pass; read-only mode rejects anything but GET + `POST /fit` | 13 Oct |
| **3 Frontend: 3 screens** | S1 Leaderboard, S2 Model detail (scores by tier, token panel, defects with evidence, drill-down), S4 Fit (templates); loading/empty/error states; fairness note | FE-AC-01..05, 07, 13, 14, 16 pass; architect clicks through Leaderboard → Model → defect → Fit on the seeded DB | 13 Oct |
| **4 Live adapters + live run (G4)** | Real `claude_code_cli` and `codex_cli` adapters (fixture-tested; Gemini dropped, D-17); preflight check; `make smoke` then `make eval`. **Architect runs both on her Mac.** Golden (6) + seeded (6) judge check. | Every mode ready; live results visible locally with reported tokens; SM-3/SM-4 measured with numbers (pass or fail); exact models (OQ-2) recorded in the goal spec | 14 Oct |
| **5 Deploy read-only demo (G5)** | Results snapshot committed; API on Render free tier (`FME_READ_ONLY=1`); frontend on Netlify (free) with the API URL; CORS = Netlify origin only | Public URL shows the real run; scripted checks (routes load, no localhost URLs, no secrets in bundle, CORS rejects other origins); architect's manual click-through | 14 Oct |
| **6 Submission pack** | Design-decision walkthrough + interview prep page (course §4.8/§8.12), delivery record (roadmap, changes from plan, architecture, $0 cost), AC→test traceability, abstract draft, YouTube demo script | Pages live at the demo URL; every form field has a value ready for the architect | 15–16 Oct |

**Post-MVP** (goal-spec §5): Compare, runs from UI, manual mode, review queue, export, history, custom profiles, two judges, full golden set, larger suite, paid-API modes, login.

## 3. Task breakdown
### Phase 0 tasks
- ✔ 0.1 Repo tooling: pre-commit, ruff, mypy, Prettier, gitleaks config (ESLint config moved to 0.3)
- ✔ 0.2 Backend skeleton: FastAPI app, `/api/v1/health`, pytest setup, health tests
- ✔ 0.3 Frontend skeleton: Vite React TS, Tailwind, Vitest, placeholder page that calls `/health`
- 0.4 Makefile: `dev`, `test`, `lint`, `ac-check` (the script scans test names for the AC IDs that are in demo scope)
- 0.5 CI workflow: lint + test for backend and frontend on push and PR (**needs architect approval**: workflow file)
- 0.6 Upgrade the deprecated ESLint pin

Later phases are broken into tasks at the start of each phase and listed in its PR.

## 4. Acceptance criteria → test matrix (demo scope)
Test types: **U** unit · **I** integration (fixture adapters, real DB) · **C** contract · **E** end-to-end (Playwright) · **M** manual / measured · **—** Post-MVP (not tested in the demo).

| AC | Type | AC | Type | AC | Type |
|---|---|---|---|---|---|
| BE-AC-01 | I | BE-AC-11 | U | FE-AC-01 | E |
| BE-AC-02 | U | BE-AC-12 | — | FE-AC-02 | E |
| BE-AC-03 | U | BE-AC-13 | U | FE-AC-03 | E |
| BE-AC-04 | U | BE-AC-14 | U | FE-AC-04 | U (component) |
| BE-AC-05 | I | BE-AC-15 | I | FE-AC-05 | U (component) |
| BE-AC-06 | I | BE-AC-16 | U | FE-AC-06 | — |
| BE-AC-07 | I | BE-AC-17 | U | FE-AC-07 | E |
| BE-AC-08 | I | BE-AC-18 | U | FE-AC-08 | — |
| BE-AC-09 | I (Docker, architect's Mac) | BE-AC-19 | U | FE-AC-09 | — |
| BE-AC-10 | I (Docker, architect's Mac) | BE-AC-20 | U | FE-AC-10 | — |
| BE-AC-21 | M (live, Phase 4) | API-AC-01 | C | FE-AC-11 | — |
| BE-AC-22 | M (live, Phase 4) | API-AC-02 | C | FE-AC-12 | — |
| BE-AC-23 | I (CI scan) | API-AC-03 | C | FE-AC-13 | E |
|  |  | API-AC-04 | I (scan) | FE-AC-14 | E (axe) |
|  |  | API-AC-05 | — | FE-AC-15 | — |
|  |  |  |  | FE-AC-16 | E |

Demo scope: **35 ACs** tested; 9 Post-MVP (BE-AC-12, API-AC-05, FE-AC-06, 08–12, 15). BE-AC-21/22 also get a fixture-based unit test of the *calculation* (agreement rate, catch rate). The pass/fail measurement itself needs the live judge.

## 5. Progress log
| Date | Phase/task | Result | Evidence |
|---|---|---|---|
| 2026-10-09 | Repo created; SPEC.md v0.1 | done | commit 420dc49 |
| 2026-10-10 | SPEC v0.2 zero-cost model; restructured into four specs (v0.3) | G1 approved | PR #1 |
| 2026-10-10 | Decisions D-6..D-11 recorded | merged | PR #2 |
| 2026-10-10 | G2 plan approved by architect | approved | — |
| 2026-10-10 | 0.1 Repo tooling | merged (PR #3) | pre-commit hooks pass; gitleaks finds no leaks in history and catches a planted key; ruff flags planted S105/S602/F401 |
| 2026-10-10 | 0.2 Backend skeleton | merged (PR #4); verified on architect's Mac (Python 3.12.4, 2 passed) | ruff/mypy(strict)/pytest pass; health test fails when endpoint broken; live server returns 200 {"status":"ok"} on 127.0.0.1:8000 |
| 2026-10-10 | 0.3 Frontend skeleton | merged (PR #5) | lint/typecheck/3 tests/build pass; 2 mutation checks caught (1 after strengthening a weak test); headless Chromium shows connected + not-reachable states via Vite proxy |
| 2026-10-12 | Re-scoped to demo (D-12..D-15) for 14 Oct demo / 18 Oct submission | merged | PR #6 |
| 2026-10-12 | Phase 0 finish: 0.4 Makefile + AC check, 0.5 CI, 0.6 ESLint 10 | merged | PR #7; first CI run green (4 jobs) |
| 2026-10-12 | D-16 (min scoring), D-17 (Claude + ChatGPT only) | merged | PR #8 |
| 2026-10-12 | Phase 1 engine: 1.1–1.8 | merged (PR #8, CI green incl. real sandbox image) | 109 tests pass with Docker required; 17/17 Phase 1 ACs covered; mutation checks on BE-AC-03, 07, 11, 13, 15 caught; synthetic demo run via CLI |
| 2026-10-12 | Phase 2: D-18, D-19, 2.1 fit engine, 2.2 read API + OpenAPI snapshot | merged (PR #9) | 155 tests pass (Docker required); API-AC-01..04 + BE-AC-18..20 covered; 7 mutations caught; 26/35 demo ACs covered |
| 2026-10-12 | Phase 3 screens: 3.1–3.6 + sandbox fix | in review | Leaderboard, Model detail (+ result drill-down), Fit; 10 Vitest + 9 Playwright/axe E2E pass; 33/35 demo ACs covered (BE-AC-21/22 are the live run); 11 mutations caught. E2E found a backend defect (Docker daemon down scored as model INCORRECT_CODE) — fixed with regression tests. Access check on architect's Mac: Claude Code 2.1.296 on Claude Pro (Sonnet 5); Codex 0.162.1 signed in with ChatGPT, model gpt-6-luna |
