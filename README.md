# Frontier Model Evaluator (FME)

A web application that evaluates frontier LLMs and helps teams decide which model fits the application they are building or testing.

- **Rates** each model 1–5 per capability category (code generation, reasoning, structured output, test design, long-context faithfulness, tool use)
- **Highlights token usage and cost** per task across Simple / Mid / Complex tiers
- **Lists defects** found in each model, with type, severity and evidence
- **Use-case fit**: click any model, or apply a profile of your app's needs, to get a Recommended / Conditional / Not recommended verdict with reasons

## How this project is built

This repo follows **spec-driven development** with a **Level 3 (conditional) autonomy** setup for AI coding agents:

```
Specify → Plan → Implement → Verify → Iterate
```

Structure follows the IISc Agentic AI course's SDD method (four specifications, a reviewed plan, project instructions):

- [`specs/goal-spec.md`](specs/goal-spec.md): problem, users, MVP scope, success metrics, constraints, glossary, decisions
- [`specs/frontend-spec.md`](specs/frontend-spec.md): screens, flows, loading/empty/error states
- [`specs/backend-spec.md`](specs/backend-spec.md): data model, evaluation workflow, scoring, fit rules, $0 access modes
- [`specs/api-contract-spec.md`](specs/api-contract-spec.md): exact endpoints, fields and error shapes
- [`claude-plan.md`](claude-plan.md): phases with observable "done when" checks and the AC→test matrix
- [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md): instructions for the coding agent (scope rules, checks, what needs approval)

## Status

| Gate | Status |
|---|---|
| G1 Specs approved | ✔ (v1.0, demo scope D-12) |
| G2 Plan approved | ✔ `claude-plan.md` |
| G3 Phase PRs | Phases 0–2 merged; Phase 3 (screens) and Phase 4 (live adapters) in review |
| G4 Live run | Planned for 14 Oct, run by the architect (see below) |
| G5 Deploy | After G4, with approval |

## Zero-cost by design

v1 runs at **$0 extra cost**. Models are reached through the owner's existing subscriptions and free tiers, never paid API keys:

| Provider | Access |
|---|---|
| Anthropic | Claude Code CLI (headless), signed in with Claude Pro |
| OpenAI | Codex CLI (`exec --json`), signed in with ChatGPT Go |

Live evaluations run locally on the owner's computer. CI uses recorded fixtures only. See `specs/backend-spec.md` §3.

## Live run (architect only, Gate G4)

Run these on your Mac, from the repo root, one at a time. Only the steps marked **LIVE** call
the models, all through your subscriptions; nothing else does.

| Step | Command | What it does |
|---|---|---|
| 1 | `cp config/models.example.yaml config/models.yaml` | Registry: Claude Sonnet 5 (Claude Code, Pro) and GPT-6 Luna (Codex, Go). Confirm the list prices first |
| 2 | `make sandbox` | Builds the Docker image that runs model-written code (Docker Desktop must be running) |
| 3 | `make preflight` | No model calls. Every line must say `ready`; an API-key sign-in is refused |
| 4 | `make smoke` | **LIVE**, 4 calls: one judged task per model, each judged by the other provider |
| 5 | `make calibrate` | **LIVE**, about 24 calls: each judge grades 6 golden + 6 seeded answers; prints SM-3 / SM-4 and writes `reports/calibration.json` |
| 6 | `make eval MODELS="claude-pro gpt-go"` | **LIVE**, about 52 calls (36 answers + 16 judge calls), capped at 80 |
| 7 | `make summary` then `make dev` | Scores in the terminal, then the screens at http://127.0.0.1:5173 |

If a plan limit is hit, the run pauses (`paused_quota`) and nothing is lost: resume later
with `cd backend && .venv/bin/python -m app.eval resume <RUN_ID>`. Finished tasks are never
repeated.

## Repository layout

```
specs/           the four specifications (source of truth)
claude-plan.md   implementation plan + progress
CLAUDE.md        coding-agent instructions
config/          models.yaml (model registry)
suite/           evaluation tasks + golden set
backend/         FastAPI API, eval worker, adapters, scoring
frontend/        React UI
sandbox/         container for running generated code
tests/           unit, integration, contract, e2e
```

## Tech stack

Python 3.12 · FastAPI · SQLite · asyncio runner · Docker sandbox · React + TypeScript (Vite) · Tailwind · Recharts · pytest · Playwright · GitHub Actions

## Owner

Madhu Kesarkar — QA Lead
