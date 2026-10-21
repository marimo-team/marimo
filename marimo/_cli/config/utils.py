# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._cli.print import orange

if TYPE_CHECKING:
    from tomlkit import TOMLDocument

    from marimo._config.provenance import ConfigPath, ResolvedConfig


def highlight_toml_headers(toml_string: str) -> str:
    lines = toml_string.splitlines()
    highlighted_lines: list[str] = []

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("[") and stripped_line.endswith("]"):
            highlighted_lines.append(orange(line))
        else:
            highlighted_lines.append(line)

    return "\n".join(highlighted_lines)


def format_config_with_sources(resolved: ResolvedConfig) -> str:
    """Render effective settings as TOML with a source comment per value."""
    import tomlkit
    from tomlkit.items import AoT, Item, Table

    document = tomlkit.parse(tomlkit.dumps(resolved.config, sort_keys=True))

    def annotate(table: TOMLDocument | Table, path: ConfigPath) -> None:
        for key in table:
            field_path = (*path, key)
            item = table.item(key)
            if isinstance(item, Table) and item:
                annotate(item, field_path)
                continue
            source = (
                str(resolved.origins[field_path])
                .replace("\n", "\\n")
                .replace("\r", "\\r")
            )
            if isinstance(item, AoT):
                for entry in item:
                    entry.comment(source)
            else:
                assert isinstance(item, Item)
                item.comment(source)

    annotate(document, ())
    return highlight_toml_headers(tomlkit.dumps(document))
