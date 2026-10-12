"""GPT via the Codex CLI, signed in with ChatGPT Go (access mode codex_cli).

`codex exec --json` prints JSON Lines events. We read the agent's final message from
`item.completed` (item type `agent_message`) and token usage from `turn.completed`.
Codex runs in a read-only sandbox in an empty directory, ignores the user's config and
rules files, and saves no session; the prompt goes in on stdin (`-`).
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


def _int(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) else None


class CodexAdapter:
    def __init__(
        self, model_id: str, exec_: Exec = run_process, timeout_s: int = CALL_TIMEOUT_S
    ) -> None:
        self.model_id = model_id
        self.exec = exec_
        self.timeout_s = timeout_s

    def argv(self, workdir: str) -> Sequence[str]:
        return [
            "codex", "exec", "--json",
            "--model", self.model_id,
            "--sandbox", "read-only",
            "--cd", workdir,
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "-",
        ]  # fmt: skip

    def complete(self, prompt: str, *, request_id: str) -> AdapterResponse:
        result = run_in_empty_dir(self.exec, self.argv, prompt, self.timeout_s)
        events: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)

        errors = [
            str((e.get("error") or {}).get("message") or e.get("message") or e)
            for e in events
            if e.get("type") in ("turn.failed", "error")
        ]
        if errors:
            message = errors[-1]
            raise AdapterError(classify_failure(message), message)
        if not events:
            message = (result.stderr or result.stdout).strip()[-500:]
            if result.returncode != 0 and message:
                raise AdapterError(classify_failure(message), message)
            raise AdapterError(ErrorKind.INVALID_RESPONSE, "Codex printed no JSON events")

        messages = [
            str(item.get("text", ""))
            for e in events
            if e.get("type") == "item.completed"
            and isinstance(item := e.get("item"), dict)
            and item.get("type") == "agent_message"
        ]
        if not messages:
            raise AdapterError(ErrorKind.INVALID_RESPONSE, "Codex returned no agent message")

        usage: dict[str, Any] = {}
        for e in events:
            if e.get("type") == "turn.completed" and isinstance(e.get("usage"), dict):
                usage = e["usage"]
        total_input = _int(usage.get("input_tokens"))
        output = _int(usage.get("output_tokens"))
        reasoning = _int(usage.get("reasoning_output_tokens")) or 0
        if output is not None:
            # OpenAI counts reasoning inside output_tokens; split them so the cost formula
            # (BE-R20, output + reasoning) never counts reasoning twice.
            output -= min(reasoning, output)
        return AdapterResponse(
            text=messages[-1],
            usage=Usage(
                input_tokens=total_input,
                output_tokens=output,
                reasoning_tokens=reasoning or None,
                cached_tokens=_int(usage.get("cached_input_tokens")),
                overhead_tokens=overhead(total_input, prompt),
                estimated={"overhead_tokens": True},
            ),
            latency_ms=result.latency_ms,
        )
