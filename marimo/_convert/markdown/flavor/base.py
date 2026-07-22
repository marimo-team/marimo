# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator

MarkdownFlavorName = Literal["pymdown", "qmd", "mystmd", "mdx"]


def _escape_attribute(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


@dataclass(frozen=True)
class MarkdownCellBlock:
    text: str


@dataclass(frozen=True)
class CodeCellBlock:
    source: str
    language: str
    options: dict[str, str]


MarkdownExportBlock = MarkdownCellBlock | CodeCellBlock


@dataclass(frozen=True)
class MarkdownExportDocument:
    metadata: dict[str, str | list[str]]
    header: str | None
    blocks: list[MarkdownExportBlock]


@dataclass
class MarkdownImportContext:
    """Mutable state shared by markdown import dialects."""

    metadata: dict[str, str] = field(default_factory=dict)


class MarkdownImportDialect(Protocol):
    """Source markdown syntax adapter for the canonical importer."""

    name: MarkdownFlavorName

    def matches(self, text: str, filepath: str | None) -> bool:
        """Return whether this dialect should preprocess the markdown."""
        ...

    def preprocess(
        self, lines: list[str], context: MarkdownImportContext
    ) -> list[str]:
        """Normalize source markdown before the canonical importer runs."""
        ...


class MarkdownFlavor(ABC):
    """Markdown-family output flavor.

    The base renderer assembles a document from preamble, markdown blocks, and
    code cells. Concrete flavors provide target-specific metadata and cell
    syntax.
    """

    name: ClassVar[MarkdownFlavorName]

    @abstractmethod
    def prepare_metadata(
        self, metadata: dict[str, str | list[str]]
    ) -> dict[str, str | list[str]]:
        """Return metadata after flavor-specific normalization.

        Flavors use this hook for metadata additions or removals before their
        preamble renderer serializes the document.
        """

    def render_document(self, document: MarkdownExportDocument) -> str:
        """Render a document by applying flavor-specific block renderers.

        Consecutive markdown cells are separated by an HTML comment, while
        transitions from markdown to executable code blocks get a blank
        line. Flavors should override smaller render hooks before replacing
        this whole assembly step.
        """

        def render_blocks() -> Iterator[str]:
            previous_was_markdown = False

            for block in document.blocks:
                if isinstance(block, MarkdownCellBlock):
                    if previous_was_markdown:
                        yield "<!---->"
                    previous_was_markdown = True
                    yield self.render_markdown(block)
                    continue

                if previous_was_markdown:
                    yield ""
                previous_was_markdown = False

                yield self.render_code_cell(block)

        return "\n".join(
            [
                *self.render_preamble(document),
                *render_blocks(),
            ]
        ).strip()

    @abstractmethod
    def render_preamble(self, document: MarkdownExportDocument) -> list[str]:
        """Render document-level metadata before the body.

        Preamble syntax and metadata filtering are target-specific. A flavor can
        use YAML frontmatter, a directive-based config block, or another
        target-native metadata surface.
        """

    @abstractmethod
    def render_markdown(self, block: MarkdownCellBlock) -> str:
        """Render user-authored markdown text unchanged."""

    @abstractmethod
    def render_code_cell(self, cell: CodeCellBlock) -> str:
        """Render an executable marimo cell.

        Code cell syntax differs across targets. Some formats use fenced code
        attributes, some use directive option lines, and others may use a
        different executable-cell wrapper.
        """
