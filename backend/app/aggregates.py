"""Aggregates and defect review (backend-spec BE-R17, BE-R19, BE-R22)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Defect, Result
from app.scoring import deterministic_score, final_score
from app.suite import Category, Tier

COUNTED_DEFECT_STATUSES = {"open", "confirmed"}  # BE-R19: false_positive never counts


def _r1(values: list[float]) -> float | None:
    """Mean to 1 decimal, rounding half up (4.25 -> 4.3), as a reader of a scorecard expects."""
    if not values:
        return None
    return float(Decimal(str(mean(values))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


@dataclass
class TokenStats:
    count: int = 0
    avg: dict[str, float | None] = field(default_factory=dict)
    total: dict[str, int | None] = field(default_factory=dict)
    estimated: bool = False
    avg_cost_usd: float | None = None
    p50_latency_ms: int | None = None
    p95_latency_ms: int | None = None


@dataclass
class ModelSummary:
    model_key: str
    overall: float | None
    categories: dict[str, float | None]
    by_tier: dict[str, dict[str, float | None]]
    scored: int
    unscored: int
    tokens_by_tier: dict[str, TokenStats]
    avg_cost_per_task_usd: float | None
    p50_latency_ms: int | None
    open_s1_s2_defects: int
    needs_review: int


TOKEN_FIELDS = ("input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens",
                "overhead_tokens")  # fmt: skip


def _token_stats(rows: list[Result]) -> TokenStats:
    stats = TokenStats(count=len(rows))
    for name in TOKEN_FIELDS:
        values = [getattr(r, name) for r in rows if getattr(r, name) is not None]
        # BE-R21: a field nobody reported stays None ("n/a"), never 0
        stats.total[name] = sum(values) if values else None
        stats.avg[name] = round(mean(values), 1) if values else None
    stats.estimated = any(any(r.tokens_estimated.values()) for r in rows if r.tokens_estimated)
    costs = [r.api_equiv_cost_usd for r in rows if r.api_equiv_cost_usd is not None]
    stats.avg_cost_usd = round(mean(costs), 6) if costs else None
    latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
    stats.p50_latency_ms = _percentile(latencies, 50)
    stats.p95_latency_ms = _percentile(latencies, 95)
    return stats


def summarize_model(s: Session, run_id: int, model_key: str) -> ModelSummary:
    rows = list(
        s.scalars(select(Result).where(Result.run_id == run_id, Result.model_key == model_key))
    )
    scored = [r for r in rows if r.status == "scored" and r.score is not None]
    by_cat_tier: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in scored:
        by_cat_tier[r.category][r.tier].append(float(r.score or 0))
    categories: dict[str, float | None] = {}
    by_tier: dict[str, dict[str, float | None]] = {}
    for cat in Category:
        tiers = by_cat_tier.get(cat.value, {})
        all_scores = [v for vals in tiers.values() for v in vals]
        categories[cat.value] = _r1(all_scores)
        by_tier[cat.value] = {t.value: _r1(tiers.get(t.value, [])) for t in Tier}
    cat_values = [v for v in categories.values() if v is not None]
    responded = [r for r in rows if r.response_text is not None]
    tokens = {t.value: _token_stats([r for r in responded if r.tier == t.value]) for t in Tier}
    costs = [r.api_equiv_cost_usd for r in responded if r.api_equiv_cost_usd is not None]
    latencies = [r.latency_ms for r in responded if r.latency_ms is not None]
    defects = s.scalars(
        select(Defect)
        .join(Result, Defect.result_id == Result.id)
        .where(Result.run_id == run_id, Defect.model_key == model_key)
    )
    open_s1_s2 = sum(
        1 for d in defects if d.status in COUNTED_DEFECT_STATUSES and d.severity in {"S1", "S2"}
    )
    return ModelSummary(
        model_key=model_key,
        overall=_r1(cat_values),
        categories=categories,
        by_tier=by_tier,
        scored=len(scored),
        unscored=len(rows) - len(scored),
        tokens_by_tier=tokens,
        avg_cost_per_task_usd=round(mean(costs), 6) if costs else None,
        p50_latency_ms=_percentile(latencies, 50),
        open_s1_s2_defects=open_s1_s2,
        needs_review=sum(1 for r in rows if r.needs_review),
    )


def set_defect_status(s: Session, defect_id: int, status: str) -> Defect:
    """Reviewer decision (BE-R19). Marking an automated defect false_positive re-scores
    its result from the remaining counted defects (and the judge, D-16)."""
    if status not in {"open", "confirmed", "false_positive"}:
        raise ValueError(f"invalid defect status {status!r}")
    defect = s.get(Defect, defect_id)
    if defect is None:
        raise LookupError(f"defect {defect_id} not found")
    defect.status = status
    s.flush()
    result = s.get(Result, defect.result_id)
    if result is not None and result.score_source != "human":
        rescore(s, result)
    return defect


def rescore(s: Session, result: Result) -> None:
    auto = s.scalars(
        select(Defect).where(Defect.result_id == result.id, Defect.source == "auto")
    ).all()
    severities = [d.severity for d in auto if d.status in COUNTED_DEFECT_STATUSES]
    judge_scores = [js.score for js in result.judge_scores if js.score is not None]
    uses_judge = bool(result.judge_scores)
    det = deterministic_score(severities)
    result.score, result.needs_review = final_score(
        det, judge_scores[0] if judge_scores else None, uses_judge
    )
