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
| G1 Specs approved | ⏳ In review (four specs, v0.3) |
| G2 Plan approved | ⏳ Draft in `claude-plan.md` |
| G3–G5 | Not started |

## Zero-cost by design

v1 runs at **$0 extra cost**. Models are reached through the owner's existing subscriptions and free tiers, never paid API keys:

| Provider | Access |
|---|---|
| Anthropic | Claude Code CLI (headless), signed in with Claude Pro |
| OpenAI | Codex CLI (`exec --json`), signed in with ChatGPT Go |
| Google | Gemini API free tier (Flash models) |
| Fallback | Manual paste from any chat app |

Live evaluations run locally on the owner's computer. CI uses recorded fixtures only. See `specs/backend-spec.md` §3.

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
