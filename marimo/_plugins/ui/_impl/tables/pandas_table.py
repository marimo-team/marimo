# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._plugins.ui._impl.tables.table_manager import (
    TableManager,
    TableManagerFactory,
)


class PandasTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "pandas"

    @staticmethod
    def create() -> type[TableManager[Any]]:
        import pandas as pd

        class PandasTableManager(TableManager[pd.DataFrame]):
            def to_csv(self) -> bytes:
                return self.data.to_csv(
                    index=False,
                ).encode("utf-8")

            def to_json(self) -> bytes:
                return self.data.to_json(orient="records").encode("utf-8")

            def select_rows(
                self, indices: list[int]
            ) -> TableManager[pd.DataFrame]:
                return PandasTableManager(self.data.iloc[indices])

            def get_row_headers(
                self,
            ) -> list[tuple[str, list[str | int | float]]]:
                return PandasTableManager._get_row_headers_for_index(
                    self.data.index
                )

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, pd.DataFrame)

            @staticmethod
            def _get_row_headers_for_index(
                index: pd.Index[Any],
            ) -> list[tuple[str, list[str | int | float]]]:
                if isinstance(index, pd.RangeIndex):
                    return []

                if isinstance(index, pd.MultiIndex):
                    # recurse
                    headers: list[Any] = []
                    for i in range(index.nlevels):
                        headers.extend(
                            PandasTableManager._get_row_headers_for_index(
                                index.get_level_values(i)
                            )
                        )
                    return headers

                # we only care about the index if it has a name
                # or if it is type 'object'
                # otherwise, it may look like meaningless number
                if isinstance(index, pd.Index):
                    dtype = str(index.dtype)
                    if (
                        index.name
                        or dtype == "object"
                        or dtype == "string"
                        or dtype == "category"
                    ):
                        name = str(index.name) if index.name else ""
                        return [(name, index.tolist())]  # type: ignore[list-item]

                return []

        return PandasTableManager
