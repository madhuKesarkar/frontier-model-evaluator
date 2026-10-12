"""Live CLI adapters, tested on recorded CLI output only: no model is ever called (BE-R4)."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.adapters.base import AdapterError, ErrorKind
from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.cli import CliResult, estimate_tokens
from app.adapters.codex import CodexAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "cli"
PROMPT = "Say hello"


class FakeExec:
    """Records each call and answers with canned output."""

    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr
        self.calls: list[tuple[list[str], str, str]] = []

    def __call__(self, argv: Sequence[str], stdin: str, cwd: str, timeout_s: int) -> CliResult:
        self.calls.append((list(argv), stdin, cwd))
        assert os.listdir(cwd) == [], "the CLI must run in an empty directory"
        return CliResult(self.returncode, self.stdout, self.stderr, 1234)


def claude_json(**overrides: object) -> str:
    data = json.loads((FIXTURES / "claude_ok.json").read_text())
    data.update(overrides)
    return json.dumps(data)


# ---------------------------------------------------------------- claude_code_cli
def test_claude_parses_real_output_and_splits_overhead() -> None:
    fake = FakeExec(claude_json())
    reply = ClaudeCodeAdapter("claude-sonnet-5", fake).complete(PROMPT, request_id="answer:X")
    assert reply.text.startswith("Hello!")
    u = reply.usage
    assert u.input_tokens == 2 + 14056 + 17157  # fresh + cache write + cache read
    assert u.cached_tokens == 17157
    assert u.output_tokens == 44
    assert u.reasoning_tokens is None  # 0 thinking tokens: not reported as a fake 0
    assert u.overhead_tokens == u.input_tokens - estimate_tokens(PROMPT)
    assert u.estimated == {"overhead_tokens": True}
    assert reply.latency_ms == 4275
    assert not reply.truncated


def test_claude_command_is_safe_and_subscription_billed() -> None:
    fake = FakeExec(claude_json())
    ClaudeCodeAdapter("claude-sonnet-5", fake).complete(PROMPT, request_id="answer:X")
    argv, stdin, _ = fake.calls[0]
    assert argv[:2] == ["claude", "-p"]
    assert "--bare" not in argv  # --bare ignores the Pro sign-in and needs an API key
    assert argv[argv.index("--tools") + 1] == ""  # all tools disabled
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5"
    assert "--no-session-persistence" in argv and "--strict-mcp-config" in argv
    assert stdin == PROMPT and PROMPT not in argv  # prompt on stdin, not the command line


def test_claude_strips_paid_keys_from_the_child_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_run(argv: list[str], *, env: dict[str, str], **_: object) -> object:
        seen.update(env)

        class P:
            returncode, stdout, stderr = 0, claude_json(), ""

        return P()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x" * 8)
    monkeypatch.setattr("app.adapters.cli.subprocess.run", fake_run)
    ClaudeCodeAdapter("claude-sonnet-5").complete(PROMPT, request_id="answer:X")
    assert "ANTHROPIC_API_KEY" not in seen


def test_claude_expired_sign_in_is_not_ready() -> None:
    fake = FakeExec((FIXTURES / "claude_auth_expired.json").read_text())
    with pytest.raises(AdapterError) as exc:
        ClaudeCodeAdapter("claude-sonnet-5", fake).complete(PROMPT, request_id="answer:X")
    assert exc.value.kind == ErrorKind.NOT_READY


@pytest.mark.parametrize(
    ("message", "status", "kind"),
    [
        ("Claude AI usage limit reached|1760300000", 429, ErrorKind.QUOTA_EXHAUSTED),
        ("You've hit your limit · resets 9pm", None, ErrorKind.QUOTA_EXHAUSTED),
        ("API Error: 529 Overloaded", 529, ErrorKind.TRANSIENT),
        ("Invalid credentials", 401, ErrorKind.NOT_READY),
    ],
)
def test_claude_error_kinds(message: str, status: int | None, kind: ErrorKind) -> None:
    fake = FakeExec(claude_json(is_error=True, result=message, api_error_status=status))
    with pytest.raises(AdapterError) as exc:
        ClaudeCodeAdapter("claude-sonnet-5", fake).complete(PROMPT, request_id="answer:X")
    assert exc.value.kind == kind


def test_claude_refuses_a_silent_model_fallback() -> None:
    fake = FakeExec(claude_json(modelUsage={"claude-haiku-5": {}}))
    with pytest.raises(AdapterError) as exc:
        ClaudeCodeAdapter("claude-sonnet-5", fake).complete(PROMPT, request_id="answer:X")
    assert exc.value.kind == ErrorKind.NOT_READY
    assert "claude-haiku-5" in str(exc.value)


def test_claude_thinking_is_split_from_output_and_truncation_flagged() -> None:
    data = json.loads(claude_json())
    data["usage"]["output_tokens"] = 500
    data["usage"]["output_tokens_details"] = {"thinking_tokens": 300}
    data["stop_reason"] = "max_tokens"
    reply = ClaudeCodeAdapter("claude-sonnet-5", FakeExec(json.dumps(data))).complete(
        PROMPT, request_id="answer:X"
    )
    assert (reply.usage.output_tokens, reply.usage.reasoning_tokens) == (200, 300)
    assert reply.truncated


def test_claude_garbage_output_is_invalid_response() -> None:
    with pytest.raises(AdapterError) as exc:
        ClaudeCodeAdapter("claude-sonnet-5", FakeExec("not json")).complete(
            PROMPT, request_id="answer:X"
        )
    assert exc.value.kind == ErrorKind.INVALID_RESPONSE


# ---------------------------------------------------------------------- codex_cli
def codex_events(text: str = "Hello!", **usage: int) -> str:
    u = {"input_tokens": 2400, "cached_input_tokens": 2048, "output_tokens": 85}
    u.update(usage)
    events = [
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "i0", "type": "reasoning", "text": "..."}},
        {"type": "item.completed", "item": {"id": "i1", "type": "agent_message", "text": text}},
        {"type": "turn.completed", "usage": u},
    ]
    return "\n".join(json.dumps(e) for e in events) + "\n"


def test_codex_parses_events() -> None:
    fake = FakeExec(codex_events(reasoning_output_tokens=25))
    reply = CodexAdapter("gpt-6-luna", fake).complete(PROMPT, request_id="answer:X")
    assert reply.text == "Hello!"
    u = reply.usage
    assert (u.input_tokens, u.cached_tokens) == (2400, 2048)
    assert (u.output_tokens, u.reasoning_tokens) == (60, 25)  # reasoning split out of output
    assert u.overhead_tokens == 2400 - estimate_tokens(PROMPT)


def test_codex_command_is_read_only_and_isolated() -> None:
    fake = FakeExec(codex_events())
    CodexAdapter("gpt-6-luna", fake).complete(PROMPT, request_id="answer:X")
    argv, stdin, cwd = fake.calls[0]
    assert argv[:3] == ["codex", "exec", "--json"]
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert argv[argv.index("--cd") + 1] == cwd
    assert argv[argv.index("--model") + 1] == "gpt-6-luna"
    for flag in ("--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules"):
        assert flag in argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv
    assert argv[-1] == "-" and stdin == PROMPT and PROMPT not in argv


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("You've hit your usage limit. Try again in 3 hours.", ErrorKind.QUOTA_EXHAUSTED),
        ("unexpected status 401 Unauthorized", ErrorKind.NOT_READY),
        ("stream disconnected before completion", ErrorKind.TRANSIENT),
    ],
)
def test_codex_turn_failed_kinds(message: str, kind: ErrorKind) -> None:
    out = "\n".join(
        [
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "turn.failed", "error": {"message": message}}),
        ]
    )
    with pytest.raises(AdapterError) as exc:
        CodexAdapter("gpt-6-luna", FakeExec(out, returncode=1)).complete(
            PROMPT, request_id="answer:X"
        )
    assert exc.value.kind == kind


def test_codex_without_a_message_is_invalid_response() -> None:
    out = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1}})
    with pytest.raises(AdapterError) as exc:
        CodexAdapter("gpt-6-luna", FakeExec(out)).complete(PROMPT, request_id="answer:X")
    assert exc.value.kind == ErrorKind.INVALID_RESPONSE


def test_missing_cli_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(AdapterError) as exc:
        CodexAdapter("gpt-6-luna").complete(PROMPT, request_id="answer:X")
    assert exc.value.kind == ErrorKind.NOT_READY


def test_codex_parses_real_recorded_output() -> None:
    fake = FakeExec((FIXTURES / "codex_ok.jsonl").read_text())
    reply = CodexAdapter("gpt-6-luna", fake).complete(PROMPT, request_id="answer:X")
    assert reply.text == "Hello!"
    u = reply.usage
    assert (u.input_tokens, u.cached_tokens, u.output_tokens) == (13487, 11008, 6)
    assert u.reasoning_tokens is None  # 0 reported: not shown as a fake 0
    assert u.overhead_tokens == 13487 - estimate_tokens(PROMPT)  # Codex's own instructions
