"""Scoring rules (backend-spec §5, D-16)."""

from __future__ import annotations

from collections.abc import Iterable

SEVERITY_CAP = {"S1": 1, "S2": 2, "S3": 3, "S4": 4}


def deterministic_score(failed_severities: Iterable[str]) -> int:
    """BE-R11: 5 when every deterministic check passes; otherwise capped by the worst
    failed check's severity (S1->1, S2->2, S3->3, S4->4)."""
    caps = [SEVERITY_CAP[s] for s in failed_severities]
    return min(caps) if caps else 5


def final_score(det_score: int, judge_score: int | None, uses_judge: bool) -> tuple[int, bool]:
    """Returns (score, needs_review).

    D-16: with a judge, score = min(judge score, deterministic score), so a fluent answer
    cannot outscore a failed hard check (this also enforces BE-R15: failed unit tests
    -> INCORRECT_CODE S2 -> score <= 2). If a judge was required but produced no valid
    score, the deterministic score is used and the result is flagged for review.
    """
    if not uses_judge:
        return det_score, False
    if judge_score is None:
        return det_score, True
    return min(det_score, judge_score), False
