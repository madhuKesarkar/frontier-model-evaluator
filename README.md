# Frontier Model Evaluator (FME)

A web application that evaluates frontier LLMs and helps teams decide which model fits the application they are building or testing.

- **Rates** each model 1–5 per capability category (code generation, reasoning, structured output, test design, long-context faithfulness, tool use)
- **Highlights token usage and cost** per task across Simple / Mid / Complex tiers
- **Lists defects** found in each model, with type, severity and evidence
- **Use-case fit**: click any model, or apply a profile of your app's needs, to get a Recommended / Conditional / Not recommended verdict with reasons

## How this project is built

This repo follows **spec-driven development** with a **Level 3 (conditional) autonomy** setup for AI coding agents:

```
Constitution → Spec → Plan → Tasks → Implement → Verify
```

- [`SPEC.md`](SPEC.md) is the source of truth: goals, requirements, acceptance criteria (AC-01 to AC-33), tech stack, architecture and agent rules.
- `specs/constitution.md`, `specs/plan.md` and `specs/tasks.md` are added at Gate G2.
- Agents work on feature branches and must stop for human approval at the gates and actions listed in SPEC.md §9.

## Status

| Gate | Status |
|---|---|
| G1 Spec approval | ⏳ In review (SPEC.md v0.1) |
| G2 Plan approval | Not started |
| G3–G5 | Not started |

## Repository layout

```
SPEC.md          source of truth
specs/           constitution, plan, tasks
config/          models.yaml (model registry)
suite/           evaluation tasks + golden set
backend/         FastAPI API, eval worker, adapters, scoring
frontend/        Next.js UI
sandbox/         container for running generated code
tests/           unit, integration, contract, e2e
```

## Tech stack

Python 3.12 · FastAPI · PostgreSQL · Redis/arq · Docker sandbox · Next.js + TypeScript · Tailwind · Recharts · pytest · Pact · Playwright · GitHub Actions

## Owner

Madhu Kesarkar — QA Lead
