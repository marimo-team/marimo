# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from markdown import Extension, Markdown, treeprocessors

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


# Adapted from https://github.com/squidfunk/mkdocs-material/discussions/3660#discussioncomment-6725823  # noqa: E501


class ExternalLinksTreeProcessor(treeprocessors.Treeprocessor):
    """
    Adds target="_blank" and rel="noopener" to external links.
    """

    def run(self, root: Element) -> None:
        for element in root.iter():
            if element.tag != "a":
                continue

            href = element.get("href", "")

            parsed_url = urlparse(href)

            if parsed_url.scheme in ["http", "https"]:
                element.set("target", "_blank")
                element.set("rel", "noopener")


class ExternalLinksExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.treeprocessors.register(
            ExternalLinksTreeProcessor(md),
            "external_links",
            -1000,
        )
