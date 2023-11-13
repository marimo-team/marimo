# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.utils import flatten_string


class PandasFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "pandas"

    def register(self) -> None:
        import pandas as pd

        pd.set_option("display.max_rows", 10)
        pd.set_option("display.max_columns", 20)

        from marimo._output import formatting

        @formatting.formatter(pd.DataFrame)
        def _show_dataframe(df: pd.DataFrame) -> tuple[str, str]:
            max_rows = pd.get_option("display.max_rows")
            max_columns = pd.get_option("display.max_columns")
            # Flatten the HTML to avoid indentation issues when
            # interpolating into other HTML/Markdown with an f-string
            return (
                "text/html",
                flatten_string(
                    df.to_html(max_rows=max_rows, max_cols=max_columns)
                ),
            )

        @formatting.formatter(pd.Series)
        def _show_series(series: pd.Series[Any]) -> tuple[str, str]:
            max_rows = pd.get_option("display.max_rows")
            return (
                "text/html",
                flatten_string(series.to_frame().to_html(max_rows=max_rows)),
            )
