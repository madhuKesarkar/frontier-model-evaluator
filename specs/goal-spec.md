# Goal Spec — Frontier Model Evaluator (FME)

> Defines *what* we're building and *why*. The other three specs derive from this one.
> Status: **v1.0 — demo scope (D-12), approved 2026-10-12.** Owner: Madhu Kesarkar.
> Delivery: working demo by **14 Oct 2026**; course submission deadline **18 Oct 2026**.

## Demo scope at a glance (D-12)
| In the v1 demo | Moved to Post-MVP |
|---|---|
| 18 tasks (6 categories × 3 tiers × 1 task) | 36+ task suite |
| Real runs on Claude, GPT, Gemini Flash, started from the command line on the owner's Mac | Starting runs from the UI, manual-paste mode, run progress screen |
| Automated checks + **one** cross-provider judge | Two judges with disagreement review |
| 1–5 scores, tokens and API-equivalent cost by tier, defects with evidence | Review queue UI, export, run history |
| 3 screens: **Leaderboard, Model detail, Fit** (template profiles) | Compare screen, custom/saved profiles |
| Judge check on 6 golden + 6 seeded items | 18 golden + 12 seeded |
| Read-only public demo on free tiers (Netlify + Render), plus YouTube video | Hosted runs, login |


## 1. Problem Statement
<!-- What problem does this app solve? Who has this problem today, and how do they cope without this tool? -->
Teams building or testing AI-powered applications must choose a frontier LLM. Today they rely on vendor benchmarks, social media and one-off manual trials. Vendor benchmarks are generic. Token usage and cost differ between providers. Failure modes such as invented facts, broken JSON or wrong code are rarely recorded in one place with evidence. As a result, teams choose a model on reputation instead of evidence that matches their own use case.

FME runs the same versioned set of tasks against several models and scores each model 1–5 per capability category. It shows token usage and API-equivalent cost per task at three complexity tiers, and records every defect found with its evidence. A user can open any model to inspect this evidence and check whether the model fits the application they are developing or testing.

## 2. Target Users
<!-- Who uses this app? Include any relevant personas. -->
| Persona | What they need from FME |
|---|---|
| QA Lead / Test Architect (primary; the owner) | Where each model breaks, with evidence, before it goes into a product |
| Engineering Manager / Tech Lead | Quality versus cost, to choose a model for a team |
| Developer | Which model handles their task type and complexity best |

v1 is a single-user tool run by the owner on her own computer.

## 3. Core Use Cases
<!-- The primary user journeys, as short scenarios. -->
- UC-1: As a QA lead, I want to run the task suite against Claude, GPT and Gemini so that every model is measured on the same tasks.
- UC-2: As a user, I want to see each model's 1–5 score per category on one screen so that I can compare models at a glance.
- UC-3: As a user, I want to see token usage and API-equivalent cost for Simple, Mid and Complex tasks so that I understand what each model would cost for my workload.
- UC-4: As a QA lead, I want to see every defect found in a model, with the prompt, response and reason, so that I can judge the risk myself.
- UC-5: As a user, I want to click a model and see its scores, tokens and defects together so that I can decide whether it suits my application.
- UC-6: As a user, I want to describe my application's needs (important categories, typical complexity, cost limit) and get a verdict per model with reasons.
- UC-7: As a QA lead, I want to review scores that the automatic judges disagree on, and mark defects as confirmed or false positive, so that the results are trustworthy.

