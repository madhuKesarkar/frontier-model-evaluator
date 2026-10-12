# API Contract Spec — Frontier Model Evaluator

> The seam between frontend and backend: exact messages, including failures.
> Status: **v1.0 — demo scope (D-12).** Both sides are built against this document.
>
> **Demo endpoints:** `GET /health`, `GET /models`, `GET /leaderboard`, `GET /models/{key}`, `GET /models/{key}/defects`, `GET /models/{key}/results`, `GET /results/{id}`, `GET /profile-templates`, `POST /fit` (with `profile_id` of a template). **Post-MVP:** `/preflight`, `/compare`, all `/runs…` endpoints, manual, review, `/profiles` CRUD, `/export`. Their rows below are kept as the Post-MVP design.

## 1. Conventions
- Base URL: `http://127.0.0.1:8000/api/v1` locally; the Render URL + `/api/v1` in the deployed demo. JSON request and response bodies.
- **No authentication** (D-4). Locally the server binds to localhost only. The deployed demo is read-only (D-13) and allows CORS only from the Netlify site's origin.
- Timestamps: ISO-8601 UTC with a trailing `Z`, for example `2026-10-10T08:30:00Z`.
- Money: `api_equiv_cost_usd` is a decimal number with 6 decimal places.
- Token fields are an integer, or `null` when not reported. A sibling `*_estimated: true` flag marks estimated values.
- Enumerations use the exact strings defined in backend-spec.md (categories, tiers, statuses, defect types, severities).
- Category keys: `code_generation`, `reasoning`, `structured_output`, `test_design`, `long_context`, `tool_use`. Tier keys: `simple`, `mid`, `complex`.

### Error shapes
| Status | When | Body |
|---|---|---|
| 400 | A business rule refuses the request | `{"detail": "<plain-language reason>"}` |
| 404 | The resource doesn't exist | `{"detail": "Not found"}` |
| 409 | Conflicts with current state (e.g. a run is already active) | `{"detail": "<reason>", "active_run_id": <int>}` |
| 422 | Malformed fields | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` (FastAPI validation shape) |
| 503 | A startup or config problem the user must fix | `{"detail": "<reason>"}` |

## 2. Core Schemas
```jsonc
// ModelSummary
{ "key": "claude-pro", "provider": "anthropic", "access_mode": "claude_code_cli",
  "model_id": "…", "display_name": "…", "enabled": true }

// UsageRecord
{ "input_tokens": 1200, "input_tokens_estimated": false,
  "output_tokens": 340, "output_tokens_estimated": false,
  "reasoning_tokens": null, "cached_tokens": 0, "overhead_tokens": 410,
  "api_equiv_cost_usd": 0.008700, "latency_ms": 5400 }

// ScoreCell  (one category for one model)
{ "category": "code_generation", "score": 4.2,
  "by_tier": { "simple": 4.8, "mid": 4.0, "complex": 3.5 },
  "scored_results": 6, "unscored_results": 0 }

// Defect
{ "id": 17, "result_id": 230, "model_key": "gpt-go", "task_id": "CG-M-02",
  "category": "code_generation", "tier": "mid", "type": "INCORRECT_CODE",
  "severity": "S2", "title": "…", "expected": "…", "actual": "…",
  "evidence": { "prompt_excerpt": "…", "response_excerpt": "…", "checker_output": "…" },
  "source": "auto", "status": "open" }

// Verdict
{ "model_key": "claude-pro", "verdict": "conditional", "fit_score": 3.74,
  "expected_cost_per_task_usd": 0.012000, "p95_latency_ms": 9100,
  "reasons": [ { "rule": "fit_between_3_and_4", "text": "Fit score 3.74 is below 4.0" } ],
  "strengths": ["code_generation"], "risks": ["long_context"], "cited_defect_ids": [17] }
