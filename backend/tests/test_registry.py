"""Model registry and paid-key guard (backend-spec BE-R1, §2)."""

from pathlib import Path

import pytest
import yaml

from app.registry import RegistryError, load_registry, parse_registry, selectable
from app.settings import PaidKeyError, assert_no_paid_keys

VALID = {
    "key": "claude-pro",
    "provider": "anthropic",
    "access_mode": "claude_code_cli",
    "model_id": "some-model",
    "display_name": "Claude (Pro)",
    "context_window": 200000,
    "price_input_per_mtok": 3.0,
    "price_output_per_mtok": 15.0,
    "enabled": True,
}


def test_BE_AC01_new_entry_is_listed_and_selectable_without_code_change(tmp_path: Path) -> None:
    other = {**VALID, "key": "gemini-flash", "provider": "google", "access_mode": "gemini_free_api"}
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({"models": [VALID, other]}), encoding="utf-8")
    entries = load_registry(path)
    assert [e.key for e in selectable(entries)] == ["claude-pro", "gemini-flash"]


@pytest.mark.parametrize("missing", ["model_id", "price_input_per_mtok", "price_output_per_mtok"])
def test_BE_AC02_missing_field_fails_naming_field_and_entry(missing: str) -> None:
    raw = {k: v for k, v in VALID.items() if k != missing}
    with pytest.raises(RegistryError) as err:
        parse_registry({"models": [raw]})
    assert "claude-pro" in str(err.value)
    assert missing in str(err.value)


def test_disabled_model_is_not_selectable() -> None:
    entries = parse_registry({"models": [{**VALID, "enabled": False}]})
    assert selectable(entries) == []


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(RegistryError, match="duplicate"):
        parse_registry({"models": [VALID, VALID]})


@pytest.mark.parametrize("var", ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"])
def test_BE_AC03_paid_key_blocks_startup(var: str) -> None:
    with pytest.raises(PaidKeyError) as err:
        assert_no_paid_keys({var: "sk-anything", "GEMINI_API_KEY": "free-tier"})
    assert var in str(err.value)
    assert "not allowed" in str(err.value)


def test_free_gemini_key_alone_is_allowed() -> None:
    assert_no_paid_keys({"GEMINI_API_KEY": "free-tier", "ANTHROPIC_API_KEY": "  "})
