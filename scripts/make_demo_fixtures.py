"""Generate SYNTHETIC recorded responses for the two demo models (backend/fixtures/demo/).

These are not real model outputs. They are reference answers with deliberate, realistic
flaws so the screens have scores, defects and token data before the architect's live run.
Re-run after changing the suite:  python scripts/make_demo_fixtures.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.suite import load_suite  # noqa: E402

OUT = ROOT / "backend/fixtures/demo"
TIER_LATENCY = {"simple": 2400, "mid": 5200, "complex": 11800}
OVERHEAD = {"demo-claude": 2600, "demo-gpt": 1900}  # CLI system-prompt tokens (illustrative)

# Planted flaws: (answer override, judge score, judge defects)
FLAWS: dict[str, dict[str, tuple[str | None, int | None, list[dict[str, str]]]]] = {
    "demo-claude": {
        "RA-M-01": ("Pixels 4200 + iPhones 3120 = 7320; add 18% GST.\nANSWER: 8637.60", None, []),
        "LC-C-01": (
            '{"q1": "4.00", "q2": "60", "q3": "4", "q4": "NOT_IN_DOCUMENT"}',
            3,
            [
                {
                    "type": "HALLUCINATION",
                    "severity": "S3",
                    "title": "Used the superseded overage rate from section 3",
                }
            ],
        ),
        "TD-C-01": (
            None,
            3,
            [
                {
                    "type": "INSTRUCTION_VIOLATION",
                    "severity": "S3",
                    "title": "No interaction test between daily cap and scheduling",
                }
            ],
        ),
    },
    "demo-gpt": {
        "CG-C-01": ("REF:self._clock() >= expiry|self._clock() > expiry", 4, []),  # off-by-one
        "SO-C-01": (
            'REF:"breaking"|"fix"',
            3,
            [
                {
                    "type": "REASONING_ERROR",
                    "severity": "S3",
                    "title": "Field removal classified as a fix, not breaking",
                }
            ],
        ),
        "TU-C-01": (
            '{"calls": [{"tool": "create_return", "arguments": {"order_id": "ORD-7781",'
            ' "item_ids": ["I1", "I3"], "reason": "changed_mind"}}, {"tool": "issue_refund",'
            ' "arguments": {"order_id": "ORD-7781", "amount_inr": 4298}}],'
            ' "message_to_customer": "Done! Your refund of Rs 4,298 has been issued."}',
            2,
            [
                {
                    "type": "INSTRUCTION_VIOLATION",
                    "severity": "S1",
                    "title": "Refund issued before items were received (policy P2)",
                }
            ],
        ),
        "LC-S-01": ('{"q1": "15", "q2": "The lab manager"}', None, []),
        "TD-M-01": (None, 4, []),
    },
}
JUDGE_OF = {"demo-claude": "demo-gpt", "demo-gpt": "demo-claude"}


def tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def main() -> None:
    tasks = load_suite(ROOT / "suite/v1")
    shutil.rmtree(OUT, ignore_errors=True)
    for model in FLAWS:
        (OUT / model).mkdir(parents=True, exist_ok=True)
    for model, flaws in FLAWS.items():
        judge = JUDGE_OF[model]
        for t in tasks:
            override, judge_score, judge_defects = flaws.get(t.task_id, (None, None, []))
            text = t.reference_response
            if override and override.startswith("REF:"):
                old, new = override[4:].split("|")
                if text.count(old) != 1:
                    raise SystemExit(f"{model}/{t.task_id}: '{old}' must occur exactly once")
                text = text.replace(old, new)
            elif override:
                text = override
            usage = {
                "input_tokens": tokens(t.prompt) + OVERHEAD[model],
                "output_tokens": tokens(text),
                "overhead_tokens": OVERHEAD[model],
                "cached_tokens": OVERHEAD[model] if model == "demo-claude" else None,
            }
            reply = {
                "text": text,
                "usage": usage,
                "latency_ms": TIER_LATENCY[t.tier] + (700 if model == "demo-gpt" else 0),
            }
            (OUT / model / f"answer__{t.task_id}.json").write_text(
                json.dumps(reply, indent=1) + "\n"
            )
            if t.uses_judge:
                verdict = {
                    "score": judge_score or 5,
                    "rationale": "Synthetic demo verdict.",
                    "defects": judge_defects,
                }
                jreply = {"text": json.dumps(verdict), "usage": {"input_tokens": 1500,
                          "output_tokens": 120}, "latency_ms": 3000}  # fmt: skip
                name = f"judge__{model}__{t.task_id}.json"
                (OUT / judge / name).write_text(json.dumps(jreply, indent=1) + "\n")
    print(f"wrote synthetic fixtures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
