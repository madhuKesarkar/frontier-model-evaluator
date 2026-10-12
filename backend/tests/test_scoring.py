"""Scoring, cost and judge rules (backend-spec §5, §8, BE-R12..R15, D-16)."""

from __future__ import annotations

import pytest

from app.cost import api_equivalent_cost
from app.judge import NoJudgeAvailable, parse_judge_output, pick_judge
from app.registry import ModelEntry
from app.scoring import deterministic_score, final_score


def model(key: str, provider: str) -> ModelEntry:
    return ModelEntry(
        key=key, provider=provider, access_mode="fixture", model_id=key, display_name=key,  # type: ignore[arg-type]
        context_window=0, price_input_per_mtok=1, price_output_per_mtok=2,
    )  # fmt: skip


CLAUDE, GPT, GEMINI = model("c", "anthropic"), model("g", "openai"), model("m", "google")


def test_BE_AC16_cost_formula_exact() -> None:
    assert api_equivalent_cost(1000, 500, 3.00, 15.00) == pytest.approx(0.0105, abs=1e-9)
    assert f"{api_equivalent_cost(1000, 500, 3.00, 15.00):.6f}" == "0.010500"


def test_cost_counts_reasoning_tokens_as_output() -> None:
    assert api_equivalent_cost(1000, 500, 3.0, 15.0, reasoning_tokens=500) == 0.018


def test_BE_AC17_unknown_tokens_give_no_cost_not_zero() -> None:
    assert api_equivalent_cost(None, 500, 3.0, 15.0) is None


@pytest.mark.parametrize(
    "failed,expected", [([], 5), (["S4"], 4), (["S3", "S4"], 3), (["S2"], 2), (["S3", "S1"], 1)]
)
def test_deterministic_score_follows_worst_severity(failed: list[str], expected: int) -> None:
    assert deterministic_score(failed) == expected


def test_BE_AC13_failed_unit_tests_cap_score_even_if_judge_says_5() -> None:
    det = deterministic_score(["S2"])  # INCORRECT_CODE on_fail severity S2
    assert final_score(det, judge_score=5, uses_judge=True) == (2, False)


def test_D16_lower_of_judge_and_checks() -> None:
    assert final_score(5, judge_score=3, uses_judge=True) == (3, False)
    assert final_score(3, judge_score=5, uses_judge=True) == (3, False)


def test_missing_judge_score_flags_review() -> None:
    assert final_score(4, judge_score=None, uses_judge=True) == (4, True)


def test_no_judge_task_ignores_judge() -> None:
    assert final_score(5, judge_score=None, uses_judge=False) == (5, False)


@pytest.mark.parametrize("candidate", [CLAUDE, GPT, GEMINI])
def test_BE_AC11_judge_is_never_from_the_candidates_provider(candidate: ModelEntry) -> None:
    judge = pick_judge(candidate.provider, [CLAUDE, GPT, GEMINI])
    assert judge.provider != candidate.provider


def test_rotation_falls_back_to_next_provider() -> None:
    assert pick_judge(CLAUDE.provider, [CLAUDE, GEMINI]) is GEMINI


def test_no_other_provider_ready_raises() -> None:
    with pytest.raises(NoJudgeAvailable):
        pick_judge(CLAUDE.provider, [CLAUDE])


@pytest.mark.parametrize(
    "text",
    ['{"score": 7, "rationale": "x"}', '{"score": "4"}', "not json", '{"score": true}', "[]"],
)
def test_malformed_judge_output_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        parse_judge_output(text)


def test_judge_output_parsed_and_unknown_defect_types_dropped() -> None:
    verdict = parse_judge_output(
        '```json\n{"score": 2, "rationale": "invented a field",'
        ' "defects": [{"type": "HALLUCINATION", "severity": "S2", "title": "made up"},'
        ' {"type": "BOGUS", "severity": "S1"}]}\n```'
    )
    assert verdict.score == 2
    assert verdict.defects == [{"type": "HALLUCINATION", "severity": "S2", "title": "made up"}]
