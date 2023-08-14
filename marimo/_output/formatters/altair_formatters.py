# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.utils import flatten_string


class AltairFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "altair"

    def register(self) -> None:
        import html

        import altair  # type:ignore[import]

        from marimo._output import formatting

        @formatting.formatter(altair.TopLevelMixin)
        def _show_chart(chart: altair.Chart) -> tuple[str, str]:
            # TODO(akshayka): remove the `onload` hack and handle iframe
            # resizing entirely in the frontend
            # `__resizeIframe` is a script defined in the frontend that sets
            # the height of the iframe to the height of the contained document
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
