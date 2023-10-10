# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import JSONType, build_stateless_plugin
from marimo._runtime.context import get_context
from marimo._runtime.data_store import UIDataLifecycleItem


def json_output(json_data: JSONType, name: Optional[str] = None) -> Html:
    """Build a json output element.

    Args:
    -----
    json_data: JSON-serializable data to display
    name: optional text label

    Returns:
    --------
    A string of HTML for a JSON output element.
    """
    text, data_store = build_stateless_plugin(
        component_name="marimo-json-output",
        args={"json-data": json_data, "name": name}
        if name is not None
        else {"json-data": json_data},
    )
    # TODO: probably not the right place to set this
    get_context().cell_lifecycle_registry.add(UIDataLifecycleItem(data_store))
    return Html(text)
