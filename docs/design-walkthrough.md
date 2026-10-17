# Design decisions and interview preparation

**Frontier Model Evaluator** · Madhu Kesarkar · IISc Agentic AI course, final project
Live demo: https://frontier-model-evaluator.netlify.app · Code: this repository

This page explains *why* the project is built the way it is, and how I prepared to defend it.
Every decision below is recorded, with its date, in [`specs/goal-spec.md` §10](../specs/goal-spec.md).

---

## 1. The problem and the one question it answers

Teams choose an LLM from public leaderboards that don't reflect their own use case. FME answers
one question for a specific application: **does this model fit what I'm building?** It rates each
model 1–5 in six QA-relevant categories, across simple, mid and complex tasks; shows token usage
and API-equivalent cost per tier; lists every defect with evidence; and gives a fit verdict.

## 2. How it was built: spec-driven development

| Course element | How it appears here |
|---|---|
| Specify | Four specs are the source of truth: [goal](../specs/goal-spec.md), [frontend](../specs/frontend-spec.md), [backend](../specs/backend-spec.md), [API contract](../specs/api-contract-spec.md). 44 acceptance criteria (35 in the demo scope). |
| Plan | [`claude-plan.md`](../claude-plan.md): phases 0–6, each with an observable "done when" check and an AC → test matrix. |
| Implement | Claude Code as the coding agent, bounded by [`CLAUDE.md`](../CLAUDE.md): one PR per phase, one commit per task, no paid APIs, never weaken a test, stop and ask before any product decision. |
| Verify | Every AC has a test named after it (`make ac-check` in CI). Key tests were mutation-checked: the behaviour was broken on purpose to prove the test fails. |
| Iterate | Gates G1–G6. I (the architect) approved the specs, the plan, each phase PR, the live run and the deployment. |

**Architect / contractor split.** I owned intent and acceptance; the agent drafted, planned,
implemented and reported evidence. When the specs didn't settle a product question, the agent
stopped and asked instead of deciding in code. Examples: the S1 blocking rule (D-18), the fit
templates (D-19), the models (D-20), and the golden labels.

## 3. Key design decisions

| # | Decision | Why | Alternative rejected |
|---|---|---|---|
| D-2 / D-17 | **$0 cost:** Claude via Claude Code on Pro, GPT via Codex on ChatGPT Go. Two providers only. | No budget for paid APIs; the official CLIs use existing subscriptions. Gemini was dropped to save time. | Paid API keys: these are refused at startup (BE-R1), and preflight refuses an API-key sign-in. |
| D-12 | **Demo scope:** 18 tasks (6 categories × 3 tiers), one judge, three screens. | A complete, honest demo beats a large unfinished app. Everything else is recorded as Post-MVP. | 54 tasks, two judges, seven screens: not finishable by the deadline. |
| D-16 | **Final score = the lower of the automated checks and the judge.** | A lenient judge must not rescue code that fails its unit tests. | Averaging, which hides hard failures. |
| BE-R12 | **Cross-provider judge:** Claude grades GPT, GPT grades Claude. | Prevents self-preference bias. | Self-grading. |
| §7 | **Judge calibration:** 6 owner-labelled golden answers (≥ 80% within ±1) and 6 planted-defect answers (≥ 80% scored ≤ 2), per judge. | You can't trust an LLM judge you haven't tested. The seeded set is a mutation test of the judge. | Trusting the judge blindly. |
| D-10 / D-15 | **Docker sandbox** for model-written code: no network, 512 MB, 1 CPU, non-root, read-only, 10 s limit. | Model output is untrusted data; it must never run on the host. | Running code directly (unsafe). |
| D-18 | **An S1 defect in a must-have category blocks a recommendation**, whatever the average. | Averages hide deal-breakers, such as a support bot issuing a refund against policy. | Average-only verdicts. |
| BE-R21 | **Unreported tokens show "n/a", never 0.** Task tokens and CLI overhead are shown separately. | A fake 0 is a lie; overhead differs per access mode, so raw counts mislead. | Treating missing values as 0. |
| D-13 | **Read-only public demo:** Netlify + Render free tiers, serving a frozen snapshot. Live runs stay on my Mac. | The deployed site can't call a model or spend quota; anyone can view it safely. | A public site that starts runs (cost and abuse risk). |
| D-14 | **One PR per phase, one commit per task.** | Reviewable chunks within the timeline; a clear history. | One PR per task (too slow), or one giant PR (unreviewable). |
| API contract | **OpenAPI snapshot + generated TypeScript types**, with a drift test on both sides. | Contract drift becomes a compile error or a failing test, not a runtime surprise. | Pact contract tests: considered, deferred to keep scope small. |

