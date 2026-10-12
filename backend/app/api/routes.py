"""Demo read endpoints (api-contract-spec §3) and POST /fit."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.aggregates import ModelSummary, TokenStats, summarize_model
from app.api import schemas as sc
from app.db import Defect, Result, Run
from app.fit import TEMPLATES, TEMPLATES_BY_ID, Profile, blocking_s1_defects, compute_fit
from app.registry import ModelEntry
from app.suite import Category, Task, Tier

router = APIRouter()
DefectType = Annotated[
    str | None,
    Query(
        pattern="^(HALLUCINATION|INSTRUCTION_VIOLATION|FORMAT_BREAK|INCORRECT_CODE|"
        "REASONING_ERROR|TOOL_CALL_ERROR|OVER_REFUSAL|UNSAFE_OUTPUT|TRUNCATION|"
        "TIMEOUT_ERROR|INCONSISTENCY)$"
    ),
]
Severity = Annotated[str | None, Query(pattern="^S[1-4]$")]
Status = Annotated[str | None, Query(pattern="^(open|confirmed|false_positive)$")]


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        if not inspect(session.get_bind()).has_table("run"):
            raise HTTPException(
                503, "Database not set up yet: run `make migrate` (or `make demo-data`)"
            )
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not found")


def iso_z(value: datetime | None) -> str | None:
    """API-AC-03: UTC with a trailing Z (stored naive UTC)."""
    return value.replace(microsecond=0).isoformat() + "Z" if value else None


def registry(request: Request) -> dict[str, ModelEntry]:
    models: dict[str, ModelEntry] = request.app.state.models
    return models


def tasks(request: Request) -> dict[str, Task]:
    by_id: dict[str, Task] = request.app.state.tasks
    return by_id


def model_out(
    key: str, models: dict[str, ModelEntry], provider: str = "unknown"
) -> sc.ModelSummaryOut:
    m = models.get(key)
    if m is None:  # a model from an older run that is no longer in the registry
        return sc.ModelSummaryOut(
            key=key,
            provider=provider,
            access_mode="unknown",
            model_id=key,
            display_name=key,
            enabled=False,
        )
    return sc.ModelSummaryOut(
        key=m.key,
        provider=m.provider.value,
        access_mode=m.access_mode.value,
        model_id=m.model_id,
        display_name=m.display_name,
        enabled=m.enabled,
    )


def resolve_run(s: Session, run_id: int | None) -> Run | None:
    if run_id is not None:
        run = s.get(Run, run_id)
        if run is None:
            raise not_found()
        return run
    return s.scalars(
        select(Run).where(Run.status == "completed").order_by(Run.finished_at.desc(), Run.id.desc())
    ).first()


def score_cells(
    summary: ModelSummary, s: Session, run_id: int, tier: Tier | None, category: Category | None
) -> list[sc.ScoreCell]:
    rows = s.scalars(
        select(Result).where(Result.run_id == run_id, Result.model_key == summary.model_key)
    ).all()
    cells = []
    for cat in Category:
        if category is not None and cat != category:
            continue
        in_cat = [
            r for r in rows if r.category == cat.value and (tier is None or r.tier == tier.value)
        ]
        scored = sum(1 for r in in_cat if r.status == "scored" and r.score is not None)
        score = summary.by_tier[cat.value][tier.value] if tier else summary.categories[cat.value]
        cells.append(
            sc.ScoreCell(
                category=cat.value,
                score=score,
                by_tier=summary.by_tier[cat.value],
                scored_results=scored,
                unscored_results=len(in_cat) - scored,
            )
        )
    return cells


def usage(r: Result) -> sc.UsageRecord:
    est = r.tokens_estimated or {}
    return sc.UsageRecord(
        input_tokens=r.input_tokens,
        input_tokens_estimated=bool(est.get("input_tokens")),
        output_tokens=r.output_tokens,
        output_tokens_estimated=bool(est.get("output_tokens")),
        reasoning_tokens=r.reasoning_tokens,
        cached_tokens=r.cached_tokens,
        overhead_tokens=r.overhead_tokens,
        api_equiv_cost_usd=r.api_equiv_cost_usd,
        latency_ms=r.latency_ms,
    )


def stats_usage(stats: TokenStats, part: str) -> sc.UsageRecord:
    values: dict[str, Any] = stats.avg if part == "avg" else stats.total
    cost = (
        stats.avg_cost_usd
        if part == "avg"
        else (
            round(stats.avg_cost_usd * stats.count, 6) if stats.avg_cost_usd is not None else None
        )
    )
    return sc.UsageRecord(
        input_tokens=values.get("input_tokens"),
        input_tokens_estimated=stats.estimated,
        output_tokens=values.get("output_tokens"),
        output_tokens_estimated=stats.estimated,
        reasoning_tokens=values.get("reasoning_tokens"),
        cached_tokens=values.get("cached_tokens"),
        overhead_tokens=values.get("overhead_tokens"),
        api_equiv_cost_usd=cost,
        latency_ms=stats.p50_latency_ms if part == "avg" else None,
    )


def defect_out(d: Defect) -> sc.DefectOut:
    ev = d.evidence or {}
    return sc.DefectOut(
        id=d.id,
        result_id=d.result_id,
        model_key=d.model_key,
        task_id=d.task_id,
        category=d.category,
        tier=d.tier,
        type=d.type,
        severity=d.severity,
        title=d.title,
        expected=d.expected,
        actual=d.actual,
        evidence=sc.Evidence(
            prompt_excerpt=ev.get("prompt_excerpt"),
            response_excerpt=ev.get("response_excerpt"),
            checker_output=ev.get("checker_output"),
        ),
        source=d.source,
        status=d.status,
    )


def profile_out(p: Profile) -> sc.ProfileOut:
    return sc.ProfileOut(
        id=p.id,
        name=p.name,
        weights={k.value: v for k, v in p.weights.items()},
        must_have=[c.value for c in p.must_have],
        tier_mix={k.value: v for k, v in p.tier_mix.items()},
        max_cost_per_task_usd=p.max_cost_per_task_usd,
        max_p95_latency_ms=p.max_p95_latency_ms,
        is_template=p.is_template,
    )


@router.get("/models", response_model=list[sc.ModelSummaryOut])
def list_models(request: Request) -> list[sc.ModelSummaryOut]:
    models = registry(request)
    return [model_out(k, models) for k in models]


@router.get("/leaderboard", response_model=sc.Leaderboard)
def leaderboard(
    request: Request,
    s: SessionDep,
    run_id: int | None = None,
    tier: Tier | None = None,
    category: Category | None = None,
) -> sc.Leaderboard:
    run = resolve_run(s, run_id)
    if run is None:  # no completed run yet: the UI shows its empty state
        return sc.Leaderboard(run_id=None, run_label=None, run_source=None, rows=[])
    models = registry(request)
    rows = []
    for key in run.model_keys:
        summary = summarize_model(s, run.id, key)
        cells = score_cells(summary, s, run.id, tier, category)
        values = [c.score for c in cells if c.score is not None]
        overall = (
            summary.overall
            if tier is None and category is None
            else (round(sum(values) / len(values), 1) if values else None)
        )
        provider = next((r.provider for r in run.results if r.model_key == key), "unknown")
        rows.append(
            sc.LeaderboardRow(
                model=model_out(key, models, provider),
                overall=overall,
                scores=cells,
                avg_cost_per_task_usd=summary.avg_cost_per_task_usd,
                p50_latency_ms=summary.p50_latency_ms,
                open_s1_s2_defects=summary.open_s1_s2_defects,
            )
        )
    rows.sort(key=lambda r: (r.overall is None, -(r.overall or 0), r.model.key))
    return sc.Leaderboard(
        run_id=run.id,
        run_label=run.params.get("label") or None,
        run_source=run.params.get("source"),
        rows=rows,
    )


def _run_for_model(s: Session, key: str, run_id: int | None) -> Run:
    run = resolve_run(s, run_id)
    if run is None or key not in run.model_keys:
        raise not_found()
    return run


@router.get("/models/{key}", response_model=sc.ModelDetail)
def model_detail(
    key: str, request: Request, s: SessionDep, run_id: int | None = None
) -> sc.ModelDetail:
    run = _run_for_model(s, key, run_id)
    summary = summarize_model(s, run.id, key)
    rows = [r for r in run.results if r.model_key == key and r.api_equiv_cost_usd is not None]
    costliest = [r.task_id for r in sorted(rows, key=lambda r: -(r.api_equiv_cost_usd or 0))[:3]]
    provider = next((r.provider for r in run.results if r.model_key == key), "unknown")
    return sc.ModelDetail(
        model=model_out(key, registry(request), provider),
        run_id=run.id,
        last_run_at=iso_z(run.finished_at or run.started_at),
        overall=summary.overall,
        scores=score_cells(summary, s, run.id, None, None),
        tokens_by_tier={
            t: sc.TierTokens(avg=stats_usage(st, "avg"), total=stats_usage(st, "total"))
            for t, st in summary.tokens_by_tier.items()
        },
        costliest_task_ids=costliest,
        p50_latency_ms=summary.p50_latency_ms,
        p95_latency_ms=summary.p95_latency_ms,
        open_s1_s2_defects=summary.open_s1_s2_defects,
    )


@router.get("/models/{key}/defects", response_model=sc.DefectList)
def model_defects(
    key: str,
    s: SessionDep,
    run_id: int | None = None,
    severity: Severity = None,
    type: DefectType = None,  # noqa: A002 - contract name
    tier: Tier | None = None,
    category: Category | None = None,
    status: Status = None,
) -> sc.DefectList:
    run = _run_for_model(s, key, run_id)
    q = (
        select(Defect)
        .join(Result, Defect.result_id == Result.id)
        .where(Result.run_id == run.id, Defect.model_key == key)
    )
    if severity:
        q = q.where(Defect.severity == severity)
    if type:
        q = q.where(Defect.type == type)
    if tier:
        q = q.where(Defect.tier == tier.value)
    if category:
        q = q.where(Defect.category == category.value)
    if status:
        q = q.where(Defect.status == status)
    order = {"S1": 1, "S2": 2, "S3": 3, "S4": 4}
    items = sorted(s.scalars(q).all(), key=lambda d: (order.get(d.severity, 9), d.task_id, d.id))
    return sc.DefectList(count=len(items), items=[defect_out(d) for d in items])


@router.get("/models/{key}/results", response_model=list[sc.ResultSummary])
def model_results(
    key: str,
    request: Request,
    s: SessionDep,
    run_id: int | None = None,
    tier: Tier | None = None,
    category: Category | None = None,
) -> list[sc.ResultSummary]:
    run = _run_for_model(s, key, run_id)
    by_id = tasks(request)
    out = []
    for r in sorted(run.results, key=lambda r: (r.task_id, r.attempt)):
        if (
            r.model_key != key
            or (tier and r.tier != tier.value)
            or (category and r.category != category.value)
        ):
            continue
        title = by_id[r.task_id].title if r.task_id in by_id else r.task_id
        out.append(
            sc.ResultSummary(
                result_id=r.id,
                task_id=r.task_id,
                title=title,
                tier=r.tier,
                category=r.category,
                attempt=r.attempt,
                score=r.score,
                status=r.status,
                needs_review=r.needs_review,
                usage=usage(r),
            )
        )
    return out


@router.get("/results/{result_id}", response_model=sc.ResultDetail)
def result_detail(result_id: int, request: Request, s: SessionDep) -> sc.ResultDetail:
    r = s.get(Result, result_id)
    if r is None:
        raise not_found()
    task = tasks(request).get(r.task_id)
    info = sc.TaskInfo(
        task_id=r.task_id,
        title=task.title if task else r.task_id,
        prompt=task.prompt if task else "",
        version=task.version if task else 0,
        content_hash=r.task_hash,
    )
    defects = s.scalars(select(Defect).where(Defect.result_id == r.id).order_by(Defect.id)).all()
    return sc.ResultDetail(
        result_id=r.id,
        model_key=r.model_key,
        category=r.category,
        tier=r.tier,
        task=info,
        response_text=r.response_text,
        checks=[sc.CheckOut(**c) for c in r.checks],
        judges=[
            sc.JudgeOut(judge_model_key=j.judge_model_key, score=j.score, rationale=j.rationale)
            for j in r.judge_scores
        ],
        score=r.score,
        score_source=r.score_source,
        needs_review=r.needs_review,
        status=r.status,
        usage=usage(r),
        defects=[defect_out(d) for d in defects],
    )


@router.get("/profile-templates", response_model=list[sc.ProfileOut])
def profile_templates() -> list[sc.ProfileOut]:
    return [profile_out(t) for t in TEMPLATES]


@router.post("/fit", response_model=sc.FitResponse)
def fit(body: sc.FitRequest, request: Request, s: SessionDep) -> sc.FitResponse:
    if (body.profile_id is None) == (body.profile is None):
        raise HTTPException(400, "Send exactly one of profile_id or profile")
    if body.profile_id is not None:
        profile = TEMPLATES_BY_ID.get(body.profile_id)
        if profile is None:
            raise not_found()
    else:
        try:
            profile = Profile.model_validate({**(body.profile or {}), "is_template": False})
        except ValidationError as exc:
            msgs = "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())
            raise HTTPException(400, f"Invalid profile: {msgs}") from None
    run = resolve_run(s, body.run_id)
    if run is None:
        return sc.FitResponse(run_id=None, profile=profile_out(profile), verdicts=[])
    models = registry(request)
    verdicts = []
    for key in run.model_keys:
        v = compute_fit(
            profile, summarize_model(s, run.id, key), blocking_s1_defects(s, run.id, key)
        )
        verdicts.append(
            sc.VerdictOut(
                model_key=key,
                display_name=model_out(key, models).display_name,
                verdict=v.verdict.value,
                fit_score=v.fit_score,
                expected_cost_per_task_usd=v.expected_cost_per_task_usd,
                p95_latency_ms=v.p95_latency_ms,
                reasons=[sc.Reason(**r) for r in v.reasons],
                strengths=v.strengths,
                risks=v.risks,
                cited_defect_ids=v.cited_defect_ids,
            )
        )
    order = {"recommended": 0, "conditional": 1, "not_recommended": 2}
    verdicts.sort(key=lambda v: (order[v.verdict], -(v.fit_score or 0), v.model_key))
    return sc.FitResponse(run_id=run.id, profile=profile_out(profile), verdicts=verdicts)
