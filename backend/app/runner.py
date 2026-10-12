"""Evaluation runner: the fixed workflow of backend-spec §4.

For each Result: call the model's adapter -> record response, tokens, cost -> run the
deterministic checkers -> ask the cross-provider judge if the task needs one -> score
(BE-R11, D-16) -> record defects. The model never chooses the next step.

Rules enforced here: BE-R5 call cap, BE-R6 retries, BE-R7 quota pause/resume,
BE-R8 one active run, BE-R9 one call at a time, BE-R18/19 defects.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.base import RETRYABLE, Adapter, AdapterError, AdapterResponse, ErrorKind
from app.checkers import CodeRunner, run_checker
from app.cost import api_equivalent_cost
from app.db import Defect, JudgeScore, Result, Run, utcnow
from app.judge import (
    JudgeVerdict,
    NoJudgeAvailable,
    build_judge_prompt,
    parse_judge_output,
    pick_judge,
)
from app.registry import ModelEntry
from app.scoring import deterministic_score, final_score
from app.suite import Task

MAX_RETRIES = 3  # BE-R6: up to 3 retries after the first attempt
EXCERPT = 600
ACTIVE = "running"
UNFINISHED = {"pending", "paused_quota"}


class RunConflict(RuntimeError):
    """BE-R8: another run is already active."""


class CapReached(Exception):
    """BE-R5: the call cap is used up."""


class QuotaExhausted(Exception):
    """BE-R7: the model's plan quota is used up."""


@dataclass
class RunConfig:
    model_keys: list[str]
    categories: list[str] | None = None
    tiers: list[str] | None = None
    repeats: int = 1
    call_cap: int = 50
    params: dict[str, Any] = field(default_factory=dict)


def _require[T](obj: T | None, what: str) -> T:
    if obj is None:
        raise LookupError(f"{what} not found")
    return obj


def _excerpt(text: str | None) -> str:
    text = text or ""
    return text if len(text) <= EXCERPT else text[:EXCERPT] + " …"


