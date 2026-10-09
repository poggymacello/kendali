"""Exact money handling. Never use floats for amounts."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation

DECIMALS = 6
UNIT = Decimal(10) ** DECIMALS


def to_units(amount: Decimal | str | int) -> int:
    """Convert a human amount (e.g. Decimal('540.00')) to token base units (6 decimals)."""
    d = Decimal(str(amount))
    if d < 0:
        raise ValueError("negative amount")
    return int((d * UNIT).to_integral_value(rounding=ROUND_DOWN))


def from_units(units: int) -> Decimal:
    return (Decimal(units) / UNIT).quantize(Decimal("0.01"))


def parse_amount(text: str) -> Decimal | None:
    """Parse '1,250.50', '1.250,50', '1250' into Decimal. Returns None if not a number."""
    s = text.strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        # decide decimal separator by the last occurrence
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        s = s.replace(",", "") if len(parts[-1]) == 3 else s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def fmt(amount: Decimal | int, unit: str = "tUSDC") -> str:
    d = from_units(amount) if isinstance(amount, int) else Decimal(amount)
    return f"{d:,.2f} {unit}"
