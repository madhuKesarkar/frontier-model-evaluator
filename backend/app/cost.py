"""API-equivalent cost (backend-spec BE-R20). Nothing is billed; this is what the tokens
*would* cost on the provider's paid API at public list prices."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def api_equivalent_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    price_in_per_mtok: float,
    price_out_per_mtok: float,
    reasoning_tokens: int | None = None,
) -> float | None:
    """(input x price_in + (output + reasoning) x price_out) / 1,000,000, to $0.000001.
    Returns None when input or output tokens are unknown (never a fake 0)."""
    if input_tokens is None or output_tokens is None:
        return None
    billed_out = output_tokens + (reasoning_tokens or 0)
    total = (
        Decimal(input_tokens) * Decimal(str(price_in_per_mtok))
        + Decimal(billed_out) * Decimal(str(price_out_per_mtok))
    ) / Decimal(1_000_000)
    return float(total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
