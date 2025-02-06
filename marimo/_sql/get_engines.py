# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, cast

from marimo._data.models import DataSourceConnection
from marimo._sql.engines import DuckDBEngine, SQLAlchemyEngine
from marimo._sql.types import SQLEngine


def get_engines_from_variables(
    variables: list[tuple[str, object]],
) -> list[tuple[str, SQLEngine]]:
    engines: list[tuple[str, SQLEngine]] = []
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
    variable_name: str,
    engine: SQLEngine,
) -> DataSourceConnection:
    return DataSourceConnection(
        source=engine.source,
        dialect=engine.dialect,
        name=variable_name,
        display_name=f"{engine.dialect} ({variable_name})",
    )
