from __future__ import annotations

import importlib
from pathlib import Path

from tests.mocks import snapshotter
from tests.utils import explore_module

snapshot = snapshotter(__file__)


def test_internal_api():
    # Get all Python files and folders in marimo/_internal
    internal_path = (
        Path(__file__).parent.parent.parent / "marimo" / "_internal"
    )

    # Get both .py files and directories
    items = []
    for item in sorted(internal_path.iterdir()):
        if item.name.startswith("_"):
            continue
        if item.is_file() and item.suffix == ".py":
            items.append((item.stem, False))
        elif item.is_dir():
            items.append((item.name, True))

    all_results = []
    for name, _is_dir in items:
        # Import the module dynamically
        module_name = f"marimo._internal.{name}"
        module = importlib.import_module(module_name)

        # Explore the module
        results = explore_module(module)
        if results:
            all_results.append(name)
            all_results.extend([f"  {line}" for line in results])

    assert len(all_results) > 0
    snapshot("internal_api.txt", "\n".join(all_results))
