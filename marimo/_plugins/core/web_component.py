# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import uuid
from typing import Mapping, Optional, Sequence, TypeVar, Union

from typing_extensions import TypeAlias

from marimo._output.md import md
from marimo._output.mime import MIME

JSONType: TypeAlias = Union[
    Mapping[str, "JSONType"],
    Sequence["JSONType"],
    str,
    int,
    float,
    bool,
    MIME,  # MIME is a JSONType since we have a custom JSONEncoder for it
    None,
]


S = TypeVar("S", bound=JSONType)


class _AttributeBuilder:
    def __init__(self) -> None:
        self._attrs: list[str] = []
        self.data_store: dict[str, JSONType] = {}

    def add(self, name: str, value: Optional[S]) -> None:
        short_uuid = uuid.uuid4().hex[:6]
        if value is not None:
            self.data_store[short_uuid] = value
            self._attrs.append(f"data-{name}='{short_uuid}'")

    def build(self) -> str:
        return " ".join(self._attrs)


def build_ui_plugin(
    component_name: str,
    initial_value: Optional[JSONType],
    label: Optional[str],
    args: dict[str, JSONType],
    slotted_html: str = "",
) -> (str, dict[str, JSONType]):
    """
    Build HTML for a UI (stateful) plugin.

    Args:
    ----
    component_name: tag name of the component
    initial_value: JSON-serializable initial value of the component
    label: markdown string that component may use a text label
    args: mapping from arg names to JSON-serializable value
    slotted_html: HTML to slot in the component

    Returns:
    -------
    HTML text for the component and a dictionary
    of data locator IDs to their values
    """
    if "initial-value" in args:
        raise ValueError("initial-value is a reserved argument.")
    if "label" in args:
        raise ValueError("label is a reserved argument.")

    attrs = _AttributeBuilder()
    attrs.add("initial-value", initial_value)
    if label:
        attrs.add("label", md(label).text)

    for name, value in args.items():
        attrs.add(name, value)

    return (
        f"<{component_name} {attrs.build()}>"
        f"{slotted_html}"
        f"</{component_name}>",
        attrs.data_store,
    )


def build_stateless_plugin(
    component_name: str,
    args: dict[str, JSONType],
    slotted_html: str = "",
) -> (str, dict[str, JSONType]):
    """
    Build HTML for a stateless plugin.

    Args:
    ----
    component_name: tag name of the component
    args: mapping from arg names to JSON-serializable value
    slotted_html: HTML to slot in the component

    Returns:
    -------
    HTML text for the component and a dictionary
    of data locator IDs to their values
    """
    attrs = _AttributeBuilder()
    for name, value in args.items():
        attrs.add(name, value)
    return (
        f"<{component_name} {attrs.build()}>"
        f"{slotted_html}"
        f"</{component_name}>",
        attrs.data_store,
    )
