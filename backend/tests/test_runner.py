"""Evaluation runner integration tests with recorded adapters and a real SQLite DB
(backend-spec §4, BE-R5..R9, BE-R12..R19)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.fixture import FixtureAdapter, Script
from app.checkers import RunResult
from app.db import Base, Defect, JudgeScore, Result, Run, make_engine, make_session_factory
from app.judge import judge_output_json
from app.registry import ModelEntry
from app.runner import EvaluationRunner, RunConfig, RunConflict
from app.sandbox import SandboxUnavailable
from app.settings import REPO_ROOT
from app.suite import Task, load_suite

SUITE = load_suite(REPO_ROOT / "suite/v1")
BY_ID = {t.task_id: t for t in SUITE}
USAGE = {"input_tokens": 1000, "output_tokens": 500}


def entry(key: str, provider: str) -> ModelEntry:
    return ModelEntry.model_validate(
        {
            "key": key, "provider": provider, "access_mode": "fixture", "model_id": key,
            "display_name": key, "context_window": 0,
            "price_input_per_mtok": 3.0, "price_output_per_mtok": 15.0,
        }
    )  # fmt: skip


CLAUDE, GPT = entry("claude", "anthropic"), entry("gpt", "openai")


class PassingRunner:
    """Stand-in CodeRunner for tests that are not about code execution."""

    def __init__(self, passed: bool = True) -> None:
        self.passed = passed

    def run_tests(self, solution: str, tests: str) -> RunResult:
        return RunResult(self.passed, "1 passed" if self.passed else "1 failed")


def ok(text: str, **usage: Any) -> dict[str, Any]:
    return {"text": text, "usage": {**USAGE, **usage}, "latency_ms": 1200}


def perfect_scripts(tasks: list[Task], judged_model: str) -> dict[str, Script]:
    """Reference answers for every task, plus a score-5 judge reply for `judged_model`."""
    scripts: dict[str, Script] = {f"answer:{t.task_id}": [ok(t.reference_response)] for t in tasks}
    for t in tasks:
        scripts[f"judge:{judged_model}:{t.task_id}"] = [ok(judge_output_json(5))]
    return scripts


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'fme.db'}")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def make_runner(
    sessions: sessionmaker[Session],
    adapters: dict[str, FixtureAdapter],
    tasks: list[Task] = SUITE,
    code_runner: PassingRunner | None = None,
) -> EvaluationRunner:
    return EvaluationRunner(
        sessions, [CLAUDE, GPT], tasks, dict(adapters), code_runner or PassingRunner(),
        sleep=lambda _: None,
    )  # fmt: skip


def results(sessions: sessionmaker[Session], run_id: int) -> list[Result]:
    with sessions() as s:
        return list(s.scalars(select(Result).where(Result.run_id == run_id).order_by(Result.id)))


def get_run(sessions: sessionmaker[Session], run_id: int) -> Run:
    with sessions() as s:
        run = s.get(Run, run_id)
        assert run is not None
        return run


def test_BE_AC05_result_count_and_statuses(sessions: sessionmaker[Session]) -> None:
    claude = FixtureAdapter(perfect_scripts(SUITE, judged_model="gpt"))
    gpt = FixtureAdapter(perfect_scripts(SUITE, judged_model="claude"))
    runner = make_runner(sessions, {"claude": claude, "gpt": gpt})
    run_id = runner.start(RunConfig(model_keys=["claude", "gpt"], repeats=2, call_cap=1000))
    rows = results(sessions, run_id)
    assert len(rows) == 2 * 18 * 2
    assert {r.status for r in rows} <= {"scored", "error", "skipped"}
    assert all(r.score == 5 for r in rows), [(r.task_id, r.score) for r in rows if r.score != 5]
    assert get_run(sessions, run_id).status == "completed"


def test_BE_AC06_three_transient_errors_then_success(sessions: sessionmaker[Session]) -> None:
    task = BY_ID["RA-S-01"]  # no judge: only answer calls count
    script = [{"error": "transient"}] * 3 + [ok(task.reference_response)]
    claude = FixtureAdapter({"answer:RA-S-01": script})
    runner = make_runner(sessions, {"claude": claude}, tasks=[task])
    run_id = runner.start(RunConfig(model_keys=["claude"], call_cap=50))
    [row] = results(sessions, run_id)
    assert row.status == "scored" and row.score == 5
    assert get_run(sessions, run_id).calls_made == 4


def test_BE_AC06_four_transient_errors_give_timeout_defect(sessions: sessionmaker[Session]) -> None:
    claude = FixtureAdapter({"answer:RA-S-01": [{"error": "transient"}]})
    runner = make_runner(sessions, {"claude": claude}, tasks=[BY_ID["RA-S-01"]])
    run_id = runner.start(RunConfig(model_keys=["claude"]))
    [row] = results(sessions, run_id)
    assert row.status == "error"
    with sessions() as s:
        defects = list(s.scalars(select(Defect)))
    assert [d.type for d in defects] == ["TIMEOUT_ERROR"]
    assert get_run(sessions, run_id).calls_made == 4


def test_BE_AC07_quota_pauses_model_and_resume_does_not_repeat(
    sessions: sessionmaker[Session],
) -> None:
    tasks = [t for t in SUITE if not t.uses_judge][:7]
    ids = sorted(t.task_id for t in tasks)
    scripts = {f"answer:{t.task_id}": [ok(t.reference_response)] for t in tasks}
    scripts[f"answer:{ids[4]}"] = [
        {"error": "quota_exhausted"},
        ok(BY_ID[ids[4]].reference_response),
    ]
    claude = FixtureAdapter(scripts)
    gpt = FixtureAdapter({f"answer:{t.task_id}": [ok(t.reference_response)] for t in tasks})
    runner = make_runner(sessions, {"claude": claude, "gpt": gpt}, tasks=tasks)
    run_id = runner.start(RunConfig(model_keys=["claude", "gpt"]))

    rows = results(sessions, run_id)
    claude_status = [r.status for r in rows if r.model_key == "claude"]
    assert claude_status == ["scored"] * 4 + ["paused_quota"] * 3
    assert all(r.status == "scored" for r in rows if r.model_key == "gpt")  # other model continues
    with sessions() as s:
        assert list(s.scalars(select(Defect))) == []  # quota is not a model defect
    assert get_run(sessions, run_id).status == "paused_quota"

    runner.resume(run_id)
    assert all(r.status == "scored" for r in results(sessions, run_id))
    assert get_run(sessions, run_id).status == "completed"
    calls = Counter(claude.log)
    assert all(calls[f"answer:{i}"] == 1 for i in ids[:4])  # finished tasks never repeated


def test_BE_AC08_call_cap_stops_run(sessions: sessionmaker[Session]) -> None:
    tasks = [t for t in SUITE if not t.uses_judge]  # 10 tasks, one call each
    assert len(tasks) > 6
    claude = FixtureAdapter({f"answer:{t.task_id}": [ok(t.reference_response)] for t in tasks})
    runner = make_runner(sessions, {"claude": claude}, tasks=tasks)
    run_id = runner.start(RunConfig(model_keys=["claude"], call_cap=6))
    run = get_run(sessions, run_id)
    assert run.status == "stopped_cap"
    assert run.calls_made == 6
    assert len(claude.log) == 6  # no 7th call was started
    statuses = Counter(r.status for r in results(sessions, run_id))
    assert statuses["scored"] == 6 and statuses["pending"] == len(tasks) - 6


def test_one_active_run_at_a_time(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as s:
        s.add(Run(status="running", suite_version="v1", model_keys=[], categories=[], tiers=[],
                  call_cap=1, params={}, judge_rotation={}))  # fmt: skip
    runner = make_runner(sessions, {"claude": FixtureAdapter({})})
    with pytest.raises(RunConflict):
        runner.start(RunConfig(model_keys=["claude"]))


def test_BE_AC11_claude_answer_is_judged_by_gpt(sessions: sessionmaker[Session]) -> None:
    task = BY_ID["TD-S-01"]
    claude = FixtureAdapter({"answer:TD-S-01": [ok(task.reference_response)]})
    gpt = FixtureAdapter({"judge:claude:TD-S-01": [ok(judge_output_json(4, "good coverage"))]})
    runner = make_runner(sessions, {"claude": claude, "gpt": gpt}, tasks=[task])
    run_id = runner.start(RunConfig(model_keys=["claude"]))
    [row] = results(sessions, run_id)
    assert gpt.log == ["judge:claude:TD-S-01"] and claude.log == ["answer:TD-S-01"]
    assert row.score == 4 and row.score_source == "judge"
    with sessions() as s:
        [js] = list(s.scalars(select(JudgeScore)))
    assert js.judge_model_key == "gpt" and js.score == 4


def test_BE_AC13_failed_code_tests_cap_score_despite_judge_5(
    sessions: sessionmaker[Session],
) -> None:
    task = BY_ID["CG-C-01"]
    claude = FixtureAdapter({"answer:CG-C-01": [ok(task.reference_response)]})
    gpt = FixtureAdapter({"judge:claude:CG-C-01": [ok(judge_output_json(5))]})
    runner = make_runner(sessions, {"claude": claude, "gpt": gpt}, [task], PassingRunner(False))
    run_id = runner.start(RunConfig(model_keys=["claude"]))
    [row] = results(sessions, run_id)
    assert row.score is not None and row.score <= 2
    with sessions() as s:
        assert [d.type for d in s.scalars(select(Defect))] == ["INCORRECT_CODE"]


def test_invalid_judge_output_twice_flags_review(sessions: sessionmaker[Session]) -> None:
    task = BY_ID["TD-S-01"]
    claude = FixtureAdapter({"answer:TD-S-01": [ok(task.reference_response)]})
    gpt = FixtureAdapter({"judge:claude:TD-S-01": [ok("I think it's fine")]})
    runner = make_runner(sessions, {"claude": claude, "gpt": gpt}, tasks=[task])
    run_id = runner.start(RunConfig(model_keys=["claude"]))
    [row] = results(sessions, run_id)
    assert row.needs_review is True and row.score == 5  # deterministic score stands
    assert gpt.log == ["judge:claude:TD-S-01"] * 2  # one retry (BE-R13)


def test_no_judge_available_flags_review(sessions: sessionmaker[Session]) -> None:
    task = BY_ID["TD-S-01"]
    claude = FixtureAdapter({"answer:TD-S-01": [ok(task.reference_response)]})
    runner = make_runner(sessions, {"claude": claude}, tasks=[task])  # no GPT adapter
    run_id = runner.start(RunConfig(model_keys=["claude"]))
    [row] = results(sessions, run_id)
    assert row.needs_review is True


def test_BE_AC14_schema_failure_creates_format_break_with_evidence(
    sessions: sessionmaker[Session],
) -> None:
    claude = FixtureAdapter({"answer:SO-S-01": [ok('{"name": "Priya Raman"}')]})
    runner = make_runner(sessions, {"claude": claude}, tasks=[BY_ID["SO-S-01"]])
    runner.start(RunConfig(model_keys=["claude"]))
    with sessions() as s:
        defects = list(s.scalars(select(Defect).order_by(Defect.id)))
    fb = next(d for d in defects if d.type == "FORMAT_BREAK")
    assert fb.severity == "S2" and fb.source == "auto"
    assert "required" in (fb.evidence["checker_output"] or "")
    assert "Priya" in fb.evidence["response_excerpt"]
    assert "Extract the contact details" in fb.evidence["prompt_excerpt"]


def test_tokens_cost_and_unreported_fields(sessions: sessionmaker[Session]) -> None:
    task = BY_ID["RA-S-01"]
    claude = FixtureAdapter({"answer:RA-S-01": [ok(task.reference_response, overhead_tokens=300)]})
    runner = make_runner(sessions, {"claude": claude}, tasks=[task])
    run_id = runner.start(RunConfig(model_keys=["claude"]))
    [row] = results(sessions, run_id)
    assert (row.input_tokens, row.output_tokens, row.overhead_tokens) == (1000, 500, 300)
    assert row.reasoning_tokens is None  # BE-AC-17: not reported -> null, never 0
    assert row.api_equiv_cost_usd == pytest.approx(0.0105)
    assert get_run(sessions, run_id).api_equiv_cost_usd == pytest.approx(0.0105)


def test_truncated_response_adds_truncation_defect(sessions: sessionmaker[Session]) -> None:
    task = BY_ID["RA-S-01"]
    reply = {**ok(task.reference_response), "truncated": True}
    claude = FixtureAdapter({"answer:RA-S-01": [reply]})
    runner = make_runner(sessions, {"claude": claude}, tasks=[task])
    run_id = runner.start(RunConfig(model_keys=["claude"]))
    [row] = results(sessions, run_id)
    assert row.score == 3
    with sessions() as s:
        assert [d.type for d in s.scalars(select(Defect))] == ["TRUNCATION"]


def test_inconsistent_repeats_create_inconsistency_defect(sessions: sessionmaker[Session]) -> None:
    task = BY_ID["RA-S-01"]
    claude = FixtureAdapter({"answer:RA-S-01": [ok("ANSWER: 215"), ok("ANSWER: 225")]})
    runner = make_runner(sessions, {"claude": claude}, tasks=[task])
    run_id = runner.start(RunConfig(model_keys=["claude"], repeats=2))
    assert sorted(r.score or 0 for r in results(sessions, run_id)) == [2, 5]
    with sessions() as s:
        types = sorted(d.type for d in s.scalars(select(Defect)))
    assert types == ["INCONSISTENCY", "REASONING_ERROR"]


class FlakySandbox:
    """Unavailable for the first `down` calls, then passes (Docker restarted)."""

    def __init__(self, down: int) -> None:
        self.down = down

    def run_tests(self, solution: str, tests: str) -> RunResult:
        if self.down > 0:
            self.down -= 1
            raise SandboxUnavailable("Cannot connect to the Docker daemon")
        return RunResult(True, "1 passed")


def test_sandbox_down_stops_run_without_model_defects_and_resumes(
    sessions: sessionmaker[Session],
) -> None:
    tasks = [t for t in SUITE if t.category == "code_generation"]
    answers = {f"answer:{t.task_id}": [ok(t.reference_response)] * 2 for t in tasks}
    claude = FixtureAdapter(answers)
    gpt = FixtureAdapter(perfect_scripts(tasks, judged_model="claude"))
    runner = EvaluationRunner(
        sessions, [CLAUDE, GPT], tasks, {"claude": claude, "gpt": gpt}, FlakySandbox(down=1),
        sleep=lambda _: None,
    )  # fmt: skip
    run_id = runner.start(RunConfig(model_keys=["claude"], call_cap=100))

    assert get_run(sessions, run_id).status == "error"
    assert runner.last_error and "Docker daemon" in runner.last_error
    assert {r.status for r in results(sessions, run_id)} == {"pending"}
    with sessions() as s:
        assert list(s.scalars(select(Defect))) == []  # not the model's fault

    runner.resume(run_id)
    assert get_run(sessions, run_id).status == "completed"
    assert all(r.status == "scored" and r.score == 5 for r in results(sessions, run_id))
