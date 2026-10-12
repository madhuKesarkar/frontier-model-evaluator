"""Versioned task suite (backend-spec §2 Task, BE-AC-04)."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Category(StrEnum):
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    STRUCTURED_OUTPUT = "structured_output"
    TEST_DESIGN = "test_design"
    LONG_CONTEXT = "long_context"
    TOOL_USE = "tool_use"


class Tier(StrEnum):
    SIMPLE = "simple"
    MID = "mid"
    COMPLEX = "complex"


DefectType = Literal[
    "HALLUCINATION",
    "INSTRUCTION_VIOLATION",
    "FORMAT_BREAK",
    "INCORRECT_CODE",
    "REASONING_ERROR",
    "TOOL_CALL_ERROR",
    "OVER_REFUSAL",
    "UNSAFE_OUTPUT",
    "TRUNCATION",
    "TIMEOUT_ERROR",
    "INCONSISTENCY",
]
Severity = Literal["S1", "S2", "S3", "S4"]
CheckerType = Literal["unit_tests", "json_schema", "exact_match", "regex", "llm_judge"]


class OnFail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: DefectType
    severity: Severity


class Checker(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: CheckerType
    on_fail: OnFail
    tests: str | None = None  # unit_tests
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")  # json_schema
    extract: dict[str, Any] | None = None  # exact_match
    expected: str | None = None  # exact_match
    numeric: bool = False  # exact_match
    pattern: str | None = None  # regex


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str
    version: int = Field(ge=1)
    category: Category
    tier: Tier
    title: str
    prompt: str
    checkers: list[Checker] = Field(min_length=1)
    rubric: str | None = None
    reference_response: str

    @property
    def uses_judge(self) -> bool:
        return any(c.type == "llm_judge" for c in self.checkers)

    @property
    def content_hash(self) -> str:
        """SHA-256 over everything that defines the task for the model and the scorer."""
        payload = {
            "prompt": self.prompt,
            "checkers": [c.model_dump(by_alias=True, exclude_none=True) for c in self.checkers],
            "rubric": self.rubric,
            "version": self.version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class SuiteError(ValueError):
    pass


def load_suite(directory: Path) -> list[Task]:
    tasks = []
    for path in sorted(directory.glob("*.yaml")):
        task = Task.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if path.stem != task.task_id:
            raise SuiteError(f"{path.name}: task_id {task.task_id} does not match file name")
        tasks.append(task)
    return tasks


def validate_suite(tasks: list[Task], min_per_cell: int = 1) -> list[str]:
    """BE-AC-04: every category x tier cell has >= min_per_cell tasks; ids unique; judge tasks
    have a rubric. Returns a list of problems (empty = valid)."""
    problems: list[str] = []
    ids = [t.task_id for t in tasks]
    for dup in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"duplicate task_id {dup}")
    for category in Category:
        for tier in Tier:
            count = sum(1 for t in tasks if t.category == category and t.tier == tier)
            if count < min_per_cell:
                problems.append(f"{category}/{tier}: {count} task(s), need >= {min_per_cell}")
    for task in tasks:
        if task.uses_judge and not task.rubric:
            problems.append(f"{task.task_id}: llm_judge checker but no rubric")
    return problems
