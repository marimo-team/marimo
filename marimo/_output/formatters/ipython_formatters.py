# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, Callable

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory


class IPythonFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "IPython"

    def register(self) -> Callable[[], None]:
        import IPython.display  # type:ignore

        from marimo._output import formatting
        from marimo._runtime.output import _output

        old_display = IPython.display.display
        # monkey patch IPython.display.display, which imperatively writes
        # outputs to the frontend

        @functools.wraps(old_display)
        def display(*objs: Any, **kwargs: Any) -> None:
            # IPython.display.display returns a DisplayHandle, which
            # can be used to update the displayed object. We don't support
            # that yet ...

            # If clear is True, clear the output before displaying
            if kwargs.pop("clear", False):
                _output.clear()

            raw = kwargs.pop("raw", False)
            for value in objs:
                # raw means it's a mimebundle, with the key (mime) and value (raw data)
                if raw and isinstance(value, dict):
                    _output.append(ReprMimeBundle(value))
                else:
                    _output.append(value)

        IPython.display.display = display
        # Patching display_functions handles display_markdown, display_x, etc.
        try:
            IPython.core.display_functions.display = display  # type: ignore
        except AttributeError:
            pass

        def unpatch() -> None:
            IPython.display.display = old_display  # type: ignore
            try:
                IPython.core.display_functions.display = old_display  # type: ignore
            except AttributeError:
                pass

        @formatting.formatter(
            IPython.display.HTML  # type:ignore
        )
        def _format_html(
            html: IPython.display.HTML,  # type:ignore
        ) -> tuple[KnownMimeType, str]:
            if html.url is not None:
                # TODO(akshayka): resize iframe not working
                data = h.iframe(
                    src=html.url,
                    onload="__resizeIframe(this)",
                    width="100%",
                )
            else:
                data = str(html._repr_html_())  # type: ignore

            return ("text/html", data)

        return unpatch


@dataclass
class ReprMimeBundle:
    data: dict[str, Any]

    def _repr_mimebundle_(
        self,
        include: Any = None,
        exclude: Any = None,
    ) -> dict[str, Any]:
        del include, exclude
        return self.data
