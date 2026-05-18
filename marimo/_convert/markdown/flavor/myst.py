"""MyST target flavor for marimo notebook exports.

Marimo cells are emitted as MyST directives:

```{marimo} python
:hide-code: true

x = 1
```

Syntax references:
- MyST directives, callouts, admonitions, and dropdown admonitions:
  https://mystmd.org/guide/admonitions
- MyST tab-set and tab-item directives:
  https://mystmd.org/docs/mystjs/dropdowns-cards-and-tabs
"""

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

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

_MARIMO_VERSION_KEY = "marimo-version"
_CONFIG_KEYS = {"header", "pyproject"}
_MARIMO_METADATA_KEYS = {_MARIMO_VERSION_KEY, "width"}
_SCRIPT_METADATA_RE = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    r"(?P<content>(^#(| .*)$\s)+)^# ///$"
)


class MystMarkdownFlavor(MarkdownFlavor):
    """Render marimo notebooks as MyST markdown.

    MyST is directive-oriented, so this flavor emits marimo cells with body
    option lines instead of inline fence attributes. Page-level execution
    metadata is emitted through a `{marimo-config}` directive.
    """

    name = "mystmd"

    def prepare_metadata(
        self, metadata: dict[str, str | list[str]]
    ) -> dict[str, str | list[str]]:
        return metadata

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

    def render_preamble(self, document: MarkdownExportDocument) -> list[str]:
        metadata = self.prepare_metadata(document.metadata)
        return [
            *_myst_frontmatter(metadata),
            *_myst_config(metadata, document.header),
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
                    f":{_myst_option_name(key)}: {value}"
                    for key, value in cell.options.items()
                ],
                *([""] if cell.options else []),
                code,
                guard,
                "",
            ]
        )

    def render_directive(self, block: DirectiveBlock) -> str:
        """Render PyMdown-style directives as native MyST directives.

        MyST admonition and dropdown syntax:
        https://mystmd.org/guide/admonitions
        """
        name = "dropdown" if block.name == "details" else block.name
        head = f":::{{{name}}}"
        if block.argument is not None:
            head = f"{head} {block.argument}"

        options = _myst_options(block)
        return "\n".join(
            [
                head,
                *([options, ""] if options else []),
                block.body,
                ":::",
                "",
            ]
        )

    def render_tab_set(self, block: TabSetBlock) -> str:
        """Render PyMdown tabs as MyST's native tab directives.

        MyST tab-set and tab-item syntax:
        https://mystmd.org/docs/mystjs/dropdowns-cards-and-tabs
        """
        return "\n".join(
            [
                "::::{tab-set}",
                *[
                    line
                    for tab in block.tabs
                    for line in [
                        f":::{{tab-item}} {tab.argument or 'Tab'}",
                        *(
                            [":selected:"]
                            if option_is_truthy(tab.options.get("select"))
                            else []
                        ),
                        tab.body,
                        ":::",
                    ]
                ],
                "::::",
                "",
            ]
        )


def _myst_frontmatter(
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


def _myst_config(
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


def _myst_options(block: DirectiveBlock) -> str:
    admonition_type = (
        block.options.get("type") if block.name == "admonition" else None
    )
    details_type = (
        block.options.get("type") if block.name == "details" else None
    )
    attrs = block.options.get("attrs")
    block_id = attrs.get("id") if isinstance(attrs, dict) else None
    classes = attrs.get("class") if isinstance(attrs, dict) else None
    class_names = [
        str(class_name)
        for class_name in [admonition_type, details_type]
        if class_name
    ]
    if classes:
        class_names.extend(str(classes).split())

    return "\n".join(
        [
            *([f":class: {' '.join(class_names)}"] if class_names else []),
            *(
                [":open:"]
                if block.name == "details"
                and option_is_truthy(block.options.get("open"))
                else []
            ),
            *([f":label: {block_id}"] if block_id else []),
        ]
    )


def _myst_option_name(key: str) -> str:
    return key.replace("_", "-")
