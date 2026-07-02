"""Quarto markdown target flavor."""

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    MarkdownCellBlock,
    MarkdownExportDocument,
    MarkdownFlavor,
    _escape_attribute,
)


class QmdMarkdownFlavor(MarkdownFlavor):
    """Render marimo exports as Quarto-native markdown.

    This flavor emits Quarto-style executable marimo code fences while
    preserving markdown cells as authored.
    """

    name = "qmd"

    def prepare_metadata(
        self, metadata: dict[str, str | list[str]]
    ) -> dict[str, str | list[str]]:
        return metadata.copy()

    def render_preamble(self, document: MarkdownExportDocument) -> list[str]:
        from marimo._utils import yaml

        metadata = self.prepare_metadata(document.metadata)
        header = yaml.marimo_compat_dump(
            {
                key: value
                for key, value in metadata.items()
                if value is not None and value != "" and value != []
            },
            sort_keys=False,
        )
        return ["---", header.strip(), "---", ""]

    def render_markdown(self, block: MarkdownCellBlock) -> str:
        return block.text

    def render_code_cell(self, cell: CodeCellBlock) -> str:
        return self._render_code_fence(
            cell.source,
            {"language": cell.language, **cell.options},
        )

    def _code_fence_head(
        self, guard: str, language: str, attribute_str: str
    ) -> str:
        # Quarto executable syntax with claimsLanguage() support:
        # ```{marimo .python attr=...}
        return f"{guard}{{marimo .{language}{attribute_str}}}"

    def _render_code_fence(
        self,
        code: str,
        attributes: dict[str, str] | None = None,
    ) -> str:
        attributes = dict(attributes or {})
        language = attributes.pop("language", "python")
        attribute_str = " ".join(
            [""]
            + [
                f'{key}="{_escape_attribute(str(value))}"'
                for key, value in attributes.items()
            ]
        )
        guard = "```"
        while guard in code:
            guard += "`"

        head = self._code_fence_head(guard, language, attribute_str)
        parts = [head, code, guard, ""]
        return "\n".join(parts)
