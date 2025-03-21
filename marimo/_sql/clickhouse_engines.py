# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

import clickhouse_connect.driver
import clickhouse_connect.driver.client

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.types import SQLEngine
from marimo._sql.utils import raise_df_import_error
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import chdb
    import clickhouse_connect

INTERNAL_CLICKHOUSE_ENGINE = cast(VariableName, "__marimo_clickhouse")


class ClickhouseEmbedded(SQLEngine):
    """Use chdb to connect to an embedded Clickhouse"""

    def __init__(
        self,
        connection: Optional[chdb.state.sqlitelike.Connection] = None,
        engine_name: Optional[VariableName] = None,
    ) -> None:
        self._connection = connection
        self._engine_name = engine_name
        self._cursor = None if connection is None else connection.cursor()

    @property
    def source(self) -> str:
        return "clickhouse"

    @property
    def dialect(self) -> str:
        return "clickhouse"

    def execute(self, query: str) -> Any:
        # chdb currently only supports pandas
        if not DependencyManager.pandas.has():
            raise_df_import_error("pandas")

        import chdb
        import pandas as pd

        # TODO: this will fail weirdly / silently when there is another connection

        if self._cursor:
            self._cursor.execute(query)
            rows = self._cursor.fetchall()
            return pd.DataFrame(rows)

        try:
            result = chdb.query(query, "Dataframe")
        except Exception:
            LOGGER.exception("Failed to execute query")
            return None
        if isinstance(result, pd.DataFrame):
            return result
        return None

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.chdb.imported():
            return False

        from chdb.state.sqlitelike import Connection

        return isinstance(var, Connection)


class ClickhouseServer(SQLEngine):
    """Use clickhouse.connect to connect to a Clickhouse server"""

    def __init__(
        self,
        connection: Optional[clickhouse_connect.driver.client.Client] = None,
        engine_name: Optional[VariableName] = None,
    ) -> None:
        self._connection = connection
        self._engine_name = engine_name

    @property
    def source(self) -> str:
        return "clickhouse"

    @property
    def dialect(self) -> str:
        return "clickhouse"

    def execute(self, query: str) -> Any:
        # clickhouse connect supports pandas and arrow format
        if not DependencyManager.pandas.has():
            raise_df_import_error("pandas")

        import pandas as pd

        # queries will not work unless they are stripped and comments are removed
        # TODO: remove comments
        query = query.strip()

        # If wrapped with try/catch, an error may not be caught
        result = self._connection.query_df(query)

        if isinstance(result, pd.DataFrame):
            return result
        return None

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.clickhouse_connect.imported():
            return False

        from clickhouse_connect.driver.client import Client

        return isinstance(var, Client)
