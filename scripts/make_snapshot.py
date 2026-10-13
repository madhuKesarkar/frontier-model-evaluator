"""Freeze the latest completed run for the read-only public demo (D-13, Phase 5).

Copies the local database (VACUUM INTO, so it's a clean single file) and the model registry
used for it into deploy/. The deployed API serves exactly these two files, read-only.

    python scripts/make_snapshot.py [--db fme.db] [--models config/models.yaml]

It refuses to write a snapshot without a completed run, and scans the copy for anything
that looks like a secret before keeping it.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy"
SECRET = re.compile(rb"(sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=ROOT / "fme.db")
    parser.add_argument("--models", type=Path, default=ROOT / "config/models.yaml")
    args = parser.parse_args()

    if not args.db.exists():
        sys.exit(f"No database at {args.db}: run `make eval` first.")
    if not args.models.exists():
        sys.exit(f"No model registry at {args.models}.")
    with sqlite3.connect(args.db) as con:
        runs = con.execute(
            "SELECT id, status, params FROM run WHERE status = 'completed' ORDER BY id DESC"
        ).fetchall()
    if not runs:
        sys.exit("No completed run in the database: nothing to publish.")

    OUT.mkdir(exist_ok=True)
    target = OUT / "fme.db"
    target.unlink(missing_ok=True)
    with sqlite3.connect(args.db) as con:
        con.execute("VACUUM INTO ?", (str(target),))
    if SECRET.search(target.read_bytes()):
        target.unlink()
        sys.exit("Refused: the snapshot contains something that looks like an API key.")
    shutil.copyfile(args.models, OUT / "models.yaml")

    run_id, _, params = runs[0]
    size_kb = target.stat().st_size // 1024
    print(f"Snapshot written: deploy/fme.db ({size_kb} KB, latest completed run {run_id}, "
          f"{params}) and deploy/models.yaml")  # fmt: skip
    print("Next: commit deploy/ on a branch, open a PR, merge -> Render redeploys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
