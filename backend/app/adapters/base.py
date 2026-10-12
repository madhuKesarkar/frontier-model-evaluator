"""Adapter interface shared by all access modes (backend-spec §3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ErrorKind(StrEnum):
    TRANSIENT = "transient"  # retryable (rate limit, network blip)
    QUOTA_EXHAUSTED = "quota_exhausted"  # plan limit reached: pause this model (BE-R7)
    NOT_READY = "not_ready"  # CLI missing / not signed in
    TIMEOUT = "timeout"  # retryable
    INVALID_RESPONSE = "invalid_response"  # unparseable CLI output: retryable


RETRYABLE = {ErrorKind.TRANSIENT, ErrorKind.TIMEOUT, ErrorKind.INVALID_RESPONSE}


class AdapterError(Exception):
    def __init__(self, kind: ErrorKind, message: str = "") -> None:
        super().__init__(message or kind.value)
        self.kind = kind


@dataclass(frozen=True)
class Usage:
    """Token counts. None = not reported and not estimated (never a fake 0, BE-R21)."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    overhead_tokens: int | None = None
    estimated: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterResponse:
    text: str
    usage: Usage
    latency_ms: int
    truncated: bool = False  # hit the max-token limit


class Adapter(Protocol):
    def complete(self, prompt: str, *, request_id: str) -> AdapterResponse:
        """Send one prompt. `request_id` names the request (e.g. 'answer:CG-S-01' or
        'judge:gpt-go:CG-S-01'); live adapters ignore it, fixture adapters look it up."""
        ...
