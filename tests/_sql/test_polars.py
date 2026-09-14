# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from marimo._sql.engines.polars import PolarsEngine
from marimo._sql.error_utils import MarimoSQLException, is_sql_parse_error
from marimo._sql.sql import sql


@pytest.mark.requires("polars", "sqlglot")
class TestPolarsEngine:
    def test_dataframe_and_lazyframe_inputs(self) -> None:
        import polars as pl

        orders = pl.DataFrame(
            {
                "customer_id": [1, 1, 2],
                "amount": [2, 3, 4],
            }
        )
        customers = pl.LazyFrame(
            {"customer_id": [1, 2], "name": ["Ada", "Grace"]}
        )

        result = sql(
            """
            SELECT customers.name, SUM(orders.amount) AS revenue
            FROM orders
            JOIN customers USING (customer_id)
            GROUP BY customers.name
            ORDER BY customers.name
            """,
            engine="polars",
            output=False,
        )

        assert isinstance(result, pl.LazyFrame)
        assert result.collect().to_dict(as_series=False) == {
            "name": ["Ada", "Grace"],
            "revenue": [5, 4],
        }

    @pytest.mark.parametrize(
        ("join", "expected_ids"),
        [
            ("SEMI JOIN", [2]),
            ("ANTI JOIN", [1]),
        ],
    )
    def test_polars_join_syntax_registers_both_frames(
        self, join: str, expected_ids: list[int]
    ) -> None:
        import polars as pl

        orders = pl.DataFrame({"id": [1, 2]})
        customers = pl.DataFrame({"id": [2]})
        result = sql(
            f"SELECT orders.* FROM orders {join} customers USING (id)",
            engine="polars",
            output=False,
        )

        assert result.collect().get_column("id").to_list() == expected_ids

    @pytest.mark.parametrize(
        "query",
        [
            (
                "SELECT * FROM t1 JOIN (t2 JOIN t3 ON t2.id = t3.id) "
                "AS nested ON t1.id = t2.id"
            ),
            (
                "SELECT * FROM (t1 JOIN t2 ON t1.id = t2.id) "
                "AS nested JOIN t3 ON true"
            ),
        ],
    )
    def test_parenthesized_join_groups_register_all_frames(
        self, query: str
    ) -> None:
        import polars as pl

        namespace = {
            "t1": pl.DataFrame({"id": [1]}),
            "t2": pl.DataFrame({"id": [1]}),
            "t3": pl.DataFrame({"id": [1]}),
        }
        result = PolarsEngine(namespace).execute(query)

        assert result.collect().height == 1

    def test_query_without_tables(self) -> None:
        import polars as pl

        result = sql("SELECT 1 AS value", engine="polars", output=False)

        assert isinstance(result, pl.LazyFrame)
        assert result.collect().to_dict(as_series=False) == {"value": [1]}

    def test_only_registers_referenced_polars_frames(self) -> None:
        import polars as pl

        orders = pl.DataFrame({"amount": [1]})
        unused = pl.LazyFrame({"amount": [2]})
        engine = PolarsEngine(
            {"orders": orders, "unused": unused, "not_a_frame": [3]}
        )

        assert engine._referenced_frames("SELECT * FROM orders") == {
            "orders": orders
        }
        assert engine._referenced_frames("SELECT * FROM not_a_frame") == {}
        assert engine._referenced_frames("SELECT * FROM main.orders") == {}

    @pytest.mark.parametrize("relation", [None, [1, 2, 3]])
    def test_missing_or_incompatible_relation_uses_sql_error_path(
        self, relation: object
    ) -> None:
        namespace = {} if relation is None else {"orders": relation}

        with pytest.raises(MarimoSQLException) as exc_info:
            with patch(
                "marimo._sql.sql._namespace_for_polars",
                return_value=namespace,
            ):
                sql("SELECT * FROM orders", engine="polars", output=False)

        assert is_sql_parse_error(exc_info.value.__cause__)

    def test_polars_errors_use_sql_error_path(self) -> None:
        import polars as pl

        namespace = {"orders": pl.DataFrame({"amount": [1]})}

        with pytest.raises(MarimoSQLException) as exc_info:
            with patch(
                "marimo._sql.sql._namespace_for_polars",
                return_value=namespace,
            ):
                sql(
                    "SELECT missing_column FROM orders",
                    engine="polars",
                    output=False,
                )

        assert isinstance(
            exc_info.value.__cause__, pl.exceptions.ColumnNotFoundError
        )

    def test_non_sql_polars_error_is_not_classified_as_sql(self) -> None:
        import polars as pl

        with pytest.raises(pl.exceptions.ColumnNotFoundError) as exc_info:
            pl.DataFrame({"amount": [1]}).select("missing")

        assert not is_sql_parse_error(exc_info.value)

    def test_polars_backtick_quoted_identifiers(self) -> None:
        import polars as pl

        orders = pl.DataFrame({"amount": [1]})
        result = sql("SELECT * FROM `orders`", engine="polars", output=False)

        assert result.collect().to_dict(as_series=False) == {"amount": [1]}

    def test_downstream_lazy_operations_remain_lazy(self) -> None:
        import polars as pl

        orders = pl.LazyFrame({"amount": [1, 2, 3]})
        result = sql(
            "SELECT * FROM orders", engine="polars", output=False
        ).filter(pl.col("amount") > 1)

        assert isinstance(result, pl.LazyFrame)
        assert result.collect().to_dict(as_series=False) == {"amount": [2, 3]}

    def test_execute_does_not_materialize_lazy_input(self) -> None:
        import polars as pl

        def fail_if_materialized(frame: pl.DataFrame) -> pl.DataFrame:
            del frame
            raise AssertionError("lazy input was materialized")

        orders = pl.LazyFrame({"amount": [1]}).map_batches(
            fail_if_materialized
        )
        result = PolarsEngine({"orders": orders}).execute(
            "SELECT * FROM orders"
        )

        assert isinstance(result, pl.LazyFrame)
        with pytest.raises(
            AssertionError, match="lazy input was materialized"
        ):
            result.collect()

    def test_default_result_limit_stays_lazy(self) -> None:
        import polars as pl

        orders = pl.LazyFrame({"amount": range(10)})
        with patch.dict(os.environ, {"MARIMO_SQL_DEFAULT_LIMIT": "3"}):
            result = sql("SELECT * FROM orders", engine="polars", output=False)

        assert isinstance(result, pl.LazyFrame)
        assert result.collect().height == 3

    @patch("marimo._sql.sql.replace")
    def test_lazy_result_uses_lazy_table_renderer(
        self, mock_replace: MagicMock
    ) -> None:
        import polars as pl

        orders = pl.LazyFrame({"amount": [1, 2, 3]})
        result = sql("SELECT * FROM orders", engine="polars")

        assert isinstance(result, pl.LazyFrame)
        mock_replace.assert_called_once()
        rendered_table = mock_replace.call_args.args[0]
        assert rendered_table._lazy is True
        assert rendered_table._component_args["preload"] is True

    def test_constructs_a_fresh_context_for_each_query(self) -> None:
        import polars as pl

        engine = PolarsEngine({})
        with patch.object(pl, "SQLContext", wraps=pl.SQLContext) as context:
            engine.execute("SELECT 1")
            engine.execute("SELECT 2")

        assert context.call_count == 2

    @pytest.mark.parametrize(
        "output_format", ["auto", "native", "lazy-polars"]
    )
    def test_lazy_output_formats(self, output_format: str) -> None:
        import polars as pl

        with patch.object(
            PolarsEngine, "sql_output_format", return_value=output_format
        ):
            result = PolarsEngine({}).execute("SELECT 1 AS value")

        assert isinstance(result, pl.LazyFrame)

    def test_explicit_polars_output_collects(self) -> None:
        import polars as pl

        with patch.object(
            PolarsEngine, "sql_output_format", return_value="polars"
        ):
            result = PolarsEngine({}).execute("SELECT 1 AS value")

        assert isinstance(result, pl.DataFrame)

    @pytest.mark.requires("pandas", "pyarrow")
    def test_explicit_pandas_output_collects_and_converts(self) -> None:
        import pandas as pd

        with patch.object(
            PolarsEngine, "sql_output_format", return_value="pandas"
        ):
            result = PolarsEngine({}).execute("SELECT 1 AS value")

        assert isinstance(result, pd.DataFrame)

    @pytest.mark.requires("pandas", "pyarrow")
    def test_pandas_output_recovers_from_stale_pyarrow_cache(self) -> None:
        import pandas as pd
        import polars as pl

        with (
            patch.object(
                PolarsEngine, "sql_output_format", return_value="pandas"
            ),
            patch.object(
                pl.DataFrame,
                "to_pandas",
                side_effect=ModuleNotFoundError("pyarrow was loaded too late"),
            ),
        ):
            result = PolarsEngine({}).execute("SELECT 1 AS value")

        assert isinstance(result, pd.DataFrame)
        assert result.to_dict(orient="list") == {"value": [1]}
