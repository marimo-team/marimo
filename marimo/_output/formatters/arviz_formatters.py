# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory

if TYPE_CHECKING:
    import matplotlib.pyplot as plt  # type: ignore
    import numpy as np  # type: ignore
    from matplotlib.figure import Figure  # type: ignore


class ArviZFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "arviz"

    def register(self) -> None:
        import arviz as az  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore

        from marimo._output import formatting

        @formatting.formatter(az.InferenceData)  # type: ignore
        def _format_inference_data(
            data: az.InferenceData,  # type: ignore
        ) -> tuple[KnownMimeType, str]:
            return ("text/plain", str(data))

        @formatting.formatter(np.ndarray)  # type: ignore
        def _format_ndarray(
            arr: np.ndarray,  # type: ignore
        ) -> tuple[KnownMimeType, str]:
            return self.format_numpy_axes(arr)

        @formatting.formatter(dict)  # type: ignore
        def _format_dict(
            d: dict,  # type: ignore
        ) -> tuple[KnownMimeType, str]:
            return self.format_dict_with_plot(d)

        @formatting.formatter(plt.Figure)  # type: ignore
        def _format_figure(
            fig: plt.Figure,  # type: ignore
        ) -> tuple[KnownMimeType, str]:
            return self.format_figure(fig)

        @formatting.formatter(object)
        def _format_arviz_plot(
            obj: Any,
        ) -> tuple[KnownMimeType, str]:
            return self.format_arviz_plot(obj)

    @classmethod
    def format_numpy_axes(cls, arr: np.ndarray) -> tuple[KnownMimeType, str]:  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore

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
    def _contains_axes(arr: np.ndarray) -> bool:  # type: ignore
        from matplotlib.axes import Axes  # type: ignore

        """
        Check if the numpy array contains any matplotlib Axes objects.
        To ensure performance for large arrays, we limit the check to the
        first 100 items. This should be sufficient for most use cases
        while avoiding excessive computation time.
        """
        # Cap the number of items to check for performance reasons
        MAX_ITEMS_TO_CHECK = 100

        if arr.ndim == 1:
            # For 1D arrays, check up to MAX_ITEMS_TO_CHECK items
            return any(
                isinstance(item, Axes) for item in arr[:MAX_ITEMS_TO_CHECK]
            )
        elif arr.ndim == 2:
            # For 2D arrays, check up to MAX_ITEMS_TO_CHECK items in total
            items_checked = 0
            for row in arr:
                for item in row:
                    if isinstance(item, Axes):
                        return True
                    items_checked += 1
                    if items_checked >= MAX_ITEMS_TO_CHECK:
                        return False
        return False

    @staticmethod
    def _get_axes_info(fig: Figure) -> str:  # type: ignore
        axes_info = []
        for _, ax in enumerate(fig.axes):
            bbox = ax.get_position()
            axes_info.append(
                f"Axes({bbox.x0:.3f},{bbox.y0:.3f};"
                f"{bbox.width:.3f}x{bbox.height:.3f})"
            )
        return "\n".join(axes_info)

    @staticmethod
    def _get_plot_html(fig: Figure) -> str:  # type: ignore
        import base64
        from io import BytesIO

        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")  # Retain default
        data = base64.b64encode(buf.getbuffer()).decode("ascii")
        return f"<img src='data:image/png;base64,{data}'/>"

    @classmethod
    def format_dict_with_plot(cls, d: dict) -> tuple[KnownMimeType, str]:  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore

        str_repr = str(d)
        fig = plt.gcf()
        if fig.get_axes():
            axes_info = cls._get_axes_info(fig)
            plot_html = cls._get_plot_html(fig)
            plt.close(fig)
            combined_html = (
                f"<pre>{str_repr}\n{axes_info}</pre><br>" f"{plot_html}"
            )
            return ("text/html", combined_html)
        return ("text/plain", str_repr)

    @classmethod
    def format_figure(cls, fig: Figure) -> tuple[KnownMimeType, str]:  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore

        axes_info = cls._get_axes_info(fig)
        plot_html = cls._get_plot_html(fig)
        plt.close(fig)
        combined_html = f"<pre>{axes_info}</pre><br>{plot_html}"
        return ("text/html", combined_html)

    @classmethod
    def format_arviz_plot(cls, result: Any) -> tuple[KnownMimeType, str]:
        import matplotlib.pyplot as plt  # type: ignore
        import numpy as np  # type: ignore
        from matplotlib.figure import Figure  # type: ignore

        if isinstance(result, Figure):
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
