# Copyright 2026 Marimo. All rights reserved.
"""Require `-P` or `-I` to prevent implicit imports from the working directory.

Checks list/tuple commands, wrapper commands after `--`, and assigned multiline
Python strings. Recognizes `sys.executable`, Python paths, and common interpreter
names. Does not resolve arbitrary aliases or commands built through mutations.

Usage: uv run python scripts/check_python_safe_path.py [FILE_OR_DIR ...]
Defaults to `marimo/`.
"""

from __future__ import annotations

import ast
import re
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_NAME = re.compile(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?$")
INTERPRETER_NAMES = {"python", "python_exe", "venv_python", "py_exe"}


def string_value(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def is_python(node: ast.expr) -> bool:
    value = string_value(node)
    if value is not None:
        return (
            PYTHON_NAME.fullmatch(value.replace("\\", "/").rsplit("/", 1)[-1])
            is not None
        )
    match node:
        case ast.Attribute(value=ast.Name(id="sys"), attr="executable"):
            return True
        case ast.Attribute(attr=name) | ast.Name(id=name):
            return name.lstrip("_").lower() in INTERPRETER_NAMES
        case _:
            return False


def has_safe_path(args: list[ast.expr]) -> bool:
    arguments = iter(args)
    for arg in arguments:
        value = string_value(arg)
        # Interpreter flags must precede the module, code, script, or *args.
        if (
            value is None
            or not value.startswith("-")
            or value in {"-", "--", "-m", "-c"}
        ):
            return False
        if value in {"-W", "-X"}:
            next(arguments, None)
            continue
        if value.startswith(("-W", "-X")):
            continue
        if re.fullmatch(r"-[bBdEhiIOPqRsSuvVx]+", value) and (
            "P" in value or "I" in value
        ):
            return True
    return False


def unsafe_commands(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        for index, arg in enumerate(node.elts):
            if index and string_value(node.elts[index - 1]) != "--":
                continue
            args = node.elts[index + 1 :]
            if not args:
                continue
            first = string_value(args[0])
            # Language lists and Literal types can also contain "python".
            if string_value(arg) is not None and first is not None:
                if not first.startswith("-") and not first.endswith(".py"):
                    continue
            if is_python(arg) and not has_safe_path(args):
                lines.append(arg.lineno)
    return lines


def offending_lines(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines = unsafe_commands(tree)
    for node in ast.walk(tree):
        if (
            not isinstance(node, (ast.Assign, ast.AnnAssign))
            or node.value is None
        ):
            continue
        value = string_value(node.value)
        if value is None or "\n" not in value:
            continue
        try:
            embedded = ast.parse(textwrap.dedent(value))
        except SyntaxError:
            continue
        if unsafe_commands(embedded):
            lines.append(node.value.lineno)
    return sorted(set(lines))


def main(argv: list[str]) -> int:
    targets = [Path(arg) for arg in argv] or [REPO_ROOT / "marimo"]
    failed = False
    for target in targets:
        paths = sorted(target.rglob("*.py")) if target.is_dir() else [target]
        for path in paths:
            for line in offending_lines(path):
                sys.stderr.write(
                    f"{path}:{line}: Python helper command must include -P "
                    "(or -I) before -m, -c, script, or forwarded arguments\n",
                )
                failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
