# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._cli.print import orange


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
