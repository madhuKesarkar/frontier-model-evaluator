# Backend Spec — Frontier Model Evaluator

> Defines the data, rules, evaluation method and operating constraints behind the journeys in goal-spec.md.
> Status: **DRAFT v0.3** — awaiting review. Exact messages are defined in api-contract-spec.md.

## 1. Technology (proposed — review before accepting)
| Choice | Why | Alternative considered |
|---|---|---|
| Python 3.12 + FastAPI + Pydantic v2 | Typed request and response models; the course's backend stack | Flask |
| SQLite + SQLAlchemy 2 + Alembic | Free, zero setup, single-user. Alembic gives versioned schema changes. | PostgreSQL: unnecessary for a local single-user tool |
| In-process asyncio job runner | One run at a time, with state stored in the database. No Redis needed. | arq + Redis |
| Docker (local) | Isolated sandbox for executing generated code | Running code directly on the host: rejected as unsafe |
| tiktoken | Estimates token counts where none are reported | Character-ratio estimate only |

The backend listens on `127.0.0.1` only. It is not reachable from other machines.

## 2. Data Model
Entities follow the glossary. A Run has many Results; a Result belongs to one Model and one Task, has 0–2 JudgeScores and has 0 or more Defects.

| Entity | Key fields and rules |
|---|---|
| Model | `key` (unique), provider, access_mode, model_id, display_name, context_window, price_input_per_mtok, price_output_per_mtok, enabled. Loaded from `config/models.yaml` at startup; the file is the source of truth. |
| Task | `task_id` (unique), category, tier, title, prompt, fixtures, expected, checkers (list), rubric, version, content_hash (SHA-256 of prompt + fixtures + expected + checkers + rubric). Loaded from `suite/`. |
| Run | id, status (`queued`, `running`, `paused_quota`, `stopped_cap`, `cancelled`, `completed`, `error`), suite_version, model_keys, categories, tiers, repeats, call_cap, calls_made, api_equiv_cost_usd, params (temperature, max_tokens), started_at, finished_at. |
| Result | id, run_id, model_key, task_id, task_hash, attempt (1..repeats), status (`pending`, `awaiting_manual`, `scored`, `error`, `paused_quota`, `skipped`), response_text, input_tokens, output_tokens, reasoning_tokens, cached_tokens, overhead_tokens, tokens_estimated (per field), api_equiv_cost_usd, latency_ms, checks (per-checker outcome), score (1–5), score_source (`auto`, `judge`, `human`), needs_review, review_note. |
| JudgeScore | result_id, judge_model_key, score (1–5), rationale, raw_output. |
| Defect | id, result_id, model_key, task_id, category, tier, type, severity, title, expected, actual, evidence, source (`auto`, `judge`, `human`), status (`open`, `confirmed`, `false_positive`). |
| Profile | id, name, weights (category → 0–5), must_have (categories), tier_mix (simple/mid/complex %), max_cost_per_task_usd (optional), max_p95_latency_ms (optional), is_template. |

Results are saved one at a time as each finishes, not only at the end of a run.

## 3. Access Modes (the $0 constraint)
Each provider is reached through an adapter. All adapters share one interface:

**Input:** model, prompt, system prompt, parameters. **Output:** response text, a usage record (each field either reported or estimated), and latency, **or** one of these errors: `transient` (retryable), `quota_exhausted`, `not_ready` (CLI missing or not signed in, or key missing), `timeout`, or `invalid_response`.

| Access mode | Mechanism | Token data |
|---|---|---|
| `claude_code_cli` | Claude Code headless (`claude -p … --output-format json`) signed in with Claude Pro. Tools disabled; a minimal custom system prompt. | Reported (input, output, cache). Overhead = reported input minus the task prompt's estimated tokens. |
| `codex_cli` | Codex CLI non-interactive (`codex exec --json`) signed in with ChatGPT Go. Read-only sandbox, no tools. | Reported in JSON events |
| `gemini_free_api` | Google GenAI SDK with a free-tier key in `GEMINI_API_KEY`. Flash-class models only. | Reported |
| `manual` | Prompt shown in the UI; the reply is pasted back. | Estimated |

Rules:
- **BE-R1 Paid-key guard:** startup fails with an explanatory message if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set.
- **BE-R2 Preflight:** the backend reports, per access mode, whether it is ready (CLI installed and signed in, or key present) without making a billable call.
- **BE-R3 Model output is data:** response text is stored and checked. It is never interpreted as an instruction to FME, and generated code runs only in the sandbox.
- **BE-R4 CI never calls models.** Tests use recorded adapter responses.

## 4. Evaluation Workflow
A fixed workflow per Result. The model never chooses the next step.

1. Send the task prompt through the model's adapter.
2. Record the response, usage, latency and API-equivalent cost.
3. Run the task's deterministic checkers (unit tests in the sandbox, JSON schema, exact match, regex).
4. If the task's checkers include `llm_judge`, ask the judges.
5. Compute the score, create defects and set `needs_review` where required.

