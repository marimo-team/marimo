# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from marimo._convert.markdown.flavor.base import (
    MarkdownFlavor,
    MarkdownFlavorName,
)
from marimo._convert.markdown.flavor.myst import MystMarkdownFlavor
from marimo._convert.markdown.flavor.pymdown import PymdownMarkdownFlavor
from marimo._convert.markdown.flavor.qmd import QmdMarkdownFlavor

if TYPE_CHECKING:
    from collections.abc import Mapping

_PYMDOWN_MARKDOWN = PymdownMarkdownFlavor()
_QMD_MARKDOWN = QmdMarkdownFlavor()
_MYST_MARKDOWN = MystMarkdownFlavor()
_MARKDOWN_FLAVORS: Mapping[MarkdownFlavorName, MarkdownFlavor] = (
    MappingProxyType(
        {
            _PYMDOWN_MARKDOWN.name: _PYMDOWN_MARKDOWN,
            _QMD_MARKDOWN.name: _QMD_MARKDOWN,
            _MYST_MARKDOWN.name: _MYST_MARKDOWN,
        }
    )
)
_MARKDOWN_FLAVORS_BY_EXTENSION: Mapping[str, MarkdownFlavor] = (
    MappingProxyType({".qmd": _QMD_MARKDOWN})
)


def default_markdown_flavor() -> MarkdownFlavor:
    return _PYMDOWN_MARKDOWN


def markdown_flavor_from_filename(filename: str) -> MarkdownFlavor:
    """Infer the export flavor from a filename extension."""
    return _MARKDOWN_FLAVORS_BY_EXTENSION.get(
        Path(filename).suffix, default_markdown_flavor()
    )


def normalize_markdown_flavor(
    flavor: MarkdownFlavor | MarkdownFlavorName | None,
    *,
    filename: str,
) -> MarkdownFlavor:
    """Resolve an optional flavor name or instance to a concrete flavor."""
    if flavor is None:
        return markdown_flavor_from_filename(filename)
    if isinstance(flavor, MarkdownFlavor):
        return flavor
    try:
        return _MARKDOWN_FLAVORS[flavor]
    except KeyError as error:
        raise ValueError(f"Unsupported markdown flavor: {flavor!r}") from error


__all__ = [
    "default_markdown_flavor",
    "markdown_flavor_from_filename",
    "normalize_markdown_flavor",
]
