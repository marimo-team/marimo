# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

from marimo._config.config import SqlOutputType
from marimo._data.models import Database, DataTable
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
    runtime_context_installed,
)

ENGINE_REGISTRY: list[type[SQLEngine]] = []
NO_SCHEMA_NAME = ""


def register_engine(cls: type[SQLEngine]) -> type[SQLEngine]:
    ENGINE_REGISTRY.append(cls)
    return cls


@dataclass
class InferenceConfig(ABC):
    auto_discover_schemas: Union[bool, Literal["auto"]]
    auto_discover_tables: Union[bool, Literal["auto"]]
    auto_discover_columns: Union[bool, Literal["auto"]]


def _validate_sql_output_format(sql_output: SqlOutputType) -> SqlOutputType:
    if sql_output in ("lazy-polars", "polars"):
        DependencyManager.polars.require(
            why="to display SQL results as a Polars DataFrame"
        )
    elif sql_output == "pandas":
        DependencyManager.pandas.require(
            why="to display SQL results as a Pandas DataFrame"
        )
    return sql_output


class SQLEngine(ABC):
    """Protocol for SQL engines that can execute queries."""

    def sql_output_format(self) -> SqlOutputType:
        if runtime_context_installed():
            try:
                ctx = get_context()
                return _validate_sql_output_format(ctx.app_config.sql_output)
            except ContextNotInitializedError:
                return "auto"
        return "auto"

    @abstractmethod
    def __init__(
        self, connection: Any, engine_name: Optional[str] = None
    ) -> None:
        pass

    @property
    @abstractmethod
    def source(self) -> str:
        """Return the source of the engine. Usually the name of the library used to connect to the database."""
        pass

    @property
    @abstractmethod
    def dialect(self) -> str:
        """Return the sqlglot dialect for this engine."""
        pass

    @property
    @abstractmethod
    def inference_config(self) -> InferenceConfig:
        """Return the inference config for the engine."""
        pass

    @abstractmethod
    def execute(self, query: str) -> Any:
        """Execute a SQL query and return a dataframe."""
        pass

    @staticmethod
    @abstractmethod
    def is_compatible(var: Any) -> bool:
        """Check if a variable is a compatible engine."""
        pass

    @abstractmethod
    def get_default_database(self) -> Optional[str]:
        """Return the default database for the engine."""
        pass

    @abstractmethod
    def get_default_schema(self) -> Optional[str]:
        """Return the default schema for the engine."""
        pass

    @abstractmethod
    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        """Return the databases for the engine."""
        pass

    @abstractmethod
    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema."""
        pass

    @abstractmethod
    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""
        pass
