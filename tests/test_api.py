from __future__ import annotations

import inspect
from typing import Any, Optional

from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def _explore_module(
    module: Any, indent: int = 0, visited: Optional[set[int]] = None
) -> list[str]:
    """
    Recursively explore a module and print all public exported items.

    Args:
        module: The module or object to explore
        indent: Current indentation level (for pretty printing)
        visited: Set[int] = set()
    """
    if visited is None:
        visited = set()

    # Skip if we've already visited this object
    if id(module) in visited:
        return []

    visited.add(id(module))

    results: list[str] = []
    # Get all attributes of the module
    for name, obj in inspect.getmembers(module):
        # Skip private/special attributes (starting with _)
        if name.startswith("_"):
            continue

        # Create indentation string
        indent_str = "  " * indent

        # Print the current item
        results.append(f"{indent_str}{name}")

        # Recursively explore if it's a module, class, or other container type
        if inspect.ismodule(obj) and obj.__name__.startswith(module.__name__):
            # Only recurse into submodules of the original module
            results.extend(_explore_module(obj, indent + 1, visited))

    return results


def test_api():
    import marimo as mo

    results = _explore_module(mo)
    assert len(results) > 0
    snapshot("api.txt", "\n".join(results))
