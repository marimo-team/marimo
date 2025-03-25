# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

# from marimo._data.models import Database


@dataclass
class InferenceConfig(ABC):
    auto_discover_schemas: bool
    auto_discover_tables: bool
    auto_discover_columns: bool


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

    @abstractmethod
    def execute(self, query: str) -> Any:
        """Execute a SQL query and return a dataframe."""
        pass

    @staticmethod
    @abstractmethod
    def is_compatible(var: Any) -> bool:
        """Check if a variable is a compatible engine."""
        pass

    # @abstractmethod
    # def get_inference_config(self) -> InferenceConfig:
    #     """Return the inference config for the engine."""
    #     pass

    # @abstractmethod
    # def get_databases(
    #     self,
    #     *,
    #     include_schemas: Union[bool, Literal["auto"]],
    #     include_tables: Union[bool, Literal["auto"]],
    #     include_table_details: Union[bool, Literal["auto"]],
    # ) -> list[Database]:
    #     """Return the databases for the engine."""
    #     pass
