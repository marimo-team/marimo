# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.utils import src_or_src_doc
from marimo._output.md import md
from marimo._output.utils import flatten_string


class LeafmapFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "leafmap"

    def register(self) -> None:
        # Different backends
        # plotly is handled by PlotlyFormatter
        import leafmap.foliumap as leafmap_folium  # type: ignore[import-untyped]
        import leafmap.leafmap as leafmap  # type: ignore[import-untyped]

        from marimo._output import formatting

        @formatting.formatter(leafmap_folium.Map)
        def _show_folium_map(
            fmap: leafmap_folium.Map,
        ) -> tuple[KnownMimeType, str]:
            # leafmap.folium.Map has a _repr_html_, which we have
            # another custom formatter for, but this wraps the map in an
            # additional iframe which can cause weird layout issues
            html_content = fmap.to_html()
            return (
                "text/html",
                flatten_string(
                    h.iframe(
                        **src_or_src_doc(html_content),
                        onload="__resizeIframe(this)",
                        style="min-height: 540px",
                        width="100%",
                    )
                ),
            )

        @formatting.formatter(leafmap.Map)
        def _show_map(
            lmap: leafmap.Map,
        ) -> tuple[KnownMimeType, str]:
            del lmap
            return (
                "text/html",
                md(
                    """
                    leafmap.Map objects are not supported in marimo.
                    Please change the backend to `folium` or `plotly`.

                    ```python
                    import leafmap.foliumap as leafmap
                    # or
                    import leafmap.plotlymap as leafmap
                    ```
                    """
                )
                .callout()
                .text,
            )

        # Kepler is an optional dependency
        # so we don't want this to fail if it's not installed
        try:
            import leafmap.kepler as leafmap_kepler  # type: ignore[import-untyped]

            @formatting.formatter(leafmap_kepler.Map)
            def _show_kepler_map(
                kmap: leafmap_kepler.Map,
            ) -> tuple[KnownMimeType, str]:
                contents = kmap.to_html() or ""
                return (
                    "text/html",
                    flatten_string(
                        h.iframe(
                            **src_or_src_doc(contents),
                            onload="__resizeIframe(this)",
                            style="min-height: 540px",
                            width="100%",
                        )
                    ),
                )

        except (ImportError, ModuleNotFoundError):
            pass
