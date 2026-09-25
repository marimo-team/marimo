from __future__ import annotations

from decimal import Decimal

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.delimited import DelimitedDialect
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager

HAS_DEPS = DependencyManager.polars.has()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_delimited_str_pt_br() -> None:
    import polars as pl

    manager = NarwhalsTableManager.from_dataframe(
        pl.DataFrame(
            {
                "integer": [1234],
                "fraction": [1234.567890123456],
                "text": ["value.1,2;3"],
                "null": [None],
            }
        )
    )
    result = manager.to_delimited_str(DelimitedDialect(";", ","))
    assert (
        result
        == 'integer;fraction;text;null\n1234;1234,567890123456;"value.1,2;3";\n'
    )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_delimited_str_decimal_and_exponent() -> None:
    import polars as pl

    manager = NarwhalsTableManager.from_dataframe(
        pl.DataFrame(
            {
                "decimal": [Decimal("1234.567890123456")],
                "exponent": [1.23e-10],
            }
        )
    )
    result = manager.to_delimited_str(DelimitedDialect(";", ","))
    assert result == "decimal;exponent\n1234,567890123456;1,23e-10\n"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_delimited_str_non_finite() -> None:
    import polars as pl

    manager = NarwhalsTableManager.from_dataframe(
        pl.DataFrame({"value": [float("nan"), float("inf"), float("-inf")]})
    )
    result = manager.to_delimited_str(DelimitedDialect(";", ","))
    assert result == "value\nnan\ninf\n-inf\n"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_delimited_str_unicode_decimal() -> None:
    import polars as pl

    manager = NarwhalsTableManager.from_dataframe(
        pl.DataFrame({"value": [12.5]})
    )
    result = manager.to_delimited_str(DelimitedDialect(",", "٫"))
    assert result == "value\n12٫5\n"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_csv_str_remains_locale_neutral() -> None:
    import polars as pl

    manager = NarwhalsTableManager.from_dataframe(
        pl.DataFrame({"value": [12.5], "text": ["1.2"]})
    )
    assert manager.to_csv_str() == "value,text\n12.5,1.2\n"
