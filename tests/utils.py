from __future__ import annotations

import inspect
import time
from typing import TYPE_CHECKING, Any, Optional

from marimo._messaging.msgspec_encoder import (
    asdict,
    encode_json_bytes,
)
from marimo._utils.parse_dataclass import parse_raw

if TYPE_CHECKING:
    from typing import Callable

    import msgspec


def try_assert_n_times(n: int, assert_fn: Callable[[], None]) -> None:
    """Attempt an assert multiple times.

    Sleeps between each attempt.
    """
    n_tries = 0
    while n_tries <= n - 1:
        try:
            assert_fn()
            return
        except Exception:
            n_tries += 1
            time.sleep(0.1)
    assert_fn()


def assert_serialize_roundtrip(obj: msgspec.Struct) -> None:
    serialized = encode_json_bytes(obj)
    cls = type(obj)
    parsed = parse_raw(serialized, cls)
    assert asdict(obj) == asdict(parsed), f"{asdict(obj)} != {asdict(parsed)}"


def explore_module(
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
            results.extend(explore_module(obj, indent + 1, visited))

    return results
