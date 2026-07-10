# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Any

_WIDGET_REF_PREFIX = "anywidget:"


def _is_anywidget_state(value: Any) -> bool:
    """Return whether an opening model state belongs to an anywidget."""
    return isinstance(value, dict) and (
        "_esm" in value or value.get("_model_module") == "anywidget"
    )


def _try_get_widget_model_id(value: Any) -> str | None:
    """Return the model id of a value if it looks like an anywidget.

    Detects ipywidgets-derived `AnyWidget` instances through `model_id` and
    protocol-based widgets through anywidget's `MimeBundleDescriptor`.
    Accessing the descriptor intentionally opens the child's comm when it has
    not been displayed independently.
    """
    model_id = getattr(value, "model_id", None)
    if isinstance(model_id, str) and model_id:
        return model_id

    # A descriptor-backed widget can only exist after this module has been
    # imported. Reuse it instead of importing an optional dependency while
    # inspecting arbitrary state values. A failed submodule import can leave a
    # partial `anywidget` module in `sys.modules`.
    descriptor_module = sys.modules.get("anywidget._descriptor")
    if descriptor_module is None:
        return None
    descriptor_type = getattr(descriptor_module, "MimeBundleDescriptor", None)
    repr_type = getattr(descriptor_module, "ReprMimeBundle", None)
    if not isinstance(descriptor_type, type) or not isinstance(
        repr_type, type
    ):
        return None

    bundle = getattr(value, "_repr_mimebundle_", None)
    if isinstance(bundle, descriptor_type):
        descriptor_get = getattr(bundle, "__get__", None)
        if not callable(descriptor_get):
            return None
        bundle = descriptor_get(value, type(value))
    if isinstance(bundle, repr_type):
        bundle_id = getattr(bundle, "model_id", None)
        if not isinstance(bundle_id, str) or not bundle_id:
            comm = getattr(bundle, "_comm", None)
            bundle_id = getattr(comm, "comm_id", None)
        if isinstance(bundle_id, str) and bundle_id:
            return bundle_id
    return None


def _replace_widget_refs(value: Any) -> Any:
    """Recursively replace anywidget instances with wire-format references.

    Walks dictionaries, lists, and tuples. Returns a new container when a
    replacement occurs and otherwise preserves the original container's
    identity.
    """
    model_id = _try_get_widget_model_id(value)
    if model_id is not None:
        return f"{_WIDGET_REF_PREFIX}{model_id}"
    if isinstance(value, dict):
        replaced = {k: _replace_widget_refs(v) for k, v in value.items()}
        if all(replaced[k] is value[k] for k in value):
            return value
        return replaced
    if isinstance(value, list):
        replaced_list = [_replace_widget_refs(v) for v in value]
        if all(a is b for a, b in zip(replaced_list, value, strict=True)):
            return value
        return replaced_list
    if isinstance(value, tuple):
        replaced_tuple = tuple(_replace_widget_refs(v) for v in value)
        if all(a is b for a, b in zip(replaced_tuple, value, strict=True)):
            return value
        return replaced_tuple
    return value


class AnyWidgetStateSerializer:
    """Serialize widget references for one anywidget comm.

    Classification happens once from the complete opening state. Subsequent
    updates are partial and therefore cannot reliably identify the model on
    their own.
    """

    def __init__(self, initial_state: Any) -> None:
        self._enabled = _is_anywidget_state(initial_state)

    def serialize(self, state: Any) -> Any:
        """Replace widget references when this comm belongs to an anywidget."""
        if not self._enabled:
            return state
        return _replace_widget_refs(state)