## 4. Core Features (MVP)
<!-- Must-have features for v1. Specific enough to scope work, not exhaustive. -->
- F-1 **Model registry** configured in a file. Adding a model is a configuration change, not a code change.
- F-2 **Versioned task suite**: 6 categories × 3 tiers, 1 task per cell (18 tasks) for the demo (D-12).
- F-3 **Evaluation runs** (command line, owner's Mac): run selected models on selected categories and tiers, with a call cap. A run stops a model when its plan quota is used up; re-running resumes without repeating finished tasks.
- F-4 **Scoring 1–5** per task and per category, using automated checks first and one cross-provider LLM judge where judgement is needed.
- F-5 **Token and cost tracking** per task: input, output and overhead tokens, plus API-equivalent cost. Estimated values are labelled.
- F-6 **Defect log** per model, with type, severity, evidence and review status.
- F-7 **Leaderboard** (home screen) with a score per category per model, sorting and filtering.
- F-8 **Model detail** screen: category scores by tier, token panel, defects, task drill-down.
- F-15 **Read-only public demo**: the dashboard is deployed on free tiers and serves results from the owner's real run (D-13).
- F-10 **Use-case fit**: three template profiles that produce Recommended / Conditional / Not recommended verdicts with reasons.

## 5. Nice-to-Have Features (Post-MVP)
<!-- Features explicitly deferred. Helps prevent scope creep. -->
- Compare screen; custom and saved profiles; review-queue UI; export; run history and run comparison.
- Starting runs from the UI, run progress screen, manual-paste mode.
- Two judges per result with disagreement review; full golden set (18 + 12).
- Growing the suite beyond 1 task per cell.
- Paid-API access modes, enabling flagship models such as Gemini Pro.
- Users uploading their own tasks from their application under test.
- Login and multi-user use.
- Hosted (online) evaluation runs.
- Scheduled re-runs when a provider releases a new model version.

## 6. Out of Scope
<!-- Explicitly excluded from this project. -->
- Training, fine-tuning or hosting models.
- Image, audio or video evaluation. v1 covers text and code only.
- A public leaderboard or marketing benchmark.
- Billing, multi-tenancy and user sign-up.
- Real-time or streaming evaluation. v1 runs in batches only.
- Any paid API usage or paid cloud service in v1 (free tiers only).

## 7. Success Metrics
<!-- How do we know this app is working? Each metric states how it is assessed. -->
| ID | Metric | How we assess it |
|---|---|---|
| SM-1 | After a completed run on three models, the Leaderboard shows a 1–5 score for each of the six categories for each model. | E2E test on fixture data, plus a manual check after the first live run |
| SM-2 | Scores are reproducible: running the same suite twice on the same model changes each category score by at most 0.5. | **Post-MVP** for the demo (needs two full live runs and run history). Measured only if quota allows. |
| SM-3 | The LLM judge agrees with the owner's labels: at least 80% of the 6 golden items (5 of 6) are scored within ±1 of the human score. | Judge calibration run on the golden set |
| SM-4 | The judge catches planted defects: at least 80% of the 6 seeded flawed responses (5 of 6) are scored 2 or lower. | Seeded-defect check (mutation-style test of the judge) |
| SM-5 | A user reaches a fit verdict for every model in 3 clicks or fewer from the home screen. | E2E test |
| SM-6 | Every displayed defect links to its prompt, response and evidence. | Contract and E2E tests |
| SM-7 | Running the project costs $0 beyond the owner's existing Claude Pro and ChatGPT Go subscriptions. | Paid-key guard test, plus review of the access modes and hosting tiers used |
| SM-8 | The demo is reachable at a public URL and shows the owner's real run results. | Live verification after deploy (claude-plan Phase 5) |

## 8. Constraints & Assumptions
<!-- Budget, timeline, team size, must-use tech, platforms, etc. -->
- **Budget: $0 extra.** Models are reached only through the owner's Claude Pro and ChatGPT Go subscriptions (via their official command-line tools), Google's free Gemini API tier, or manual paste. No paid API keys. See backend-spec §3.
- **Platform:** evaluation runs on the owner's Mac (where the CLIs are signed in). Results are published to a **read-only** public demo: frontend on Netlify (free), API on Render (free tier). No model is ever called from the deployed site (D-13).
- **Team:** 1 person (architect), plus a coding agent (contractor).
- **Timeline:** working demo by 14 Oct 2026; course submission by 18 Oct 2026 (D-12, supersedes D-7).
- **Required technology:** Python backend (the evaluation libraries are Python), React frontend, SQLite storage. Exact choices are proposed in the frontend and backend specs.
- **Quotas:** subscription and free-tier limits are the binding resource. The suite size and repeat count are sized so that a full run fits within them.
- **Fairness:** results describe each model *as reached through its access mode*: Claude via Claude Code on Pro, GPT via Codex on Go, and Gemini Flash on the free tier. They are not a comparison of three flagship APIs, and the UI must say so.
- **Data:** the task suite must contain no confidential or personal data, because free-tier prompts may be used by the provider to improve its products.
- **System type:** the evaluator is a fixed **workflow** (call → check → judge → score), not an autonomous agent. This is the simplest system that meets the goal. The model never chooses the next step of an evaluation.

## 9. Glossary
<!-- Domain terms used consistently across all four specs. -->
| Term | Definition |
|---|---|
| Provider | A model vendor: Anthropic, OpenAI or Google. |
| Model | One configured entry in the registry: a provider, access mode and model ID. |
| Access mode | How FME reaches a model at $0: `claude_code_cli`, `codex_cli`, `gemini_free_api` or `manual`. |
| Category | A capability area rated 1–5: Code Generation; Reasoning & Analysis; Instruction Following & Structured Output; Test Design (QA); Long-Context Faithfulness; Tool Use. |
| Tier | Task complexity: **Simple** (single step), **Mid** (2–5 steps or constraints), **Complex** (long context, multi-step or ambiguity). |
| Task | One versioned prompt with fixtures, expected outcome and checker(s). Identified by ID and content hash. |
| Checker | An automated check on a response: unit tests, JSON schema, exact match, regex, or an LLM judge. |
| Run | One execution of selected tasks against selected models. |
| Result | One model's response to one task in one run, with tokens, cost, latency, checks, score and status. |
| Judge | A model from a *different* provider that scores a result against the task rubric. |
| Score | An integer from 1 to 5 for one result. Category and overall scores are means of result scores. |
| Defect | A failure found in a result, with a type, severity (S1–S4), evidence, source and status. |
| Golden set | Results labelled by the owner, used to check that the judges score like a human. |
| Seeded defect | A response deliberately made wrong, used to check that the judges catch failures. |
| Overhead tokens | Tokens added by an access mode itself (for example a CLI's system prompt) rather than by the task. |
| API-equivalent cost | Tokens × the provider's public list price. What the task *would* cost on a paid API. Nothing is billed. |
| Quota pause | A model's tasks stop because its plan limit is reached. This is not a model defect. |
| Use-case profile | The user's description of their application: category weights, must-have categories, tier mix and limits. |
| Verdict | Recommended, Conditional or Not recommended, with the reasons that produced it. |

## 10. Decision Record and Open Questions
### Decisions (architect-approved)
| ID | Date | Decision | Affects |
|---|---|---|---|
| D-1 | 2026-10-10 | Providers: Anthropic, OpenAI, Google | all |
| D-2 | 2026-10-10 | $0 extra cost: Claude Pro and ChatGPT Go via official CLIs, Gemini free tier, manual fallback | goal, backend, API |
| D-3 | 2026-10-10 | Keep all 6 categories | goal, backend |
| D-4 | 2026-10-10 | No login and no user-uploaded tasks in v1 | goal, frontend, API |
| D-5 | 2026-10-10 | Follow the course's four-spec structure. SPEC.md v0.2 is retired into these four documents. | repo |
| D-6 | 2026-10-10 | Golden set: the owner labels 18 results (3 per category), plus 12 seeded defects (2 per category) | goal, backend |
| D-7 | 2026-10-10 | No fixed v1 date; work phase by phase | goal, plan |
| D-8 | 2026-10-10 | Visual style: clean neutral palette, system font, one accent colour. The agent proposes design tokens for review. | frontend |
| D-9 | 2026-10-10 | Minimum supported width 1024 px (desktop-first; phone layout out of scope) | frontend |
| D-10 | 2026-10-10 | Sandbox limits: 10 s run time and 512 MB memory per execution | backend |
| D-11 | 2026-10-10 | Run progress via polling `GET /runs/{id}` every 3 s while a run is active; no server-sent events in v1. *(Dormant in the demo: runs start from the command line.)* | frontend, API |
| D-12 | 2026-10-12 | **Demo scope** for the course submission: 18 tasks, one judge, 3 screens (Leaderboard, Model detail, Fit with templates), 6 golden + 6 seeded. Everything else moves to Post-MVP. Demo by 14 Oct, submit by 18 Oct. **Supersedes D-6 and D-7.** | all |
| D-13 | 2026-10-12 | **Deployment:** read-only demo on free tiers, Netlify (frontend) + Render (API serving the owner's real run results); YouTube video as backup. Live runs stay on the owner's Mac. | goal, backend, API, plan |
| D-14 | 2026-10-12 | **Process:** one PR per phase, each task a separate commit, to fit the timeline (replaces one PR per task). | plan, CLAUDE.md |
| D-15 | 2026-10-12 | Docker sandbox confirmed: the owner has Docker Desktop. D-10 limits stand. | backend |

### Open questions
- OQ-2 `[NEEDS CLARIFICATION]` Exact model per provider, confirmed at the first live run (G4): which Claude model in Claude Code, which GPT model Codex uses on Go, and which free Gemini Flash model.
