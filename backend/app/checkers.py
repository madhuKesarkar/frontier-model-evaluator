"""Deterministic checkers (backend-spec §4 step 3, BE-R18). Model output is data (BE-R3).

`unit_tests` checkers are executed by a CodeRunner (the Docker sandbox in production);
this module only extracts the code and delegates.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import jsonschema

from app.suite import Checker

_CODE_BLOCK = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)
_JSON_BLOCK = re.compile(r"```(?:json)?[ \t]*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class CheckOutcome:
    checker: str
    passed: bool
    output: str


@dataclass(frozen=True)
class RunResult:
    passed: bool
    output: str
    timed_out: bool = False


class CodeRunner(Protocol):
    def run_tests(self, solution: str, tests: str) -> RunResult: ...


def extract_code(text: str) -> str | None:
    blocks = _CODE_BLOCK.findall(text)
    return max(blocks, key=len) if blocks else None


def extract_json(text: str) -> Any:
    """Parse the whole response as JSON, else the first ```json block, else the outermost {...}."""
    candidates = [text.strip(), *(_JSON_BLOCK.findall(text))]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    raise ValueError("response does not contain valid JSON")


def _normalize(value: str) -> str:
    return " ".join(value.strip().rstrip(".").split()).casefold()


def _resolve_pointer(document: Any, pointer: str) -> list[Any]:
    """JSON-pointer lookup where a '*' segment fans out over a list."""
    nodes = [document]
    for raw in pointer.strip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        nxt: list[Any] = []
        for node in nodes:
            if part == "*":
                if not isinstance(node, list):
                    raise KeyError(f"'{pointer}': expected a list")
                nxt.extend(node)
            elif isinstance(node, list):
                nxt.append(node[int(part)])
            elif isinstance(node, dict):
                nxt.append(node[part])
            else:
                raise KeyError(f"'{pointer}': cannot descend into {type(node).__name__}")
        nodes = nxt
    return nodes


def _extracted_value(checker: Checker, response: str) -> str:
    extract = checker.extract or {}
    if "answer_line" in extract:
        marker = str(extract["answer_line"])
        lines = [ln for ln in response.splitlines() if ln.strip().startswith(marker)]
        if not lines:
            raise ValueError(f"no line starting with '{marker}'")
        return lines[-1].strip()[len(marker) :].strip()
    if "json_pointer" in extract:
        values = _resolve_pointer(extract_json(response), str(extract["json_pointer"]))
        flat: list[Any] = []
        for v in values:
            flat.extend(v if isinstance(v, list) else [v])
        items = [str(v) for v in flat]
        if extract.get("sort"):
            items.sort()
        return ",".join(items)
    raise ValueError("exact_match needs extract.answer_line or extract.json_pointer")


def _numbers_equal(actual: str, expected: str) -> bool:
    try:
        return Decimal(actual.replace(",", "")) == Decimal(expected.replace(",", ""))
    except InvalidOperation:
        return False


def run_checker(checker: Checker, response: str, runner: CodeRunner | None = None) -> CheckOutcome:
    kind = checker.type
    try:
        if kind == "json_schema":
            jsonschema.validate(extract_json(response), checker.schema_ or {})
            return CheckOutcome(kind, True, "valid")
        if kind == "exact_match":
            actual = _extracted_value(checker, response)
            expected = checker.expected or ""
            ok = (
                _numbers_equal(actual, expected)
                if checker.numeric
                else _normalize(actual) == _normalize(expected)
            )
            return CheckOutcome(kind, ok, f"expected {expected!r}, got {actual!r}")
        if kind == "regex":
            ok = re.search(checker.pattern or "", response) is not None
            return CheckOutcome(kind, ok, f"pattern {'found' if ok else 'not found'}")
        if kind == "unit_tests":
            code = extract_code(response)
            if code is None:
                return CheckOutcome(kind, False, "no ```python code block in the response")
            if runner is None:
                raise RuntimeError("unit_tests checker needs a CodeRunner (sandbox)")
            result = runner.run_tests(code, checker.tests or "")
            note = " (killed: time limit)" if result.timed_out else ""
            return CheckOutcome(kind, result.passed, result.output[-4000:] + note)
    except jsonschema.ValidationError as exc:
        return CheckOutcome(
            kind, False, f"schema violation at {list(exc.absolute_path)}: {exc.message}"
        )
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return CheckOutcome(kind, False, f"could not evaluate: {exc}")
    raise ValueError(f"run_checker does not handle {kind!r} (llm_judge is scored by the judge)")
