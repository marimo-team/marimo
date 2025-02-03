# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from marimo._data.models import DataTable


class SQLEngine(ABC):
    """Protocol for SQL engines that can execute queries."""

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

    @abstractmethod
    def get_tables(self) -> list[DataTable]:
        """Get data tables from a variable."""
        pass