```

## 3. Endpoints

### Health and setup
| Method & path | Success | Notes |
|---|---|---|
| `GET /health` | 200 `{"status": "ok"}` | |
| `GET /preflight` | 200 `{"access_modes": [{"access_mode": "codex_cli", "ready": false, "reason": "Not signed in"}]}` | Never makes a billable call |

### Models and results
| Method & path | Success | Failures |
|---|---|---|
| `GET /models` | 200 `[ModelSummary]` | |
| `GET /leaderboard?run_id=&tier=&category=` | 200 `{"run_id", "rows": [{"model": ModelSummary, "overall": 3.9, "scores": [ScoreCell], "avg_cost_per_task_usd", "p50_latency_ms", "open_s1_s2_defects"}]}`. `run_id` defaults to the latest completed run. | 404 unknown run · 422 bad enum |
| `GET /models/{key}?run_id=` | 200 `{"model": ModelSummary, "last_run_at", "overall", "scores": [ScoreCell], "tokens_by_tier": {"simple": {"avg": UsageRecord, "total": UsageRecord}, …}, "costliest_task_ids": [...]}` | 404 unknown model or run |
| `GET /models/{key}/defects?run_id=&severity=&type=&tier=&category=&status=` | 200 `{"count": 3, "items": [Defect]}` | 404 · 422 |
| `GET /models/{key}/results?run_id=&tier=&category=` | 200 `[{"result_id", "task_id", "tier", "category", "score", "status", "usage": UsageRecord}]` | 404 |
| `GET /results/{id}` | 200 `{"result_id", "task": {"task_id", "title", "prompt", "version", "content_hash"}, "response_text", "checks": [{"checker", "passed", "output"}], "judges": [{"judge_model_key", "score", "rationale"}], "score", "score_source", "needs_review", "usage": UsageRecord, "defects": [Defect]}` | 404 |
| `GET /compare?model_keys=a,b,c&run_id=` | 200 `{"models": [{"model": ModelSummary, "scores": [ScoreCell], "cost_by_tier": {...}, "defects_by_type": {...}}]}` | 400 if fewer than 2 or more than 4 keys · 404 |

### Runs
| Method & path | Success | Failures |
|---|---|---|
| `POST /runs` body `{"model_keys": [...], "categories": [...], "tiers": [...], "repeats": 1, "call_cap": 50}` | 201 `Run` (status `queued`) | 400 disabled or not-ready model, empty selection, or call_cap < 1 · 409 a run is already active · 422 |
| `GET /runs` | 200 `[Run]` (newest first) | |
| `GET /runs/{id}` | 200 `Run` with `"progress": [{"model_key", "done", "total", "status"}]`, where per-model `status` is `pending`, `running`, `paused_quota`, `done` or `error` | 404 |
| `POST /runs/{id}/resume` | 200 `Run` | 400 if the run is not `paused_quota` or `stopped_cap` · 409 · 404 |
| `POST /runs/{id}/cancel` | 200 `Run` (status `cancelled`) | 400 if already finished · 404 |
| `GET /runs/{id}/manual-queue` | 200 `[{"result_id", "model_key", "task_id", "prompt"}]` | 404 |
| `POST /results/{id}/manual` body `{"response_text": "…"}` | 200 result summary (scored, or judging queued) | 400 if the result isn't `awaiting_manual` or the text is empty after trimming · 404 |
| `GET /runs/compare?a={id}&b={id}` | 200 `{"a": {"run_id", "suite_version"}, "b": {...}, "changes": [{"model_key", "category", "a_score", "b_score", "delta"}]}` | 404 |

`Run` = `{"id", "status", "suite_version", "model_keys", "categories", "tiers", "repeats", "call_cap", "calls_made", "api_equiv_cost_usd", "started_at", "finished_at"}`

### Review
| Method & path | Success | Failures |
|---|---|---|
| `GET /review-queue` | 200 `{"results": [result summary], "defects": [Defect]}` | |
| `PATCH /results/{id}/review` body `{"score": 1-5, "note": "…"}` | 200 result with `score_source: "human"`, `needs_review: false` | 404 · 422 score out of range |
| `PATCH /defects/{id}` body `{"status"?: "confirmed" \| "false_positive", "severity"?: "S1".."S4"}` | 200 `Defect` | 404 · 422 |

### Fit and profiles
| Method & path | Success | Failures |
|---|---|---|
| `GET /profile-templates` | 200 `[Profile]` (`is_template: true`) | |
| `GET /profiles` · `POST /profiles` · `PUT /profiles/{id}` · `DELETE /profiles/{id}` | 200 / 201 / 200 / 204 | 400 tier_mix doesn't total 100, all weights 0, or a negative limit · 400 editing a template · 404 · 422 |
| `POST /fit` body `{"profile_id"}` or `{"profile": Profile}`, plus optional `"run_id"` | 200 `{"run_id", "verdicts": [Verdict]}` | 400 invalid profile · 404 |

`Profile` = `{"id", "name", "weights": {"code_generation": 5, …}, "must_have": [...], "tier_mix": {"simple": 20, "mid": 60, "complex": 20}, "max_cost_per_task_usd": null, "max_p95_latency_ms": null, "is_template": false}`

### Export
| Method & path | Success | Failures |
|---|---|---|
| `GET /export?view=leaderboard\|model\|defects&format=csv\|json&run_id=&model_key=` | 200 file (`text/csv` or `application/json`). Values match the corresponding view endpoint. | 400 `model_key` missing for `model`/`defects` · 404 |

## 3a. Demo additions (Phase 2, for architect review)
Additive fields the screens need. Nothing documented above was removed or renamed.
- **Machine-readable contract:** `backend/openapi.json` is generated from the code (`make openapi`). A test fails if the code and the snapshot differ, so any API change is a visible, reviewed diff.
- `GET /leaderboard`: adds `run_label` and `run_source` (`recorded` or `live`) so the UI can label synthetic demo data honestly. With no completed run it returns `200 {"run_id": null, "run_label": null, "run_source": null, "rows": []}` (the UI's empty state). Rows are sorted by `overall`, best first.
- `GET /models/{key}`: adds `run_id`, `p50_latency_ms`, `p95_latency_ms`, `open_s1_s2_defects`. In `tokens_by_tier`, `avg` values may be decimals and `avg.latency_ms` is the tier's p50; `total.latency_ms` is `null`.
- `GET /models/{key}/results` items: add `title`, `attempt`, `needs_review`.
- `GET /results/{id}`: adds `model_key`, `category`, `tier`, `status`.
- `POST /fit`: the response adds `profile` (the profile used); each verdict adds `display_name`. `verdict` is `recommended`, `conditional` or `not_recommended`. Verdicts are sorted best first. Template ids are strings (`tpl-test-case-gen`, `tpl-support-chatbot`, `tpl-code-assistant`).
- Defects are sorted by severity (S1 first), then task.
- **503** `{"detail": "Database not set up yet: run `make migrate` …"}` when the schema doesn't exist.
- **Read-only mode** (deployed demo): any method other than GET/HEAD/OPTIONS and `POST /fit` returns `405 {"detail": "This demo is read-only"}`.

## 4. Acceptance Criteria

**Demo scope:** API-AC-01 to 04 for the demo endpoints. **API-AC-05** (export) is Post-MVP.
- **API-AC-01** Given each endpoint above, when called with valid input, then the response matches the documented schema (verified by contract tests generated from this document and the OpenAPI schema).
- **API-AC-02** Given every documented failure, when triggered, then the documented status and error shape are returned.
- **API-AC-03** Given any timestamp in any response, when inspected, then it is UTC with a trailing `Z`.
- **API-AC-04** Given any API response, when scanned, then no provider key or secret appears.
- **API-AC-05** Given `GET /export?view=leaderboard&format=csv`, when compared with `GET /leaderboard` for the same run and filters, then the values are identical.

## 5. Open Questions
None. Progress is polled every 3 s (D-11).
