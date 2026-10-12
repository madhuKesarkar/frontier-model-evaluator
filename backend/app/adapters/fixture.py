"""Recorded-response adapter: tests and offline demos, never a live call (BE-R4)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.adapters.base import AdapterError, AdapterResponse, ErrorKind, Usage

Script = list[dict[str, Any]]


def _to_response(item: dict[str, Any]) -> AdapterResponse:
    if "error" in item:
        raise AdapterError(ErrorKind(item["error"]), item.get("message", ""))
    usage = item.get("usage", {})
    return AdapterResponse(
        text=item["text"],
        usage=Usage(
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            reasoning_tokens=usage.get("reasoning_tokens"),
            cached_tokens=usage.get("cached_tokens"),
            overhead_tokens=usage.get("overhead_tokens"),
            estimated=usage.get("estimated", {}),
        ),
        latency_ms=int(item.get("latency_ms", 1000)),
        truncated=bool(item.get("truncated", False)),
    )


class FixtureAdapter:
    """Replays scripted replies per request_id. Each request_id maps to a list; call N gets
    item N (the last item repeats). Items are {"text", "usage", ...} or {"error": kind}."""

    def __init__(self, scripts: dict[str, Script]) -> None:
        self._scripts = scripts
        self._calls: dict[str, int] = defaultdict(int)
        self.log: list[str] = []

    @classmethod
    def from_dir(cls, directory: Path) -> FixtureAdapter:
        """Load <request_id with ':' replaced by '__'>.json files from a directory."""
        scripts: dict[str, Script] = {}
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            scripts[path.stem.replace("__", ":")] = data if isinstance(data, list) else [data]
        return cls(scripts)

    def complete(self, prompt: str, *, request_id: str) -> AdapterResponse:
        self.log.append(request_id)
        script = self._scripts.get(request_id)
        if not script:
            raise AdapterError(ErrorKind.INVALID_RESPONSE, f"no fixture for {request_id}")
        index = min(self._calls[request_id], len(script) - 1)
        self._calls[request_id] += 1
        return _to_response(script[index])
