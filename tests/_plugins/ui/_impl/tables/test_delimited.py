from __future__ import annotations

import pytest

from marimo._plugins.ui._impl.tables.delimited import (
    DelimitedDialect,
    ResolvedExportLocale,
    resolve_delimited_dialect,
)


def locale(tag: str, decimal_separator: str) -> ResolvedExportLocale:
    return ResolvedExportLocale(tag=tag, decimal_separator=decimal_separator)


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
