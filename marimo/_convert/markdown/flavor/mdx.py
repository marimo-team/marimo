"""MDX markdown target flavor."""

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    MarkdownCellBlock,
    MarkdownExportDocument,
    MarkdownFlavor,
    MarkdownFlavorName,
)
from marimo._utils.typing import override

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

_CONFIG_KEYS = {"header", "pyproject"}
_SIMPLE_OPTION_VALUE_RE = re.compile(r"^[A-Za-z0-9_.:/+-]+$")
_SCRIPT_METADATA_RE = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    + r"(?P<content>(^#(| .*)$\s)+)^# ///$"
)


class MdxMarkdownFlavor(MarkdownFlavor):
    """Render marimo notebooks as MDX for `mdx-marimo`.

    Code cells use MDX info strings such as `python marimo echo=true`.
    Script metadata is emitted through a `marimo-config` fence.
    """

    name: ClassVar[MarkdownFlavorName] = "mdx"

    @override
    def prepare_metadata(
        self, metadata: dict[str, str | list[str]]
    ) -> dict[str, str | list[str]]:
        return {
            key: value
            for key, value in metadata.items()
            if key not in _CONFIG_KEYS
        }

    @override
    def render_preamble(self, document: MarkdownExportDocument) -> list[str]:
        metadata = document.metadata
        return [
            *_mdx_frontmatter(self.prepare_metadata(metadata)),
            *_mdx_config(metadata, document.header),
        ]

    @override
    def render_document(self, document: MarkdownExportDocument) -> str:
        def render_blocks() -> Iterator[str]:
            previous_was_markdown = False

            for block in document.blocks:
                if isinstance(block, MarkdownCellBlock):
                    if previous_was_markdown:
                        yield "{/* */}"
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

    @override
    def render_markdown(self, block: MarkdownCellBlock) -> str:
        return block.text

    @override
    def render_code_cell(self, cell: CodeCellBlock) -> str:
        return self._render_code_fence(
            cell.source,
            {"language": cell.language, **cell.options},
        )

    def _render_code_fence(
        self,
        code: str,
        attributes: dict[str, str] | None = None,
    ) -> str:
        attributes = dict(attributes or {})
        language = attributes.pop("language", "python")
        return _render_mdx_code_fence(code, language, attributes)


def _mdx_frontmatter(metadata: Mapping[str, object]) -> list[str]:
    from marimo._utils import yaml

    filtered = {
        key: value
        for key, value in metadata.items()
        if value is not None and value != "" and value != []
    }
    if not filtered:
        return []

    body = yaml.marimo_compat_dump(filtered, sort_keys=False).strip()
    return ["---", body, "---", ""]


def _mdx_config(
    metadata: Mapping[str, object], document_header: str | None
) -> list[str]:
    header = str(metadata.get("header") or document_header or "").strip()
    header, header_pyproject = _split_script_metadata(header)
    pyproject = str(metadata.get("pyproject") or header_pyproject).strip()
    config: list[str] = []

    if pyproject:
        guard = _fence_guard_for(pyproject)
        config.extend([f"{guard}marimo-config", pyproject, guard, ""])

    if header:
        config.append(
            _render_mdx_code_fence(header, "python", {"include": "false"})
        )

    return config


def _split_script_metadata(header: str) -> tuple[str, str]:
    pyproject = ""

    def replace(match: re.Match[str]) -> str:
        nonlocal pyproject
        if match.group("type") != "script":
            return match.group(0)
        if not pyproject:
            pyproject = _uncomment_script_metadata(
                match.group("content")
            ).strip()
        return ""

    return _SCRIPT_METADATA_RE.sub(replace, header).strip(), pyproject


def _uncomment_script_metadata(content: str) -> str:
    return "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in content.splitlines(keepends=True)
    )


def _fence_guard_for(body: str) -> str:
    guard = "```"
    while guard in body:
        guard += "`"
    return guard


def _mdx_option_token(key: str, value: object) -> str:
    return f"{key.replace('_', '-')}={_mdx_option_value(value)}"


def _render_mdx_code_fence(
    code: str, language: str, attributes: Mapping[str, object]
) -> str:
    options = " ".join(
        _mdx_option_token(key, value) for key, value in attributes.items()
    )
    guard = _fence_guard_for(code)
    head = f"{guard}{language} marimo"
    if options:
        head = f"{head} {options}"

    return f"{head}\n{code}\n{guard}\n"


def _mdx_option_value(value: object) -> str:
    text = str(value)
    if _SIMPLE_OPTION_VALUE_RE.match(text):
        return text
    if '"' not in text:
        return f'"{text}"'
    if "'" not in text:
        return f"'{text}'"
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