Rules:
- **BE-R5 Call cap:** every model call, including judge calls, counts toward `call_cap`. When the cap is reached, no new calls start, in-flight calls finish, and the run becomes `stopped_cap`.
- **BE-R6 Retries:** `transient` and `timeout` errors are retried up to 3 times with exponential backoff. After that, the Result is `error` with a `TIMEOUT_ERROR` defect.
- **BE-R7 Quota pause:** `quota_exhausted` marks that model's remaining Results `paused_quota` and creates no defect. Other models continue. **Resume** continues only unfinished Results; finished Results are never repeated.
- **BE-R8 One active run:** starting a run while another is `running` is refused.
- **BE-R9 Concurrency:** at most one in-flight call per provider, to respect quotas.
- **BE-R10 Sandbox:** generated code runs in a Docker container with no network, a non-root user, and CPU, memory and time limits (10 s, 512 MB; D-10). A limit breach kills the container, and the Result's code checks fail.

## 5. Scoring
| Score | Label | Rubric |
|---|---|---|
| 5 | Excellent | Fully correct, meets every constraint, no defects |
| 4 | Good | Correct; at most cosmetic (S4) issues |
| 3 | Acceptable | Mostly correct; one S3 defect or needs light edits |
| 2 | Poor | Partially correct; an S2 defect or significant rework needed |
| 1 | Fail | Wrong, unsafe, wrongly refused, an S1 defect, or no usable output |

- **BE-R11 Deterministic-only tasks:** if all checkers are deterministic, score = 5 when all pass. Otherwise the score is derived from the failed checks' defect severities (worst S1→1, S2→2, S3→3, S4→4).
- **BE-R12 Judge assignment:** a Result from provider X is judged by one model from each of the *other two* providers. If only one other provider is ready, one judge is used and the Result is flagged `needs_review`.
- **BE-R13 Judge output:** judges must return `{score: 1–5, rationale, defects: [...]}`. Invalid output is retried once; if it is still invalid, the Result is flagged `needs_review`.
- **BE-R14 Combining:** with two judges, score = round-half-up of their mean. If they differ by more than 1, flag `needs_review`.
- **BE-R15 Deterministic override:** if a code task's unit tests all fail, the score is at most 2, whatever the judges say.
- **BE-R16 Human final say:** a reviewer's score replaces the computed score (`score_source = human`).
- **BE-R17 Aggregates:** category score = mean of that model's Result scores in the category, across tiers and repeats, to 1 decimal. Tier sub-scores are computed the same way. Overall = mean of category scores. Results that are not `scored` are excluded and counted separately.

## 6. Evaluating the Evaluator
Our acceptance criteria for a probabilistic system state the cases, the repetitions and the decision rule.
- **Golden set:** 18 owner-labelled Results, 3 per category (D-6). Decision rule: the judges agree within ±1 on ≥ 80% (SM-3).
- **Seeded defects:** 12 deliberately flawed responses, 2 per category (D-6). Decision rule: ≥ 80% are scored ≤ 2 (SM-4). This is the mutation-style check of the judge.
- **Reproducibility:** the same suite, models and parameters run twice. Decision rule: each category score changes by ≤ 0.5 (SM-2).
- **Consistency:** when repeats > 1 and a task's scores across repeats differ by ≥ 2, create an `INCONSISTENCY` defect.

## 7. Defects
**Types:** `HALLUCINATION`, `INSTRUCTION_VIOLATION`, `FORMAT_BREAK`, `INCORRECT_CODE`, `REASONING_ERROR`, `TOOL_CALL_ERROR`, `OVER_REFUSAL`, `UNSAFE_OUTPUT`, `TRUNCATION`, `TIMEOUT_ERROR`, `INCONSISTENCY`.

**Severity:** S1 Critical (unsafe, or silently wrong in a way that would ship a bug) · S2 Major (wrong or unusable but detectable) · S3 Minor (usable with edits) · S4 Cosmetic.

- **BE-R18** A failed JSON-schema check creates a `FORMAT_BREAK` defect with the validator's error as evidence. A failed unit test creates `INCORRECT_CODE` with the failing test output. Output that hit the token limit creates `TRUNCATION`.
- **BE-R19** Defects marked `false_positive` are excluded from defect counts, scores derived from defects, and verdicts.

## 8. Tokens and Cost
- **BE-R20** API-equivalent cost = `(input × price_input_per_mtok + output × price_output_per_mtok) / 1,000,000`, accurate to $0.000001. Reasoning tokens are billed as output where the provider reports them separately.
- **BE-R21** A token field that was not reported is either estimated (and flagged as estimated) or stored as null. It is never stored as 0.
- **BE-R22** Per model × tier aggregates: average and total tokens per field, average cost per task, p50 and p95 latency.

