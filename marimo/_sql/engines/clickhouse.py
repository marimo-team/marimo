# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataTableType,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import (
    InferenceConfig,
    SQLEngine,
    register_engine,
)
from marimo._sql.utils import sql_type_to_data_type
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from chdb.state.sqlitelike import Connection as ChdbConnection  # type: ignore # noqa: I001
    from clickhouse_connect.driver.client import Client as ClickhouseClient  # type: ignore


PANDAS_REQUIRED_MSG = (
    "Pandas is required to convert Clickhouse results to a DataFrame"
)


@register_engine
class ClickhouseEmbedded(SQLEngine):
    """Use chdb to connect to an embedded Clickhouse"""

    def __init__(
        self,
        connection: Optional[ChdbConnection] = None,
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
        DependencyManager.pandas.require(PANDAS_REQUIRED_MSG)

        import chdb  # type: ignore
        import pandas as pd

        # TODO: this will fail weirdly / silently when there is another connection

        if self._cursor:
            try:
                self._cursor.execute(query)
                rows = self._cursor.fetchall()
                return pd.DataFrame(rows)
            except Exception:
                LOGGER.exception("Failed to execute query")
                return None

        try:
            result = chdb.query(query, "Dataframe")
        except Exception:
            LOGGER.exception("Failed to execute query")
            return None
        if isinstance(result, pd.DataFrame):
            return result
        return None

    # TODO: Implement the following functionalities
    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        _, _, _ = include_schemas, include_tables, include_table_details
        return []

    def get_tables_in_schema(
        self, *, database: str, schema: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema."""
        _, _, _ = database, schema, include_table_details
        return []

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""
        _, _, _ = table_name, schema_name, database_name
        return None

    def get_default_database(self) -> Optional[str]:
        return None

    def get_default_schema(self) -> Optional[str]:
        return None

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.chdb.imported():
            return False

        from chdb.state.sqlitelike import Connection

        return isinstance(var, Connection)

    @property
    def inference_config(self) -> InferenceConfig:
        # Because chdb is a local connection, we can auto-discover everything
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables=True,
            auto_discover_columns=True,
        )


@register_engine
class ClickhouseServer(SQLEngine):
    """Use clickhouse.connect to connect to a Clickhouse server"""

    def __init__(
        self,
        connection: Optional[ClickhouseClient] = None,
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
        if self._connection is None:
            return None

        # clickhouse connect supports pandas and arrow format
        DependencyManager.pandas.require(PANDAS_REQUIRED_MSG)

        import pandas as pd

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

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas=False,
            auto_discover_tables="auto",
            auto_discover_columns="auto",
        )

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        """
        Get all databases from the ClickHouse server.

        Args:
            include_schemas: Whether to include schema information. (ignored for ClickHouse)
            include_tables: Whether to include table information.
            include_table_details: Whether to include detailed table metadata.

        Returns:
            List of Database objects representing the server's databases.
        """
        _ = include_schemas  # ClickHouse doesn't have schemas

        if self._connection is None:
            return []

        if not DependencyManager.pandas.has():
            LOGGER.info("Unable to get databases without pandas")
            return []

        import pandas as pd

        databases: list[Database] = []
        try:
            db_df = self._connection.query_df("SHOW DATABASES")
        except Exception:
            LOGGER.warning("Failed to get databases", exc_info=True)
            return databases

        if not isinstance(db_df, pd.DataFrame):
            LOGGER.warning(
                f"Failed to convert database result to DataFrame, result: {str(db_df)}"
            )
            return databases

        include_table_details = self._resolve_should_auto_discover(
            include_table_details
        )

        # Assume the first column contains the database names.
        if db_df.empty:
            return databases

        db_names = db_df[db_df.columns[0]].tolist()
        for db in db_names:
            db_name = cast(str, db)
            if (
                # Skip meta db's, TODO: do this for other engines too.
                db_name.lower() in ["system", "information_schema"]
                or not include_tables
            ):
                tables = []
            else:
                tables = self.get_tables_in_schema(
                    schema="",
                    database=db,
                    include_table_details=include_table_details,
                )
            databases.append(
                Database(
                    name=db,
                    dialect=self.dialect,
                    engine=self._engine_name,
                    # ClickHouse does not have schemas
                    schemas=[Schema(name="", tables=tables)],
                )
            )
        return databases

    def _resolve_should_auto_discover(
        self, value: Union[bool, Literal["auto"]]
    ) -> bool:
        if value == "auto":
            # TODO: Smartly determine if we should auto-discover
            return False
        return value

    def get_tables_in_schema(
        self,
        *,
        schema: str,
        database: str,
        include_table_details: bool,
    ) -> list[DataTable]:
        """
        Return all tables in a given ClickHouse database.

        Args:
            schema: The schema name. (ignored for ClickHouse)
            database: The name of the database.
            include_table_details: Whether to retrieve detailed table metadata.

        Returns:
            List of DataTable objects.
        """
        _ = schema  # ClickHouse does not have schemas
        if self._connection is None:
            return []

        tables: list[DataTable] = []
        try:
            query = f"SHOW TABLES FROM {database}"
            table_df = self._connection.query_df(query)
        except Exception:
            LOGGER.warning(
                f"Failed to get tables from database {database}", exc_info=True
            )
            return tables

        import pandas as pd

        if not isinstance(table_df, pd.DataFrame):
            LOGGER.warning("Failed to convert table result to DataFrame")
            return tables

        if table_df.empty:
            return tables

        # Assume the first column contains table names.
        table_names = table_df[table_df.columns[0]].tolist()
        for table in table_names:
            if include_table_details:
                table_detail = self.get_table_details(
                    table_name=table, schema_name="", database_name=database
                )
                if table_detail is not None:
                    tables.append(table_detail)
            else:
                tables.append(
                    DataTable(
                        source_type="connection",
                        source=self.dialect,
                        name=table,
                        num_rows=None,
                        num_columns=None,
                        variable_name=None,
                        engine=self._engine_name,
                        type="table",
                        columns=[],
                        primary_keys=[],
                        indexes=[],
                    )
                )
        return tables

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """
        Get detailed metadata for a given table in a database.

        Args:
            database_name: The database name.
            schema_name: The schema name. (ignored for ClickHouse)
            table_name: The table name.

        Returns:
            A DataTable object with detailed metadata,
            or None if the table cannot be described.
        """
        _ = schema_name
        if self._connection is None:
            return None

        try:
            query = f"SELECT * FROM system.tables WHERE name = '{table_name}' AND database = '{database_name}'"
            table_df = self._connection.query_df(query)
        except Exception:
            LOGGER.warning(
                f"Failed to get table details for {table_name} in database {database_name}",
                exc_info=True,
            )
            return None

        import pandas as pd

        if not isinstance(table_df, pd.DataFrame):
            LOGGER.warning(
                "Failed to convert table description result to DataFrame"
            )
            return None

        primary_keys: list[str] = []
        total_rows = None
        table_type: DataTableType = "table"
        try:
            primary_key = table_df["primary_key"].iloc[0]
            if primary_key:
                primary_keys.append(primary_key)

            engine = table_df["engine"].iloc[0]
            if engine and str(engine).lower() == "view":
                table_type = "view"  # TODO: We should add support for general table types

            total_rows = table_df["total_rows"].iloc[0]
        except Exception:
            pass

        try:
            query = f"DESCRIBE TABLE {database_name}.{table_name}"
            desc_df = self._connection.query_df(query)
        except Exception:
            LOGGER.warning(
                f"Failed to get table description for {table_name} in database {database_name}",
                exc_info=True,
            )
            return None

        if not isinstance(desc_df, pd.DataFrame):
            LOGGER.warning(
                "Failed to convert table description result to DataFrame"
            )
            return None

        if desc_df.empty:
            return None

        cols: list[DataTableColumn] = []
        for _, row in desc_df.iterrows():
            col_name = row.get("name")
            if col_name is None:
                continue
            col_type_str = str(row.get("type", "string"))
            data_type = sql_type_to_data_type(col_type_str)
            cols.append(
                DataTableColumn(
                    name=str(col_name),
                    type=data_type,
                    external_type=col_type_str,
                    sample_values=[],
                )
            )

        try:
            total_rows = int(total_rows) if total_rows is not None else None
        except Exception:
            total_rows = None

        return DataTable(
            source_type="connection",
            source=self.dialect,
            name=table_name,
            num_rows=total_rows,
            num_columns=len(cols),
            variable_name=None,
            engine=self._engine_name,
            type=table_type,
            columns=cols,
            primary_keys=primary_keys,
            indexes=[],  # TODO
        )

    def get_default_database(self) -> Optional[str]:
        if self._connection is None:
            return None

        if not DependencyManager.pandas.has():
            return None

        try:
            query = "SELECT currentDatabase()"
            db_name = self._connection.query_df(query)
        except Exception:
            LOGGER.warning("Failed to get current database", exc_info=True)
            return None

        import pandas as pd

        if not isinstance(db_name, pd.DataFrame):
            return None

        if db_name.empty:
            return None
        return str(db_name.iloc[0, 0])

    def get_default_schema(self) -> Optional[str]:
        # ClickHouse does not have schemas
        return None
