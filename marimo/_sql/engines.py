from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.types import SQLEngine

if TYPE_CHECKING:
    import duckdb
    from sqlalchemy import Engine


def raise_df_import_error(pkg: str) -> None:
    raise ModuleNotFoundError(
        "pandas or polars is required to execute sql. "
        + "You can install them with 'pip install pandas polars'",
        name=pkg,
    )


class DuckDBEngine(SQLEngine):
    """DuckDB SQL engine."""

    def __init__(
        self, connection: Optional[duckdb.DuckDBPyConnection]
    ) -> None:
        self._connection = connection

    @property
    def source(self) -> str:
        return "duckdb"

    @property
    def dialect(self) -> str:
        return "duckdb"

    def execute(self, query: str) -> Any:
        import duckdb

        if self._connection is None:
            relation = duckdb.sql(query)
        else:
            relation = self._connection.sql(query)

        if DependencyManager.polars.has():
            return relation.pl()
        elif DependencyManager.pandas.has():
            return relation.df()
        else:
            raise_df_import_error("polars")

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.duckdb.imported():
            return False

        import duckdb

        return isinstance(var, duckdb.DuckDBPyConnection)


class SQLAlchemyEngine(SQLEngine):
    """SQLAlchemy engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @property
    def source(self) -> str:
        return "sqlalchemy"

    @property
    def dialect(self) -> str:
        return str(self._engine.dialect.name)

    def execute(self, query: str) -> Any:
        # Can't use polars.imported() because this is the first time we
        # might come across polars.
        if DependencyManager.polars.has():
            import pandas as pd
            import polars as pl

            # SQLAlchemy doesn't support polars directly, so we go through pandas
            df = pd.read_sql_query(query, self._engine)
            return pl.from_pandas(df)
        elif DependencyManager.pandas.has():
            import pandas as pd

            return pd.read_sql_query(query, self._engine)
        else:
            raise_df_import_error("pandas")

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.sqlalchemy.imported():
            return False

        from sqlalchemy.engine import Engine

        return isinstance(var, Engine)
