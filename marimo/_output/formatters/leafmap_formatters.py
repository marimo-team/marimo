# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import marimo._output.data.data as mo_data
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.utils import flatten_string


class LeafmapFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "leafmap"

    def register(self) -> None:
        import leafmap  # type: ignore[import-not-found]

        from marimo._output import formatting

        @formatting.formatter(leafmap.Map)
        def _show_dataframe(lmap: leafmap.Map) -> tuple[str, str]:
            # 540px is the pixel height that makes the map fit in the
            # notebook without scrolling
            html = mo_data.html(lmap.to_html(height="540px"))
            return (
                "text/html",
                (
                    flatten_string(
                        f"<iframe src='{html.url}'"
                        "frameborder='0' scrolling='auto'"
                        "style='width: 100%'"
                        "onload='__resizeIframe(this)'></iframe>"
                    )
                ),
            )
