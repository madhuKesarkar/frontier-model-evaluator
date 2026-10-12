"""Preflight (backend-spec BE-R2): is each access mode ready, without a billable call?

Checks, per enabled model: the CLI is installed, it is signed in, and it is signed in with
the SUBSCRIPTION (Claude Pro / ChatGPT), not an API key. An API-key sign-in would bill
per token, so it counts as not ready (goal-spec D-2, $0 rule).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.adapters.base import AdapterError
from app.adapters.cli import Exec, run_process
from app.registry import AccessMode, ModelEntry
from app.settings import PAID_KEY_VARS

# `claude auth status` methods that mean a Claude subscription sign-in. Anything else
# (an API key, a Console account, an unknown value) is refused rather than guessed.
CLAUDE_SUBSCRIPTION_METHODS = {"oauth_token", "claude.ai", "claude_ai", "subscription"}


@dataclass
class Check:
    access_mode: str
    ready: bool
    reason: str
    warnings: list[str] = field(default_factory=list)


def _run(exec_: Exec, argv: list[str]) -> tuple[int, str]:
    with tempfile.TemporaryDirectory(prefix="fme-preflight-") as workdir:
        try:
            result = exec_(argv, "", workdir, 30)
        except AdapterError as exc:
            return 127, str(exc)
    return result.returncode, (result.stdout + "\n" + result.stderr).strip()


def check_claude(exec_: Exec = run_process, home: Path | None = None) -> Check:
    mode = AccessMode.CLAUDE_CODE_CLI.value
    code, out = _run(exec_, ["claude", "--version"])
    if code != 0:
        return Check(
            mode, False, "Claude Code is not installed (npm i -g @anthropic-ai/claude-code)"
        )
    version = out.splitlines()[0] if out else "?"
    code, out = _run(exec_, ["claude", "auth", "status", "--json"])
    try:
        status = json.loads(out)
    except ValueError:
        return Check(mode, False, f"Could not read `claude auth status`: {out[:200]}")
    if not status.get("loggedIn"):
        return Check(mode, False, "Claude Code is not signed in: run `claude`, then /login")
    method = str(status.get("authMethod", ""))
    if method not in CLAUDE_SUBSCRIPTION_METHODS:
        return Check(
            mode,
            False,
            f"Claude Code is signed in with '{method}', not the Claude Pro subscription. "
            "Run `claude`, /login, and choose the Claude account with subscription.",
        )
    plan = str(status.get("subscriptionType", "")).lower()
    if plan and plan not in {"pro", "max"}:
        return Check(mode, False, f"Claude Code subscription is '{plan}', expected Pro (or Max)")
    warnings = []
    memory = (home or Path.home()) / ".claude" / "CLAUDE.md"
    if memory.exists():
        warnings.append(
            f"{memory} exists: Claude Code adds it to every prompt, so it shows up as "
            "overhead tokens and may influence answers. Consider moving it aside for the run."
        )
    label = f"Claude {plan.title()}" if plan else method
    return Check(mode, True, f"{version}, signed in with the subscription ({label})", warnings)


def check_codex(exec_: Exec = run_process) -> Check:
    mode = AccessMode.CODEX_CLI.value
    code, out = _run(exec_, ["codex", "--version"])
    if code != 0:
        return Check(mode, False, "Codex CLI is not installed (npm i -g @openai/codex)")
    version = out.splitlines()[-1] if out else "?"
    code, out = _run(exec_, ["codex", "login", "status"])
    text = out.lower()
    if code != 0 or "not logged in" in text:
        return Check(
            mode, False, "Codex is not signed in: run `codex login` (Sign in with ChatGPT)"
        )
    if "api key" in text:
        return Check(
            mode,
            False,
            "Codex is signed in with an API key (pay-per-use). Run `codex logout`, then "
            "`codex login` and choose Sign in with ChatGPT.",
        )
    if "chatgpt" not in text:
        return Check(mode, False, f"Unrecognised `codex login status` output: {out[:200]}")
    return Check(mode, True, f"{version}, signed in with ChatGPT")


def preflight(
    models: list[ModelEntry], exec_: Exec = run_process, env: dict[str, str] | None = None
) -> list[Check]:
    environ = os.environ if env is None else env
    checks: list[Check] = []
    keys = [k for k in PAID_KEY_VARS if environ.get(k, "").strip()]
    if keys:
        checks.append(Check("paid_keys", False, f"Paid API key set: {', '.join(keys)} (BE-R1)"))
    modes = {m.access_mode for m in models if m.enabled}
    if AccessMode.CLAUDE_CODE_CLI in modes:
        checks.append(check_claude(exec_))
    if AccessMode.CODEX_CLI in modes:
        checks.append(check_codex(exec_))
    return checks
