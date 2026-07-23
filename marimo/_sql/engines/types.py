# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from marimo._config.config import SqlOutputType
from marimo._data.models import Database, DataTable, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.parse import (
    format_query_with_globals,
    replace_brackets_with_quotes,
)
from marimo._sql.utils import (
    get_configured_sql_output_format,
    is_cheap_dialect,
    is_query_empty,
    strip_explain_from_error_message,
    wrap_query_with_explain,
)
from marimo._types.ids import VariableName

NO_SCHEMA_NAME = ""

# Probe name that no real DB connection defines.
_MISSING_ATTRIBUTE_PROBE = "_marimo_does_not_exist_"
_MISSING_ATTRIBUTE_SENTINEL = object()


def fabricates_attributes(var: Any) -> bool:
    """Return True if `var` invents attributes via a catch-all `__getattr__`.

    Used to reject objects (e.g. ignite metrics) that pass every getattr-based
    duck-type check. Prefer this over `getattr_static` so connection proxies
    that forward `__getattr__` still work.

    See https://github.com/marimo-team/marimo/issues/10213.
    """
    try:
        return (
            getattr(var, _MISSING_ATTRIBUTE_PROBE, _MISSING_ATTRIBUTE_SENTINEL)
            is not _MISSING_ATTRIBUTE_SENTINEL
        )
    except Exception:
        # Not a usable connection if __getattr__ raises unexpectedly.
        return True


@dataclass
class InferenceConfig(ABC):
    auto_discover_schemas: bool | Literal["auto"]
    auto_discover_tables: bool | Literal["auto"]
    auto_discover_columns: bool | Literal["auto"]


def default_inference_config() -> InferenceConfig:
    """Default discovery config shared by general-purpose SQL engines.

    Expensive backends can have a large number of schemas and tables, so we
    gate discovery behind the `"auto"` heuristic.
    """
    return InferenceConfig(
        auto_discover_schemas="auto",
        auto_discover_tables="auto",
        auto_discover_columns=False,
    )


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
        self, connection: CONN, engine_name: VariableName | None = None
    ) -> None:
        self._connection: CONN = connection
        self._engine_name: VariableName | None = engine_name

    @property
    @abstractmethod
    def source(self) -> str:
        """Return the source of the engine. Usually the name of the library used to connect to the database."""

    @property
    @abstractmethod
    def dialect(self) -> str:
        """Return the sqlglot dialect for this engine."""

    @staticmethod
    @abstractmethod
    def is_compatible(var: Any) -> bool:
        """Check if a variable is a compatible engine."""


T = TypeVar("T", bound=BaseEngine[Any])


class EngineCatalog(BaseEngine[CONN], ABC):
    """Protocol for querying the catalog of an engine."""

    @property
    @abstractmethod
    def inference_config(self) -> InferenceConfig:
        """Return the inference config for the engine."""

    @abstractmethod
    def get_default_database(self) -> str | None:
        """Return the default database for the engine."""

    @abstractmethod
    def get_default_schema(self) -> str | None:
        """Return the default schema for the engine."""

    @abstractmethod
    def get_databases(
        self,
        *,
        include_schemas: bool | Literal["auto"],
        include_tables: bool | Literal["auto"],
        include_table_details: bool | Literal["auto"],
    ) -> list[Database]:
        """Return the databases for the engine."""

    @abstractmethod
    def get_schemas(
        self,
        *,
        database: str | None,
        include_tables: bool,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[Schema]:
        """Return schemas within a database.

        Empty `schema_path` lists the database's top-level schemas; a non-empty
        path lists the child schemas at that path. Only nested-namespace engines
        (e.g. Iceberg) honour a non-empty path; flat engines return `[]` for one.
        """

    @abstractmethod
    def get_tables_in_schema(
        self,
        *,
        schema: str,
        database: str,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[DataTable]:
        """Return all tables in a schema.

        Nested-namespace engines locate the schema via `schema_path` (relative
        to `database`); flat engines use `schema` and ignore it.
        """

    @abstractmethod
    def get_table_details(
        self,
        *,
        table_name: str,
        schema_name: str,
        database_name: str,
        schema_path: list[str] | None = None,
    ) -> DataTable | None:
        """Get a single table from the engine.

        Nested-namespace engines locate the table via `schema_path` (relative to
        `database_name`); flat engines ignore it.
        """

    def _resolve_should_auto_discover(
        self, value: bool | Literal["auto"]
    ) -> bool:
        """Resolve a discovery flag, deferring `"auto"` to engine policy."""
        if value == "auto":
            return self._is_cheap_discovery()
        return value

    def _is_cheap_discovery(self) -> bool:
        """Whether discovery is cheap enough to run when a flag is `"auto"`.

        Defaults to a dialect-based heuristic; engines with different cost
        profiles (e.g. always-cheap local catalogs, or expensive remote
        warehouses) should override this.
        """
        return is_cheap_dialect(self.dialect)


class QueryEngine(BaseEngine[CONN], ABC):
    """Protocol for SQL engines that can execute queries."""

    @abstractmethod
    def execute(self, query: str) -> Any:
        """Execute a SQL query and return a dataframe."""

    def sql_output_format(self) -> SqlOutputType:
        configured_output_format = get_configured_sql_output_format()
        return _validate_sql_output_format(configured_output_format)

    def execute_in_explain_mode(
        self, query: str, globals_dict: dict[str, Any] | None = None
    ) -> tuple[Any, str | None]:
        """Execute a query in explain mode. Returns a tuple of the result and an error if there is one."""

        if globals_dict is None:
            globals_dict = {}

        explain_query = wrap_query_with_explain(query)
        if self.dialect == "duckdb":
            explain_query = format_query_with_globals(
                explain_query, globals_dict
            )
        else:
            explain_query, _ = replace_brackets_with_quotes(explain_query)

        try:
            return self.execute(explain_query), None
        except Exception as e:
            if is_query_empty(query):
                return None, None
            return None, strip_explain_from_error_message(str(e))


class SQLConnection(EngineCatalog[CONN], QueryEngine[CONN]):
    """Combines the catalog and query interfaces for an SQL engine."""


SQLConnectionType = EngineCatalog[Any] | QueryEngine[Any]
