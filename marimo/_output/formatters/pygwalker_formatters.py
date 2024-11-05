# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._runtime.context.utils import running_in_notebook


class PygWalkerFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "pygwalker"

    def register(self) -> None:
        if running_in_notebook():
            # monkey-patch pygwalker.walk to work in marimo;
            # older versions of marimo may not have api.marimo, and not sure
            # about pygwalker's API stability, so use a coarse try/except
            try:
                import pygwalker  # type: ignore
                from pygwalker.api.marimo import walk  # type: ignore

                pygwalker.walk = walk  # type: ignore
            except Exception:
                pass
