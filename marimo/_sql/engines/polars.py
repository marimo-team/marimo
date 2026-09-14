# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._ast.sql_visitor import find_polars_sql_refs
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import QueryEngine
from marimo._utils.assert_never import log_never

if TYPE_CHECKING:
    from collections.abc import Mapping


class PolarsEngine(QueryEngine[dict[str, Any]]):
    """Execute SQL against Polars frames in a Python namespace."""

    def __init__(self, namespace: Mapping[str, Any]) -> None:
        super().__init__(dict(namespace))

    @property
    def source(self) -> str:
        return "polars"

    @property
    def dialect(self) -> str:
        return "polars"

    @staticmethod
    def is_compatible(var: Any) -> bool:
        return isinstance(var, str) and var == "polars"

    def _referenced_frames(self, query: str) -> dict[str, Any]:
        import polars as pl

        frames: dict[str, Any] = {}
        for ref in find_polars_sql_refs(query):
            value = self._connection.get(ref.table)
            if isinstance(value, (pl.DataFrame, pl.LazyFrame)):
                frames[ref.table] = value
        return frames

    @staticmethod
    def _to_pandas(frame: Any) -> Any:
        try:
            return frame.to_pandas()
        except ModuleNotFoundError as error:
            # In WASM, PyArrow can be installed after Polars was imported when
            # a user switches the live SQL output setting to pandas. Polars
            # caches optional-dependency availability at import time, so use
            # the now-installed PyArrow directly in that narrow case.
            if "pyarrow" not in str(error).casefold():
                raise
            import pyarrow as pa

            return pa.Table.from_pydict(
                frame.to_dict(as_series=False)
            ).to_pandas()

    def execute(self, query: str) -> Any:
        DependencyManager.polars.require("to execute SQL with Polars")
        DependencyManager.sqlglot.require("to find tables referenced by SQL")

        import polars as pl

        context = pl.SQLContext(frames=self._referenced_frames(query))
        result = context.execute(query, eager=False)
        sql_output_format = self.sql_output_format()

        match sql_output_format:
            case "auto" | "native" | "lazy-polars":
                return result
            case "polars":
                return result.collect()
            case "pandas":
                return self._to_pandas(result.collect())
            case _:
                log_never(sql_output_format)
