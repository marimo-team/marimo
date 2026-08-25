# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

DownloadFormat = Literal["csv", "tsv"]

_FORBIDDEN_DECIMAL_SEPARATORS = frozenset({"\r", "\n", "\0"})


@dataclass(frozen=True)
class ResolvedExportLocale:
    tag: str
    decimal_separator: str


@dataclass(frozen=True)
class DelimitedDialect:
    field_separator: str
    decimal_separator: str


def resolve_delimited_dialect(
    download_format: DownloadFormat,
    locale: ResolvedExportLocale | None,
    explicit_separator: str | None = None,
) -> DelimitedDialect:
    """Resolve field and decimal separators for CSV or TSV export.

    TSV always uses a tab field separator. An explicit CSV separator wins.
    CSV uses `;` when the decimal separator is `,`, otherwise `,`. A missing
    locale keeps the current locale-neutral defaults.
    """
    if download_format not in ("csv", "tsv"):
        raise ValueError(f"Unsupported delimited format: {download_format}")

    if locale is not None:
        _validate_locale(locale)
        decimal_separator = locale.decimal_separator
    else:
        decimal_separator = "."

    if download_format == "tsv":
        return DelimitedDialect("\t", decimal_separator)

    if explicit_separator is not None:
        field_separator = explicit_separator
    elif decimal_separator == ",":
        field_separator = ";"
    else:
        field_separator = ","

    return DelimitedDialect(field_separator, decimal_separator)


def is_delimited_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(
        value, (int, float, Decimal)
    )


def format_delimited_number(
    value: float | Decimal, decimal_separator: str
) -> str:
    """Format a numeric value without grouping, using `decimal_separator`."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    text = str(value)
    if decimal_separator == ".":
        return text
    return text.replace(".", decimal_separator)


def _validate_locale(locale: ResolvedExportLocale) -> None:
    if locale.tag == "":
        raise ValueError("Locale tag must be a non-empty string.")
    separator = locale.decimal_separator
    if len(separator) != 1 or separator in _FORBIDDEN_DECIMAL_SEPARATORS:
        raise ValueError(
            "Decimal separator must be a single Unicode character."
        )
