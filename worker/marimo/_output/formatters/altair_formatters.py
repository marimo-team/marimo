# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.utils import flatten_string


class AltairFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "altair"

    def register(self) -> None:
        import html

        import altair  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        from marimo._output import formatting
        from marimo._plugins.ui._impl.charts.altair_transformer import (
            register_transformers,
        )

        # add marimo transformers
        register_transformers()

        @formatting.formatter(altair.TopLevelMixin)
        def _show_chart(chart: altair.Chart) -> tuple[KnownMimeType, str]:
            # TODO(akshayka): remove the `onload` hack and handle iframe
            # resizing entirely in the frontend
            # `__resizeIframe` is a script defined in the frontend that sets
            # the height of the iframe to the height of the contained document
            import altair as alt

            # If the user has not set the max_rows option, we set it to 20_000
            # since we are able to handle the larger sizes (default is 5000)
            if "max_rows" not in alt.data_transformers.options:
                alt.data_transformers.options["max_rows"] = 20_000
            return (
                "text/html",
                (
                    flatten_string(
                        f"<iframe srcdoc='{html.escape(chart.to_html())}'"
                        "frameborder='0' scrolling='auto'"
                        "style='width: 100%'"
                        "onload='__resizeIframe(this)'></iframe>"
                    )
                ),
            )
