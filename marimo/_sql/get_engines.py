# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, cast

from marimo import _loggers
from marimo._data.models import Database, DataSourceConnection
from marimo._sql.engines import (
    INTERNAL_DUCKDB_ENGINE,
    DuckDBEngine,
    SQLAlchemyEngine,
)
from marimo._sql.types import SQLEngine
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()


def get_engines_from_variables(
    variables: list[tuple[VariableName, object]],
) -> list[tuple[VariableName, SQLEngine]]:
    engines: list[tuple[VariableName, SQLEngine]] = []
    for variable_name, value in variables:
        if SQLAlchemyEngine.is_compatible(value):
            engines.append(
                (
                    variable_name,
                    SQLAlchemyEngine(
                        cast(Any, value), engine_name=variable_name
                    ),
                )
            )
        elif DuckDBEngine.is_compatible(value):
            engines.append(
                (
                    variable_name,
                    DuckDBEngine(cast(Any, value), engine_name=variable_name),
                )
            )

    return engines


def engine_to_data_source_connection(
    variable_name: VariableName,
    engine: SQLEngine,
) -> DataSourceConnection:
    databases: list[Database] = []
    if isinstance(engine, SQLAlchemyEngine):
        databases = engine.get_databases(
            include_schemas=True,
            include_tables=True,
            include_table_details=False,
        )
    elif isinstance(engine, DuckDBEngine):
        databases = engine.get_databases()
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
    )
