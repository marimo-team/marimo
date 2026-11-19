# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from unittest import mock

import pytest

from marimo._ast.sql_visitor import (
    POLARS_SQL_MIN_VERSION,
    find_polars_sql_table_names,
)
from marimo._config.types import SqlOutputType
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.polars import PolarsEngine, PolarsSQLResult
from marimo._sql.error_utils import MarimoSQLException
from marimo._sql.sql import sql

pytestmark = pytest.mark.skipif(
    not DependencyManager.polars.has_at_version(
        min_version=POLARS_SQL_MIN_VERSION, quiet=True
    ),
    reason=f"Polars SQL requires polars>={POLARS_SQL_MIN_VERSION}",
)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("SELECT * FROM cars", {"cars"}),
        ("SELECT * FROM a SEMI JOIN b USING (id)", {"a", "b"}),
        ("SELECT * FROM `cars`", {"cars"}),
        ('SELECT * FROM "Cars"', {"Cars"}),
        (
            "SELECT * FROM (SELECT * FROM a) WHERE x IN (SELECT x FROM b)",
            {"a", "b"},
        ),
        ("SELECT * FROM a UNION ALL SELECT * FROM b", {"a", "b"}),
        # Qualified names and names that aren't identifiers aren't frames.
        ("SELECT * FROM sch.cars JOIN `my cars` USING (id)", set()),
        # CTE names are over-reported; at worst they add an extra edge.
        ("WITH t AS (SELECT * FROM a) SELECT * FROM t", {"a", "t"}),
        ("SELECT * FROM cars WHERE", set()),
    ],
)
def test_find_polars_sql_table_names(query: str, expected: set[str]) -> None:
    assert find_polars_sql_table_names(query) == expected


def test_find_polars_sql_table_names_tolerates_parser_changes() -> None:
    with mock.patch(
        "polars._plr.PySQLContext.table_identifiers",
        side_effect=AttributeError,
    ):
        assert find_polars_sql_table_names("SELECT * FROM cars") == set()


def test_find_polars_sql_table_names_requires_supported_polars() -> None:
    with mock.patch.object(
        DependencyManager.polars, "has_at_version", return_value=False
    ):
        assert find_polars_sql_table_names("SELECT * FROM cars") == set()


def _engine(**namespace: object) -> PolarsEngine:
    return PolarsEngine(namespace)


def _execute_cars_query(sql_output_format: SqlOutputType) -> PolarsSQLResult:
    import polars as pl

    engine = _engine(cars=pl.LazyFrame({"id": [1, 2], "make": ["a", "b"]}))
    with mock.patch.object(
        PolarsEngine, "sql_output_format", return_value=sql_output_format
    ):
        return engine.execute("SELECT make FROM cars WHERE id > 1")


@pytest.mark.parametrize("sql_output_format", ["auto", "polars"])
def test_execute_collects_eager_output(
    sql_output_format: SqlOutputType,
) -> None:
    import polars as pl

    result = _execute_cars_query(sql_output_format)
    assert isinstance(result, pl.DataFrame)
    assert result["make"].to_list() == ["b"]


@pytest.mark.parametrize("sql_output_format", ["lazy-polars", "native"])
def test_execute_keeps_lazy_output_lazy(
    sql_output_format: SqlOutputType,
) -> None:
    import polars as pl

    result = _execute_cars_query(sql_output_format)
    assert isinstance(result, pl.LazyFrame)
    assert result.collect()["make"].to_list() == ["b"]


@pytest.mark.requires("pandas", "pyarrow")
def test_execute_pandas_output() -> None:
    import pandas as pd

    result = _execute_cars_query("pandas")
    assert isinstance(result, pd.DataFrame)
    assert result["make"].to_list() == ["b"]


def test_execute_joins_eager_and_lazy_frames() -> None:
    import polars as pl

    engine = _engine(
        cars=pl.DataFrame({"id": [1, 2], "make": ["a", "b"]}),
        owners=pl.LazyFrame({"id": [2], "owner": ["x"]}),
        not_a_frame=[1, 2, 3],
    )
    with mock.patch.object(
        PolarsEngine, "sql_output_format", return_value="polars"
    ):
        result = engine.execute(
            "SELECT make, owner FROM cars JOIN owners USING (id)"
        )
    assert isinstance(result, pl.DataFrame)
    assert result.to_dicts() == [{"make": "b", "owner": "x"}]


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM cars WHERE",
        "SELECT * FROM missing",
        "SELECT nope FROM cars",
    ],
)
def test_execute_raises_sql_errors_eagerly(query: str) -> None:
    import polars as pl

    engine = _engine(cars=pl.LazyFrame({"id": [1]}))
    with (
        mock.patch.object(
            PolarsEngine, "sql_output_format", return_value="lazy-polars"
        ),
        pytest.raises(MarimoSQLException) as exc_info,
    ):
        engine.execute(query)
    assert exc_info.value.sql_statement == query


def test_execute_requires_supported_polars() -> None:
    with (
        mock.patch.object(
            DependencyManager.polars, "get_version", return_value="1.36.0"
        ),
        pytest.raises(RuntimeError, match=POLARS_SQL_MIN_VERSION),
    ):
        _engine().execute("SELECT 1")


@pytest.mark.parametrize(
    ("engine", "expected"),
    [("polars", True), ("Polars", False), ("duckdb", False), (None, False)],
)
def test_is_compatible(engine: object, expected: bool) -> None:
    assert PolarsEngine.is_compatible(engine) is expected


@mock.patch("marimo._sql.sql.replace")
def test_sql_default_limit(mock_replace: mock.MagicMock) -> None:
    import polars as pl

    namespace = {"numbers": pl.LazyFrame({"n": list(range(10))})}
    with (
        mock.patch.dict(os.environ, {"MARIMO_RUNTIME_SQL_DEFAULT_LIMIT": "3"}),
        mock.patch(
            "marimo._sql.sql._execution_globals", return_value=namespace
        ),
    ):
        with mock.patch.object(
            PolarsEngine, "sql_output_format", return_value="auto"
        ):
            eager = sql("SELECT * FROM numbers", engine="polars")
        assert isinstance(eager, pl.DataFrame)
        assert len(eager) == 3
        assert mock_replace.call_args[0][0]._component_args["total-rows"] == (
            "too_many"
        )

        with mock.patch.object(
            PolarsEngine, "sql_output_format", return_value="lazy-polars"
        ):
            lazy = sql("SELECT * FROM numbers", engine="polars")
        assert isinstance(lazy, pl.LazyFrame)
        assert len(lazy.collect()) == 3