## 9. Use-Case Fit
- **BE-R23 Fit score** = Σ(weight_c × score_c) / Σ(weight_c) over categories with weight > 0. Each category score is weighted by the profile's tier mix using tier sub-scores.
- **BE-R24 Expected cost per task** = Σ over tiers of (tier mix % × the model's average cost per task in that tier).
- **BE-R25 Verdict:**
  - **Not recommended** if fit < 3.0, **or** any `confirmed` S1 defect is in a must-have category, **or** any must-have category scores < 3.0.
  - Otherwise **Conditional** if fit is 3.0–3.99, **or** expected cost exceeds the profile limit, **or** p95 latency exceeds the profile limit.
  - Otherwise **Recommended**.
  - Every verdict lists the rules that produced it.
- **BE-R26** Fit is deterministic: the same profile on the same run data gives the same output.
- **BE-R27** Templates are read-only, but can be copied into a custom profile.

## 10. Non-Functional Requirements
| Area | Requirement |
|---|---|
| Security | No secrets in logs, API responses or the repository. `GEMINI_API_KEY` is read from the environment only. Secret scanning runs in CI. |
| Privacy | The suite contains no confidential or personal data (the free tier may use prompts). |
| Reliability | A crash mid-run loses at most the in-flight Result. Resume continues the run. |
| Performance | Read endpoints respond in under 500 ms (p95) on a seeded database. |
| Observability | Each Result keeps its full trace: prompt, raw response, checker outputs, judge prompts and outputs. Structured logs include run_id, model_key and task_id. |
| Reproducibility | Every Run stores the suite version, task hashes, model IDs, parameters and judge models. |

## 11. Acceptance Criteria
- **BE-AC-01** Given a valid new entry in `models.yaml`, when the app starts, then the model is listed and selectable for a run, with no code change.
- **BE-AC-02** Given an entry missing `model_id` or a price, when the app starts, then startup fails with an error naming the field and the entry.
- **BE-AC-03** Given `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set, when the app starts, then startup fails, explaining that paid keys are not allowed.
- **BE-AC-04** Given the v1 suite, when validated, then every category × tier cell has ≥ 2 tasks, and every task has ≥ 1 checker and a content hash.
- **BE-AC-05** Given a run with 2 models, all tasks and repeats = 2, when it completes, then there are exactly 2 × tasks × 2 Results, each `scored`, `error` or `skipped`.
- **BE-AC-06** Given an adapter returning `transient` three times then success, when called, then the Result is scored and 4 calls are counted. Given four `transient` errors, then the Result is `error` with a `TIMEOUT_ERROR` defect.
- **BE-AC-07** Given an adapter returning `quota_exhausted` on the 5th task, when the run continues, then that model's remaining Results are `paused_quota`, no defect is created, and Resume finishes them without repeating the first four.
- **BE-AC-08** Given call_cap = 10, when the 10th call is made, then no further calls start and the run ends `stopped_cap`.
- **BE-AC-09** Given generated code that opens a network connection, when executed, then the connection fails inside the sandbox and the run continues.
- **BE-AC-10** Given generated code that runs past the time limit, when executed, then the container is killed and an `INCORRECT_CODE` or `TIMEOUT_ERROR` defect is recorded.
- **BE-AC-11** Given a Result from provider X, when judges are assigned, then no judge is from provider X.
- **BE-AC-12** Given judge scores 2 and 5, when combined, then `needs_review` is true.
- **BE-AC-13** Given a code task whose unit tests all fail and judges that score 5, when scored, then the score is ≤ 2.
- **BE-AC-14** Given a response failing its JSON schema, when checked, then a `FORMAT_BREAK` defect exists with the validator error as evidence.
- **BE-AC-15** Given a defect marked `false_positive`, when aggregates and fit are recalculated, then it no longer counts.
- **BE-AC-16** Given input = 1,000, output = 500, prices 3.00 and 15.00, when cost is computed, then it equals $0.010500.
- **BE-AC-17** Given an adapter that doesn't report reasoning tokens, when stored, then `reasoning_tokens` is null, not 0.
- **BE-AC-18** Given a profile with Code Generation as must-have and a confirmed S1 defect in that category, when fit is computed, then the verdict is Not recommended and the defect is cited.
- **BE-AC-19** Given a profile with a $0.01 cost limit and a model whose expected cost is $0.03, when fit is computed, then the verdict is at best Conditional and the overrun is cited.
- **BE-AC-20** Given the same profile and run, when fit is computed twice, then the outputs are identical.
- **BE-AC-21** Given the golden set, when the calibration check runs, then the agreement rate is reported, and the check passes only if it is ≥ 80% (SM-3).
- **BE-AC-22** Given the seeded-defect set, when the check runs, then the catch rate is reported, and the check passes only if it is ≥ 80% (SM-4).
- **BE-AC-23** Given any log line, API response or committed file, when secret-scanned, then no API key is found.

## 12. Open Questions
None.
