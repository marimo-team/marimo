# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Literal, Optional, TypeVar, Union

from marimo._config.config import SqlOutputType
from marimo._data.models import Database, DataTable
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
    runtime_context_installed,
)
from marimo._types.ids import VariableName

ENGINE_REGISTRY: list[type[BaseEngine[Any]]] = []
NO_SCHEMA_NAME = ""


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


CONN = TypeVar("CONN")


class BaseEngine(ABC, Generic[CONN]):
    """Base fields for all engines and catalogs."""

    def __init__(
        self, connection: CONN, engine_name: Optional[VariableName] = None
    ) -> None:
        self._connection: CONN = connection
        self._engine_name: Optional[VariableName] = engine_name

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

    @staticmethod
    @abstractmethod
    def is_compatible(var: Any) -> bool:
        """Check if a variable is a compatible engine."""
        pass


T = TypeVar("T", bound=BaseEngine[Any])


def register_engine(cls: type[T]) -> type[T]:
    ENGINE_REGISTRY.append(cls)
    return cls


class EngineCatalog(BaseEngine[CONN], ABC):
    """Protocol for querying the catalog of an engine."""

    @property
    @abstractmethod
    def inference_config(self) -> InferenceConfig:
        """Return the inference config for the engine."""
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


class QueryEngine(BaseEngine[CONN], ABC):
    """Protocol for SQL engines that can execute queries."""

    @abstractmethod
    def execute(self, query: str) -> Any:
        """Execute a SQL query and return a dataframe."""
        pass

    def sql_output_format(self) -> SqlOutputType:
        if runtime_context_installed():
            try:
                ctx = get_context()
                return _validate_sql_output_format(ctx.app_config.sql_output)
            except ContextNotInitializedError:
                return "auto"
        return "auto"


class SQLConnection(EngineCatalog[CONN], QueryEngine[CONN]):
    """Combines the catalog and query interfaces for an SQL engine."""

    pass
