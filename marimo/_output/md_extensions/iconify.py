# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from markdown import Extension, Markdown, inlinepatterns

if TYPE_CHECKING:
    import re


class IconifyPattern(inlinepatterns.InlineProcessor):
    """
    Converts ::icon-set:icon-name:: to an iconify-icon element.
    """

    def __init__(self, pattern: str, md: Markdown) -> None:
        super().__init__(pattern, md)

    def handleMatch(  # type: ignore
        self, m: re.Match[str], data: str
    ) -> tuple[Element, int, int]:
        del data
        icon_name = m.group(1)
        return (
            Element("iconify-icon", {"icon": icon_name, "inline": ""}),
            m.start(0),
            m.end(0),
        )


class IconifyExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        # Add IconifyPattern with high priority (200) to
        # handle it before other inline patterns
        md.inlinePatterns.register(
            IconifyPattern(r"::([a-zA-Z0-9-]+:[a-zA-Z0-9-]+)::", md),
            "iconify",
            200,
        )
