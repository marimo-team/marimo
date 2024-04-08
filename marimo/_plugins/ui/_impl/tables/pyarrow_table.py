# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Any, Union

from marimo._plugins.ui._impl.tables.table_manager import (
    TableManager,
    TableManagerFactory,
)


class PyArrowTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "pyarrow"

    @staticmethod
    def create() -> type[TableManager[Any]]:
        import pyarrow as pa  # type: ignore

        class PyArrowTableManager(
            TableManager[Union[pa.Table, pa.RecordBatch]]
        ):
            def to_csv(self) -> bytes:
                import pyarrow.csv as csv  # type: ignore

                buffer = io.BytesIO()
                csv.write_csv(self.data, buffer)
                return buffer.getvalue()

            def to_json(self) -> bytes:
                # Arrow does not have a built-in JSON writer
                return (
                    self.data.to_pandas()
                    .to_json(orient="records")
                    .encode("utf-8")
                )

            def select_rows(self, indices: list[int]) -> PyArrowTableManager:
                if not indices:
                    return PyArrowTableManager(
                        pa.Table.from_pylist([], schema=self.data.schema)
                    )
                return PyArrowTableManager(self.data.take(indices))

            def get_row_headers(
                self,
            ) -> list[tuple[str, list[str | int | float]]]:
                return []

            @staticmethod
            def is_type(value: Any) -> bool:
                import pyarrow as pa  # type: ignore

                return isinstance(value, pa.Table) or isinstance(
                    value, pa.RecordBatch
                )

        return PyArrowTableManager
