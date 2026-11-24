# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._sql.engines.polars import PolarsEngine
from marimo._sql.error_utils import MarimoSQLException, is_sql_parse_error
from marimo._sql.sql import sql

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.requires("polars", "sqlglot")
class TestPolarsEngine:
    """Test Polars SQL execution, reference discovery, and output formats."""

    def test_rejects_polars_one(self) -> None:
        """Require the supported major version even in existing environments."""
        with patch(
            "marimo._dependencies.dependencies.Dependency.get_version",
            return_value="1.37.1",
        ):
            with pytest.raises(RuntimeError, match=r"expected >=2\.0\.0"):
                PolarsEngine({}).execute("SELECT 1")

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            (
                (
                    "SELECT amount FROM orders WHERE EXISTS "
                    "(SELECT 1 FROM customers WHERE customers.id = orders.id) "
                    "ORDER BY amount"
                ),
                {"amount": [20]},
            ),
            (
                (
                    "SELECT id, amount FROM orders QUALIFY "
                    "ROW_NUMBER() OVER (PARTITION BY id ORDER BY amount DESC) = 1 "
                    "ORDER BY id"
                ),
                {"id": [1, 2], "amount": [30, 20]},
            ),
            (
                (
                    "SELECT id FROM orders UNION BY NAME "
                    "SELECT id FROM customers ORDER BY id"
                ),
                {"id": [1, 2]},
            ),
            (
                (
                    "SELECT amount, SUM(amount) OVER (ORDER BY amount "
                    "ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS running "
                    "FROM orders ORDER BY amount"
                ),
                {"amount": [10, 20, 30], "running": [10, 30, 50]},
            ),
        ],
    )
    def test_polars_two_sql_dialect(
        self, query: str, expected: dict[str, list[int]]
    ) -> None:
        """Pass advanced SQL through to Polars without DuckDB transpilation."""
        import polars as pl

        engine = PolarsEngine(
            {
                "orders": pl.LazyFrame(
                    {"id": [1, 2, 1], "amount": [10, 20, 30]}
                ),
                "customers": pl.DataFrame({"id": [2]}),
            }
        )
        result = engine.execute(query)

        assert isinstance(result, pl.LazyFrame)
        assert result.collect().to_dict(as_series=False) == expected

    def test_read_csv_table_function(self, tmp_path: Path) -> None:
        """Allow native table functions without treating them as Python refs."""
        import polars as pl

        path = tmp_path / "orders.csv"
        pl.DataFrame({"amount": [1, 2]}).write_csv(path)
        result = PolarsEngine({}).execute(
            f"SELECT SUM(amount) AS total FROM read_csv('{path.as_posix()}')"
        )

        assert result.collect().to_dict(as_series=False) == {"total": [3]}

    def test_sql_numeric_semantics(self) -> None:
        """Preserve Polars 2 exact literals and truncating SQL remainder."""
        result = PolarsEngine({}).execute(
            "SELECT 1.25 AS exact, -5 % 2 AS remainder"
        )

        assert result.collect().to_dict(as_series=False) == {
            "exact": [Decimal("1.25")],
            "remainder": [-1],
        }

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            (
                (
                    "WITH RECURSIVE nums(n) AS (SELECT n FROM seed UNION ALL "
                    "SELECT n + 1 FROM nums WHERE n < 3) "
                    "SELECT n FROM nums ORDER BY n"
                ),
                {"n": [1, 2, 3]},
            ),
            (
                (
                    "SELECT seed.n, other.n AS matched FROM seed ASOF JOIN other "
                    "MATCH_CONDITION (seed.n >= other.n) ORDER BY seed.n"
                ),
                {"n": [1], "matched": [1]},
            ),
        ],
    )
    def test_polars_two_one_sql_dialect(
        self, query: str, expected: dict[str, list[int]]
    ) -> None:
        """Support newer syntax when the installed Polars version provides it."""
        import polars as pl

        from marimo._dependencies.dependencies import DependencyManager

        if not DependencyManager.polars.has_at_version(min_version="2.1.0"):
            pytest.skip("Requires Polars 2.1")
        result = PolarsEngine(
            {
                "seed": pl.DataFrame({"n": [1]}),
                "other": pl.DataFrame({"n": [1]}),
            }
        ).execute(query)

        assert result.collect().to_dict(as_series=False) == expected

    @pytest.mark.parametrize(
        ("query", "error"),
        [
            ("SELECT * FROM missing", "SQLInterfaceError"),
            ("SELECT missing FROM orders", "ColumnNotFoundError"),
        ],
    )
    def test_lazy_sql_errors_are_deferred(
        self, query: str, error: str
    ) -> None:
        """Preserve Polars 2 error timing without resolving lazy plans early."""
        import polars as pl

        with patch(
            "marimo._sql.sql._namespace_for_polars",
            return_value={"orders": pl.LazyFrame({"amount": [1]})},
        ):
            result = sql(query, engine="polars", output=False)

        assert isinstance(result, pl.LazyFrame)
        with pytest.raises(getattr(pl.exceptions, error)):
            result.collect()

    @pytest.mark.parametrize("quote", ["", '"', "`"])
    @pytest.mark.parametrize("cte_name", ["orders", "Orders"])
    def test_cte_names_match_polars_case_insensitive_resolution(
        self, quote: str, cte_name: str
    ) -> None:
        """Resolve CTE names using Polars 2 case-insensitive semantics."""
        import polars as pl

        engine = PolarsEngine({"orders": pl.DataFrame({"amount": [99]})})
        result = engine.execute(
            f"WITH {quote}{cte_name}{quote} AS (SELECT 1 AS amount) "
            f"SELECT * FROM {quote}orders{quote}"
        )

        assert result.collect().to_dict(as_series=False) == {"amount": [1]}

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
        """Report missing tables immediately when eager output is selected."""
        namespace = {} if relation is None else {"orders": relation}

        with pytest.raises(MarimoSQLException) as exc_info:
            with (
                patch(
                    "marimo._sql.sql._namespace_for_polars",
                    return_value=namespace,
                ),
                patch.object(
                    PolarsEngine, "sql_output_format", return_value="polars"
                ),
            ):
                sql("SELECT * FROM orders", engine="polars", output=False)

        assert is_sql_parse_error(exc_info.value.__cause__)

    def test_polars_errors_use_sql_error_path(self) -> None:
        """Wrap eager SQL planning errors with their query context."""
        import polars as pl

        namespace = {"orders": pl.DataFrame({"amount": [1]})}

        with pytest.raises(MarimoSQLException) as exc_info:
            with (
                patch(
                    "marimo._sql.sql._namespace_for_polars",
                    return_value=namespace,
                ),
                patch.object(
                    PolarsEngine, "sql_output_format", return_value="polars"
                ),
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
        """Apply the default limit without executing the Polars query."""
        import polars as pl

        orders = pl.LazyFrame({"amount": range(10)})
        with (
            patch.dict(os.environ, {"MARIMO_SQL_DEFAULT_LIMIT": "3"}),
            patch.object(
                pl.LazyFrame,
                "collect",
                side_effect=AssertionError("lazy result was materialized"),
            ),
        ):
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
