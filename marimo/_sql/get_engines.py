# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional, cast

from marimo import _loggers
from marimo._config.config import DatasourcesConfig
from marimo._config.manager import get_default_config_manager
from marimo._data.models import Database, DataSourceConnection
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._sql.engines.clickhouse import (
    ClickhouseEmbedded,
    ClickhouseServer,
)
from marimo._sql.engines.duckdb import (
    INTERNAL_DUCKDB_ENGINE,
    DuckDBEngine,
)
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.engines.types import SQLEngine
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()


def get_engines_from_variables(
    variables: list[tuple[VariableName, object]],
) -> list[tuple[VariableName, SQLEngine]]:
    engines: list[tuple[VariableName, SQLEngine]] = []

    supported_engines: list[type[SQLEngine]] = [
        SQLAlchemyEngine,
        DuckDBEngine,
        ClickhouseEmbedded,
        ClickhouseServer,
    ]

    for variable_name, value in variables:
        for sql_engine in supported_engines:
            if sql_engine.is_compatible(value):
                engines.append(
                    (
                        variable_name,
                        sql_engine(
                            cast(Any, value), engine_name=variable_name
                        ),
                    )
                )

    return engines


def engine_to_data_source_connection(
    variable_name: VariableName,
    engine: SQLEngine,
) -> DataSourceConnection:
    databases: list[Database] = []
    default_database: Optional[str] = None
    default_schema: Optional[str] = None

    config = get_datasources_config()
    auto_discover_schemas = config.get("auto_discover_schemas", True)
    auto_discover_tables = config.get("auto_discover_tables", "auto")
    auto_discover_columns = config.get("auto_discover_columns", False)

    if isinstance(engine, SQLAlchemyEngine):
        default_database = engine.default_database
        default_schema = engine.default_schema
        databases = engine.get_databases(
            include_schemas=auto_discover_schemas,
            include_tables=auto_discover_tables,
            include_table_details=auto_discover_columns,
        )
    elif isinstance(engine, DuckDBEngine):
        databases = engine.get_databases()
        default_database = engine.get_current_database()
        default_schema = engine.get_current_schema()
    elif isinstance(engine, ClickhouseEmbedded):
        pass
    elif isinstance(engine, ClickhouseServer):
        default_database = engine.get_default_database()
        databases = engine.get_databases(
            include_tables=auto_discover_tables,
            include_table_details=auto_discover_columns,
        )
    else:
        LOGGER.warning(
            f"Unsupported engine type: {type(engine)}. Unable to get databases for {variable_name}."
        )

    display_name = (
        f"{engine.dialect} ({variable_name})"
        if variable_name != INTERNAL_DUCKDB_ENGINE
        else f"{engine.dialect} (In-Memory)"
    )

    return DataSourceConnection(
        source=engine.source,
        dialect=engine.dialect,
        name=variable_name,
        display_name=display_name,
        databases=databases,
        default_database=default_database,
        default_schema=default_schema,
    )


def get_datasources_config() -> DatasourcesConfig:
    try:
        return get_context().marimo_config.get("datasources", {})
    except ContextNotInitializedError:
        pass
    except Exception as e:
        LOGGER.warning(
            f"Failed to get datasources config from context: {e}. Falling back to default config."
        )

    try:
        return (
            get_default_config_manager(current_path=None)
            .get_config()
            .get("datasources", {})
        )
    except Exception as e:
        LOGGER.warning(
            f"Failed to get datasources config from default config: {e}. Returning empty config."
        )
        return {}
