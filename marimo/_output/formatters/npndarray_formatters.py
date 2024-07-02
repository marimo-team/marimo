# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory


class NpndarrayFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "np.ndarray class type"

    def register(self) -> None:
        from marimo._output import formatting
        import numpy as np

        @formatting.formatter(np.ndarray)
        def _show_npndarray_plot(plot: np.ndarray) -> tuple[KnownMimeType, str]:
            import matplotlib.pyplot as plt

            # Ensure that the plot is shown within the notebook
            plt.show()

            return "text/plain", "Plot displayed."

