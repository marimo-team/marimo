# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import QueryEngine, register_engine
from marimo._sql.utils import raise_df_import_error

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence


class DBAPIConnection(Protocol):
    def cursor(self) -> Any: ...

    def commit(self) -> None: ...


@register_engine
class DBAPIEngine(QueryEngine[DBAPIConnection]):
    """DB-API 2.0 (PEP 249) engine."""

    @property
    def source(self) -> str:
        return "dbapi"

    @property
    def dialect(self) -> str:
        # Try to get dialect from connection
        try:
            return str(self._connection.dialect)  # type: ignore[attr-defined]
        except AttributeError:
            return "sql"

    def execute(
        self, query: str, parameters: Optional[Sequence[Any]] = None
    ) -> Any:
        sql_output_format = self.sql_output_format()

        cursor = self._connection.cursor()
        should_close = True
        try:
            cursor.execute(query, parameters or ())

            if sql_output_format == "native":
                should_close = False
                return cursor

            rows = cursor.fetchall() if cursor.description else None

            try:
                self._connection.commit()
            except Exception:
                LOGGER.info("Unable to commit transaction", exc_info=True)

            if rows is None:
                return None

            # Get column names from cursor description
            if cursor.description:
                columns = [col[0] for col in cursor.description]
            else:
                columns = []

            def convert_to_polars(rows: list[tuple[Any, ...]]) -> pl.DataFrame:
                import polars as pl

                data: dict[str, list[Any]] = {col: [] for col in columns}
                for row in rows:
                    for i, col in enumerate(columns):
                        data[col].append(row[i])
                return pl.DataFrame(data)

            if sql_output_format == "polars":
                return convert_to_polars(rows)

            if sql_output_format == "lazy-polars":
                return convert_to_polars(rows).lazy()

            if sql_output_format == "pandas":
                import pandas as pd

                return pd.DataFrame(rows, columns=columns)

            # Auto
            if DependencyManager.polars.has():
                import polars as pl

                try:
                    return convert_to_polars(rows)
                except (
                    pl.exceptions.PanicException,
                    pl.exceptions.ComputeError,
                ):
                    LOGGER.info(
                        "Failed to convert to polars, falling back to pandas"
                    )

            if DependencyManager.pandas.has():
                import pandas as pd

                try:
                    return pd.DataFrame(rows, columns=columns)
                except Exception as e:
                    LOGGER.warning("Failed to convert dataframe", exc_info=e)
                    return None

            raise_df_import_error("polars[pyarrow]")
        finally:
            if should_close:
                cursor.close()

    @staticmethod
    def is_compatible(var: Any) -> bool:
        """Check if a variable is a DB-API 2.0 compatible connection.

        A DB-API 2.0 connection must have:
        - cursor() method
        - commit() method
        - rollback() method
        - close() method
        """
        try:
            required_methods = ["cursor", "commit", "rollback", "close"]
            has_required_methods = all(
                callable(getattr(var, method, None))
                for method in required_methods
            )

            if not has_required_methods:
                return False

            cursor = var.cursor()
            cursor_methods = ["execute", "fetchall"]
            has_cursor_methods = all(
                callable(getattr(cursor, method, None))
                for method in cursor_methods
            )

            return has_required_methods and has_cursor_methods

        except Exception:
            return False
