"""Runtime settings read from the environment (backend-spec §1, §3)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Paid provider keys that must never be present (BE-R1, D-2).
PAID_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


class PaidKeyError(RuntimeError):
    """Raised at startup when a paid API key is found in the environment."""


def assert_no_paid_keys(env: dict[str, str] | None = None) -> None:
    """BE-R1: refuse to start if a paid API key is set (even to an empty-looking value)."""
    environ = os.environ if env is None else env
    found = [name for name in PAID_KEY_VARS if environ.get(name, "").strip()]
    if found:
        raise PaidKeyError(
            f"Paid API keys are not allowed: {', '.join(found)} is set. "
            "This project runs at $0 using Claude Code, Codex CLI and the free Gemini tier "
            "(goal-spec D-2). Unset the variable and start again."
        )


@dataclass(frozen=True)
class Settings:
    models_file: Path
    suite_dir: Path
    database_url: str
    read_only: bool
    sandbox_image: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            models_file=Path(os.environ.get("FME_MODELS_FILE", REPO_ROOT / "config/models.yaml")),
            suite_dir=Path(os.environ.get("FME_SUITE_DIR", REPO_ROOT / "suite/v1")),
            database_url=os.environ.get("FME_DATABASE_URL", f"sqlite:///{REPO_ROOT / 'fme.db'}"),
            read_only=os.environ.get("FME_READ_ONLY", "0") == "1",
            sandbox_image=os.environ.get("FME_SANDBOX_IMAGE", "fme-sandbox:1"),
        )
