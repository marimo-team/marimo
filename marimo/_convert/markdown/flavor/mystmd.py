"""mystmd markdown target flavor for marimo notebook exports.

Marimo cells are emitted as mystmd directives:

```{marimo} python
:hide-code: true

x = 1
```
"""

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    MarkdownCellBlock,
    MarkdownExportDocument,
    MarkdownFlavor,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

# Metadata emitted through the `{marimo-config}` directive.
_CONFIG_KEYS = {"header", "pyproject"}
# marimo-specific metadata filtered before writing MyST frontmatter.
_MARIMO_METADATA_KEYS = {"width"}
# PEP 723 script metadata blocks embedded in exported notebook headers.
_SCRIPT_METADATA_RE = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    r"(?P<content>(^#(| .*)$\s)+)^# ///$"
)


class MystmdMarkdownFlavor(MarkdownFlavor):
    """Render marimo notebooks as mystmd markdown.

    mystmd uses directive option lines for cell metadata. Page-level execution
    metadata is emitted through a `{marimo-config}` directive.
    """

    name = "mystmd"

    def prepare_metadata(
        self, metadata: dict[str, str | list[str]]
    ) -> dict[str, str | list[str]]:
        return metadata

    def render_preamble(self, document: MarkdownExportDocument) -> list[str]:
        metadata = self.prepare_metadata(document.metadata)
        return [
            *_mystmd_frontmatter(metadata),
            *_mystmd_config(metadata, document.header),
        ]

    def render_markdown(self, block: MarkdownCellBlock) -> str:
        return block.text

    def render_code_cell(self, cell: CodeCellBlock) -> str:
        code_lines = cell.source.splitlines()
        if not any(line.strip() for line in code_lines):
            code_lines = [
                "pass" if cell.language == "python" else "-- empty cell"
            ]
        code = "\n".join(code_lines)
        guard = "```"
        while guard in code:
            guard += "`"

        return "\n".join(
            [
                f"{guard}{{marimo}} {cell.language}",
                *[
                    f":{_mystmd_option_name(key)}: {value}"
                    for key, value in cell.options.items()
                ],
                *([""] if cell.options else []),
                code,
                guard,
                "",
            ]
        )


def _mystmd_frontmatter(
    metadata: Mapping[str, object],
) -> list[str]:
    from marimo._utils import yaml

    filtered = {
        key: value
        for key, value in metadata.items()
        if key not in _CONFIG_KEYS
        and key not in _MARIMO_METADATA_KEYS
        and value is not None
        and value != ""
        and value != []
    }
    if not filtered:
        return []

    body = yaml.marimo_compat_dump(filtered, sort_keys=False).strip()
    return [
        "---",
        body,
        "---",
        "",
    ]


def _mystmd_config(
    metadata: Mapping[str, object], document_header: str | None
) -> list[str]:
    from marimo._utils import yaml

    header = str(metadata.get("header") or document_header or "").strip()
    header, header_pyproject = _split_script_metadata(header)
    pyproject = str(metadata.get("pyproject") or header_pyproject).strip()
    config = {
        key: value
        for key, value in {"header": header, "pyproject": pyproject}.items()
        if value
    }
    if not config:
        return []

    body = yaml.marimo_compat_dump(config, sort_keys=False).strip()
    return [
        "```{marimo-config}",
        "---",
        body,
        "---",
        "```",
        "",
    ]


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


def _mystmd_option_name(key: str) -> str:
    return key.replace("_", "-")
