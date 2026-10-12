"""Use-case fit: profiles, templates and verdicts (backend-spec §9, D-18, D-19)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.aggregates import ModelSummary
from app.db import Defect, Result
from app.suite import Category, Tier


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str = Field(min_length=1)
    weights: dict[Category, int]
    must_have: list[Category] = Field(default_factory=list)
    tier_mix: dict[Tier, int]
    max_cost_per_task_usd: float | None = Field(default=None, ge=0)
    max_p95_latency_ms: int | None = Field(default=None, ge=0)
    is_template: bool = False

    @model_validator(mode="after")
    def _check(self) -> Profile:
        if any(not 0 <= w <= 5 for w in self.weights.values()):
            raise ValueError("weights must be between 0 and 5")
        if not any(self.weights.values()):
            raise ValueError("at least one category weight must be above 0")
        if any(v < 0 for v in self.tier_mix.values()) or sum(self.tier_mix.values()) != 100:
            raise ValueError("tier_mix percentages must be non-negative and total 100")
        return self


def _profile(pid: str, name: str, w: tuple[int, ...], must: list[Category],
             mix: tuple[int, int, int], cost: float | None = None,
             p95: int | None = None) -> Profile:  # fmt: skip
    cats: list[Category] = list(Category)
    return Profile(
        id=pid, name=name, weights=dict(zip(cats, w, strict=True)), must_have=must,
        tier_mix=dict(zip(list(Tier), mix, strict=True)), max_cost_per_task_usd=cost,
        max_p95_latency_ms=p95, is_template=True,
    )  # fmt: skip


#: D-19 / backend-spec §9.1. Weight order: CG, RA, SO, TD, LC, TU.
TEMPLATES = [
    _profile("tpl-test-case-gen", "Test-case generation tool", (1, 3, 4, 5, 2, 1),
             [Category.TEST_DESIGN], (20, 60, 20), cost=0.05),
    _profile("tpl-support-chatbot", "Customer support chatbot", (0, 3, 3, 0, 5, 5),
             [Category.LONG_CONTEXT, Category.TOOL_USE], (40, 40, 20), p95=15_000),
    _profile("tpl-code-assistant", "Code assistant", (5, 4, 3, 2, 2, 3),
             [Category.CODE_GENERATION], (20, 50, 30)),
]  # fmt: skip
TEMPLATES_BY_ID = {t.id: t for t in TEMPLATES}

LABEL = {
    Category.CODE_GENERATION: "Code Generation",
    Category.REASONING: "Reasoning & Analysis",
    Category.STRUCTURED_OUTPUT: "Structured Output",
    Category.TEST_DESIGN: "Test Design",
    Category.LONG_CONTEXT: "Long-Context Faithfulness",
    Category.TOOL_USE: "Tool Use",
}


class VerdictKind(StrEnum):
    RECOMMENDED = "recommended"
    CONDITIONAL = "conditional"
    NOT_RECOMMENDED = "not_recommended"


@dataclass(frozen=True)
class BlockingDefect:
    id: int
    category: str
    title: str


@dataclass
class Verdict:
    model_key: str
    verdict: VerdictKind
    fit_score: float | None
    expected_cost_per_task_usd: float | None
    p95_latency_ms: int | None
    reasons: list[dict[str, str]] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    cited_defect_ids: list[int] = field(default_factory=list)


def _q(value: float, places: str) -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def mix_weighted_category_score(
    summary: ModelSummary, category: Category, profile: Profile
) -> float | None:
    """BE-R23: a category score weighted by the profile's tier mix, using tier sub-scores
    (tiers without results are left out and the mix renormalised)."""
    subs = summary.by_tier.get(category.value, {})
    pairs = [(profile.tier_mix.get(t, 0), subs.get(t.value)) for t in Tier]
    used = [(w, s) for w, s in pairs if s is not None and w > 0]
    total = sum(w for w, _ in used)
    return sum(w * s for w, s in used) / total if total else None


def compute_fit(
    profile: Profile, summary: ModelSummary, s1_defects: list[BlockingDefect]
) -> Verdict:
    """BE-R23..R26. Deterministic: same inputs -> same output."""
    weighted = {c: w for c, w in profile.weights.items() if w > 0}
    scores = {c: mix_weighted_category_score(summary, c, profile) for c in Category}
    scored = {c: s for c, s in scores.items() if c in weighted and s is not None}
    weight_sum = sum(weighted[c] for c in scored)
    fit = (
        _q(sum(weighted[c] * s for c, s in scored.items()) / weight_sum, "0.01")
        if weight_sum
        else None
    )

    costs = {t: summary.tokens_by_tier[t.value].avg_cost_usd for t in Tier}
    mix_with_cost = [(profile.tier_mix.get(t, 0), costs[t]) for t in Tier if costs[t] is not None]
    mix_total = sum(w for w, _ in mix_with_cost)
    expected_cost = (
        _q(sum(w * c for w, c in mix_with_cost if c is not None) / mix_total, "0.000001")
        if mix_total
        else None
    )
    p95 = summary.p95_latency_ms

    hard: list[dict[str, str]] = []
    soft: list[dict[str, str]] = []
    cited: list[int] = []
    if fit is None:
        hard.append({"rule": "no_results", "text": "No scored results for the weighted categories"})
    elif fit < 3.0:
        hard.append({"rule": "fit_below_3", "text": f"Fit score {fit:.2f} is below 3.0"})
    for cat in profile.must_have:
        score = scores.get(cat)
        if score is None:
            hard.append(
                {
                    "rule": "must_have_not_evaluated",
                    "text": f"Must-have {LABEL[cat]} has no results",
                }
            )
        elif score < 3.0:
            hard.append(
                {
                    "rule": "must_have_below_3",
                    "text": f"Must-have {LABEL[cat]} scores {_q(score, '0.1')} (< 3.0)",
                }
            )
        for d in s1_defects:
            if d.category == cat.value:
                cited.append(d.id)
                hard.append(
                    {
                        "rule": "s1_in_must_have",
                        "text": f"S1 defect in must-have {LABEL[cat]}: {d.title}",
                    }
                )
    if fit is not None and 3.0 <= fit < 4.0:
        soft.append({"rule": "fit_between_3_and_4", "text": f"Fit score {fit:.2f} is below 4.0"})
    limit = profile.max_cost_per_task_usd
    if limit is not None and expected_cost is not None and expected_cost > limit:
        soft.append(
            {
                "rule": "cost_over_limit",
                "text": f"Expected API-equivalent cost ${expected_cost:.4f}/task exceeds "
                f"the ${limit:.4f} limit",
            }
        )
    lat = profile.max_p95_latency_ms
    if lat is not None and p95 is not None and p95 > lat:
        soft.append(
            {
                "rule": "latency_over_limit",
                "text": f"p95 latency {p95} ms exceeds the {lat} ms limit",
            }
        )

    if hard:
        kind, reasons = VerdictKind.NOT_RECOMMENDED, hard + soft
    elif soft:
        kind, reasons = VerdictKind.CONDITIONAL, soft
    else:
        kind = VerdictKind.RECOMMENDED
        reasons = [
            {"rule": "all_clear", "text": f"Fit score {fit:.2f}; no blockers or limits exceeded"}
        ]

    ranked = sorted(scored.items(), key=lambda kv: (-weighted[kv[0]] * kv[1], kv[0].value))
    strengths = [c.value for c, s in ranked if s >= 4.0][:3]
    risks = [c.value for c, s in sorted(scored.items(), key=lambda kv: kv[1]) if s < 3.5][:3]
    return Verdict(
        summary.model_key,
        kind,
        fit,
        expected_cost,
        p95,
        reasons,
        strengths,
        risks,
        sorted(set(cited)),
    )


def blocking_s1_defects(s: Session, run_id: int, model_key: str) -> list[BlockingDefect]:
    """D-18: S1 defects that are not false_positive (open or confirmed)."""
    rows = s.scalars(
        select(Defect)
        .join(Result, Defect.result_id == Result.id)
        .where(
            Result.run_id == run_id,
            Defect.model_key == model_key,
            Defect.severity == "S1",
            Defect.status != "false_positive",
        )
        .order_by(Defect.id)
    )
    return [BlockingDefect(d.id, d.category, d.title) for d in rows]
