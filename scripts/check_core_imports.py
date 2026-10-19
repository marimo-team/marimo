#!/usr/bin/env python3
"""Check that `marimo._core` imports no other marimo modules.

Includes imports inside functions and `TYPE_CHECKING` blocks.

Usage: check_core_imports.py [FILE_OR_DIR ...]

Defaults to the core package.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "marimo" / "_core"
PACKAGE = "marimo._core"


def is_outside_core(module: str) -> bool:
    """Whether `module` names a marimo module outside the core package."""
    if module == PACKAGE or module.startswith(PACKAGE + "."):
        return False
    return module == "marimo" or module.startswith("marimo.")


def offending_imports(path: Path) -> list[tuple[int, str]]:
    """Return `(line, module)` pairs for disallowed imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                (node.lineno, alias.name)
                for alias in node.names
                if is_outside_core(alias.name)
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Absolute imports make the target package explicit.
                found.append(
                    (node.lineno, "." * node.level + (node.module or ""))
                )
            elif node.module is not None and is_outside_core(node.module):
                found.append((node.lineno, node.module))
    return found


def python_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(sorted(target.rglob("*.py")))
        else:
            files.append(target)
    return files


def main(argv: list[str]) -> int:
    targets = [Path(arg) for arg in argv] or [CORE]
    failures = 0
    for path in python_files(targets):
        for line, module in offending_imports(path):
            print(f"{path}:{line}: imports {module}", file=sys.stderr)
            failures += 1
    if failures:
        print(
            f"\n{PACKAGE} must not import from the rest of marimo "
            f"({failures} violation{'s' if failures != 1 else ''}).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
