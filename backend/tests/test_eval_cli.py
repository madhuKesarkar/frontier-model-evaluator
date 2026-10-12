"""End-to-end through the command line with the synthetic demo fixtures (D-12, BE-R8b)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import eval as cli
from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex import CodexAdapter
from app.aggregates import summarize_model
from app.db import Run, make_engine, make_session_factory
from app.preflight import Check
from app.registry import load_registry
from app.settings import REPO_ROOT


@pytest.fixture
def demo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("FME_DATABASE_URL", url)
    monkeypatch.setenv("FME_MODELS_FILE", str(REPO_ROOT / "config/models.demo.yaml"))
    assert cli.main(["migrate"]) == 0
    return url


def summaries(url: str) -> dict[str, dict[str, float | None]]:
    sessions = make_session_factory(make_engine(url))
    with sessions() as s:
        run = s.query(Run).one()
        assert run.status == "completed" and run.params["source"] == "recorded"
        return {k: summarize_model(s, run.id, k).categories for k in run.model_keys}


def test_cli_run_scores_planted_flaws_without_code_tasks(demo_env: str) -> None:
    args = ["run", "--models", "demo-claude", "demo-gpt", "--categories", "reasoning",
            "tool_use", "long_context", "--label", "test"]  # fmt: skip
    assert cli.main(args) == 0
    cats = summaries(demo_env)
    assert cats["demo-claude"]["reasoning"] == 4.0  # forgot the discount (5, 2, 5)
    assert cats["demo-gpt"]["tool_use"] == 3.7  # refund before receipt -> S1 -> 1
    assert cats["demo-gpt"]["long_context"] == 3.7  # hallucinated approver -> S1 -> 1
    assert cats["demo-claude"]["code_generation"] is None  # not run


@pytest.mark.docker
def test_cli_full_demo_run_with_sandbox(demo_env: str, sandbox: object) -> None:
    import os

    os.environ["FME_SANDBOX_IMAGE"] = getattr(sandbox, "image", "fme-sandbox:1")
    assert cli.main(["run", "--models", "demo-claude", "demo-gpt", "--call-cap", "100"]) == 0
    cats = summaries(demo_env)
    assert cats["demo-gpt"]["code_generation"] == 4.0  # expiry off-by-one fails unit tests
    assert cats["demo-claude"]["code_generation"] == 5.0


def live_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models = tmp_path / "models.yaml"
    models.write_text(
        "models:\n"
        "  - {key: claude-pro, provider: anthropic, access_mode: claude_code_cli,"
        " model_id: claude-sonnet-5, display_name: x, context_window: 0,"
        " price_input_per_mtok: 3, price_output_per_mtok: 15}\n"
        "  - {key: gpt-go, provider: openai, access_mode: codex_cli,"
        " model_id: gpt-6-luna, display_name: y, context_window: 0,"
        " price_input_per_mtok: 1, price_output_per_mtok: 8}\n"
    )
    monkeypatch.setenv("FME_MODELS_FILE", str(models))
    monkeypatch.setenv("FME_DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    cli.main(["migrate"])


def test_live_run_refuses_to_start_when_preflight_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_registry(tmp_path, monkeypatch)
    not_ready = [Check("codex_cli", False, "Codex is signed in with an API key")]
    monkeypatch.setattr(cli, "preflight", lambda models: not_ready)
    built: list[str] = []
    monkeypatch.setattr(cli, "build_adapters", lambda *a: built.append("x"))
    with pytest.raises(cli.CliError, match="preflight failed"):
        cli.main(["run", "--models", "claude-pro"])
    assert built == []  # stopped before any adapter (and so any model call) exists


def test_live_models_get_cli_adapters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    live_registry(tmp_path, monkeypatch)
    adapters = cli.build_adapters(load_registry(tmp_path / "models.yaml"), None)
    assert isinstance(adapters["claude-pro"], ClaudeCodeAdapter)
    assert isinstance(adapters["gpt-go"], CodexAdapter)
    assert adapters["claude-pro"].model_id == "claude-sonnet-5"


def test_preflight_command_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_registry(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "preflight", lambda models: [Check("claude_code_cli", True, "ok")])
    assert cli.main(["preflight"]) == 0
    monkeypatch.setattr(cli, "preflight", lambda models: [Check("codex_cli", False, "no")])
    assert cli.main(["preflight"]) == 1
    assert "NOT READY" in capsys.readouterr().out


def test_cli_refuses_paid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(Exception, match="not allowed"):
        cli.main(["summary"])
