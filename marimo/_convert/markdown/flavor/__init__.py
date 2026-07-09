# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from marimo._convert.markdown.flavor.base import (
    MarkdownFlavor,
    MarkdownFlavorName,
    MarkdownImportDialect,
)
from marimo._convert.markdown.flavor.mdx import MdxMarkdownFlavor
from marimo._convert.markdown.flavor.mystmd import (
    MystmdMarkdownFlavor,
    _MystmdMarkdownImportDialect,
)
from marimo._convert.markdown.flavor.pymdown import PymdownMarkdownFlavor
from marimo._convert.markdown.flavor.qmd import QmdMarkdownFlavor

if TYPE_CHECKING:
    from collections.abc import Mapping

_PYMDOWN_MARKDOWN = PymdownMarkdownFlavor()
_QMD_MARKDOWN = QmdMarkdownFlavor()
_MYSTMD_MARKDOWN = MystmdMarkdownFlavor()
_MDX_MARKDOWN = MdxMarkdownFlavor()
_MYSTMD_MARKDOWN_IMPORT = _MystmdMarkdownImportDialect()
_MARKDOWN_FLAVORS: Mapping[MarkdownFlavorName, MarkdownFlavor] = (
    MappingProxyType(
        {
            _PYMDOWN_MARKDOWN.name: _PYMDOWN_MARKDOWN,
            _QMD_MARKDOWN.name: _QMD_MARKDOWN,
            _MYSTMD_MARKDOWN.name: _MYSTMD_MARKDOWN,
            _MDX_MARKDOWN.name: _MDX_MARKDOWN,
        }
    )
)
_MARKDOWN_IMPORT_DIALECTS: Mapping[
    MarkdownFlavorName, MarkdownImportDialect
] = MappingProxyType({_MYSTMD_MARKDOWN_IMPORT.name: _MYSTMD_MARKDOWN_IMPORT})
# Filename inference handles target-specific markdown extensions.
_MARKDOWN_FLAVORS_BY_EXTENSION: Mapping[str, MarkdownFlavor] = (
    MappingProxyType(
        {
            ".myst.md": _MYSTMD_MARKDOWN,
            ".qmd": _QMD_MARKDOWN,
            ".mdx": _MDX_MARKDOWN,
        }
    )
)
# Download and auto-export filenames use the selected flavor's suffix.
_MARKDOWN_OUTPUT_EXTENSIONS: Mapping[MarkdownFlavorName, str] = (
    MappingProxyType(
        {
            "pymdown": "md",
            "qmd": "qmd",
            "mystmd": "myst.md",
            "mdx": "mdx",
        }
    )
)
# Strip known markdown suffixes before applying an output suffix.
_MARKDOWN_FILENAME_SUFFIXES = (
    ".myst.md",
    ".markdown",
    ".qmd",
    ".mdx",
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


def _markdown_import_dialects(
    text: str, filepath: str | None
) -> tuple[MarkdownImportDialect, ...]:
    return tuple(
        dialect
        for dialect in _MARKDOWN_IMPORT_DIALECTS.values()
        if dialect.matches(text, filepath)
    )


def _markdown_output_extension(
    flavor: MarkdownFlavor | MarkdownFlavorName,
) -> str:
    flavor_name = flavor.name if isinstance(flavor, MarkdownFlavor) else flavor
    return _MARKDOWN_OUTPUT_EXTENSIONS[flavor_name]


def markdown_output_filename(
    filename: str | None,
    flavor: MarkdownFlavor | MarkdownFlavorName,
) -> str:
    """Return the filename for a rendered markdown artifact.

    Known markdown suffixes are replaced with the selected flavor's suffix.
    For example, exporting `notebook.myst.md` as pymdown returns `notebook.md`.
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
