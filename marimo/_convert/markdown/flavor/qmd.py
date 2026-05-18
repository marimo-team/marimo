"""Quarto markdown target flavor.

PyMdown admonitions become Quarto callouts:

/// tip | Heads up
Body
///

::: {.callout-tip title="Heads up"}
Body
:::

Syntax references:
- Quarto callout blocks:
  https://quarto.org/docs/authoring/callouts.html
- Quarto tabset panels:
  https://quarto.org/docs/interactive/layout.html#tabset-panel
"""

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    DirectiveBlock,
    MarkdownCellBlock,
    MarkdownExportBlock,
    MarkdownExportDocument,
    MarkdownFlavor,
    TabSetBlock,
)
from marimo._convert.markdown.flavor.pymdown import (
    group_pymdown_tabs,
    option_is_truthy,
    split_pymdown_blocks,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class QmdMarkdownFlavor(MarkdownFlavor):
    """Render marimo exports as Quarto-native markdown.

    This flavor parses PyMdown Blocks from markdown cells and maps known
    semantic blocks to Quarto callouts and panel tabsets. Unknown directives
    are emitted as Pandoc fenced divs.
    """

    name = "qmd"

    _callout_types: ClassVar[Mapping[str, str]] = MappingProxyType(
        {
            "admonition": "note",
            "attention": "important",
            "caution": "caution",
            "danger": "caution",
            "error": "caution",
            "hint": "tip",
            "important": "important",
            "note": "note",
            "tip": "tip",
            "warning": "warning",
        }
    )

    def transform_blocks(
        self, blocks: list[MarkdownExportBlock]
    ) -> list[MarkdownExportBlock]:
        transformed: list[MarkdownExportBlock] = []
        for block in blocks:
            if isinstance(block, MarkdownCellBlock):
                transformed.extend(split_pymdown_blocks(block.text))
            else:
                transformed.append(block)
        return group_pymdown_tabs(transformed)

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
            [""] + [f'{key}="{value}"' for key, value in attributes.items()]
        )
        guard = "```"
        while guard in code:
            guard += "`"

        head = self._code_fence_head(guard, language, attribute_str)
        parts = [head, code, guard, ""]
        return "\n".join(parts)

    def render_directive(self, block: DirectiveBlock) -> str:
        """Render PyMdown admonitions as Quarto callout blocks.

        Quarto callout syntax:
        https://quarto.org/docs/authoring/callouts.html
        """
        callout_type = self._callout_type(block)
        if callout_type is None:
            return _render_pandoc_div(block)

        attributes = [
            f".callout-{callout_type}",
            *(
                [f'title="{_escape_attribute(block.argument)}"']
                if block.argument
                else []
            ),
            *[
                f'{key}="{_escape_attribute(str(value))}"'
                for key in ("collapse", "appearance", "icon")
                for value in [block.options.get(key)]
                if value is not None
            ],
        ]

        return "\n".join(
            [
                f"::: {{{' '.join(attributes)}}}",
                block.body,
                ":::",
                "",
            ]
        )

    def render_tab_set(self, block: TabSetBlock) -> str:
        """Render PyMdown tabs as a Quarto `.panel-tabset` div.

        Quarto tabset panel syntax:
        https://quarto.org/docs/interactive/layout.html#tabset-panel
        """
        return "\n".join(
            [
                "::: {.panel-tabset}",
                *[
                    line
                    for tab in block.tabs
                    for line in ["", _tab_heading(tab), "", tab.body]
                ],
                ":::",
                "",
            ]
        )

    def _callout_type(self, block: DirectiveBlock) -> str | None:
        if block.name == "admonition":
            explicit_type = block.options.get("type")
            if isinstance(explicit_type, str):
                return self._callout_types.get(explicit_type)
        return self._callout_types.get(block.name)


def _escape_attribute(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;")


def _render_pandoc_div(block: DirectiveBlock) -> str:
    attributes = _pandoc_attributes(block)
    return "\n".join(
        [
            f"::: {{{' '.join(attributes)}}}",
            block.body,
            ":::",
            "",
        ]
    )


def _pandoc_attributes(block: DirectiveBlock) -> list[str]:
    attributes = [f".{block.name}"]
    if block.argument:
        attributes.append(f'title="{_escape_attribute(block.argument)}"')

    for key, value in block.options.items():
        if key == "attrs" and isinstance(value, dict):
            block_id = value.get("id")
            if block_id:
                attributes.append(f"#{block_id}")
            classes = value.get("class")
            if classes:
                attributes.extend(
                    f".{class_name}"
                    for class_name in str(classes).split()
                    if class_name
                )
            continue
        attributes.append(
            f'{key}="{_escape_attribute(_attribute_value(value))}"'
        )
    return attributes


def _attribute_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _tab_heading(tab: DirectiveBlock) -> str:
    heading = f"## {tab.argument or 'Tab'}"
    if option_is_truthy(tab.options.get("select")):
        return f"{heading} {{.active}}"
    return heading
