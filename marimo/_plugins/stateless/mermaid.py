# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin


@mddoc
def mermaid(diagram: str) -> Html:
    """
    A Mermaid diagram.

    **Examples.**

    ```python
    diagram = '''
    graph LR
        A[Square Rect] -- Link text --> B((Circle))
        A --> C(Round Rect)
        B --> D{Rhombus}
        C --> D
    '''
    mo.mermaid(diagram)
    ```

    **Args.**

    - `diagram`: a string containing a Mermaid diagram

    **Returns.**

    - An `Html` object.
    """
    return Html(
        build_stateless_plugin(
            component_name="marimo-mermaid",
            args={"diagram": diagram},
        )
    )
