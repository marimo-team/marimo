# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.utils import flatten_string


class PandasFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "pandas"

    def register(self) -> None:
        import pandas as pd  # type:ignore[import]

        from marimo._output import formatting

        @formatting.formatter(pd.DataFrame)
        def _show_dataframe(df: pd.DataFrame) -> tuple[str, str]:
            # Flatten the HTML to avoid indentation issues when
            # interpolating into other HTML/Markdown with an f-string
            return (
                "text/html",
                flatten_string(df.to_html()),
            )

        @formatting.formatter(pd.Series)
        def _show_series(series: pd.Series) -> tuple[str, str]:
            return (
                "text/html",
                flatten_string(series.to_frame().to_html()),
            )
