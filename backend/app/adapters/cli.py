"""Shared plumbing for the subscription CLIs (backend-spec §3, D-2).

Every call runs in a fresh, empty working directory, so no project files (and no
CLAUDE.md / AGENTS.md from this repo) leak into the prompt, and the prompt goes in on
stdin, never on the command line.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.adapters.base import AdapterError, ErrorKind
from app.settings import PAID_KEY_VARS

CALL_TIMEOUT_S = 300


@dataclass(frozen=True)
class CliResult:
    returncode: int
    stdout: str
    stderr: str
    latency_ms: int


# Injected in tests; production runs the real binary.
Exec = Callable[[Sequence[str], str, str, int], CliResult]


def run_process(argv: Sequence[str], stdin: str, cwd: str, timeout_s: int) -> CliResult:
    # The paid-key guard (BE-R1) already refuses to start with these set; strip them anyway
    # so a child CLI can never fall back to pay-per-use billing.
    env = {k: v for k, v in os.environ.items() if k not in PAID_KEY_VARS}
    started = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            list(argv),
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdapterError(ErrorKind.TIMEOUT, f"{argv[0]} took longer than {timeout_s}s") from exc
    except FileNotFoundError as exc:
        raise AdapterError(ErrorKind.NOT_READY, f"{argv[0]} is not installed") from exc
    return CliResult(
        proc.returncode, proc.stdout, proc.stderr, int((time.monotonic() - started) * 1000)
    )


def run_in_empty_dir(
    exec_: Exec, argv_for: Callable[[str], Sequence[str]], prompt: str, timeout_s: int
) -> CliResult:
    """Run the CLI in a throwaway empty directory (argv may need the directory path)."""
    with tempfile.TemporaryDirectory(prefix="fme-call-") as workdir:
        return exec_(argv_for(workdir), prompt, workdir, timeout_s)


def estimate_tokens(text: str) -> int:
    """Rough tokenizer-free estimate (~4 characters per token). Only used to split a
    reported input count into task tokens and access-mode overhead (backend-spec §3)."""
    return max(1, round(len(text) / 4))


def overhead(reported_input: int | None, prompt: str) -> int | None:
    if reported_input is None:
        return None
    return max(0, reported_input - estimate_tokens(prompt))


QUOTA_MARKERS = (
    "usage limit",
    "limit reached",
    "hit your limit",
    "quota",
    "out of credits",
    "limit will reset",
)
AUTH_MARKERS = (
    "not logged in",
    "failed to authenticate",
    "please run /login",
    "login expired",
    "oauth",
    "unauthorized",
    "401",
)


def classify_failure(message: str) -> ErrorKind:
    """Map a CLI error message to the adapter error kinds (backend-spec §3)."""
    text = message.lower()
    if any(m in text for m in AUTH_MARKERS):
        return ErrorKind.NOT_READY
    if any(m in text for m in QUOTA_MARKERS):
        return ErrorKind.QUOTA_EXHAUSTED
    return ErrorKind.TRANSIENT
