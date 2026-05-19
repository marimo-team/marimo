# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from marimo._convert.markdown.flavor.base import (
    MarkdownFlavor,
    MarkdownFlavorName,
)
from marimo._convert.markdown.flavor.mystmd import MystmdMarkdownFlavor
from marimo._convert.markdown.flavor.pymdown import PymdownMarkdownFlavor
from marimo._convert.markdown.flavor.qmd import QmdMarkdownFlavor

if TYPE_CHECKING:
    from collections.abc import Mapping

_PYMDOWN_MARKDOWN = PymdownMarkdownFlavor()
_QMD_MARKDOWN = QmdMarkdownFlavor()
_MYSTMD_MARKDOWN = MystmdMarkdownFlavor()
_MARKDOWN_FLAVORS: Mapping[MarkdownFlavorName, MarkdownFlavor] = (
    MappingProxyType(
        {
            _PYMDOWN_MARKDOWN.name: _PYMDOWN_MARKDOWN,
            _QMD_MARKDOWN.name: _QMD_MARKDOWN,
            _MYSTMD_MARKDOWN.name: _MYSTMD_MARKDOWN,
        }
    )
)
_MARKDOWN_FLAVORS_BY_EXTENSION: Mapping[str, MarkdownFlavor] = (
    MappingProxyType({".myst.md": _MYSTMD_MARKDOWN, ".qmd": _QMD_MARKDOWN})
)
_MARKDOWN_OUTPUT_EXTENSIONS: Mapping[MarkdownFlavorName, str] = (
    MappingProxyType(
        {
            "pymdown": "md",
            "qmd": "qmd",
            "mystmd": "myst.md",
        }
    )
)
_MARKDOWN_FILENAME_SUFFIXES = (
    ".myst.md",
    ".markdown",
    ".qmd",
    ".md",
)


def default_markdown_flavor() -> MarkdownFlavor:
    return _PYMDOWN_MARKDOWN


def markdown_flavor_from_filename(filename: str) -> MarkdownFlavor:
    """Infer the export flavor from a filename extension."""
    suffixes = Path(filename).suffixes
    for suffix in ("".join(suffixes[-2:]), suffixes[-1] if suffixes else ""):
        if suffix in _MARKDOWN_FLAVORS_BY_EXTENSION:
            return _MARKDOWN_FLAVORS_BY_EXTENSION[suffix]
    return default_markdown_flavor()


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


def _markdown_output_extension(
    flavor: MarkdownFlavor | MarkdownFlavorName,
) -> str:
    flavor_name = flavor.name if isinstance(flavor, MarkdownFlavor) else flavor
    return _MARKDOWN_OUTPUT_EXTENSIONS[flavor_name]


def markdown_output_filename(
    filename: str | None,
    flavor: MarkdownFlavor | MarkdownFlavorName,
) -> str:
    """Return the output filename for a rendered markdown flavor.

    Output naming is registry policy, not part of the rendering protocol.
    Known markdown suffixes are stripped longest-first before appending the
    selected flavor's suffix, so `notebook.myst.md` exported as pymdown becomes
    `notebook.md` instead of reusing the MyST-specific filename.
    """
    extension = _markdown_output_extension(flavor)
    basename = os.path.basename(filename or f"notebook.{extension}")
    for suffix in _MARKDOWN_FILENAME_SUFFIXES:
        if basename.endswith(suffix):
            return f"{basename[: -len(suffix)]}.{extension}"
    return f"{os.path.splitext(basename)[0]}.{extension}"


__all__ = [
    "default_markdown_flavor",
    "markdown_flavor_from_filename",
    "markdown_output_filename",
    "normalize_markdown_flavor",
]
