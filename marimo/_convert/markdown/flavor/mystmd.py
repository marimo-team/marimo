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

from marimo import _loggers
from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    MarkdownCellBlock,
    MarkdownExportDocument,
    MarkdownFlavor,
    MarkdownFlavorName,
    MarkdownImportContext,
    _escape_attribute,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

LOGGER = _loggers.marimo_logger()

# Metadata emitted through the `{marimo-config}` directive.
_CONFIG_KEYS = {"header", "pyproject", "width"}
# marimo-specific metadata filtered before writing MyST frontmatter.
_MARIMO_METADATA_KEYS = {"width"}
# MyST marimo executable directive headers.
_MARIMO_DIRECTIVE_HEADER_RE = re.compile(
    r"^[ ]{0,3}(?P<fence>`{3,})\{marimo\}"
    r"(?:\s+(?P<language>\w+))?\s*$"
)
# MyST marimo page-level configuration directive headers.
_MARIMO_CONFIG_HEADER_RE = re.compile(
    r"^[ ]{0,3}(?P<fence>`{3,})\{marimo-config\}\s*$"
)
# Markdown backtick fences. Used to skip ordinary fenced examples before
# normalizing MyST marimo directives.
_FENCE_HEADER_RE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}).*$")
# MyST directive options, e.g. `:hide-code: true`.
_DIRECTIVE_OPTION_RE = re.compile(r"^:([A-Za-z0-9_-]+):(?:\s+(.*))?$")
# PEP 723 script metadata blocks embedded in exported notebook headers.
_SCRIPT_METADATA_RE = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    r"(?P<content>(^#(| .*)$\s)+)^# ///$"
)


class _MystmdMarkdownImportDialect:
    """Normalize MyST marimo directives into canonical marimo markdown."""

    name: MarkdownFlavorName = "mystmd"

    def matches(self, text: str, filepath: str | None) -> bool:
        del filepath
        return (
            _find_next_top_level_marimo_header(text.splitlines()) is not None
        )

    def preprocess(
        self, lines: list[str], context: MarkdownImportContext
    ) -> list[str]:
        normalized: list[str] = []
        index = 0

        while index < len(lines):
            config_match = _MARIMO_CONFIG_HEADER_RE.match(lines[index])
            if config_match is not None:
                closing_index = _find_closing_fence(
                    lines, index + 1, config_match.group("fence")
                )
                if closing_index is None:
                    normalized.extend(lines[index:])
                    break

                context.metadata.update(
                    _extract_config_metadata(lines[index + 1 : closing_index])
                )
                index = closing_index + 1
                continue

            match = _MARIMO_DIRECTIVE_HEADER_RE.match(lines[index])
            if match is None:
                fence_match = _FENCE_HEADER_RE.match(lines[index])
                if fence_match is None:
                    normalized.append(lines[index])
                    index += 1
                    continue

                closing_index = _find_closing_fence(
                    lines, index + 1, fence_match.group("fence")
                )
                if closing_index is None:
                    normalized.extend(lines[index:])
                    break
                normalized.extend(lines[index : closing_index + 1])
                index = closing_index + 1
                continue

            closing_index = _find_closing_fence(
                lines, index + 1, match.group("fence")
            )
            if closing_index is None:
                normalized.extend(lines[index:])
                break

            options, body_lines = _extract_directive_options(
                lines[index + 1 : closing_index]
            )
            normalized.append(_canonical_code_fence_head(match, options))
            normalized.extend(body_lines)
            normalized.append(match.group("fence"))
            index = closing_index + 1

        return normalized


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
        code = "\n".join(code_lines)
        guard = _fence_guard_for(code)

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
    width = metadata.get("width")
    config = {
        key: value
        for key, value in {"header": header, "pyproject": pyproject}.items()
        if value
    }
    if isinstance(width, str) and width:
        config["width"] = width
    if not config:
        return []

    body = yaml.marimo_compat_dump(config, sort_keys=False).strip()
    guard = _fence_guard_for(f"---\n{body}\n---")
    return [
        f"{guard}{{marimo-config}}",
        "---",
        body,
        "---",
        guard,
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


def _is_marimo_header(line: str) -> bool:
    return bool(
        _MARIMO_DIRECTIVE_HEADER_RE.match(line)
        or _MARIMO_CONFIG_HEADER_RE.match(line)
    )


def _fence_guard_for(body: str) -> str:
    guard = "```"
    while guard in body:
        guard += "`"
    return guard


def _find_next_top_level_marimo_header(lines: list[str]) -> int | None:
    index = 0
    while index < len(lines):
        if _is_marimo_header(lines[index]):
            return index

        fence_match = _FENCE_HEADER_RE.match(lines[index])
        if fence_match is None:
            index += 1
            continue

        closing_index = _find_closing_fence(
            lines, index + 1, fence_match.group("fence")
        )
        if closing_index is None:
            return None
        index = closing_index + 1

    return None


def _is_closing_fence(line: str, opening_fence: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= len(opening_fence) and set(stripped) == {"`"}


def _find_closing_fence(
    lines: list[str], start: int, opening_fence: str
) -> int | None:
    for index in range(start, len(lines)):
        if _is_closing_fence(lines[index], opening_fence):
            return index
    return None


def _extract_directive_options(
    lines: list[str],
) -> tuple[dict[str, str], list[str]]:
    options: dict[str, str] = {}
    body_start = 0

    for index, line in enumerate(lines):
        match = _DIRECTIVE_OPTION_RE.match(line)
        if match is None:
            break
        options[match.group(1).replace("-", "_")] = match.group(2) or "true"
        body_start = index + 1

    if body_start and body_start < len(lines) and lines[body_start] == "":
        body_start += 1

    return options, lines[body_start:]


def _canonical_code_fence_head(
    match: re.Match[str], options: dict[str, str]
) -> str:
    attribute_str = "".join(
        f' {key}="{_escape_attribute(value)}"'
        for key, value in options.items()
    )
    return "{fence}{language} {{.marimo{attributes}}}".format(
        fence=match.group("fence"),
        language=match.group("language") or "python",
        attributes=attribute_str,
    )


def extract_mystmd_config_metadata(markdown: str) -> dict[str, str]:
    lines = markdown.splitlines()
    metadata: dict[str, str] = {}
    index = 0

    while index < len(lines):
        next_index = _find_next_top_level_marimo_header(lines[index:])
        if next_index is None:
            break
        index += next_index

        config_match = _MARIMO_CONFIG_HEADER_RE.match(lines[index])
        if config_match is None:
            directive_match = _MARIMO_DIRECTIVE_HEADER_RE.match(lines[index])
            if directive_match is None:
                index += 1
                continue

            closing_index = _find_closing_fence(
                lines, index + 1, directive_match.group("fence")
            )
            if closing_index is None:
                break
            index = closing_index + 1
            continue

        closing_index = _find_closing_fence(
            lines, index + 1, config_match.group("fence")
        )
        if closing_index is None:
            break

        metadata.update(
            _extract_config_metadata(lines[index + 1 : closing_index])
        )
        index = closing_index + 1

    return metadata


def _extract_config_metadata(lines: list[str]) -> dict[str, str]:
    from marimo._utils import yaml

    if lines and lines[0] == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line == "---":
                lines = lines[1:index]
                break

    try:
        metadata = yaml.load("\n".join(lines))
    except yaml.YAMLError:
        LOGGER.warning("Error parsing marimo-config YAML. Ignoring config.")
        return {}

    if not isinstance(metadata, dict):
        return {}

    return {
        key: value
        for key, value in metadata.items()
        if key in _CONFIG_KEYS and isinstance(value, str)
    }