class EvaluationRunner:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        registry: list[ModelEntry],
        tasks: list[Task],
        adapters: dict[str, Adapter],
        code_runner: CodeRunner | None,
        suite_version: str = "v1",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.sessions = sessions
        self.models = {m.key: m for m in registry}
        self.tasks = {t.task_id: t for t in tasks}
        self.adapters = adapters
        self.code_runner = code_runner
        self.suite_version = suite_version
        self.sleep = sleep
        self._calls_made = 0
        self._call_cap = 0

    # ------------------------------------------------------------------ public API
    def start(self, config: RunConfig) -> int:
        with self.sessions.begin() as s:
            self._refuse_if_active(s)
            unknown = [k for k in config.model_keys if k not in self.models]
            disabled = [
                k for k in config.model_keys if k in self.models and not self.models[k].enabled
            ]
            if unknown or disabled or not config.model_keys:
                raise ValueError(f"invalid models: unknown={unknown} disabled={disabled}")
            if config.call_cap < 1 or not 1 <= config.repeats <= 3:
                raise ValueError("call_cap must be >= 1 and repeats 1-3")
            tasks = [
                t
                for t in self.tasks.values()
                if (not config.categories or t.category in config.categories)
                and (not config.tiers or t.tier in config.tiers)
            ]
            run = Run(
                status="queued",
                suite_version=self.suite_version,
                model_keys=config.model_keys,
                categories=config.categories or [],
                tiers=config.tiers or [],
                repeats=config.repeats,
                call_cap=config.call_cap,
                params=config.params,
                judge_rotation={},
            )
            s.add(run)
            for key in config.model_keys:
                model = self.models[key]
                for task in sorted(tasks, key=lambda t: t.task_id):
                    for attempt in range(1, config.repeats + 1):
                        run.results.append(
                            Result(
                                model_key=key,
                                provider=model.provider.value,
                                task_id=task.task_id,
                                task_hash=task.content_hash,
                                category=task.category.value,
                                tier=task.tier.value,
                                attempt=attempt,
                                status="pending",
                            )
                        )
            s.flush()
            run_id = run.id
        self._execute(run_id)
        return run_id

    def resume(self, run_id: int) -> None:
        """BE-R7 / BE-R8b: continue only unfinished Results; finished ones are never repeated."""
        with self.sessions.begin() as s:
            run = s.get(Run, run_id)
            if run is None:
                raise ValueError(f"run {run_id} not found")
            if run.status not in {"paused_quota", "stopped_cap", "error"}:
                raise ValueError(f"run {run_id} is {run.status}; only paused/stopped runs resume")
            self._refuse_if_active(s)
            for r in run.results:
                if r.status == "paused_quota":
                    r.status = "pending"
        self._execute(run_id)

    # ------------------------------------------------------------------ internals
    def _refuse_if_active(self, s: Session) -> None:
        active = s.scalars(select(Run).where(Run.status == ACTIVE)).first()
        if active is not None:
            raise RunConflict(f"run {active.id} is already running")

    def _execute(self, run_id: int) -> None:
        with self.sessions.begin() as s:
            run = _require(s.get(Run, run_id), "Run")
            run.status = ACTIVE
            self._calls_made, self._call_cap = run.calls_made, run.call_cap
            pending = [
                r.id for r in sorted(run.results, key=lambda r: r.id) if r.status == "pending"
            ]
        paused_models: set[str] = set()
        status = "completed"
        for result_id in pending:
            with self.sessions.begin() as s:
                result = _require(s.get(Result, result_id), "Result")
                if result.model_key in paused_models:
                    result.status = "paused_quota"
                    continue
                try:
                    with s.begin_nested():  # partial work rolls back; call counts survive
                        self._evaluate(s, result)
                except QuotaExhausted:
                    paused_models.add(result.model_key)
                    result.status = "paused_quota"  # no defect: not the model's fault
                except CapReached:
                    status = "stopped_cap"  # this Result stays pending for a resume
                run = _require(s.get(Run, result.run_id), "Run")
                run.calls_made = self._calls_made  # outside the savepoint: real calls count
            if status == "stopped_cap":
                break
        with self.sessions.begin() as s:
            run = _require(s.get(Run, run_id), "Run")
            if status != "stopped_cap" and any(r.status == "paused_quota" for r in run.results):
                status = "paused_quota"
            run.status = status
            run.api_equiv_cost_usd = round(sum(r.api_equiv_cost_usd or 0.0 for r in run.results), 6)
            self._consistency_defects(s, run)
            if status == "completed":
                run.finished_at = utcnow()

    def _call(self, model_key: str, prompt: str, request_id: str) -> AdapterResponse:
        """One logical request with BE-R6 retries; every attempt counts toward BE-R5."""
        adapter = self.adapters.get(model_key)
        if adapter is None:
            raise AdapterError(ErrorKind.NOT_READY, f"no adapter for {model_key}")
        last: AdapterError | None = None
        for attempt in range(MAX_RETRIES + 1):
            if self._calls_made >= self._call_cap:
                raise CapReached
            self._calls_made += 1
            try:
                return adapter.complete(prompt, request_id=request_id)
            except AdapterError as exc:
                if exc.kind == ErrorKind.QUOTA_EXHAUSTED:
                    raise QuotaExhausted from exc
                if exc.kind not in RETRYABLE:
                    raise
                last = exc
                if attempt < MAX_RETRIES:
                    self.sleep(2**attempt)
        raise last if last else AdapterError(ErrorKind.TRANSIENT)

    def _evaluate(self, s: Session, result: Result) -> None:
        task = self.tasks[result.task_id]
        model = self.models[result.model_key]
        try:
            reply = self._call(model.key, task.prompt, f"answer:{task.task_id}")
        except AdapterError as exc:
            result.status = "skipped" if exc.kind == ErrorKind.NOT_READY else "error"
            if exc.kind != ErrorKind.NOT_READY:
                self._add_defect(
                    s, result, task, "TIMEOUT_ERROR", "S2",
                    f"No usable response after {MAX_RETRIES} retries ({exc.kind})",
                    expected="A response", actual=str(exc), source="auto",
                )  # fmt: skip
            return

        u = reply.usage
        result.response_text = reply.text
        result.input_tokens, result.output_tokens = u.input_tokens, u.output_tokens
        result.reasoning_tokens, result.cached_tokens = u.reasoning_tokens, u.cached_tokens
        result.overhead_tokens, result.tokens_estimated = u.overhead_tokens, dict(u.estimated)
        result.latency_ms = reply.latency_ms
        result.api_equiv_cost_usd = api_equivalent_cost(
            u.input_tokens, u.output_tokens, model.price_input_per_mtok,
            model.price_output_per_mtok, u.reasoning_tokens,
        )  # fmt: skip

        # Deterministic checks (BE-R18)
        failed: list[str] = []
        checks = []
        for checker in task.checkers:
            if checker.type == "llm_judge":
                continue
            outcome = run_checker(checker, reply.text, self.code_runner)
            checks.append(
                {"checker": outcome.checker, "passed": outcome.passed, "output": outcome.output}
            )
            if not outcome.passed:
                failed.append(checker.on_fail.severity)
                self._add_defect(
                    s, result, task, checker.on_fail.type, checker.on_fail.severity,
                    f"{checker.type} check failed", expected=checker.expected,
                    actual=outcome.output, source="auto", checker_output=outcome.output,
                )  # fmt: skip
        if reply.truncated:
            failed.append("S3")
            self._add_defect(
                s, result, task, "TRUNCATION", "S3", "Response cut off at the token limit",
                expected="A complete response", actual="Truncated", source="auto",
            )  # fmt: skip
        result.checks = checks

        # Judge (BE-R12, BE-R13)
        judge_score: int | None = None
        if task.uses_judge:
            judge_score = self._judge(s, result, task, model, reply.text)

        det = deterministic_score(failed)
        result.score, result.needs_review = final_score(det, judge_score, task.uses_judge)
        result.score_source = "judge" if judge_score is not None else "auto"
        result.status = "scored"

    def _judge(
        self, s: Session, result: Result, task: Task, model: ModelEntry, response: str
    ) -> int | None:
        ready = [m for m in self.models.values() if m.enabled and m.key in self.adapters]
        try:
            judge = pick_judge(model.provider, ready)
        except NoJudgeAvailable:
            return None
        prompt = build_judge_prompt(task, response)
        verdict: JudgeVerdict | None = None
        raw = None
        for _ in range(2):  # BE-R13: one retry on invalid output
            try:
                reply = self._call(judge.key, prompt, f"judge:{model.key}:{task.task_id}")
            except (AdapterError, QuotaExhausted):
                break  # judge unavailable -> needs_review via final_score
            raw = reply.text
            try:
                verdict = parse_judge_output(reply.text)
                break
            except ValueError:
                continue
        s.add(
            JudgeScore(
                result_id=result.id, judge_model_key=judge.key,
                score=verdict.score if verdict else None,
                rationale=verdict.rationale if verdict else None, raw_output=raw,
            )
        )  # fmt: skip
        if verdict is None:
            return None
        judge_checker = next(c for c in task.checkers if c.type == "llm_judge")
        for d in verdict.defects:
            self._add_defect(
                s, result, task, d["type"], d["severity"], d["title"],
                expected=None, actual=verdict.rationale, source="judge",
            )  # fmt: skip
        if verdict.score <= 2 and not verdict.defects:
            self._add_defect(
                s, result, task, judge_checker.on_fail.type, judge_checker.on_fail.severity,
                f"Judge scored {verdict.score}/5", expected=None, actual=verdict.rationale,
                source="judge",
            )  # fmt: skip
        return verdict.score

    def _add_defect(
        self,
        s: Session,
        result: Result,
        task: Task,
        dtype: str,
        severity: str,
        title: str,
        *,
        expected: str | None,
        actual: str | None,
        source: str,
        checker_output: str | None = None,
    ) -> None:
        s.add(
            Defect(
                result_id=result.id, model_key=result.model_key, task_id=task.task_id,
                category=task.category.value, tier=task.tier.value, type=dtype,
                severity=severity, title=title[:200], expected=expected, actual=_excerpt(actual),
                evidence={
                    "prompt_excerpt": _excerpt(task.prompt),
                    "response_excerpt": _excerpt(result.response_text),
                    "checker_output": _excerpt(checker_output) if checker_output else None,
                },
                source=source, status="open",
            )
        )  # fmt: skip

    def _consistency_defects(self, s: Session, run: Run) -> None:
        """BE §6: repeats > 1 and scores across repeats differ by >= 2 -> INCONSISTENCY."""
        if run.repeats < 2:
            return
        groups: dict[tuple[str, str], list[Result]] = {}
        for r in run.results:
            if r.score is not None:
                groups.setdefault((r.model_key, r.task_id), []).append(r)
        for (_, task_id), rows in groups.items():
            scores = [r.score for r in rows if r.score is not None]
            if len(scores) > 1 and max(scores) - min(scores) >= 2:
                already = any(d.type == "INCONSISTENCY" for r in rows for d in r.defects)
                if not already:
                    last = max(rows, key=lambda r: r.attempt)
                    self._add_defect(
                        s, last, self.tasks[task_id], "INCONSISTENCY", "S3",
                        f"Scores across repeats ranged {min(scores)}-{max(scores)}",
                        expected="Consistent results", actual=str(scores), source="auto",
                    )  # fmt: skip
