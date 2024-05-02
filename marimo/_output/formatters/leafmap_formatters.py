# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, cast

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.utils import src_or_src_doc
from marimo._output.utils import flatten_string


class LeafmapFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "leafmap"

    def register(self) -> None:
        import leafmap  # type: ignore[import-not-found]

        from marimo._output import formatting

        @formatting.formatter(leafmap.folium.Map)
        def _show_folium_map(
            fmap: leafmap.folium.Map,
        ) -> tuple[KnownMimeType, str]:
            # leafmap.folium.Map has a _repr_html_, which we have
            # another custom formatter for, but this wraps the map in an
            # additional iframe which can cause weird layout issues
            html_content = cast(Any, fmap).to_html()
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
            # 540px is the pixel height that makes the map fit in the
            # notebook without scrolling
            height = lmap.layout.height or "540px"
            width = lmap.layout.width or "100%"
            html_content = lmap.to_html(width=width, height=height)
            return (
                "text/html",
                (
                    flatten_string(
                        h.iframe(
                            **src_or_src_doc(html_content),
                            onload="__resizeIframe(this)",
                            width="100%",
                        )
                    )
                ),
            )
