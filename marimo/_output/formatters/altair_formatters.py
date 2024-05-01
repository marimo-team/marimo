# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import html

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.utils import flatten_string


class AltairFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "altair"

    def register(self) -> None:
        import altair  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        from marimo._output import formatting
        from marimo._plugins.ui._impl.charts.altair_transformer import (
            register_transformers,
        )

        # add marimo transformers
        register_transformers()

        @formatting.formatter(altair.TopLevelMixin)
        def _show_chart(chart: altair.Chart) -> tuple[KnownMimeType, str]:
            import altair as alt

            # If the user has not set the max_rows option, we set it to 20_000
            # since we are able to handle the larger sizes (default is 5000)
            if "max_rows" not in alt.data_transformers.options:
                alt.data_transformers.options["max_rows"] = 20_000
            return (
                "text/html",
                (
                    flatten_string(
                        h.iframe(
                            # Must be srcdoc, or if you try to use src, see
                            # https://github.com/marimo-team/marimo/issues/1279
                            # and 1279.py
                            srcdoc=html.escape(chart.to_html()),
                            onload="__resizeIframe(this)",
                            style="width: 100%",
                        )
                    )
                ),
            )