## 4. Architecture

```
suite/v1 (18 tasks)  ──►  runner ──► adapters ──► claude -p … | codex exec …   (owner's Mac only)
                              │
                              ├─► checkers (unit tests in Docker, JSON schema, exact match, regex)
                              ├─► cross-provider judge
                              └─► SQLite: runs, results, judge scores, defects
                                         │
                          make snapshot ─┘──► deploy/fme.db ──► FastAPI (read-only, Render)
                                                                    │  /api/v1 (OpenAPI contract)
                                                                    ▼
                                                     React + TypeScript (Netlify)
                                                     Leaderboard · Model detail · Fit
```

**Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy + Alembic, SQLite · React 19, TypeScript
(strict), TanStack Query, Recharts, Tailwind · pytest, Vitest, Playwright + axe · GitHub Actions
(lint, types, tests, AC traceability, secret scan).

## 5. Quality evidence

- **201 backend tests**, 10 component tests and 9 browser (E2E) tests; CI green on every PR.
- **35/35 demo acceptance criteria** have a test named after them.
- **Mutation checks** on key behaviour: the call cap, quota pause and resume, the min-score rule,
  the cross-provider judge, the fit rules, the read-only mode, the calibration maths, the
  preflight gate, the n/a badges and the accessibility of scrollable panels.
- **WCAG 2.1 AA:** no serious or critical axe violations; every journey works with the keyboard.
- **Bugs found by the tests**, not by users:
  1. With Docker down, failed code checks were blamed on the model. Now it's a harness error:
     the run stops, nothing is recorded, and it can be resumed.
  2. Two accessibility violations (scrollable evidence boxes weren't keyboard-focusable).
  3. The demo database was ignored by git, so the deployed API had no data. Caught by checking
     the live endpoint, and fixed in PR #14.

## 6. Honest limitations

- The public demo shows a **labelled synthetic run** (recorded responses with planted flaws).
  Live runs use my subscriptions on my own machine.
- One task per category and tier is a small sample. The scores show the method, not a definitive
  ranking.
- Models are compared **as reached through each access mode**: Claude Code and Codex add their
  own system prompts, so these aren't the flagship APIs under identical conditions.
- Token counts use different tokenizers per provider, so the UI compares API-equivalent cost.

## 7. Interview preparation: questions I expect

**Why spec-driven development instead of just prompting the agent?**
Specs give the agent a fixed target and give me a way to verify it. Every requirement has an
acceptance criterion and a test, so "done" is objective, and the agent can't silently change
scope.

**How did you keep the agent under control?**
Four control surfaces from the course. Prompt: one phase per request. Context: the four specs and
CLAUDE.md. Loop: lint, type checks, tests, the AC check and mutation checks before reporting
"done". Graph: gates that need my approval. Hard rules: no paid APIs, never weaken a test, stop
and ask before product decisions.

**How do you know the LLM judge is reliable?**
Calibration: each judge grades 6 golden answers that I labelled, and 6 answers with planted
defects. It must agree within ±1 point on at least 5 of 6, and score at least 5 of 6 planted
defects at 2 or lower. And it never has the final word on code: the lower score wins.

**Why take the minimum of the checks and the judge?**
Deterministic checks are ground truth for what they cover. A judge can be impressed by good
prose around broken code; the minimum stops that.

**Isn't comparing via CLIs unfair?**
Yes, partly, and the UI says so. The goal is a $0 comparison of the models as I can actually
access them. Overhead tokens are shown separately, and cost is compared instead of raw tokens.

**What would you build next?**
More models and tasks, a second judge with disagreement review, custom fit profiles in the UI,
CSV export and run history. All of these are already specified as Post-MVP.

**What was the hardest part?**
Keeping the scope honest under a deadline: cutting to a demo scope (D-12) without cutting
corners on tests, and making sure the public demo never pretends synthetic data is real.
