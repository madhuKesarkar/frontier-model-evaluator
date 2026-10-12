"""Response models for the demo endpoints (api-contract-spec §2). Field names are the
contract: changing one here must be a reviewed contract change."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelSummaryOut(_Model):
    key: str
    provider: str
    access_mode: str
    model_id: str
    display_name: str
    enabled: bool


class UsageRecord(_Model):
    input_tokens: float | None
    input_tokens_estimated: bool
    output_tokens: float | None
    output_tokens_estimated: bool
    reasoning_tokens: float | None
    cached_tokens: float | None
    overhead_tokens: float | None
    api_equiv_cost_usd: float | None
    latency_ms: float | None


class ScoreCell(_Model):
    category: str
    score: float | None
    by_tier: dict[str, float | None]
    scored_results: int
    unscored_results: int


class LeaderboardRow(_Model):
    model: ModelSummaryOut
    overall: float | None
    scores: list[ScoreCell]
    avg_cost_per_task_usd: float | None
    p50_latency_ms: int | None
    open_s1_s2_defects: int


class Leaderboard(_Model):
    run_id: int | None
    run_label: str | None
    run_source: str | None
    rows: list[LeaderboardRow]


class TierTokens(_Model):
    avg: UsageRecord
    total: UsageRecord


class ModelDetail(_Model):
    model: ModelSummaryOut
    run_id: int
    last_run_at: str | None
    overall: float | None
    scores: list[ScoreCell]
    tokens_by_tier: dict[str, TierTokens]
    costliest_task_ids: list[str]
    p50_latency_ms: int | None
    p95_latency_ms: int | None
    open_s1_s2_defects: int


class Evidence(_Model):
    prompt_excerpt: str | None
    response_excerpt: str | None
    checker_output: str | None


class DefectOut(_Model):
    id: int
    result_id: int
    model_key: str
    task_id: str
    category: str
    tier: str
    type: str
    severity: str
    title: str
    expected: str | None
    actual: str | None
    evidence: Evidence
    source: str
    status: str


class DefectList(_Model):
    count: int
    items: list[DefectOut]


class ResultSummary(_Model):
    result_id: int
    task_id: str
    title: str
    tier: str
    category: str
    attempt: int
    score: int | None
    status: str
    needs_review: bool
    usage: UsageRecord


class TaskInfo(_Model):
    task_id: str
    title: str
    prompt: str
    version: int
    content_hash: str


class CheckOut(_Model):
    checker: str
    passed: bool
    output: str


class JudgeOut(_Model):
    judge_model_key: str
    score: int | None
    rationale: str | None


class ResultDetail(_Model):
    result_id: int
    model_key: str
    category: str
    tier: str
    task: TaskInfo
    response_text: str | None
    checks: list[CheckOut]
    judges: list[JudgeOut]
    score: int | None
    score_source: str | None
    needs_review: bool
    status: str
    usage: UsageRecord
    defects: list[DefectOut]


class ProfileOut(_Model):
    id: str | None
    name: str
    weights: dict[str, int]
    must_have: list[str]
    tier_mix: dict[str, int]
    max_cost_per_task_usd: float | None
    max_p95_latency_ms: int | None
    is_template: bool


class Reason(_Model):
    rule: str
    text: str


class VerdictOut(_Model):
    model_key: str
    display_name: str
    verdict: str
    fit_score: float | None
    expected_cost_per_task_usd: float | None
    p95_latency_ms: int | None
    reasons: list[Reason]
    strengths: list[str]
    risks: list[str]
    cited_defect_ids: list[int]


class FitResponse(_Model):
    run_id: int | None
    profile: ProfileOut
    verdicts: list[VerdictOut]


class FitRequest(BaseModel):
    """Validated by hand so an invalid profile is a 400 (api-contract-spec §3), not a 422."""

    model_config = ConfigDict(extra="forbid")
    profile_id: str | None = None
    profile: dict[str, Any] | None = None
    run_id: int | None = None
