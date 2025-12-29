# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import Any

from marimo._utils.toml import read_toml_string

REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def read_pyproject_from_script(script: str) -> dict[str, Any] | None:
    """
    Read the pyproject.toml file from the script.

    Adapted from https://peps.python.org/pep-0723/#reference-implementation
    """
    name = "script"
    matches = list(
        filter(lambda m: m.group("type") == name, re.finditer(REGEX, script))
    )
    if len(matches) > 1:
        raise ValueError(f"Multiple {name} blocks found")
    elif len(matches) == 1:
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in matches[0].group("content").splitlines(keepends=True)
        )

        pyproject = read_toml_string(content)
        return pyproject
    else:
        return None


def write_pyproject_to_script(project: dict[str, Any]) -> str:
    """
    Convert a project dict to PEP 723 inline script metadata format.

    Adapted from https://peps.python.org/pep-0723/#reference-implementation

    Args:
        project: Dictionary containing project metadata (dependencies,
                 requires-python, etc.)

    Returns:
        PEP 723 formatted string with "# /// script" markers
    """
    from marimo._dependencies.dependencies import DependencyManager

    # Convert project dict to TOML
    if DependencyManager.tomlkit.has():
        import tomlkit

        toml_content = tomlkit.dumps(project)
    else:
        # Fallback to simple formatting if tomlkit not available
        # This should rarely happen in practice
        import json

        lines = []
        if "dependencies" in project:
            lines.append(
                f"dependencies = {json.dumps(project['dependencies'])}"
            )
        if "requires-python" in project:
            lines.append(
                f"requires-python = {json.dumps(project['requires-python'])}"
            )
        toml_content = "\n".join(lines) + "\n" if lines else ""

    # Wrap in PEP 723 comment format
    return wrap_script_metadata(toml_content)


def wrap_script_metadata(toml_content: str) -> str:
    """
    Wrap TOML content in PEP 723 inline script metadata markers.

    Args:
        toml_content: Raw TOML content string

    Returns:
        PEP 723 formatted string with "# /// script" markers
    """
    result_lines = ["# /// script"]
    for line in toml_content.rstrip().split("\n"):
        result_lines.append(f"# {line}")
    result_lines.append("# ///")

    return "\n".join(result_lines)
