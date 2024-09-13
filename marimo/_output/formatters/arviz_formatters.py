from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory


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

    @staticmethod
    def _get_axes_info(fig: plt.Figure) -> str:
        axes_info = []
        for i, ax in enumerate(fig.axes):
            bbox = ax.get_position()
            axes_info.append(f"Axes({bbox.x0:.3f},{bbox.y0:.3f};{bbox.width:.3f}x{bbox.height:.3f})")
        return "\n".join(axes_info)

    @staticmethod
    def _get_plot_html(fig: plt.Figure) -> str:
        import base64
        from io import BytesIO

        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")  # Retain default settings
        data = base64.b64encode(buf.getbuffer()).decode("ascii")
        return f"<img src='data:image/png;base64,{data}'/>"

    @classmethod
    def format_dict_with_plot(cls, d: dict) -> tuple[KnownMimeType, str]:
        str_repr = str(d)
        fig = plt.gcf()
        if fig.get_axes():
            axes_info = cls._get_axes_info(fig)
            plot_html = cls._get_plot_html(fig)
            plt.close(fig)
            combined_html = f"<pre>{str_repr}\n{axes_info}</pre><br>{plot_html}"
            return ("text/html", combined_html)
        return ("text/plain", str_repr)

    @classmethod
    def format_figure(cls, fig: plt.Figure) -> tuple[KnownMimeType, str]:
        axes_info = cls._get_axes_info(fig)
        plot_html = cls._get_plot_html(fig)
        plt.close(fig)
        combined_html = f"<pre>{axes_info}</pre><br>{plot_html}"
        return ("text/html", combined_html)

    @classmethod
    def format_arviz_plot(cls, result: Any) -> tuple[KnownMimeType, str]:
        if isinstance(result, plt.Figure):
            return cls.format_figure(result)
        elif isinstance(result, np.ndarray):
            return cls.format_numpy_axes(result)
        elif isinstance(result, dict):
            return cls.format_dict_with_plot(result)
        else:
            fig = plt.gcf()
            if fig.get_axes():
                return cls.format_figure(fig)
            return ("text/plain", str(result))
