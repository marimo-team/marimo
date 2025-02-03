from __future__ import annotations

from marimo._plugins.ui._impl.tables.format import format_value


def test_numeric_formatting():
    # Test positive number with + sign
    assert format_value("col", 42.123, {"col": "{:+.2f}"}) == "+42.12"
    assert format_value("col", -42.123, {"col": "{:+.2f}"}) == "-42.12"

    # Test thousand separators
    assert format_value("col", 1234.567, {"col": "{:,.2f}"}) == "1,234.57"
    assert format_value("col", -1234.567, {"col": "{:,.2f}"}) == "-1,234.57"

    # Test combining + sign and thousand separators
    assert format_value("col", 1234.567, {"col": "{:+,.2f}"}) == "+1,234.57"
    assert format_value("col", -1234.567, {"col": "{:+,.2f}"}) == "-1,234.57"

    # Test integer values
    assert format_value("col", 1234, {"col": "{:,d}"}) == "1,234"
    assert format_value("col", -1234, {"col": "{:+,d}"}) == "-1,234"

    # Test non-numeric values (should not be affected)
    assert format_value("col", "text", {"col": "{}"}) == "text"
    assert format_value("col", None, {"col": "{}"}) is None
