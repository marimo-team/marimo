# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import QueryEngine
from marimo._sql.utils import raise_df_import_error

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence


class DBAPIConnection(Protocol):
    def cursor(self) -> Any: ...

    def commit(self) -> None: ...


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

    @staticmethod
    def is_dbapi_cursor(obj: Any) -> bool:
        """
        Return True if obj looks like a DB-API 2.0 cursor.
        """
        try:
            # Required methods
            has_execute = callable(getattr(obj, "execute", None))
            # has_executemany = callable(getattr(obj, "executemany", None))

            # At least one fetch method
            fetch_methods = ("fetchone", "fetchmany", "fetchall")
            has_fetch = any(
                callable(getattr(obj, m, None)) for m in fetch_methods
            )

            # Required attributes (description may be None after DML, but must exist)
            has_description_attr = hasattr(obj, "description")
            has_rowcount = hasattr(obj, "rowcount")

            return (
                has_execute
                and has_fetch
                and has_description_attr
                and has_rowcount
            )
        except Exception:
            return False

    @staticmethod
    def get_cursor_metadata(cursor: Any) -> dict[str, Any]:
        """
        Extract standard DB-API 2.0 cursor metadata.
        """
        try:
            meta: dict[str, Any] = {
                "result_type": f"{type(cursor)}",
            }

            # Column info
            desc = getattr(cursor, "description", None)
            if desc:
                cols: list[dict[str, Optional[Any]]] = []
                for col in desc:
                    # description tuple: (name, type_code, display_size, internal_size, precision, scale, null_ok)
                    name = col[0]
                    type_code = col[1] if len(col) > 1 else None
                    display_size = col[2] if len(col) > 2 else None
                    internal_size = col[3] if len(col) > 3 else None
                    precision = col[4] if len(col) > 4 else None
                    scale = col[5] if len(col) > 5 else None
                    null_ok = col[6] if len(col) > 6 else None

                    cols.append(
                        {
                            "name": name,
                            "type_code": type_code,
                            "display_size": display_size,
                            "internal_size": internal_size,
                            "precision": precision,
                            "scale": scale,
                            "null_ok": null_ok,
                        }
                    )
                meta["columns"] = cols
            else:
                meta["columns"] = None

            if hasattr(cursor, "rowcount"):
                meta["rowcount"] = cursor.rowcount

            # lastrowid (optional in many drivers)
            if hasattr(cursor, "lastrowid"):
                meta["lastrowid"] = cursor.lastrowid

            # SQL type guess
            # rowcount == -1 usually means SELECT (or DDL), >=0 means DML
            rc = getattr(cursor, "rowcount", None)
            if rc is None:
                sql_type = "Unknown"
            elif rc == -1:
                sql_type = "Query/DDL"
            else:
                sql_type = "Query/DML"
            meta["sql_statement_type"] = sql_type

            return meta

        except Exception:
            LOGGER.warning("Failed to extract cursor metadata", exc_info=True)
            return {
                "result_type": f"{type(cursor)}",
                "error": "Failed to extract metadata",
            }
