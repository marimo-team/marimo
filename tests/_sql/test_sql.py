from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._sql.sql import _query_includes_limit, sql

HAS_DEPS = DependencyManager.has_duckdb() and DependencyManager.has_polars()


@pytest.mark.skipif(not HAS_DEPS, reason="pandas or polars is required")
def test_query_includes_limit():
    assert _query_includes_limit("SELECT * FROM t LIMIT 10") is True
    assert _query_includes_limit("SELECT * FROM t LIMIT\n10") is True
    assert _query_includes_limit("SELECT * FROM t limit 10") is True
    assert _query_includes_limit("SELECT * FROM t limit\n10") is True
    assert _query_includes_limit("SELECT * FROM t") is False
    assert _query_includes_limit("INSERT INTO t VALUES (1, 2, 3)") is False
    assert _query_includes_limit("") is False
    assert (
        _query_includes_limit("SELECT * FROM t; SELECT * FROM t2 LIMIT 5")
        is True
    )
    assert (
        _query_includes_limit("SELECT * FROM t LIMIT 5; SELECT * FROM t2")
        is False
    )


# @pytest.mark.skipif(not HAS_DEPS, reason="pandas or polars is required")
@patch("marimo._sql.sql.output.replace")
def test_applies_limit(mock_replace: MagicMock) -> None:
    import duckdb

    duckdb.sql("CREATE TABLE t AS SELECT * FROM range(1000)")
    mock_replace.assert_not_called()

    table: ui.table

    # No limit, fallback to 300
    assert len(sql("SELECT * FROM t")) == 300
    mock_replace.assert_called_once()
    table = mock_replace.call_args[0][0]
    assert table._component_args["total-rows"] == "too_many"
    assert table._component_args["pagination"] is True
    assert len(table._data) == 300
    assert table._filtered_manager.get_num_rows() == 300

    # Limit 10
    mock_replace.reset_mock()
    assert len(sql("SELECT * FROM t LIMIT 10")) == 10
    mock_replace.assert_called_once()
    table = mock_replace.call_args[0][0]
    assert table._component_args["total-rows"] == 10
    assert table._component_args["pagination"] is True
    assert len(table._data) == 10
    assert table._filtered_manager.get_num_rows() == 10

    # Limit 400
    mock_replace.reset_mock()
    assert len(sql("SELECT * FROM t LIMIT 400")) == 400
    mock_replace.assert_called_once()
    table = mock_replace.call_args[0][0]
    assert table._component_args["total-rows"] == 400
    assert table._component_args["pagination"] is True
    assert len(table._data) == 400
    assert table._filtered_manager.get_num_rows() == 400

    # Limit above 20_0000 (which is the mo.ui.table cutoff)
    mock_replace.reset_mock()
    duckdb.sql("CREATE TABLE big_table AS SELECT * FROM range(30_000)")
    assert len(sql("SELECT * FROM big_table LIMIT 25_000")) == 25_000
    mock_replace.assert_called_once()
    table = mock_replace.call_args[0][0]
    assert table._component_args["total-rows"] == 25_000
    assert table._component_args["pagination"] is True
    assert len(table._data) == 25_000
    assert (
        table._filtered_manager.get_num_rows() == 20_000
    )  # cutoff by mo.ui.table DEFAULT_ROW_LIMIT


@pytest.mark.skipif(HAS_DEPS, reason="must be missing deps")
def test_sql_raises_error_without_duckdb():
    with pytest.raises(ModuleNotFoundError):
        sql("SELECT * FROM t")
