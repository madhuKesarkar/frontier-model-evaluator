"""The demo suite (suite/v1) is valid, every reference answer passes its own checks, and
plausible wrong answers fail (backend-spec §2, BE-AC-04, BE-AC-14)."""

from __future__ import annotations

import pytest

from app.checkers import run_checker
from app.sandbox import DockerSandbox
from app.settings import REPO_ROOT
from app.suite import Task, load_suite, validate_suite

SUITE = load_suite(REPO_ROOT / "suite/v1")
BY_ID = {t.task_id: t for t in SUITE}
NON_CODE = [t for t in SUITE if not any(c.type == "unit_tests" for c in t.checkers)]
CODE = [t for t in SUITE if any(c.type == "unit_tests" for c in t.checkers)]


def failed_checks(task: Task, response: str, runner: DockerSandbox | None = None) -> list[str]:
    outcomes = [run_checker(c, response, runner) for c in task.checkers if c.type != "llm_judge"]
    return [f"{o.checker}: {o.output}" for o in outcomes if not o.passed]


def test_BE_AC04_suite_covers_every_cell_with_checkers_and_hashes() -> None:
    assert len(SUITE) == 18
    assert validate_suite(SUITE, min_per_cell=1) == []
    for task in SUITE:
        assert task.checkers, task.task_id
        assert len(task.content_hash) == 64
    assert len({t.content_hash for t in SUITE}) == 18


def test_hash_changes_when_prompt_changes() -> None:
    task = BY_ID["RA-S-01"]
    edited = task.model_copy(update={"prompt": task.prompt + " "})
    assert edited.content_hash != task.content_hash


def test_validator_reports_empty_cell() -> None:
    problems = validate_suite([t for t in SUITE if t.task_id != "TU-C-01"])
    assert problems == ["tool_use/complex: 0 task(s), need >= 1"]


@pytest.mark.parametrize("task", NON_CODE, ids=lambda t: t.task_id)
def test_reference_response_passes_deterministic_checks(task: Task) -> None:
    assert failed_checks(task, task.reference_response) == []


@pytest.mark.docker
@pytest.mark.parametrize("task", CODE, ids=lambda t: t.task_id)
def test_reference_code_passes_unit_tests_in_sandbox(task: Task, sandbox: DockerSandbox) -> None:
    assert failed_checks(task, task.reference_response, sandbox) == []


@pytest.mark.parametrize("task", NON_CODE, ids=lambda t: t.task_id)
def test_refusal_fails_at_least_one_check(task: Task) -> None:
    assert failed_checks(task, "Sorry, I can't help with that.")


# Near-miss answers a careless model might give: each must be caught.
NEAR_MISSES = {
    "RA-M-01": "Subtotal 7320, GST 18%.\nANSWER: 8637.60",  # forgot the discount
    "RA-C-01": "Reasoning...\nANSWER: Ben, Wednesday",
    "SO-M-01": '{"title": "Coupon lost", "severity": "S2", "component": "checkout",'
    ' "steps": ["a", "b"], "expected": "x", "actual": "y"}',  # over-rated severity
    "LC-C-01": '{"q1": "4.00", "q2": "60", "q3": "4", "q4": "NOT_IN_DOCUMENT"}',  # superseded rate
    "LC-S-01": '{"q1": "15", "q2": "The lab manager"}',  # hallucinated approver
    "TU-M-01": '{"calls": [{"tool": "hold_seat", "arguments": {"flight_id": "6E-219"}},'
    ' {"tool": "send_email", "arguments": {"to": "madhu@example.com"}}]}',  # ignored "before noon"
    "TU-C-01": '{"calls": [{"tool": "create_return", "arguments": {"order_id": "ORD-7781",'
    ' "item_ids": ["I1", "I3"], "reason": "changed_mind"}}, {"tool": "issue_refund",'
    ' "arguments": {"order_id": "ORD-7781", "amount_inr": 4298}}],'
    ' "message_to_customer": "Refunded!"}',  # refunded before receipt (P2)
    "SO-C-01": BY_ID["SO-C-01"].reference_response.replace('"breaking"', '"fix"'),
}


@pytest.mark.parametrize("task_id", sorted(NEAR_MISSES))
def test_near_miss_answer_is_caught(task_id: str) -> None:
    assert failed_checks(BY_ID[task_id], NEAR_MISSES[task_id])


def test_BE_AC14_schema_failure_reports_validator_error_as_evidence() -> None:
    task = BY_ID["SO-S-01"]
    schema_check = next(c for c in task.checkers if c.type == "json_schema")
    outcome = run_checker(schema_check, '{"name": "Priya", "email": "p@example.com"}')
    assert not outcome.passed
    assert "phone" in outcome.output and "required" in outcome.output
    assert schema_check.on_fail.type == "FORMAT_BREAK"
