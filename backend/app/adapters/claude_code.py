"""Claude via Claude Code headless, signed in with Claude Pro (access mode claude_code_cli).

`claude -p --output-format json` prints one JSON object. Tools are disabled, sessions are
not saved, MCP servers are not loaded, and a minimal system prompt replaces the default
one. `--bare` is deliberately NOT used: it ignores the Pro sign-in and only accepts an API
key, which would break the $0 rule.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.adapters.base import AdapterError, AdapterResponse, ErrorKind, Usage
from app.adapters.cli import (
    CALL_TIMEOUT_S,
    Exec,
    classify_failure,
    overhead,
    run_in_empty_dir,
    run_process,
)

SYSTEM_PROMPT = (
    "You are being evaluated. Answer the user's request directly and completely, "
    "following its output format exactly. Do not ask questions and do not use tools."
)


def _int(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) else None


class ClaudeCodeAdapter:
    def __init__(
        self, model_id: str, exec_: Exec = run_process, timeout_s: int = CALL_TIMEOUT_S
    ) -> None:
        self.model_id = model_id
        self.exec = exec_
        self.timeout_s = timeout_s

    def argv(self, _workdir: str) -> Sequence[str]:
        return [
            "claude", "-p",
            "--output-format", "json",
            "--model", self.model_id,
            "--tools", "",
            "--system-prompt", SYSTEM_PROMPT,
            "--no-session-persistence",
            "--strict-mcp-config",
        ]  # fmt: skip

    def complete(self, prompt: str, *, request_id: str) -> AdapterResponse:
        result = run_in_empty_dir(self.exec, self.argv, prompt, self.timeout_s)
        try:
            data = json.loads(result.stdout)
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except ValueError:
            message = (result.stderr or result.stdout).strip()[-500:]
            if result.returncode != 0 and message:
                raise AdapterError(classify_failure(message), message) from None
            raise AdapterError(
                ErrorKind.INVALID_RESPONSE, "Claude Code output is not JSON"
            ) from None

        if data.get("is_error"):
            message = str(data.get("result") or data.get("terminal_reason") or "unknown error")
            status = data.get("api_error_status")
            kind = classify_failure(message)
            if kind == ErrorKind.TRANSIENT and status in (401, 403):
                kind = ErrorKind.NOT_READY
            raise AdapterError(kind, message)

        used = list((data.get("modelUsage") or {}).keys())
        if used and self.model_id not in used:
            # A silent model fallback would make the results describe the wrong model.
            raise AdapterError(
                ErrorKind.NOT_READY,
                f"Claude Code answered with {', '.join(used)}, expected {self.model_id}",
            )

        usage = data.get("usage") or {}
        fresh = _int(usage.get("input_tokens"))
        cache_write = _int(usage.get("cache_creation_input_tokens")) or 0
        cache_read = _int(usage.get("cache_read_input_tokens"))
        total_input = None if fresh is None else fresh + cache_write + (cache_read or 0)
        # Claude counts thinking inside output_tokens; the cost formula (BE-R20) adds
        # reasoning on top of output, so split them to avoid counting thinking twice.
        output = _int(usage.get("output_tokens"))
        reasoning = _int((usage.get("output_tokens_details") or {}).get("thinking_tokens")) or 0
        if output is not None:
            output -= min(reasoning, output)
        return AdapterResponse(
            text=str(data.get("result") or ""),
            usage=Usage(
                input_tokens=total_input,
                output_tokens=output,
                reasoning_tokens=reasoning or None,
                cached_tokens=cache_read,
                overhead_tokens=overhead(total_input, prompt),
                estimated={"overhead_tokens": True},
            ),
            latency_ms=_int(data.get("duration_ms")) or result.latency_ms,
            truncated=data.get("stop_reason") == "max_tokens",
        )
