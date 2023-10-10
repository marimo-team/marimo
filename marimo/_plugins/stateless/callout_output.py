# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._runtime.context import get_context
from marimo._runtime.data_store import UIDataLifecycleItem


@mddoc
def callout(
    value: object,
    kind: Literal["neutral", "warn", "success", "info", "danger"] = "neutral",
) -> Html:
    """Build a callout output.

    **Args.**

    - `value`: A value to render in the callout
    - `kind`: The kind of callout (affects styling).

    **Returns.**

    - An HTML object.
    """
    text, data_store = build_stateless_plugin(
        component_name="marimo-callout-output",
        args={"html": as_html(value).text, "kind": kind},
    )
    # TODO: probably not the right place to set this
    get_context().cell_lifecycle_registry.add(UIDataLifecycleItem(data_store))
    return Html(text)
