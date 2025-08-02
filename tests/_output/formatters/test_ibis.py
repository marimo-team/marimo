from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import (
    get_formatter,
)

HAS_IBIS = DependencyManager.ibis.has()
HAS_POLARS = DependencyManager.polars.has()


@pytest.fixture
def test_table():
    """Create a test ibis table with various data types."""
    if not HAS_IBIS:
        pytest.skip("ibis not available")

    import ibis

    test_data = {
        "str": ["a", "c", "hello"],
        "num": [1, 2, 3],
        "list": [["a", "b"], ["c"], []],
        "struct": [{"a": 0}, {"a": 1}, {"a": 2}],
        "floats": [1.1, 2.2, None],
    }
    return ibis.memtable(test_data)


@pytest.mark.skipif(not HAS_IBIS, reason="ibis not installed")
def test_ibis_formatters_interactive_mode(test_table) -> None:
    """Test ibis formatters in interactive mode."""
    register_formatters()

    import ibis

    # Save original setting
    original_interactive = ibis.options.interactive
    ibis.options.interactive = True

    try:
        # Test table - should return table widget
        formatter = get_formatter(test_table, include_opinionated=False)
        assert formatter is not None
        mime, content = formatter(test_table)
        assert mime == "text/html"
        assert "<marimo-table" in content

        # Test column - should return table widget via as_table()
        column = test_table.struct
        formatter = get_formatter(column, include_opinionated=False)
        assert formatter is not None
        mime, content = formatter(column)
        assert mime == "text/html"
        assert "<marimo-table" in content

        # Test scalar - should return formatted text
        scalar = test_table.floats.min()
        formatter = get_formatter(scalar, include_opinionated=False)
        assert formatter is not None
        mime, content = formatter(scalar)
        assert mime == "text/html"
        assert content.startswith("<pre")

    finally:
        ibis.options.interactive = original_interactive


@pytest.mark.skipif(not HAS_IBIS, reason="ibis not installed")
def test_ibis_formatters_lazy_mode(test_table) -> None:
    """Test ibis formatters in lazy mode."""
    register_formatters()

    import ibis

    # Save original setting
    original_interactive = ibis.options.interactive
    ibis.options.interactive = False

    try:
        # Test table - should return Expression+SQL tabs
        formatter = get_formatter(test_table, include_opinionated=False)
        assert formatter is not None
        mime, content = formatter(test_table)
        assert mime == "text/html"
        assert "<marimo-tabs" in content

        # Test column - should return Expression+SQL tabs
        column = test_table.struct
        formatter = get_formatter(column, include_opinionated=False)
        assert formatter is not None
        mime, content = formatter(column)
        assert mime == "text/html"
        assert "<marimo-tabs" in content

        # Test scalar - should return Expression+SQL tabs
        scalar = test_table.floats.min()
        formatter = get_formatter(scalar, include_opinionated=False)
        assert formatter is not None
        mime, content = formatter(scalar)
        assert mime == "text/html"
        assert "<marimo-tabs" in content

    finally:
        ibis.options.interactive = original_interactive


@pytest.mark.skipif(not HAS_IBIS, reason="ibis not installed")
def test_ibis_unbound_expressions() -> None:
    """Test unbound expressions - should always show Expression+SQL tabs."""
    register_formatters()

    import ibis

    # Create unbound tables like in smoke tests
    t1 = ibis.table(
        dict(value1="float", key1="string", key2="string"), name="table1"
    )
    t2 = ibis.table(
        dict(value2="float", key3="string", key4="string"), name="table2"
    )
    joined = t1.left_join(t2, t1.key1 == t2.key3)

    # Test in both interactive modes - should always return tabs
    for interactive_mode in [True, False]:
        original_interactive = ibis.options.interactive
        ibis.options.interactive = interactive_mode

        try:
            formatter = get_formatter(joined, include_opinionated=False)
            assert formatter is not None

            mime, content = formatter(joined)
            assert mime == "text/html"
            assert "<marimo-tabs" in content
        finally:
            ibis.options.interactive = original_interactive


@pytest.mark.skipif(not HAS_IBIS, reason="ibis not installed")
def test_ibis_complex_scalar_interactive(test_table) -> None:
    """Test complex scalar (array) in interactive mode - should return JSON output."""
    register_formatters()

    import ibis

    # Save original setting
    original_interactive = ibis.options.interactive
    ibis.options.interactive = True

    try:
        # Array scalar like in smoke tests
        array_scalar = test_table.list.first()

        formatter = get_formatter(array_scalar, include_opinionated=False)
        assert formatter is not None

        mime, content = formatter(array_scalar)
        # Complex scalars should use JSON output
        assert mime == "text/html"
        assert "<marimo-json-output" in content

    finally:
        ibis.options.interactive = original_interactive


@pytest.mark.skipif(
    not HAS_IBIS or not HAS_POLARS, reason="ibis and polars not installed"
)
def test_ibis_polars_backend() -> None:
    """Test ibis with polars backend - SQL tab should show 'Backend doesn't support SQL'."""
    register_formatters()

    import ibis
    import polars as pl

    lazy_frame = pl.LazyFrame(
        {"name": ["Jimmy", "Keith"], "band": ["Led Zeppelin", "Stones"]}
    )
    pl_connection = ibis.polars.connect(tables={"band_members": lazy_frame})

    original_interactive = ibis.options.interactive
    ibis.options.interactive = False

    try:
        polars_table = pl_connection.table("band_members")

        formatter = get_formatter(polars_table, include_opinionated=False)
        assert formatter is not None

        mime, content = formatter(polars_table)
        assert mime == "text/html"
        assert "<marimo-tabs" in content

    finally:
        ibis.options.interactive = original_interactive
