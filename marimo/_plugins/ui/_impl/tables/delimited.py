# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from marimo._utils.delimited import DelimitedDialect

DownloadFormat = Literal["csv", "tsv"]

_FORBIDDEN_DECIMAL_SEPARATORS = frozenset({"\r", "\n", "\0"})


class InvalidExportLocaleError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedExportLocale:
    tag: str
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


def _validate_locale(locale: ResolvedExportLocale) -> None:
    if locale.tag == "":
        raise InvalidExportLocaleError(
            "Locale tag must be a non-empty string."
        )
    separator = locale.decimal_separator
    if len(separator) != 1 or separator in _FORBIDDEN_DECIMAL_SEPARATORS:
        raise InvalidExportLocaleError(
            "Decimal separator must be a single Unicode character."
        )
