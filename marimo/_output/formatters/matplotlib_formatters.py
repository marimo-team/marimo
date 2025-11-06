# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._config.config import Theme
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
        import json
        import struct

        from matplotlib.artist import Artist  # type: ignore
        from matplotlib.container import BarContainer  # type: ignore

        from marimo._output import formatting
        from marimo._utils.data_uri import build_data_url

        def _extract_png_dimensions(png_bytes: bytes) -> tuple[int, int]:
            """Extract width and height from PNG binary data.

            Implements the same logic as Jupyter's _pngxy function.
            """
            # Find IHDR chunk and extract dimensions
            ihdr_index = png_bytes.index(b"IHDR")
            # Next 8 bytes after IHDR are width (4 bytes) and height (4 bytes)
            width, height = struct.unpack(
                ">II", png_bytes[ihdr_index + 4 : ihdr_index + 12]
            )
            return width, height

        def mime_data_artist(artist: Artist) -> tuple[KnownMimeType, str]:
            buf = io.BytesIO()
            fig = artist.figure  # type: ignore

            # Get current DPI and double it for retina display
            original_dpi = fig.dpi
            retina_dpi = original_dpi * 2

            # Save figure at 2x DPI for retina displays
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=retina_dpi)

            # Get the PNG bytes
            png_bytes = buf.getvalue()
            plot_bytes = base64.b64encode(png_bytes)

            # Build the data URL
            mimetype: KnownMimeType = "image/png"
            data_url = build_data_url(mimetype=mimetype, data=plot_bytes)

            try:
                # Extract dimensions from the PNG
                width, height = _extract_png_dimensions(png_bytes)
                # Create a mimebundle with metadata
                # The metadata includes halved dimensions so the browser displays
                # the 2x image at 1x size for crisp retina rendering
                mimebundle = {
                    "image/png": data_url,
                    "__metadata__": {
                        "image/png": {
                            "width": width // 2,
                            "height": height // 2,
                        }
                    },
                }
                return (
                    "application/vnd.marimo+mimebundle",
                    json.dumps(mimebundle),
                )
            except (ValueError, struct.error, IndexError):
                # If dimension extraction fails, return simple image without metadata
                return (mimetype, data_url)

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

    def apply_theme(self, theme: Theme) -> None:
        import matplotlib.style  # type: ignore

        # Note: we don't set to "default", because that overwrites all
        # rcParams.
        #
        # We also don't try to restore from an rcParams file, because that
        # may overwrite other rcParams that the user set.
        #
        # This means that the style can't be switched from dark to light
        # without restarting the kernel.
        if theme == "dark":
            matplotlib.style.use("dark_background")
