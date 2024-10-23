# Copyright 2024 Marimo. All rights reserved.
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

from markdown import Extension, Markdown, treeprocessors  # type: ignore

# Adapted from https://github.com/squidfunk/mkdocs-material/discussions/3660#discussioncomment-6725823  # noqa: E501


class ExternalLinksTreeProcessor(treeprocessors.Treeprocessor):  # type: ignore[misc]  # noqa: E501
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


class ExternalLinksExtension(Extension):  # type: ignore[misc]
    def extendMarkdown(self, md: Markdown) -> None:
        md.treeprocessors.register(
            ExternalLinksTreeProcessor(md),
            "external_links",
            -1000,
        )
