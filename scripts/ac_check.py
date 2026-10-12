"""AC traceability check (CLAUDE.md "Checks"; claude-plan.md §4).

Every acceptance criterion in demo scope must have at least one test whose name
contains its ID. IDs are written in tests as e.g. ``BE_AC16`` / ``BE-AC-16``.

- AC IDs are read from the specs (bold ``**BE-AC-16**`` definitions).
- An AC is *Post-MVP* if its row in the claude-plan.md matrix has type ``—``.
- Tests are found in backend/tests/**/*.py and frontend/src/**/*.test.ts(x).

Usage:
    python scripts/ac_check.py            # report only (exit 0)
    python scripts/ac_check.py --strict   # exit 1 if any demo AC is uncovered
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AC_DEF = re.compile(r"\*\*((?:BE|FE|API)-AC-\d+)\*\*")
MATRIX_ROW = re.compile(r"((?:BE|FE|API)-AC-\d+) \| ([^|]+)\|")
# Not \b: "_" is a word character, so "test_BE_AC16" has no word boundary before "BE".
TEST_REF = re.compile(r"(?<![A-Za-z0-9])(BE|FE|API)[-_]AC[-_]?(\d+)(?!\d)")


def canonical(prefix: str, number: str) -> str:
    return f"{prefix}-AC-{int(number):02d}"


def defined_acs() -> set[str]:
    found: set[str] = set()
    for spec in (ROOT / "specs").glob("*-spec.md"):
        found.update(AC_DEF.findall(spec.read_text(encoding="utf-8")))
    return found


def post_mvp_acs() -> set[str]:
    plan = (ROOT / "claude-plan.md").read_text(encoding="utf-8")
    return {ac for ac, kind in MATRIX_ROW.findall(plan) if kind.strip() == "—"}


def referenced_acs() -> dict[str, list[str]]:
    files = list((ROOT / "backend" / "tests").rglob("*.py"))
    files += list((ROOT / "frontend" / "src").rglob("*.test.ts"))
    files += list((ROOT / "frontend" / "src").rglob("*.test.tsx"))
    files += list((ROOT / "frontend" / "e2e").rglob("*.spec.ts"))
    refs: dict[str, list[str]] = {}
    for path in files:
        for prefix, number in TEST_REF.findall(path.read_text(encoding="utf-8")):
            refs.setdefault(canonical(prefix, number), []).append(str(path.relative_to(ROOT)))
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="fail if any demo AC is uncovered")
    args = parser.parse_args()

    defined = defined_acs()
    deferred = post_mvp_acs() & defined
    in_scope = sorted(defined - deferred, key=lambda a: (a.split("-")[0], int(a.split("-")[2])))
    refs = referenced_acs()

    covered = [ac for ac in in_scope if ac in refs]
    uncovered = [ac for ac in in_scope if ac not in refs]
    unknown = sorted(set(refs) - defined)

    print(f"Demo-scope ACs: {len(in_scope)}  covered: {len(covered)}  uncovered: {len(uncovered)}")
    print(f"Post-MVP (not required): {len(deferred)}")
    for ac in covered:
        print(f"  [x] {ac}  <- {', '.join(sorted(set(refs[ac])))}")
    for ac in uncovered:
        print(f"  [ ] {ac}")
    if unknown:
        print(f"Tests reference unknown AC IDs: {', '.join(unknown)}")

    if unknown or (args.strict and uncovered):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
