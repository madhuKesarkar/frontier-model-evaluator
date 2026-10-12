"""Judge calibration (backend-spec §7; SM-3 / BE-AC-21, SM-4 / BE-AC-22).

Each judge model grades the 6 golden answers (owner-labelled) and the 6 seeded-defect answers
with exactly the prompt it uses in a real run. Both providers act as a judge in a run (each
grades the other's answers), so each judge is calibrated separately and must pass on its own.

- Agreement (SM-3): share of golden items scored within +/-1 of the owner's label. Pass >= 80%.
- Catch rate (SM-4): share of seeded items scored 2 or lower. Pass >= 80%.
An unparseable judge reply gets one retry (BE-R13); if it is still invalid the item counts as
a miss, never as a pass.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.adapters.base import Adapter, AdapterError
from app.judge import build_judge_prompt, parse_judge_output
from app.suite import Task

PASS_RATE = 0.8


class GoldenItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    task_id: str
    human_score: int = Field(ge=1, le=5)
    why: str
    response: str


class SeededItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    task_id: str
    flaw: str
    response: str


@dataclass
class ItemResult:
    id: str
    task_id: str
    judge_score: int | None
    expected: str
    ok: bool
    rationale: str = ""


@dataclass
class JudgeReport:
    judge: str
    golden: list[ItemResult] = field(default_factory=list)
    seeded: list[ItemResult] = field(default_factory=list)

    @property
    def agreement(self) -> float:
        return rate(self.golden)

    @property
    def catch_rate(self) -> float:
        return rate(self.seeded)

    @property
    def passed(self) -> bool:
        return self.agreement >= PASS_RATE and self.catch_rate >= PASS_RATE

    def as_dict(self) -> dict[str, Any]:
        return {
            "judge": self.judge,
            "agreement": round(self.agreement, 3),
            "catch_rate": round(self.catch_rate, 3),
            "passed": self.passed,
            "golden": [asdict(r) for r in self.golden],
            "seeded": [asdict(r) for r in self.seeded],
        }


def rate(items: list[ItemResult]) -> float:
    return sum(r.ok for r in items) / len(items) if items else 0.0


def agrees(judge_score: int | None, human_score: int) -> bool:
    return judge_score is not None and abs(judge_score - human_score) <= 1


def caught(judge_score: int | None) -> bool:
    return judge_score is not None and judge_score <= 2


def load_sets(directory: Path) -> tuple[list[GoldenItem], list[SeededItem], str]:
    golden_doc = yaml.safe_load((directory / "golden.yaml").read_text(encoding="utf-8"))
    seeded_doc = yaml.safe_load((directory / "seeded.yaml").read_text(encoding="utf-8"))
    golden = [GoldenItem.model_validate(i) for i in golden_doc["items"]]
    seeded = [SeededItem.model_validate(i) for i in seeded_doc["items"]]
    return golden, seeded, str(golden_doc.get("labelled_by", "unknown"))


def _grade(
    adapter: Adapter, judge: str, task: Task, item_id: str, response: str
) -> tuple[int | None, str]:
    prompt = build_judge_prompt(task, response)
    for _attempt in range(2):  # BE-R13: one retry on invalid output
        try:
            reply = adapter.complete(prompt, request_id=f"judge:{judge}:calib:{item_id}")
        except AdapterError as exc:
            return None, f"judge call failed: {exc}"
        try:
            verdict = parse_judge_output(reply.text)
        except ValueError:
            continue
        return verdict.score, verdict.rationale
    return None, "judge output invalid twice"


def calibrate(
    judges: dict[str, Adapter],
    tasks: dict[str, Task],
    golden: list[GoldenItem],
    seeded: list[SeededItem],
) -> list[JudgeReport]:
    reports = []
    for judge, adapter in judges.items():
        report = JudgeReport(judge)
        for g in golden:
            score, why = _grade(adapter, judge, tasks[g.task_id], g.id, g.response)
            report.golden.append(
                ItemResult(
                    g.id,
                    g.task_id,
                    score,
                    f"{g.human_score} +/-1",
                    agrees(score, g.human_score),
                    why,
                )
            )
        for sd in seeded:
            score, why = _grade(adapter, judge, tasks[sd.task_id], sd.id, sd.response)
            report.seeded.append(ItemResult(sd.id, sd.task_id, score, "<= 2", caught(score), why))
        reports.append(report)
    return reports
