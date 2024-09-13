from __future__ import annotations

from typing import Any, Union
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
import matplotlib.pyplot as plt
import numpy as np

class ArviZFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "arviz"

    def register(self) -> None:
        import arviz as az
        from marimo._output import formatting

        @formatting.formatter(az.InferenceData)
        def _format_inference_data(
            data: az.InferenceData,
        ) -> tuple[KnownMimeType, str]:
            return ("text/plain", str(data))

        @formatting.formatter(np.ndarray)
        def _format_ndarray(
            arr: np.ndarray,
        ) -> tuple[KnownMimeType, str]:
            return self.format_numpy_axes(arr)

        @formatting.formatter(dict)
        def _format_dict(
            d: dict,
        ) -> tuple[KnownMimeType, str]:
            return self.format_dict_with_plot(d)

        @formatting.formatter(plt.Figure)
        def _format_figure(
            fig: plt.Figure,
        ) -> tuple[KnownMimeType, str]:
            return self.format_figure(fig)

        @formatting.formatter(object)
        def _format_arviz_plot(
            obj: Any,
        ) -> tuple[KnownMimeType, str]:
            return self.format_arviz_plot(obj)

    @classmethod
    def format_numpy_axes(cls, arr: np.ndarray) -> tuple[KnownMimeType, str]:
        # Check if array contains axes (to render plots) or not
        if arr.dtype == object and cls._contains_axes(arr):
            fig = plt.gcf()
            if fig.get_axes():  # Only process if there are axes to show
                axes_info = cls._get_axes_info(fig)
                plot_html = cls._get_plot_html(fig)
                plt.close(fig)  # Safely close the figure after saving
                combined_html = f"<pre>{axes_info}</pre><br>{plot_html}"
                return ("text/html", combined_html)
        # Fallback to plain text if no axes or plot are present
        return ("text/plain", str(arr))

    @staticmethod
    def _contains_axes(arr: np.ndarray) -> bool:
        if arr.ndim == 1:
            return any(isinstance(item, plt.Axes) for item in arr)
        elif arr.ndim == 2:
            return any(isinstance(item, plt.Axes) for row in arr for item in row)
        return False

    