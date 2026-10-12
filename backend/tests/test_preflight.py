"""Preflight (BE-R2): readiness per access mode, never a billable call."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.adapters.cli import CliResult
from app.preflight import check_claude, check_codex, preflight
from app.registry import ModelEntry

# Shape of the architect's real `claude auth status` (2026-10-12), personal fields left out.
CLAUDE_OK = json.dumps(
    {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
     "subscriptionType": "pro"}
)  # fmt: skip
MODEL_COMMANDS = {"-p", "exec"}  # any of these would be a model call


class fake:  # noqa: N801 - reads like a function at the call sites
    """Answers status commands from a table; fails the test on anything that calls a model."""

    def __init__(self, outputs: dict[str, tuple[int, str]]) -> None:
        self.outputs = outputs
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str], stdin: str, cwd: str, timeout_s: int) -> CliResult:
        args = list(argv)
        self.calls.append(args)
        assert not MODEL_COMMANDS & set(args), f"preflight must not call a model: {args}"
        code, out = self.outputs.get(" ".join(args), (127, "command not found"))
        return CliResult(code, out, "", 5)


def claude_outputs(status: str = CLAUDE_OK) -> dict[str, tuple[int, str]]:
    return {
        "claude --version": (0, "2.1.296 (Claude Code)"),
        "claude auth status --json": (0, status),
    }


def codex_outputs(status: str = "Logged in using ChatGPT") -> dict[str, tuple[int, str]]:
    return {"codex --version": (0, "codex-cli 0.162.1"), "codex login status": (0, status)}


def test_claude_ready_with_subscription(tmp_path: Path) -> None:
    check = check_claude(fake(claude_outputs()), home=tmp_path)
    assert check.ready, check.reason
    assert "2.1.296" in check.reason and "Claude Pro" in check.reason
    assert check.warnings == []


def test_claude_api_key_sign_in_is_refused(tmp_path: Path) -> None:
    status = json.dumps({"loggedIn": True, "authMethod": "api_key"})
    check = check_claude(fake(claude_outputs(status)), home=tmp_path)
    assert not check.ready
    assert "not the Claude Pro subscription" in check.reason


def test_claude_signed_out_is_not_ready(tmp_path: Path) -> None:
    check = check_claude(fake(claude_outputs(json.dumps({"loggedIn": False}))), home=tmp_path)
    assert not check.ready and "/login" in check.reason


def test_claude_missing_is_not_ready(tmp_path: Path) -> None:
    check = check_claude(fake({}), home=tmp_path)
    assert not check.ready and "not installed" in check.reason


def test_claude_global_memory_file_is_warned_about(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("Always answer in French.")
    check = check_claude(fake(claude_outputs()), home=tmp_path)
    assert check.ready
    assert check.warnings and "overhead" in check.warnings[0]


@pytest.mark.parametrize(
    ("status", "ready", "reason"),
    [
        ("Logged in using ChatGPT", True, "signed in with ChatGPT"),
        ("Logged in using an API key - sk-test-***-real", False, "API key"),
        ("Not logged in", False, "not signed in"),
    ],
)
def test_codex_sign_in_states(status: str, ready: bool, reason: str) -> None:
    code = 1 if status == "Not logged in" else 0
    outputs = codex_outputs()
    outputs["codex login status"] = (code, status)
    check = check_codex(fake(outputs))
    assert check.ready is ready
    assert reason in check.reason


def entry(key: str, mode: str) -> ModelEntry:
    provider = "anthropic" if mode.startswith("claude") else "openai"
    return ModelEntry.model_validate(
        {"key": key, "provider": provider, "access_mode": mode, "model_id": "m",
         "display_name": key, "context_window": 0,
         "price_input_per_mtok": 1, "price_output_per_mtok": 1}
    )  # fmt: skip


def test_preflight_checks_each_enabled_mode_and_paid_keys() -> None:
    exec_ = fake({**claude_outputs(), **codex_outputs()})
    models = [entry("claude-pro", "claude_code_cli"), entry("gpt-go", "codex_cli")]
    checks = preflight(models, exec_, env={"OPENAI_API_KEY": "x" * 8})
    assert [c.access_mode for c in checks] == ["paid_keys", "claude_code_cli", "codex_cli"]
    assert [c.ready for c in checks] == [False, True, True]


def test_preflight_skips_fixture_models() -> None:
    exec_ = fake({})
    assert preflight([entry("demo", "fixture")], exec_, env={}) == []
    assert exec_.calls == []


def test_claude_free_plan_is_not_ready(tmp_path: Path) -> None:
    status = json.dumps({"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "free"})
    check = check_claude(fake(claude_outputs(status)), home=tmp_path)
    assert not check.ready and "free" in check.reason
