# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any


def _merge_key(
    original: dict[Any, Any],
    update: dict[Any, Any],
    key: str,
    replace_paths: frozenset[str],
    current_path: str,
) -> Any:
    # Precondition: key is in at least one of original and update
    path = f"{current_path}.{key}" if current_path else key

    if key not in update:
        # keep keys in original if they aren't in the update
        return original[key]
    elif key not in original:
        # new keys in update get added to original
        return update[key]
    elif path in replace_paths:
        # Use merge-replace behavior:
        # - Keys come from UPDATE only (so deletions work)
        # - But each key's value is merged with original (so partial updates
        #   preserve unmodified fields like api_key)
        if isinstance(original[key], dict) and isinstance(update[key], dict):
            return _merge_replace(original[key], update[key])
        return update[key]
    elif isinstance(original[key], dict) and isinstance(update[key], dict):
        # both dicts, so recurse
        return deep_merge(
            original[key], update[key], replace_paths, current_path=path
        )
    else:
        # key is present in both original and update, but values are not
        # both dicts; just take the update value.
        return update[key]


def _merge_replace(
    original: dict[Any, Any], update: dict[Any, Any]
) -> dict[Any, Any]:
    """Merge-replace: keys from update, but merge each value with original.

    This handles record-type dicts like custom_providers where:
    - Deleting a record works (key not in update = deleted)
    - Editing a record preserves unmodified fields (values are merged)
    """
    result = {}
    for key in update:
        if (
            key in original
            and isinstance(original[key], dict)
            and isinstance(update[key], dict)
        ):
            # Merge the record's fields (original first, update overwrites)
            result[key] = {**original[key], **update[key]}
        else:
            result[key] = update[key]
    return result


def deep_merge(
    original: dict[Any, Any],
    update: dict[Any, Any],
    replace_paths: frozenset[str] | None = None,
    current_path: str = "",
) -> dict[Any, Any]:
    """Deep merge of two dicts.

    Args:
        original: The original dict.
        update: The dict to merge into the original.
        replace_paths: Optional set of dot-separated paths that use
            merge-replace behavior. For these paths:
            - Keys come from update only (so deletions work)
            - Each key's value is merged with original (so partial updates
              preserve unmodified fields like masked api_key)
            Example: {"ai.custom_providers"}
        current_path: Internal parameter for tracking the current path during
            recursion.

    Returns:
        A new dict with the merged values.
    """
    if replace_paths is None:
        replace_paths = frozenset()

    return {
        key: _merge_key(original, update, key, replace_paths, current_path)
        for key in set(original.keys()).union(set(update.keys()))
    }
