"""PyMdown Blocks markdown flavor.

Example source block:

/// tip | Heads up
    attrs: {id: tip-demo}

Body
///

Syntax references:
- Blocks fences and options:
  https://facelessuser.github.io/pymdown-extensions/extensions/blocks/
- Blocks admonitions:
  https://facelessuser.github.io/pymdown-extensions/extensions/blocks/plugins/admonition/
- Blocks details:
  https://facelessuser.github.io/pymdown-extensions/extensions/blocks/plugins/details/
- Blocks tabs:
  https://facelessuser.github.io/pymdown-extensions/extensions/blocks/plugins/tab/
- Legacy tabbed extension:
  https://facelessuser.github.io/pymdown-extensions/extensions/tabbed/
- Obsidian-style quotes/callouts:
  https://facelessuser.github.io/pymdown-extensions/extensions/quotes/
"""

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import Any

from pymdownx.blocks import (  # type: ignore[import-untyped]
    get_frontmatter as _get_pymdown_frontmatter,
)

from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    DirectiveBlock,
    MarkdownCellBlock,
    MarkdownExportBlock,
    MarkdownExportDocument,
    MarkdownFlavor,
    TabSetBlock,
)
from marimo._dependencies.dependencies import DependencyManager


class PymdownMarkdownFlavor(MarkdownFlavor):
    """Render marimo Markdown with PyMdown syntax.

    This flavor emits YAML frontmatter, fenced marimo code cells, and PyMdown
    Blocks for admonitions, details, and tabs.
    """

    name = "pymdown"

    def prepare_metadata(
        self, metadata: dict[str, str | list[str]]
    ) -> dict[str, str | list[str]]:
        return metadata

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

    def transform_blocks(
        self, blocks: list[MarkdownExportBlock]
    ) -> list[MarkdownExportBlock]:
        return blocks

    def render_code_cell(self, cell: CodeCellBlock) -> str:
        return self._render_code_fence(
            cell.source,
            {"language": cell.language, **cell.options},
        )

    def render_directive(self, block: DirectiveBlock) -> str:
        return render_pymdown_directive(block)

    def render_tab_set(self, block: TabSetBlock) -> str:
        return render_pymdown_tab_set(block)

    def _code_fence_head(
        self, guard: str, language: str, attribute_str: str
    ) -> str:
        # Compatible with GitHub syntax highlighting:
        # ```python {.marimo attr=...}
        if DependencyManager.new_superfences.has_required_version(quiet=True):
            return f"{guard}{language} {{.marimo{attribute_str}}}"

        # ```{.python.marimo attr=...}
        return f"{guard}{{.{language}.marimo{attribute_str}}}"

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


def render_pymdown_directive(block: DirectiveBlock) -> str:
    """Render a directive using PyMdown Blocks syntax.

    Target flavors can use this helper when a directive has no more specific
    target-native rendering.
    """
    options = "\n".join(
        f"{key}: {value}" for key, value in block.options.items()
    )
    head = f"/// {block.name}"
    if block.argument is not None:
        head = f"{head} | {block.argument}"

    return "\n".join(
        [
            head,
            *([f"    {options}", ""] if options else [""]),
            block.body,
            "///",
        ]
    )


def render_pymdown_tab_set(block: TabSetBlock) -> str:
    """Expand grouped tabs back to consecutive PyMdown tab directives."""
    return "\n\n".join(render_pymdown_directive(tab) for tab in block.tabs)


_PYMDOWN_BLOCK_START_RE = re.compile(
    r"^(?P<indent> {0,3})(?P<fence>/{3,})[ \t]+"
    r"(?P<name>[\w-]+)[ \t]*(?:\|[ \t]*(?P<title>.*?)[ \t]*)?$"
)
_PYMDOWN_BLOCK_END_RE = re.compile(r"^ {0,3}(?P<fence>/{3,})[ \t]*$")
_MARKDOWN_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
_MARKDOWN_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})[ \t]*$")


