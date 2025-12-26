# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, Any, Union

from marimo._messaging.notification import VariableValue
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def get_variable_preview(
    obj: Any,
    max_items: int = 5,
    max_str_len: int = 50,
    max_bytes: int = 32,
    _depth: int = 0,
    _seen: set[int] | None = None,
) -> str:
    """
    Generate a preview string for any Python object.

    Args:
        obj: Any Python object
        max_items: Maximum number of items to show for sequences/mappings
        max_str_len: Maximum length for string previews
        max_bytes: Maximum number of bytes to show for binary data
        _depth: Internal parameter to track recursion depth
        _seen: Set to track circular references

    Returns:
        str: A preview string
    """
    if _seen is None:
        _seen = set()

    # Check for circular references
    obj_id = id(obj)
    if obj_id in _seen:
        return f"<circular reference: {type(obj).__name__}>"

    # Track mutable objects that could be circular
    if isinstance(obj, (list, dict, set, tuple)):
        _seen.add(obj_id)

    # Add max recursion depth
    MAX_DEPTH = 5
    if _depth > MAX_DEPTH:
        return f"<max depth reached: {type(obj).__name__}>"

    def truncate_str(s: str, max_len: int) -> str:
        return s if len(s) <= max_len else s[:max_len]

    def preview_sequence(
        seq: Union[Sequence[Any], set[Any], frozenset[Any]],
    ) -> str:
        # Convert set-like objects to list for indexing
        if isinstance(seq, (set, frozenset)):
            seq = list(seq)

        length = len(seq)
        if length <= max_items:
            items = [
                get_variable_preview(
                    x, max_items // 2, _depth=_depth + 1, _seen=_seen
                )
                for x in seq
            ]
        else:
            half = max_items // 2
            first = [
                get_variable_preview(
                    x, max_items // 2, _depth=_depth + 1, _seen=_seen
                )
                for x in seq[:half]
            ]
            last = [
                get_variable_preview(
                    x, max_items // 2, _depth=_depth + 1, _seen=_seen
                )
                for x in seq[-half:]
            ]
            items = first + ["..."] + last
        return f"[{', '.join(items)}]"

    def preview_mapping(d: Mapping[Any, Any]) -> str:
        length = len(d)
        if length <= max_items:
            items = [
                f"{get_variable_preview(k, max_items // 2, _depth=_depth + 1, _seen=_seen)}: {get_variable_preview(v, max_items // 2, _depth=_depth + 1, _seen=_seen)}"
                for k, v in d.items()
            ]
        else:
            half = max_items // 2
            items = (
                [
                    f"{get_variable_preview(k, max_items // 2, _depth=_depth + 1, _seen=_seen)}: {get_variable_preview(v, max_items // 2, _depth=_depth + 1, _seen=_seen)}"
                    for k, v in list(d.items())[:half]
                ]
                + ["..."]
                + [
                    f"{get_variable_preview(k, max_items // 2, _depth=_depth + 1, _seen=_seen)}: {get_variable_preview(v, max_items // 2, _depth=_depth + 1, _seen=_seen)}"
                    for k, v in list(d.items())[-half:]
                ]
            )
        return f"{{{', '.join(items)}}}"

    def preview_bytes(data: bytes | bytearray) -> str:
        length = len(data)
        if length <= max_bytes:
            preview = data.hex()
        else:
            half = max_bytes // 2
            preview = f"{data[:half].hex()}...{data[-half:].hex()}"
        return f"<{length} bytes: {preview}>"

    # Get type name
    type_name = type(obj).__name__

    try:
        # Handle None
        if obj is None:
            return "None"

        # Handle basic types
        elif isinstance(obj, (bool, int, float, complex)):
            return str(obj)

        # Handle strings
        elif isinstance(obj, str):
            return f"'{truncate_str(obj, max_str_len)}'"

        # Handle bytes and bytearray
        elif isinstance(obj, (bytes, bytearray)):
            return f"{type_name}{preview_bytes(obj)}"

        # Handle lists, tuples, sets
        elif isinstance(obj, (list, tuple, set, frozenset)):
            preview = preview_sequence(obj)
            if isinstance(obj, (set, frozenset)):
                preview = f"{{{preview[1:-1]}}}"
            elif isinstance(obj, tuple):
                preview = f"({preview[1:-1]})"
            return preview

        # Handle dictionaries
        elif isinstance(obj, dict):
            return preview_mapping(obj)

        # Handle dataframes
        table_manager = get_table_manager_or_none(obj)
        if table_manager is not None:
            return str(table_manager)

        # Handle common standard library types
        elif hasattr(obj, "__dict__"):
            return f"<{type_name} object at {hex(id(obj))}>"

        # Fallback for other types
        else:
            try:
                preview = str(obj)
                return truncate_str(preview, max_str_len)
            except Exception:
                return f"<unprintable {type_name} object>"

    except Exception as e:
        return f"<error previewing {type_name}: {str(e)}>"


def _stringify_variable_value(value: object) -> str:
    """Convert a value to its string representation.

    Limits string length and handles objects that may have expensive __str__.
    """
    MAX_STR_LEN = 50

    if isinstance(value, str):
        if len(value) > MAX_STR_LEN:
            return value[:MAX_STR_LEN]
        return value

    try:
        # str(value) can be slow for large objects
        # or lead to large memory spikes
        return get_variable_preview(value, max_str_len=MAX_STR_LEN)
    except BaseException:
        # Catch-all: some libraries like Polars have bugs and raise
        # BaseExceptions, which shouldn't crash the kernel
        return "<UNKNOWN>"


def _format_variable_value(value: object) -> str:
    """Format a variable value for display.

    Handles special types like UIElement, Html, and ModuleType.
    """

    from marimo._output.hypertext import Html
    from marimo._plugins.ui._core.ui_element import UIElement

    resolved = value
    if isinstance(value, UIElement):
        resolved = value.value
    elif isinstance(value, Html):
        resolved = value.text
    elif isinstance(value, ModuleType):
        resolved = value.__name__
    return _stringify_variable_value(resolved)


def create_variable_value(
    name: str, value: object, datatype: str | None = None
) -> VariableValue:
    """Factory function to create a VariableValue from an object.

    Args:
        name: Variable name
        value: Variable value (any Python object)
        datatype: Optional datatype override. If None, will be inferred.

    Returns:
        VariableValue with formatted value and datatype
    """
    # Defensively try-catch attribute accesses, which could raise exceptions
    # If datatype is already defined, don't try to infer it
    if datatype is None:
        try:
            computed_datatype = (
                type(value).__name__ if value is not None else None
            )
        except Exception:
            computed_datatype = datatype
    else:
        computed_datatype = datatype

    try:
        formatted_value = _format_variable_value(value)
    except Exception:
        formatted_value = None

    return VariableValue(
        name=name, value=formatted_value, datatype=computed_datatype
    )
