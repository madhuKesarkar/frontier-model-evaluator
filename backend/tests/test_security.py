"""No provider secrets in error messages, stored data or committed files (BE-AC-23)."""

from __future__ import annotations

import re
import subprocess

import pytest

from app.settings import REPO_ROOT, PaidKeyError, assert_no_paid_keys

KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),  # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),  # OpenAI
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),  # Google
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),  # GitHub tokens
]


def test_BE_AC23_guard_error_never_echoes_the_key_value() -> None:
    fake_value = "-".join(["sk", "ant", "api03", "FAKE" * 6])  # built at runtime, never committed
    with pytest.raises(PaidKeyError) as err:
        assert_no_paid_keys({"ANTHROPIC_API_KEY": fake_value})
    assert fake_value not in str(err.value)
    assert "ANTHROPIC_API_KEY" in str(err.value)


def test_BE_AC23_no_key_shaped_strings_in_committed_files() -> None:
    git_ls = ["git", "ls-files"]
    listing = subprocess.run(git_ls, cwd=REPO_ROOT, capture_output=True, text=True, check=True)  # noqa: S603
    files = listing.stdout.split()
    hits = []
    for name in files:
        path = REPO_ROOT / name
        if path.suffix in {".png", ".ico", ".lock"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits += [f"{name}: {p.pattern}" for p in KEY_PATTERNS if p.search(text)]
    assert hits == []


def test_key_pattern_detector_works() -> None:
    planted = "OPENAI_API_KEY=sk-proj-" + "a1B2" * 12
    assert any(p.search(planted) for p in KEY_PATTERNS)
