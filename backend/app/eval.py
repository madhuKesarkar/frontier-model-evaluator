"""Command-line entry point for evaluation runs (backend-spec BE-R8b; D-12, D-13).

    python -m app.eval migrate
    python -m app.eval run --models claude-pro gpt-go [--categories ...] [--tiers ...]
                           [--repeats 1] [--call-cap 50] [--fixtures DIR]
    python -m app.eval resume RUN_ID [--fixtures DIR]
    python -m app.eval summary [RUN_ID]

Live runs use the access mode in config/models.yaml and are started only by the architect.
`--fixtures DIR` replays recorded responses from DIR/<model_key>/ instead (no live call).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.adapters.base import Adapter
from app.adapters.fixture import FixtureAdapter
from app.aggregates import summarize_model
from app.db import Run, make_engine, make_session_factory
from app.registry import AccessMode, ModelEntry, load_registry
from app.runner import EvaluationRunner, RunConfig
from app.sandbox import DockerSandbox
from app.settings import REPO_ROOT, Settings, assert_no_paid_keys
from app.suite import load_suite, validate_suite


class CliError(RuntimeError):
    pass


def build_adapters(models: list[ModelEntry], fixtures: Path | None) -> dict[str, Adapter]:
    adapters: dict[str, Adapter] = {}
    for model in models:
        if not model.enabled:
            continue
        if fixtures is not None or model.access_mode == AccessMode.FIXTURE:
            directory = (fixtures or REPO_ROOT / "backend/fixtures/demo") / model.key
            if not directory.is_dir():
                raise CliError(f"no recorded responses for {model.key} in {directory}")
            adapters[model.key] = FixtureAdapter.from_dir(directory)
        else:
            raise CliError(
                f"{model.key}: live access mode '{model.access_mode}' arrives in Phase 4 "
                "(claude-plan.md). Use --fixtures for recorded runs until then."
            )
    return adapters


def migrate(settings: Settings) -> None:
    cfg = Config(str(REPO_ROOT / "backend/alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "backend/migrations"))
    command.upgrade(cfg, "head")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.eval", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="create or upgrade the database schema")
    run_p = sub.add_parser("run", help="start an evaluation run")
    run_p.add_argument("--models", nargs="+", required=True)
    run_p.add_argument("--categories", nargs="*")
    run_p.add_argument("--tiers", nargs="*")
    run_p.add_argument("--repeats", type=int, default=1)
    run_p.add_argument("--call-cap", type=int, default=50)
    run_p.add_argument("--fixtures", type=Path)
    run_p.add_argument("--label", default="", help="free-text label stored with the run")
    res_p = sub.add_parser("resume", help="resume a paused or stopped run")
    res_p.add_argument("run_id", type=int)
    res_p.add_argument("--fixtures", type=Path)
    sum_p = sub.add_parser("summary", help="print scores for a run (default: latest)")
    sum_p.add_argument("run_id", type=int, nargs="?")
    args = parser.parse_args(argv)

    assert_no_paid_keys()  # BE-R1
    settings = Settings.from_env()
    if args.cmd == "migrate":
        migrate(settings)
        print(f"Database ready: {settings.database_url}")
        return 0

    sessions = make_session_factory(make_engine(settings.database_url))
    registry = load_registry(settings.models_file)
    if args.cmd == "summary":
        with sessions() as s:
            run = (
                s.get(Run, args.run_id)
                if args.run_id
                else s.scalars(select(Run).order_by(Run.id.desc())).first()
            )
            if run is None:
                raise CliError("no runs yet")
            print(f"Run {run.id}: {run.status}, {run.calls_made}/{run.call_cap} calls, "
                  f"API-equivalent ${run.api_equiv_cost_usd:.4f} {run.params}")  # fmt: skip
            for key in run.model_keys:
                m = summarize_model(s, run.id, key)
                cats = ", ".join(f"{c}={v}" for c, v in m.categories.items())
                print(f"  {key}: overall={m.overall} | {cats} | S1+S2 defects="
                      f"{m.open_s1_s2_defects} | needs_review={m.needs_review}")  # fmt: skip
        return 0

    tasks = load_suite(settings.suite_dir)
    problems = validate_suite(tasks)
    if problems:
        raise CliError("suite is invalid: " + "; ".join(problems))
    adapters = build_adapters(registry, args.fixtures)
    runner = EvaluationRunner(
        sessions, registry, tasks, adapters, DockerSandbox(settings.sandbox_image)
    )
    if args.cmd == "run":
        recorded = args.fixtures is not None or any(
            m.access_mode == AccessMode.FIXTURE for m in registry if m.key in args.models
        )
        params = {"label": args.label, "source": "recorded" if recorded else "live"}
        run_id = runner.start(
            RunConfig(
                args.models, args.categories, args.tiers, args.repeats, args.call_cap, params
            )  # fmt: skip
        )
    else:
        run_id = args.run_id
        runner.resume(run_id)
    with sessions() as s:
        run = s.get(Run, run_id)
        print(f"Run {run_id} finished with status: {run.status if run else '?'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # one clear line for the architect instead of a traceback
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
