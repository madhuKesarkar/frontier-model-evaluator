"""Model registry loaded from config/models.yaml (backend-spec §2, FR-01)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class AccessMode(StrEnum):
    CLAUDE_CODE_CLI = "claude_code_cli"
    CODEX_CLI = "codex_cli"
    GEMINI_FREE_API = "gemini_free_api"
    FIXTURE = "fixture"  # recorded responses, used by tests and demos (never a live call)


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1)
    provider: Provider
    access_mode: AccessMode
    model_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    context_window: int = Field(ge=0)
    price_input_per_mtok: float = Field(ge=0)
    price_output_per_mtok: float = Field(ge=0)
    enabled: bool = True


class RegistryError(ValueError):
    """Raised when models.yaml is invalid. The message names the entry and field (BE-AC-02)."""


def parse_registry(data: Any) -> list[ModelEntry]:
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise RegistryError("models.yaml must contain a top-level 'models' list")
    entries: list[ModelEntry] = []
    seen: set[str] = set()
    for index, raw in enumerate(data["models"]):
        label = raw.get("key", f"#{index + 1}") if isinstance(raw, dict) else f"#{index + 1}"
        try:
            entry = ModelEntry.model_validate(raw)
        except ValidationError as exc:
            problems = "; ".join(
                f"field '{'.'.join(str(p) for p in err['loc'])}': {err['msg']}"
                for err in exc.errors()
            )
            raise RegistryError(f"Invalid model entry '{label}': {problems}") from None
        if entry.key in seen:
            raise RegistryError(f"Invalid model entry '{entry.key}': duplicate key")
        seen.add(entry.key)
        entries.append(entry)
    return entries


def load_registry(path: Path) -> list[ModelEntry]:
    if not path.exists():
        raise RegistryError(f"Model registry not found: {path} (copy config/models.example.yaml)")
    return parse_registry(yaml.safe_load(path.read_text(encoding="utf-8")))


def selectable(entries: list[ModelEntry]) -> list[ModelEntry]:
    """Models that may be chosen for a run (BE-AC-01: enabled only)."""
    return [e for e in entries if e.enabled]