def split_pymdown_blocks(text: str) -> list[MarkdownExportBlock]:
    """Split PyMdown `/// name | argument` blocks out of plain markdown."""
    lines = text.splitlines()
    blocks: list[MarkdownExportBlock] = []
    pending: list[str] = []
    index = 0
    markdown_fence: str | None = None

    while index < len(lines):
        line = lines[index]
        fence_match = _MARKDOWN_FENCE_RE.match(line)
        if fence_match is not None:
            fence = fence_match.group("fence")
            if markdown_fence is None:
                markdown_fence = fence
            elif _is_markdown_fence_close(line, markdown_fence):
                markdown_fence = None
            pending.append(line)
            index += 1
            continue

        start = (
            None
            if markdown_fence is not None
            else _PYMDOWN_BLOCK_START_RE.match(line)
        )
        if start is None:
            pending.append(line)
            index += 1
            continue

        end_index = _find_pymdown_block_end(
            lines, index + 1, start.group("fence")
        )
        if end_index is None:
            pending.append(line)
            index += 1
            continue

        _append_markdown_block(blocks, pending)
        body_lines = lines[index + 1 : end_index]
        options, body = _extract_pymdown_options(body_lines)
        blocks.append(
            DirectiveBlock(
                name=start.group("name").lower(),
                argument=start.group("title") or None,
                options=options,
                body=body,
            )
        )
        index = end_index + 1

    _append_markdown_block(blocks, pending)
    return blocks


def group_pymdown_tabs(
    blocks: list[MarkdownExportBlock],
) -> list[MarkdownExportBlock]:
    """Group consecutive `/// tab` blocks like PyMdown Blocks does."""
    grouped: list[MarkdownExportBlock] = []
    pending_tabs: list[DirectiveBlock] = []

    def flush_tabs() -> None:
        if pending_tabs:
            grouped.append(TabSetBlock(pending_tabs.copy()))
            pending_tabs.clear()

    for block in blocks:
        if isinstance(block, DirectiveBlock) and block.name == "tab":
            if option_is_truthy(block.options.get("new")):
                flush_tabs()
            pending_tabs.append(block)
            continue

        flush_tabs()
        grouped.append(block)

    flush_tabs()
    return grouped


def option_is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "on"}
    return bool(value)


def _find_pymdown_block_end(
    lines: list[str], start_index: int, opening_fence: str
) -> int | None:
    for index in range(start_index, len(lines)):
        match = _PYMDOWN_BLOCK_END_RE.match(lines[index])
        if match is not None and len(match.group("fence")) == len(
            opening_fence
        ):
            return index
    return None


def _is_markdown_fence_close(line: str, opening_fence: str) -> bool:
    match = _MARKDOWN_FENCE_CLOSE_RE.match(line)
    if match is None:
        return False
    closing_fence = match.group("fence")
    return closing_fence[0] == opening_fence[0] and len(closing_fence) >= len(
        opening_fence
    )


def _append_markdown_block(
    blocks: list[MarkdownExportBlock], lines: list[str]
) -> None:
    text = "\n".join(lines).strip("\n")
    lines.clear()
    if text:
        blocks.append(MarkdownCellBlock(text))


def _extract_pymdown_options(lines: list[str]) -> tuple[dict[str, Any], str]:
    options: dict[str, Any] = {}
    body_start = 0
    option_lines: list[str] = []

    while body_start < len(lines):
        line = lines[body_start]
        if line.startswith("    ") and ":" in line:
            option_lines.append(line[4:])
            body_start += 1
            continue
        if option_lines and not line.strip():
            body_start += 1
            break
        if option_lines:
            return {}, "\n".join(lines).strip("\n")
        break

    if option_lines:
        options = _get_pymdown_frontmatter("\n".join(option_lines)) or {}

    return options, "\n".join(lines[body_start:]).strip("\n")
