# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output import builder
from marimo._output.formatters.formatter_factory import FormatterFactory


class IPythonFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "IPython"

    def register(self) -> None:
        import IPython.display

        from marimo._output import formatting
        from marimo._runtime.output import _output

        # monkey patch IPython.display.display, which imperatively writes
        # outputs to the frontend
        def display(*objs: Any, **kwargs: Any) -> None:
            """Patch of IPython.display.display to work in marimo
            """
            # IPython.display.display returns a DisplayHandle, which
            # can be used to update the displayed object. We don't support
            # that yet ...
            if kwargs.pop("clear", False):
                _output.clear()
            for value in objs:
                _output.append(value)

        IPython.display.display = display

        @formatting.formatter(IPython.display.HTML)
        def _format_html(
            html: IPython.display.HTML,
        ) -> tuple[KnownMimeType, str]:
            if html.url is not None:
                # TODO(akshayka): resize iframe not working
                data = builder.h.iframe(
                    src=html.url,
                    width="100%",
                    onload="__resizeIframe(this)",
                    scrolling="auto",
                    frameborder="0",
                )
            else:
                data = str(html._repr_html_())  # type: ignore

            return ("text/html", data)
