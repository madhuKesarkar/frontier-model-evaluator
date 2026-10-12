"""Use-case fit (backend-spec §9, BE-AC-18..20, D-18, D-19)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.fixture import FixtureAdapter
from app.aggregates import ModelSummary, TokenStats, set_defect_status, summarize_model
from app.db import Base, Defect, make_engine, make_session_factory
from app.fit import (
    TEMPLATES,
    TEMPLATES_BY_ID,
    BlockingDefect,
    Profile,
    VerdictKind,
    blocking_s1_defects,
    compute_fit,
)
from app.runner import RunConfig
from app.suite import Category, Tier
from tests.test_runner import BY_ID, CLAUDE, make_runner, ok

CATS = [c.value for c in Category]


def summary(
    scores: dict[str, float] | None = None,
    cost: float | None = 0.01,
    p95: int | None = 8000,
) -> ModelSummary:
    """A model with the same score in every tier of each category."""
    scores = scores or {}
    by_tier = {c: {t.value: scores.get(c, 4.5) for t in Tier} for c in CATS}
    tokens = {t.value: TokenStats(count=1, avg_cost_usd=cost) for t in Tier}
    cats: dict[str, float | None] = {c: scores.get(c, 4.5) for c in CATS}
    return ModelSummary("m", 4.5, cats, by_tier, 18, 0, tokens, cost, 5000, p95, 0, 0)  # type: ignore[arg-type]


CODE_ASSISTANT = TEMPLATES_BY_ID["tpl-code-assistant"]


def test_three_templates_match_spec_9_1() -> None:
    assert [t.name for t in TEMPLATES] == [
        "Test-case generation tool",
        "Customer support chatbot",
        "Code assistant",
    ]
    assert all(t.is_template and sum(t.tier_mix.values()) == 100 for t in TEMPLATES)
    assert CODE_ASSISTANT.must_have == [Category.CODE_GENERATION]


def test_recommended_when_all_clear() -> None:
    v = compute_fit(CODE_ASSISTANT, summary(), [])
    assert v.verdict == VerdictKind.RECOMMENDED and v.fit_score == 4.5
    assert v.reasons[0]["rule"] == "all_clear"


def test_BE_AC18_s1_in_must_have_blocks_and_is_cited() -> None:
    blocker = BlockingDefect(17, "code_generation", "Refund before receipt")
    v = compute_fit(CODE_ASSISTANT, summary(), [blocker])
    assert v.verdict == VerdictKind.NOT_RECOMMENDED
    assert v.cited_defect_ids == [17]
    assert any(r["rule"] == "s1_in_must_have" for r in v.reasons)


def test_s1_outside_must_have_does_not_block() -> None:
    v = compute_fit(CODE_ASSISTANT, summary(), [BlockingDefect(3, "tool_use", "x")])
    assert v.verdict == VerdictKind.RECOMMENDED and v.cited_defect_ids == []


def test_BE_AC19_cost_over_limit_is_at_best_conditional() -> None:
    profile = CODE_ASSISTANT.model_copy(update={"max_cost_per_task_usd": 0.01})
    v = compute_fit(profile, summary(cost=0.03), [])
    assert v.verdict == VerdictKind.CONDITIONAL
    assert v.expected_cost_per_task_usd == 0.03
    assert any(r["rule"] == "cost_over_limit" and "0.0300" in r["text"] for r in v.reasons)


def test_BE_AC20_fit_is_deterministic() -> None:
    s = summary({"reasoning": 3.2, "tool_use": 2.9})
    blocker = [BlockingDefect(5, "code_generation", "x")]
    assert compute_fit(CODE_ASSISTANT, s, blocker) == compute_fit(CODE_ASSISTANT, s, blocker)


def test_fit_between_3_and_4_is_conditional() -> None:
    v = compute_fit(CODE_ASSISTANT, summary({c: 3.5 for c in CATS}), [])
    assert v.verdict == VerdictKind.CONDITIONAL and v.fit_score == 3.5


@pytest.mark.parametrize(
    "scores,rule",
    [({c: 2.5 for c in CATS}, "fit_below_3"), ({"code_generation": 2.9}, "must_have_below_3")],
)
def test_not_recommended_rules(scores: dict[str, float], rule: str) -> None:
    v = compute_fit(CODE_ASSISTANT, summary(scores), [])
    assert v.verdict == VerdictKind.NOT_RECOMMENDED
    assert any(r["rule"] == rule for r in v.reasons)


def test_latency_limit_makes_conditional() -> None:
    chatbot = TEMPLATES_BY_ID["tpl-support-chatbot"]
    v = compute_fit(chatbot, summary(p95=20_000), [])
    assert v.verdict == VerdictKind.CONDITIONAL
    assert any(r["rule"] == "latency_over_limit" for r in v.reasons)


def test_tier_mix_weights_category_score() -> None:
    s = summary()
    s.by_tier["code_generation"] = {"simple": 5.0, "mid": 4.0, "complex": 2.0}
    only_code = Profile(
        name="code only", weights={Category.CODE_GENERATION: 1}, tier_mix={
            Tier.SIMPLE: 20, Tier.MID: 50, Tier.COMPLEX: 30}
    )  # fmt: skip
    # 0.2*5 + 0.5*4 + 0.3*2 = 3.6
    assert compute_fit(only_code, s, []).fit_score == 3.6


def test_strengths_and_risks() -> None:
    v = compute_fit(CODE_ASSISTANT, summary({"long_context": 2.0, "test_design": 3.0}), [])
    assert v.strengths[0] == "code_generation"
    assert v.risks == ["long_context", "test_design"]


@pytest.mark.parametrize(
    "bad",
    [
        {"tier_mix": {"simple": 50, "mid": 30, "complex": 10}},
        {"weights": {"code_generation": 0}},
        {"weights": {"code_generation": 6}},
        {"max_cost_per_task_usd": -1},
    ],
)
def test_invalid_profiles_rejected(bad: dict[str, object]) -> None:
    base: dict[str, object] = {
        "name": "x",
        "weights": {"code_generation": 3},
        "tier_mix": {"simple": 20, "mid": 60, "complex": 20},
    }
    with pytest.raises(ValidationError):
        Profile.model_validate({**base, **bad})


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'fit.db'}")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def test_BE_AC18_end_to_end_false_positive_removes_block(sessions: sessionmaker[Session]) -> None:
    """A real S1 (tool-use refund before receipt) blocks the chatbot template until a reviewer
    marks it false_positive (D-18)."""
    refund = (
        '{"calls": [{"tool": "create_return", "arguments": {"order_id": "ORD-7781",'
        ' "item_ids": ["I1", "I3"], "reason": "changed_mind"}}, {"tool": "issue_refund",'
        ' "arguments": {"order_id": "ORD-7781", "amount_inr": 4298}}],'
        ' "message_to_customer": "Refunded."}'
    )
    answers = {t.task_id: t.reference_response for t in BY_ID.values()
               if t.category in {"long_context", "tool_use"} and not t.uses_judge}  # fmt: skip
    answers["TU-C-01"] = refund
    scripts = {f"answer:{k}": [ok(v)] for k, v in answers.items()}
    runner = make_runner(sessions, {"claude": FixtureAdapter(scripts)},
                         tasks=[BY_ID[k] for k in answers])  # fmt: skip
    run_id = runner.start(RunConfig(model_keys=[CLAUDE.key]))
    chatbot = TEMPLATES_BY_ID["tpl-support-chatbot"]
    with sessions() as s:
        blockers = blocking_s1_defects(s, run_id, "claude")
        verdict = compute_fit(chatbot, summarize_model(s, run_id, "claude"), blockers)
    assert verdict.verdict == VerdictKind.NOT_RECOMMENDED
    assert verdict.cited_defect_ids == [b.id for b in blockers] and blockers

    with sessions.begin() as s:
        for d in s.scalars(select(Defect).where(Defect.severity == "S1")):
            set_defect_status(s, d.id, "false_positive")
    with sessions() as s:
        assert blocking_s1_defects(s, run_id, "claude") == []
