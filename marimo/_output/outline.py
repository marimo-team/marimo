# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin


@mddoc
def outline(*, label: str = "") -> Html:
    """Display a table of contents outline showing all markdown headers in the notebook.

    The outline automatically extracts all markdown headers from executed cells
    and displays them in a hierarchical structure with clickable navigation.

    Examples:
        Basic outline:
        ```python
        mo.outline()
        ```

        With custom label:
        ```python
        mo.outline(label="Table of Contents")
        ```

    Args:
        label (str, optional): A descriptive label for the outline. Defaults to "".

    Returns:
        Html: An HTML object that renders the outline component.
    """
    return Html(
        build_stateless_plugin(
            component_name="marimo-outline",
            args={"label": label},
        )
    )
