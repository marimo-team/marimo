# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory


class MatplotlibFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "matplotlib"

    def register(self) -> None:
        import matplotlib  # type: ignore

        from marimo._runtime.context import (
            get_global_context,
        )
        from marimo._runtime.context.utils import running_in_notebook

        get_global_context().set_mpl_installed(True)
        from marimo._output import mpl  # noqa: F401

        if running_in_notebook():
            matplotlib.use("module://marimo._output.mpl")

        import base64
        import io

        from matplotlib.artist import Artist  # type: ignore
        from matplotlib.container import BarContainer  # type: ignore

        from marimo._output import formatting
        from marimo._output.utils import build_data_url

        def mime_data_artist(artist: Artist) -> tuple[KnownMimeType, str]:
            buf = io.BytesIO()
            artist.figure.savefig(buf, format="png", bbox_inches="tight")  # type: ignore
            mimetype: KnownMimeType = "image/png"
            plot_bytes = base64.b64encode(buf.getvalue())
            return (
                mimetype,
                build_data_url(mimetype=mimetype, data=plot_bytes),
            )

        # monkey-patch a _mime_ method, instead of using a formatter, because
        # we want all subclasses of Artist to inherit this renderer.
        Artist._mime_ = mime_data_artist  # type: ignore[attr-defined]

        # use an explicit formatter, no need to try to format subclasses of
        # BarContainer
        @formatting.formatter(BarContainer)
        def _show_bar_container(bc: BarContainer) -> tuple[KnownMimeType, str]:
            if len(bc.patches) > 0:
                return mime_data_artist(bc.patches[0].figure)  # type: ignore
            else:
                return ("text/plain", str(bc))
