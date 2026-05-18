# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal

if TYPE_CHECKING:
    from collections.abc import Iterator

MarkdownFlavorName = Literal["pymdown", "qmd", "mystmd"]


@dataclass(frozen=True)
class MarkdownCellBlock:
    text: str


@dataclass(frozen=True)
class CodeCellBlock:
    source: str
    language: str
    options: dict[str, str]


@dataclass(frozen=True)
class DirectiveBlock:
    name: str
    argument: str | None
    options: dict[str, Any]
    body: str


@dataclass(frozen=True)
class TabSetBlock:
    tabs: list[DirectiveBlock]


MarkdownExportBlock = (
    MarkdownCellBlock | CodeCellBlock | DirectiveBlock | TabSetBlock
)


@dataclass(frozen=True)
class MarkdownExportDocument:
    metadata: dict[str, str | list[str]]
    header: str | None
    blocks: list[MarkdownExportBlock]


class MarkdownFlavor(ABC):
    """Markdown-family output flavor.

    This class defines document assembly: metadata, markdown text, code cells,
    directives, and tab groups are delegated to concrete flavors. That keeps
    dialect-specific syntax out of the template method.
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
        """Render a document by applying block transforms, then block renderers.

        Consecutive markdown cells are separated by an HTML comment, while
        transitions from markdown to executable/directive blocks get a blank
        line. Flavors should override smaller render hooks before replacing
        this whole assembly step.
        """

        def render_blocks() -> Iterator[str]:
            previous_was_markdown = False

            for block in self.transform_blocks(document.blocks):
                if isinstance(block, MarkdownCellBlock):
                    if previous_was_markdown:
                        yield "<!---->"
                    previous_was_markdown = True
                    yield self.render_markdown(block)
                    continue

                if previous_was_markdown:
                    yield ""
                previous_was_markdown = False

                if isinstance(block, CodeCellBlock):
                    yield self.render_code_cell(block)
                elif isinstance(block, TabSetBlock):
                    yield self.render_tab_set(block)
                else:
                    yield self.render_directive(block)

        return "\n".join(
            [
                *self.render_preamble(document),
                *render_blocks(),
            ]
        ).strip()

    @abstractmethod
    def render_preamble(self, document: MarkdownExportDocument) -> list[str]:
        """Render document-level metadata before the body.

        Preamble syntax and metadata filtering are target-specific. A flavor
        might use YAML frontmatter, a directive-based config block, no preamble
        at all, or another target-native metadata surface.
        """

    @abstractmethod
    def render_markdown(self, block: MarkdownCellBlock) -> str:
        """Render markdown text that already belongs to the target flavor.

        Cross-flavor conversion of embedded syntax belongs in
        `transform_blocks`, not here, so markdown cells can first be split into
        more specific block objects. For example, a target flavor may parse
        source callouts or tab blocks before deciding how to render them.
        """

    @abstractmethod
    def transform_blocks(
        self, blocks: list[MarkdownExportBlock]
    ) -> list[MarkdownExportBlock]:
        """Normalize the block stream before rendering.

        Target flavors use this hook to parse source-specific blocks out of
        markdown cells and group related blocks. For example, a flavor may
        split PyMdown-style `///` blocks out of markdown text, then group
        consecutive tab directives before rendering.
        """

    @abstractmethod
    def render_code_cell(self, cell: CodeCellBlock) -> str:
        """Render an executable marimo cell.

        Code cell syntax differs across targets. Some formats use fenced code
        attributes, some use directive option lines, and others may use a
        different executable-cell wrapper.
        """

    @abstractmethod
    def render_directive(self, block: DirectiveBlock) -> str:
        """Render a semantic directive block.

        Concrete flavors decide the target-native form. For example, a semantic
        callout might become a PyMdown `///` block, a Quarto callout, a MyST
        directive, or another container syntax.
        """

    @abstractmethod
    def render_tab_set(self, block: TabSetBlock) -> str:
        """Render a grouped tab container.

        Tabs are grouped before rendering so target flavors can emit one
        container when the target supports one. Examples include Quarto panel
        tabsets, MyST tab-set directives, and PyMdown tab blocks.
        """
