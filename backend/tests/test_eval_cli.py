"""End-to-end through the command line with the synthetic demo fixtures (D-12, BE-R8b)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import eval as cli
from app.aggregates import summarize_model
from app.db import Run, make_engine, make_session_factory
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


def test_live_access_mode_is_not_available_yet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models = tmp_path / "models.yaml"
    models.write_text(
        "models:\n  - {key: claude-pro, provider: anthropic, access_mode: claude_code_cli,"
        " model_id: x, display_name: x, context_window: 0, price_input_per_mtok: 0,"
        " price_output_per_mtok: 0}\n"
    )
    monkeypatch.setenv("FME_MODELS_FILE", str(models))
    monkeypatch.setenv("FME_DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    cli.main(["migrate"])
    with pytest.raises(cli.CliError, match="Phase 4"):
        cli.main(["run", "--models", "claude-pro"])


def test_cli_refuses_paid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(Exception, match="not allowed"):
        cli.main(["summary"])
