# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeAlias

from marimo._ast.sql_visitor import POLARS_ENGINE, POLARS_SQL_MIN_VERSION
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import QueryEngine
from marimo._sql.error_utils import MarimoSQLException
from marimo._utils.log_never import log_never

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

PolarsSQLResult: TypeAlias = "pl.DataFrame | pl.LazyFrame | pd.DataFrame"


class PolarsEngine(QueryEngine[Mapping[str, object]]):
    """Run SQL with Polars against the Polars frames in a namespace."""

    def __init__(self, namespace: Mapping[str, object]) -> None:
        super().__init__(namespace)

    @property
    def source(self) -> str:
        return "polars"

    @property
    def dialect(self) -> str:
        return "polars"

    @staticmethod
    def is_compatible(var: object) -> bool:
        return isinstance(var, str) and var == POLARS_ENGINE

    def execute(self, query: str) -> PolarsSQLResult:
        DependencyManager.polars.require_at_version(
            "to execute sql with Polars", min_version=POLARS_SQL_MIN_VERSION
        )
        import polars as pl

        # Registration is zero-copy, so registering every frame is cheaper
        # than parsing the query to pick the referenced ones.
        frames = {
            name: value
            for name, value in self._connection.items()
            if isinstance(value, (pl.DataFrame, pl.LazyFrame))
        }
        try:
            result = pl.SQLContext(frames=frames).execute(query, eager=False)
            # Unknown tables and columns only surface once the plan resolves.
            result.collect_schema()
            return self._to_output(result)
        except pl.exceptions.PolarsError as e:
            raise MarimoSQLException(
                message=str(e), sql_statement=query
            ) from e

    def _to_output(self, result: pl.LazyFrame) -> PolarsSQLResult:
        sql_output_format = self.sql_output_format()
        match sql_output_format:
            case "native" | "lazy-polars":
                return result
            case "auto" | "polars":
                return result.collect()
            case "pandas":
                return result.collect().to_pandas()
            case _:
                log_never(sql_output_format)
                return result.collect()
