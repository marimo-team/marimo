# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from tests._data.mocks import create_dataframes


@pytest.mark.requires("duckdb", "polars")
def test_duckdb_dataframe_has_isolated_connection() -> None:
    import duckdb

    default_tables = duckdb.sql("SHOW TABLES").fetchall()
    (relation,) = create_dataframes({"value": [1, 2]}, include=["duckdb"])
    assert isinstance(relation, duckdb.DuckDBPyRelation)

    # Relation.query creates a temporary view, as Narwhals' timezone lookup does.
    assert relation.query(
        "fixture_view", "SELECT * FROM fixture_view"
    ).fetchall() == [
        (1,),
        (2,),
    ]
    assert duckdb.sql("SHOW TABLES").fetchall() == default_tables

    (other_relation,) = create_dataframes({"value": [3]}, include=["duckdb"])
    assert isinstance(other_relation, duckdb.DuckDBPyRelation)
    assert other_relation.query(
        "fixture_view", "SELECT * FROM fixture_view"
    ).fetchall() == [
        (3,),
    ]
    assert relation.query(
        "fixture_view", "SELECT * FROM fixture_view"
    ).fetchall() == [
        (1,),
        (2,),
    ]
