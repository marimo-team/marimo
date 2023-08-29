# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin


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
    return Html(
        build_stateless_plugin(
            component_name="marimo-callout-output",
            args={"html": as_html(value).text, "kind": kind},
        )
    )
