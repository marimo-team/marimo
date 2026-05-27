#!/usr/bin/env python3
# Copyright 2026 Marimo. All rights reserved.
"""Enforce unique basenames across `tests/`.

pytest's default `prepend` import mode imports collected test files as
top-level modules. When two files share a basename, the second import
clobbers the first and pytest fails collection with an error like:

    imported module 'test_exceptions' has this __file__ attribute:
      .../tests/_mcp/server/test_exceptions.py
    which is not the same as the test file we want to collect:
      .../tests/_runtime/test_exceptions.py

This script walks `tests/` and fails if any basename appears more than
once. Paths matched by pytest's `--ignore` list in pyproject.toml are
skipped (they hold fixture modules imported by name, not real tests).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = REPO_ROOT / "tests"

# Mirror of `--ignore ...` entries in `[tool.pytest.ini_options].addopts`
# in pyproject.toml. Keep in sync if that list changes.
IGNORED_PREFIXES = (
    REPO_ROOT / "tests" / "_cli" / "fixtures",
    REPO_ROOT / "tests" / "_ast" / "codegen_data",
    REPO_ROOT / "tests" / "_ast" / "app_data",
)


def is_ignored(path: Path) -> bool:
    return any(
        prefix in path.parents or path == prefix
        for prefix in IGNORED_PREFIXES
    )


def main() -> int:
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in TESTS_ROOT.rglob("test_*.py"):
        if is_ignored(path):
            continue
        by_name[path.name].append(path)

    duplicates = {n: ps for n, ps in by_name.items() if len(ps) > 1}
    if not duplicates:
        return 0

    print("Duplicate test filenames found in tests/:", file=sys.stderr)
    print(
        "(pytest's default import mode requires unique basenames; "
        "rename one of each pair below)",
        file=sys.stderr,
    )
    for name in sorted(duplicates):
        print(f"\n  {name}", file=sys.stderr)
        for path in sorted(duplicates[name]):
            print(f"    {path.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
