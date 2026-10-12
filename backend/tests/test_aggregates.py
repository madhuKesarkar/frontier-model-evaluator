"""Aggregates and false-positive handling (BE-R17, BE-R19, BE-R22, BE-AC-15)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.fixture import FixtureAdapter
from app.aggregates import set_defect_status, summarize_model
from app.db import Base, Defect, Result, make_engine, make_session_factory
from app.runner import RunConfig
from tests.test_runner import BY_ID, CLAUDE, make_runner, ok


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'agg.db'}")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def run_with(sessions: sessionmaker[Session], answers: dict[str, str]) -> int:
    tasks = [BY_ID[t] for t in answers]
    claude = FixtureAdapter({f"answer:{t}": [ok(a)] for t, a in answers.items()})
    return make_runner(sessions, {"claude": claude}, tasks=tasks).start(
        RunConfig(model_keys=[CLAUDE.key])
    )


def test_category_tier_and_overall_scores(sessions: sessionmaker[Session]) -> None:
    run_id = run_with(
        sessions,
        {
            "RA-S-01": BY_ID["RA-S-01"].reference_response,  # 5
            "RA-M-01": "ANSWER: 8637.60",  # REASONING_ERROR S2 -> 2
            "SO-S-01": BY_ID["SO-S-01"].reference_response,  # 5
        },
    )
    with sessions() as s:
        summary = summarize_model(s, run_id, "claude")
    assert summary.categories["reasoning"] == 3.5
    assert summary.by_tier["reasoning"] == {"simple": 5.0, "mid": 2.0, "complex": None}
    assert summary.categories["structured_output"] == 5.0
    assert summary.categories["code_generation"] is None  # not run: no fake score
    assert summary.overall == 4.3  # mean of evaluated categories (3.5, 5.0) = 4.25 -> 4.3
    assert summary.open_s1_s2_defects == 1


def test_token_stats_per_tier(sessions: sessionmaker[Session]) -> None:
    run_id = run_with(sessions, {"RA-S-01": BY_ID["RA-S-01"].reference_response})
    with sessions() as s:
        summary = summarize_model(s, run_id, "claude")
    simple = summary.tokens_by_tier["simple"]
    assert simple.count == 1 and simple.total["input_tokens"] == 1000
    assert simple.avg["reasoning_tokens"] is None  # BE-R21
    assert simple.avg_cost_usd == pytest.approx(0.0105)
    assert summary.tokens_by_tier["complex"].count == 0


def test_BE_AC15_false_positive_no_longer_counts(sessions: sessionmaker[Session]) -> None:
    run_id = run_with(sessions, {"RA-M-01": "Total is 7341.96.\nANSWER: 7,341.96"})
    with sessions() as s:
        before = summarize_model(s, run_id, "claude")
        defect = s.scalars(select(Defect)).one()
    assert before.categories["reasoning"] == 2.0 and before.open_s1_s2_defects == 1

    with sessions.begin() as s:  # reviewer: the comma format is acceptable
        set_defect_status(s, defect.id, "false_positive")
    with sessions() as s:
        after = summarize_model(s, run_id, "claude")
        result = s.scalars(select(Result)).one()
    assert after.open_s1_s2_defects == 0
    assert result.score == 5 and after.categories["reasoning"] == 5.0


def test_invalid_defect_status_rejected(sessions: sessionmaker[Session]) -> None:
    run_with(sessions, {"RA-M-01": "ANSWER: 1"})
    with sessions.begin() as s:
        defect = s.scalars(select(Defect)).one()
        with pytest.raises(ValueError):
            set_defect_status(s, defect.id, "ignored")
