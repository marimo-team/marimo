# Copyright 2026 Marimo. All rights reserved.
"""Fail if any docstring uses double backticks for inline code.

marimo renders docstrings as Markdown, where inline code uses single
backticks (`value`). Double backticks are reStructuredText
syntax and render incorrectly. This check flags them.

Triple-backtick Markdown code fences are allowed.

Usage:
    python scripts/check_docstring_backticks.py [files...]
"""

from __future__ import annotations

import ast
import sys

# A run of exactly two backticks, not adjacent to a third. This matches
# RST-style inline code (``value``) while ignoring Markdown code fences
# (``` or longer), where every interior pair is backtick-adjacent.
import re

_DOUBLE_BACKTICK = re.compile(r"(?<!`)``(?!`)")

_DOCSTRINGABLE = (
    ast.Module,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)


def check_file(path: str) -> list[str]:
    """Return a list of `path:line: message` errors for one file."""
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [f"{path}: could not read file ({e})"]

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        # Leave syntax errors to other tools (ruff, the compiler).
        return []

    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, _DOCSTRINGABLE):
            continue
        docstring = ast.get_docstring(node, clean=False)
        if docstring and _DOUBLE_BACKTICK.search(docstring):
            # ast.Module has no lineno; its docstring starts the file.
            lineno = getattr(node, "lineno", 1)
            errors.append(
                f"{path}:{lineno}: double backticks in docstring"
            )
    return errors


def main(argv: list[str]) -> int:
    errors: list[str] = []
    for path in argv:
        errors.extend(check_file(path))

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(
            "\nUse single backticks for inline code in docstrings "
            "(`value`, not ``value``).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
