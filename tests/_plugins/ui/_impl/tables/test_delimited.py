from __future__ import annotations

from decimal import Decimal
from numbers import Real

import pytest

from marimo._plugins.ui._impl.tables.delimited import (
    ResolvedExportLocale,
    resolve_delimited_dialect,
)
from marimo._utils.delimited import (
    DelimitedDialect,
    format_delimited_number,
    is_delimited_number,
)


def locale(tag: str, decimal_separator: str) -> ResolvedExportLocale:
    return ResolvedExportLocale(tag=tag, decimal_separator=decimal_separator)


def _format_if_delimited_number(value: object) -> str | None:
    from typing_extensions import assert_type

    if is_delimited_number(value):
        assert_type(value, Real | Decimal)
        return format_delimited_number(value, ",")
    return None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, "1"),
        (1.25, "1,25"),
        (Decimal("1.25"), "1,25"),
        (True, None),
        ("1.25", None),
    ],
)
def test_delimited_number_narrowing(
    value: object, expected: str | None
) -> None:
    assert _format_if_delimited_number(value) == expected


def test_resolve_csv_comma_decimal_uses_semicolon_fields() -> None:
    assert resolve_delimited_dialect(
        "csv", locale("pt-BR", ","), None
    ) == DelimitedDialect(";", ",")


def test_resolve_csv_explicit_separator_wins() -> None:
    assert resolve_delimited_dialect(
        "csv", locale("pt-BR", ","), "|"
    ) == DelimitedDialect("|", ",")


def test_resolve_tsv_ignores_explicit_separator() -> None:
    assert resolve_delimited_dialect(
        "tsv", locale("pt-BR", ","), "|"
    ) == DelimitedDialect("\t", ",")


def test_resolve_csv_without_locale_preserves_current_behavior() -> None:
    assert resolve_delimited_dialect("csv", None, None) == DelimitedDialect(
        ",", "."
    )


def test_resolve_tsv_without_locale_uses_tab_and_dot() -> None:
    assert resolve_delimited_dialect("tsv", None, None) == DelimitedDialect(
        "\t", "."
    )


def test_resolve_csv_decimal_point_uses_comma_fields() -> None:
    assert resolve_delimited_dialect(
        "csv", locale("en-US", "."), None
    ) == DelimitedDialect(",", ".")


@pytest.mark.parametrize(
    "bad_locale",
    [
        locale("", ","),
        locale("pt-BR", ",,"),
        locale("pt-BR", "\r"),
        locale("pt-BR", "\n"),
        locale("pt-BR", "\0"),
        locale("pt-BR", ""),
    ],
)
def test_resolve_rejects_malformed_locale(
    bad_locale: ResolvedExportLocale,
) -> None:
    with pytest.raises(ValueError):
        resolve_delimited_dialect("csv", bad_locale, None)
