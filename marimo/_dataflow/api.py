# Copyright 2026 Marimo. All rights reserved.
"""Public declarative API for dataflow inputs, outputs, and triggers.

`mo.api.input(...)` produces a configured `mo.ui` element that doubles as
both an interactive control (when the notebook runs in an editor) and a
remote-controllable input (when served via the dataflow API).

A notebook with `mo.api.input(...)` declarations is a fully runnable marimo
notebook on its own; the dataflow API just promotes those UI elements to
externally addressable inputs.

Usage:

    import marimo as mo

    @app.cell
    def _():
        threshold = mo.api.input(min=0, max=100, default=50)
        category = mo.api.input(options=["all", "A", "B"], default="all")
        return threshold, category
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from marimo._plugins.ui._core.ui_element import UIElement


# Sentinel attribute marking a UI element as an exposed dataflow input.
# Used by the schema introspector to find inputs in the kernel's UI registry.
DATAFLOW_INPUT_MARKER = "_dataflow_input_metadata"


@_dataclass(frozen=True)
class _InputMetadata:
    """Metadata attached to a `mo.api.input(...)` UI element.

    Carried as `element._dataflow_input_metadata` so the schema introspector
    can identify this element as a dataflow input and read its declared
    description / kind hint without re-parsing the call site.
    """

    description: str | None = None
    kind_hint: str | None = None
    constraints: dict[str, Any] = _field(default_factory=dict)


@_dataclass(frozen=True)
class _OutputAnnotation:
    """Metadata for a dataflow output variable.

    Returned by `mo.api.output(...)` and used inside `typing.Annotated`.
    Treat as opaque; the public construction API is `mo.api.output(...)`.
    """

    kind: str | None = None
    description: str | None = None
    accepts: list[str] | None = None


@_dataclass(frozen=True)
class _TriggerAnnotation:
    """Metadata for a side-effect trigger.

    Returned by `mo.api.trigger(...)` and used as a decorator. Treat as
    opaque; the public construction API is `mo.api.trigger(...)`.
    """

    description: str | None = None

    def __call__(self, func: Any) -> Any:
        if not hasattr(func, "__dataflow_annotations__"):
            func.__dataflow_annotations__ = []
        func.__dataflow_annotations__.append(self)
        return func




def input(  # noqa: A001 - matches public name `mo.api.input`
    *,
    default: Any = None,
    min: Any = None,  # noqa: A002
    max: Any = None,  # noqa: A002
    step: Any = None,
    options: Sequence[Any] | None = None,
    multiline: bool = False,
    description: str | None = None,
    label: str | None = None,
    ui: UIElement[Any, Any] | None = None,
) -> UIElement[Any, Any]:
    """Declare an exposed input for the dataflow API.

    Returns a `mo.ui.*` element that doubles as an interactive control in the
    editor and a remote-controllable input via `POST /api/v1/dataflow/run`.

    The kind of UI element is inferred from the kwargs:

    - `min` and `max` (numeric) → `mo.ui.slider`
    - `min` or `max` only → `mo.ui.number`
    - `options=[...]` → `mo.ui.dropdown`
    - `default=bool` → `mo.ui.switch`
    - `multiline=True` → `mo.ui.text_area`
    - `default=str` → `mo.ui.text`

    Pass `ui=mo.ui.<some_element>(...)` to use a specific element verbatim;
    the other kwargs are ignored in that case.

    Args:
        default: Default value when no override is provided.
        min: Minimum value (numeric inputs).
        max: Maximum value (numeric inputs).
        step: Step size (numeric inputs).
        options: Allowed values (dropdown).
        multiline: If True, use a text area instead of a single-line input.
        description: Human-readable description for the schema.
        label: Markdown label rendered next to the control.
        ui: An explicit `mo.ui.*` element to use instead of inferring one.

    Returns:
        A configured `mo.ui.*` element marked as a dataflow input.
    """
    from marimo import ui as mo_ui

    label_str = label if label is not None else (description or "")

    element: UIElement[Any, Any]
    constraints: dict[str, Any] = {}

    if ui is not None:
        element = ui
    elif options is not None:
        element = mo_ui.dropdown(
            options=list(options),
            value=default if default is not None else None,
            label=label_str,
        )
        constraints["options"] = list(options)
    elif isinstance(default, bool):
        element = mo_ui.switch(value=default, label=label_str)
    elif min is not None and max is not None:
        element = mo_ui.slider(
            start=min,
            stop=max,
            step=step,
            value=default,
            label=label_str,
            show_value=True,
        )
        constraints["min"] = min
        constraints["max"] = max
        if step is not None:
            constraints["step"] = step
    elif min is not None or max is not None or isinstance(default, (int, float)):
        element = mo_ui.number(
            start=min,
            stop=max,
            step=step,
            value=default,
            label=label_str,
        )
        if min is not None:
            constraints["min"] = min
        if max is not None:
            constraints["max"] = max
    elif multiline:
        element = mo_ui.text_area(value=default or "", label=label_str)
    else:
        element = mo_ui.text(value=default or "", label=label_str)

    metadata = _InputMetadata(
        description=description,
        kind_hint=None,
        constraints=constraints,
    )
    setattr(element, DATAFLOW_INPUT_MARKER, metadata)
    return element


def output(
    *,
    kind: str | None = None,
    description: str | None = None,
    accepts: list[str] | None = None,
) -> _OutputAnnotation:
    """Annotation for a dataflow output variable.

    Use with `typing.Annotated`:

        result: Annotated[dict, mo.api.output(description="Stats")]

    Args:
        kind: Logical kind of the output (e.g. "table", "image").
        description: Human-readable description for the schema.
        accepts: Wire encodings the server can produce for this variable.
    """
    return _OutputAnnotation(
        kind=kind, description=description, accepts=accepts
    )


def trigger(*, description: str | None = None) -> _TriggerAnnotation:
    """Decorator marking a side-effect cell as an explicitly invokable trigger.

    Args:
        description: Human-readable description of the side effect.
    """
    return _TriggerAnnotation(description=description)
