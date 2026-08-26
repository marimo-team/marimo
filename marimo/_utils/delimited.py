# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from numbers import Integral, Real
from typing import Any


@dataclass(frozen=True)
class DelimitedDialect:
    field_separator: str
    decimal_separator: str


def is_delimited_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (Integral, Real, Decimal))


def format_delimited_number(
    value: Real | Decimal, decimal_separator: str
) -> str:
    """Format a numeric value without grouping."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    text = str(value)
    if decimal_separator == ".":
        return text
    return text.replace(".", decimal_separator)
