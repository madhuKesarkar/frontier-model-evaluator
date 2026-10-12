"""Command-line entry point for evaluation runs (backend-spec BE-R8b; D-12, D-13).

    python -m app.eval migrate
    python -m app.eval run --models claude-pro gpt-go [--categories ...] [--tiers ...]
                           [--repeats 1] [--call-cap 50] [--fixtures DIR]
    python -m app.eval resume RUN_ID [--fixtures DIR]
    python -m app.eval summary [RUN_ID]
    python -m app.eval preflight
    python -m app.eval calibrate [--fixtures DIR]


Live runs use the access mode in config/models.yaml and are started only by the architect.
`--fixtures DIR` replays recorded responses from DIR/<model_key>/ instead (no live call).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.adapters.base import Adapter
from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex import CodexAdapter
from app.adapters.fixture import FixtureAdapter
from app.aggregates import summarize_model
from app.calibration import calibrate, load_sets
from app.db import Run, make_engine, make_session_factory
from app.preflight import Check, preflight
from app.registry import AccessMode, ModelEntry, load_registry
from app.runner import EvaluationRunner, RunConfig
from app.sandbox import DockerSandbox, SandboxUnavailable
from app.settings import REPO_ROOT, Settings, assert_no_paid_keys
from app.suite import Task, load_suite, validate_suite


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
        elif model.access_mode == AccessMode.CLAUDE_CODE_CLI:
            adapters[model.key] = ClaudeCodeAdapter(model.model_id)
        elif model.access_mode == AccessMode.CODEX_CLI:
            adapters[model.key] = CodexAdapter(model.model_id)
        else:
            raise CliError(f"{model.key}: access mode '{model.access_mode}' is Post-MVP (D-17)")
    return adapters


def print_checks(checks: list[Check]) -> bool:
    for c in checks:
        print(f"  [{'ready' if c.ready else 'NOT READY'}] {c.access_mode}: {c.reason}")
        for w in c.warnings:
            print(f"      warning: {w}")
    return all(c.ready for c in checks)


def require_ready(models: list[ModelEntry]) -> None:
    """Before any live call (BE-R2): every live access mode must pass preflight. Judges come
    from the other provider, so all enabled live models are checked, not only the selected."""
    live = [m for m in models if m.enabled and m.access_mode != AccessMode.FIXTURE]
    if not live:
        return
    print("Preflight (no model calls):")
    if not print_checks(preflight(live)):
        raise CliError("preflight failed: fix the items marked NOT READY, then run again")


def run_calibration(
    registry: list[ModelEntry], tasks: list[Task], fixtures: Path | None, report_path: Path
) -> int:
    """SM-3 / SM-4: every enabled model, acting as a judge, grades the 12 calibration items."""
    if fixtures is None:
        require_ready(registry)
    judges = build_adapters(registry, fixtures)
    golden, seeded, labelled_by = load_sets(REPO_ROOT / "suite/calibration")
    print(f"Calibrating {len(judges)} judge(s): up to {len(judges) * 24} calls "
          f"({len(golden)} golden + {len(seeded)} seeded each, one retry if invalid)")  # fmt: skip
    if labelled_by != "architect":
        print(f"  note: golden labels are '{labelled_by}', not yet approved by the architect")
    reports = calibrate(judges, {t.task_id: t for t in tasks}, golden, seeded)
    for r in reports:
        verdict = "PASS" if r.passed else "FAIL"
        print(f"  {r.judge}: agreement {r.agreement:.0%} (SM-3), catch rate {r.catch_rate:.0%} "
              f"(SM-4) -> {verdict}")  # fmt: skip
        for item in r.golden + r.seeded:
            if not item.ok:
                print(f"      miss {item.id}: judge {item.judge_score}, expected {item.expected}")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {"labelled_by": labelled_by, "source": "recorded" if fixtures else "live",
             "judges": [r.as_dict() for r in reports]},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    print(f"Report written to {report_path}")
    return 0 if all(r.passed for r in reports) else 1


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
    sub.add_parser("preflight", help="check each access mode is ready (no model calls)")
    cal_p = sub.add_parser("calibrate", help="judge check on the golden + seeded sets")
    cal_p.add_argument("--fixtures", type=Path)
    cal_p.add_argument("--report", type=Path, default=REPO_ROOT / "reports/calibration.json")
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
    if args.cmd == "preflight":
        checks = preflight(registry)
        if not checks:
            print("No live access modes configured (fixture models only).")
            return 0
        return 0 if print_checks(checks) else 1
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
    if args.cmd == "calibrate":
        return run_calibration(registry, tasks, args.fixtures, args.report)
    if args.fixtures is None:
        require_ready(registry)
    adapters = build_adapters(registry, args.fixtures)
    try:
        sandbox = DockerSandbox(settings.sandbox_image)
        sandbox.check()  # before any model call: a dead sandbox must not cost quota
    except SandboxUnavailable as exc:
        raise CliError(
            f"Docker sandbox not ready ({exc}). Start Docker Desktop and run `make sandbox`."
        ) from exc
    runner = EvaluationRunner(sessions, registry, tasks, adapters, sandbox)
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
        if run and run.status == "error":
            print(f"Stopped: {runner.last_error}. Fix it, then: python -m app.eval resume {run_id}")
            return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # one clear line for the architect instead of a traceback
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
