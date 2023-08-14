# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatters.formatter_factory import FormatterFactory


class SeabornFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "seaborn"

    def register(self) -> None:
        from typing import Any, cast

        import seaborn  # type:ignore[import]

        from marimo._output import formatting
        from marimo._output.mime import MIME

        def _show_ax_or_subplots(grid: Any) -> tuple[str, str]:
            # Seaborn uses matplotlib under the hood: figures and axes are
            # instances of matplotlib's Artist class. (We've monkey pathed
            # `Artist` to implement the MIME protocol.)
            if hasattr(grid, "figure"):
                return cast(MIME, grid.figure)._mime_()
            if hasattr(grid, "ax"):
                return cast(MIME, grid.ax)._mime_()
            elif hasattr(grid, "axes"):
                return cast(MIME, grid.axes.flatten()[0])._mime_()
            else:
                return ("text/plain", str(grid))

        @formatting.formatter(seaborn.axisgrid.FacetGrid)
        def _show_facet_grid(
            fg: seaborn.axisgrid.FacetGrid,
        ) -> tuple[str, str]:
            return _show_ax_or_subplots(fg)

        @formatting.formatter(seaborn.axisgrid.PairGrid)
        def _show_pair_grid(pg: seaborn.axisgrid.PairGrid) -> tuple[str, str]:
            return _show_ax_or_subplots(pg)

        @formatting.formatter(seaborn.axisgrid.JointGrid)
        def _show_joint_grid(
            jg: seaborn.axisgrid.JointGrid,
        ) -> tuple[str, str]:
            return _show_ax_or_subplots(jg)
