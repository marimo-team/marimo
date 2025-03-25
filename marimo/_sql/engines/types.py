# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

from marimo._data.models import Database, DataTable

ENGINE_REGISTRY: list[type[SQLEngine]] = []


def register_engine(cls: type[SQLEngine]) -> type[SQLEngine]:
    ENGINE_REGISTRY.append(cls)
    return cls


@dataclass
class InferenceConfig(ABC):
    auto_discover_schemas: Union[bool | Literal["auto"]]
    auto_discover_tables: Union[bool | Literal["auto"]]
    auto_discover_columns: Union[bool | Literal["auto"]]


class SQLEngine(ABC):
    """Protocol for SQL engines that can execute queries."""

    @abstractmethod
    def __init__(self, connection: Any, engine_name: str) -> None:
        pass

    @property
    @abstractmethod
    def source(self) -> str:
        """Return the source of the engine."""
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
